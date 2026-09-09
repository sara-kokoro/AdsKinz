"""The money engine: charging campaigns, paying publishers, taking commission.

Every billable event goes through :func:`charge_campaign`, which is the single
place where an advertiser's budget is decremented and where the 35% platform
commission is split out. Concurrency is handled with a Redis lock plus a
conditional SQL update, so a campaign can never be charged past its budget even
when several workers bill it at the same time.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload

from app.config import settings
from app.core.enums import CampaignStatus, LedgerEntryType
from app.core.errors import InsufficientBalanceError
from app.models.accounts import Advertiser, LedgerEntry, Publisher
from app.models.campaigns import Campaign, CampaignDailySpend, utc_today
from app.models.finance import PlatformRevenue
from app.models.placements import Channel, MiniApp, PlacementDailyStat
from app.redis_client import distributed_lock
from app.services import email_service

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")
MICRO = Decimal("0.000001")


def q6(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MICRO, rounding=ROUND_DOWN)


def q2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_DOWN)


def impression_cost(cpm_bid: Decimal, views: int = 1) -> Decimal:
    """CPM means "cost per mille": one view costs ``cpm / 1000``."""
    return q6(Decimal(cpm_bid) * Decimal(views) / Decimal(1000))


@dataclass(slots=True)
class ChargeResult:
    charged: Decimal
    commission: Decimal
    publisher_share: Decimal
    billed_units: int
    campaign_exhausted: bool
    skipped_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.charged > 0


# --------------------------------------------------------------------------- #
# Ledger
# --------------------------------------------------------------------------- #
def add_ledger_entry(
    session: AsyncSession,
    *,
    account_type: str,
    account_id: uuid.UUID | None,
    entry_type: str,
    amount: Decimal,
    balance_after: Decimal | None = None,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
    description: str | None = None,
) -> LedgerEntry:
    entry = LedgerEntry(
        account_type=account_type,
        account_id=account_id,
        entry_type=entry_type,
        amount_usd=q6(amount),
        balance_after_usd=balance_after,
        reference_type=reference_type,
        reference_id=reference_id,
        description=description,
    )
    session.add(entry)
    return entry


# --------------------------------------------------------------------------- #
# Funding / refunding a campaign's isolated budget
# --------------------------------------------------------------------------- #
async def fund_campaign(
    session: AsyncSession,
    *,
    advertiser: Advertiser,
    campaign: Campaign,
    amount: Decimal,
) -> None:
    """Move ``amount`` out of the wallet into this campaign's isolated budget.

    This is the only place a campaign's ``total_budget`` grows. Once funded,
    that money is reserved for this campaign alone — ``charge_campaign`` never
    touches ``advertiser.balance_usd`` again.
    """
    amount = q2(amount)
    if amount <= 0:
        return
    if amount > Decimal(advertiser.balance_usd):
        raise InsufficientBalanceError(
            f"Your wallet balance (${advertiser.balance_usd}) is lower than the "
            f"${amount} you're trying to add to this campaign. Top up your "
            f"wallet first."
        )
    advertiser.balance_usd = q2(Decimal(advertiser.balance_usd) - amount)
    campaign.total_budget = q2(Decimal(campaign.total_budget) + amount)
    add_ledger_entry(
        session,
        account_type="advertiser",
        account_id=advertiser.id,
        entry_type=LedgerEntryType.CAMPAIGN_TOPUP.value,
        amount=-amount,
        balance_after=advertiser.balance_usd,
        reference_type="campaign",
        reference_id=campaign.id,
        description=f"Funded campaign {campaign.name}",
    )


async def refund_campaign(
    session: AsyncSession,
    *,
    advertiser: Advertiser,
    campaign: Campaign,
    amount: Decimal,
) -> None:
    """Return unspent, isolated campaign budget to the advertiser's wallet.

    Used when a campaign is rejected, manually stopped, or has its budget
    reduced — never on a plain pause, which keeps the reserved money in place
    in case the campaign resumes.
    """
    amount = q2(amount)
    if amount <= 0:
        return
    advertiser.balance_usd = q2(Decimal(advertiser.balance_usd) + amount)
    campaign.total_budget = q2(Decimal(campaign.total_budget) - amount)
    add_ledger_entry(
        session,
        account_type="advertiser",
        account_id=advertiser.id,
        entry_type=LedgerEntryType.CAMPAIGN_REFUND.value,
        amount=amount,
        balance_after=advertiser.balance_usd,
        reference_type="campaign",
        reference_id=campaign.id,
        description=f"Refunded unspent budget from {campaign.name}",
    )


# --------------------------------------------------------------------------- #
# Charging a campaign
# --------------------------------------------------------------------------- #
async def charge_campaign(
    session: AsyncSession,
    *,
    campaign: Campaign,
    amount: Decimal,
    units: int,
    event_type: str,
    placement_type: str | None = None,
    placement_id: uuid.UUID | None = None,
) -> ChargeResult:
    """Debit ``amount`` from the campaign budget and the advertiser balance.

    The amount is clamped to whichever is smaller: the campaign's remaining
    budget, its remaining daily budget, and the advertiser's balance. Returns a
    :class:`ChargeResult` describing what was actually billed — callers must
    honour ``charged`` rather than assuming the full amount went through.
    """
    amount = q6(amount)
    if amount <= 0 or units <= 0:
        return ChargeResult(Decimal("0"), Decimal("0"), Decimal("0"), 0, False, "zero_amount")

    lock_key = f"campaign_charge:{campaign.id}"
    async with distributed_lock(lock_key, timeout=settings.LOCK_TIMEOUT_SECONDS) as acquired:
        # `acquired` is only ever False in two cases: Redis is unreachable
        # (nothing to skip — proceed and rely on the row-level lock below),
        # or another worker genuinely holds this campaign's lock right now.
        # Both are handled the same way: `with_for_update=True` on the next
        # line blocks until it can safely read+write this row, so there is
        # no correctness gap either way — only a skip-and-hope-the-next-
        # event-catches-it path here, which is what was silently losing
        # every view when Redis wasn't configured (see distributed_lock's
        # own docstring: "the caller must rely on the database-level
        # guarantee instead").
        # Campaign.advertiser is lazy="joined" by default, which turns this
        # into "FROM campaigns LEFT OUTER JOIN advertisers ... FOR UPDATE" —
        # Postgres refuses to lock the nullable side of an outer join
        # (asyncpg.exceptions.FeatureNotSupportedError). This call only
        # needs the Campaign row locked, not the advertiser eager-loaded, so
        # override the loader strategy just for this fetch.
        fresh = await session.get(
            Campaign, campaign.id, with_for_update=True, options=[lazyload(Campaign.advertiser)]
        )
        if fresh is None:
            return ChargeResult(Decimal("0"), Decimal("0"), Decimal("0"), 0, False, "not_found")

        advertiser = await session.get(Advertiser, fresh.advertiser_id, with_for_update=True)
        if advertiser is None:
            return ChargeResult(Decimal("0"), Decimal("0"), Decimal("0"), 0, False, "no_advertiser")

        # The campaign's budget is isolated money, already moved out of the
        # wallet when it was funded — the wallet balance plays no part in how
        # much can be billed here anymore.
        remaining_total = q6(fresh.total_budget - fresh.spent_usd)
        billable = min(amount, remaining_total)

        # Daily cap, when the advertiser set one.
        if fresh.daily_budget:
            today = utc_today()
            spent_today = (
                await session.execute(
                    select(func.coalesce(CampaignDailySpend.amount_usd, 0)).where(
                        CampaignDailySpend.campaign_id == fresh.id,
                        CampaignDailySpend.spend_date == today,
                    )
                )
            ).scalar() or Decimal("0")
            remaining_daily = q6(Decimal(fresh.daily_budget) - Decimal(spent_today))
            billable = min(billable, max(Decimal("0"), remaining_daily))

        if billable <= 0:
            exhausted = remaining_total <= 0
            if exhausted and fresh.status == CampaignStatus.ACTIVE.value:
                fresh.status = CampaignStatus.STOPPED.value
            await session.commit()
            return ChargeResult(
                Decimal("0"), Decimal("0"), Decimal("0"), 0, exhausted,
                "budget_exhausted" if exhausted else "daily_cap_or_balance",
            )

        # Scale the billed units down if we could only bill part of the amount.
        billed_units = units if billable >= amount else max(1, int(units * (billable / amount)))

        commission = q6(billable * settings.PLATFORM_COMMISSION_RATE)
        publisher_share = q6(billable - commission)

        fresh.spent_usd = q6(fresh.spent_usd + billable)
        # Wallet balance is untouched here — it already left the wallet when
        # the campaign was funded. Only lifetime stats move.
        advertiser.lifetime_spend_usd = q2(advertiser.lifetime_spend_usd + billable)

        if event_type == "impression":
            fresh.impressions += billed_units
        elif event_type == "click":
            fresh.clicks += billed_units

        exhausted = q6(fresh.total_budget - fresh.spent_usd) <= 0
        if exhausted and fresh.status == CampaignStatus.ACTIVE.value:
            fresh.status = CampaignStatus.STOPPED.value

        await _bump_daily_spend(session, fresh.id, billable, event_type, billed_units)

        session.add(
            PlatformRevenue(
                source_type="campaign_spend",
                source_id=fresh.id,
                gross_amount_usd=billable,
                commission_amount_usd=commission,
                publisher_amount_usd=publisher_share,
                event_type=event_type,
                placement_type=placement_type,
                placement_id=placement_id,
            )
        )
        add_ledger_entry(
            session,
            # Spend now mutates the campaign's own isolated pot, not the
            # wallet — so this entry is logged against the campaign account,
            # with balance_after reflecting what's left of *that* pot.
            account_type="campaign",
            account_id=fresh.id,
            entry_type=LedgerEntryType.CAMPAIGN_SPEND.value,
            amount=-billable,
            balance_after=q6(fresh.total_budget - fresh.spent_usd),
            reference_type="campaign",
            reference_id=fresh.id,
            description=f"{event_type} x{billed_units} on {fresh.name}",
        )

        if placement_type and placement_id and publisher_share > 0:
            await credit_publisher(
                session,
                placement_type=placement_type,
                placement_id=placement_id,
                amount=publisher_share,
                event_type=event_type,
                units=billed_units,
                campaign_id=fresh.id,
            )

        await maybe_send_campaign_low_balance_alert(fresh, advertiser)
        await session.commit()

    logger.info(
        "billing.charged campaign=%s amount=%s commission=%s event=%s units=%s",
        campaign.id, billable, commission, event_type, billed_units,
    )
    return ChargeResult(billable, commission, publisher_share, billed_units, exhausted)


async def _bump_daily_spend(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    amount: Decimal,
    event_type: str,
    units: int,
) -> None:
    """Upsert today's spend row without a read-modify-write race."""
    stmt = (
        pg_insert(CampaignDailySpend)
        .values(
            campaign_id=campaign_id,
            spend_date=utc_today(),
            amount_usd=amount,
            impressions=units if event_type == "impression" else 0,
            clicks=units if event_type == "click" else 0,
        )
        .on_conflict_do_update(
            index_elements=["campaign_id", "spend_date"],
            set_={
                "amount_usd": CampaignDailySpend.amount_usd + amount,
                "impressions": CampaignDailySpend.impressions
                + (units if event_type == "impression" else 0),
                "clicks": CampaignDailySpend.clicks
                + (units if event_type == "click" else 0),
            },
        )
    )
    await session.execute(stmt)


# --------------------------------------------------------------------------- #
# Crediting a publisher
# --------------------------------------------------------------------------- #
async def credit_publisher(
    session: AsyncSession,
    *,
    placement_type: str,
    placement_id: uuid.UUID,
    amount: Decimal,
    event_type: str,
    units: int,
    campaign_id: uuid.UUID | None = None,
) -> Publisher | None:
    """Add the publisher's 65% share to their available balance."""
    amount = q6(amount)
    if amount <= 0:
        return None

    if placement_type == "channel":
        placement = await session.get(Channel, placement_id)
    else:
        placement = await session.get(MiniApp, placement_id)
    if placement is None:
        return None

    publisher = await session.get(Publisher, placement.publisher_id, with_for_update=True)
    if publisher is None:
        return None

    publisher.available_balance_usd = q2(publisher.available_balance_usd + amount)
    publisher.lifetime_earnings_usd = q2(publisher.lifetime_earnings_usd + amount)

    placement.lifetime_earnings_usd = q2(placement.lifetime_earnings_usd + amount)
    if event_type == "impression":
        placement.lifetime_impressions += units

    await _bump_placement_daily(session, placement_type, placement_id, amount, event_type, units)

    add_ledger_entry(
        session,
        account_type="publisher",
        account_id=publisher.id,
        entry_type=LedgerEntryType.PUBLISHER_EARNING.value,
        amount=amount,
        balance_after=publisher.available_balance_usd,
        reference_type=placement_type,
        reference_id=placement_id,
        description=f"{event_type} x{units}",
    )
    return publisher


async def charge_premium(session: AsyncSession, *, publisher: Publisher) -> Publisher:
    """Debit PREMIUM_MONTHLY_PRICE_USD from the publisher's available
    balance and (re)activate premium for PREMIUM_PERIOD_DAYS. Extends from
    the current expiry if still active, otherwise from now."""
    price = q2(settings.PREMIUM_MONTHLY_PRICE_USD)
    if publisher.available_balance_usd < price:
        raise InsufficientBalanceError(
            f"Insufficient balance: ${publisher.available_balance_usd} available, "
            f"${price} required for premium."
        )

    publisher.available_balance_usd = q2(publisher.available_balance_usd - price)

    now = datetime.now(UTC)
    base = publisher.premium_expires_at if publisher.premium_expires_at and publisher.premium_expires_at > now else now
    publisher.premium_expires_at = base + timedelta(days=settings.PREMIUM_PERIOD_DAYS)
    publisher.is_premium = True

    add_ledger_entry(
        session,
        account_type="publisher",
        account_id=publisher.id,
        entry_type=LedgerEntryType.PREMIUM_CHARGE.value,
        amount=-price,
        balance_after=publisher.available_balance_usd,
        reference_type="premium_subscription",
        reference_id=publisher.id,
        description=f"Premium subscription, {settings.PREMIUM_PERIOD_DAYS} days",
    )
    return publisher


async def expire_premium(session: AsyncSession, *, publisher: Publisher) -> None:
    publisher.is_premium = False
    publisher.premium_auto_renew = False


async def _bump_placement_daily(
    session: AsyncSession,
    placement_type: str,
    placement_id: uuid.UUID,
    amount: Decimal,
    event_type: str,
    units: int,
) -> None:
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = (
        pg_insert(PlacementDailyStat)
        .values(
            placement_type=placement_type,
            placement_id=placement_id,
            stat_date=today,
            impressions=units if event_type == "impression" else 0,
            clicks=units if event_type == "click" else 0,
            earnings_usd=amount,
            ads_delivered=0,
        )
        .on_conflict_do_update(
            index_elements=["placement_type", "placement_id", "stat_date"],
            set_={
                "impressions": PlacementDailyStat.impressions
                + (units if event_type == "impression" else 0),
                "clicks": PlacementDailyStat.clicks + (units if event_type == "click" else 0),
                "earnings_usd": PlacementDailyStat.earnings_usd + amount,
            },
        )
    )
    await session.execute(stmt)


# --------------------------------------------------------------------------- #
# Deposits
# --------------------------------------------------------------------------- #
async def credit_deposit(
    session: AsyncSession,
    *,
    advertiser: Advertiser,
    net_amount: Decimal,
    reference_id: uuid.UUID,
    network: str,
) -> Decimal:
    """Credit a confirmed deposit and log it in the ledger."""
    net_amount = q2(net_amount)
    if net_amount <= 0:
        return Decimal("0.00")

    advertiser.balance_usd = q2(advertiser.balance_usd + net_amount)
    add_ledger_entry(
        session,
        account_type="advertiser",
        account_id=advertiser.id,
        entry_type=LedgerEntryType.DEPOSIT_CREDIT.value,
        amount=net_amount,
        balance_after=advertiser.balance_usd,
        reference_type="deposit",
        reference_id=reference_id,
        description=f"Deposit confirmed on {network}",
    )
    # A top-up may make previously paused campaigns servable again.
    advertiser.low_balance_alerted_at = None
    return advertiser.balance_usd


# --------------------------------------------------------------------------- #
# Withdrawals
# --------------------------------------------------------------------------- #
async def hold_withdrawal_funds(
    session: AsyncSession, *, publisher: Publisher, amount: Decimal, reference_id: uuid.UUID
) -> None:
    """Move funds from available to held when a request is created."""
    amount = q2(amount)
    if publisher.available_balance_usd < amount:
        raise InsufficientBalanceError(
            "Your available balance does not cover this withdrawal amount."
        )
    publisher.available_balance_usd = q2(publisher.available_balance_usd - amount)
    publisher.held_balance_usd = q2(publisher.held_balance_usd + amount)
    add_ledger_entry(
        session,
        account_type="publisher",
        account_id=publisher.id,
        entry_type=LedgerEntryType.WITHDRAWAL_HOLD.value,
        amount=-amount,
        balance_after=publisher.available_balance_usd,
        reference_type="withdrawal",
        reference_id=reference_id,
        description="Withdrawal requested",
    )


async def release_withdrawal_funds(
    session: AsyncSession, *, publisher: Publisher, amount: Decimal, reference_id: uuid.UUID
) -> None:
    """Return held funds to available when a request is rejected."""
    amount = q2(amount)
    publisher.held_balance_usd = q2(max(Decimal("0.00"), publisher.held_balance_usd - amount))
    publisher.available_balance_usd = q2(publisher.available_balance_usd + amount)
    add_ledger_entry(
        session,
        account_type="publisher",
        account_id=publisher.id,
        entry_type=LedgerEntryType.WITHDRAWAL_RELEASE.value,
        amount=amount,
        balance_after=publisher.available_balance_usd,
        reference_type="withdrawal",
        reference_id=reference_id,
        description="Withdrawal rejected, funds returned",
    )


async def settle_withdrawal(
    session: AsyncSession, *, publisher: Publisher, amount: Decimal, reference_id: uuid.UUID
) -> None:
    """Clear held funds once the payout has actually been sent."""
    amount = q2(amount)
    publisher.held_balance_usd = q2(max(Decimal("0.00"), publisher.held_balance_usd - amount))
    add_ledger_entry(
        session,
        account_type="publisher",
        account_id=publisher.id,
        entry_type=LedgerEntryType.WITHDRAWAL_SETTLE.value,
        amount=-amount,
        balance_after=publisher.available_balance_usd,
        reference_type="withdrawal",
        reference_id=reference_id,
        description="Withdrawal paid",
    )


# --------------------------------------------------------------------------- #
# Budget supervision
# --------------------------------------------------------------------------- #
async def committed_active_budget(session: AsyncSession, advertiser_id: uuid.UUID) -> Decimal:
    """Sum of remaining isolated budget across an advertiser's active campaigns.

    This money has already left the wallet (it was reserved when each
    campaign was funded) — this is purely informational: how much is
    currently locked up and still spendable by running campaigns.
    """
    total = (
        await session.execute(
            select(
                func.coalesce(func.sum(Campaign.total_budget - Campaign.spent_usd), 0)
            ).where(
                Campaign.advertiser_id == advertiser_id,
                Campaign.status == CampaignStatus.ACTIVE.value,
            )
        )
    ).scalar_one()
    return q2(Decimal(total or 0))


async def maybe_send_campaign_low_balance_alert(
    campaign: Campaign, advertiser: Advertiser
) -> bool:
    """Warn once when a single campaign's remaining budget drops under the
    per-campaign threshold (distinct from the advertiser-wide wallet alert).

    Resets automatically the next time the campaign is topped back up above
    the threshold, so a later dip can alert again. Caller is responsible for
    committing the session afterwards.
    """
    remaining = campaign.remaining_budget
    if remaining >= settings.CAMPAIGN_LOW_BALANCE_THRESHOLD:
        if campaign.low_balance_alerted_at is not None:
            campaign.low_balance_alerted_at = None
        return False

    if campaign.low_balance_alerted_at is not None:
        return False

    campaign.low_balance_alerted_at = datetime.now(UTC)
    return await email_service.send_campaign_low_balance(
        advertiser.email,
        campaign_name=campaign.name,
        remaining=q2(remaining),
        threshold=q2(settings.CAMPAIGN_LOW_BALANCE_THRESHOLD),
    )


async def apply_buffered_spend(session: AsyncSession, buffered: dict[str, Decimal]) -> int:
    """Flush the Redis spend buffer into ``campaigns.spent_usd``.

    High-frequency events accumulate in Redis first so the hot path stays fast;
    this job reconciles them into the durable store.
    """
    applied = 0
    for campaign_id, amount in buffered.items():
        if amount <= 0:
            continue
        result = await session.execute(
            update(Campaign)
            .where(Campaign.id == uuid.UUID(campaign_id))
            .values(spent_usd=Campaign.spent_usd + q6(amount))
        )
        applied += result.rowcount or 0
    if applied:
        await session.commit()
    return applied


def period_bounds(period: str, anchor: date | None = None) -> tuple[date, date]:
    """Resolve an admin finance period into an inclusive ``(start, end)``."""
    today = anchor or datetime.now(UTC).date()
    if period == "today":
        return today, today
    if period == "week":
        start = today - timedelta(days=today.weekday())
        return start, today
    if period == "month":
        return today.replace(day=1), today
    if period == "year":
        return today.replace(month=1, day=1), today
    return today, today

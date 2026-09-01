"""Admin back-office endpoints (kingcey.adskinz.io).

    GET  /admin/queue/campaigns|channels|mini-apps|withdrawals
    POST /admin/queue/campaigns/{id}/approve|reject
    POST /admin/queue/channels/{id}/approve|reject
    POST /admin/queue/mini-apps/{id}/approve|reject
    POST /admin/queue/withdrawals/{id}/approve|reject
    GET  /admin/finances?period=today|week|month|year|custom&date=YYYY-MM-DD
    GET  /admin/anomalies
    GET  /admin/audit
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from app.core.deps import ClientIPHashDep, CurrentAdminDep, PaginationDep, SessionDep
from app.core.enums import (
    AuditAction,
    CampaignStatus,
    ChannelStatus,
    DepositStatus,
    MiniAppStatus,
    WithdrawalStatus,
)
from app.core.errors import NotFoundError, ValidationError
from app.models.accounts import Advertiser, AdminUser, Publisher, RefreshToken
from app.models.campaigns import Campaign, campaign_format_to_frontend
from app.models.finance import Bep20Sweep, Deposit, PlatformRevenue, WalletAddress, Withdrawal
from app.models.placements import Channel, MiniApp
from app.models.tracking import Anomaly, AuditLog
from app.schemas.admin import (
    AdminOverviewResponse,
    AnomalyItem,
    AnomalyListResponse,
    ApproveRequest,
    AuditItem,
    AuditListResponse,
    Bep20SweepItem,
    Bep20SweepListResponse,
    Bep20SweepRetryResponse,
    BlockAccountRequest,
    FinanceSeriesPoint,
    FinancesResponse,
    FinanceTopEntry,
    ModerationActionResponse,
    QueueCampaignItem,
    QueueChannelItem,
    QueueMiniAppItem,
    QueueResponse,
    QueueWithdrawalItem,
)
from app.schemas.common import MessageResponse
from app.services import bep20_sweep_service, billing_service, moderation_service

router = APIRouter(prefix="/admin", tags=["admin"])


# --------------------------------------------------------------------------- #
# Queue counts
# --------------------------------------------------------------------------- #
async def _queue_counts(session: SessionDep) -> dict[str, int]:
    campaigns = (
        await session.execute(
            select(func.count())
            .select_from(Campaign)
            .where(Campaign.status == CampaignStatus.PENDING_REVIEW.value)
        )
    ).scalar_one()
    channels = (
        await session.execute(
            select(func.count())
            .select_from(Channel)
            .where(Channel.status == ChannelStatus.PENDING_MODERATION.value)
        )
    ).scalar_one()
    mini_apps = (
        await session.execute(
            select(func.count())
            .select_from(MiniApp)
            .where(MiniApp.status == MiniAppStatus.PENDING_MODERATION.value)
        )
    ).scalar_one()
    withdrawals = (
        await session.execute(
            select(func.count())
            .select_from(Withdrawal)
            .where(Withdrawal.status == WithdrawalStatus.PENDING.value)
        )
    ).scalar_one()
    return {
        "campaigns": int(campaigns or 0),
        "channels": int(channels or 0),
        "miniApps": int(mini_apps or 0),
        "withdrawals": int(withdrawals or 0),
    }


@router.get("/overview", response_model=AdminOverviewResponse, summary="Dashboard tiles")
async def overview(admin: CurrentAdminDep, session: SessionDep) -> AdminOverviewResponse:
    counts = await _queue_counts(session)

    async def _count(model, *conditions) -> int:
        value = (
            await session.execute(
                select(func.count()).select_from(model).where(*conditions)
            )
        ).scalar_one()
        return int(value or 0)

    open_anomalies = await _count(Anomaly, Anomaly.resolved.is_(False))
    active_campaigns = await _count(Campaign, Campaign.status == CampaignStatus.ACTIVE.value)
    active_channels = await _count(
        Channel,
        Channel.status.in_(
            [ChannelStatus.ACTIVE.value, ChannelStatus.ACTIVE_BUILDING_TRUST.value]
        ),
    )
    advertisers = await _count(Advertiser)
    publishers = await _count(Publisher)

    owed = (
        await session.execute(
            select(
                func.coalesce(func.sum(Publisher.available_balance_usd), 0)
                + func.coalesce(func.sum(Publisher.held_balance_usd), 0)
            )
        )
    ).scalar_one()
    commission_today = (
        await session.execute(
            select(func.coalesce(func.sum(PlatformRevenue.commission_amount_usd), 0)).where(
                func.date(PlatformRevenue.recorded_at) == datetime.now(UTC).date()
            )
        )
    ).scalar_one()

    return AdminOverviewResponse(
        pendingCampaigns=counts["campaigns"],
        pendingChannels=counts["channels"],
        pendingMiniApps=counts["miniApps"],
        pendingWithdrawals=counts["withdrawals"],
        openAnomalies=open_anomalies,
        activeCampaigns=active_campaigns,
        activeChannels=active_channels,
        advertisers=advertisers,
        publishers=publishers,
        balanceOwedToPublishers=Decimal(owed or 0),
        commissionToday=Decimal(commission_today or 0),
    )


# --------------------------------------------------------------------------- #
# Moderation queues
# --------------------------------------------------------------------------- #
@router.get("/queue/campaigns", response_model=QueueResponse, summary="Campaign queue")
async def queue_campaigns(
    admin: CurrentAdminDep, session: SessionDep, page: PaginationDep
) -> QueueResponse:
    rows = (
        (
            await session.execute(
                select(Campaign)
                .options(selectinload(Campaign.advertiser))
                .where(Campaign.status == CampaignStatus.PENDING_REVIEW.value)
                .order_by(Campaign.created_at.asc())
                .offset(page.offset)
                .limit(page.limit)
            )
        )
        .scalars()
        .unique()
        .all()
    )
    items = [
        QueueCampaignItem(
            id=str(row.id),
            name=row.name,
            advertiser=row.advertiser.display_name or row.advertiser.email,
            advertiserId=str(row.advertiser_id),
            format=campaign_format_to_frontend(row.format),
            language=row.target_language,
            cpm=row.cpm_bid,
            budget=row.total_budget,
            copy=row.ad_text,
            buttonLabel=row.button_label,
            destinationUrl=row.destination_url,
            imageUrl=row.image_url,
            submittedAt=row.updated_at or row.created_at,
            # An already-approved campaign back in the queue is an edit.
            isEdit=row.approved_at is not None or row.translations_generated,
        )
        for row in rows
    ]
    return QueueResponse(
        items=items, total=len(items), counts=await _queue_counts(session)
    )


@router.get("/queue/channels", response_model=QueueResponse, summary="Channel queue")
async def queue_channels(
    admin: CurrentAdminDep, session: SessionDep, page: PaginationDep
) -> QueueResponse:
    rows = (
        (
            await session.execute(
                select(Channel)
                .options(selectinload(Channel.publisher))
                .where(Channel.status == ChannelStatus.PENDING_MODERATION.value)
                .order_by(Channel.created_at.asc())
                .offset(page.offset)
                .limit(page.limit)
            )
        )
        .scalars()
        .unique()
        .all()
    )
    items = [
        QueueChannelItem(
            id=str(row.id),
            name=row.name,
            publisher=row.publisher.display_name or row.publisher.email,
            publisherId=str(row.publisher_id),
            language=row.declared_language,
            subscribers=row.subscriber_count,
            publicLink=row.public_link,
            privateLink=row.private_invite_link,
            adminUsername=row.admin_username,
            maxAdsPerDay=row.max_ads_per_day,
            botAdminVerified=row.bot_admin_verified,
            submittedAt=row.created_at,
        )
        for row in rows
    ]
    return QueueResponse(
        items=items, total=len(items), counts=await _queue_counts(session)
    )


@router.get("/queue/mini-apps", response_model=QueueResponse, summary="Mini App queue")
async def queue_mini_apps(
    admin: CurrentAdminDep, session: SessionDep, page: PaginationDep
) -> QueueResponse:
    rows = (
        (
            await session.execute(
                select(MiniApp)
                .options(selectinload(MiniApp.publisher))
                .where(MiniApp.status == MiniAppStatus.PENDING_MODERATION.value)
                .order_by(MiniApp.created_at.asc())
                .offset(page.offset)
                .limit(page.limit)
            )
        )
        .scalars()
        .unique()
        .all()
    )
    items = [
        QueueMiniAppItem(
            id=str(row.id),
            name=row.name,
            publisher=row.publisher.display_name or row.publisher.email,
            publisherId=str(row.publisher_id),
            url=row.url,
            formats=list(row.formats_enabled or []),
            submittedAt=row.created_at,
        )
        for row in rows
    ]
    return QueueResponse(
        items=items, total=len(items), counts=await _queue_counts(session)
    )


@router.get(
    "/queue/withdrawals", response_model=QueueResponse, summary="Withdrawal queue"
)
async def queue_withdrawals(
    admin: CurrentAdminDep, session: SessionDep, page: PaginationDep
) -> QueueResponse:
    rows = (
        (
            await session.execute(
                select(Withdrawal)
                .options(selectinload(Withdrawal.publisher))
                .where(Withdrawal.status == WithdrawalStatus.PENDING.value)
                .order_by(Withdrawal.requested_at.asc())
                .offset(page.offset)
                .limit(page.limit)
            )
        )
        .scalars()
        .unique()
        .all()
    )
    items = [
        QueueWithdrawalItem(
            id=str(row.id),
            publisher=row.publisher.display_name or row.publisher.email,
            publisherId=str(row.publisher_id),
            amount=row.amount_usd,
            address=row.destination_address,
            memo=row.effective_memo,
            method=row.method_label,
            availableBalance=row.publisher.available_balance_usd,
            lifetimeEarnings=row.publisher.lifetime_earnings_usd,
            requestedAt=row.requested_at,
        )
        for row in rows
    ]
    return QueueResponse(
        items=items, total=len(items), counts=await _queue_counts(session)
    )


# --------------------------------------------------------------------------- #
# Moderation actions
# --------------------------------------------------------------------------- #
@router.post(
    "/queue/campaigns/{campaign_id}/approve",
    response_model=ModerationActionResponse,
    summary="Approve a campaign (triggers translation generation)",
)
async def approve_campaign(
    campaign_id: uuid.UUID,
    admin: CurrentAdminDep,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
    payload: ApproveRequest | None = None,
) -> ModerationActionResponse:
    campaign = await moderation_service.approve_campaign(
        session, campaign_id=campaign_id, admin_id=admin.id, ip_hash=ip_hash
    )
    return ModerationActionResponse(
        id=str(campaign.id),
        status=campaign.status,
        message="Campaign approved and translations generated.",
    )


@router.post(
    "/queue/campaigns/{campaign_id}/reject",
    response_model=ModerationActionResponse,
    summary="Reject a campaign",
)
async def reject_campaign(
    campaign_id: uuid.UUID,
    payload: dict,
    admin: CurrentAdminDep,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> ModerationActionResponse:
    reason = (payload or {}).get("reason", "").strip()
    if len(reason) < 3:
        raise ValidationError("A rejection reason is required.")
    campaign = await moderation_service.reject_campaign(
        session,
        campaign_id=campaign_id,
        admin_id=admin.id,
        reason=reason,
        ip_hash=ip_hash,
    )
    return ModerationActionResponse(
        id=str(campaign.id),
        status=campaign.status,
        message="Campaign rejected.",
        reason=reason,
    )


@router.post(
    "/queue/channels/{channel_id}/approve",
    response_model=ModerationActionResponse,
    summary="Approve a channel",
)
async def approve_channel(
    channel_id: uuid.UUID,
    admin: CurrentAdminDep,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
    payload: ApproveRequest | None = None,
) -> ModerationActionResponse:
    channel = await moderation_service.approve_channel(
        session, channel_id=channel_id, admin_id=admin.id, ip_hash=ip_hash
    )
    return ModerationActionResponse(
        id=str(channel.id),
        status=channel.status,
        message="Channel approved. The publisher can now start delivery.",
    )


@router.post(
    "/queue/channels/{channel_id}/reject",
    response_model=ModerationActionResponse,
    summary="Reject a channel",
)
async def reject_channel(
    channel_id: uuid.UUID,
    payload: dict,
    admin: CurrentAdminDep,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> ModerationActionResponse:
    reason = (payload or {}).get("reason", "").strip()
    if len(reason) < 3:
        raise ValidationError("A rejection reason is required.")
    channel = await moderation_service.reject_channel(
        session,
        channel_id=channel_id,
        admin_id=admin.id,
        reason=reason,
        ip_hash=ip_hash,
    )
    return ModerationActionResponse(
        id=str(channel.id),
        status=channel.status,
        message="Channel rejected.",
        reason=reason,
    )


@router.post(
    "/queue/mini-apps/{mini_app_id}/approve",
    response_model=ModerationActionResponse,
    summary="Approve a Mini App",
)
async def approve_mini_app(
    mini_app_id: uuid.UUID,
    admin: CurrentAdminDep,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
    payload: ApproveRequest | None = None,
) -> ModerationActionResponse:
    mini_app = await moderation_service.approve_mini_app(
        session, mini_app_id=mini_app_id, admin_id=admin.id, ip_hash=ip_hash
    )
    return ModerationActionResponse(
        id=str(mini_app.id),
        status=mini_app.status,
        message="Mini App approved. Its Kinz-ID key now serves ads.",
    )


@router.post(
    "/queue/mini-apps/{mini_app_id}/reject",
    response_model=ModerationActionResponse,
    summary="Reject a Mini App",
)
async def reject_mini_app(
    mini_app_id: uuid.UUID,
    payload: dict,
    admin: CurrentAdminDep,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> ModerationActionResponse:
    reason = (payload or {}).get("reason", "").strip()
    if len(reason) < 3:
        raise ValidationError("A rejection reason is required.")
    mini_app = await moderation_service.reject_mini_app(
        session,
        mini_app_id=mini_app_id,
        admin_id=admin.id,
        reason=reason,
        ip_hash=ip_hash,
    )
    return ModerationActionResponse(
        id=str(mini_app.id),
        status=mini_app.status,
        message="Mini App rejected.",
        reason=reason,
    )


@router.post(
    "/queue/withdrawals/{withdrawal_id}/approve",
    response_model=ModerationActionResponse,
    summary="Approve a payout",
)
async def approve_withdrawal(
    withdrawal_id: uuid.UUID,
    admin: CurrentAdminDep,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
    payload: ApproveRequest | None = None,
) -> ModerationActionResponse:
    """Approve a payout.

    The transfer is only attempted from the dedicated payout wallet. When
    automatic payouts are disabled, the request stays approved and waits for
    the operator to send it manually.
    """
    withdrawal = await moderation_service.approve_withdrawal(
        session, withdrawal_id=withdrawal_id, admin_id=admin.id, ip_hash=ip_hash
    )
    if withdrawal.status == WithdrawalStatus.PAID.value:
        message = f"Payout sent. Transaction {withdrawal.tx_hash}."
    else:
        message = (
            "Payout approved. Automatic sending did not complete — send it "
            "manually and record the transaction hash."
        )
    return ModerationActionResponse(
        id=str(withdrawal.id), status=withdrawal.status, message=message
    )


@router.post(
    "/queue/withdrawals/{withdrawal_id}/reject",
    response_model=ModerationActionResponse,
    summary="Reject a payout and release the held funds",
)
async def reject_withdrawal(
    withdrawal_id: uuid.UUID,
    payload: dict,
    admin: CurrentAdminDep,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> ModerationActionResponse:
    reason = (payload or {}).get("reason", "").strip()
    if len(reason) < 3:
        raise ValidationError("A rejection reason is required.")
    withdrawal = await moderation_service.reject_withdrawal(
        session,
        withdrawal_id=withdrawal_id,
        admin_id=admin.id,
        reason=reason,
        ip_hash=ip_hash,
    )
    return ModerationActionResponse(
        id=str(withdrawal.id),
        status=withdrawal.status,
        message="Payout rejected and the held funds were returned to the publisher.",
        reason=reason,
    )


@router.post(
    "/queue/withdrawals/{withdrawal_id}/mark-paid",
    response_model=ModerationActionResponse,
    summary="Record a manually sent payout",
)
async def mark_withdrawal_paid(
    withdrawal_id: uuid.UUID,
    payload: dict,
    admin: CurrentAdminDep,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> ModerationActionResponse:
    """Used after the operator sent the transfer by hand from the payout wallet."""
    from app.core.enums import AuditAction

    tx_hash = (payload or {}).get("txHash", "").strip()
    if len(tx_hash) < 8:
        raise ValidationError("A valid transaction hash is required.")

    withdrawal = await session.get(Withdrawal, withdrawal_id)
    if withdrawal is None:
        raise NotFoundError("Withdrawal request not found.")
    if withdrawal.status != WithdrawalStatus.APPROVED.value:
        raise ValidationError("Only an approved withdrawal can be marked as paid.")

    publisher = await session.get(Publisher, withdrawal.publisher_id)
    if publisher is None:
        raise NotFoundError("Publisher not found.")

    withdrawal.status = WithdrawalStatus.PAID.value
    withdrawal.tx_hash = tx_hash
    withdrawal.paid_at = datetime.now(UTC)
    withdrawal.payout_error = None

    await billing_service.settle_withdrawal(
        session,
        publisher=publisher,
        amount=Decimal(withdrawal.amount_usd),
        reference_id=withdrawal.id,
    )
    moderation_service.log_action(
        session,
        admin_id=admin.id,
        action=AuditAction.WITHDRAWAL_MARKED_PAID.value,
        target_type="withdrawal",
        target_id=withdrawal.id,
        target_label=f"${withdrawal.amount_usd}",
        details={"txHash": tx_hash},
        ip_hash=ip_hash,
    )
    await session.commit()
    return ModerationActionResponse(
        id=str(withdrawal.id), status=withdrawal.status, message="Payout recorded as paid."
    )


# --------------------------------------------------------------------------- #
# BEP20 sweeps
# --------------------------------------------------------------------------- #
@router.get(
    "/sweeps/bep20",
    response_model=Bep20SweepListResponse,
    summary="List BEP20 sweeps (filter by status)",
)
async def list_bep20_sweeps(
    admin: CurrentAdminDep,
    session: SessionDep,
    status_filter: str | None = Query(None, alias="status"),
) -> Bep20SweepListResponse:
    query = (
        select(Bep20Sweep, Advertiser.email)
        .join(Deposit, Deposit.id == Bep20Sweep.deposit_id)
        .join(Advertiser, Advertiser.id == Deposit.advertiser_id)
        .order_by(Bep20Sweep.created_at.desc())
    )
    if status_filter:
        query = query.where(Bep20Sweep.status == status_filter)

    rows = (await session.execute(query)).all()

    items = [
        Bep20SweepItem(
            id=str(sweep.id),
            depositId=str(sweep.deposit_id),
            advertiserEmail=email,
            derivedAddress=sweep.derived_address,
            derivationIndex=sweep.derivation_index,
            treasuryAddress=sweep.treasury_address,
            grossAmountUsd=sweep.gross_amount_usd,
            sweptAmountUsd=sweep.swept_amount_usd,
            gasTopupTxHash=sweep.gas_topup_tx_hash,
            sweepTxHash=sweep.sweep_tx_hash,
            dustReturnTxHash=sweep.dust_return_tx_hash,
            status=sweep.status,
            error=sweep.error,
            createdAt=sweep.created_at,
            updatedAt=sweep.updated_at,
        )
        for sweep, email in rows
    ]
    return Bep20SweepListResponse(items=items, total=len(items))


@router.post(
    "/sweeps/bep20/{sweep_id}/retry",
    response_model=Bep20SweepRetryResponse,
    summary="Manually retry a failed BEP20 sweep",
)
async def retry_bep20_sweep(
    sweep_id: uuid.UUID,
    admin: CurrentAdminDep,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> Bep20SweepRetryResponse:
    sweep = (
        await session.execute(select(Bep20Sweep).where(Bep20Sweep.id == sweep_id))
    ).scalar_one_or_none()
    if sweep is None:
        raise NotFoundError("Sweep not found.")
    if sweep.status == "swept":
        return Bep20SweepRetryResponse(
            id=str(sweep.id), status=sweep.status, message="Already swept, nothing to do."
        )

    deposit = (
        await session.execute(select(Deposit).where(Deposit.id == sweep.deposit_id))
    ).scalar_one()
    wallet = (
        await session.execute(
            select(WalletAddress).where(
                WalletAddress.advertiser_id == deposit.advertiser_id,
                WalletAddress.network == "bnb",
            )
        )
    ).scalar_one_or_none()
    if wallet is None:
        raise NotFoundError("No BEP20 wallet address on file for this advertiser anymore.")

    sweep = await bep20_sweep_service.sweep_bep20_deposit(session, deposit, wallet)

    moderation_service.log_action(
        session,
        admin_id=admin.id,
        action=AuditAction.BEP20_SWEEP_RETRIED.value,
        target_type="bep20_sweep",
        target_id=sweep.id,
        target_label=sweep.derived_address,
        details={"status": sweep.status, "error": sweep.error},
        ip_hash=ip_hash,
    )
    await session.commit()

    if sweep.status == "swept":
        message = f"Swept successfully. tx={sweep.sweep_tx_hash}"
    else:
        message = f"Retry failed: {sweep.error}"
    return Bep20SweepRetryResponse(id=str(sweep.id), status=sweep.status, message=message)


# --------------------------------------------------------------------------- #
# Finances
# --------------------------------------------------------------------------- #
@router.get("/finances", response_model=FinancesResponse, summary="Financial report")
async def finances(
    admin: CurrentAdminDep,
    session: SessionDep,
    period: str = Query("month", pattern="^(today|week|month|year|custom)$"),
    date_param: date | None = Query(None, alias="date"),
) -> FinancesResponse:
    start, end = billing_service.period_bounds(period, date_param)

    # platform_revenue holds one row per billable event, so the daily series is
    # aggregated on the fly from recorded_at.
    revenue_day = func.date(PlatformRevenue.recorded_at).label("revenue_day")
    revenue_rows = (
        await session.execute(
            select(
                revenue_day,
                func.coalesce(func.sum(PlatformRevenue.gross_amount_usd), 0),
                func.coalesce(func.sum(PlatformRevenue.commission_amount_usd), 0),
                func.coalesce(func.sum(PlatformRevenue.publisher_amount_usd), 0),
                func.count().filter(PlatformRevenue.event_type == "impression"),
                func.count().filter(PlatformRevenue.event_type == "click"),
            )
            .where(
                revenue_day >= start,
                revenue_day <= end,
            )
            .group_by(revenue_day)
            .order_by(revenue_day)
        )
    ).all()

    gross = sum((Decimal(row[1]) for row in revenue_rows), Decimal("0"))
    commission = sum((Decimal(row[2]) for row in revenue_rows), Decimal("0"))
    publisher_share = sum((Decimal(row[3]) for row in revenue_rows), Decimal("0"))
    impressions = sum(int(row[4]) for row in revenue_rows)
    clicks = sum(int(row[5]) for row in revenue_rows)

    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    end_dt = datetime.combine(end, datetime.min.time(), tzinfo=UTC) + timedelta(days=1)

    deposits_total = (
        await session.execute(
            select(func.coalesce(func.sum(Deposit.amount_usd), 0)).where(
                Deposit.status == DepositStatus.CONFIRMED.value,
                Deposit.confirmed_at >= start_dt,
                Deposit.confirmed_at < end_dt,
            )
        )
    ).scalar_one()
    withdrawals_paid = (
        await session.execute(
            select(func.coalesce(func.sum(Withdrawal.amount_usd), 0)).where(
                Withdrawal.status == WithdrawalStatus.PAID.value,
                Withdrawal.paid_at >= start_dt,
                Withdrawal.paid_at < end_dt,
            )
        )
    ).scalar_one()
    withdrawals_pending = (
        await session.execute(
            select(func.coalesce(func.sum(Withdrawal.amount_usd), 0)).where(
                Withdrawal.status.in_(
                    [WithdrawalStatus.PENDING.value, WithdrawalStatus.APPROVED.value]
                )
            )
        )
    ).scalar_one()

    advertiser_balances = (
        await session.execute(select(func.coalesce(func.sum(Advertiser.balance_usd), 0)))
    ).scalar_one()
    publisher_liabilities = (
        await session.execute(
            select(
                func.coalesce(func.sum(Publisher.available_balance_usd), 0)
                + func.coalesce(func.sum(Publisher.held_balance_usd), 0)
            )
        )
    ).scalar_one()

    top_advertisers = (
        await session.execute(
            select(
                Advertiser.id,
                Advertiser.email,
                Advertiser.display_name,
                func.coalesce(func.sum(Campaign.spent_usd), 0).label("spend"),
            )
            .join(Campaign, Campaign.advertiser_id == Advertiser.id)
            .group_by(Advertiser.id, Advertiser.email, Advertiser.display_name)
            .order_by(func.coalesce(func.sum(Campaign.spent_usd), 0).desc())
            .limit(10)
        )
    ).all()
    top_publishers = (
        await session.execute(
            select(
                Publisher.id,
                Publisher.email,
                Publisher.display_name,
                Publisher.lifetime_earnings_usd,
            )
            .order_by(Publisher.lifetime_earnings_usd.desc())
            .limit(10)
        )
    ).all()

    active_campaigns = (
        await session.execute(
            select(func.count())
            .select_from(Campaign)
            .where(Campaign.status == CampaignStatus.ACTIVE.value)
        )
    ).scalar_one()
    active_channels = (
        await session.execute(
            select(func.count())
            .select_from(Channel)
            .where(
                Channel.status.in_(
                    [
                        ChannelStatus.ACTIVE.value,
                        ChannelStatus.ACTIVE_BUILDING_TRUST.value,
                    ]
                )
            )
        )
    ).scalar_one()

    return FinancesResponse(
        period=period,  # type: ignore[arg-type]
        periodStart=start,
        periodEnd=end,
        grossRevenue=gross,
        commission=commission,
        publisherShare=publisher_share,
        depositsTotal=Decimal(deposits_total or 0),
        withdrawalsPaid=Decimal(withdrawals_paid or 0),
        withdrawalsPending=Decimal(withdrawals_pending or 0),
        advertiserBalances=Decimal(advertiser_balances or 0),
        publisherLiabilities=Decimal(publisher_liabilities or 0),
        netTreasury=Decimal(advertiser_balances or 0) - Decimal(publisher_liabilities or 0),
        impressions=impressions,
        clicks=clicks,
        activeCampaigns=int(active_campaigns or 0),
        activeChannels=int(active_channels or 0),
        series=[
            FinanceSeriesPoint(
                date=row[0].isoformat(),
                gross=Decimal(row[1]),
                commission=Decimal(row[2]),
                payouts=Decimal(row[3]),
            )
            for row in revenue_rows
        ],
        topAdvertisers=[
            FinanceTopEntry(
                id=str(row[0]),
                label=row[2] or row[1],
                amount=Decimal(row[3] or 0),
                secondary=row[1],
            )
            for row in top_advertisers
        ],
        topPublishers=[
            FinanceTopEntry(
                id=str(row[0]),
                label=row[2] or row[1],
                amount=Decimal(row[3] or 0),
                secondary=row[1],
            )
            for row in top_publishers
        ],
    )


# --------------------------------------------------------------------------- #
# Anomalies and audit trail
# --------------------------------------------------------------------------- #
@router.get("/anomalies", response_model=AnomalyListResponse, summary="Fraud signals")
async def anomalies(
    admin: CurrentAdminDep,
    session: SessionDep,
    page: PaginationDep,
    resolved: bool | None = Query(None),
) -> AnomalyListResponse:
    stmt = select(Anomaly).order_by(Anomaly.detected_at.desc())
    if resolved is not None:
        stmt = stmt.where(Anomaly.resolved.is_(resolved))
    rows = (
        (await session.execute(stmt.offset(page.offset).limit(page.limit)))
        .scalars()
        .all()
    )
    return AnomalyListResponse(
        items=[
            AnomalyItem(
                id=str(row.id),
                kind=row.kind,
                subject=row.subject_label or row.kind,
                subjectId=str(row.subject_id) if row.subject_id else None,
                reason=row.reason,
                score=row.score,
                details=row.details,
                resolved=row.resolved,
                detectedAt=row.detected_at,
            )
            for row in rows
        ],
        total=len(rows),
    )


@router.post(
    "/anomalies/{anomaly_id}/resolve",
    response_model=MessageResponse,
    summary="Mark an anomaly as reviewed",
)
async def resolve_anomaly(
    anomaly_id: uuid.UUID,
    admin: CurrentAdminDep,
    session: SessionDep,
) -> MessageResponse:
    anomaly = await session.get(Anomaly, anomaly_id)
    if anomaly is None:
        raise NotFoundError("Anomaly not found.")
    anomaly.resolved = True
    anomaly.resolved_at = datetime.now(UTC)
    anomaly.resolved_by_admin_id = admin.id
    await session.commit()
    return MessageResponse(message="Anomaly marked as reviewed.")


@router.get("/audit", response_model=AuditListResponse, summary="Admin audit trail")
async def audit(
    admin: CurrentAdminDep,
    session: SessionDep,
    page: PaginationDep,
    action: str | None = Query(None),
) -> AuditListResponse:
    stmt = (
        select(AuditLog, AdminUser.email)
        .join(AdminUser, AdminUser.id == AuditLog.admin_id, isouter=True)
        .order_by(AuditLog.created_at.desc())
    )
    if action:
        stmt = stmt.where(AuditLog.action == action)
    rows = (await session.execute(stmt.offset(page.offset).limit(page.limit))).all()

    return AuditListResponse(
        items=[
            AuditItem(
                id=str(log.id),
                actor=email or "system",
                action=log.action,
                target=log.target_label,
                targetType=log.target_type,
                targetId=str(log.target_id) if log.target_id else None,
                details=log.details,
                createdAt=log.created_at,
            )
            for log, email in rows
        ],
        total=len(rows),
    )


# --------------------------------------------------------------------------- #
# Account moderation
# --------------------------------------------------------------------------- #
@router.post(
    "/accounts/{role}/{account_id}/block",
    response_model=MessageResponse,
    summary="Block or unblock an account",
)
async def block_account(
    role: str,
    account_id: uuid.UUID,
    payload: BlockAccountRequest,
    admin: CurrentAdminDep,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> MessageResponse:
    from app.core.enums import AuditAction

    if role not in ("advertiser", "publisher"):
        raise ValidationError("Role must be 'advertiser' or 'publisher'.")

    model = Advertiser if role == "advertiser" else Publisher
    account = await session.get(model, account_id)
    if account is None:
        raise NotFoundError("Account not found.")

    account.is_blocked = payload.blocked
    account.blocked_reason = payload.reason if payload.blocked else None

    if payload.blocked:
        await session.execute(
            delete(RefreshToken).where(
                RefreshToken.account_id == account.id,
                RefreshToken.account_type == role,
            )
        )

    moderation_service.log_action(
        session,
        admin_id=admin.id,
        action=(
            AuditAction.USER_BLOCKED.value
            if payload.blocked
            else AuditAction.USER_UNBLOCKED.value
        ),
        target_type=role,
        target_id=account.id,
        target_label=account.email,
        details={"reason": payload.reason},
        ip_hash=ip_hash,
    )
    await session.commit()
    return MessageResponse(
        message="Account blocked." if payload.blocked else "Account unblocked."
    )

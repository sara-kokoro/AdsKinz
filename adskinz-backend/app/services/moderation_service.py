"""Moderation workflow: approving and rejecting campaigns, channels, mini apps.

Approving a campaign is the only moment translations are generated. Approving a
channel does not start delivery — the publisher must press Start, which opens
the trust window.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.enums import (
    AuditAction,
    CampaignStatus,
    ChannelStatus,
    MiniAppStatus,
    WithdrawalStatus,
)
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.models.accounts import Advertiser, Publisher
from app.models.campaigns import Campaign, CampaignTranslation
from app.models.finance import Withdrawal
from app.models.placements import Channel, MiniApp
from app.models.tracking import AuditLog
from app.redis_client import cache_delete_pattern
from app.services import billing_service, email_service, openrouter_service

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def log_action(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    action: str,
    target_type: str,
    target_id: uuid.UUID,
    target_label: str | None = None,
    details: dict | None = None,
    ip_hash: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label,
        details=details,
        ip_hash=ip_hash,
    )
    session.add(entry)
    return entry


# --------------------------------------------------------------------------- #
# Translations
# --------------------------------------------------------------------------- #
async def generate_translations(session: AsyncSession, campaign: Campaign) -> int:
    """Translate an approved campaign into every other supported language.

    One OpenRouter call per language. Existing translations are replaced, which is
    what happens when a campaign is edited and re-approved. A failure on one
    language does not abort the others — the ad simply falls back to the
    original copy for that language.
    """
    if not openrouter_service.is_configured():
        logger.warning("translations.skipped campaign=%s reason=openrouter_not_configured", campaign.id)
        return 0

    source_lang = campaign.target_language if campaign.target_language != "all" else "en"
    targets = openrouter_service.target_languages(source_lang)
    if not targets:
        return 0

    # Drop the previous set so a re-approval never leaves stale copy behind.
    existing = (
        (
            await session.execute(
                select(CampaignTranslation).where(
                    CampaignTranslation.campaign_id == campaign.id
                )
            )
        )
        .scalars()
        .all()
    )
    for row in existing:
        await session.delete(row)

    async def _one(lang: str) -> tuple[str, str, str] | None:
        try:
            text = await openrouter_service.translate_text(
                campaign.ad_text, target_lang=lang, source_lang=source_lang
            )
            label = await openrouter_service.translate_button_label(
                campaign.button_label, target_lang=lang
            )
            return lang, text, label
        except Exception as exc:  # noqa: BLE001 - one language must not break the rest
            logger.warning(
                "translation.failed campaign=%s lang=%s error=%s", campaign.id, lang, exc
            )
            return None

    results = await asyncio.gather(*(_one(lang) for lang in targets))

    created = 0
    for result in results:
        if result is None:
            continue
        lang, text, label = result
        session.add(
            CampaignTranslation(
                campaign_id=campaign.id,
                lang_code=lang,
                translated_text=text,
                translated_button_label=label,
                source="openrouter",
            )
        )
        created += 1

    # Store the source language too, so serving never has to special-case it.
    session.add(
        CampaignTranslation(
            campaign_id=campaign.id,
            lang_code=source_lang,
            translated_text=campaign.ad_text,
            translated_button_label=campaign.button_label,
            source="original",
        )
    )

    campaign.translations_generated = created > 0
    logger.info("translations.generated campaign=%s count=%s", campaign.id, created)
    return created


# --------------------------------------------------------------------------- #
# Campaigns
# --------------------------------------------------------------------------- #
async def approve_campaign(
    session: AsyncSession,
    *,
    campaign_id: uuid.UUID,
    admin_id: uuid.UUID,
    ip_hash: str | None = None,
) -> Campaign:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise NotFoundError("Campaign not found.")
    if campaign.status != CampaignStatus.PENDING_REVIEW.value:
        raise ConflictError("This campaign is not awaiting review.")

    campaign.status = CampaignStatus.ACTIVE.value
    campaign.approved_at = datetime.now(UTC)
    campaign.reviewed_by_admin_id = admin_id
    campaign.rejection_reason = None

    await generate_translations(session, campaign)

    log_action(
        session,
        admin_id=admin_id,
        action=AuditAction.CAMPAIGN_APPROVED.value,
        target_type="campaign",
        target_id=campaign.id,
        target_label=campaign.name,
        ip_hash=ip_hash,
    )
    await session.commit()
    await session.refresh(campaign)

    # A new active campaign changes the eligible set for every language.
    await cache_delete_pattern(settings.ns("adsel", "*"))

    advertiser = await session.get(Advertiser, campaign.advertiser_id)
    if advertiser:
        await email_service.send_campaign_approved(
            advertiser.email, campaign_name=campaign.name
        )
    return campaign


async def reject_campaign(
    session: AsyncSession,
    *,
    campaign_id: uuid.UUID,
    admin_id: uuid.UUID,
    reason: str,
    ip_hash: str | None = None,
) -> Campaign:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise NotFoundError("Campaign not found.")
    if campaign.status != CampaignStatus.PENDING_REVIEW.value:
        raise ConflictError("This campaign is not awaiting review.")

    campaign.status = CampaignStatus.REJECTED.value
    campaign.rejection_reason = reason
    campaign.reviewed_by_admin_id = admin_id

    advertiser = await session.get(Advertiser, campaign.advertiser_id)

    # A rejected campaign never ran, so whatever was reserved for it (its
    # isolated budget) goes straight back to the advertiser's wallet.
    if advertiser is not None and campaign.remaining_budget > 0:
        await billing_service.refund_campaign(
            session,
            advertiser=advertiser,
            campaign=campaign,
            amount=campaign.remaining_budget,
        )

    log_action(
        session,
        admin_id=admin_id,
        action=AuditAction.CAMPAIGN_REJECTED.value,
        target_type="campaign",
        target_id=campaign.id,
        target_label=campaign.name,
        details={"reason": reason},
        ip_hash=ip_hash,
    )
    await session.commit()
    await session.refresh(campaign)

    if advertiser:
        await email_service.send_campaign_rejected(
            advertiser.email, campaign_name=campaign.name, reason=reason
        )
    return campaign


# --------------------------------------------------------------------------- #
# Channels
# --------------------------------------------------------------------------- #
async def approve_channel(
    session: AsyncSession,
    *,
    channel_id: uuid.UUID,
    admin_id: uuid.UUID,
    ip_hash: str | None = None,
) -> Channel:
    """Approve a channel. Delivery only begins when the publisher presses Start."""
    channel = await session.get(Channel, channel_id)
    if channel is None:
        raise NotFoundError("Channel not found.")
    if channel.status != ChannelStatus.PENDING_MODERATION.value:
        raise ConflictError("This channel is not awaiting moderation.")

    channel.status = ChannelStatus.APPROVED_NOT_STARTED.value
    channel.approved_at = datetime.now(UTC)
    channel.rejection_reason = None

    publisher = await session.get(Publisher, channel.publisher_id)
    if publisher is not None and publisher.first_channel_approved_at is None:
        # Starts the withdrawal cooldown clock for this publisher.
        publisher.first_channel_approved_at = channel.approved_at

    log_action(
        session,
        admin_id=admin_id,
        action=AuditAction.CHANNEL_APPROVED.value,
        target_type="channel",
        target_id=channel.id,
        target_label=channel.name,
        ip_hash=ip_hash,
    )
    await session.commit()
    await session.refresh(channel)

    if publisher:
        await email_service.send_channel_approved(publisher.email, channel_name=channel.name)
    return channel


async def reject_channel(
    session: AsyncSession,
    *,
    channel_id: uuid.UUID,
    admin_id: uuid.UUID,
    reason: str,
    ip_hash: str | None = None,
) -> Channel:
    channel = await session.get(Channel, channel_id)
    if channel is None:
        raise NotFoundError("Channel not found.")
    if channel.status != ChannelStatus.PENDING_MODERATION.value:
        raise ConflictError("This channel is not awaiting moderation.")

    channel.status = ChannelStatus.REJECTED.value
    channel.rejection_reason = reason

    log_action(
        session,
        admin_id=admin_id,
        action=AuditAction.CHANNEL_REJECTED.value,
        target_type="channel",
        target_id=channel.id,
        target_label=channel.name,
        details={"reason": reason},
        ip_hash=ip_hash,
    )
    await session.commit()
    await session.refresh(channel)

    publisher = await session.get(Publisher, channel.publisher_id)
    if publisher:
        await email_service.send_channel_rejected(
            publisher.email, channel_name=channel.name, reason=reason
        )
    return channel


async def start_channel(session: AsyncSession, channel: Channel) -> Channel:
    """Publisher pressing Start. Opens the trust window."""
    if channel.status != ChannelStatus.APPROVED_NOT_STARTED.value:
        raise ConflictError("This channel cannot be started in its current state.")
    if not channel.bot_admin_verified:
        raise BusinessRuleError(
            f"@{settings.BOT_USERNAME} must be an administrator of the channel "
            f"before delivery can start."
        )

    channel.status = ChannelStatus.ACTIVE_BUILDING_TRUST.value
    channel.started_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(channel)
    return channel


async def suspend_channel(
    session: AsyncSession, channel: Channel, *, reason: str, notify: bool = True
) -> Channel:
    channel.status = ChannelStatus.SUSPENDED.value
    channel.rejection_reason = reason
    channel.suspended_at = datetime.now(UTC)
    await session.commit()

    if notify:
        publisher = await session.get(Publisher, channel.publisher_id)
        if publisher:
            await email_service.send_channel_suspended_bot_removed(
                publisher.email, channel_name=channel.name
            )
    return channel


# --------------------------------------------------------------------------- #
# Mini Apps
# --------------------------------------------------------------------------- #
async def approve_mini_app(
    session: AsyncSession,
    *,
    mini_app_id: uuid.UUID,
    admin_id: uuid.UUID,
    ip_hash: str | None = None,
) -> MiniApp:
    mini_app = await session.get(MiniApp, mini_app_id)
    if mini_app is None:
        raise NotFoundError("Mini App not found.")
    if mini_app.status != MiniAppStatus.PENDING_MODERATION.value:
        raise ConflictError("This Mini App is not awaiting moderation.")

    mini_app.status = MiniAppStatus.ACTIVE.value
    mini_app.approved_at = datetime.now(UTC)
    mini_app.rejection_reason = None

    log_action(
        session,
        admin_id=admin_id,
        action=AuditAction.MINI_APP_APPROVED.value,
        target_type="mini_app",
        target_id=mini_app.id,
        target_label=mini_app.name,
        ip_hash=ip_hash,
    )
    await session.commit()
    await session.refresh(mini_app)
    return mini_app


async def reject_mini_app(
    session: AsyncSession,
    *,
    mini_app_id: uuid.UUID,
    admin_id: uuid.UUID,
    reason: str,
    ip_hash: str | None = None,
) -> MiniApp:
    mini_app = await session.get(MiniApp, mini_app_id)
    if mini_app is None:
        raise NotFoundError("Mini App not found.")
    if mini_app.status != MiniAppStatus.PENDING_MODERATION.value:
        raise ConflictError("This Mini App is not awaiting moderation.")

    mini_app.status = MiniAppStatus.REJECTED.value
    mini_app.rejection_reason = reason

    log_action(
        session,
        admin_id=admin_id,
        action=AuditAction.MINI_APP_REJECTED.value,
        target_type="mini_app",
        target_id=mini_app.id,
        target_label=mini_app.name,
        details={"reason": reason},
        ip_hash=ip_hash,
    )
    await session.commit()
    await session.refresh(mini_app)
    return mini_app


# --------------------------------------------------------------------------- #
# Withdrawals
# --------------------------------------------------------------------------- #
async def approve_withdrawal(
    session: AsyncSession,
    *,
    withdrawal_id: uuid.UUID,
    admin_id: uuid.UUID,
    ip_hash: str | None = None,
) -> Withdrawal:
    """Approve a payout and attempt the on-chain transfer from Wallet 2.

    Funds are only cleared from the held balance once the transfer actually
    succeeded. If automatic payout is disabled, the request stays ``approved``
    and the operator sends it manually, then records the hash.
    """
    withdrawal = await session.get(Withdrawal, withdrawal_id)
    if withdrawal is None:
        raise NotFoundError("Withdrawal request not found.")
    if withdrawal.status != WithdrawalStatus.PENDING.value:
        raise ConflictError("This withdrawal is not pending.")

    publisher = await session.get(Publisher, withdrawal.publisher_id, with_for_update=True)
    if publisher is None:
        raise NotFoundError("Publisher not found.")

    withdrawal.status = WithdrawalStatus.APPROVED.value
    withdrawal.approved_at = datetime.now(UTC)
    withdrawal.processed_by_admin_id = admin_id

    log_action(
        session,
        admin_id=admin_id,
        action=AuditAction.WITHDRAWAL_APPROVED.value,
        target_type="withdrawal",
        target_id=withdrawal.id,
        target_label=f"${withdrawal.amount_usd} to {withdrawal.destination_address[:12]}…",
        details={"amount": str(withdrawal.amount_usd)},
        ip_hash=ip_hash,
    )
    await session.commit()

    from app.services import payout_service

    tx_hash, error = await payout_service.send_payout(
        address=withdrawal.destination_address,
        amount=Decimal(withdrawal.amount_usd),
        memo=withdrawal.effective_memo,
    )

    if tx_hash:
        withdrawal.status = WithdrawalStatus.PAID.value
        withdrawal.tx_hash = tx_hash
        withdrawal.paid_at = datetime.now(UTC)
        await billing_service.settle_withdrawal(
            session,
            publisher=publisher,
            amount=Decimal(withdrawal.amount_usd),
            reference_id=withdrawal.id,
        )
        await session.commit()
        await email_service.send_withdrawal_paid(
            publisher.email, amount=withdrawal.amount_usd, tx_hash=tx_hash
        )
    else:
        withdrawal.payout_error = error
        await session.commit()
        if error:
            await email_service.send_admin_alert(
                "Manual payout required",
                f"Withdrawal {withdrawal.id} was approved but could not be sent "
                f"automatically: {error}",
            )

    await session.refresh(withdrawal)
    return withdrawal


async def reject_withdrawal(
    session: AsyncSession,
    *,
    withdrawal_id: uuid.UUID,
    admin_id: uuid.UUID,
    reason: str,
    ip_hash: str | None = None,
) -> Withdrawal:
    withdrawal = await session.get(Withdrawal, withdrawal_id)
    if withdrawal is None:
        raise NotFoundError("Withdrawal request not found.")
    if withdrawal.status != WithdrawalStatus.PENDING.value:
        raise ConflictError("This withdrawal is not pending.")

    publisher = await session.get(Publisher, withdrawal.publisher_id, with_for_update=True)
    if publisher is None:
        raise NotFoundError("Publisher not found.")

    withdrawal.status = WithdrawalStatus.REJECTED.value
    withdrawal.rejection_reason = reason
    withdrawal.processed_by_admin_id = admin_id

    await billing_service.release_withdrawal_funds(
        session,
        publisher=publisher,
        amount=Decimal(withdrawal.amount_usd),
        reference_id=withdrawal.id,
    )

    log_action(
        session,
        admin_id=admin_id,
        action=AuditAction.WITHDRAWAL_REJECTED.value,
        target_type="withdrawal",
        target_id=withdrawal.id,
        target_label=f"${withdrawal.amount_usd}",
        details={"reason": reason},
        ip_hash=ip_hash,
    )
    await session.commit()
    await session.refresh(withdrawal)

    await email_service.send_withdrawal_rejected(
        publisher.email, amount=withdrawal.amount_usd, reason=reason
    )
    return withdrawal

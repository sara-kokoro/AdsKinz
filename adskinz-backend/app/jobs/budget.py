"""Jobs that supervise advertiser balances and flush deferred spend."""

from __future__ import annotations

from sqlalchemy import select

from app.core.enums import CampaignStatus
from app.database import session_scope
from app.models.accounts import Advertiser
from app.models.campaigns import Campaign
from app.redis_client import cache_delete_pattern, drain_spend_buffer
from app.services import billing_service


async def _advertisers_with_active_campaigns(
    session, *, include_paused_insufficient: bool = False
) -> list[Advertiser]:
    statuses = [CampaignStatus.ACTIVE.value]
    if include_paused_insufficient:
        # Include these in allocation checks so a top-up can automatically
        # resume campaigns that were paused by a previous allocation run.
        statuses.append(CampaignStatus.PAUSED_INSUFFICIENT_BALANCE.value)
    return (
        (
            await session.execute(
                select(Advertiser)
                .join(Campaign, Campaign.advertiser_id == Advertiser.id)
                .where(Campaign.status.in_(statuses))
                .distinct()
            )
        )
        .scalars()
        .unique()
        .all()
    )


async def low_balance_alert() -> dict:
    """Send at most one low-balance alert per advertiser in its 24-hour window."""
    summary = {"advertisers_checked": 0, "alerts_sent": 0}
    async with session_scope() as session:
        advertisers = await _advertisers_with_active_campaigns(session)
        summary["advertisers_checked"] = len(advertisers)
        for advertiser in advertisers:
            if await billing_service.maybe_send_low_balance_alert(session, advertiser):
                summary["alerts_sent"] += 1
    return summary


async def budget_allocation_check() -> dict:
    """Keep only the advertiser's highest-CPM campaigns covered by its balance."""
    summary = {"advertisers_checked": 0, "campaigns_changed": 0}
    async with session_scope() as session:
        advertisers = await _advertisers_with_active_campaigns(
            session, include_paused_insufficient=True
        )
        summary["advertisers_checked"] = len(advertisers)
        for advertiser in advertisers:
            changed = await billing_service.enforce_balance_allocation(session, advertiser)
            summary["campaigns_changed"] += len(changed)

    if summary["campaigns_changed"]:
        # Campaign status is part of every cached auction result.
        await cache_delete_pattern("adsel:*")
    return summary


async def spend_flush() -> dict:
    """Atomically drain Redis's campaign spend buffer into PostgreSQL."""
    buffered = await drain_spend_buffer()
    if not buffered:
        return {"buffered_campaigns": 0, "campaigns_applied": 0}

    async with session_scope() as session:
        applied = await billing_service.apply_buffered_spend(session, buffered)
    return {"buffered_campaigns": len(buffered), "campaigns_applied": applied}

"""Daily sweep for advertiser premium subscriptions (AI poster generation).

For every advertiser whose premium period has ended:
- if premium_auto_renew and the balance covers PREMIUM_MONTHLY_PRICE_USD,
  charge them for another period (same billing_service.charge_premium path
  as the manual "Subscribe" button);
- otherwise, premium is switched off. No proration, no partial period.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.errors import InsufficientBalanceError
from app.database import session_scope
from app.models.accounts import Advertiser
from app.services import billing_service

logger = logging.getLogger(__name__)


async def premium_renewal() -> dict:
    now = datetime.now(UTC)
    summary = {"renewed": 0, "expired": 0}

    async with session_scope() as session:
        advertisers = (
            (
                await session.execute(
                    select(Advertiser).where(
                        Advertiser.is_premium.is_(True),
                        Advertiser.premium_expires_at.is_not(None),
                        Advertiser.premium_expires_at <= now,
                    )
                )
            )
            .scalars()
            .all()
        )

        for advertiser in advertisers:
            if advertiser.premium_auto_renew:
                try:
                    await billing_service.charge_premium(session, advertiser=advertiser)
                    summary["renewed"] += 1
                    continue
                except InsufficientBalanceError:
                    logger.info("premium.renewal_failed_balance advertiser_id=%s", advertiser.id)
            await billing_service.expire_premium(session, advertiser=advertiser)
            summary["expired"] += 1

    return summary

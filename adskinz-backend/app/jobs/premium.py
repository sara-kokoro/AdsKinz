"""Daily sweep for publisher premium subscriptions.

For every publisher whose premium period has ended:
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
from app.models.accounts import Publisher
from app.services import billing_service

logger = logging.getLogger(__name__)


async def premium_renewal() -> dict:
    now = datetime.now(UTC)
    summary = {"renewed": 0, "expired": 0}

    async with session_scope() as session:
        publishers = (
            (
                await session.execute(
                    select(Publisher).where(
                        Publisher.is_premium.is_(True),
                        Publisher.premium_expires_at.is_not(None),
                        Publisher.premium_expires_at <= now,
                    )
                )
            )
            .scalars()
            .all()
        )

        for publisher in publishers:
            if publisher.premium_auto_renew:
                try:
                    await billing_service.charge_premium(session, publisher=publisher)
                    summary["renewed"] += 1
                    continue
                except InsufficientBalanceError:
                    logger.info("premium.renewal_failed_balance publisher_id=%s", publisher.id)
            await billing_service.expire_premium(session, publisher=publisher)
            summary["expired"] += 1

    return summary

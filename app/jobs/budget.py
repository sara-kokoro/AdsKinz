"""Jobs that flush deferred campaign spend.

Wallet-level low-balance pausing and cross-campaign balance allocation used
to live here, but both relied on the wallet balance funding active campaigns
in real time. Now that a campaign's budget is isolated money reserved at
top-up time (see billing_service.fund_campaign), neither job has anything
left to do: a running campaign can only ever be stopped by exhausting its
own reserved budget, never by the wallet balance moving underneath it.
"""

from __future__ import annotations

from app.redis_client import drain_spend_buffer
from app.database import session_scope
from app.services import billing_service


async def spend_flush() -> dict:
    """Atomically drain Redis's campaign spend buffer into PostgreSQL."""
    buffered = await drain_spend_buffer()
    if not buffered:
        return {"buffered_campaigns": 0, "campaigns_applied": 0}

    async with session_scope() as session:
        applied = await billing_service.apply_buffered_spend(session, buffered)
    return {"buffered_campaigns": len(buffered), "campaigns_applied": applied}

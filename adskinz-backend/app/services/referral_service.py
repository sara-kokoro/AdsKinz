"""Referral codes: generation and lookup.

Commission math itself lives in billing_service (credit_publisher /
credit_deposit) since it needs to run inside the same transaction as the
earning/deposit it's a percentage of.
"""

from __future__ import annotations

import secrets
import string

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounts import Advertiser, Publisher

_ALPHABET = string.ascii_uppercase + string.digits
# Characters that are easy to misread out loud (0/O, 1/I/L) are dropped —
# this code gets shared verbally / typed by hand a lot more than a UUID.
_ALPHABET = "".join(c for c in _ALPHABET if c not in "0O1IL")


def _generate_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(7))


async def ensure_referral_code(session: AsyncSession, account: Advertiser | Publisher) -> str:
    """Idempotent: returns the existing code, or mints + persists a new one."""
    if account.referral_code:
        return account.referral_code

    for _ in range(5):
        code = _generate_code()
        account.referral_code = code
        try:
            await session.flush()
            return code
        except IntegrityError:
            await session.rollback()
            session.add(account)
    raise RuntimeError("Could not generate a unique referral code after 5 attempts.")


async def find_by_referral_code(
    session: AsyncSession, model: type[Advertiser] | type[Publisher], code: str
) -> Advertiser | Publisher | None:
    code = code.strip().upper()
    if not code:
        return None
    return (
        await session.execute(select(model).where(model.referral_code == code))
    ).scalar_one_or_none()


async def referral_summary(
    session: AsyncSession, *, model: type[Advertiser] | type[Publisher], account: Advertiser | Publisher
) -> dict:
    from decimal import Decimal

    from sqlalchemy import func

    from app.models.accounts import LedgerEntry

    account_type = "publisher" if model is Publisher else "advertiser"
    code = await ensure_referral_code(session, account)

    referred_count = (
        await session.execute(
            select(func.count()).select_from(model).where(model.referred_by_id == account.id)
        )
    ).scalar_one()

    total_earned = (
        await session.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount_usd), Decimal("0")))
            .where(
                LedgerEntry.account_type == account_type,
                LedgerEntry.account_id == account.id,
                LedgerEntry.entry_type == "referral_commission",
            )
        )
    ).scalar_one()

    return {
        "code": code,
        "referredCount": int(referred_count or 0),
        "totalEarned": total_earned,
    }

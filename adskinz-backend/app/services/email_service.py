"""Transactional email over SMTP.

Every send is best-effort: an SMTP outage must never break a request or abort a
background job, so failures are logged and swallowed.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


def _render(title: str, intro: str, rows: dict[str, Any] | None, outro: str | None) -> str:
    lines = [title, "=" * len(title), "", intro, ""]
    if rows:
        for key, value in rows.items():
            lines.append(f"  {key}: {value}")
        lines.append("")
    if outro:
        lines.extend([outro, ""])
    lines.append("— AdsKinz")
    lines.append(settings.PUBLIC_BASE_URL)
    return "\n".join(lines)


def _send_blocking(to: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(message)


async def send_email(to: str | None, subject: str, body: str) -> bool:
    """Send one plain-text email. Returns whether it was handed to the server."""
    if not to:
        return False
    if not settings.ENABLE_EMAIL or not settings.SMTP_HOST:
        logger.info("email.skipped to=%s subject=%s (email disabled)", to, subject)
        return False
    try:
        await asyncio.to_thread(_send_blocking, to, subject, body)
        logger.info("email.sent to=%s subject=%s", to, subject)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        logger.warning("email.failed to=%s subject=%s error=%s", to, subject, exc)
        return False


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #
async def send_low_balance_alert(
    to: str, *, balance: Any, active_budget: Any, threshold: Any
) -> bool:
    body = _render(
        "Your AdsKinz balance is running low",
        "Your remaining balance has fallen below 10% of the total budget "
        "committed to your active campaigns.",
        {
            "Current balance": f"${balance}",
            "Committed active budget": f"${active_budget}",
            "Alert threshold": f"${threshold}",
        },
        "Top up your balance to avoid your campaigns being paused automatically.",
    )
    return await send_email(to, "AdsKinz — low balance warning", body)


async def send_campaign_approved(to: str, *, campaign_name: str) -> bool:
    body = _render(
        "Your campaign has been approved",
        f'Your campaign "{campaign_name}" passed moderation and is now eligible '
        f"for delivery.",
        None,
        "Translations have been generated and delivery will start shortly.",
    )
    return await send_email(to, "AdsKinz — campaign approved", body)


async def send_campaign_rejected(to: str, *, campaign_name: str, reason: str) -> bool:
    body = _render(
        "Your campaign was rejected",
        f'Your campaign "{campaign_name}" did not pass moderation.',
        {"Reason": reason},
        "You can edit the campaign and submit it again for review.",
    )
    return await send_email(to, "AdsKinz — campaign rejected", body)


async def send_campaign_paused_balance(to: str, *, campaign_name: str) -> bool:
    body = _render(
        "A campaign was paused for insufficient balance",
        f'Your campaign "{campaign_name}" has been paused because your balance '
        f"no longer covers its active budget.",
        None,
        "It resumes automatically once you top up your balance.",
    )
    return await send_email(to, "AdsKinz — campaign paused", body)


async def send_channel_approved(to: str, *, channel_name: str) -> bool:
    body = _render(
        "Your channel has been approved",
        f'Your channel "{channel_name}" has been approved. Press Start in your '
        f"dashboard to begin receiving ads.",
        None,
        "The first 72 hours are a trust-building period limited to one ad per day.",
    )
    return await send_email(to, "AdsKinz — channel approved", body)


async def send_channel_rejected(to: str, *, channel_name: str, reason: str) -> bool:
    body = _render(
        "Your channel was rejected",
        f'Your channel "{channel_name}" did not pass moderation.',
        {"Reason": reason},
        None,
    )
    return await send_email(to, "AdsKinz — channel rejected", body)


async def send_channel_suspended_bot_removed(to: str, *, channel_name: str) -> bool:
    body = _render(
        "Your channel has been suspended",
        f'@{settings.BOT_USERNAME} is no longer an administrator of '
        f'"{channel_name}", so the channel has been suspended and will not '
        f"receive ads.",
        None,
        "Restore the bot's admin rights, then contact support to reactivate.",
    )
    return await send_email(to, "AdsKinz — channel suspended", body)


async def send_withdrawal_paid(to: str, *, amount: Any, tx_hash: str | None) -> bool:
    body = _render(
        "Your withdrawal has been paid",
        "Your payout has been sent on the TON network.",
        {"Amount": f"${amount} USDT", "Transaction": tx_hash or "pending confirmation"},
        None,
    )
    return await send_email(to, "AdsKinz — withdrawal paid", body)


async def send_withdrawal_rejected(to: str, *, amount: Any, reason: str) -> bool:
    body = _render(
        "Your withdrawal request was rejected",
        f"Your ${amount} withdrawal request was not approved. The amount has "
        f"been returned to your available balance.",
        {"Reason": reason},
        None,
    )
    return await send_email(to, "AdsKinz — withdrawal rejected", body)


async def send_deposit_confirmed(to: str, *, amount: Any, network: str, fee: Any) -> bool:
    rows: dict[str, Any] = {"Credited": f"${amount} USDT", "Network": network}
    if fee and float(fee) > 0:
        rows["Network fee withheld"] = f"${fee} USDT"
    body = _render(
        "Deposit confirmed",
        "Your deposit has been confirmed on chain and credited to your balance.",
        rows,
        None,
    )
    return await send_email(to, "AdsKinz — deposit confirmed", body)


async def send_admin_alert(subject: str, detail: str) -> bool:
    """Operational alert to the platform operator."""
    return await send_email(
        settings.ADMIN_ALERT_EMAIL, f"[AdsKinz] {subject}", detail
    )

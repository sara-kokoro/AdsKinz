"""Transactional email via the Resend API.

Every send is best-effort: a Resend outage must never break a request or abort
a background job, so failures are logged and swallowed.

Each email goes out as multipart (plain text + HTML). The HTML layer mirrors
the app's dark theme (see src/styles.css, `.dark` block) so a verification
code or a payout notice looks like it came from the same product as the
dashboard, not a bare text dump.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any, Literal

import resend

from app.config import settings

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Brand palette — kept in sync with the `.dark` block in src/styles.css so the
# email and the app never drift apart.
# --------------------------------------------------------------------------- #
_INK = "#0b0d10"  # page background
_PANEL = "#15181c"  # card background
_PANEL_2 = "#1b1f24"  # nested row background
_SEAM = "#262b31"  # borders / dividers
_PAPER = "#eceff3"  # primary text
_PAPER_DIM = "#99a1ac"  # muted text
_SIGNAL = "#0088cc"  # brand blue
_SIGNAL_SOFT = "rgba(0, 136, 204, 0.14)"
_SUCCESS = "#3fd18b"
_BOUNTY = "#f5b942"
_DANGER = "#f2665f"

_FONT = "'Inter','Helvetica Neue',Helvetica,Arial,sans-serif"
_FONT_MONO = "'JetBrains Mono','SFMono-Regular',Consolas,'Courier New',monospace"

_LOGO_URL = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/adskinz-logo.png"

IconKind = Literal["lock", "check", "warning", "alert"]

_ICON_COLORS: dict[IconKind, tuple[str, str]] = {
    "lock": (_SIGNAL, "#4fc3f7"),
    "check": (_SUCCESS, "#1f9d64"),
    "warning": (_BOUNTY, "#c98a1e"),
    "alert": (_DANGER, "#d94840"),
}

_ICON_GLYPHS: dict[IconKind, str] = {
    "lock": (
        '<rect x="16" y="22" width="16" height="14" rx="3" fill="#fff"/>'
        '<path d="M19 22v-5a5 5 0 0 1 10 0v5" stroke="#fff" stroke-width="3" '
        'fill="none" stroke-linecap="round"/>'
    ),
    "check": (
        '<path d="M15 24l6 6 12-12" stroke="#fff" stroke-width="3.5" fill="none" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "warning": (
        '<rect x="22" y="14" width="4" height="14" rx="2" fill="#fff"/>'
        '<circle cx="24" cy="33" r="2.6" fill="#fff"/>'
    ),
    "alert": (
        '<rect x="22" y="14" width="4" height="14" rx="2" fill="#fff"/>'
        '<circle cx="24" cy="33" r="2.6" fill="#fff"/>'
    ),
}


def _icon_data_uri(kind: IconKind) -> str:
    start, end = _ICON_COLORS[kind]
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{start}"/><stop offset="1" stop-color="{end}"/>'
        "</linearGradient></defs>"
        '<circle cx="24" cy="24" r="24" fill="url(#g)"/>'
        f"{_ICON_GLYPHS[kind]}"
        "</svg>"
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _render(title: str, intro: str, rows: dict[str, Any] | None, outro: str | None) -> str:
    """Plain-text part — kept simple, this is the fallback most clients hide."""
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


def _rows_html(rows: dict[str, Any]) -> str:
    items = list(rows.items())
    cells = []
    for i, (key, value) in enumerate(items):
        border = f"border-bottom:1px solid {_SEAM};" if i < len(items) - 1 else ""
        cells.append(
            f'<tr><td style="padding:13px 18px;{border}">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="font-family:{_FONT};font-size:13px;color:{_PAPER_DIM};">{key}</td>'
            f'<td align="right" style="font-family:{_FONT};font-size:13px;color:{_PAPER};'
            f'font-weight:600;">{value}</td>'
            f"</tr></table></td></tr>"
        )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{_PANEL_2};border:1px solid {_SEAM};border-radius:12px;">'
        f'{"".join(cells)}</table>'
    )


def _render_html(
    *,
    title: str,
    intro: str,
    rows: dict[str, Any] | None = None,
    outro: str | None = None,
    code: str | None = None,
    icon: IconKind = "lock",
    preheader: str = "",
) -> str:
    body_parts = [
        f'<tr><td align="center" style="padding-bottom:18px;">'
        f'<img src="{_icon_data_uri(icon)}" width="48" height="48" alt="" '
        f'style="display:block;border:0;">'
        f"</td></tr>",
        f'<tr><td align="center" style="padding-bottom:10px;">'
        f'<h1 style="margin:0;font-family:{_FONT};font-size:21px;font-weight:700;'
        f'color:{_PAPER};">{title}</h1></td></tr>',
        f'<tr><td align="center" style="padding-bottom:24px;">'
        f'<p style="margin:0;font-family:{_FONT};font-size:14.5px;line-height:1.6;'
        f'color:{_PAPER_DIM};">{intro}</p></td></tr>',
    ]

    if code:
        body_parts.append(
            f'<tr><td align="center" style="padding-bottom:22px;">'
            f'<div style="display:inline-block;background:{_SIGNAL_SOFT};'
            f'border:1px solid {_SIGNAL};border-radius:14px;padding:18px 30px;">'
            f'<span style="font-family:{_FONT_MONO};font-size:32px;font-weight:700;'
            f'letter-spacing:10px;color:{_PAPER};">{code}</span>'
            f"</div></td></tr>"
        )
    elif rows:
        body_parts.append(
            f'<tr><td style="padding-bottom:22px;">{_rows_html(rows)}</td></tr>'
        )

    if outro:
        body_parts.append(
            f'<tr><td align="center">'
            f'<p style="margin:0;font-family:{_FONT};font-size:12.5px;line-height:1.6;'
            f'color:{_PAPER_DIM};opacity:0.85;">{outro}</p></td></tr>'
        )

    body_html = "".join(body_parts)

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title></title>
</head>
<body style="margin:0;padding:0;background:{_INK};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_INK};padding:36px 16px;">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;">
<tr><td align="center" style="padding-bottom:22px;">
<img src="{_LOGO_URL}" width="60" alt="AdsKinz" style="display:block;border:0;">
</td></tr>
<tr><td style="background:{_PANEL};border:1px solid {_SEAM};border-radius:20px;padding:36px 30px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
{body_html}
</table>
</td></tr>
<tr><td align="center" style="padding-top:26px;">
<p style="margin:0 0 6px;font-family:{_FONT};font-size:13px;">
<a href="{settings.PUBLIC_BASE_URL}" style="color:{_SIGNAL};text-decoration:none;font-weight:700;">AdsKinz</a>
</p>
<p style="margin:0;font-family:{_FONT};font-size:11px;color:{_PAPER_DIM};opacity:0.7;">
Vous recevez cet email car cette adresse est liée à un compte AdsKinz.
</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def _send_blocking(to: str, subject: str, text: str, html: str | None) -> str:
    resend.api_key = settings.RESEND_API_KEY
    params: resend.Emails.SendParams = {
        "from": settings.EMAIL_FROM,
        "to": [to],
        "subject": subject,
        "text": text,
    }
    if html:
        params["html"] = html
    result = resend.Emails.send(params)
    return result["id"]


async def send_email(to: str | None, subject: str, body: str, html: str | None = None) -> bool:
    """Send one email (plain text, optionally with an HTML part). Returns
    whether Resend accepted it."""
    if not to:
        return False
    if not settings.ENABLE_EMAIL or not settings.RESEND_API_KEY:
        logger.info("email.skipped to=%s subject=%s (email disabled)", to, subject)
        return False
    try:
        email_id = await asyncio.to_thread(_send_blocking, to, subject, body, html)
        logger.info("email.sent to=%s subject=%s id=%s", to, subject, email_id)
        return True
    except resend.exceptions.ResendError as exc:
        logger.warning(
            "email.failed to=%s subject=%s code=%s error=%s",
            to, subject, getattr(exc, "code", "unknown"), exc,
        )
        return False
    except Exception as exc:  # network errors, timeouts, etc. — never break the caller
        logger.warning("email.failed to=%s subject=%s error=%s", to, subject, exc)
        return False


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #
async def send_low_balance_alert(
    to: str, *, balance: Any, active_budget: Any, threshold: Any
) -> bool:
    title = "Your AdsKinz balance is running low"
    intro = (
        "Your remaining balance has fallen below 10% of the total budget "
        "committed to your active campaigns."
    )
    rows = {
        "Current balance": f"${balance}",
        "Committed active budget": f"${active_budget}",
        "Alert threshold": f"${threshold}",
    }
    outro = "Top up your balance to avoid your campaigns being paused automatically."
    return await send_email(
        to,
        "AdsKinz — low balance warning",
        _render(title, intro, rows, outro),
        _render_html(title=title, intro=intro, rows=rows, outro=outro, icon="warning",
                     preheader=f"Balance: ${balance}"),
    )


async def send_campaign_approved(to: str, *, campaign_name: str) -> bool:
    title = "Your campaign has been approved"
    intro = f'Your campaign "{campaign_name}" passed moderation and is now eligible for delivery.'
    outro = "Translations have been generated and delivery will start shortly."
    return await send_email(
        to,
        "AdsKinz — campaign approved",
        _render(title, intro, None, outro),
        _render_html(title=title, intro=intro, outro=outro, icon="check",
                     preheader=f'"{campaign_name}" is live'),
    )


async def send_campaign_rejected(to: str, *, campaign_name: str, reason: str) -> bool:
    title = "Your campaign was rejected"
    intro = f'Your campaign "{campaign_name}" did not pass moderation.'
    rows = {"Reason": reason}
    outro = "You can edit the campaign and submit it again for review."
    return await send_email(
        to,
        "AdsKinz — campaign rejected",
        _render(title, intro, rows, outro),
        _render_html(title=title, intro=intro, rows=rows, outro=outro, icon="alert",
                     preheader=f'"{campaign_name}" needs changes'),
    )


async def send_campaign_paused_balance(to: str, *, campaign_name: str) -> bool:
    title = "A campaign was paused for insufficient balance"
    intro = (
        f'Your campaign "{campaign_name}" has been paused because your balance '
        f"no longer covers its active budget."
    )
    outro = "It resumes automatically once you top up your balance."
    return await send_email(
        to,
        "AdsKinz — campaign paused",
        _render(title, intro, None, outro),
        _render_html(title=title, intro=intro, outro=outro, icon="warning",
                     preheader=f'"{campaign_name}" is paused'),
    )


async def send_campaign_low_balance(
    to: str, *, campaign_name: str, remaining: Any, threshold: Any
) -> bool:
    title = "A campaign is about to run out of budget"
    intro = (
        f'Your campaign "{campaign_name}" has ${remaining} left, below your '
        f"${threshold} alert threshold."
    )
    rows = {"Remaining budget": f"${remaining}", "Alert threshold": f"${threshold}"}
    outro = "Add budget to this campaign to keep it delivering without interruption."
    return await send_email(
        to,
        "AdsKinz — campaign budget running low",
        _render(title, intro, rows, outro),
        _render_html(title=title, intro=intro, rows=rows, outro=outro, icon="warning",
                     preheader=f'"{campaign_name}": ${remaining} left'),
    )


async def send_channel_approved(to: str, *, channel_name: str) -> bool:
    title = "Your channel has been approved"
    intro = (
        f'Your channel "{channel_name}" has been approved. Press Start in your '
        f"dashboard to begin receiving ads."
    )
    outro = "The first 72 hours are a trust-building period limited to one ad per day."
    return await send_email(
        to,
        "AdsKinz — channel approved",
        _render(title, intro, None, outro),
        _render_html(title=title, intro=intro, outro=outro, icon="check",
                     preheader=f'"{channel_name}" is approved'),
    )


async def send_channel_not_started_reminder(to: str, *, channel_name: str) -> bool:
    title = "Your channel is approved but not earning yet"
    intro = (
        f'"{channel_name}" was approved but is still waiting for you to press '
        f"Start. Until then it receives no ads and earns nothing."
    )
    outro = "Open the channel in your dashboard and press Start to begin delivery."
    return await send_email(
        to,
        "AdsKinz — don't forget to start your channel",
        _render(title, intro, None, outro),
        _render_html(title=title, intro=intro, outro=outro, icon="alert",
                     preheader=f'"{channel_name}" is still not started'),
    )


async def send_channel_rejected(to: str, *, channel_name: str, reason: str) -> bool:
    title = "Your channel was rejected"
    intro = f'Your channel "{channel_name}" did not pass moderation.'
    rows = {"Reason": reason}
    return await send_email(
        to,
        "AdsKinz — channel rejected",
        _render(title, intro, rows, None),
        _render_html(title=title, intro=intro, rows=rows, icon="alert",
                     preheader=f'"{channel_name}" needs changes'),
    )


async def send_channel_suspended_bot_removed(to: str, *, channel_name: str) -> bool:
    title = "Your channel has been suspended"
    intro = (
        f'@{settings.BOT_USERNAME} is no longer an administrator of '
        f'"{channel_name}", so the channel has been suspended and will not '
        f"receive ads."
    )
    outro = "Restore the bot's admin rights, then contact support to reactivate."
    return await send_email(
        to,
        "AdsKinz — channel suspended",
        _render(title, intro, None, outro),
        _render_html(title=title, intro=intro, outro=outro, icon="alert",
                     preheader=f'"{channel_name}" is suspended'),
    )


async def send_withdrawal_paid(to: str, *, amount: Any, tx_hash: str | None) -> bool:
    title = "Your withdrawal has been paid"
    intro = "Your payout has been sent on the TON network."
    rows = {"Amount": f"${amount} USDT", "Transaction": tx_hash or "pending confirmation"}
    return await send_email(
        to,
        "AdsKinz — withdrawal paid",
        _render(title, intro, rows, None),
        _render_html(title=title, intro=intro, rows=rows, icon="check",
                     preheader=f"${amount} USDT sent"),
    )


async def send_withdrawal_rejected(to: str, *, amount: Any, reason: str) -> bool:
    title = "Your withdrawal request was rejected"
    intro = (
        f"Your ${amount} withdrawal request was not approved. The amount has "
        f"been returned to your available balance."
    )
    rows = {"Reason": reason}
    return await send_email(
        to,
        "AdsKinz — withdrawal rejected",
        _render(title, intro, rows, None),
        _render_html(title=title, intro=intro, rows=rows, icon="alert",
                     preheader=f"${amount} withdrawal rejected"),
    )


async def send_deposit_confirmed(to: str, *, amount: Any, network: str, fee: Any) -> bool:
    title = "Deposit confirmed"
    intro = "Your deposit has been confirmed on chain and credited to your balance."
    rows: dict[str, Any] = {"Credited": f"${amount} USDT", "Network": network}
    if fee and float(fee) > 0:
        rows["Network fee withheld"] = f"${fee} USDT"
    return await send_email(
        to,
        "AdsKinz — deposit confirmed",
        _render(title, intro, rows, None),
        _render_html(title=title, intro=intro, rows=rows, icon="check",
                     preheader=f"${amount} USDT credited"),
    )


async def send_verification_code(to: str, *, code: str) -> bool:
    """Send the 6-digit email verification code for a new account."""
    title = "Verify your AdsKinz account"
    intro = "Thanks for signing up. Enter the code below in the verification screen to activate your account."
    outro = "This code expires in 3 hours. If you did not create an account, you can safely ignore this email."
    return await send_email(
        to,
        "AdsKinz — verify your email",
        _render(title, intro, {"Verification code": code}, outro),
        _render_html(title=title, intro=intro, code=code, outro=outro, icon="lock",
                     preheader=f"Your verification code: {code}"),
    )


async def send_admin_login_code(to: str, *, code: str) -> bool:
    """Send the one-time 8-digit code used to sign in to the internal console."""
    title = "AdsKinz internal console — sign-in code"
    intro = (
        "Someone requested a sign-in code for the internal console. Enter it "
        "together with the console password to continue."
    )
    outro = (
        "This code expires in 10 minutes and can only be used once. If you did "
        "not request this, ignore this email — no one can sign in without it."
    )
    return await send_email(
        to,
        "AdsKinz — internal console sign-in code",
        _render(title, intro, {"Sign-in code": code}, outro),
        _render_html(title=title, intro=intro, code=code, outro=outro, icon="lock",
                     preheader=f"Your sign-in code: {code}"),
    )


async def send_admin_alert(subject: str, detail: str) -> bool:
    """Operational alert to the platform operator."""
    return await send_email(
        settings.ADMIN_ALERT_EMAIL, f"[AdsKinz] {subject}", detail,
        _render_html(title=subject, intro=detail, icon="warning"),
    )

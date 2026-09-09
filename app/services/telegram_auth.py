"""Validate Telegram Mini App ``initData`` signatures.

Telegram signs every WebApp launch payload with an HMAC-SHA256 keyed on the
owning bot's token (see
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app).
Verifying this signature is the only reliable way to confirm that a Kinz-ID
SDK call genuinely comes from the specific bot's Mini App it was issued to,
rather than from a copy of the ``kinz_key`` embedded in an unrelated app.

This never needs the mini app's own audience data beyond what Telegram
already signed — AdsKinz only stores the bot token to run this check
server-side, and never returns it in any API response.
"""

from __future__ import annotations

import hashlib
import hmac
from urllib.parse import parse_qsl


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> tuple[bool, str | None]:
    """Return ``(is_valid, error)``.

    ``error`` is a short machine-readable reason (never containing secrets)
    suitable for logging and for the SDK-facing error message.
    """
    if not init_data or not bot_token:
        return False, "missing_init_data"

    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return False, "malformed_init_data"

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return False, "missing_hash"

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return False, "signature_mismatch"

    auth_date = pairs.get("auth_date")
    if auth_date:
        try:
            import time

            if time.time() - int(auth_date) > max_age_seconds:
                return False, "expired"
        except ValueError:
            return False, "malformed_auth_date"

    return True, None

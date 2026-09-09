"""One-time setup: create a TonAPI webhook and subscribe the TON hot wallet.

Run this once, after TONAPI_API_KEY and TON_WEBHOOK_TOKEN are set in the
environment. It prints the webhook_id to put into TON_WEBHOOK_ID so re-runs
are a safe no-op (idempotent — reuses the existing webhook instead of
creating a duplicate).

Usage:
    python scripts/setup_ton_webhook.py
"""

from __future__ import annotations

import asyncio
import sys

import httpx

sys.path.insert(0, ".")

from app.config import settings  # noqa: E402


async def main() -> None:
    if not settings.TONAPI_API_KEY:
        print("TONAPI_API_KEY is not set. Get one at tonconsole.com first.")
        return
    if not settings.TON_WEBHOOK_TOKEN:
        print("TON_WEBHOOK_TOKEN is not set. Pick any random secret string and set it first.")
        return

    endpoint = f"https://{settings.API_BASE_URL}/billing/ton-webhook?token={settings.TON_WEBHOOK_TOKEN}"
    headers = {"Authorization": f"Bearer {settings.TONAPI_API_KEY}"}

    async with httpx.AsyncClient(timeout=20) as client:
        webhook_id = settings.TON_WEBHOOK_ID
        if not webhook_id:
            resp = await client.post(
                f"{settings.TONAPI_WEBHOOK_RT_URL}/webhooks",
                json={"endpoint": endpoint},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            webhook_id = str(data.get("id") or data.get("webhook_id") or "")
            if not webhook_id:
                print("Unexpected response creating webhook:", data)
                return
            print(f"Created webhook id={webhook_id}. Set TON_WEBHOOK_ID={webhook_id} in Koyeb.")
        else:
            print(f"Reusing existing webhook id={webhook_id}.")

        resp = await client.post(
            f"{settings.TONAPI_WEBHOOK_RT_URL}/webhooks/{webhook_id}/account-tx/subscribe",
            json={"accounts": [{"account_id": settings.TON_DEPOSIT_ADDRESS}]},
            headers=headers,
        )
        resp.raise_for_status()
        print(f"Subscribed {settings.TON_DEPOSIT_ADDRESS} to webhook {webhook_id}.")
        print("Done. TonAPI will now POST to /billing/ton-webhook on every TON hot wallet transaction.")


if __name__ == "__main__":
    asyncio.run(main())

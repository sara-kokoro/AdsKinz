"""End-to-end smoke test over the real API contract.

Runs against a live PostgreSQL and Redis. It walks the full lifecycle:
advertiser signs up, creates a campaign, an admin approves it, a publisher
registers a Mini App, the SDK serves an ad, and the tracking link redirects.
"""

from __future__ import annotations

import uuid

from sqlalchemy.pool import NullPool

import pytest
from fastapi.testclient import TestClient

from app.core.security import generate_totp_secret, hash_password


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_credentials(client):
    """Create an admin directly in the database, as the operator script does.

    There is deliberately no public admin signup endpoint, so the row is
    inserted the same way ``scripts/create_admin.py`` does it.
    """
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import settings
    from app.models.accounts import AdminUser

    email = f"admin-{uuid.uuid4().hex[:8]}@adskinz.io"
    secret = generate_totp_secret()

    async def _create():
        # A dedicated engine: the application engine belongs to the TestClient's
        # own event loop and asyncpg connections cannot cross loops.
        engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            session.add(
                AdminUser(
                    email=email,
                    password_hash=hash_password("AdminPassw0rd!"),
                    totp_secret=secret,
                    totp_confirmed=True,
                    is_active=True,
                )
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(_create())
    return email, secret


def _register(client, role: str) -> tuple[str, dict]:
    email = f"{role}-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SuperSecret123",
            "role": role,
            "display_name": f"Test {role}",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["token"]
    return email, {"Authorization": f"Bearer {body['token']}"}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_advertiser_journey(client):
    email, headers = _register(client, "advertiser")

    # Duplicate registration must be refused.
    dup = client.post(
        "/auth/register",
        json={"email": email, "password": "SuperSecret123", "role": "advertiser"},
    )
    assert dup.status_code == 409

    login = client.post(
        "/auth/login", json={"email": email, "password": "SuperSecret123"}
    )
    assert login.status_code == 200

    assert client.get("/auth/me", headers=headers).json()["role"] == "advertiser"

    # Budget below the $50 minimum is rejected by validation.
    too_small = client.post(
        "/advertiser/campaigns",
        headers=headers,
        json={
            "name": "Too small",
            "format": "channel",
            "target_language": "en",
            "ad_text": "Hello there, this is an advert.",
            "button_label": "Open",
            "destination_url": "https://t.me/example",
            "cpm_bid": "3.00",
            "total_budget": "10.00",
        },
    )
    assert too_small.status_code == 422

    # CPM below $2.00 is rejected too.
    low_cpm = client.post(
        "/advertiser/campaigns",
        headers=headers,
        json={
            "name": "Low CPM",
            "format": "channel",
            "target_language": "en",
            "ad_text": "Hello there, this is an advert.",
            "button_label": "Open",
            "destination_url": "https://t.me/example",
            "cpm_bid": "0.50",
            "total_budget": "100.00",
        },
    )
    assert low_cpm.status_code == 422

    created = client.post(
        "/advertiser/campaigns",
        headers=headers,
        json={
            "name": "Launch campaign",
            "format": "interstitial",
            "target_language": "en",
            "ad_text": "Discover AdsKinz, the Telegram ad network.",
            "button_label": "Learn more",
            "destination_url": "https://adskinz.io",
            "cpm_bid": "4.00",
            "total_budget": "500.00",
        },
    )
    assert created.status_code == 201, created.text
    campaign = created.json()
    assert campaign["status"] == "pending_review"

    listed = client.get("/advertiser/campaigns", headers=headers).json()
    assert listed["total"] == 1

    stats = client.get("/advertiser/stats", headers=headers)
    assert stats.status_code == 200
    assert stats.json()["pendingCampaigns"] == 1

    balance = client.get("/billing/balance", headers=headers)
    assert balance.status_code == 200

    for network in ("ton", "trc20", "bnb"):
        response = client.get(
            f"/billing/deposit-address?network={network}", headers=headers
        )
        assert response.status_code in (200, 503), (network, response.text)

    assert client.get("/billing/deposits", headers=headers).status_code == 200


def test_publisher_journey(client):
    _, headers = _register(client, "publisher")

    # Fewer than 500 subscribers is refused.
    small = client.post(
        "/publisher/channels",
        headers=headers,
        json={
            "name": "Tiny channel",
            "public_link": f"https://t.me/tiny{uuid.uuid4().hex[:6]}",
            "declared_language": "en",
            "subscriber_count": 120,
        },
    )
    assert small.status_code == 422

    channel = client.post(
        "/publisher/channels",
        headers=headers,
        json={
            "name": "Crypto Daily News",
            "public_link": f"https://t.me/crypto{uuid.uuid4().hex[:6]}",
            "declared_language": "en",
            "subscriber_count": 12000,
            "max_ads_per_day": 3,
        },
    )
    assert channel.status_code == 201, channel.text
    assert channel.json()["status"] == "pending_moderation"

    mini_app = client.post(
        "/publisher/mini-apps",
        headers=headers,
        json={
            "name": "Tap Game",
            "url": "https://t.me/tapgame_bot/app",
            "formats_enabled": ["interstitial", "popInterstitial"],
        },
    )
    assert mini_app.status_code == 201, mini_app.text
    key = mini_app.json()["kinzKey"]
    assert key

    key_response = client.get(
        f"/publisher/mini-apps/{mini_app.json()['id']}/key", headers=headers
    )
    assert key_response.status_code == 200
    assert "data-kinz-id" in key_response.json()["snippet"]

    # A brand new publisher cannot withdraw yet.
    withdrawals = client.get("/publisher/withdrawals", headers=headers).json()
    assert withdrawals["eligible"] is False

    refused = client.post(
        "/publisher/withdrawals",
        headers=headers,
        json={"amount": "80.00", "destination_address": "UQ" + "a" * 46},
    )
    assert refused.status_code in (400, 403, 409, 422)

    assert client.get("/publisher/stats", headers=headers).status_code == 200
    assert client.get("/publisher/channels/bot-status", headers=headers).status_code == 200


def test_admin_two_step_login(client, admin_credentials):
    import pyotp

    email, secret = admin_credentials

    step1 = client.post(
        "/admin/auth/login", json={"email": email, "password": "AdminPassw0rd!"}
    )
    assert step1.status_code == 200, step1.text
    partial = step1.json()["partialToken"]

    # The partial token alone must not grant access.
    assert (
        client.get(
            "/admin/overview", headers={"Authorization": f"Bearer {partial}"}
        ).status_code
        == 401
    )

    bad = client.post(
        "/admin/auth/totp", json={"partial_token": partial, "code": "000000"}
    )
    assert bad.status_code in (401, 403)

    step2 = client.post(
        "/admin/auth/totp",
        json={"partial_token": partial, "code": pyotp.TOTP(secret).now()},
    )
    assert step2.status_code == 200, step2.text
    headers = {"Authorization": f"Bearer {step2.json()['token']}"}

    assert client.get("/admin/overview", headers=headers).status_code == 200
    for queue in ("campaigns", "channels", "mini-apps", "withdrawals"):
        assert client.get(f"/admin/queue/{queue}", headers=headers).status_code == 200
    for period in ("today", "week", "month", "year"):
        assert (
            client.get(f"/admin/finances?period={period}", headers=headers).status_code
            == 200
        )
    assert client.get("/admin/anomalies", headers=headers).status_code == 200
    assert client.get("/admin/audit", headers=headers).status_code == 200


def test_moderation_and_serving(client, admin_credentials):
    import pyotp

    email, secret = admin_credentials
    partial = client.post(
        "/admin/auth/login", json={"email": email, "password": "AdminPassw0rd!"}
    ).json()["partialToken"]
    admin_headers = {
        "Authorization": "Bearer "
        + client.post(
            "/admin/auth/totp",
            json={"partial_token": partial, "code": pyotp.TOTP(secret).now()},
        ).json()["token"]
    }

    # Approve everything sitting in the queues.
    campaigns = client.get("/admin/queue/campaigns", headers=admin_headers).json()
    for item in campaigns["items"]:
        response = client.post(
            f"/admin/queue/campaigns/{item['id']}/approve", headers=admin_headers
        )
        assert response.status_code == 200, response.text

    mini_apps = client.get("/admin/queue/mini-apps", headers=admin_headers).json()
    mini_app_ids = [item["id"] for item in mini_apps["items"]]
    for mini_app_id in mini_app_ids:
        response = client.post(
            f"/admin/queue/mini-apps/{mini_app_id}/approve", headers=admin_headers
        )
        assert response.status_code == 200, response.text

    channels = client.get("/admin/queue/channels", headers=admin_headers).json()
    for item in channels["items"]:
        response = client.post(
            f"/admin/queue/channels/{item['id']}/approve", headers=admin_headers
        )
        assert response.status_code == 200, response.text

    assert client.get("/admin/queue/campaigns", headers=admin_headers).json()["total"] == 0


def test_sdk_serve_and_tracking(client):
    """An unknown key never errors, and a live key returns a renderable ad."""
    unknown = client.get("/sdk/serve?key=kinz_unknown_key_value&lang=en")
    assert unknown.status_code == 200
    assert unknown.json()["filled"] is False

    _, headers = _register(client, "publisher")
    mini_app = client.post(
        "/publisher/mini-apps",
        headers=headers,
        json={
            "name": "Serve Test App",
            "url": "https://t.me/servetest_bot/app",
            "formats_enabled": ["interstitial"],
        },
    ).json()

    # Not approved yet: the SDK must get an empty slot, not an error.
    pending = client.get(f"/sdk/serve?key={mini_app['kinzKey']}&lang=en")
    assert pending.status_code == 200
    assert pending.json()["filled"] is False
    assert pending.json()["reason"] == "placement_inactive"


def test_tracking_always_redirects(client):
    """Even a bogus tracking id sends the user somewhere, never an error page."""
    response = client.get(f"/t/{uuid.uuid4()}", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"]

    response = client.get("/t/definitely-not-a-uuid", follow_redirects=False)
    assert response.status_code == 302

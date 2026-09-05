"""Redis layer: cache, distributed locks, rate limiting, spend buffering.

Redis is the hot path in front of PostgreSQL:

* ``/sdk/serve`` reads a cached ad-selection result instead of re-running the
  auction query on every impression.
* Budget decrements are serialised through a distributed lock so two concurrent
  impressions can never overspend a campaign.
* Click de-duplication and IP-frequency fraud signals live in short-TTL keys.
* Rate limiting for login, ad serving and Groq generation.

Every helper degrades gracefully: if ``REDIS_ENABLED`` is false or the server is
unreachable, calls become no-ops and the caller falls back to PostgreSQL. The
API must never 500 because Redis blinked.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio.client import Redis
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger(__name__)

_client: Redis | None = None
_unavailable_logged = False


# --------------------------------------------------------------------------- #
# Connection lifecycle
# --------------------------------------------------------------------------- #
async def init_redis() -> Redis | None:
    """Create the shared connection pool. Called once on application startup."""
    global _client
    if not settings.REDIS_ENABLED:
        logger.info("Redis disabled by configuration; running without cache")
        return None
    if _client is not None:
        return _client
    try:
        _client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=10,
            socket_timeout=10,
            health_check_interval=30,
            retry_on_timeout=True,
        )
        await _client.ping()
        logger.info("Redis connected")
    except (RedisError, OSError) as exc:  # pragma: no cover - infra dependent
        logger.warning("Redis unavailable at startup (%s); continuing without it", exc)
        _client = None
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def get_redis() -> Redis | None:
    return _client


async def redis_healthy() -> bool:
    if _client is None:
        return False
    try:
        await _client.ping()
        return True
    except (RedisError, OSError):
        return False


def _warn_once(exc: Exception) -> None:
    global _unavailable_logged
    if not _unavailable_logged:
        logger.warning("Redis operation failed, falling back to PostgreSQL: %s", exc)
        _unavailable_logged = True


# --------------------------------------------------------------------------- #
# Generic JSON cache
# --------------------------------------------------------------------------- #
async def cache_get(key: str) -> Any | None:
    if _client is None:
        return None
    try:
        raw = await _client.get(settings.ns("cache", key))
    except (RedisError, OSError) as exc:
        _warn_once(exc)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    if _client is None:
        return
    try:
        await _client.set(settings.ns("cache", key), json.dumps(value, default=str), ex=ttl)
    except (RedisError, OSError) as exc:
        _warn_once(exc)


async def cache_delete(*keys: str) -> None:
    if _client is None or not keys:
        return
    try:
        await _client.delete(*[settings.ns("cache", k) for k in keys])
    except (RedisError, OSError) as exc:
        _warn_once(exc)


async def cache_delete_pattern(pattern: str) -> int:
    """Delete every key matching a glob pattern. Uses SCAN, never KEYS."""
    if _client is None:
        return 0
    deleted = 0
    try:
        async for key in _client.scan_iter(match=settings.ns("cache", pattern), count=200):
            await _client.delete(key)
            deleted += 1
    except (RedisError, OSError) as exc:
        _warn_once(exc)
    return deleted


# --------------------------------------------------------------------------- #
# Distributed lock (SET NX PX + Lua-guarded release)
# --------------------------------------------------------------------------- #
_RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


@asynccontextmanager
async def distributed_lock(
    name: str,
    timeout: int | None = None,
    wait: float = 3.0,
    poll: float = 0.05,
) -> AsyncIterator[bool]:
    """Acquire a named lock. Yields True when held, False when Redis is absent.

    A False yield means the caller must rely on the database-level guarantee
    (``SELECT ... FOR UPDATE``) instead, which every critical path also does.
    """
    if _client is None:
        yield False
        return

    key = settings.ns("lock", name)
    token = uuid.uuid4().hex
    ttl_ms = (timeout or settings.LOCK_TIMEOUT_SECONDS) * 1000
    acquired = False
    deadline = asyncio.get_event_loop().time() + wait

    try:
        while True:
            try:
                acquired = bool(await _client.set(key, token, nx=True, px=ttl_ms))
            except (RedisError, OSError) as exc:
                _warn_once(exc)
                yield False
                return
            if acquired or asyncio.get_event_loop().time() >= deadline:
                break
            await asyncio.sleep(poll)
        yield acquired
    finally:
        if acquired:
            try:
                await _client.eval(_RELEASE_LUA, 1, key, token)
            except (RedisError, OSError) as exc:
                _warn_once(exc)


# --------------------------------------------------------------------------- #
# Rate limiting (fixed window counter)
# --------------------------------------------------------------------------- #
async def rate_limit_hit(bucket: str, identifier: str, limit: int, window: int) -> tuple[bool, int]:
    """Register one hit. Returns ``(allowed, remaining)``.

    Fails open: when Redis is down every request is allowed.
    """
    if _client is None:
        return True, limit
    key = settings.ns("rl", bucket, identifier)
    try:
        pipe = _client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window, nx=True)
        count, _ = await pipe.execute()
    except (RedisError, OSError) as exc:
        _warn_once(exc)
        return True, limit
    count = int(count)
    return count <= limit, max(0, limit - count)


# --------------------------------------------------------------------------- #
# Campaign spend buffer
# --------------------------------------------------------------------------- #
# Impressions and clicks increment a Redis counter first (microsecond writes),
# and a background job flushes the accumulated amount into `campaigns.spent_usd`
# every `JOB_SPEND_FLUSH_MINUTES`. Reads that need an exact figure add the
# buffered delta on top of the persisted value.
_SPEND_BUFFER_KEY = "spend_buffer"


async def buffer_spend(campaign_id: uuid.UUID | str, amount: Decimal) -> bool:
    """Accumulate spend for a campaign. Returns False when Redis is unavailable."""
    if _client is None or amount <= 0:
        return False
    try:
        await _client.hincrbyfloat(
            settings.ns(_SPEND_BUFFER_KEY), str(campaign_id), float(amount)
        )
        return True
    except (RedisError, OSError) as exc:
        _warn_once(exc)
        return False


async def peek_buffered_spend(campaign_id: uuid.UUID | str) -> Decimal:
    if _client is None:
        return Decimal("0")
    try:
        raw = await _client.hget(settings.ns(_SPEND_BUFFER_KEY), str(campaign_id))
    except (RedisError, OSError) as exc:
        _warn_once(exc)
        return Decimal("0")
    return Decimal(str(raw)) if raw else Decimal("0")


async def drain_spend_buffer() -> dict[str, Decimal]:
    """Atomically read and clear the whole buffer. Used by the flush job."""
    if _client is None:
        return {}
    key = settings.ns(_SPEND_BUFFER_KEY)
    try:
        pipe = _client.pipeline()
        pipe.hgetall(key)
        pipe.delete(key)
        raw, _ = await pipe.execute()
    except (RedisError, OSError) as exc:
        _warn_once(exc)
        return {}
    return {cid: Decimal(str(v)) for cid, v in (raw or {}).items() if Decimal(str(v)) > 0}


# --------------------------------------------------------------------------- #
# Fraud / click signals
# --------------------------------------------------------------------------- #
async def click_velocity(ip_hash: str, window: int = 300) -> int:
    """Number of clicks seen from this hashed IP inside the rolling window."""
    if _client is None:
        return 0
    key = settings.ns("click_vel", ip_hash)
    try:
        pipe = _client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window, nx=True)
        count, _ = await pipe.execute()
        return int(count)
    except (RedisError, OSError) as exc:
        _warn_once(exc)
        return 0


async def claim_once(key: str, ttl: int) -> bool:
    """Idempotency guard. True the first time, False for replays inside the TTL."""
    if _client is None:
        return True
    try:
        return bool(await _client.set(settings.ns("once", key), "1", nx=True, ex=ttl))
    except (RedisError, OSError) as exc:
        _warn_once(exc)
        return True


# --------------------------------------------------------------------------- #
# Channel daily quota counters
# --------------------------------------------------------------------------- #
async def incr_channel_daily_posts(channel_id: uuid.UUID | str, day: str) -> int:
    if _client is None:
        return 0
    key = settings.ns("chan_posts", str(channel_id), day)
    try:
        pipe = _client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 172_800, nx=True)  # keep two days of history
        count, _ = await pipe.execute()
        return int(count)
    except (RedisError, OSError) as exc:
        _warn_once(exc)
        return 0


async def get_channel_daily_posts(channel_id: uuid.UUID | str, day: str) -> int | None:
    if _client is None:
        return None
    try:
        raw = await _client.get(settings.ns("chan_posts", str(channel_id), day))
    except (RedisError, OSError) as exc:
        _warn_once(exc)
        return None
    return int(raw) if raw is not None else None

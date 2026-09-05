"""APScheduler lifecycle and durable scheduling policy for AdsKinz jobs."""

from __future__ import annotations

import inspect
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.redis_client import distributed_lock, get_redis

from .budget import spend_flush
from .channels import bot_admin_check, channel_trust_expiry, refresh_channel_subscribers
from .deposits import deposit_watcher
from .fraud import fraud_scan
from .posts import auto_delete_posts, expire_posts_for_inactive_campaigns, post_dispatch
from .views import views_polling

logger = logging.getLogger(__name__)

JobFunction = Callable[[], Awaitable[dict[str, Any]]]
JOB_LOCK_TIMEOUT_SECONDS = 15 * 60
_scheduler: AsyncIOScheduler | None = None


async def _run(name: str, coro_fn: JobFunction) -> None:
    """Execute one job safely, preventing a job failure from stopping APScheduler."""
    started = time.perf_counter()
    try:
        # The job-level lock is a nice-to-have for deployment topologies with
        # multiple API containers, guarding against two of them running the
        # same job at once. It must never become the reason a job doesn't
        # run at all: when Redis is unreachable, distributed_lock always
        # yields False (see its own docstring), and treating that as "a
        # peer already has it" — as this used to — means every scheduled
        # job silently no-ops forever the moment Redis is down or
        # unconfigured, while manually calling the same job function
        # directly (e.g. the /admin/debug/run-* endpoints) still works,
        # since those bypass this lock entirely. That mismatch is exactly
        # what made "it only posts when I curl it" true. So: log-and-skip
        # only ever happens for the one case that's actually a real skip
        # (see below); anything else runs the job regardless of the lock.
        async with distributed_lock(
            f"job:{name}", timeout=JOB_LOCK_TIMEOUT_SECONDS, wait=0
        ) as acquired:
            if not acquired and get_redis() is not None:
                # Redis is up and another container genuinely holds this
                # job's lock right now — an actual, intentional skip.
                logger.info("jobs.skipped_for_lock name=%s", name)
                return
            if not acquired:
                logger.info("jobs.lock_unavailable name=%s — running anyway (Redis is down)", name)
            result = coro_fn()
            if inspect.isawaitable(result):
                result = await result
            logger.info(
                "jobs.completed name=%s summary=%s",
                name,
                result,
            )
    except Exception:  # noqa: BLE001 - no scheduled job may kill the scheduler
        logger.exception(
            "jobs.failed name=%s duration_seconds=%.3f",
            name,
            time.perf_counter() - started,
        )
    finally:
        logger.info(
            "jobs.duration name=%s duration_seconds=%.3f",
            name,
            time.perf_counter() - started,
        )


def _add_interval_job(
    scheduler: AsyncIOScheduler, name: str, func: JobFunction, minutes: int
) -> None:
    scheduler.add_job(
        _run,
        trigger=IntervalTrigger(minutes=minutes, timezone=UTC),
        args=(name, func),
        id=name,
        name=name,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )


def _register_jobs(scheduler: AsyncIOScheduler) -> None:
    if not settings.ENABLE_SCHEDULER:
        return

    _add_interval_job(scheduler, "auto_delete_posts", auto_delete_posts, 5)
    _add_interval_job(
        scheduler, "expire_posts_for_inactive_campaigns", expire_posts_for_inactive_campaigns, 1
    )
    _add_interval_job(scheduler, "refresh_channel_subscribers", refresh_channel_subscribers, 1)
    _add_interval_job(scheduler, "views_polling", views_polling, 15)
    _add_interval_job(scheduler, "deposit_watcher", deposit_watcher, 2)
    _add_interval_job(scheduler, "channel_trust_expiry", channel_trust_expiry, 60)
    scheduler.add_job(
        _run,
        trigger=CronTrigger(hour=3, minute=0, timezone=UTC),
        args=("bot_admin_check", bot_admin_check),
        id="bot_admin_check",
        name="bot_admin_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    # Wallet-level low-balance pausing and cross-campaign balance allocation
    # are retired: each campaign's budget is now isolated money reserved at
    # top-up time, so the shared wallet balance can no longer starve a
    # running campaign mid-flight.
    _add_interval_job(scheduler, "post_dispatch", post_dispatch, 10)
    _add_interval_job(scheduler, "spend_flush", spend_flush, 1)
    _add_interval_job(scheduler, "fraud_scan", fraud_scan, 30)


def get_scheduler() -> AsyncIOScheduler:
    """Return the process-wide scheduler, registering jobs when enabled."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone=UTC)
        _register_jobs(_scheduler)
    return _scheduler


async def start_scheduler() -> None:
    """Start APScheduler only when scheduled work is enabled by configuration."""
    if not settings.ENABLE_SCHEDULER:
        logger.info("jobs.scheduler_disabled")
        return
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("jobs.scheduler_started jobs=%s", len(scheduler.get_jobs()))


async def shutdown_scheduler() -> None:
    """Stop the scheduler without waiting for a slow external API call."""
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("jobs.scheduler_stopped")

"""AdsKinz API — application entrypoint.

Single FastAPI application, single container, deployed on Koyeb. Everything it
needs comes from environment variables; nothing is hardcoded.

Startup order matters: Redis first (the ad selection cache and the distributed
locks depend on it), then the scheduler, then the Telegram integrations. Each
of those is optional and degrades gracefully — the API must still answer even
if Telegram or Redis is unreachable.
"""

from __future__ import annotations

import logging
import logging.config
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.core.errors import register_exception_handlers
from app.database import dispose_engine
from app.redis_client import close_redis, init_redis
from app.routers import admin, advertiser, auth, billing, publisher, sdk, tracking

logger = logging.getLogger("adskinz")


def _configure_logging() -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s %(levelname)-8s %(name)s %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"handlers": ["console"], "level": settings.LOG_LEVEL},
            "loggers": {
                "uvicorn.access": {"level": "WARNING"},
                "aiogram": {"level": "WARNING"},
                "pyrogram": {"level": "WARNING"},
                "apscheduler": {"level": "WARNING"},
                "httpx": {"level": "WARNING"},
            },
        }
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _configure_logging()
    logger.info(
        "adskinz.starting env=%s version=%s", settings.ENVIRONMENT, settings.APP_VERSION
    )

    await init_redis()

    scheduler_started = False
    if settings.ENABLE_SCHEDULER:
        try:
            from app.jobs.scheduler import start_scheduler

            await start_scheduler()
            scheduler_started = True
        except Exception:  # noqa: BLE001
            logger.exception("adskinz.scheduler_failed")

    bot_started = False
    if settings.ENABLE_BOT:
        try:
            from app.bot.aiogram_bot import start_bot

            await start_bot()
            bot_started = True
        except Exception:  # noqa: BLE001
            logger.exception("adskinz.bot_failed")

    mtproto_started = False
    if settings.ENABLE_MTPROTO:
        try:
            from app.mtproto.client import start_client_background

            await start_client_background()
            mtproto_started = True
        except Exception:  # noqa: BLE001
            logger.exception("adskinz.mtproto_failed")

    logger.info(
        "adskinz.started scheduler=%s bot=%s mtproto=%s",
        scheduler_started,
        bot_started,
        mtproto_started,
    )

    try:
        yield
    finally:
        logger.info("adskinz.shutting_down")

        if mtproto_started:
            try:
                from app.mtproto.client import stop_client

                await stop_client()
            except Exception:  # noqa: BLE001
                logger.exception("adskinz.mtproto_stop_failed")

        if bot_started:
            try:
                from app.bot.aiogram_bot import stop_bot

                await stop_bot()
            except Exception:  # noqa: BLE001
                logger.exception("adskinz.bot_stop_failed")

        if scheduler_started:
            try:
                from app.jobs.scheduler import shutdown_scheduler

                await shutdown_scheduler()
            except Exception:  # noqa: BLE001
                logger.exception("adskinz.scheduler_stop_failed")

        await close_redis()
        await dispose_engine()
        logger.info("adskinz.stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AdsKinz API",
        version=settings.APP_VERSION,
        description=(
            "Telegram advertising network: campaigns, channel and Mini App "
            "placements, USDT deposits and payouts."
        ),
        lifespan=lifespan,
        docs_url="/docs" if settings.ENABLE_API_DOCS else None,
        redoc_url="/redoc" if settings.ENABLE_API_DOCS else None,
        openapi_url="/openapi.json" if settings.ENABLE_API_DOCS else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
        max_age=3600,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    if settings.ALLOWED_HOSTS:
        app.add_middleware(
            TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list
        )

    register_exception_handlers(app)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        """Propagate a request id so a frontend error can be traced in the logs."""
        import uuid as _uuid

        request_id = request.headers.get("X-Request-Id") or _uuid.uuid4().hex[:16]
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response

    # Order matters only for readability; the paths do not overlap.
    app.include_router(auth.router)
    app.include_router(auth.admin_auth_router)
    app.include_router(advertiser.router)
    app.include_router(billing.router)
    app.include_router(publisher.router)
    app.include_router(admin.router)
    app.include_router(sdk.router)
    app.include_router(tracking.router)

    @app.api_route("/", methods=["GET", "HEAD"], tags=["ops"], summary="Service banner")
    async def root() -> dict[str, str]:
        return {
            "service": "adskinz-api",
            "version": settings.APP_VERSION,
            "status": "ok",
            "docs": "/docs" if settings.ENABLE_API_DOCS else "disabled",
        }

    return app


app = create_app()

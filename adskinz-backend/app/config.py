"""Application configuration.

Every value is read from the environment. Nothing sensitive is ever hard-coded.
See `.env.example` for the full list of expected variables.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Network = Literal["ton", "trc20", "bnb"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ #
    # Runtime
    # ------------------------------------------------------------------ #
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"
    ENABLE_API_DOCS: bool = True
    API_BASE_URL: str = "https://api.adskinz.io"
    PUBLIC_BASE_URL: str = "https://adskinz.io"
    CORS_ORIGINS: str = "http://localhost:3000,https://adskinz.io,https://kingcey.adskinz.io"
    CORS_ORIGIN_REGEX: str = ""
    # Comma-separated Host header allowlist. Empty disables the check, which is
    # the right default behind a platform proxy that already filters hosts.
    ALLOWED_HOSTS: str = ""

    # ------------------------------------------------------------------ #
    # Mini App SDK
    # ------------------------------------------------------------------ #
    SDK_SERVE_RATE_LIMIT: int = 600
    SDK_SERVE_RATE_WINDOW: int = 60
    SDK_CREATIVE_TTL: int = 30
    TRACKING_LINK_TTL_DAYS: int = 30
    # A click costs this multiple of one impression at the campaign's CPM.
    CLICK_PRICE_MULTIPLIER: Decimal = Decimal("7")

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    DATABASE_URL: str = "postgresql+asyncpg://adskinz:adskinz@localhost:5432/adskinz"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False

    # ------------------------------------------------------------------ #
    # Redis — cache, distributed locks, rate limiting, fraud dedup
    # ------------------------------------------------------------------ #
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = True
    REDIS_NAMESPACE: str = "adskinz"
    # TTL (seconds) for the ad-selection cache used by /sdk/serve
    AD_SELECTION_CACHE_TTL: int = 20
    # TTL for the campaign spend counters mirrored in Redis before flush to PG
    SPEND_BUFFER_FLUSH_SECONDS: int = 30
    # How long a distributed lock is held before it auto-expires
    LOCK_TIMEOUT_SECONDS: int = 10

    # ------------------------------------------------------------------ #
    # Security / auth
    # ------------------------------------------------------------------ #
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TTL_DAYS: int = 7
    ADMIN_PARTIAL_TOKEN_TTL_SECONDS: int = 300  # token between /login and /totp
    ADMIN_SESSION_TTL_HOURS: int = 12
    IP_HASH_SALT: str = "change-me-too"
    TOTP_ISSUER: str = "AdsKinz"

    # Rate limits (requests per window, window in seconds)
    RATE_LIMIT_LOGIN: int = 10
    RATE_LIMIT_LOGIN_WINDOW: int = 300
    RATE_LIMIT_SERVE: int = 600
    RATE_LIMIT_SERVE_WINDOW: int = 60
    RATE_LIMIT_GENERATE: int = 20
    RATE_LIMIT_GENERATE_WINDOW: int = 3600

    # ------------------------------------------------------------------ #
    # Telegram
    # ------------------------------------------------------------------ #
    BOT_TOKEN: str = ""
    BOT_USERNAME: str = "AdsKinzBot"
    MTPROTO_API_ID: int = 0
    MTPROTO_API_HASH: str = ""
    MTPROTO_SESSION_STRING: str = ""
    ENABLE_BOT: bool = False
    ENABLE_MTPROTO: bool = False
    ENABLE_SCHEDULER: bool = True

    # ------------------------------------------------------------------ #
    # Groq (ad copy generation + translations)
    # ------------------------------------------------------------------ #
    GROQ_API_KEY: str = "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"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_TIMEOUT_SECONDS: float = 30.0

    # ------------------------------------------------------------------ #
    # Wallets — WATCH-ONLY. The backend never holds a full mnemonic seed.
    # ------------------------------------------------------------------ #
    XPUB_TRC20: str = ""
    XPUB_BEP20: str = ""
    TON_DEPOSIT_ADDRESS: str = ""
    # Wallet 2 (payouts) — separate key, only used for withdrawal disbursement.
    WALLET_2_PRIVATE_KEY: str = ""
    WALLET_2_ADDRESS: str = ""
    ENABLE_AUTO_PAYOUT: bool = False

    TRONGRID_API_KEY: str = ""
    TRONGRID_BASE_URL: str = "https://api.trongrid.io"
    BSCSCAN_API_KEY: str = ""
    BSCSCAN_BASE_URL: str = "https://api.bscscan.com/api"
    TONCENTER_API_KEY: str = ""
    TONCENTER_BASE_URL: str = "https://toncenter.com/api/v2"

    USDT_TRC20_CONTRACT: str = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    USDT_BEP20_CONTRACT: str = "0x55d398326f99059fF775485246999027B3197955"
    USDT_TON_JETTON_MASTER: str = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"

    DEPOSIT_MIN_CONFIRMATIONS_TRC20: int = 19
    DEPOSIT_MIN_CONFIRMATIONS_BEP20: int = 12
    DEPOSIT_MIN_CONFIRMATIONS_TON: int = 1

    # ------------------------------------------------------------------ #
    # Email (SMTP)
    # ------------------------------------------------------------------ #
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "AdsKinz <no-reply@adskinz.io>"
    SMTP_USE_TLS: bool = True
    ADMIN_ALERT_EMAIL: str = ""
    ENABLE_EMAIL: bool = False

    # ------------------------------------------------------------------ #
    # Business rules — single source of truth, enforced server-side
    # ------------------------------------------------------------------ #
    MIN_CAMPAIGN_BUDGET: Decimal = Decimal("50.00")
    MIN_CPM_BID: Decimal = Decimal("2.00")
    MIN_DAILY_BUDGET: Decimal = Decimal("2.00")
    MIN_WITHDRAWAL: Decimal = Decimal("50.00")
    MIN_CHANNEL_SUBSCRIBERS: int = 500
    MIN_CHANNEL_NAME_LENGTH: int = 5
    MAX_ADS_PER_DAY: int = 3
    # Ads per day allowed while a channel is in its trust window
    TRUST_WINDOW_MAX_ADS_PER_DAY: int = 1
    TRUST_WINDOW_HOURS: int = 72
    # Delay after the first channel approval before a payout may be requested
    WITHDRAWAL_COOLDOWN_HOURS: int = 48
    POST_LIFETIME_HOURS: int = 24
    PLATFORM_COMMISSION_RATE: Decimal = Decimal("0.35")
    TRC20_DEPOSIT_FEE_USDT: Decimal = Decimal("3.25")
    LOW_BALANCE_ALERT_RATIO: Decimal = Decimal("0.10")
    FRAUD_SCORE_BILLING_THRESHOLD: Decimal = Decimal("0.70")
    SUPPORTED_TRANSLATION_LANGS: str = "en,fr,ru,zh"
    DEFAULT_WITHDRAWAL_MEMO: str = "AdsKinz"

    # ------------------------------------------------------------------ #
    # Job intervals (minutes unless stated)
    # ------------------------------------------------------------------ #
    JOB_AUTO_DELETE_MINUTES: int = 5
    JOB_VIEWS_POLLING_MINUTES: int = 15
    JOB_DEPOSIT_WATCHER_MINUTES: int = 2
    JOB_TRUST_EXPIRY_MINUTES: int = 60
    JOB_BOT_ADMIN_CHECK_HOURS: int = 24
    JOB_LOW_BALANCE_MINUTES: int = 60
    JOB_BUDGET_ALLOCATION_MINUTES: int = 10
    JOB_POST_DISPATCH_MINUTES: int = 5
    JOB_SPEND_FLUSH_MINUTES: int = 1

    # ------------------------------------------------------------------ #
    # Derived helpers
    # ------------------------------------------------------------------ #
    @field_validator("DATABASE_URL")
    @classmethod
    def _normalise_db_url(cls, value: str) -> str:
        """Accept plain postgres:// URLs (Neon default) and upgrade the driver."""
        if value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql://", 1)
        if value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
        # asyncpg rejects libpq-style sslmode; translate it to its own kwarg.
        if "sslmode=" in value:
            value = value.replace("sslmode=require", "ssl=require")
            value = value.replace("sslmode=prefer", "ssl=prefer")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # Alias kept because the application factory reads ``cors_origins``.
    @property
    def cors_origins(self) -> list[str]:
        return self.cors_origin_list

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]

    @property
    def translation_langs(self) -> list[str]:
        return [c.strip() for c in self.SUPPORTED_TRANSLATION_LANGS.split(",") if c.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    def tracking_link(self, tracking_id: object) -> str:
        return f"{self.PUBLIC_BASE_URL.rstrip('/')}/t/{tracking_id}"

    def ns(self, *parts: str) -> str:
        """Build a namespaced Redis key."""
        return ":".join([self.REDIS_NAMESPACE, *parts])


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

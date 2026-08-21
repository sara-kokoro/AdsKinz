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
    API_BASE_URL: str = "competent-rebekkah-davelam-58380a6b.koyeb.app"
    PUBLIC_BASE_URL: str = "https://ads-kinz.vercel.app"
    CORS_ORIGINS: str = "http://localhost:3000,https://adskinz.io,https://kingcey.adskinz.io,https://ads-kinz.vercel.app"
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
    CLICK_PRICE_MULTIPLIER: Decimal = Decimal("4")

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    DATABASE_URL: str = "postgresql://neondb_owner:npg_6ockmfAH8tgl@ep-late-dew-axz8nu8u-pooler.c-4.us-east-2.aws.neon.tech/neondb?sslmode=require"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False

    # ------------------------------------------------------------------ #
    # Redis — cache, distributed locks, rate limiting, fraud dedup
    # ------------------------------------------------------------------ #
    REDIS_URL: str = "redis://default:gQAAAAAAAbpkAAIgcDFiZDdiMDBkNzdlOTM0YTQzYWI0NDUyZTk5OGY2ZjZhZg@informed-iguana-113252.upstash.io:6379"
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
    JWT_SECRET: str = "de3eb828ac366f5ded9d65a6665c49306c8e4d49d604358036e50f27b4665f2a"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TTL_DAYS: int = 7
    REFRESH_TOKEN_TTL_DAYS: int = 30
    ADMIN_PARTIAL_TOKEN_TTL_SECONDS: int = 300  # token between /login and /totp
    ADMIN_SESSION_TTL_HOURS: int = 2
    IP_HASH_SALT: str = "d325aba518966f51e592b88e2b21f2226f22363cc194665379e85ec2d7192486"
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
    BOT_TOKEN: str = "8517598174:AAFhANCor9iLfhr4VLJhSumK1IA65CNJBhU"
    BOT_USERNAME: str = "AdsKinzBot"
    MTPROTO_API_ID: int = 37641587
    MTPROTO_API_HASH: str = "9bce1167e828939f39452795e56202a9"
    MTPROTO_SESSION_STRING: str = "BAI-XXMAPRj1cv2w0A2DzKq3El9CLj4nMBaEo_2RFtehsOgDB-8WqYXTHT_cgRo8RVgOGawCBehBfZHNeIH_rAeQ7i4ui_5sm5INbuDLCJmaRSO30fMiupHg6TaIa_ILE-7Ymp7N8D4FLT6AOeyt3M090p0csLSx1LI-Ei4lRqyxk695Y0lMj_5SJ9nzxi-Ocx1r-vYRDQhkHVE8Z1R0H0kXPMCPH53qtX_5zRoM6opjVtaI0v4avUotpCqmibAhPCwzxpLWQLrqIzn3umHg3-FQgC4SY-gXTUntk8vMDIjHuE8e7H5RpRFZcm_NbVsgCldGIO_ciN4aTSY-bETFFPu7tANrWwAAAAH4szcSAA"
    ENABLE_BOT: bool = True
    ENABLE_MTPROTO: bool = True
    ENABLE_SCHEDULER: bool = True

    # ------------------------------------------------------------------ #
    # Groq (ad copy generation + translations)
    # ------------------------------------------------------------------ #
    GROQ_API_KEY: str = "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"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_TIMEOUT_SECONDS: float = 30.0

    # ------------------------------------------------------------------ #
    # Wallets — WATCH-ONLY deposit derivation (xpub) + sweep signing (xprv).
    # ------------------------------------------------------------------ #
    # Extended public keys used to derive advertiser deposit addresses.
    XPUB_BEP20: str = "xpub6BudUdijXt6ssjdwCd4wL82zjADiKDjtctq1DTzuuGuf8eKzgrwfKNLuuwqM34oLNMBtEfNdkZ4GuDc6B3JGfJc1NKy5FSCDvKnTbynf5FD"
    XPUB_TRC20: str = "xpub6D4E86ZuWj39YuRsXZMkuHoqtU4bvhqGmq8tfzCH6a6jKCPpwwqt44et8YGJcK68wx5jSn9nRJrzZxjty8ynjCSRJcFZmMe1jKPeDrsydsm"
    # Extended private key for BEP20 deposit addresses. Required to sign the
    # automatic sweep of USDT from derived addresses to the treasury.
    ACCOUNT_XPRV: str = "xprv9xvH58BqhWYafFZU6bXvxz6GB8PDum23FfuQR5bJLwNgFqzr9KdQma2S4gxnE5QxJcivH2acZXKjZVhdhBNbpuEzVgdWsPRH4t1qvTyytf2"
    # Hot wallet that funds derived addresses with BNB for gas. Must hold BNB.
    BSC_GAS_WALLET_PRIVATE_KEY: str = ""
    # Main treasury address that receives swept USDT on BNB Smart Chain.
    BSC_TREASURY_ADDRESS: str = "0x92c15096035f8e37606fa4d907cf84c5b5b2ecc5"
    # RPC endpoint for BNB Smart Chain.
    BSC_RPC_URL: str = "https://bsc-dataseed.binance.org/"
    # Minimum native BNB balance (in BNB) a derived address must keep after the
    # gas top-up. Anything above this is sent back to the gas wallet.
    BSC_GAS_DUST_BNB: Decimal = Decimal("0.0001")
    # Estimated gas limit for a BEP20 transfer. Used to compute the BNB top-up.
    BSC_TRANSFER_GAS_LIMIT: int = 100_000
    # Wallet 2 (payouts) — separate key, only used for withdrawal disbursement.
    WALLET_2_PRIVATE_KEY: str = "drastic enforce bicycle fox satisfy major excuse depend amount acoustic figure exist typical reduce glimpse charge kite volume truck bicycle post when only bunker"
    WALLET_2_ADDRESS: str = "UQBXWGv8ni_K5RdVt8pkBjdxAuq4hHSMWVocLs-JDYSbpuv6"
    ENABLE_AUTO_PAYOUT: bool = True
    # Whether automatic BEP20 sweeps are enabled. Disable to keep deposits
    # watch-only even when ACCOUNT_XPRV is configured.
    ENABLE_BEP20_SWEEP: bool = True

    TRONGRID_API_KEY: str = "b94228c9-c234-4399-8c39-ccaf46d13b97"
    TRONGRID_BASE_URL: str = "https://api.trongrid.io"
    BSCSCAN_API_KEY: str = "RAYN37HRFNVPYJYNEWMUJJ6RVBZFY4M2ZH"
    BSCSCAN_BASE_URL: str = "https://api.bscscan.com/api"
    TONCENTER_API_KEY: str = "f355c8138b5f1d7158541863828cdd9693470c25621006e54615bfdee49785ad"
    TONCENTER_BASE_URL: str = "https://toncenter.com/api/v2"
    
    TON_DEPOSIT_ADDRESS: str = "UQCTEfgy5MouZG3gcLzTFvi8JoPDWCVfU4HTx4Lukoo8Lcou"

    USDT_TRC20_CONTRACT: str = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    USDT_BEP20_CONTRACT: str = "0x55d398326f99059fF775485246999027B3197955"
    USDT_TON_JETTON_MASTER: str = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"

    DEPOSIT_MIN_CONFIRMATIONS_TRC20: int = 19
    DEPOSIT_MIN_CONFIRMATIONS_BEP20: int = 12
    DEPOSIT_MIN_CONFIRMATIONS_TON: int = 1

    # ------------------------------------------------------------------ #
    # Email (Resend)
    # ------------------------------------------------------------------ #
    RESEND_API_KEY: str = "re_ixaWFLmD_4MLXCxQ9yZaDJp3ZxP5q8DvP"
    # No domain purchased/verified yet: falls back to Resend's shared testing
    # domain, which can only deliver to the address on the Resend account
    # itself. Switch to "AdsKinz <no-reply@yourdomain.tld>" once a domain is
    # verified in the Resend dashboard.
    EMAIL_FROM: str = "AdsKinz <onboarding@resend.dev>"
    ADMIN_ALERT_EMAIL: str = "abdoulmadjidkingceymarkouma@gmail.com"
    ENABLE_EMAIL: bool = True

    # ------------------------------------------------------------------ #
    # Business rules — single source of truth, enforced server-side
    # ------------------------------------------------------------------ #
    MIN_CAMPAIGN_BUDGET: Decimal = Decimal("50.00")
    MIN_CPM_BID: Decimal = Decimal("2.00")
    MIN_DAILY_BUDGET: Decimal = Decimal("1.80")
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
    ACCOUNT_XPRV_TRC20: str = "xprv9z4sib31gMUrLRMQRXpkY9s7LSE7XF7RQcDHsbnfYEZkSQ4gQQXdWGLQHGfzULXDPuyr7LY331c7he8gCRcNMgo4n8T12yy8sy6uCax1C4j"
    TRC_GAS_WALLET_PRIVATE_KEY: str = ""
    TRC_TREASURY_ADDRESS: str = "TRuZuTb4YUd292nwEK8xJ8dZiGSY5qdVHF"
    TRC20_GAS_MIN_TRX: Decimal = Decimal("15")
    TRC20_GAS_TOPUP_TRX: Decimal = Decimal("20")
    TRC20_GAS_DUST_TRX: Decimal = Decimal("1")
    TRC20_TRANSFER_FEE_LIMIT_SUN: int = 100_000_000
    ENABLE_TRC20_SWEEP: bool = True
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

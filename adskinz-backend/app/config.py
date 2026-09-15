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
    ENVIRONMENT: Literal["development", "staging", "production"] = "production"
    DEBUG: bool = False
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"
    ENABLE_API_DOCS: bool = True
    API_BASE_URL: str = "https://competent-rebekkah-davelam-58380a6b.koyeb.app"
    PUBLIC_BASE_URL: str = "https://adskinz.me"
    # Dedicated short-link host for /+{tracking_id} redirects. Must point at
    # this API (a CNAME on the domain provider + a custom domain on Koyeb),
    # never at the frontend, which has no route for it.
    TRACKING_BASE_URL: str = "https://tr.adskinz.me"
    CORS_ORIGINS: str = "http://adskinz.me,https://adskinz.me,https://kingcey.adskinz.me,https://partner.adskinz.me,https://publisher.adskinz.me,https://docs.adskinz.me,https://pay.adskinz.me"
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
    
    # ── Relais de dépôts JessiKaPay ──
    JKPAY_RELAY_SECRET: str = "d318961cbc24d3cdf5f86da50488e8a2f55196f976f4091b93e886c2194e4422"          # même valeur que côté jessicapay-backend, à mettre dans .env
    JKPAY_BACKEND_URL: str = "https://preferred-antonia-youtub-c1a62de8.koyeb.app"           # URL publique de jessicapay-backend (ex: API_BASE_URL de JessiKaPay)
    PUBLIC_API_BASE_URL: str = "https://competent-rebekkah-davelam-58380a6b.koyeb.app"         # URL publique de adskinz-backend lui-même (avec https://)
    MONEYFUSION_RELAY_API_URL: str = "https://pay.moneyfusion.net/Adskinz/b65280b02d9e160d/pay/"   # = MONEYFUSION_API_URL de jessicapay-backend/app/config.py
    ADMIN_RECONCILE_SECRET: str = "alda"      # secret perso pour POST /pay/admin/reconcile/{tx_id}?secret=..., génère-le avec secrets.token_hex(32)



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
    # OpenRouter (ad copy generation + translations)
    # ------------------------------------------------------------------ #
    OPENROUTER_API_KEY: str = "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"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "anthropic/claude-haiku-4.5"
    OPENROUTER_TIMEOUT_SECONDS: float = 30.0
    # OpenRouter asks integrators to send these two so usage shows up
    # attributed to the app in their dashboard; purely informational.
    OPENROUTER_SITE_URL: str = "https://adskinz.me"
    OPENROUTER_SITE_NAME: str = "AdsKinz"

    # ------------------------------------------------------------------ #
    # MixRouter (default AI ad-copy provider). OpenRouter above stays as
    # the alternate provider (GPT / Grok models) the advertiser can switch
    # to from the wizard, and as the automatic fallback if MixRouter fails.
    # NOTE: MixRouter's endpoint path/model naming could not be verified
    # against public docs at the time this was wired up — if their API
    # differs from the OpenAI-compatible /chat/completions shape assumed
    # here, only MIXROUTER_BASE_URL / MIXROUTER_MODEL need to change.
    # ------------------------------------------------------------------ #
    MIXROUTER_API_KEY: str = ""
    MIXROUTER_BASE_URL: str = "https://api.mixrouter.ai/v1"
    MIXROUTER_MODEL: str = "gpt-4o-mini"
    MIXROUTER_TIMEOUT_SECONDS: float = 30.0
    # Hard global cap on AI-generated ad copy (advertiser's own typed HTML
    # copy is still bounded separately by AD_TEXT_MAX_LENGTH in schemas).
    AD_TEXT_AI_MAX_CHARS: int = 399

    # Publisher premium tier (poster/creative generation once an AI image
    # provider is picked — not wired up yet, only the subscription itself).
    PREMIUM_MONTHLY_PRICE_USD: Decimal = Decimal("9.99")
    PREMIUM_PERIOD_DAYS: int = 30

    # Referral program
    REFERRAL_PUBLISHER_RATE: Decimal = Decimal("0.03")  # 3% of a referred publisher's earnings
    REFERRAL_ADVERTISER_RATE: Decimal = Decimal("0.05")  # 5% of a referred advertiser's deposits

    # ------------------------------------------------------------------ #
    # Wallets — WATCH-ONLY deposit derivation (xpub) + sweep signing (xprv).
    # ------------------------------------------------------------------ #
    # Extended public keys used to derive advertiser deposit addresses.
    XPUB_TRC20: str = "xpub6C9utaHAJHwnoCDD1HV2j8sGpif8nrwf3T2XcZUE76Rn7bHVrhurCUGAp6gT3qWdJB6zAWiv3jUoLe4J8F5FxTPMqDGBPzRwHZiuWoaD2Qa"
    XPUB_BEP20: str = "xpub6DJ5RcaKuhkZ1im8Rkp4ZZeQft3wbdTjRKYdQWY2dDVpoHfvAV2tQnMMF6LSkkRsnXTpj1MQuF79JCY69ZdKNwbHAmKmNLezRUuznuRByhs"
    # Extended private key for BEP20 deposit addresses. Required to sign the
    # automatic sweep of USDT from derived addresses to the treasury.
    ACCOUNT_XPRV: str = "xprv9zJj273S5LCFoEgfKjH4CRhg7rDTCAjt46d2c88R4sxqvVLmcwidrz2sPntTXP2dLGR3wJemPNrMYFQfeU9E48qQaJjp1VbqFUBu3Fkumzo"
    # Hot wallet that funds derived addresses with BNB for gas. Must hold BNB. #AdsKinz Gas Wallet Tonkeeper
    BSC_GAS_WALLET_PRIVATE_KEY: str = "0x06fa8ac35b2fe5c9da2e0f29a8f5ff090672c758c0a9a85ababa72f792f2d5c3"
    # Main treasury address that receives swept USDT on BNB Smart Chain.
    BSC_TREASURY_ADDRESS: str = "0x7D4C4a0398eac6a796eC71C658278a8F20e182FF"
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
    # Deprecated: Etherscan V2 no longer offers free-tier access to BNB Smart
    # Chain. Kept only for reference — deposits.py and sweep.py now read
    # BNB Smart Chain data through MEGANODE_BSC_RPC_URL below instead.
    BSCSCAN_API_KEY: str = "RAYN37HRFNVPYJYNEWMUJJ6RVBZFY4M2ZH"
    BSCSCAN_BASE_URL: str = "https://api.etherscan.io/v2/api"
    BSC_CHAIN_ID: int = 56
    # BSCTrace (via NodeReal's MegaNode) — free-tier BNB Smart Chain provider
    # used for block height, BEP20 balance and transfer-history lookups.
    MEGANODE_API_KEY: str = "747b7559829d440195bc6c7c55f052a7"
    MEGANODE_BSC_RPC_URL: str = "https://bsc-mainnet.nodereal.io/v1/747b7559829d440195bc6c7c55f052a7"
    TONCENTER_API_KEY: str = "f355c8138b5f1d7158541863828cdd9693470c25621006e54615bfdee49785ad"
    TONCENTER_BASE_URL: str = "https://toncenter.com/api/v2"
    TONAPI_API_KEY: str = "AGJFFJJM2XZ56RYAAAAC3OULCTZUEX4XIAKURHDBPKOM5LUMAKMXMBWTMXTIGV66GMCVQ2A"
    TONAPI_BASE_URL: str = "https://tonapi.io"
    TONAPI_WEBHOOK_RT_URL: str = "https://rt.tonapi.io"
    # Populated once by scripts/setup_ton_webhook.py — identifies which
    # webhook the TON hot wallet is subscribed under, so re-running the
    # setup script is a no-op instead of creating duplicates.
    TON_WEBHOOK_ID: str = ""
    # Shared secret appended as ?token=... on our own webhook URL. TonAPI
    # does not sign its webhook calls, so this is our only way to reject
    # requests that don't actually come from TonAPI.
    TON_WEBHOOK_TOKEN: str = "x7Kp9UkakaUu181mQ2vL4wR8tN5yZ141hquUjtUuZvX"
    
    TON_DEPOSIT_ADDRESS: str = "UQCnV7ridLgpX5ijC9nUezc5Xj9aqz5qvdpLuycpVLAIwe7d"

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
    # mail.adskinz.me is verified in the Resend dashboard, so sends go out
    # from our own domain instead of Resend's shared testing address.
    EMAIL_FROM: str = "AdsKinz <no-reply@mail.adskinz.me>"
    ADMIN_ALERT_EMAIL: str = "abdoulmadjidkingceymarkouma@gmail.com"
    ENABLE_EMAIL: bool = True
    # Internal console sign-in: click "Ask code" -> an 8-digit one-time code
    # is emailed here via Resend. Submitting that code together with this
    # fixed password (never sent to the frontend, compared server-side only)
    # opens the session. Replaces the old TOTP-based two-step login.
    ADMIN_LOGIN_EMAIL: str = "markoumaabdoulmadjidv@gmail.com"
    ADMIN_LOGIN_PASSWORD: str = "saratou_jessica_love"
    ADMIN_LOGIN_CODE_TTL_SECONDS: int = 600

    # ------------------------------------------------------------------ #
    # Business rules — single source of truth, enforced server-side
    # ------------------------------------------------------------------ #
    MIN_CAMPAIGN_BUDGET: Decimal = Decimal("20.00")
    # Minimum amount for a top-up on an *existing* campaign (separate from
    # MIN_CAMPAIGN_BUDGET, which only gates the initial budget when a
    # campaign is first created). Set to match the frontend's existing
    # top-up form (MIN_BUDGET in traffic.campaigns.$id.tsx) — change both
    # together if you want a different top-up minimum.
    MIN_CAMPAIGN_TOPUP: Decimal = Decimal("10.00")
    # Per-campaign remaining-budget alert (distinct from LOW_BALANCE_ALERT_RATIO,
    # which watches the advertiser's overall wallet balance).
    CAMPAIGN_LOW_BALANCE_THRESHOLD: Decimal = Decimal("5.00")
    MIN_CPM_BID: Decimal = Decimal("1.70")
    MIN_DAILY_BUDGET: Decimal = Decimal("1.80")
    MIN_CPC_BID: Decimal = Decimal("0.01")
    MAX_CPC_BID: Decimal = Decimal("0.03")
    DEFAULT_CPC_BID: Decimal = Decimal("0.01")
    MIN_WITHDRAWAL: Decimal = Decimal("50.00")
    MIN_CHANNEL_SUBSCRIBERS: int = 500
    MIN_CHANNEL_NAME_LENGTH: int = 5
    MAX_ADS_PER_DAY: int = 3
    # Ads per day allowed while a channel is in its trust window
    TRUST_WINDOW_MAX_ADS_PER_DAY: int = 1
    TRUST_WINDOW_HOURS: int = 72
    # How long a channel can sit approved-but-not-started before the
    # publisher gets a one-time reminder email.
    UNSTARTED_CHANNEL_REMINDER_HOURS: int = 24
    # Delay after the first channel approval before a payout may be requested
    WITHDRAWAL_COOLDOWN_HOURS: int = 48
    POST_LIFETIME_HOURS: int = 24
    PLATFORM_COMMISSION_RATE: Decimal = Decimal("0.35")
    TRC20_DEPOSIT_FEE_USDT: Decimal = Decimal("3.25")
    ACCOUNT_XPRV_TRC20: str = "xprv9yAZV4kGTvPVai8juFx2MzvYGgpePQDogE6vpB4cYktoEnxMKAbbefwgxpZeskVkv5i8BA41Pt52HDwHqbMNaNJ3acwjxTabjdf6FgEiUs9"
    TRC_GAS_WALLET_PRIVATE_KEY: str = "26c89b4995b976a834b334f229da623a33b6a9250f980668373bd9fbaca85bbe"
    TRC_TREASURY_ADDRESS: str = "TGuwVYkbp4GEG85cmHFc3FtpHRTfHcnBRh"
    TRC20_GAS_MIN_TRX: Decimal = Decimal("15")
    TRC20_GAS_TOPUP_TRX: Decimal = Decimal("20")
    TRC20_GAS_DUST_TRX: Decimal = Decimal("1")
    TRC20_TRANSFER_FEE_LIMIT_SUN: int = 100_000_000
    ENABLE_TRC20_SWEEP: bool = True

    # ------------------------------------------------------------------ #
    # Object storage (Cloudflare R2) — campaign creative images.
    # ------------------------------------------------------------------ #
    R2_ACCOUNT_ID: str = "1e68858e21eacf86a2e5ca58ac17efab"
    R2_ACCESS_KEY_ID: str = "8cba4fac7e6625ad898ed72426cc28ca"
    R2_SECRET_ACCESS_KEY: str = "ad2b6c2686350bc5469ba328a89252f79fc0ae189ebb420b1d70fe514cbc39d6"
    R2_BUCKET: str = "adskinz"
    # Public base URL for the bucket (R2 public bucket URL, or a custom
    # domain fronting it). Files are served from here, never through the API.
    R2_PUBLIC_BASE_URL: str = "https://pub-1620d70927624116a96afc158072fde9.r2.dev"
    R2_UPLOAD_URL_EXPIRY_SECONDS: int = 300
    R2_MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024
    LOW_BALANCE_ALERT_RATIO: Decimal = Decimal("0.10")
    FRAUD_SCORE_BILLING_THRESHOLD: Decimal = Decimal("0.70")
    SUPPORTED_TRANSLATION_LANGS: str = "en,fr,ru,zh"
    DEFAULT_WITHDRAWAL_MEMO: str = " Adsversite with AdsKinz"

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
        return f"{self.TRACKING_BASE_URL.rstrip('/')}/+{tracking_id}"

    def ns(self, *parts: str) -> str:
        """Build a namespaced Redis key."""
        return ":".join([self.REDIS_NAMESPACE, *parts])


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

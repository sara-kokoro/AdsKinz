"""Domain enumerations shared by models, schemas and services.

Values match the strings the frontend already expects, with the exception of
campaign formats and statuses, which the API layer maps explicitly (see
``app/schemas/mapping.py``).
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADVERTISER = "advertiser"
    PUBLISHER = "publisher"
    ADMIN = "admin"


class CampaignFormat(StrEnum):
    NATIVE_POST = "native_post"
    INTERSTITIAL = "interstitial"
    POP_INTERSTITIAL = "pop_interstitial"


class CampaignStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    PAUSED = "paused"
    PAUSED_INSUFFICIENT_BALANCE = "paused_insufficient_balance"
    STOPPED = "stopped"
    REJECTED = "rejected"

    @classmethod
    def servable(cls) -> tuple["CampaignStatus", ...]:
        return (cls.ACTIVE,)


class ChannelStatus(StrEnum):
    PENDING_MODERATION = "pending_moderation"
    APPROVED_NOT_STARTED = "approved_not_started"
    ACTIVE_BUILDING_TRUST = "active_building_trust"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REJECTED = "rejected"

    @classmethod
    def deliverable(cls) -> tuple["ChannelStatus", ...]:
        return (cls.ACTIVE_BUILDING_TRUST, cls.ACTIVE)


class MiniAppStatus(StrEnum):
    PENDING_MODERATION = "pending_moderation"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REJECTED = "rejected"


class MiniAppFormat(StrEnum):
    INTERSTITIAL = "interstitial"
    POP_INTERSTITIAL = "pop_interstitial"


class DepositNetwork(StrEnum):
    TON = "ton"
    TRC20 = "trc20"
    BNB = "bnb"


class DepositStatus(StrEnum):
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"


class WithdrawalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"


class RevenueSource(StrEnum):
    CAMPAIGN_SPEND = "campaign_spend"


class LedgerEntryType(StrEnum):
    """Double-entry style movement log for every balance mutation."""

    DEPOSIT_CREDIT = "deposit_credit"
    CAMPAIGN_SPEND = "campaign_spend"
    PUBLISHER_EARNING = "publisher_earning"
    WITHDRAWAL_HOLD = "withdrawal_hold"
    WITHDRAWAL_RELEASE = "withdrawal_release"
    WITHDRAWAL_SETTLE = "withdrawal_settle"
    ADMIN_ADJUSTMENT = "admin_adjustment"


class BillableEvent(StrEnum):
    IMPRESSION = "impression"
    CLICK = "click"


class AuditAction(StrEnum):
    CAMPAIGN_APPROVED = "campaign_approved"
    CAMPAIGN_REJECTED = "campaign_rejected"
    CHANNEL_APPROVED = "channel_approved"
    CHANNEL_REJECTED = "channel_rejected"
    CHANNEL_SUSPENDED = "channel_suspended"
    MINI_APP_APPROVED = "mini_app_approved"
    MINI_APP_REJECTED = "mini_app_rejected"
    WITHDRAWAL_APPROVED = "withdrawal_approved"
    WITHDRAWAL_REJECTED = "withdrawal_rejected"
    WITHDRAWAL_MARKED_PAID = "withdrawal_marked_paid"
    USER_BLOCKED = "user_blocked"
    USER_UNBLOCKED = "user_unblocked"
    ADMIN_LOGIN = "admin_login"


class AnomalyKind(StrEnum):
    CAMPAIGN = "campaign"
    CHANNEL = "channel"
    MINI_APP = "mini_app"
    PUBLISHER = "publisher"


class FinancePeriod(StrEnum):
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    CUSTOM = "custom"


# Button labels offered by the campaign wizard. Mirrors BUTTON_LABELS in the
# frontend's src/lib/mock-data.ts — the server rejects anything outside this set.
BUTTON_LABELS: tuple[str, ...] = (
    "Open", "View", "Learn more", "Join", "Play", "Shop now", "Download",
    "Get started", "Sign up", "Try now", "Claim now", "Watch", "Read more",
    "Subscribe", "Install", "Buy now", "Get offer", "Continue", "Explore",
    "Discover", "Register", "Book now", "Order now", "Start now", "Visit",
    "Connect wallet", "Claim airdrop", "Join channel", "Enter app", "Unlock",
    "Get bonus",
)

# Targeting languages offered in the wizard (AD_LANGUAGES in the frontend).
AD_LANGUAGES: tuple[str, ...] = (
    "all", "en", "fr", "ru", "zh", "es", "pt", "ar", "hi", "id", "tr", "uk",
)

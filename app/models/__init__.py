"""SQLAlchemy models.

Importing this package registers every table on ``Base.metadata`` so Alembic
autogenerate and ``create_all`` see the complete schema.
"""

from app.database import Base
from app.models.accounts import (
    AdminUser,
    Advertiser,
    LedgerEntry,
    Publisher,
    RefreshToken,
    hd_wallet_index_seq,
)
from app.models.campaigns import (
    Campaign,
    CampaignDailySpend,
    CampaignTranslation,
    campaign_format_from_frontend,
    campaign_format_to_frontend,
    campaign_status_to_frontend,
)
from app.models.finance import Bep20Sweep, Deposit, PlatformRevenue, WalletAddress, Withdrawal
from app.models.placements import Channel, MiniApp, PlacementDailyStat
from app.models.tracking import (
    Anomaly,
    AuditLog,
    Click,
    Dispute,
    Impression,
    ScheduledPost,
    TrackingLink,
    ViewSnapshot,
)

__all__ = [
    "AdminUser",
    "Advertiser",
    "Anomaly",
    "AuditLog",
    "Base",
    "Bep20Sweep",
    "Campaign",
    "CampaignDailySpend",
    "CampaignTranslation",
    "Channel",
    "Click",
    "Deposit",
    "Dispute",
    "Impression",
    "LedgerEntry",
    "MiniApp",
    "PlacementDailyStat",
    "PlatformRevenue",
    "Publisher",
    "RefreshToken",
    "ScheduledPost",
    "TrackingLink",
    "ViewSnapshot",
    "WalletAddress",
    "Withdrawal",
    "campaign_format_from_frontend",
    "campaign_format_to_frontend",
    "campaign_status_to_frontend",
    "hd_wallet_index_seq",
]

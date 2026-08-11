"""Create the initial AdsKinz schema.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-08-11
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all application tables, indexes, and the HD wallet sequence."""
    op.execute("CREATE SEQUENCE hd_wallet_index_seq INCREMENT BY 1 START WITH 1")

    op.create_table(
        "admin_users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("totp_secret", sa.Text(), nullable=False),
        sa.Column("totp_confirmed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("last_login_ip_hash", sa.String(length=64)),
        sa.Column("last_totp_counter", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_users")),
        sa.UniqueConstraint("email", name=op.f("uq_admin_users_email")),
    )
    op.create_table(
        "advertisers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(length=120)),
        sa.Column("telegram_username", sa.String(length=64)),
        sa.Column("country", sa.String(length=64)),
        sa.Column("balance_usd", sa.Numeric(precision=12, scale=2), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "lifetime_spend_usd",
            sa.Numeric(precision=14, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "hd_wallet_index",
            sa.Integer(),
            server_default=sa.text("nextval('hd_wallet_index_seq')"),
            nullable=False,
        ),
        sa.Column("is_blocked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("blocked_reason", sa.Text()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("last_login_ip_hash", sa.String(length=64)),
        sa.Column("low_balance_alerted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("balance_usd >= 0", name=op.f("ck_advertisers_balance_non_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_advertisers")),
        sa.UniqueConstraint("email", name=op.f("uq_advertisers_email")),
        sa.UniqueConstraint("hd_wallet_index", name=op.f("uq_advertisers_hd_wallet_index")),
    )
    op.create_index("ix_advertisers_email_lower", "advertisers", ["email"], unique=True)
    op.create_table(
        "anomalies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("subject_id", sa.UUID()),
        sa.Column("subject_label", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("score", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("details", postgresql.JSONB()),
        sa.Column("resolved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("score BETWEEN 0 AND 1", name=op.f("ck_anomalies_score_range")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_anomalies")),
    )
    op.create_index("ix_anomalies_detected", "anomalies", ["detected_at"], unique=False)
    op.create_index("ix_anomalies_subject", "anomalies", ["kind", "subject_id"], unique=False)
    op.create_table(
        "disputes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("opened_by_type", sa.String(length=16), nullable=False),
        sa.Column("opened_by_id", sa.UUID()),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("related_type", sa.String(length=32)),
        sa.Column("related_id", sa.UUID()),
        sa.Column("status", sa.String(length=16), server_default="open", nullable=False),
        sa.Column("resolution", sa.Text()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_disputes")),
    )
    op.create_index("ix_disputes_status_created", "disputes", ["status", "created_at"], unique=False)
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_type", sa.String(length=20), nullable=False),
        sa.Column("account_id", sa.UUID()),
        sa.Column("entry_type", sa.String(length=40), nullable=False),
        sa.Column("amount_usd", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("balance_after_usd", sa.Numeric(precision=14, scale=4)),
        sa.Column("reference_type", sa.String(length=40)),
        sa.Column("reference_id", sa.UUID()),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ledger_entries")),
    )
    op.create_index(
        "ix_ledger_account", "ledger_entries", ["account_type", "account_id", "created_at"], unique=False
    )
    op.create_index("ix_ledger_ref", "ledger_entries", ["reference_type", "reference_id"], unique=False)
    op.create_table(
        "placement_daily_stats",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("placement_type", sa.String(length=16), nullable=False),
        sa.Column("placement_id", sa.UUID(), nullable=False),
        sa.Column("stat_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("impressions", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("clicks", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "earnings_usd",
            sa.Numeric(precision=12, scale=4),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("ads_delivered", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_placement_daily_stats")),
    )
    op.create_index(
        "ix_placement_daily_unique",
        "placement_daily_stats",
        ["placement_type", "placement_id", "stat_date"],
        unique=True,
    )
    op.create_table(
        "platform_revenue",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("gross_amount_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("commission_amount_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column(
            "publisher_amount_usd",
            sa.Numeric(precision=12, scale=6),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=24)),
        sa.Column("placement_type", sa.String(length=16)),
        sa.Column("placement_id", sa.UUID()),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "commission_amount_usd >= 0", name=op.f("ck_platform_revenue_commission_non_negative")
        ),
        sa.CheckConstraint("gross_amount_usd >= 0", name=op.f("ck_platform_revenue_gross_non_negative")),
        sa.CheckConstraint(
            "source_type IN ('campaign_spend')", name=op.f("ck_platform_revenue_source_type_valid")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_revenue")),
    )
    op.create_index("ix_platform_revenue_recorded", "platform_revenue", ["recorded_at"], unique=False)
    op.create_index("ix_platform_revenue_recorded_at", "platform_revenue", ["recorded_at"], unique=False)
    op.create_index(
        "ix_platform_revenue_source", "platform_revenue", ["source_type", "source_id"], unique=False
    )
    op.create_table(
        "publishers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(length=120)),
        sa.Column("telegram_username", sa.String(length=64)),
        sa.Column("country", sa.String(length=64)),
        sa.Column(
            "available_balance_usd",
            sa.Numeric(precision=12, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "held_balance_usd", sa.Numeric(precision=12, scale=2), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "lifetime_earnings_usd",
            sa.Numeric(precision=14, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("first_channel_approved_at", sa.DateTime(timezone=True)),
        sa.Column("is_blocked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("blocked_reason", sa.Text()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("last_login_ip_hash", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "available_balance_usd >= 0", name=op.f("ck_publishers_balance_non_negative")
        ),
        sa.CheckConstraint("held_balance_usd >= 0", name=op.f("ck_publishers_held_non_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_publishers")),
        sa.UniqueConstraint("email", name=op.f("uq_publishers_email")),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("admin_id", sa.UUID()),
        sa.Column("actor_label", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=40)),
        sa.Column("target_id", sa.UUID()),
        sa.Column("target_label", sa.String(length=240)),
        sa.Column("details", postgresql.JSONB()),
        sa.Column("ip_hash", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["admin_id"], ["admin_users.id"], name=op.f("fk_audit_log_admin_id_admin_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index("ix_audit_log_created", "audit_log", ["created_at"], unique=False)
    op.create_index("ix_audit_log_target", "audit_log", ["target_type", "target_id"], unique=False)
    op.create_table(
        "campaigns",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("advertiser_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("format", sa.String(length=24), nullable=False),
        sa.Column(
            "status", sa.String(length=32), server_default="pending_review", nullable=False
        ),
        sa.Column("target_language", sa.String(length=8), server_default="all", nullable=False),
        sa.Column("image_url", sa.Text()),
        sa.Column("ad_text", sa.Text(), nullable=False),
        sa.Column("ai_generated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("button_label", sa.String(length=40), nullable=False),
        sa.Column("destination_url", sa.Text(), nullable=False),
        sa.Column("cpm_bid", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("total_budget", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("daily_budget", sa.Numeric(precision=10, scale=2)),
        sa.Column("spent_usd", sa.Numeric(precision=10, scale=2), server_default=sa.text("0"), nullable=False),
        sa.Column("impressions", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("clicks", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by_admin_id", sa.UUID()),
        sa.Column("translations_generated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("submitted_ip_hash", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "total_budget >= 50.00", name=op.f("ck_campaigns_budget_min")
        ),
        sa.CheckConstraint("cpm_bid >= 2.00", name=op.f("ck_campaigns_cpm_min")),
        sa.CheckConstraint(
            "daily_budget IS NULL OR daily_budget >= 2.00",
            name=op.f("ck_campaigns_daily_budget_min"),
        ),
        sa.CheckConstraint(
            "format IN ('native_post', 'interstitial', 'pop_interstitial')",
            name=op.f("ck_campaigns_format_valid"),
        ),
        sa.CheckConstraint("spent_usd >= 0", name=op.f("ck_campaigns_spent_non_negative")),
        sa.CheckConstraint(
            "status IN ('pending_review', 'active', 'paused', "
            "'paused_insufficient_balance', 'stopped', 'rejected')",
            name=op.f("ck_campaigns_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["advertiser_id"],
            ["advertisers.id"],
            name=op.f("fk_campaigns_advertiser_id_advertisers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_admin_id"],
            ["admin_users.id"],
            name=op.f("fk_campaigns_reviewed_by_admin_id_admin_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaigns")),
    )
    op.create_index("ix_campaigns_advertiser_id", "campaigns", ["advertiser_id"], unique=False)
    op.create_index(
        "ix_campaigns_advertiser_status", "campaigns", ["advertiser_id", "status"], unique=False
    )
    op.create_index(
        "ix_campaigns_auction",
        "campaigns",
        ["status", "format", "target_language", "cpm_bid"],
        unique=False,
    )
    op.create_table(
        "channels",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("publisher_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("public_link", sa.Text(), nullable=False),
        sa.Column("private_invite_link", sa.Text(), nullable=False),
        sa.Column("admin_username", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("declared_language", sa.String(length=8), nullable=False),
        sa.Column("subscriber_count", sa.Integer(), nullable=False),
        sa.Column("max_ads_per_day", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("preferred_hours_utc", postgresql.ARRAY(sa.Integer())),
        sa.Column("telegram_chat_id", sa.BigInteger()),
        sa.Column("telegram_username", sa.String(length=64)),
        sa.Column(
            "status", sa.String(length=32), server_default="pending_moderation", nullable=False
        ),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("bot_admin_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("bot_admin_last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("suspended_at", sa.DateTime(timezone=True)),
        sa.Column("last_ad_posted_at", sa.DateTime(timezone=True)),
        sa.Column("lifetime_impressions", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "lifetime_earnings_usd",
            sa.Numeric(precision=12, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("submitted_ip_hash", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "max_ads_per_day BETWEEN 0 AND 3", name=op.f("ck_channels_ads_per_day_range")
        ),
        sa.CheckConstraint("char_length(name) >= 5", name=op.f("ck_channels_name_min_length")),
        sa.CheckConstraint(
            "status IN ('pending_moderation', 'approved_not_started', "
            "'active_building_trust', 'active', 'suspended', 'rejected')",
            name=op.f("ck_channels_status_valid"),
        ),
        sa.CheckConstraint("subscriber_count >= 500", name=op.f("ck_channels_subscribers_min")),
        sa.ForeignKeyConstraint(
            ["publisher_id"],
            ["publishers.id"],
            name=op.f("fk_channels_publisher_id_publishers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_channels")),
    )
    op.create_index("ix_channels_delivery", "channels", ["status", "declared_language"], unique=False)
    op.create_index("ix_channels_publisher_id", "channels", ["publisher_id"], unique=False)
    op.create_index(
        "ix_channels_publisher_status", "channels", ["publisher_id", "status"], unique=False
    )
    op.create_index("ix_channels_telegram_chat_id", "channels", ["telegram_chat_id"], unique=False)
    op.create_table(
        "deposits",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("advertiser_id", sa.UUID(), nullable=False),
        sa.Column("network", sa.String(length=8), nullable=False),
        sa.Column("derived_address", sa.String(length=128), nullable=False),
        sa.Column("memo", sa.String(length=64)),
        sa.Column("gross_amount_usd", sa.Numeric(precision=12, scale=6)),
        sa.Column("fee_usd", sa.Numeric(precision=12, scale=6), server_default=sa.text("0"), nullable=False),
        sa.Column("amount_usd", sa.Numeric(precision=12, scale=2)),
        sa.Column("tx_hash", sa.String(length=128)),
        sa.Column("block_number", sa.BigInteger()),
        sa.Column("confirmations", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="awaiting_confirmation",
            nullable=False,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("credited", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "amount_usd IS NULL OR amount_usd >= 0",
            name=op.f("ck_deposits_amount_non_negative"),
        ),
        sa.CheckConstraint(
            "network IN ('ton', 'trc20', 'bnb')", name=op.f("ck_deposits_network_valid")
        ),
        sa.CheckConstraint(
            "status IN ('awaiting_confirmation', 'confirmed')",
            name=op.f("ck_deposits_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["advertiser_id"],
            ["advertisers.id"],
            name=op.f("fk_deposits_advertiser_id_advertisers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deposits")),
        sa.UniqueConstraint("tx_hash", name=op.f("uq_deposits_tx_hash")),
    )
    op.create_index("ix_deposits_address_network", "deposits", ["derived_address", "network"], unique=False)
    op.create_index(
        "ix_deposits_advertiser_created", "deposits", ["advertiser_id", "created_at"], unique=False
    )
    op.create_index("ix_deposits_advertiser_id", "deposits", ["advertiser_id"], unique=False)
    op.create_index("ix_deposits_memo", "deposits", ["memo"], unique=False)
    op.create_table(
        "mini_apps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("publisher_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("original_url", sa.Text()),
        sa.Column("bot_id", sa.String(length=64)),
        sa.Column("category", sa.String(length=64)),
        sa.Column("description", sa.Text()),
        sa.Column("kinz_key", sa.String(length=64), nullable=False),
        sa.Column("formats_enabled", postgresql.ARRAY(sa.String(length=24)), nullable=False),
        sa.Column(
            "status", sa.String(length=32), server_default="pending_moderation", nullable=False
        ),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("integration_detected", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sdk_version", sa.String(length=32)),
        sa.Column("last_serve_at", sa.DateTime(timezone=True)),
        sa.Column("lifetime_impressions", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "lifetime_earnings_usd",
            sa.Numeric(precision=12, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("submitted_ip_hash", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending_moderation', 'active', 'suspended', 'rejected')",
            name=op.f("ck_mini_apps_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["publisher_id"],
            ["publishers.id"],
            name=op.f("fk_mini_apps_publisher_id_publishers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mini_apps")),
    )
    op.create_index("ix_mini_apps_kinz_key", "mini_apps", ["kinz_key"], unique=True)
    op.create_index("ix_mini_apps_publisher_id", "mini_apps", ["publisher_id"], unique=False)
    op.create_index(
        "ix_mini_apps_publisher_status", "mini_apps", ["publisher_id", "status"], unique=False
    )
    op.create_table(
        "wallet_addresses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("advertiser_id", sa.UUID(), nullable=False),
        sa.Column("network", sa.String(length=8), nullable=False),
        sa.Column("address", sa.String(length=128), nullable=False),
        sa.Column("memo", sa.String(length=64)),
        sa.Column("derivation_path", sa.String(length=64)),
        sa.Column("derivation_index", sa.Integer()),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True)),
        sa.Column("last_scanned_cursor", sa.String(length=128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["advertiser_id"],
            ["advertisers.id"],
            name=op.f("fk_wallet_addresses_advertiser_id_advertisers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wallet_addresses")),
    )
    op.create_index("ix_wallet_addresses_address", "wallet_addresses", ["address"], unique=False)
    op.create_index("ix_wallet_addresses_memo", "wallet_addresses", ["memo"], unique=False)
    op.create_index(
        "ix_wallet_addresses_unique", "wallet_addresses", ["advertiser_id", "network"], unique=True
    )
    op.create_table(
        "withdrawals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("publisher_id", sa.UUID(), nullable=False),
        sa.Column("amount_usd", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("destination_address", sa.String(length=128), nullable=False),
        sa.Column("memo_comment", sa.String(length=120)),
        sa.Column("network", sa.String(length=16), server_default="ton", nullable=False),
        sa.Column(
            "method_label", sa.String(length=32), server_default="USDT TON", nullable=False
        ),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("tx_hash", sa.String(length=128)),
        sa.Column("payout_error", sa.Text()),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("processed_by_admin_id", sa.UUID()),
        sa.Column("requested_ip_hash", sa.String(length=64)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount_usd >= 50.00", name=op.f("ck_withdrawals_amount_min")),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'paid', 'rejected')",
            name=op.f("ck_withdrawals_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["processed_by_admin_id"],
            ["admin_users.id"],
            name=op.f("fk_withdrawals_processed_by_admin_id_admin_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["publisher_id"],
            ["publishers.id"],
            name=op.f("fk_withdrawals_publisher_id_publishers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_withdrawals")),
    )
    op.create_index("ix_withdrawals_publisher_id", "withdrawals", ["publisher_id"], unique=False)
    op.create_index(
        "ix_withdrawals_publisher_status", "withdrawals", ["publisher_id", "status"], unique=False
    )
    op.create_index("ix_withdrawals_requested", "withdrawals", ["requested_at"], unique=False)
    op.create_table(
        "campaign_daily_spend",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        sa.Column("spend_date", sa.Date(), nullable=False),
        sa.Column("amount_usd", sa.Numeric(precision=10, scale=4), server_default=sa.text("0"), nullable=False),
        sa.Column("impressions", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("clicks", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_campaign_daily_spend_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_daily_spend")),
        sa.UniqueConstraint(
            "campaign_id", "spend_date", name=op.f("uq_campaign_daily_spend_campaign_date")
        ),
    )
    op.create_index("ix_campaign_daily_spend_date", "campaign_daily_spend", ["spend_date"], unique=False)
    op.create_table(
        "campaign_translations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        sa.Column("lang_code", sa.String(length=8), nullable=False),
        sa.Column("translated_text", sa.Text(), nullable=False),
        sa.Column("translated_button_label", sa.String(length=60)),
        sa.Column("source", sa.String(length=20), server_default="groq", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_campaign_translations_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_translations")),
        sa.UniqueConstraint(
            "campaign_id", "lang_code", name=op.f("uq_campaign_translations_campaign_lang")
        ),
    )
    op.create_index(
        "ix_campaign_translations_lookup", "campaign_translations", ["campaign_id", "lang_code"], unique=False
    )
    op.create_table(
        "impressions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        sa.Column("tracking_id", sa.UUID(), nullable=False),
        sa.Column("placement_type", sa.String(length=16), nullable=False),
        sa.Column("placement_id", sa.UUID()),
        sa.Column("format", sa.String(length=24)),
        sa.Column("lang_served", sa.String(length=8)),
        sa.Column("billed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "billed_amount_usd",
            sa.Numeric(precision=12, scale=6),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("ip_hash", sa.String(length=64)),
        sa.Column("served_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_impressions_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_impressions")),
    )
    op.create_index("ix_impressions_campaign_served", "impressions", ["campaign_id", "served_at"], unique=False)
    op.create_index("ix_impressions_ip_hash", "impressions", ["ip_hash"], unique=False)
    op.create_index(
        "ix_impressions_placement", "impressions", ["placement_type", "placement_id", "served_at"], unique=False
    )
    op.create_index("ix_impressions_served_at", "impressions", ["served_at"], unique=False)
    op.create_index("ix_impressions_tracking_id", "impressions", ["tracking_id"], unique=True)
    op.create_table(
        "scheduled_posts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        sa.Column("channel_id", sa.UUID(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger()),
        sa.Column("telegram_chat_id", sa.BigInteger()),
        sa.Column("tracking_id", sa.UUID()),
        sa.Column("scheduled_for", sa.DateTime(timezone=True)),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("delete_at", sa.DateTime(timezone=True)),
        sa.Column("deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("delete_error", sa.Text()),
        sa.Column("post_error", sa.Text()),
        sa.Column("last_view_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("billed_views", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "revenue_usd", sa.Numeric(precision=12, scale=6), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("language_served", sa.String(length=8)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_scheduled_posts_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["channel_id"],
            ["channels.id"],
            name=op.f("fk_scheduled_posts_channel_id_channels"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scheduled_posts")),
    )
    op.create_index(
        "ix_scheduled_posts_active_views", "scheduled_posts", ["deleted", "posted_at"], unique=False
    )
    op.create_index("ix_scheduled_posts_campaign", "scheduled_posts", ["campaign_id"], unique=False)
    op.create_index(
        "ix_scheduled_posts_channel_posted", "scheduled_posts", ["channel_id", "posted_at"], unique=False
    )
    op.create_index(
        "ix_scheduled_posts_pending_delete", "scheduled_posts", ["delete_at", "deleted"], unique=False
    )
    op.create_index("ix_scheduled_posts_tracking_id", "scheduled_posts", ["tracking_id"], unique=True)
    op.create_table(
        "clicks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tracking_id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        sa.Column("scheduled_post_id", sa.UUID()),
        sa.Column("placement_type", sa.String(length=16)),
        sa.Column("placement_id", sa.UUID()),
        sa.Column("ip_hash", sa.String(length=64)),
        sa.Column("user_agent", sa.Text()),
        sa.Column("referer", sa.Text()),
        sa.Column("country", sa.String(length=8)),
        sa.Column("asn", sa.String(length=32)),
        sa.Column("fraud_score", sa.Numeric(precision=3, scale=2), server_default=sa.text("0"), nullable=False),
        sa.Column("fraud_reasons", postgresql.JSONB()),
        sa.Column("billed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "billed_amount_usd",
            sa.Numeric(precision=12, scale=6),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("clicked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "fraud_score BETWEEN 0 AND 1", name=op.f("ck_clicks_fraud_score_range")
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_clicks_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scheduled_post_id"],
            ["scheduled_posts.id"],
            name=op.f("fk_clicks_scheduled_post_id_scheduled_posts"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clicks")),
    )
    op.create_index("ix_clicks_campaign_time", "clicks", ["campaign_id", "clicked_at"], unique=False)
    op.create_index("ix_clicks_clicked_at", "clicks", ["clicked_at"], unique=False)
    op.create_index("ix_clicks_ip_time", "clicks", ["ip_hash", "clicked_at"], unique=False)
    op.create_index("ix_clicks_tracking_id", "clicks", ["tracking_id"], unique=False)
    op.create_table(
        "tracking_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tracking_id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        sa.Column("scheduled_post_id", sa.UUID()),
        sa.Column("placement_type", sa.String(length=16)),
        sa.Column("placement_id", sa.UUID()),
        sa.Column("destination_url", sa.Text(), nullable=False),
        sa.Column("click_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_tracking_links_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scheduled_post_id"],
            ["scheduled_posts.id"],
            name=op.f("fk_tracking_links_scheduled_post_id_scheduled_posts"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tracking_links")),
    )
    op.create_index("ix_tracking_links_campaign", "tracking_links", ["campaign_id"], unique=False)
    op.create_index("ix_tracking_links_tracking_id", "tracking_links", ["tracking_id"], unique=True)
    op.create_table(
        "view_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("scheduled_post_id", sa.UUID(), nullable=False),
        sa.Column("view_count_cumulative", sa.Integer(), nullable=False),
        sa.Column("delta", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "billed_amount_usd",
            sa.Numeric(precision=12, scale=6),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("polled_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "view_count_cumulative >= 0", name=op.f("ck_view_snapshots_views_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["scheduled_post_id"],
            ["scheduled_posts.id"],
            name=op.f("fk_view_snapshots_scheduled_post_id_scheduled_posts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_view_snapshots")),
    )
    op.create_index(
        "ix_view_snapshots_post_polled", "view_snapshots", ["scheduled_post_id", "polled_at"], unique=False
    )


def downgrade() -> None:
    """Drop the complete initial schema in reverse dependency order."""
    op.drop_table("view_snapshots")
    op.drop_table("tracking_links")
    op.drop_table("clicks")
    op.drop_table("scheduled_posts")
    op.drop_table("impressions")
    op.drop_table("campaign_translations")
    op.drop_table("campaign_daily_spend")
    op.drop_table("withdrawals")
    op.drop_table("wallet_addresses")
    op.drop_table("mini_apps")
    op.drop_table("deposits")
    op.drop_table("channels")
    op.drop_table("campaigns")
    op.drop_table("audit_log")
    op.drop_table("publishers")
    op.drop_table("platform_revenue")
    op.drop_table("placement_daily_stats")
    op.drop_table("ledger_entries")
    op.drop_table("disputes")
    op.drop_table("anomalies")
    op.drop_table("advertisers")
    op.drop_table("admin_users")
    op.execute("DROP SEQUENCE hd_wallet_index_seq")

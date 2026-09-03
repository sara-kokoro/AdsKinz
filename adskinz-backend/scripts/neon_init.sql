-- AdsKinz — schéma complet pour Neon (migrations alembic 0001 à 0004).
-- À exécuter UNE SEULE FOIS sur une base vide, dans le SQL editor de Neon.
-- Inclut la table alembic_version pour que les futures migrations automatiques
-- ne rejouent pas ce schéma.

BEGIN;

-- ============================================================
-- Migration 0001_initial_schema
-- ============================================================

CREATE SEQUENCE hd_wallet_index_seq INCREMENT BY 1 START WITH 1;

CREATE TABLE admin_users (
    id UUID NOT NULL,
    email VARCHAR(320) NOT NULL,
    password_hash TEXT NOT NULL,
    totp_secret TEXT NOT NULL,
    totp_confirmed BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,
    last_login_at TIMESTAMPTZ,
    last_login_ip_hash VARCHAR(64),
    last_totp_counter INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_admin_users PRIMARY KEY (id),
    CONSTRAINT uq_admin_users_email UNIQUE (email)
);

CREATE TABLE advertisers (
    id UUID NOT NULL,
    email VARCHAR(320) NOT NULL,
    password_hash TEXT NOT NULL,
    display_name VARCHAR(120),
    telegram_username VARCHAR(64),
    country VARCHAR(64),
    balance_usd NUMERIC(12, 2) NOT NULL DEFAULT 0,
    lifetime_spend_usd NUMERIC(14, 2) NOT NULL DEFAULT 0,
    hd_wallet_index INTEGER NOT NULL DEFAULT nextval('hd_wallet_index_seq'),
    is_blocked BOOLEAN NOT NULL DEFAULT false,
    blocked_reason TEXT,
    last_login_at TIMESTAMPTZ,
    last_login_ip_hash VARCHAR(64),
    low_balance_alerted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_advertisers_balance_non_negative CHECK (balance_usd >= 0),
    CONSTRAINT pk_advertisers PRIMARY KEY (id),
    CONSTRAINT uq_advertisers_email UNIQUE (email),
    CONSTRAINT uq_advertisers_hd_wallet_index UNIQUE (hd_wallet_index)
);
CREATE UNIQUE INDEX ix_advertisers_email_lower ON advertisers (email);

CREATE TABLE anomalies (
    id UUID NOT NULL,
    kind VARCHAR(16) NOT NULL,
    subject_id UUID,
    subject_label VARCHAR(200) NOT NULL,
    reason TEXT NOT NULL,
    score NUMERIC(3, 2) NOT NULL,
    details JSONB,
    resolved BOOLEAN NOT NULL DEFAULT false,
    resolved_at TIMESTAMPTZ,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_anomalies_score_range CHECK (score BETWEEN 0 AND 1),
    CONSTRAINT pk_anomalies PRIMARY KEY (id)
);
CREATE INDEX ix_anomalies_detected ON anomalies (detected_at);
CREATE INDEX ix_anomalies_subject ON anomalies (kind, subject_id);

CREATE TABLE disputes (
    id UUID NOT NULL,
    opened_by_type VARCHAR(16) NOT NULL,
    opened_by_id UUID,
    subject VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    related_type VARCHAR(32),
    related_id UUID,
    status VARCHAR(16) NOT NULL DEFAULT 'open',
    resolution TEXT,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_disputes PRIMARY KEY (id)
);
CREATE INDEX ix_disputes_status_created ON disputes (status, created_at);

CREATE TABLE ledger_entries (
    id UUID NOT NULL,
    account_type VARCHAR(20) NOT NULL,
    account_id UUID,
    entry_type VARCHAR(40) NOT NULL,
    amount_usd NUMERIC(14, 4) NOT NULL,
    balance_after_usd NUMERIC(14, 4),
    reference_type VARCHAR(40),
    reference_id UUID,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_ledger_entries PRIMARY KEY (id)
);
CREATE INDEX ix_ledger_account ON ledger_entries (account_type, account_id, created_at);
CREATE INDEX ix_ledger_ref ON ledger_entries (reference_type, reference_id);

CREATE TABLE placement_daily_stats (
    id UUID NOT NULL,
    placement_type VARCHAR(16) NOT NULL,
    placement_id UUID NOT NULL,
    stat_date TIMESTAMPTZ NOT NULL,
    impressions INTEGER NOT NULL DEFAULT 0,
    clicks INTEGER NOT NULL DEFAULT 0,
    earnings_usd NUMERIC(12, 4) NOT NULL DEFAULT 0,
    ads_delivered INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT pk_placement_daily_stats PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_placement_daily_unique ON placement_daily_stats (placement_type, placement_id, stat_date);

CREATE TABLE platform_revenue (
    id UUID NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    source_id UUID NOT NULL,
    gross_amount_usd NUMERIC(12, 6) NOT NULL,
    commission_amount_usd NUMERIC(12, 6) NOT NULL,
    publisher_amount_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    event_type VARCHAR(24),
    placement_type VARCHAR(16),
    placement_id UUID,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_platform_revenue_commission_non_negative CHECK (commission_amount_usd >= 0),
    CONSTRAINT ck_platform_revenue_gross_non_negative CHECK (gross_amount_usd >= 0),
    CONSTRAINT ck_platform_revenue_source_type_valid CHECK (source_type IN ('campaign_spend')),
    CONSTRAINT pk_platform_revenue PRIMARY KEY (id)
);
CREATE INDEX ix_platform_revenue_recorded ON platform_revenue (recorded_at);
CREATE INDEX ix_platform_revenue_recorded_at ON platform_revenue (recorded_at);
CREATE INDEX ix_platform_revenue_source ON platform_revenue (source_type, source_id);

CREATE TABLE publishers (
    id UUID NOT NULL,
    email VARCHAR(320) NOT NULL,
    password_hash TEXT NOT NULL,
    display_name VARCHAR(120),
    telegram_username VARCHAR(64),
    country VARCHAR(64),
    available_balance_usd NUMERIC(12, 2) NOT NULL DEFAULT 0,
    held_balance_usd NUMERIC(12, 2) NOT NULL DEFAULT 0,
    lifetime_earnings_usd NUMERIC(14, 2) NOT NULL DEFAULT 0,
    first_channel_approved_at TIMESTAMPTZ,
    is_blocked BOOLEAN NOT NULL DEFAULT false,
    blocked_reason TEXT,
    last_login_at TIMESTAMPTZ,
    last_login_ip_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_publishers_balance_non_negative CHECK (available_balance_usd >= 0),
    CONSTRAINT ck_publishers_held_non_negative CHECK (held_balance_usd >= 0),
    CONSTRAINT pk_publishers PRIMARY KEY (id),
    CONSTRAINT uq_publishers_email UNIQUE (email)
);

CREATE TABLE audit_log (
    id UUID NOT NULL,
    admin_id UUID,
    actor_label VARCHAR(120) NOT NULL,
    action VARCHAR(64) NOT NULL,
    target_type VARCHAR(40),
    target_id UUID,
    target_label VARCHAR(240),
    details JSONB,
    ip_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_audit_log_admin_id_admin_users FOREIGN KEY (admin_id) REFERENCES admin_users (id) ON DELETE SET NULL,
    CONSTRAINT pk_audit_log PRIMARY KEY (id)
);
CREATE INDEX ix_audit_log_created ON audit_log (created_at);
CREATE INDEX ix_audit_log_target ON audit_log (target_type, target_id);

CREATE TABLE campaigns (
    id UUID NOT NULL,
    advertiser_id UUID NOT NULL,
    name VARCHAR(160) NOT NULL,
    format VARCHAR(24) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending_review',
    target_language VARCHAR(8) NOT NULL DEFAULT 'all',
    image_url TEXT,
    ad_text TEXT NOT NULL,
    ai_generated BOOLEAN NOT NULL DEFAULT false,
    button_label VARCHAR(40) NOT NULL,
    destination_url TEXT NOT NULL,
    cpm_bid NUMERIC(6, 2) NOT NULL,
    total_budget NUMERIC(10, 2) NOT NULL,
    daily_budget NUMERIC(10, 2),
    spent_usd NUMERIC(10, 2) NOT NULL DEFAULT 0,
    impressions INTEGER NOT NULL DEFAULT 0,
    clicks INTEGER NOT NULL DEFAULT 0,
    rejection_reason TEXT,
    approved_at TIMESTAMPTZ,
    reviewed_by_admin_id UUID,
    translations_generated BOOLEAN NOT NULL DEFAULT false,
    submitted_ip_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_campaigns_budget_min CHECK (total_budget >= 0.00),
    CONSTRAINT ck_campaigns_cpm_min CHECK (cpm_bid >= 2.00),
    CONSTRAINT ck_campaigns_daily_budget_min CHECK (daily_budget IS NULL OR daily_budget >= 2.00),
    CONSTRAINT ck_campaigns_format_valid CHECK (format IN ('native_post', 'interstitial', 'pop_interstitial')),
    CONSTRAINT ck_campaigns_spent_non_negative CHECK (spent_usd >= 0),
    CONSTRAINT ck_campaigns_status_valid CHECK (status IN ('pending_review', 'active', 'paused', 'paused_insufficient_balance', 'stopped', 'rejected')),
    CONSTRAINT fk_campaigns_advertiser_id_advertisers FOREIGN KEY (advertiser_id) REFERENCES advertisers (id) ON DELETE CASCADE,
    CONSTRAINT fk_campaigns_reviewed_by_admin_id_admin_users FOREIGN KEY (reviewed_by_admin_id) REFERENCES admin_users (id) ON DELETE SET NULL,
    CONSTRAINT pk_campaigns PRIMARY KEY (id)
);
CREATE INDEX ix_campaigns_advertiser_id ON campaigns (advertiser_id);
CREATE INDEX ix_campaigns_advertiser_status ON campaigns (advertiser_id, status);
CREATE INDEX ix_campaigns_auction ON campaigns (status, format, target_language, cpm_bid);

CREATE TABLE channels (
    id UUID NOT NULL,
    publisher_id UUID NOT NULL,
    name VARCHAR(160) NOT NULL,
    public_link TEXT NOT NULL,
    private_invite_link TEXT NOT NULL,
    admin_username VARCHAR(64) NOT NULL,
    description TEXT,
    declared_language VARCHAR(8) NOT NULL,
    subscriber_count INTEGER NOT NULL,
    max_ads_per_day INTEGER NOT NULL DEFAULT 1,
    preferred_hours_utc INTEGER[],
    telegram_chat_id BIGINT,
    telegram_username VARCHAR(64),
    status VARCHAR(32) NOT NULL DEFAULT 'pending_moderation',
    rejection_reason TEXT,
    bot_admin_verified BOOLEAN NOT NULL DEFAULT false,
    bot_admin_last_checked_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    suspended_at TIMESTAMPTZ,
    last_ad_posted_at TIMESTAMPTZ,
    lifetime_impressions INTEGER NOT NULL DEFAULT 0,
    lifetime_earnings_usd NUMERIC(12, 2) NOT NULL DEFAULT 0,
    submitted_ip_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_channels_ads_per_day_range CHECK (max_ads_per_day BETWEEN 0 AND 3),
    CONSTRAINT ck_channels_name_min_length CHECK (char_length(name) >= 5),
    CONSTRAINT ck_channels_status_valid CHECK (status IN ('pending_moderation', 'approved_not_started', 'active_building_trust', 'active', 'suspended', 'rejected')),
    CONSTRAINT ck_channels_subscribers_min CHECK (subscriber_count >= 500),
    CONSTRAINT fk_channels_publisher_id_publishers FOREIGN KEY (publisher_id) REFERENCES publishers (id) ON DELETE CASCADE,
    CONSTRAINT pk_channels PRIMARY KEY (id)
);
CREATE INDEX ix_channels_delivery ON channels (status, declared_language);
CREATE INDEX ix_channels_publisher_id ON channels (publisher_id);
CREATE INDEX ix_channels_publisher_status ON channels (publisher_id, status);
CREATE INDEX ix_channels_telegram_chat_id ON channels (telegram_chat_id);

CREATE TABLE deposits (
    id UUID NOT NULL,
    advertiser_id UUID NOT NULL,
    network VARCHAR(8) NOT NULL,
    derived_address VARCHAR(128) NOT NULL,
    memo VARCHAR(64),
    gross_amount_usd NUMERIC(12, 6),
    fee_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    amount_usd NUMERIC(12, 2),
    tx_hash VARCHAR(128),
    block_number BIGINT,
    confirmations INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'awaiting_confirmation',
    confirmed_at TIMESTAMPTZ,
    credited BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_deposits_amount_non_negative CHECK (amount_usd IS NULL OR amount_usd >= 0),
    CONSTRAINT ck_deposits_network_valid CHECK (network IN ('ton', 'trc20', 'bnb')),
    CONSTRAINT ck_deposits_status_valid CHECK (status IN ('awaiting_confirmation', 'confirmed')),
    CONSTRAINT fk_deposits_advertiser_id_advertisers FOREIGN KEY (advertiser_id) REFERENCES advertisers (id) ON DELETE CASCADE,
    CONSTRAINT pk_deposits PRIMARY KEY (id),
    CONSTRAINT uq_deposits_tx_hash UNIQUE (tx_hash)
);
CREATE INDEX ix_deposits_address_network ON deposits (derived_address, network);
CREATE INDEX ix_deposits_advertiser_created ON deposits (advertiser_id, created_at);
CREATE INDEX ix_deposits_advertiser_id ON deposits (advertiser_id);
CREATE INDEX ix_deposits_memo ON deposits (memo);

CREATE TABLE mini_apps (
    id UUID NOT NULL,
    publisher_id UUID NOT NULL,
    name VARCHAR(160) NOT NULL,
    url TEXT NOT NULL,
    original_url TEXT,
    bot_id VARCHAR(64),
    category VARCHAR(64),
    description TEXT,
    kinz_key VARCHAR(64) NOT NULL,
    formats_enabled VARCHAR(24)[] NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending_moderation',
    rejection_reason TEXT,
    approved_at TIMESTAMPTZ,
    integration_detected BOOLEAN NOT NULL DEFAULT false,
    sdk_version VARCHAR(32),
    last_serve_at TIMESTAMPTZ,
    lifetime_impressions INTEGER NOT NULL DEFAULT 0,
    lifetime_earnings_usd NUMERIC(12, 2) NOT NULL DEFAULT 0,
    submitted_ip_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_mini_apps_status_valid CHECK (status IN ('pending_moderation', 'active', 'suspended', 'rejected')),
    CONSTRAINT fk_mini_apps_publisher_id_publishers FOREIGN KEY (publisher_id) REFERENCES publishers (id) ON DELETE CASCADE,
    CONSTRAINT pk_mini_apps PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_mini_apps_kinz_key ON mini_apps (kinz_key);
CREATE INDEX ix_mini_apps_publisher_id ON mini_apps (publisher_id);
CREATE INDEX ix_mini_apps_publisher_status ON mini_apps (publisher_id, status);

CREATE TABLE wallet_addresses (
    id UUID NOT NULL,
    advertiser_id UUID NOT NULL,
    network VARCHAR(8) NOT NULL,
    address VARCHAR(128) NOT NULL,
    memo VARCHAR(64),
    derivation_path VARCHAR(64),
    derivation_index INTEGER,
    last_scanned_at TIMESTAMPTZ,
    last_scanned_cursor VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_wallet_addresses_advertiser_id_advertisers FOREIGN KEY (advertiser_id) REFERENCES advertisers (id) ON DELETE CASCADE,
    CONSTRAINT pk_wallet_addresses PRIMARY KEY (id)
);
CREATE INDEX ix_wallet_addresses_address ON wallet_addresses (address);
CREATE INDEX ix_wallet_addresses_memo ON wallet_addresses (memo);
CREATE UNIQUE INDEX ix_wallet_addresses_unique ON wallet_addresses (advertiser_id, network);

CREATE TABLE withdrawals (
    id UUID NOT NULL,
    publisher_id UUID NOT NULL,
    amount_usd NUMERIC(10, 2) NOT NULL,
    destination_address VARCHAR(128) NOT NULL,
    memo_comment VARCHAR(120),
    network VARCHAR(16) NOT NULL DEFAULT 'ton',
    method_label VARCHAR(32) NOT NULL DEFAULT 'USDT TON',
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    rejection_reason TEXT,
    tx_hash VARCHAR(128),
    payout_error TEXT,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    processed_by_admin_id UUID,
    requested_ip_hash VARCHAR(64),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_withdrawals_amount_min CHECK (amount_usd >= 50.00),
    CONSTRAINT ck_withdrawals_status_valid CHECK (status IN ('pending', 'approved', 'paid', 'rejected')),
    CONSTRAINT fk_withdrawals_processed_by_admin_id_admin_users FOREIGN KEY (processed_by_admin_id) REFERENCES admin_users (id) ON DELETE SET NULL,
    CONSTRAINT fk_withdrawals_publisher_id_publishers FOREIGN KEY (publisher_id) REFERENCES publishers (id) ON DELETE CASCADE,
    CONSTRAINT pk_withdrawals PRIMARY KEY (id)
);
CREATE INDEX ix_withdrawals_publisher_id ON withdrawals (publisher_id);
CREATE INDEX ix_withdrawals_publisher_status ON withdrawals (publisher_id, status);
CREATE INDEX ix_withdrawals_requested ON withdrawals (requested_at);

CREATE TABLE campaign_daily_spend (
    id UUID NOT NULL,
    campaign_id UUID NOT NULL,
    spend_date DATE NOT NULL,
    amount_usd NUMERIC(10, 4) NOT NULL DEFAULT 0,
    impressions INTEGER NOT NULL DEFAULT 0,
    clicks INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT fk_campaign_daily_spend_campaign_id_campaigns FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE,
    CONSTRAINT pk_campaign_daily_spend PRIMARY KEY (id),
    CONSTRAINT uq_campaign_daily_spend_campaign_date UNIQUE (campaign_id, spend_date)
);
CREATE INDEX ix_campaign_daily_spend_date ON campaign_daily_spend (spend_date);

CREATE TABLE campaign_translations (
    id UUID NOT NULL,
    campaign_id UUID NOT NULL,
    lang_code VARCHAR(8) NOT NULL,
    translated_text TEXT NOT NULL,
    translated_button_label VARCHAR(60),
    source VARCHAR(20) NOT NULL DEFAULT 'groq',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_campaign_translations_campaign_id_campaigns FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE,
    CONSTRAINT pk_campaign_translations PRIMARY KEY (id),
    CONSTRAINT uq_campaign_translations_campaign_lang UNIQUE (campaign_id, lang_code)
);
CREATE INDEX ix_campaign_translations_lookup ON campaign_translations (campaign_id, lang_code);

CREATE TABLE impressions (
    id UUID NOT NULL,
    campaign_id UUID NOT NULL,
    tracking_id UUID NOT NULL,
    placement_type VARCHAR(16) NOT NULL,
    placement_id UUID,
    format VARCHAR(24),
    lang_served VARCHAR(8),
    billed BOOLEAN NOT NULL DEFAULT false,
    billed_amount_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    ip_hash VARCHAR(64),
    served_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_impressions_campaign_id_campaigns FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE,
    CONSTRAINT pk_impressions PRIMARY KEY (id)
);
CREATE INDEX ix_impressions_campaign_served ON impressions (campaign_id, served_at);
CREATE INDEX ix_impressions_ip_hash ON impressions (ip_hash);
CREATE INDEX ix_impressions_placement ON impressions (placement_type, placement_id, served_at);
CREATE INDEX ix_impressions_served_at ON impressions (served_at);
CREATE UNIQUE INDEX ix_impressions_tracking_id ON impressions (tracking_id);

CREATE TABLE scheduled_posts (
    id UUID NOT NULL,
    campaign_id UUID NOT NULL,
    channel_id UUID NOT NULL,
    telegram_message_id BIGINT,
    telegram_chat_id BIGINT,
    tracking_id UUID,
    scheduled_for TIMESTAMPTZ,
    posted_at TIMESTAMPTZ,
    delete_at TIMESTAMPTZ,
    deleted BOOLEAN NOT NULL DEFAULT false,
    deleted_at TIMESTAMPTZ,
    delete_error TEXT,
    post_error TEXT,
    last_view_count INTEGER NOT NULL DEFAULT 0,
    billed_views INTEGER NOT NULL DEFAULT 0,
    revenue_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    language_served VARCHAR(8),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_scheduled_posts_campaign_id_campaigns FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE,
    CONSTRAINT fk_scheduled_posts_channel_id_channels FOREIGN KEY (channel_id) REFERENCES channels (id) ON DELETE CASCADE,
    CONSTRAINT pk_scheduled_posts PRIMARY KEY (id)
);
CREATE INDEX ix_scheduled_posts_active_views ON scheduled_posts (deleted, posted_at);
CREATE INDEX ix_scheduled_posts_campaign ON scheduled_posts (campaign_id);
CREATE INDEX ix_scheduled_posts_channel_posted ON scheduled_posts (channel_id, posted_at);
CREATE INDEX ix_scheduled_posts_pending_delete ON scheduled_posts (delete_at, deleted);
CREATE UNIQUE INDEX ix_scheduled_posts_tracking_id ON scheduled_posts (tracking_id);

CREATE TABLE clicks (
    id UUID NOT NULL,
    tracking_id UUID NOT NULL,
    campaign_id UUID NOT NULL,
    scheduled_post_id UUID,
    placement_type VARCHAR(16),
    placement_id UUID,
    ip_hash VARCHAR(64),
    user_agent TEXT,
    referer TEXT,
    country VARCHAR(8),
    asn VARCHAR(32),
    fraud_score NUMERIC(3, 2) NOT NULL DEFAULT 0,
    fraud_reasons JSONB,
    billed BOOLEAN NOT NULL DEFAULT false,
    billed_amount_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    clicked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_clicks_fraud_score_range CHECK (fraud_score BETWEEN 0 AND 1),
    CONSTRAINT fk_clicks_campaign_id_campaigns FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE,
    CONSTRAINT fk_clicks_scheduled_post_id_scheduled_posts FOREIGN KEY (scheduled_post_id) REFERENCES scheduled_posts (id) ON DELETE SET NULL,
    CONSTRAINT pk_clicks PRIMARY KEY (id)
);
CREATE INDEX ix_clicks_campaign_time ON clicks (campaign_id, clicked_at);
CREATE INDEX ix_clicks_clicked_at ON clicks (clicked_at);
CREATE INDEX ix_clicks_ip_time ON clicks (ip_hash, clicked_at);
CREATE INDEX ix_clicks_tracking_id ON clicks (tracking_id);

CREATE TABLE tracking_links (
    id UUID NOT NULL,
    tracking_id UUID NOT NULL,
    campaign_id UUID NOT NULL,
    scheduled_post_id UUID,
    placement_type VARCHAR(16),
    placement_id UUID,
    destination_url TEXT NOT NULL,
    click_count INTEGER NOT NULL DEFAULT 0,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_tracking_links_campaign_id_campaigns FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE,
    CONSTRAINT fk_tracking_links_scheduled_post_id_scheduled_posts FOREIGN KEY (scheduled_post_id) REFERENCES scheduled_posts (id) ON DELETE SET NULL,
    CONSTRAINT pk_tracking_links PRIMARY KEY (id)
);
CREATE INDEX ix_tracking_links_campaign ON tracking_links (campaign_id);
CREATE UNIQUE INDEX ix_tracking_links_tracking_id ON tracking_links (tracking_id);

CREATE TABLE view_snapshots (
    id UUID NOT NULL,
    scheduled_post_id UUID NOT NULL,
    view_count_cumulative INTEGER NOT NULL,
    delta INTEGER NOT NULL DEFAULT 0,
    billed_amount_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    polled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_view_snapshots_views_non_negative CHECK (view_count_cumulative >= 0),
    CONSTRAINT fk_view_snapshots_scheduled_post_id_scheduled_posts FOREIGN KEY (scheduled_post_id) REFERENCES scheduled_posts (id) ON DELETE CASCADE,
    CONSTRAINT pk_view_snapshots PRIMARY KEY (id)
);
CREATE INDEX ix_view_snapshots_post_polled ON view_snapshots (scheduled_post_id, polled_at);

-- ============================================================
-- Migration 0002_add_bep20_sweeps
-- ============================================================

CREATE TABLE bep20_sweeps (
    id UUID NOT NULL,
    deposit_id UUID NOT NULL REFERENCES deposits (id) ON DELETE CASCADE,
    derived_address VARCHAR(128) NOT NULL,
    derivation_index INTEGER NOT NULL,
    treasury_address VARCHAR(128) NOT NULL,
    gross_amount_usd NUMERIC(12, 6),
    swept_amount_usd NUMERIC(12, 6),
    gas_topup_tx_hash VARCHAR(128),
    gas_topup_amount_bnb NUMERIC(18, 18),
    sweep_tx_hash VARCHAR(128),
    dust_return_tx_hash VARCHAR(128),
    dust_return_amount_bnb VARCHAR(128),
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_bep20_sweeps PRIMARY KEY (id),
    CONSTRAINT uq_bep20_sweeps_deposit_id UNIQUE (deposit_id)
);
CREATE UNIQUE INDEX ix_bep20_sweeps_deposit ON bep20_sweeps (deposit_id);
CREATE INDEX ix_bep20_sweeps_status ON bep20_sweeps (status);

-- ============================================================
-- Migration 0003_add_refresh_tokens
-- ============================================================

CREATE TABLE refresh_tokens (
    id UUID NOT NULL,
    account_type VARCHAR(20) NOT NULL,
    account_id UUID NOT NULL,
    jti VARCHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_refresh_tokens PRIMARY KEY (id),
    CONSTRAINT uq_refresh_tokens_jti UNIQUE (jti)
);
CREATE INDEX ix_refresh_tokens_account ON refresh_tokens (account_type, account_id);
CREATE INDEX ix_refresh_tokens_expires ON refresh_tokens (expires_at);

-- ============================================================
-- Migration 0004_add_email_verification
-- ============================================================

ALTER TABLE advertisers ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE advertisers ADD COLUMN email_verification_code VARCHAR(8);
ALTER TABLE advertisers ADD COLUMN email_verification_expires_at TIMESTAMPTZ;
ALTER TABLE publishers ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE publishers ADD COLUMN email_verification_code VARCHAR(8);
ALTER TABLE publishers ADD COLUMN email_verification_expires_at TIMESTAMPTZ;

-- ============================================================
-- Marqueur alembic : dit au backend que les 4 migrations sont faites.
-- ============================================================

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO alembic_version (version_num) VALUES ('0004_add_email_verification');

COMMIT;

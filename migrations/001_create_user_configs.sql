-- Migration 001: Create user_configs table
-- Maps 1:1 to ScannerConfig dataclass in core/config.py
-- Run in Supabase SQL Editor: https://supabase.com/dashboard → SQL Editor → New Query
--
-- This table stores per-user scanner configuration. For now (single-user),
-- user_id is a TEXT field holding a placeholder ID. When Supabase Auth is
-- added in Phase 1, this migrates to UUID REFERENCES auth.users(id).

CREATE TABLE IF NOT EXISTS user_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT NOT NULL,           -- placeholder; becomes UUID FK in Phase 1

    -- Watchlist & strategy
    tickers         TEXT[] DEFAULT '{TSLA,NVDA}',
    strategy        TEXT DEFAULT 'both',     -- 'cc' | 'csp' | 'both'
    data_source     TEXT DEFAULT 'yahoo',    -- 'yahoo' | 'ibkr'

    -- Expiry window
    min_dte         INT DEFAULT 21,
    max_dte         INT DEFAULT 42,

    -- Strike range
    strike_range_pct FLOAT DEFAULT 0.2,      -- ±20% of current price

    -- Delta range
    cc_delta_min    FLOAT DEFAULT 0.20,
    cc_delta_max    FLOAT DEFAULT 0.35,
    csp_delta_min   FLOAT DEFAULT -0.35,
    csp_delta_max   FLOAT DEFAULT -0.20,

    -- Theta
    min_theta       FLOAT DEFAULT 0.08,

    -- IV filters
    min_iv_rank     FLOAT DEFAULT 0.0,
    max_iv_rank     FLOAT DEFAULT 100.0,
    min_iv          FLOAT DEFAULT 0.40,

    -- Vega
    max_vega        FLOAT DEFAULT 0.50,

    -- Return / premium
    min_annualised_return FLOAT DEFAULT 0.15,
    min_premium     FLOAT DEFAULT 2.00,

    -- Liquidity
    min_open_interest INT DEFAULT 0,
    min_volume      INT DEFAULT 0,
    max_bid_ask_spread_pct FLOAT DEFAULT 1.0,

    -- Scoring weights (must sum to 1.0)
    weight_iv              FLOAT DEFAULT 0.15,
    weight_theta_yield     FLOAT DEFAULT 0.15,
    weight_delta_safety    FLOAT DEFAULT 0.20,
    weight_liquidity       FLOAT DEFAULT 0.10,
    weight_ann_return      FLOAT DEFAULT 0.25,
    weight_mean_reversion  FLOAT DEFAULT 0.15,

    -- Mean reversion settings
    use_mean_reversion BOOLEAN DEFAULT TRUE,
    mr_rsi_period      INT DEFAULT 5,
    mr_z_period        INT DEFAULT 20,
    mr_roc_period      INT DEFAULT 100,
    mr_w_rsi           FLOAT DEFAULT 0.40,
    mr_w_z             FLOAT DEFAULT 0.40,
    mr_w_roc           FLOAT DEFAULT 0.20,
    mr_trend_guard     BOOLEAN DEFAULT TRUE,
    mr_trend_pct       FLOAT DEFAULT 15.0,

    -- Timestamps
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),

    UNIQUE(user_id)
);

-- Auto-update updated_at on every UPDATE
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_user_configs_updated_at
    BEFORE UPDATE ON user_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Row-level security (prepared for Phase 1 — not enforced until auth is added)
ALTER TABLE user_configs ENABLE ROW LEVEL SECURITY;

-- Phase 0: allow all access (single user, no auth yet)
-- Phase 1: replace with: CREATE POLICY ... USING (auth.uid()::text = user_id);
CREATE POLICY "Allow all access during Phase 0"
    ON user_configs FOR ALL
    USING (true)
    WITH CHECK (true);

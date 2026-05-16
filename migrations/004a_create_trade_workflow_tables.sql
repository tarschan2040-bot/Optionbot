-- Migration 004a: Create trade workflow tables for shadow review
--
-- Purpose:
-- Some shadow Supabase projects may have the SaaS config/scan tables but not
-- the candidate and portfolio workflow tables. The active backend expects:
--
--   trade_candidates - starred/approved/placed/rejected scan ideas
--   trade_log        - confirmed portfolio trades, open and closed
--
-- Run this in shadow before migration 005 if these tables are missing.
-- Do not run against production without a separate production approval.

BEGIN;

CREATE TABLE IF NOT EXISTS trade_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,

    ticker TEXT NOT NULL,
    strategy TEXT NOT NULL,
    strike DOUBLE PRECISION NOT NULL,
    expiry DATE NOT NULL,
    dte INTEGER NOT NULL,

    delta DOUBLE PRECISION,
    theta DOUBLE PRECISION,
    premium DOUBLE PRECISION,
    total_premium DOUBLE PRECISION,
    contracts INTEGER NOT NULL DEFAULT 1,
    score DOUBLE PRECISION,
    iv_rank DOUBLE PRECISION,
    ann_return DOUBLE PRECISION,

    scan_time TIMESTAMPTZ DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'starred', 'approved', 'placed', 'rejected')),
    approved_at TIMESTAMPTZ,
    rejected_at TIMESTAMPTZ,
    notes TEXT,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trade_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,

    trade_date DATE NOT NULL DEFAULT CURRENT_DATE,
    ticker TEXT NOT NULL,
    strategy TEXT NOT NULL,
    strike DOUBLE PRECISION NOT NULL,
    expiry DATE NOT NULL,
    dte_at_entry INTEGER,

    entry_price DOUBLE PRECISION,
    contracts INTEGER NOT NULL DEFAULT 1,
    entry_delta DOUBLE PRECISION,
    iv_percentile DOUBLE PRECISION,
    net_premium DOUBLE PRECISION,
    candidate_id UUID REFERENCES trade_candidates(id) ON DELETE SET NULL,

    exit_date DATE,
    exit_price DOUBLE PRECISION,
    pnl DOUBLE PRECISION,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trade_candidates_user_status_time
    ON trade_candidates (user_id, status, scan_time DESC);

CREATE INDEX IF NOT EXISTS idx_trade_candidates_user_ticker_expiry
    ON trade_candidates (user_id, ticker, expiry);

CREATE INDEX IF NOT EXISTS idx_trade_log_user_exit_trade_date
    ON trade_log (user_id, exit_date, trade_date DESC);

CREATE INDEX IF NOT EXISTS idx_trade_log_user_candidate_id
    ON trade_log (user_id, candidate_id);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_trade_candidates_updated_at ON trade_candidates;
CREATE TRIGGER update_trade_candidates_updated_at
    BEFORE UPDATE ON trade_candidates
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_trade_log_updated_at ON trade_log;
CREATE TRIGGER update_trade_log_updated_at
    BEFORE UPDATE ON trade_log
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE trade_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE trade_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all access during Phase 0" ON trade_candidates;
CREATE POLICY "Allow all access during Phase 0"
    ON trade_candidates FOR ALL
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS "Allow all access during Phase 0" ON trade_log;
CREATE POLICY "Allow all access during Phase 0"
    ON trade_log FOR ALL
    USING (true)
    WITH CHECK (true);

COMMIT;

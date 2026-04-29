-- Migration 002: Create scan_results table
-- Stores per-user scan output (results JSONB + metadata).
-- Used by: GET /scan/results, POST /scan/trigger, GET /scan/history
--
-- Run in Supabase SQL Editor after 001_create_user_configs.sql

CREATE TABLE IF NOT EXISTS scan_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             TEXT NOT NULL,           -- placeholder; becomes UUID FK in Phase 1 auth migration

    -- Scan metadata
    config_hash         TEXT NOT NULL,           -- SHA-256 of ScannerConfig used (audit trail)
    scan_timestamp      TIMESTAMPTZ DEFAULT now(),
    slot_label          TEXT,                    -- 'Open', 'Midday', 'Pre-Close', 'Manual'

    -- Results
    results             JSONB NOT NULL,          -- array of scored opportunities (rank, ticker, score, greeks, etc.)
    ticker_count        INT,                     -- how many tickers were scanned
    opportunity_count   INT,                     -- how many opportunities passed filters
    duration_seconds    FLOAT                    -- scan wall-clock time
);

-- Index for fast per-user latest-first queries
CREATE INDEX IF NOT EXISTS idx_scan_results_user_time
    ON scan_results (user_id, scan_timestamp DESC);

-- Index for config_hash lookups (reproduce a scan)
CREATE INDEX IF NOT EXISTS idx_scan_results_config_hash
    ON scan_results (config_hash);

-- Row-level security
ALTER TABLE scan_results ENABLE ROW LEVEL SECURITY;

-- Phase 0: allow all access (single user, no auth yet)
-- Phase 1: replace with: CREATE POLICY ... USING (auth.uid()::text = user_id);
CREATE POLICY "Allow all access during Phase 0"
    ON scan_results FOR ALL
    USING (true)
    WITH CHECK (true);

-- Migration 004: Add user_id scoping to trade_candidates and trade_log
-- Required for multi-user isolation in the SaaS workflow.
--
-- Run in Supabase SQL Editor after migrations 001-003.
--
-- Important:
-- 1. This adds the user_id columns the web app now expects.
-- 2. Existing legacy rows will have NULL user_id until backfilled.
-- 3. Rows with NULL user_id will no longer appear in the web portfolio/candidates
--    endpoints once the backend is updated.
-- 4. Backfill existing owner rows manually after deciding the correct owner UUID.

ALTER TABLE IF EXISTS trade_candidates
    ADD COLUMN IF NOT EXISTS user_id TEXT;

ALTER TABLE IF EXISTS trade_log
    ADD COLUMN IF NOT EXISTS user_id TEXT;

CREATE INDEX IF NOT EXISTS idx_trade_candidates_user_status_time
    ON trade_candidates (user_id, status, scan_time DESC);

CREATE INDEX IF NOT EXISTS idx_trade_log_user_exit_trade_date
    ON trade_log (user_id, exit_date, trade_date DESC);

CREATE INDEX IF NOT EXISTS idx_trade_log_user_candidate_id
    ON trade_log (user_id, candidate_id);

-- Optional manual backfill example for legacy owner rows:
-- Replace OWNER_UUID with the real Supabase auth user ID for the owner account.
--
-- UPDATE trade_candidates
-- SET user_id = 'OWNER_UUID'
-- WHERE user_id IS NULL;
--
-- UPDATE trade_log
-- SET user_id = 'OWNER_UUID'
-- WHERE user_id IS NULL;

-- Future tightening:
-- - make user_id NOT NULL after backfill
-- - replace permissive RLS with auth.uid()::text = user_id policies

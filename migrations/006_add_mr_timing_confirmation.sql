-- Migration 006: Add mean-reversion timing confirmation settings
--
-- Adds the user-configurable Option 2 timing layer:
-- raw MR detects the setup, while timing confirmation can cap strong
-- unconfirmed setups until the MR score starts cooling from an extreme.

ALTER TABLE user_configs
    ADD COLUMN IF NOT EXISTS mr_timing_confirmation BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS mr_timing_sma_period INT DEFAULT 3,
    ADD COLUMN IF NOT EXISTS mr_timing_unconfirmed_cap FLOAT DEFAULT 0.75;

UPDATE user_configs
SET
    mr_timing_confirmation = COALESCE(mr_timing_confirmation, TRUE),
    mr_timing_sma_period = COALESCE(mr_timing_sma_period, 3),
    mr_timing_unconfirmed_cap = COALESCE(mr_timing_unconfirmed_cap, 0.75);

COMMENT ON COLUMN user_configs.mr_timing_confirmation
    IS 'When true, cap strong unconfirmed mean-reversion setups until timing confirms.';
COMMENT ON COLUMN user_configs.mr_timing_sma_period
    IS 'Daily raw MR score SMA period used for timing confirmation.';
COMMENT ON COLUMN user_configs.mr_timing_unconfirmed_cap
    IS 'Maximum effective MR score for strong setups before timing confirmation.';

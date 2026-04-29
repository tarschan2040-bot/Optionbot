-- Migration 003: Create subscriptions table
-- Tracks Stripe subscription status per user.
-- Used by: tier-gating (free vs pro), Stripe webhook handler
--
-- Run in Supabase SQL Editor after 002_create_scan_results.sql

CREATE TABLE IF NOT EXISTS subscriptions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 TEXT NOT NULL,           -- placeholder; becomes UUID FK in Phase 1 auth migration

    -- Stripe references
    stripe_customer_id      TEXT,
    stripe_subscription_id  TEXT,

    -- Subscription state
    tier                    TEXT DEFAULT 'free',     -- 'free' or 'pro'
    status                  TEXT DEFAULT 'active',   -- 'active', 'cancelled', 'past_due', 'trialing'
    current_period_end      TIMESTAMPTZ,

    -- Timestamps
    created_at              TIMESTAMPTZ DEFAULT now(),
    updated_at              TIMESTAMPTZ DEFAULT now(),

    UNIQUE(user_id)
);

-- Auto-update updated_at
CREATE TRIGGER update_subscriptions_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();  -- function created in migration 001

-- Row-level security
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Users can only READ their own subscription (writes happen via Stripe webhook / server-side)
CREATE POLICY "Allow all access during Phase 0"
    ON subscriptions FOR ALL
    USING (true)
    WITH CHECK (true);

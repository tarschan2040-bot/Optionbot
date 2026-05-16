-- Migration 005: Harden SaaS user isolation
-- Converts SaaS ownership columns to UUID, adds auth.users FKs, and replaces
-- Phase 0 permissive RLS with authenticated-user ownership policies.
--
-- IMPORTANT RELEASE NOTE:
-- Apply this only after the backend/worker have SUPABASE_SERVICE_ROLE_KEY
-- configured, or after backend queries are changed to forward end-user JWTs.
-- The current FastAPI layer does its own auth and user_id filtering; the
-- service role lets it keep working after browser-facing RLS is tightened.
--
-- Preflight:
-- - Backfill any NULL trade_candidates.user_id / trade_log.user_id rows first.
-- - Remove or migrate any non-UUID placeholder user_id values such as 'owner'.
-- - Confirm every user_id UUID belongs to a real Supabase auth.users row.
-- - Run in a shadow Supabase project before production.

BEGIN;

-- ── Preflight validation ──────────────────────────────────────────────────

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM user_configs
        WHERE user_id::text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    ) THEN
        RAISE EXCEPTION 'user_configs contains non-UUID user_id values. Backfill before migration 005.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM scan_results
        WHERE user_id::text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    ) THEN
        RAISE EXCEPTION 'scan_results contains non-UUID user_id values. Backfill before migration 005.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM subscriptions
        WHERE user_id::text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    ) THEN
        RAISE EXCEPTION 'subscriptions contains non-UUID user_id values. Backfill before migration 005.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM user_configs uc
        WHERE NOT EXISTS (
            SELECT 1 FROM auth.users au WHERE au.id = uc.user_id::uuid
        )
    ) THEN
        RAISE EXCEPTION 'user_configs contains user_id values that do not exist in auth.users. Backfill before migration 005.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM scan_results sr
        WHERE NOT EXISTS (
            SELECT 1 FROM auth.users au WHERE au.id = sr.user_id::uuid
        )
    ) THEN
        RAISE EXCEPTION 'scan_results contains user_id values that do not exist in auth.users. Backfill before migration 005.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM subscriptions s
        WHERE NOT EXISTS (
            SELECT 1 FROM auth.users au WHERE au.id = s.user_id::uuid
        )
    ) THEN
        RAISE EXCEPTION 'subscriptions contains user_id values that do not exist in auth.users. Backfill before migration 005.';
    END IF;

    IF to_regclass('public.trade_candidates') IS NOT NULL THEN
        IF EXISTS (SELECT 1 FROM trade_candidates WHERE user_id IS NULL) THEN
            RAISE EXCEPTION 'trade_candidates contains NULL user_id values. Backfill before migration 005.';
        END IF;
        IF EXISTS (
            SELECT 1 FROM trade_candidates
            WHERE user_id::text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        ) THEN
            RAISE EXCEPTION 'trade_candidates contains non-UUID user_id values. Backfill before migration 005.';
        END IF;
        IF EXISTS (
            SELECT 1
            FROM trade_candidates tc
            WHERE NOT EXISTS (
                SELECT 1 FROM auth.users au WHERE au.id = tc.user_id::uuid
            )
        ) THEN
            RAISE EXCEPTION 'trade_candidates contains user_id values that do not exist in auth.users. Backfill before migration 005.';
        END IF;
    END IF;

    IF to_regclass('public.trade_log') IS NOT NULL THEN
        IF EXISTS (SELECT 1 FROM trade_log WHERE user_id IS NULL) THEN
            RAISE EXCEPTION 'trade_log contains NULL user_id values. Backfill before migration 005.';
        END IF;
        IF EXISTS (
            SELECT 1 FROM trade_log
            WHERE user_id::text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        ) THEN
            RAISE EXCEPTION 'trade_log contains non-UUID user_id values. Backfill before migration 005.';
        END IF;
        IF EXISTS (
            SELECT 1
            FROM trade_log tl
            WHERE NOT EXISTS (
                SELECT 1 FROM auth.users au WHERE au.id = tl.user_id::uuid
            )
        ) THEN
            RAISE EXCEPTION 'trade_log contains user_id values that do not exist in auth.users. Backfill before migration 005.';
        END IF;
    END IF;
END $$;

-- ── Drop existing RLS policies before changing user_id column types ───────
-- PostgreSQL will not alter a column while an RLS policy depends on it.

DROP POLICY IF EXISTS "Allow all access during Phase 0" ON user_configs;
DROP POLICY IF EXISTS "Users manage own configs" ON user_configs;

DROP POLICY IF EXISTS "Allow all access during Phase 0" ON scan_results;
DROP POLICY IF EXISTS "Users read own scan results" ON scan_results;

DROP POLICY IF EXISTS "Allow all access during Phase 0" ON subscriptions;
DROP POLICY IF EXISTS "Users read own subscriptions" ON subscriptions;

DO $$
BEGIN
    IF to_regclass('public.trade_candidates') IS NOT NULL THEN
        EXECUTE 'DROP POLICY IF EXISTS "Allow all access during Phase 0" ON trade_candidates';
        EXECUTE 'DROP POLICY IF EXISTS "Users manage own trade candidates" ON trade_candidates';
    END IF;

    IF to_regclass('public.trade_log') IS NOT NULL THEN
        EXECUTE 'DROP POLICY IF EXISTS "Allow all access during Phase 0" ON trade_log';
        EXECUTE 'DROP POLICY IF EXISTS "Users manage own trade log" ON trade_log';
    END IF;
END $$;

-- ── Convert user_id columns and add referential integrity ─────────────────

ALTER TABLE user_configs
    ALTER COLUMN user_id TYPE UUID USING user_id::uuid,
    ALTER COLUMN user_id SET NOT NULL;

ALTER TABLE scan_results
    ALTER COLUMN user_id TYPE UUID USING user_id::uuid,
    ALTER COLUMN user_id SET NOT NULL;

ALTER TABLE subscriptions
    ALTER COLUMN user_id TYPE UUID USING user_id::uuid,
    ALTER COLUMN user_id SET NOT NULL;

ALTER TABLE IF EXISTS trade_candidates
    ALTER COLUMN user_id TYPE UUID USING user_id::uuid,
    ALTER COLUMN user_id SET NOT NULL;

ALTER TABLE IF EXISTS trade_log
    ALTER COLUMN user_id TYPE UUID USING user_id::uuid,
    ALTER COLUMN user_id SET NOT NULL;

ALTER TABLE user_configs
    DROP CONSTRAINT IF EXISTS user_configs_user_id_fkey,
    ADD CONSTRAINT user_configs_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE scan_results
    DROP CONSTRAINT IF EXISTS scan_results_user_id_fkey,
    ADD CONSTRAINT scan_results_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE subscriptions
    DROP CONSTRAINT IF EXISTS subscriptions_user_id_fkey,
    ADD CONSTRAINT subscriptions_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE IF EXISTS trade_candidates
    DROP CONSTRAINT IF EXISTS trade_candidates_user_id_fkey,
    ADD CONSTRAINT trade_candidates_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE IF EXISTS trade_log
    DROP CONSTRAINT IF EXISTS trade_log_user_id_fkey,
    ADD CONSTRAINT trade_log_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

-- ── RLS: replace Phase 0 open policies with ownership policies ────────────

ALTER TABLE user_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE scan_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS trade_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS trade_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own configs"
    ON user_configs
    FOR ALL
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users read own scan results"
    ON scan_results
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Users read own subscriptions"
    ON subscriptions
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

DO $$
BEGIN
    IF to_regclass('public.trade_candidates') IS NOT NULL THEN
        EXECUTE 'CREATE POLICY "Users manage own trade candidates"
            ON trade_candidates
            FOR ALL
            TO authenticated
            USING (auth.uid() = user_id)
            WITH CHECK (auth.uid() = user_id)';
    END IF;

    IF to_regclass('public.trade_log') IS NOT NULL THEN
        EXECUTE 'CREATE POLICY "Users manage own trade log"
            ON trade_log
            FOR ALL
            TO authenticated
            USING (auth.uid() = user_id)
            WITH CHECK (auth.uid() = user_id)';
    END IF;
END $$;

COMMIT;

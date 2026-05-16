# OptionBot Shadow Review

Use this file as the fixed starting point before any live deploy.

Shadow review means:

- run the current local code only
- review it against localhost and a shadow Supabase project when possible
- do not apply production migrations from this checklist
- do not deploy frontend, backend, worker, or database changes from this checklist

## Review Location

After starting the local services, review the app here:

- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/health
- Backend API docs: http://localhost:8000/docs

If port 3000 is busy, Next.js may choose another local port. Use the URL printed by `npm run dev`.

## Required Environment

Before starting services, confirm local environment values point to a shadow or local review setup.

Backend `.env`:

```bash
SUPABASE_URL=<shadow-supabase-url>
SUPABASE_KEY=<shadow-supabase-anon-key>
SUPABASE_SERVICE_ROLE_KEY=<shadow-supabase-service-role-key>
OPTIONBOT_OWNER_USER_ID=<shadow-auth-user-uuid>
FRONTEND_URL=http://localhost:3000
```

Frontend `frontend/.env.local`:

```bash
NEXT_PUBLIC_SUPABASE_URL=<shadow-supabase-url>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<shadow-supabase-anon-key>
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Do not use production Supabase keys or production auth users for shadow review unless that is explicitly approved for a controlled production-risk test.

## Start Local Shadow Services

Terminal 1, backend API:

```bash
python3 -m uvicorn backend.app:app --reload --port 8000
```

Terminal 2, frontend:

```bash
cd frontend
npm run dev
```

Optional Terminal 3, worker:

```bash
python3 -m backend.worker
```

Only run the worker when the shadow database and owner user are ready, because it can write scan/candidate rows.

## Pre-Deploy Review Checklist

Run these checks from the repo root unless noted otherwise:

```bash
python3 -B -m pytest -q -p no:cacheprovider tools/test_greeks.py tools/test_regressions.py
python3 -B -c "import backend.app; print('backend import ok')"
```

Run this from `frontend/`:

```bash
npm run typecheck
npm run lint
npm run build
```

Current note: on 2026-05-15, `npm run typecheck`, `npm run lint`, and
`npm run build` passed in the local checkout. The frontend build script uses
`next build --webpack` because the default Next 16 Turbopack build can fail in
restricted local review environments when its CSS worker tries to bind a helper
port. If any check fails later, treat it as a fresh local environment or source
issue and inspect the new error.

Latest local check: on 2026-05-15, `npm run shadow:check`, backend import, and
Python regressions passed after the portfolio/live-data cleanup.

## What To Review In The Browser

1. Sign in with a shadow reviewer account.
2. Open Account and confirm the displayed tier matches the backend `/me` response.
3. Open scanner/dashboard pages and confirm no unauthenticated content flashes as valid data.
4. Star a candidate in the shadow account.
5. Confirm the candidate and verify a trade log row is created before the candidate becomes `placed`.
6. Sign in as a second shadow user and confirm the first user's configs, candidates, scan results, subscriptions, and trades are not visible.
7. Let the session sit long enough for token refresh behavior, then perform an API-backed action.

## Migration 005 Shadow Rule

`migrations/005_harden_user_isolation.sql` must be tested in a shadow Supabase project before production.

Plain English: this migration changes saved `user_id` values from loose text
into real Supabase user IDs, then locks each table so signed-in users can only
read or write their own rows. If a row has no owner, an old placeholder owner,
or an owner ID that does not exist as a real Supabase auth user, the migration
must stop.

The migration also drops old Phase 0 or owner-scoped RLS policies before it
changes `user_id` column types, then recreates the strict owner policies. Plain
English: PostgreSQL cannot reshape a column while an existing security rule is
still attached to that column.

Before migration `005`, confirm the shadow project has the candidate and
portfolio tables:

```sql
SELECT to_regclass('public.trade_candidates') AS trade_candidates;
SELECT to_regclass('public.trade_log') AS trade_log;
```

If either result is blank, run
`migrations/004a_create_trade_workflow_tables.sql` in the shadow Supabase SQL
editor first. Plain English: `004a` creates the missing tables that store
starred candidates and portfolio trades.

Before running it anywhere:

- backend and worker must have `SUPABASE_SERVICE_ROLE_KEY`
- legacy `trade_candidates.user_id` and `trade_log.user_id` values must be real auth UUIDs
- `OPTIONBOT_OWNER_USER_ID` must be set for legacy scanner and Telegram workflows
- rollback/restore steps must be ready for the database layer

Run these read-only checks in the shadow Supabase SQL editor before applying
migration `005`. Every `bad_rows` value should be `0`.

```sql
SELECT 'user_configs_non_uuid' AS check_name, count(*) AS bad_rows
FROM user_configs
WHERE user_id::text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';

SELECT 'scan_results_non_uuid' AS check_name, count(*) AS bad_rows
FROM scan_results
WHERE user_id::text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';

SELECT 'subscriptions_non_uuid' AS check_name, count(*) AS bad_rows
FROM subscriptions
WHERE user_id::text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';

SELECT 'trade_candidates_missing_owner' AS check_name, count(*) AS bad_rows
FROM trade_candidates
WHERE user_id IS NULL
   OR user_id::text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';

SELECT 'trade_log_missing_owner' AS check_name, count(*) AS bad_rows
FROM trade_log
WHERE user_id IS NULL
   OR user_id::text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';
```

After those are all zero, check for valid-looking UUIDs that are not real
Supabase users. These should also return `0`.

```sql
SELECT 'user_configs_orphan_auth_user' AS check_name, count(*) AS bad_rows
FROM user_configs uc
LEFT JOIN auth.users au ON au.id = uc.user_id::uuid
WHERE au.id IS NULL;

SELECT 'scan_results_orphan_auth_user' AS check_name, count(*) AS bad_rows
FROM scan_results sr
LEFT JOIN auth.users au ON au.id = sr.user_id::uuid
WHERE au.id IS NULL;

SELECT 'subscriptions_orphan_auth_user' AS check_name, count(*) AS bad_rows
FROM subscriptions s
LEFT JOIN auth.users au ON au.id = s.user_id::uuid
WHERE au.id IS NULL;

SELECT 'trade_candidates_orphan_auth_user' AS check_name, count(*) AS bad_rows
FROM trade_candidates tc
LEFT JOIN auth.users au ON au.id = tc.user_id::uuid
WHERE au.id IS NULL;

SELECT 'trade_log_orphan_auth_user' AS check_name, count(*) AS bad_rows
FROM trade_log tl
LEFT JOIN auth.users au ON au.id = tl.user_id::uuid
WHERE au.id IS NULL;
```

After running it in shadow, verify direct Supabase client access only returns rows owned by the signed-in user.

## Migration 006 Shadow Rule

`migrations/006_add_mr_timing_confirmation.sql` must be reviewed in shadow
before production. It is an additive config migration for `user_configs`, not a
data-isolation migration.

Plain English: this migration adds three mean-reversion timing settings so the
frontend, backend config API, scanner config model, and database can all store
the same timing-confirmation values:

- `mr_timing_confirmation`
- `mr_timing_sma_period`
- `mr_timing_unconfirmed_cap`

Code/schema alignment checked locally on 2026-05-15:

- `core/config.py` defines all three fields and validates their ranges.
- `backend/routers/config.py` exposes all three fields in config responses and updates.
- `data/supabase_client.py` dynamically saves/loads all stored `ScannerConfig` fields.
- `frontend/src/app/settings/page.tsx` and `frontend/src/app/scan/parameters/page.tsx`
  expose the controls.
- `tools/test_regressions.py` covers MR timing behavior.

Run this read-only check in the shadow Supabase SQL editor before applying
`006`:

```sql
SELECT
    to_regclass('public.user_configs') AS user_configs,
    EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'user_configs'
          AND column_name = 'mr_timing_confirmation'
    ) AS has_mr_timing_confirmation,
    EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'user_configs'
          AND column_name = 'mr_timing_sma_period'
    ) AS has_mr_timing_sma_period,
    EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'user_configs'
          AND column_name = 'mr_timing_unconfirmed_cap'
    ) AS has_mr_timing_unconfirmed_cap;
```

Expected before migration:

- `user_configs` is not blank.
- The three `has_*` columns may be false if the shadow project predates these fields.

After applying `006` in shadow, run:

```sql
SELECT
    count(*) FILTER (WHERE mr_timing_confirmation IS NULL) AS null_confirmation,
    count(*) FILTER (WHERE mr_timing_sma_period IS NULL) AS null_sma_period,
    count(*) FILTER (WHERE mr_timing_unconfirmed_cap IS NULL) AS null_cap,
    count(*) FILTER (WHERE mr_timing_sma_period < 2) AS bad_sma_period,
    count(*) FILTER (
        WHERE mr_timing_unconfirmed_cap < 0.50
           OR mr_timing_unconfirmed_cap > 1.00
    ) AS bad_cap
FROM user_configs;
```

Every value should be `0`. Then verify in the shadow app:

1. Open Settings or Scan Parameters.
2. Confirm MR timing controls load with defaults.
3. Save a config change.
4. Reload the page and confirm the values persist.
5. Run the local regression and frontend checks again.

## Promotion Gate

Passing this shadow review is not deployment approval.

Deployment needs a separate explicit approval after shadow review, then a second explicit approval for production deployment itself.

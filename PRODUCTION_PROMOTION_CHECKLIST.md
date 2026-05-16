# Production Promotion Checklist

Last updated: 2026-05-15

This checklist is for deciding whether the shadow-tested database changes are
ready to promote to the live Supabase project.

Plain English: this file is a safety checklist. It is not permission to run the
migrations. Production Supabase must not be changed until there is a separate,
explicit approval for that exact production action.

## Project Names

- Shadow/testing Supabase: `sysgzfualdunywahxico`
- Live/production Supabase: `eaphmnbbsfvuxzbmsmos`

Before doing anything in Supabase, check the browser URL and project ref. The
production project ref must be `eaphmnbbsfvuxzbmsmos`.

## Scope

This promotion is only about these local migrations:

- `migrations/004a_create_trade_workflow_tables.sql`
  - creates `trade_candidates` and `trade_log` if the target project does not
    already have those workflow tables.
- `migrations/005_harden_user_isolation.sql`
  - changes `user_id` columns to real Supabase Auth UUIDs.
  - adds foreign keys to `auth.users`.
  - replaces open Phase 0 RLS policies with owner-only policies.

Do not include `migrations/006_add_mr_timing_confirmation.sql` in this
production action unless it gets its own separate review and approval.

## Stop Conditions

Stop immediately if any of these are true:

- You are looking at the shadow project instead of production, or you are not
  sure which Supabase project is open.
- Any production precheck below returns a non-zero `bad_rows` value.
- Production backend or worker is missing `SUPABASE_SERVICE_ROLE_KEY`.
- Production backend or worker is missing `OPTIONBOT_OWNER_USER_ID`.
- No current Supabase backup, restore point, or clone/restore plan is confirmed.
- The user has not explicitly approved the exact production step being run.

Plain English: a non-zero `bad_rows` means the database has rows that migration
`005` cannot safely lock to a real user. That needs fixing before the migration,
not during it.

## Approval Gates

Use these gates in order:

1. Docs/checklist approval.
   - Current task only.
   - No production impact.
2. Production precheck approval.
   - Read-only checks against production.
   - Still no schema change.
3. Migration `004a` approval, only if production is missing
   `trade_candidates` or `trade_log`.
4. Migration `005` approval.
   - This is the main production database change.
5. Deploy or restart approval, only if a service change is needed after the
   database migration.

Approval for one gate does not approve the next gate.

## Before Production Prechecks

Confirm these production environment requirements without copying secrets into
chat or docs:

- Backend `SUPABASE_URL` points to `https://eaphmnbbsfvuxzbmsmos.supabase.co`.
- Backend `SUPABASE_KEY` is the production anon key.
- Backend `SUPABASE_SERVICE_ROLE_KEY` exists and is production server-only.
- Backend `OPTIONBOT_OWNER_USER_ID` is a real production `auth.users.id` UUID.
- Backend `FRONTEND_URL` points to the live frontend domain.
- Worker has the same production Supabase and owner settings as the backend.
- Frontend `NEXT_PUBLIC_SUPABASE_URL` points to
  `https://eaphmnbbsfvuxzbmsmos.supabase.co`.
- Frontend `NEXT_PUBLIC_SUPABASE_ANON_KEY` is the production anon key.
- Frontend `NEXT_PUBLIC_API_URL` points to the production backend.

Plain English: migration `005` makes browser/direct database access stricter.
The backend and worker need the service role key because they already do their
own login check and user filtering before talking to Supabase.

## Production Precheck 1: Confirm Workflow Tables

Run this in the production Supabase SQL editor only after approval for
production read-only prechecks.

```sql
SELECT
    to_regclass('public.trade_candidates') AS trade_candidates,
    to_regclass('public.trade_log') AS trade_log;
```

Expected result:

- Both values are not blank: production already has the workflow tables.
- Either value is blank: production needs `004a` before `005`, but only after
  separate approval.

## Production Precheck 2: Check Bad Owner Values

Run this in the production Supabase SQL editor only after approval for
production read-only prechecks.

Every `bad_rows` value must be `0`.

Only run this after Precheck 1 confirms both `trade_candidates` and `trade_log`
exist. If either table is missing, stop and decide separately whether to run
`004a`.

```sql
SELECT 'user_configs_non_uuid' AS check_name, count(*) AS bad_rows
FROM user_configs
WHERE user_id::text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'

UNION ALL
SELECT 'scan_results_non_uuid' AS check_name, count(*) AS bad_rows
FROM scan_results
WHERE user_id::text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'

UNION ALL
SELECT 'subscriptions_non_uuid' AS check_name, count(*) AS bad_rows
FROM subscriptions
WHERE user_id::text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'

UNION ALL
SELECT 'trade_candidates_missing_or_bad_owner' AS check_name, count(*) AS bad_rows
FROM trade_candidates
WHERE user_id IS NULL
   OR user_id::text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'

UNION ALL
SELECT 'trade_log_missing_or_bad_owner' AS check_name, count(*) AS bad_rows
FROM trade_log
WHERE user_id IS NULL
   OR user_id::text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';
```

Plain English: this checks for old placeholder owners like `owner`, blank
owners, or any value that is not shaped like a real Supabase user ID.

## Production Precheck 3: Check Owners Exist In Auth

Run this in the production Supabase SQL editor only after approval for
production read-only prechecks.

Every `bad_rows` value must be `0`.

Only run this after Precheck 1 confirms both `trade_candidates` and `trade_log`
exist. If either table is missing, stop and decide separately whether to run
`004a`.

```sql
SELECT 'user_configs_orphan_auth_user' AS check_name, count(*) AS bad_rows
FROM user_configs uc
LEFT JOIN auth.users au ON au.id = uc.user_id::uuid
WHERE au.id IS NULL

UNION ALL
SELECT 'scan_results_orphan_auth_user' AS check_name, count(*) AS bad_rows
FROM scan_results sr
LEFT JOIN auth.users au ON au.id = sr.user_id::uuid
WHERE au.id IS NULL

UNION ALL
SELECT 'subscriptions_orphan_auth_user' AS check_name, count(*) AS bad_rows
FROM subscriptions s
LEFT JOIN auth.users au ON au.id = s.user_id::uuid
WHERE au.id IS NULL

UNION ALL
SELECT 'trade_candidates_orphan_auth_user' AS check_name, count(*) AS bad_rows
FROM trade_candidates tc
LEFT JOIN auth.users au ON au.id = tc.user_id::uuid
WHERE au.id IS NULL

UNION ALL
SELECT 'trade_log_orphan_auth_user' AS check_name, count(*) AS bad_rows
FROM trade_log tl
LEFT JOIN auth.users au ON au.id = tl.user_id::uuid
WHERE au.id IS NULL;
```

Plain English: a value can look like a UUID but still not belong to any real
production account. This catches that case before the migration tries to add
foreign keys.

## Production Backup Requirement

Before running any production migration:

- confirm the latest known good production Supabase backup or restore point.
- know how to restore into a separate Supabase project first.
- record the current live frontend deployment identifier.
- record the current live backend deployment identifier.
- record the current live worker deployment identifier.

Plain English: frontend and backend rollbacks can be quick, but database
rollback is usually not instant. Treat this as controlled recovery work, not a
one-click undo.

## Migration Order

Only after all required approvals:

1. Run `migrations/004a_create_trade_workflow_tables.sql` in production only if
   `trade_candidates` or `trade_log` is missing.
2. Run `migrations/005_harden_user_isolation.sql` in production.
3. Do not run `006` as part of this action.

If a SQL error appears before the transaction commits, stop and copy the error
message for review. Do not keep editing and rerunning pieces randomly.

## Post-Migration Checks

After production migration `005`, verify:

- Backend health returns `"supabase_connected": true`.
- Production app login still works.
- Account page loads for a signed-in user.
- Scan page loads for a signed-in user.
- Candidate list loads and only shows that user's candidates.
- Portfolio page loads and only shows that user's trades.
- A second production test user cannot see the first test user's data.
- Direct anonymous/browser database access does not return other users' rows.
- Backend and worker logs do not show a new spike in Supabase permission errors.

Plain English: the main thing we are proving is simple: each signed-in user can
see their own data, and no one else's.

## Rollback And Incident Notes

If the app breaks after the migration:

1. Stop follow-up deploys and schema changes.
2. Check whether backend and worker production env vars are correct.
3. If the issue is API-only, consider Railway backend rollback first.
4. If the issue is worker writes, stop or roll back the worker first.
5. If the issue is database/auth state, follow `ROLLBACK_SOP.md`.
6. Restore Supabase into a separate project first; do not casually overwrite
   the live project.

Report the outcome honestly as one of:

- stopped before production change
- production prechecks passed
- production prechecks failed
- migration applied and verified
- migration applied with partial verification
- rolled back or recovery in progress

## Current Known Status

- `004a` and `005` were applied successfully to shadow Supabase on 2026-05-10.
- Manual two-user shadow browser test passed on 2026-05-10.
- Automated local regression tests cover user-scoped scan, candidate,
  portfolio, and config paths.
- Production Supabase already had `trade_candidates` and `trade_log`, so `004a`
  was not applied to production.
- Production migration `005` was applied successfully on 2026-05-11 after:
  - approved cleanup of old/test NULL-owner `trade_candidates` rows
  - production precheck 2 returned all zero bad rows
  - production precheck 3 returned all zero bad rows
  - Supabase daily backup was visible at 2026-05-11 06:35:02 UTC
  - Railway backend env was updated and backend health returned
    `"supabase_connected": true`
- Post-migration smoke check passed on 2026-05-11:
  - production backend health OK
  - live app pages loaded
- Remaining follow-up: before migration `005`, the live web Scan page created
  10 NULL-owner `trade_candidates` rows. After `005`, ownerless candidate writes
  should be rejected, but the Scan page candidate persistence path still needs
  controlled verification before another production scan is used as a test.
- Follow-up completed on 2026-05-15: one controlled production Scan page test
  passed after backend fix `2bca174`; production `scan_results` saved with a
  real user and read-only SQL checks showed no ownerless `trade_candidates`.

## Candidate Promotion Package After Shadow Review

This section is for the next possible production package. It is preparation
only, not approval to deploy or run SQL.

### Included Local Changes

- Backend service-role support already pushed in commit `2bca174`.
- Legacy scanner/Telegram candidate workflow requires
  `OPTIONBOT_OWNER_USER_ID` before writing or reading workflow rows.
- Candidate confirmation writes the portfolio row before marking a candidate
  `placed`, with cleanup if final status update fails.
- Frontend session/account improvements are present locally.
- Route/documentation drift cleanup is complete.
- Frontend shadow review flow is stable through `npm run shadow:check`.
- Portfolio/live-data cleanup is complete locally:
  - active portfolio API is `/candidates/portfolio`
  - retired legacy `backend/routers/portfolio.py`
  - active live-data/P&L behavior has regression coverage
  - close-trade flow validates non-negative exit price and only closes open trades
- Optional schema migration under review:
  `migrations/006_add_mr_timing_confirmation.sql`.

### Local/Shadow Status

- User reported the active portfolio browser review passed.
- Local verification on 2026-05-15:
  - `python3 -B -m pytest -q -p no:cacheprovider tools/test_greeks.py tools/test_regressions.py`
    passed: 28 tests
  - `python3 -B -c "import backend.app; print('backend import ok')"` passed
  - `cd frontend && npm run shadow:check` passed
- Migration `006` code/schema alignment checked locally:
  - config model, backend config API, Supabase config persistence, frontend
    controls, and regression tests all reference the same three fields.

### Recommended Release Split

Use two production gates:

1. Code/docs deployment package.
   - Backend/API changes.
   - Frontend changes.
   - Documentation/handoff updates.
   - No production schema change.
2. Migration `006` package.
   - Additive Supabase `user_configs` schema change.
   - Run only after separate shadow SQL review and separate production approval.

Plain English: the code can be promoted independently because it mostly improves
guards and review reliability. Migration `006` should stay separate because
database rollback is slower than frontend/backend rollback.

### Production Precheck For Migration 006

Only after explicit approval for read-only production prechecks, run:

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

Stop if `user_configs` is blank. If all three `has_*` values are already true,
production may already have the columns and `006` should be treated as
idempotent/no-op after confirmation.

After applying `006` with separate approval, run:

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

All values should be `0`.

Production read-only result on 2026-05-16:

- User ran the column-existence SQL in production Supabase project
  `eaphmnbbsfvuxzbmsmos`.
- `user_configs` existed.
- `mr_timing_confirmation`, `mr_timing_sma_period`, and
  `mr_timing_unconfirmed_cap` already existed.
- User ran the validation-count SQL and reported all values were `0`.

Conclusion: do not run migration `006` for this promotion. Treat it as already
applied / no-op unless a later schema check contradicts this.

### Required Approval Gates For Next Production Work

1. Approval to prepare a backup and rollback record.
2. Approval for read-only production prechecks.
3. Approval to deploy the code package.
4. Separate approval to run migration `006`, if still needed after prechecks.
5. Approval for any controlled production smoke test that writes data.

Approval for one gate does not approve the next gate.

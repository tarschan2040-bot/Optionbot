# AI Task Queue

Use this when the user says "continue development" without naming a specific
task. Do not start change-making work without approval.

## Recently Completed

- 2026-05-10: Rechecked local shadow verification. `npm run lint`,
  `./node_modules/.bin/tsc --noEmit`, Python regressions, and backend import all
  passed. No dependency install was required.
- 2026-05-10: Strengthened migration `005` preflight so it catches rows whose
  `user_id` looks like a UUID but does not belong to a real Supabase auth user.
  Updated `SHADOW_REVIEW.md` with plain-English review notes and copy/paste SQL
  checks. Production remains untouched.
- 2026-05-10: Confirmed shadow Supabase was missing `trade_candidates` and
  `trade_log`; added local migration `004a_create_trade_workflow_tables.sql` to
  create those tables for shadow review.
- 2026-05-10: Applied migrations `004a` and `005` successfully to shadow
  Supabase. Read-only service-role checks returned HTTP 200 for all expected
  tables. Production remains untouched.
- 2026-05-10: Manual two-user shadow browser test passed. User B could not see
  User A's data, and User B's app views showed clean/empty account data.
- 2026-05-10: Added automated regression tests for user-scoped scan reads,
  candidate reads/writes, portfolio reads/writes, and config CRUD. Regression
  checks now report `25 passed`.
- 2026-05-11: Prepared `PRODUCTION_PROMOTION_CHECKLIST.md` for migrations
  `004a`/`005`, including production prechecks, backup/rollback notes, and
  approval gates. Production remains untouched.
- 2026-05-11: Production prechecks for migration `005` passed after approved
  cleanup of old/test NULL-owner `trade_candidates` rows. Production Supabase
  backup was visible at `2026-05-11 06:35:02 UTC`.
- 2026-05-11: Migration `005_harden_user_isolation.sql` was applied
  successfully to production. Backend health returned Supabase connected true,
  and live app pages loaded after migration.
- 2026-05-15: Pushed narrow backend fix `2bca174` to `main` so
  `SupabaseClient` prefers `SUPABASE_SERVICE_ROLE_KEY` when present. Production
  backend health stayed OK afterward with Supabase connected true.
- 2026-05-15: Completed one controlled production Scan page verification after
  backend fix `2bca174`. The live Scan completed, results displayed, production
  `scan_results` saved with a real user, and read-only SQL checks showed no
  ownerless `trade_candidates`.
- 2026-05-15: Cleaned up route/documentation drift locally. Added
  `docs/API_ROUTES.md` as the mounted FastAPI route inventory, updated current
  state/context docs, and clarified that `/auth/*`, `/stripe/*`, and legacy
  `/portfolio/*` backend paths are not mounted today.
- 2026-05-15: Stabilized the frontend shadow review flow locally. Removed the
  network-dependent root Google font import, made `npm run build` use
  `next build --webpack`, added `npm run shadow:check`, and verified it passed.
- 2026-05-15: Completed local portfolio/live-data cleanup. Retired the
  unmounted legacy `backend/routers/portfolio.py` to an empty guardrail router,
  added active `/candidates/portfolio` live-data/P&L regression coverage,
  hardened close-trade exit-price validation, and verified Python/frontend
  checks passed.
- 2026-05-15: User reported active portfolio browser review passed. Prepared
  the next promotion package in docs only: `SHADOW_REVIEW.md` now includes
  migration `006` shadow SQL checks, and `PRODUCTION_PROMOTION_CHECKLIST.md`
  separates code/docs deployment from optional migration `006` approval.
- 2026-05-16: Prepared backup and rollback record for the narrow code/docs
  promotion package:
  `backups/optionbot_backup_20260516_125442.zip`,
  `backups/optionbot_backup_20260516_125442_changelog.md`, and
  `backups/optionbot_promotion_20260516_125442_rollback_record.md`.
- 2026-05-16: Production read-only precheck for migration `006` passed by
  user-run SQL. Production already has the three MR timing columns, and all
  null/range validation counts were zero. Do not run migration `006` for this
  promotion unless later checks disagree.

## Ready For Approval

1. Deploy narrow code/docs promotion package
   - Scope: deploy the reviewed backend/frontend/docs code package only.
   - Production impact: live code changes; no schema migration.
   - Requires separate explicit approval.

2. Controlled production smoke test
   - Scope: verify live pages and read paths after deployment. Any write test
     needs separate explicit approval.
   - Production impact: depends on approved smoke-test scope.

## Needs Product Decision

- Whether portfolio is active now or explicitly deferred.
- Whether the beta tier model remains all-users-Max until Stripe launches.
- Which billing tiers/prices should be treated as final.
- Whether landing-page education work is still the next conversion priority.

## Not Approved By Default

- Applying migration `004a` or `006` to production Supabase.
- Deploying frontend, backend, worker, auth, or database changes.
- Restarting or modifying the live bot process.
- Touching production secrets or live user data.
- Running a production scan as a test after migration `005`.
- Broad refactors that mix legacy single-user bot behavior with SaaS behavior.

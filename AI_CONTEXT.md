# AI Context

Last updated: 2026-05-17 23:55 Europe/London

This is the compact startup context for future AI sessions. Read this after
`AGENTS.md`; open deeper docs only when the task needs them.

## Current Truth

- Core product is still the Python options scanner plus Telegram-controlled bot.
- `scheduler.py` is the live scanner/bot entry point.
- Dry-run scanner path works through `python scheduler.py --once --no-telegram --dry-run`.
- SaaS layer exists around the scanner:
  - FastAPI backend in `backend/`
  - Next.js frontend in `frontend/`
  - Supabase migrations in `migrations/`
- Live frontend is `https://app.optionbot.org`.
- Signup email is routed through Resend/custom SMTP and the token-hash
  `/auth/confirm` flow.
- Candidate and portfolio isolation is wired in active web routes and migration
  `004_add_user_scoping_to_trade_workflow.sql`.
- Production deployment and production database changes still require separate
  explicit approval after shadow review.
- Production migration `005_harden_user_isolation.sql` was applied successfully
  on 2026-05-11 after production prechecks, backup confirmation, and explicit
  approval.

## Pending Local Work

- `migrations/005_harden_user_isolation.sql`
  - replaces permissive Phase 0 RLS with owner-scoped policies
  - converts ownership columns to UUID auth-user FKs
  - now preflights valid-looking UUIDs that do not exist in `auth.users`
  - applied successfully to shadow Supabase on 2026-05-10
  - applied successfully to production Supabase on 2026-05-11
- `migrations/004a_create_trade_workflow_tables.sql`
  - creates missing `trade_candidates` and `trade_log` tables for shadow review
  - needed if a shadow Supabase project only has the early SaaS tables
  - not applied to production Supabase
  - applied successfully to shadow Supabase on 2026-05-10
- Manual two-user shadow browser test passed on 2026-05-10:
  - User B could not see User A's scan/candidate/portfolio data
  - User B showed empty/clean account data
- Automated regression tests now cover user-scoped scan reads, candidate reads
  and writes, portfolio reads and writes, and config CRUD.
- `PRODUCTION_PROMOTION_CHECKLIST.md` now records the production promotion
  steps, precheck SQL, backup/rollback notes, and approval gates for migrations
  `004a` and `005`.
- Production precheck notes from 2026-05-11:
  - production already had `trade_candidates` and `trade_log`, so `004a` was
    not applied to production
  - 150 old/test `trade_candidates` rows with NULL `user_id` were deleted with
    user approval before migration
  - a live web Scan page run created 10 new NULL-owner candidate rows before
    migration; those 10 rows were deleted with user approval
  - precheck 2 and precheck 3 then returned all zero bad rows
  - Supabase daily backup was visible: 2026-05-11 06:35:02 UTC, Physical
  - Railway backend health after env update and after migration returned
    `supabase_connected: true`
  - live app pages loaded after migration
- `migrations/006_add_mr_timing_confirmation.sql`
  - adds mean-reversion timing confirmation config fields
  - production read-only precheck on 2026-05-16 showed these columns already
    exist and values are valid, so do not run it for the next promotion
- Backend/worker code supports `SUPABASE_SERVICE_ROLE_KEY`.
- Production backend service-role fix was pushed to `main` on 2026-05-15:
  commit `2bca174` (`Use service role key for Supabase backend`). The backend
  health endpoint stayed OK afterward with `supabase_connected: true`.
- One controlled production Scan page test passed on 2026-05-15 after backend
  fix `2bca174`: live Scan completed, results displayed, the latest
  `scan_results` row had a real `user_id`, and read-only production SQL checks
  confirmed no ownerless `trade_candidates` rows were created.
- Legacy Telegram/scanner candidate workflow requires `OPTIONBOT_OWNER_USER_ID`
  before writing/reading workflow rows.
- Mean-reversion scoring treats missing MR data as neutral.
- Candidate confirmation writes the portfolio row before marking candidate
  `placed`, with cleanup if the final status update fails.
- Frontend auth/session/account updates are present locally.
- Route/documentation drift cleanup was completed locally on 2026-05-15:
  - `docs/API_ROUTES.md` lists the mounted FastAPI surface from `backend/app.py`
  - mounted API is root health/account, `/config`, `/scan`, and `/candidates`
  - older `/portfolio/*`, `/auth/*`, and `/stripe/*` backend paths are documented
    as unmounted legacy/planned routes
- Frontend shadow review was stabilized locally on 2026-05-15:
  - `frontend/src/app/layout.tsx` no longer imports network-dependent Google fonts
  - `npm run build` uses `next build --webpack` to avoid local Turbopack helper-port failures
  - `npm run shadow:check` runs typecheck, lint, and build
- Portfolio/live-data cleanup was completed locally on 2026-05-15:
  - active portfolio API remains `/candidates/portfolio`
  - unmounted `backend/routers/portfolio.py` was retired to an empty guardrail router
  - regression coverage verifies active portfolio live-data/P&L response behavior
  - close-trade flow now rejects invalid/negative exit prices before changing P&L
- User reported the local/shadow portfolio browser review was OK.
- Local safety fixes and migration `006` were reviewed as a promotion package:
  - local checks passed again on 2026-05-15
  - `SHADOW_REVIEW.md` now has a migration `006` shadow rule
  - `PRODUCTION_PROMOTION_CHECKLIST.md` now separates code deploy approval from
    optional migration `006` approval
- Backup and rollback record for the narrow code/docs promotion package were
  prepared on 2026-05-16:
  - `backups/optionbot_backup_20260516_125442.zip`
  - `backups/optionbot_backup_20260516_125442_changelog.md`
  - `backups/optionbot_promotion_20260516_125442_rollback_record.md`
- Production read-only migration `006` prechecks passed by user-run SQL on
  2026-05-16:
  - production already has the three MR timing columns
  - validation counts were all zero
  - do not run migration `006` for this promotion unless a later check disagrees
- `tools/test_regressions.py` exists for recent isolation/MR/workflow coverage,
  including the manual web Scan write path.
- Local public-launch UX batch was built on 2026-05-17 but is not deployed:
  - login/signup modal, Google OAuth entry, expanded signup fields, required
    Terms of Service acceptance, `/terms-of-service`
  - landing-page market update signup and floating Contact Us modal
  - backend `/public/newsletter` and `/public/contact` routes
  - migration `007_create_public_lead_tables.sql` for
    `newsletter_subscribers` and `contact_messages`
  - frontend `npm run shadow:check` and backend import passed
  - production remains untouched; apply migration `007` only after shadow review
    and separate production approval
- Local landing-page conversion cleanup was built on 2026-05-17 but is not
  deployed:
  - AAPL/product preview moved directly after the hero
  - visible strategy cards reduced to three beginner-relevant examples
  - strategy headings are plain-English first, technical names second
  - visible landing wording avoids bullish/bearish/neutral jargon
  - visible pricing, testimonials/social proof, future-pacing, and FAQ sections
    added
  - frontend `npm run shadow:check` and backend import passed
  - production remains untouched

## Known Issues

- The earlier post-`005` live Scan risk has been checked: one controlled
  production Scan test passed on 2026-05-15 and did not create ownerless
  `trade_candidates`.
- `backend/routers/portfolio.py` is retired and not mounted. Current mounted
  routes are listed in `docs/API_ROUTES.md`.
- Billing/Stripe is implemented in code but not yet fully activated in
  production operations; beta mode currently grants Max tier.
- Stripe Billing code now exists locally for production promotion:
  `/billing/plans`, `/billing/checkout`, `/billing/portal`, and
  `/billing/webhook`. Keep `OPTIONBOT_BETA_ALL_MAX=true` for the first live
  billing deploy until live Stripe products/prices, webhook signing, and
  subscription sync are verified.
- `SAAS_MASTER_PLAN.md` and `KEN_MASTER_HANDOFF.md` are useful history but are
  not fully up to date with live auth/domain/SMTP milestones. The master plan's
  API section now distinguishes current mounted routes from planned routes.
- Full public-launch package was integrated locally on 2026-05-17:
  landing-page conversion rewrite, login/signup modal, Terms page, newsletter
  and Contact Us capture, public lead endpoints, Stripe billing routes/UI, and
  portfolio open/closed/detail/roll/chart upgrades.
- Verification on 2026-05-17:
  - backend import passed
  - `tools/test_greeks.py`, `tools/test_regressions.py`, and
    `tools/test_billing.py` passed: `36 passed`
  - frontend `npm run shadow:check` passed
- Production still needs operational follow-through after code deploy:
  - apply `migrations/007_create_public_lead_tables.sql` before relying on live
    newsletter/contact persistence
  - configure live Stripe env vars and `/billing/webhook`
  - leave `OPTIONBOT_BETA_ALL_MAX=true` until billing is confirmed end to end

## Recommended Next Step

For a generic "continue development" request:

1. Check `AI_TASK_QUEUE.md`.
2. Prefer the first `Ready For Approval` item unless the user names a task.
3. Ask approval for the narrow scope before changing files.
4. Keep production untouched unless separately approved.

The safest immediate continuation is to ask for separate approval before any
production read-only prechecks. Do not deploy or run migration `006` without a
later explicit approval for that exact action.

## Verification Commands

Run from repo root unless noted:

```bash
python3 -B -m pytest -q -p no:cacheprovider tools/test_greeks.py tools/test_regressions.py
python3 -B -c "import backend.app; print('backend import ok')"
```

Run from `frontend/`:

```bash
npm run shadow:check
```

## Last Read-Only Check

On 2026-05-15 at 17:25 Europe/London:

- Python regression checks: `26 passed`
- backend import: passed

On 2026-05-15 at 23:10 Europe/London:

- frontend `npm run shadow:check`: passed

On 2026-05-15 at 23:15 Europe/London:

- Python regression checks: `28 passed`
- backend import: passed
- frontend `npm run shadow:check`: passed

On 2026-05-15 at 23:21 Europe/London:

- Python regression checks: `28 passed`
- backend import: passed
- frontend `npm run shadow:check`: passed

On 2026-05-10 at 21:22 Europe/London:

- Python regression checks: `25 passed`
- backend import: passed
- shadow Supabase service-role table access: passed for `user_configs`,
  `scan_results`, `subscriptions`, `trade_candidates`, and `trade_log`

## Do Not Assume

- SaaS is production-ready for broad public traffic.
- Portfolio live-data math is fully correct.
- Billing or feature gating is complete.
- Production Supabase needs migration `006` to be run; read-only precheck says
  the three columns already exist and values are valid.
- Historical docs describe current deployment exactly.

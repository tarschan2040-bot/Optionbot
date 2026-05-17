# Current State

Read `AGENTS.md` and `CURRENT_STATE.md` first; no code changes without my approval.

Last updated: 2026-05-17 23:55 Europe/London

## AI Startup Note

Future AI sessions should use the compact startup packet first:

- `AGENTS.md`
- `AI_CONTEXT.md`
- `AI_TASK_QUEUE.md` when the user says "continue development"
- `PROJECT_MAP.md` for file lookup

This file remains the fuller current-state record and should be opened when the
compact context is not enough.

This is the concise operational snapshot for new AI agents. It should describe reality, not aspiration.

## Product Direction

- Core product remains a Python options scanner and Telegram-controlled bot.
- SaaS direction is web-first, with FastAPI backend and Next.js frontend layered around the scanner.
- Telegram should be treated as an operator channel and possible premium notification channel, not the only future interface.

## What Exists and Works

- `scheduler.py` runs the scanner and Telegram bot.
- Dry-run path works through `python scheduler.py --once --no-telegram --dry-run`.
- Core scanner tests pass: `python3 -m pytest -q` was green during the latest review.
- The scanner core, scoring pipeline, and existing Telegram workflow are in usable shape.
- SaaS scaffolding exists:
  - `backend/` FastAPI app
  - `frontend/` Next.js app
  - `migrations/` for SaaS-related tables
  - `user_configs` and scan result concepts are present
- Frontend app is live on `https://app.optionbot.org`.
- Custom SMTP is configured through Resend using `mail.optionbot.org`.
- Signup email delivery is working again after replacing the default Supabase sender.
- Signup confirmation no longer relies on the fragile PKCE email flow:
  - frontend uses a server-side `/auth/confirm` route
  - Supabase confirm-signup template should use `token_hash`
  - users are redirected into `/portfolio` after successful confirmation
- Multi-user candidate and portfolio isolation is now wired in code and database:
  - migration `004_add_user_scoping_to_trade_workflow.sql` exists
  - migration `005_harden_user_isolation.sql` is applied in production
  - `trade_candidates` and `trade_log` are user-scoped in active web routes
  - legacy owner rows were backfilled to the owner UUID during live setup
- Scan page and parameters page are working again on the custom domain after:
  - backend CORS was updated for `https://app.optionbot.org`
  - parameter page got explicit loading/error states
- Backup process is now documented in `BACKUP_PROCESS.md`.

## Implemented but Incomplete

- Multi-user configuration layer exists and is active for `user_configs` and scan results.
- Candidate workflow API exists in `backend/routers/candidates.py` and is user-scoped.
- Scan/config API routes exist and are working on the live domain.
- Backend route inventory is now documented in `docs/API_ROUTES.md`.
- Frontend dashboard shell exists and basic auth flow is working end to end.
- Domain, auth, and SMTP wiring are now far more production-shaped than before.

## Production Status After Migration 005

- Production Supabase daily backup was visible before migration:
  2026-05-11 06:35:02 UTC, Physical.
- Production already had `trade_candidates` and `trade_log`, so migration
  `004a_create_trade_workflow_tables.sql` was not applied to production.
- Old/test `trade_candidates` rows with missing `user_id` were deleted with user
  approval before migration:
  - first cleanup: 150 rows
  - second cleanup: 10 rows created by a live web Scan page run before migration
- Production precheck 2 returned all zero bad rows after cleanup.
- Production precheck 3 returned all zero bad rows after cleanup.
- Migration `005_harden_user_isolation.sql` was applied successfully to
  production on 2026-05-11.
- Production backend health returned `supabase_connected: true` after migration.
- User confirmed live app pages loaded after migration.

Plain English: the production database is now stricter. Rows in the checked
tables must belong to real Supabase Auth users.

Follow-up completed: one controlled production Scan page test passed on
2026-05-15 after the backend service-role fix. The live Scan completed, results
displayed, `scan_results` saved with a real `user_id`, and read-only production
SQL checks confirmed no ownerless `trade_candidates` rows were created.

## Production Backend Fix After Migration 005

- On 2026-05-15, a narrow backend fix was pushed to `main`:
  commit `2bca174` (`Use service role key for Supabase backend`).
- The fix makes `data/supabase_client.py` prefer `SUPABASE_SERVICE_ROLE_KEY`
  when it exists, falling back to `SUPABASE_KEY` for older/dev setups.
- A focused test was added in `tools/test_supabase_service_key.py`.
- Verification before push:
  - `python3 -B -m pytest -q -p no:cacheprovider tools/test_greeks.py tools/test_supabase_service_key.py`
    passed: 17 tests
  - `python3 -B -c "import backend.app; print('backend import ok')"` passed
- Post-push production health checks returned `supabase_connected: true`.

Plain English: the live backend should now be able to write through the
post-`005` Supabase security rules, as long as Railway has
`SUPABASE_SERVICE_ROLE_KEY` configured.

The controlled production Scan page test was completed with separate approval.
Plain English: the live web Scan button, backend write path, and post-`005`
database ownership rules are working together for this path.

## Local Changes Pending Shadow Review

- Backend/worker code now supports `SUPABASE_SERVICE_ROLE_KEY`.
- Legacy Telegram/scanner candidate workflow now requires `OPTIONBOT_OWNER_USER_ID` before writing or reading workflow rows.
- Mean-reversion scoring now treats unavailable MR data as neutral instead of zero.
- Mean-reversion scoring now has local/shadow timing confirmation settings:
  - default `mr_timing_confirmation=true`
  - raw MR setup can be capped by `mr_timing_unconfirmed_cap` until the MR score cools relative to its short SMA
  - production read-only precheck on 2026-05-16 showed the migration `006`
    columns already exist and values are valid, so do not run it for the next promotion
- Candidate confirmation now writes the portfolio row before marking the candidate as placed, with rollback cleanup if the final status update fails.
- Frontend session handling now listens for Supabase auth state changes, and the account page reads tier info from `/me`.
- Route/documentation drift cleanup is done locally:
  - `backend/app.py` mounts `health`, `public`, `config`, `scan`,
    `candidates`, and `billing`
  - current mounted endpoints are listed in `docs/API_ROUTES.md`
  - older `/auth/*`, `/stripe/*`, and legacy `/portfolio/*` backend paths are
    marked as planned or legacy, not active mounted routes
- Frontend shadow review flow is stable locally:
  - Google-hosted `next/font` dependency was removed from the root layout
  - `npm run build` uses `next build --webpack` for restricted local review
  - `npm run shadow:check` passed on 2026-05-15
- Portfolio/live-data cleanup is done locally:
  - active portfolio route remains `/candidates/portfolio`
  - legacy unmounted `backend/routers/portfolio.py` is retired to an empty guardrail router
  - active portfolio live-data/P&L response behavior is covered in regression tests
  - close-trade flow now requires a valid non-negative exit price and only closes open trades
- User reported the active portfolio browser review passed.
- Next production package has been prepared in docs only:
  - code/docs deployment package is separate from migration `006`
  - migration `006` has shadow/prod precheck SQL documented
  - no production deploy, migration, precheck, or smoke test has been run from this step
- Backup and rollback record for narrow code/docs promotion were prepared:
  - `backups/optionbot_backup_20260516_125442.zip`
  - `backups/optionbot_backup_20260516_125442_changelog.md`
  - `backups/optionbot_promotion_20260516_125442_rollback_record.md`
- Production migration `006` precheck was completed by user-run SQL:
  - production `user_configs` already has all three MR timing columns
  - null/range validation counts were all zero
  - migration `006` should not be run as part of the next promotion unless a
    later schema check contradicts this
- Full public-launch package was integrated locally on 2026-05-17 for production
  promotion after user approval:
  - landing-page conversion cleanup with AAPL/product preview, clearer CTAs,
    three beginner strategy cards, visible pricing, testimonials, future-pacing,
    and FAQ
  - login/signup modal with Google OAuth entry and required Terms acceptance
  - `/terms-of-service`
  - newsletter subscription and floating Contact Us capture
  - backend `/public/newsletter` and `/public/contact`
  - migration `007_create_public_lead_tables.sql`
  - Stripe Billing routes/UI/tests under `/billing/*`
  - portfolio open/closed/detail/roll/chart upgrades
- Verification on 2026-05-17:
  - backend import passed
  - `tools/test_greeks.py`, `tools/test_regressions.py`, and
    `tools/test_billing.py` passed: `36 passed`
  - frontend `npm run shadow:check` passed

## Known Issues From Latest Review

1. Stripe/billing is implemented in code but still needs production operations.
   - Live Stripe products/prices, Railway env vars, and the production webhook
     must be configured and smoke-tested before turning beta access off.
   - Keep `OPTIONBOT_BETA_ALL_MAX=true` for the first billing deploy.

2. Historical documentation drift still exists.
   - `KEN_MASTER_HANDOFF.md` reflects an older single-user / Netlify-dashboard era.
   - `SAAS_MASTER_PLAN.md` is directionally useful, but still contains roadmap/history beyond the current mounted API. Its API section now points to `docs/API_ROUTES.md` for current route truth.

## What Is Not Yet Safe To Assume

- That the SaaS layer is fully production-ready for broad public traffic
- That every portfolio endpoint and portfolio math path is correct
- That billing enforcement is active; the code exists, but beta mode should
  remain on until live Stripe is verified
- That planned API surfaces beyond `docs/API_ROUTES.md` are mounted and complete
- That older historical docs still describe the current deployed system accurately

## Current Development Guardrail

Any new AI agent should treat this repository as:

- safe for read-only analysis without approval
- not safe for code changes without explicit approval

Before making changes, read `AGENTS.md` and ask the user for approval.

## Recommended Next Priorities

1. Improve the landing page around strategy education and conversion
   - goal-first chooser
   - beginner-friendly strategy explanations
   - stronger path from learning to scanner usage
2. Add more regression tests for:
   - cross-user candidate isolation
   - cross-user portfolio isolation
   - signup confirmation route
3. Ask separately before deploying the code/docs package or running any
   controlled production smoke test that writes data

## Latest Milestones

- Custom domain live: `app.optionbot.org`
- Resend SMTP live through `mail.optionbot.org`
- Supabase confirm-signup flow updated away from localhost
- `/auth/confirm` route added for robust email confirmation
- New signups now receive email and create clean empty accounts
- User-specific candidates and portfolio data no longer leak into brand-new accounts
- Scan and parameters pages are working on the live custom domain
- Production migration `005_harden_user_isolation.sql` applied successfully
- Production backend health and live app page smoke checks passed after `005`
- Controlled production Scan page verification passed after backend fix `2bca174`

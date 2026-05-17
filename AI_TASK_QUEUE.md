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
- 2026-05-17: Built the first public-launch UX batch locally, excluding the
  broader landing-page layout/conversion rewrite. Added login/signup modal with
  Google OAuth entry, expanded email signup fields, required Terms of Service
  acceptance, `/terms-of-service`, landing-page market update signup, floating
  Contact Us modal, public lead-capture backend routes, and migration `007` for
  `newsletter_subscribers` and `contact_messages`. Frontend `npm run
  shadow:check` and backend import passed. Production remains untouched.
- 2026-05-17: Built the landing-page conversion cleanup locally in shadow mode.
  Kept the hero concept and guided input, moved the AAPL/product example
  directly after the hero, reduced visible strategy cards to three
  beginner-relevant examples, changed strategy headings to plain-English titles
  with technical names as subtitles, replaced bullish/bearish/neutral wording in
  the visible landing flow, added product preview, visible pricing, testimonials,
  future-pacing, and FAQ sections, and rewrote visible CTAs to clearer outcomes.
  Frontend `npm run shadow:check` and backend import passed. Production remains
  untouched.
- 2026-05-17: Integrated the full public-launch production package after user
  approval to deploy: landing-page conversion cleanup, public login/signup modal
  work, Terms page, newsletter/contact capture, Stripe billing routes/UI/tests,
  and portfolio open/closed/detail/roll/chart upgrades. Verification passed:
  backend import, Python greeks/regression/billing tests (`36 passed`), and
  frontend `npm run shadow:check`.

## Ready For Approval

1. Deploy narrow code/docs promotion package
   - Scope: deploy the reviewed backend/frontend/docs code package only.
   - Production impact: live code changes; no schema migration.
   - Requires separate explicit approval.

2. Controlled production smoke test
   - Scope: verify live pages and read paths after deployment. Any write test
     needs separate explicit approval.
   - Production impact: depends on approved smoke-test scope.

## Pending Production Operations

These items may be outside the Git code push and should be checked after the
live deployment:

- Apply `migrations/007_create_public_lead_tables.sql` to production Supabase
  before relying on live newsletter/contact persistence.
- Configure live Stripe env vars in Railway:
  `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
  `STRIPE_PRICE_PRO_MONTHLY`, `STRIPE_PRICE_PRO_ANNUAL`,
  `STRIPE_PRICE_MAX_MONTHLY`, and `STRIPE_PRICE_MAX_ANNUAL`.
- Configure the live Stripe webhook to call the production backend
  `/billing/webhook`.
- Keep `OPTIONBOT_BETA_ALL_MAX=true` for the first production billing deploy.
- Run live smoke checks for homepage, login/signup modal, authenticated
  portfolio, scan page, public lead forms, and billing plan display.

## Public Launch Package In Current Deployment

### Included In The Production Push

- Stripe billing package:
  - backend `/billing/plans`, `/billing/checkout`, `/billing/portal`, and
    `/billing/webhook` routes
  - Stripe Checkout, Customer Portal, and webhook subscription sync
  - account billing UI for plan selection, monthly/annual billing, and manage
    billing
  - billing docs, Stripe shadow notes, production promotion notes, and billing
    tests
  - keep `OPTIONBOT_BETA_ALL_MAX=true` for the first production billing deploy
- Portfolio upgrades:
  - Open Positions and Closed Positions tables
  - DTE sorting with closest expiry first
  - `Strategy` as the left-most table column
  - contract label format such as `TSLA JUN 18 '26 470 Call`
  - Delta column instead of IV
  - same-contract position count
  - expired positions remain in Open Positions and show `Expired` until user
    reviews them
  - position detail page with top summary box, position detail section, edit
    section, delete, close, expired-worthless, and roll actions
  - roll position page
  - option contract price chart using Yahoo when available, with previous chart
    fallback when Yahoo has no new data
  - Greeks/payoff chart with Greek selector
- Public-launch UX batch:
  - login/signup modal instead of sending landing-page visitors to a separate
    login page
  - Google OAuth entry point
  - signup fields for email, first name, last name, optional mobile number,
    password, and confirm password
  - required `I agree to the Terms of Service` checkbox for signup
  - `/terms-of-service` page with OptionBot-specific launch draft language
  - landing-page subscription capture for free market updates and opportunity
    alerts
  - Free plan benefit copy for market updates and opportunity alerts
  - floating bottom-right `Contact Us` button and contact form modal
  - backend `/public/newsletter` and `/public/contact` endpoints
  - migration `007_create_public_lead_tables.sql` for the new public lead
    tables
- Landing-page conversion cleanup:
  - AAPL/product example moved directly after the hero
  - visible landing-page strategy cards reduced to the three most practical
    beginner starts
  - plain-English strategy titles are primary, with technical names as smaller
    subtitles
  - visible landing flow uses beginner wording like `Stock going up`,
    `Stock going down`, and `Stock going sideways`
  - product preview table added for AAPL setups
  - pricing now shows `Free`, `Pro`, and `Max` with visible monthly numbers
  - testimonials/social proof, future-pacing, and FAQ sections added
  - visible CTAs now use clearer outcomes such as `Try free with AAPL`,
    `See free AAPL setups`, and `Start free - no card needed`

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

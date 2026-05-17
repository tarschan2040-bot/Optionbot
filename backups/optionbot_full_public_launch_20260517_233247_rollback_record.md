# OptionBot Full Public Launch Package Rollback Record

Prepared: 2026-05-17 23:55 Europe/London

## Scope

This release package combines:

- landing-page conversion update
- login/signup modal and Terms page
- public newsletter and Contact Us capture
- Stripe Billing routes and account plan UI
- portfolio open/closed/detail/roll/chart upgrades
- migration `007_create_public_lead_tables.sql`

## Pre-Deploy Backup

- `backups/optionbot_backup_20260517_233247.zip`
- `backups/optionbot_backup_20260517_233247_changelog.md`

## Verified Before Promotion

- Backend import passed.
- Python tests passed:
  `python3 -B -m pytest -q -p no:cacheprovider tools/test_greeks.py tools/test_regressions.py tools/test_billing.py`
- Frontend shadow check passed:
  `npm run shadow:check`

## Production Dependencies

- Apply `migrations/007_create_public_lead_tables.sql` before relying on live
  newsletter/contact persistence.
- Keep `OPTIONBOT_BETA_ALL_MAX=true` during the first billing deploy.
- Configure live Stripe env vars and webhook before asking users to complete
  checkout.

## First Rollback Actions

1. If frontend-only smoke checks fail, revert the Git deployment to the previous
   Vercel production deployment.
2. If backend API smoke checks fail, revert the Railway backend deployment to the
   prior successful deployment.
3. If migration `007` causes database issues, disable public lead form UI or
   revert the app deployment first; table drops should only happen after
   confirming no lead data must be preserved.
4. Keep `OPTIONBOT_BETA_ALL_MAX=true` if Stripe checkout or webhooks fail.

## Smoke Tests After Deploy

- Homepage loads on `https://app.optionbot.org`.
- Login/signup modal opens and closes.
- Terms of Service page loads.
- Authenticated Portfolio page loads.
- Authenticated Scan page loads.
- Public newsletter form submits after migration `007`.
- Contact Us form submits after migration `007`.
- Account plans page shows Free/Pro/Max and `beta_all_max=true`.

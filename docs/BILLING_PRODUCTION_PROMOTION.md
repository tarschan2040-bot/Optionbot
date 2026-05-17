# Billing Production Promotion Package

Last updated: 2026-05-16 22:05 Europe/London

This is the production promotion package for Stripe Billing. It is a checklist
and rollback plan, not a record that production was changed.

## Current Execution Status

2026-05-16 follow-up check:

- User approved going ahead with the first production billing setup gate.
- Stripe connector access was checked before creating resources.
- Connector account was `acct_1TXSSzCIrksxUPvd`, display name
  "Optionbot sandbox".
- Existing products/prices in that account matched the shadow/test billing
  resources.
- Live Stripe products/prices were not created from this connector because it
  is not connected to the intended production live Stripe account.

Plain English: the promotion can continue only from the real live Stripe
Dashboard/account or after this connector is connected to the live production
Stripe account. Do not treat the sandbox product IDs as production env values.

## Scope

Promote the existing billing implementation to production:

- backend routes mounted at `/billing/plans`, `/billing/checkout`,
  `/billing/portal`, and `/billing/webhook`
- frontend account/plans flows that open Stripe Checkout and Customer Portal
- live Stripe products and recurring Prices for Pro and Max
- signed production Stripe webhook delivery to the backend
- subscription state synced into Supabase `subscriptions`

Keep this out of scope for the first billing deploy:

- setting `OPTIONBOT_BETA_ALL_MAX=false`
- changing tier enforcement
- running database migrations
- changing production Supabase RLS or ownership rules
- touching the Telegram bot process or live scanner scheduler

## Safety Gate

`OPTIONBOT_BETA_ALL_MAX` must stay `true` for the first production billing
deploy.

Plain English: live Checkout and webhook sync can be introduced while all users
still receive Max access. Paid-tier enforcement is a later, separate production
approval after live billing sync is proven.

Stop if any of these are true:

- the Stripe Dashboard is not in the intended live account
- any live Stripe key or webhook secret would be exposed to frontend code
- the production backend URL for `/billing/webhook` is not known
- the latest deploy identifiers and rollback path have not been recorded
- `OPTIONBOT_BETA_ALL_MAX` is missing or false in production backend env
- the user has not explicitly approved the exact production action being run

## Backup And Rollback Notes

Prepared repo backup:

- `backups/optionbot_backup_20260516_220557.zip`
- `backups/optionbot_backup_20260516_220557_changelog.md`

Prepared rollback record:

- `backups/optionbot_billing_promotion_20260516_220557_rollback_record.md`

Before production execution, record:

- Vercel production deployment identifier before frontend promotion
- Railway backend deployment identifier before backend promotion
- Railway worker deployment identifier if worker env is touched
- latest visible production Supabase backup or restore point
- existing production values for billing-related env names, without copying
  secret values into docs or chat

Primary rollback path:

- keep or restore `OPTIONBOT_BETA_ALL_MAX=true`
- disable the new Stripe webhook endpoint if webhook retries are noisy
- roll back Railway backend if backend startup or `/billing/*` routes fail
- roll back Vercel frontend if the account/plans UI fails
- restore prior billing env values if keys, webhook secret, or Price IDs are
  wrong

No database migration is expected for this package.

## Live Stripe Products And Prices

Create these in Stripe live mode only after confirming the intended live Stripe
account.

| Product | Price label | Stripe recurring setup | Env var |
| --- | --- | --- | --- |
| OptionBot Pro | Pro monthly | USD 19.99, monthly | `STRIPE_PRICE_PRO_MONTHLY` |
| OptionBot Pro | Pro annual | USD 191.88, yearly | `STRIPE_PRICE_PRO_ANNUAL` |
| OptionBot Max | Max monthly | USD 49.99, monthly | `STRIPE_PRICE_MAX_MONTHLY` |
| OptionBot Max | Max annual | USD 479.88, yearly | `STRIPE_PRICE_MAX_ANNUAL` |

Notes:

- Annual display copy is currently "$15.99/month billed annually" for Pro and
  "$39.99/month billed annually" for Max, so the live Stripe annual Prices
  should use the yearly totals above unless the pricing decision changes.
- Use Prices, not legacy Plans.
- Do not reuse test-mode Price IDs in production env.
- If a Price is wrong, create a replacement Price and deactivate the wrong one
  after confirming it is unused.

## Production Env Checklist

Backend / Railway server-only env:

- `STRIPE_SECRET_KEY=sk_live_...`
- `STRIPE_WEBHOOK_SECRET=whsec_...`
- `STRIPE_API_VERSION=2026-02-25.clover`
- `STRIPE_PRICE_PRO_MONTHLY=price_live_...`
- `STRIPE_PRICE_PRO_ANNUAL=price_live_...`
- `STRIPE_PRICE_MAX_MONTHLY=price_live_...`
- `STRIPE_PRICE_MAX_ANNUAL=price_live_...`
- `OPTIONBOT_BETA_ALL_MAX=true`
- `FRONTEND_URL=https://app.optionbot.org`
- existing production `SUPABASE_URL`, `SUPABASE_KEY`,
  `SUPABASE_SERVICE_ROLE_KEY`, and `OPTIONBOT_OWNER_USER_ID` still present

Frontend / Vercel env:

- `NEXT_PUBLIC_API_URL` points to the production backend
- no `STRIPE_SECRET_KEY`
- no `STRIPE_WEBHOOK_SECRET`
- no live Supabase service-role key

Worker env:

- do not add Stripe env unless the worker imports billing code or the deployment
  platform requires shared env
- do not change the live bot process as part of this package

## Production Webhook Setup Plan

1. Deploy or confirm the production backend includes `backend.routers.billing`.
2. In Stripe live mode, create a webhook endpoint:
   `https://<production-backend-domain>/billing/webhook`.
3. Subscribe the endpoint to:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Copy the webhook signing secret into backend `STRIPE_WEBHOOK_SECRET`.
5. Restart or redeploy the backend only after explicit approval for that action.
6. Use Stripe Dashboard test delivery to confirm the endpoint returns 2xx.
7. Check backend logs for signature verification errors or ignored events.

For full sync verification, a controlled live Checkout is still needed because
sample webhook events may not contain an OptionBot `user_id`. Run that only
after separate approval for a live billing smoke test.

## Post-Deploy Checks With Beta Gate True

Run these after the production billing deploy:

- backend health still reports Supabase connected
- `GET /billing/plans` returns `stripe_configured: true`
- `GET /billing/plans` returns `beta_all_max: true`
- account/plans page loads for a signed-in user
- Checkout opens for Pro monthly
- Customer Portal opens after a Stripe customer exists
- Stripe webhook endpoint returns 2xx for Dashboard test delivery
- no new ownerless rows appear in user-owned Supabase tables
- backend logs do not show a spike in Stripe or Supabase errors

For the later controlled live Checkout smoke test:

- use a known production test account
- document the live subscription ID and customer ID privately
- verify the production `subscriptions` row syncs to the expected user
- verify `/me` still reports Max access because `OPTIONBOT_BETA_ALL_MAX=true`
- cancel/refund any live test subscription only after explicit approval

## Paid-Tier Enforcement Gate

Do not set:

```bash
OPTIONBOT_BETA_ALL_MAX=false
```

until all of these are true:

- production Checkout created a real subscription for the correct user
- production webhook sync updated `subscriptions`
- subscription update/cancel events were observed or safely simulated
- Customer Portal opened for that user
- rollback notes have been reviewed after the live billing test
- the user separately approved paid-tier enforcement activation

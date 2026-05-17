# OptionBot Stripe Billing

Last updated: 2026-05-16

This is the local implementation plan and operator checklist for Stripe Billing.
It is not a production activation record.

Production promotion prep lives in
`docs/BILLING_PRODUCTION_PROMOTION.md`.

## Integration Shape

- Use Stripe Billing subscriptions, not one-off PaymentIntents.
- Use hosted Stripe Checkout for upgrades and plan changes.
- Use hosted Stripe Customer Portal for payment method updates, cancellation,
  and self-service billing management.
- Sync subscription state into Supabase `subscriptions` from signed Stripe
  webhooks.
- Keep `OPTIONBOT_BETA_ALL_MAX=true` until the production webhook path and paid
  subscription sync are verified.

Primary Stripe references:

- https://docs.stripe.com/billing/subscriptions/designing-integration
- https://docs.stripe.com/payments/checkout
- https://docs.stripe.com/customer-management
- https://docs.stripe.com/webhooks

## Local Backend Routes

Mounted in `backend/app.py`:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/billing/plans` | Public plan metadata and config status |
| `POST` | `/billing/checkout` | Authenticated Checkout Session creation |
| `POST` | `/billing/portal` | Authenticated Customer Portal Session creation |
| `POST` | `/billing/webhook` | Signed Stripe webhook receiver |

## Required Environment Variables

Server-side:

```bash
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_API_VERSION=2026-02-25.clover
STRIPE_PRICE_PRO_MONTHLY=price_...
STRIPE_PRICE_PRO_ANNUAL=price_...
STRIPE_PRICE_MAX_MONTHLY=price_...
STRIPE_PRICE_MAX_ANNUAL=price_...
OPTIONBOT_BETA_ALL_MAX=true
FRONTEND_URL=https://app.optionbot.org
```

Frontend:

```bash
NEXT_PUBLIC_API_URL=https://your-backend.example.com
```

## Stripe Dashboard Setup

1. Create products:
   - OptionBot Pro
   - OptionBot Max
2. Create recurring Prices:
   - Pro monthly: `$19.99` per month
   - Pro annual: `$15.99` per month, billed annually
   - Max monthly: `$49.99` per month
   - Max annual: `$39.99` per month, billed annually
3. Copy Price IDs into the environment variables above.
4. Configure Customer Portal for subscription cancellation, payment method
   updates, and plan changes.
5. Add a webhook endpoint:
   - `https://YOUR_BACKEND_DOMAIN/billing/webhook`
6. Subscribe to these events:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
7. Copy the webhook signing secret into `STRIPE_WEBHOOK_SECRET`.

## Production Activation Gate

Do not turn on paid-tier enforcement until all of these are true:

- Checkout creates a Stripe subscription in test mode.
- Webhook writes/updates the Supabase `subscriptions` row for the same user.
- `/me` returns the paid tier after webhook sync.
- Customer Portal opens for that user.
- Cancel/update events move the user back to Free when appropriate.
- Read-only ownerless checks still return zero for user-owned tables.

After that, and only with separate production approval:

```bash
OPTIONBOT_BETA_ALL_MAX=false
```

No database migration is required for the initial implementation because the
current `subscriptions` table already has:

- `user_id`
- `stripe_customer_id`
- `stripe_subscription_id`
- `tier`
- `status`
- `current_period_end`

Future useful metadata, if desired later:

- `stripe_price_id`
- `billing_period`
- `cancel_at_period_end`
- `trial_end`

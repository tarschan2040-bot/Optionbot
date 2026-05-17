# Stripe Test-Mode Shadow Setup

Last updated: 2026-05-16

Connected Stripe account:

- Account: `acct_1TXSSzCIrksxUPvd`
- Display name: Optionbot sandbox
- Dashboard API keys: https://dashboard.stripe.com/acct_1TXSSzCIrksxUPvd/apikeys

All resources below were created in Stripe test mode (`livemode=false`).

Local Stripe CLI:

- Installed via Homebrew
- Verified version: `stripe version 1.40.9`
- Authenticated to Optionbot sandbox with test-mode key only

## Products

| Product | Stripe product ID |
| --- | --- |
| OptionBot Pro | `prod_UWqwxhzYeP6f52` |
| OptionBot Max | `prod_UWqwQuxiYhqPUy` |

## Prices

| Env var | Amount | Stripe price ID |
| --- | ---: | --- |
| `STRIPE_PRICE_PRO_MONTHLY` | `$19.99 / month` | `price_1TXnEZCIrksxUPvdgT4rGHQu` |
| `STRIPE_PRICE_PRO_ANNUAL` | `$191.88 / year` | `price_1TXnEdCIrksxUPvdm5Tg4SxS` |
| `STRIPE_PRICE_MAX_MONTHLY` | `$49.99 / month` | `price_1TXnEgCIrksxUPvdgSQhGnI4` |
| `STRIPE_PRICE_MAX_ANNUAL` | `$479.88 / year` | `price_1TXnEkCIrksxUPvd3WpP1bVf` |

## Local Shadow Env Template

Do not commit real secret values.

```bash
OPTIONBOT_BETA_ALL_MAX=true
STRIPE_SECRET_KEY=sk_test_REPLACE_ME
STRIPE_WEBHOOK_SECRET=whsec_REPLACE_ME
STRIPE_API_VERSION=2026-02-25.clover
STRIPE_PRICE_PRO_MONTHLY=price_1TXnEZCIrksxUPvdgT4rGHQu
STRIPE_PRICE_PRO_ANNUAL=price_1TXnEdCIrksxUPvdm5Tg4SxS
STRIPE_PRICE_MAX_MONTHLY=price_1TXnEgCIrksxUPvdgSQhGnI4
STRIPE_PRICE_MAX_ANNUAL=price_1TXnEkCIrksxUPvd3WpP1bVf
FRONTEND_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Remaining Shadow Test Steps

1. Add the test secret key locally as `STRIPE_SECRET_KEY`.
2. Start the local FastAPI backend.
3. Start the Stripe CLI webhook listener:

```bash
stripe listen --forward-to localhost:8000/billing/webhook
```

4. Copy the printed `whsec_...` value into `STRIPE_WEBHOOK_SECRET`.
5. Start the frontend locally.
6. Login with a test account and open `/account/plans`.
7. Click a paid plan and complete Checkout with Stripe test card `4242 4242 4242 4242`.
8. Confirm the webhook updates Supabase `subscriptions`.
9. Confirm `/me` returns the expected tier while `OPTIONBOT_BETA_ALL_MAX=true`.

Do not set `OPTIONBOT_BETA_ALL_MAX=false` until test and production webhook sync
are verified and separately approved.

## Shadow Test Result

Completed on 2026-05-16 against shadow Supabase project
`sysgzfualdunywahxico`.

Local stack:

- Frontend: `http://127.0.0.1:3001`
- Backend: `http://127.0.0.1:8001`
- Stripe listener: `localhost:8001/billing/webhook`
- Beta gate during browser test: `OPTIONBOT_BETA_ALL_MAX=true`

Result:

- Checkout opened successfully from `/account/plans`
- Stripe test subscription created:
  `sub_1TXpHKCIrksxUPvdYbyz2EO2`
- Initial webhook delivery exposed two local parser issues:
  - Stripe `metadata` can be a Stripe object rather than a plain dict
  - subscription period end can be present on the subscription item
- Both parser issues were fixed in `backend/routers/billing.py` and covered in
  `tools/test_billing.py`
- Shadow `subscriptions` row synced successfully:
  - `tier=pro`
  - `status=active`
  - Stripe customer ID present
  - Stripe subscription ID present
  - `current_period_end=2026-06-16T20:57:43+00:00`
- One-off tier lookup with `OPTIONBOT_BETA_ALL_MAX=false` returned `pro`

Verification:

```bash
python3 -B -m pytest -q -p no:cacheprovider tools/test_billing.py
```

Result: `5 passed`.

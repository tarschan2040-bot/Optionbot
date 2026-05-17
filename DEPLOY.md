# OptionBot SaaS — Deployment Guide

## Architecture

```
[Vercel] → frontend (Next.js)
              ↓ API calls
[Railway] → backend (FastAPI) + worker (background scans)
              ↓ DB queries
[Supabase] → PostgreSQL + Auth
```

## 1. Backend on Railway

1. Create a new project at https://railway.app
2. Connect your GitHub repo (or deploy from CLI)
3. Set the root directory to `/` (project root, not backend/)
4. Set start command: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
5. Add environment variables:
   - `SUPABASE_URL` = your Supabase URL
   - `SUPABASE_KEY` = your Supabase anon key
   - `SUPABASE_SERVICE_ROLE_KEY` = your Supabase service role key, server-only
   - `OPTIONBOT_OWNER_USER_ID` = Supabase `auth.users.id` UUID for legacy Telegram/scanner-owned workflow rows
   - `SUPABASE_JWT_SECRET` = (not needed for ES256 — auto-fetched from JWKS)
   - `FRONTEND_URL` = your Vercel domain (for CORS)

6. For the background worker, add a second service:
   - Start command: `python -m backend.worker`
   - Same env vars as above

Railway auto-installs from `requirements.txt`.

## 2. Frontend on Vercel

1. Create a new project at https://vercel.com
2. Connect your GitHub repo
3. Set the root directory to `frontend/`
4. Framework preset: Next.js (auto-detected)
5. Add environment variables:
   - `NEXT_PUBLIC_SUPABASE_URL` = your Supabase URL
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = your Supabase anon key
   - `NEXT_PUBLIC_API_URL` = your Railway backend URL (e.g. https://optionbot-api.up.railway.app)

## 3. Supabase

Already configured. Ensure these tables exist (run migrations in order):
- `migrations/001_create_user_configs.sql`
- `migrations/002_create_scan_results.sql`
- `migrations/003_create_subscriptions.sql`
- `migrations/004_add_user_scoping_to_trade_workflow.sql`
- `migrations/004a_create_trade_workflow_tables.sql` only if
  `trade_candidates` or `trade_log` is missing in the target project
- `migrations/005_harden_user_isolation.sql`
- `migrations/006_add_mr_timing_confirmation.sql` only if the target project
  does not already have the MR timing columns
- `migrations/007_create_public_lead_tables.sql` for landing-page newsletter
  signups and Contact Us messages

Auth URL configuration also matters for email confirmation and password reset flows:

- Set **Site URL** to your deployed frontend domain, not localhost
- Add your production callback URL to **Redirect URLs**
- Keep localhost callback URLs only for local development if needed

Recommended production redirect URL:

- `https://app.optionbot.org/auth/callback`

If the Vercel preview domain is still used for a controlled preview, keep that
preview callback separate from the production custom-domain callback.

Migration `005_harden_user_isolation.sql` replaces Phase 0 permissive RLS with
owner-scoped policies and converts `user_id` fields to UUID FKs. Run it in a
shadow Supabase project first. Do not apply it to production until:

- `SUPABASE_SERVICE_ROLE_KEY` is configured on backend and worker services
- legacy `trade_candidates` and `trade_log` rows have valid owner UUIDs
- any placeholder `user_id` values such as `owner` have been migrated
- the rollback/restore path is documented for the database layer

For the production promotion checklist and copy/paste precheck SQL, use
`PRODUCTION_PROMOTION_CHECKLIST.md`.

### Billing production variables

Billing code is deployed separately from billing enforcement. Keep
`OPTIONBOT_BETA_ALL_MAX=true` for the first production billing deploy so users
retain Max access while Stripe is verified.

Before turning on paid checkout, Railway must have:

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_PRO_MONTHLY`
- `STRIPE_PRICE_PRO_ANNUAL`
- `STRIPE_PRICE_MAX_MONTHLY`
- `STRIPE_PRICE_MAX_ANNUAL`
- `FRONTEND_URL=https://app.optionbot.org`

Stripe should send subscription events to:

- `https://<railway-backend-domain>/billing/webhook`

## 4. Domain (optional)

- Add a custom domain in Vercel settings
- Update `FRONTEND_URL` in Railway env vars
- Update Supabase Auth redirect URLs in Dashboard → Authentication → URL Configuration

## Local Development

```bash
# Terminal 1 — Backend API
cd optionbot
python3 -m uvicorn backend.app:app --reload --port 8000

# Terminal 2 — Background worker (optional for dev)
cd optionbot
python3 -m backend.worker

# Terminal 3 — Frontend
cd optionbot/frontend
npm run dev
```

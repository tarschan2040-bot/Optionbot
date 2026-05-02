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

Auth URL configuration also matters for email confirmation and password reset flows:

- Set **Site URL** to your deployed frontend domain, not localhost
- Add your production callback URL to **Redirect URLs**
- Keep localhost callback URLs only for local development if needed

Recommended production redirect URL:

- `https://optionbot-theta.vercel.app/auth/callback`

Update RLS policies for production:
```sql
-- Replace Phase 0 open policies with proper user isolation
DROP POLICY "Allow all access during Phase 0" ON user_configs;
CREATE POLICY "Users access own configs" ON user_configs
    FOR ALL USING (auth.uid()::text = user_id);
```

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

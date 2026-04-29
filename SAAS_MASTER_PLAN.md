# OptionBot SaaS Master Plan

**Last updated:** April 28, 2026
**Owner:** KC (cindy.chan@bit.com)
**Status:** Phase 0 — In progress (Task 0.1 complete)

---

## Purpose of this document

This is the single source of truth for turning OptionBot from a personal trading bot into a multi-user SaaS product. Any AI assistant or developer working on this project should read this file first to understand where we are, what has been decided, and what to do next.

If something in this document conflicts with `README.md`, `KEN_MASTER_HANDOFF.md`, or `OPTIONBOT_SAAS_BUSINESS_PLAN.md`, this document takes precedence — those are historical references, this is the active plan.

---

## Current state of the codebase (as of April 28, 2026)

### What exists and works

OptionBot is a Python-based options scanner that finds Covered Call and Cash-Secured Put opportunities. It runs on a Mac Mini, is controlled via Telegram, and stores trade candidates in Supabase.

**Core pipeline (working):**
- `core/scanner.py` orchestrates: fetch option chains → filter by strategy → calculate Greeks → score → rank
- `core/greeks.py` provides Black-Scholes Greeks (delta, theta, vega, gamma, rho) + IV Rank + annualised return
- `core/indicators.py` provides mean reversion signals (RSI, Z-Score, ROC Rank)
- `core/scorer.py` scores each opportunity 0–100 using 6 weighted factors
- `core/config.py` holds all tunable parameters in a `ScannerConfig` dataclass
- `strategies/covered_call.py` and `strategies/cash_secured_put.py` apply per-strategy filters

**Data sources (working):**
- `data/yfinance_fetcher.py` — Yahoo Finance (free, no login, default)
- `data/ibkr_fetcher.py` — Interactive Brokers (live, requires TWS/Gateway)
- `data/mock_fetcher.py` — Synthetic data for testing (dry-run mode)

**Output and control (working):**
- `scheduler.py` — Main entry point. Runs 3 daily scans at 09:35, 12:45, 15:00 ET + Telegram bot listener
- `output/telegram_bot.py` — Interactive Telegram bot with 20+ commands
- `output/telegram_notifier.py` — Sends scan alerts to Telegram
- `output/reporter.py` — Terminal table + CSV export
- `data/supabase_client.py` — Trade candidates (pending → starred → approved → placed)

**Codebase stats:** ~6,300 lines of Python across 19 source files.

### What was fixed on April 28, 2026

Eleven bugs were identified and fixed in a code review session:

1. **[FIXED]** Dry-run flag was not wired through `run_scan()` — now `--dry-run --once` works correctly
2. **[FIXED]** CSP annualised return used `underlying_price` instead of `strike` — `greeks.py` now branches on strategy
3. **[FIXED]** Division by zero risk when DTE=0 in CSP filter — guard added
4. **[FIXED]** `tools/test_*.py` scripts crashed pytest collection — renamed to `check_*.py`
5. **[FIXED]** Config `validate()` had identical if/else branches — simplified
6. **[FIXED]** Race condition in `cancel_event` clearing — consolidated under lock
7. **[FIXED]** No DTE bounds validation — `min_dte >= 0` and `max_dte >= min_dte` checks added
8. **[FIXED]** Bare `except:` in `debug_prices.py` — changed to `except (TypeError, ValueError)`
9. **[FIXED]** README referenced non-existent `main.py` — updated to `scheduler.py`
10. **[FIXED]** `test_greeks.py` delta parity assertion was wrong — corrected to `call_delta - put_delta ≈ 1`
11. **[FIXED]** `check_telegram.py` loaded `.env` from wrong directory — now looks at project root

### Known architectural issues (not yet fixed)

- **Telegram coupling:** `scheduler.py` cannot start without Telegram credentials. The scanner should be runnable standalone.
- **Single-user design:** `ScannerConfig` is an in-memory dataclass. No per-user config storage.
- **No auth, no billing, no web UI.**

---

## The plan — four phases

### Design principles (agreed)

These were validated through discussion and peer review:

1. **Keep the scanner core intact.** The Python pipeline (fetch → filter → Greeks → score → rank) is the product. Don't rewrite it — wrap it.
2. **Shared market data, personal scoring.** Fetch option chains once, cache them, then apply each user's personal `ScannerConfig` to score independently.
3. **Web dashboard is the product.** Telegram, email, API are delivery channels, not the product itself.
4. **Don't over-engineer v1.** No Kubernetes, no Celery, no Redis until traffic demands it. One server handles 200 users.
5. **Two tiers at launch.** Free + Pro ($49/mo). Add tiers when users ask for them.
6. **Validate data licensing before building.** Yahoo Finance and Polygon.io retail plans may not cover commercial SaaS redistribution.

---

### Phase 0 — Prepare the scanner core

**Status:** CODING COMPLETE — Tasks 0.1 + 0.2 + 0.3 done. Task 0.4 scheduled for May 4, 2026.
**Estimated effort:** 1–2 weeks
**Goal:** Make the scanner callable as a standalone function. No user-facing changes yet.

#### Tasks

**0.1 — Decouple Telegram from startup** ✅ DONE (April 28, 2026)
- ✅ `TelegramNotifier` and `TelegramBotListener` imports moved behind `--no-telegram` guard (lazy import)
- ✅ Added `--no-telegram` CLI flag to `scheduler.py`
- ✅ Created `NullNotifier` class — drop-in replacement that logs messages to terminal
- ✅ `DEFAULT_WATCHLIST` moved from `telegram_bot.py` to `scheduler.py` (no Telegram dependency for defaults)
- ✅ `reporter.py` prints results to terminal when Telegram is disabled
- ✅ Scanner core (`core/scanner.py`) has zero Telegram imports — confirmed clean
- ✅ Test passed: `python scheduler.py --once --no-telegram --dry-run` runs full scan and prints results

**0.2 — Extract ScannerConfig into a database-ready model** ✅ DONE (April 28, 2026)
- ✅ SQL migration: `migrations/001_create_user_configs.sql` — 35 columns mapping every ScannerConfig field (including MR settings the original plan missed)
- ✅ `load_user_config(user_id)` — loads a ScannerConfig from DB row
- ✅ `save_user_config(user_id, config)` — upserts config to DB (insert or update)
- ✅ `ensure_user_config(user_id)` — auto-migration: loads if exists, writes defaults if not
- ✅ `delete_user_config(user_id)` — cleanup helper
- ✅ Field mapping uses `dataclass_fields()` introspection — auto-adapts if ScannerConfig adds fields
- ✅ `dry_run` excluded from DB (runtime-only flag)
- ✅ ScannerConfig dataclass unchanged — DB layer wraps it, doesn't replace it
- ✅ All 15 existing tests pass, scanner dry-run works

**0.3 — Add config_hash to scan results** ✅ DONE (April 28, 2026)
- ✅ `ScannerConfig.config_hash()` method — SHA-256 of JSON-serialized fields (sorted keys, `dry_run` excluded)
- ✅ Deterministic: identical configs always produce the same hash
- ✅ `run_scan()` computes and logs config_hash at scan start
- ✅ `save_scan_history()` stores `config_hash` in the scan_history DB row
- ✅ Backward compatible: hash is auto-computed from config if not passed explicitly

**0.4 — Research data licensing (CRITICAL — do this first)** ⏰ SCHEDULED May 4, 2026
- Scheduled task `data-licensing-research` will run Monday May 4
- Will research Yahoo Finance ToS, Polygon.io commercial licensing, and alternatives
- Findings will be written to the "Data licensing status" section below
- Does not block Phase 1 coding — runs in parallel

#### Definition of done for Phase 0
- `python scheduler.py --once --no-telegram` works
- `ScannerConfig` can be loaded from and saved to Supabase
- Scan results include config_hash
- Data licensing research is in progress (does not need to be resolved to start Phase 1)

---

### Phase 1 — Web MVP + first paying users

**Status:** COMPLETE — Full MVP built (April 28, 2026). Ready for deployment + beta users.
**Estimated effort:** 4–6 weeks
**Goal:** A web dashboard where 10 beta users can sign up, configure, scan, and pay.

#### Tech stack (decided)

| Component | Choice | Reason |
|-----------|--------|--------|
| Frontend | Next.js on Vercel | Fast deployment, good React ecosystem, free tier |
| Backend API | FastAPI (Python) | Matches existing Python scanner, async-capable |
| Auth | Supabase Auth | Already in stack, no additional vendor |
| Database | Supabase PostgreSQL | Already in stack, has RLS, realtime subscriptions |
| Payments | Stripe | Industry standard, good docs, customer portal |
| Backend hosting | Railway or Render | Simple Python deployment, affordable |
| Background worker | Single Python process on same server | No Redis/Celery until queue pressure appears |

#### Web dashboard pages

1. **Login / Signup** — Supabase Auth (email + password, optionally Google OAuth)
2. **Dashboard** — Scan results table (sortable, filterable), last scan timestamp, next scheduled scan
3. **Detail view** — Full opportunity card: Greeks breakdown, scoring factors, contract details
4. **Settings** — Sliders and dropdowns for all `ScannerConfig` parameters (much better UX than Telegram `/set` commands). Watchlist management.
5. **Account** — Stripe customer portal (manage subscription, payment method, invoices)

#### API endpoints (FastAPI)

```
POST   /auth/signup          — Create account
POST   /auth/login           — Get JWT
GET    /scan/results         — Latest scan results for authenticated user
POST   /scan/trigger         — Queue a manual scan (with job deduping)
GET    /config               — Get user's ScannerConfig
PUT    /config               — Update user's ScannerConfig
POST   /stripe/webhook       — Stripe subscription events
GET    /stripe/portal        — Redirect to Stripe customer portal
```

#### Database schema additions

```sql
-- Extends existing Supabase tables

CREATE TABLE user_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    tickers TEXT[] DEFAULT '{}',
    strategy TEXT DEFAULT 'both',
    data_source TEXT DEFAULT 'yahoo',
    min_dte INT DEFAULT 21,
    max_dte INT DEFAULT 42,
    cc_delta_min FLOAT DEFAULT 0.20,
    cc_delta_max FLOAT DEFAULT 0.35,
    csp_delta_min FLOAT DEFAULT -0.35,
    csp_delta_max FLOAT DEFAULT -0.20,
    min_theta FLOAT DEFAULT 0.08,
    min_iv_rank FLOAT DEFAULT 0.0,
    min_iv FLOAT DEFAULT 0.40,
    max_vega FLOAT DEFAULT 0.50,
    min_annualised_return FLOAT DEFAULT 0.15,
    min_premium FLOAT DEFAULT 2.00,
    min_open_interest INT DEFAULT 0,
    max_bid_ask_spread_pct FLOAT DEFAULT 1.0,
    weight_iv FLOAT DEFAULT 0.15,
    weight_theta_yield FLOAT DEFAULT 0.15,
    weight_delta_safety FLOAT DEFAULT 0.20,
    weight_liquidity FLOAT DEFAULT 0.10,
    weight_ann_return FLOAT DEFAULT 0.25,
    weight_mean_reversion FLOAT DEFAULT 0.15,
    use_mean_reversion BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id)
);

CREATE TABLE scan_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    config_hash TEXT NOT NULL,
    scan_timestamp TIMESTAMPTZ DEFAULT now(),
    slot_label TEXT,
    results JSONB NOT NULL,        -- array of scored opportunities
    ticker_count INT,
    opportunity_count INT,
    duration_seconds FLOAT
);

CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    tier TEXT DEFAULT 'free',       -- 'free' or 'pro'
    status TEXT DEFAULT 'active',   -- 'active', 'cancelled', 'past_due'
    current_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id)
);

-- Row-level security on ALL tables
ALTER TABLE user_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE scan_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Users can only read/write their own data
CREATE POLICY "Users access own configs" ON user_configs
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users access own results" ON scan_results
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users access own subscriptions" ON subscriptions
    FOR SELECT USING (auth.uid() = user_id);
```

#### Pricing (decided)

| Tier | Price | Includes |
|------|-------|----------|
| Free | $0 | Previous day's top 5 results (delayed), 2 tickers, read-only scoring |
| Pro | $49/mo ($39/mo annual) | Real-time scans, unlimited tickers, full config, trade workflow, all channels |

No additional tiers until real user demand signals what to charge more for.

#### How multi-user scanning works

1. Background worker wakes up every 30 seconds
2. Checks for pending scan jobs (manual triggers) and scheduled scan times
3. For scheduled scans: loads all active Pro users, creates one job per user
4. For each job: loads user's config from `user_configs` → fetches market data from cache (or fresh if expired) → runs scanner pipeline → writes results to `scan_results` with config_hash
5. Market data cache: option chain metadata (strikes, expiries) cached 30 min. Quotes and IV cached 3 min. This avoids hammering Yahoo Finance for the same ticker across users.
6. Job deduping: if a user already has a pending/running job, ignore duplicate trigger requests

#### Definition of done for Phase 1
- A stranger can visit the site, sign up, configure their watchlist and parameters, trigger a scan, and see ranked results
- Stripe checkout works (Free → Pro upgrade)
- 10 beta users have accounts and have given feedback

---

### Phase 2 — Notification channels + community

**Status:** NOT STARTED
**Estimated effort:** 3–4 weeks
**Goal:** Users receive results via email and optionally Telegram. Community exists.

#### Tasks

**2.1 — Email alerts**
- Daily digest email at market close: user's top 5 opportunities with score, Greeks summary, and link to dashboard
- Use SendGrid or AWS SES
- User can toggle on/off in dashboard settings
- Also send: welcome email, scan complete notification (optional), weekly summary

**2.2 — Telegram bot (optional for paid users)**
- User links their Telegram account in dashboard settings (enters chat_id)
- Bot maps chat_id → user_id in database
- All existing Telegram commands work, routed to that user's config and results
- Not premium-only — available to all paid users. May become a higher-tier feature later based on usage data
- Your personal Telegram setup continues to work as before

**2.3 — Discord community**
- Free tier: read-only access
- Paid tier: full access (post, discuss, share trades)
- Channels: #general, #scan-results, #strategies, #feature-requests, #bugs
- This becomes the primary marketing and support channel

**2.4 — Operational improvements**
- Split cache by data type (chain metadata: 30 min TTL, quotes/IV: 3 min TTL, user results: per-user snapshot)
- Job deduping (one active scan per user at a time)
- Better error messages when scans return zero results (explain which filter eliminated everything)

#### Definition of done for Phase 2
- Email alerts working and toggleable
- Telegram linkable from dashboard
- Discord server live with 20+ members

---

### Phase 3 — Scale + advanced features

**Status:** NOT STARTED
**Estimated effort:** Ongoing
**Goal:** Handle 200+ users, add premium features, comply with regulations.

#### Tasks (prioritised by user demand)

**3.1 — Infrastructure scaling (only when needed)**
- Add Redis + Celery task queue when single worker becomes bottleneck
- Priority queue: Pro users' scans run before Free users'
- Horizontal scaling: add worker processes as needed
- Expected trigger: 100+ concurrent scan jobs at scheduled times

**3.2 — Paid data source (only after licensing is resolved)**
- Polygon.io or equivalent, under commercial/SaaS license
- Offer as part of Pro tier or as separate data add-on
- Must validate: can you legally redistribute processed results derived from their data?

**3.3 — REST API (only if customers ask)**
- Authenticated API returning JSON scan results
- Rate-limited by tier
- Suitable for institutional tier ($199/mo) or developer integrations

**3.4 — Advanced features (based on user feedback)**
- Payoff diagrams for each opportunity (visual risk/reward)
- Historical performance tracking (how did past scan #1 picks actually perform?)
- Advanced charting and technical analysis overlays
- Webhook delivery of scan results
- Custom scoring weight presets

**3.5 — Legal and compliance (before meaningful revenue)**
- Consult a lawyer on FINRA/SEC implications
- Key question: does selling a scanning tool with scores cross into "investment advice"?
- Never use language like "best trade for you" or "recommended" — the product "scores and ranks opportunities"
- Maintain logs of all configs, outputs, and notification history
- Terms of service, privacy policy, disclaimers must be reviewed by legal counsel
- Reference: https://www.finra.org/investors/investing/working-with-investment-professional/investment-advisers

---

## Data licensing status

**Yahoo Finance:** NOT YET VERIFIED for commercial SaaS use. Must read ToS and confirm.

**Polygon.io:** NOT YET VERIFIED. Retail pricing ($29-199/mo) is for individual use. Commercial/SaaS redistribution requires a separate business license. Must contact sales.

**Strategy:** Launch with Yahoo Finance if terms allow. Add paid data source later. If Yahoo disallows commercial use, Polygon becomes a launch requirement, not a Phase 3 item. This is the single biggest risk to the timeline.

---

## Unit economics target

| Item | Monthly cost | Notes |
|------|-------------|-------|
| Vercel (frontend) | $0–20 | Free tier handles ~100K requests |
| Railway/Render (backend) | $20–40 | Single server with worker |
| Supabase | $25 | Pro plan (8GB, 50K auth users) |
| SendGrid | $0–20 | Free tier: 100 emails/day |
| Data source | $0–200 | Yahoo = free. Polygon = $29-199+ |
| Stripe fees | 2.9% + $0.30/txn | Standard |
| **Total (Yahoo)** | **~$65/mo** | |
| **Total (Polygon)** | **~$265/mo** | |

**Break-even:** 2 Pro subscribers at $49/mo covers Yahoo-based infrastructure. 6 Pro subscribers covers Polygon-based infrastructure.

**Target margin:** At 50 Pro users ($2,450 MRR), infrastructure costs ~$100-300/mo = 88-96% gross margin.

---

## File reference

| File | Purpose | Status |
|------|---------|--------|
| `SAAS_MASTER_PLAN.md` | This document — the active plan | **Current** |
| `OPTIONBOT_SAAS_BUSINESS_PLAN.md` | Original business plan with competitor analysis | Historical reference |
| `KEN_MASTER_HANDOFF.md` | Project status and handoff notes | Historical reference |
| `README.md` | User-facing documentation for the current bot | Needs update when web MVP launches |
| `scheduler.py` | Current entry point (single-user bot) | Will be wrapped by FastAPI in Phase 1 |
| `core/config.py` | `ScannerConfig` dataclass | Will map to `user_configs` DB table in Phase 0 |
| `core/scanner.py` | Scanner orchestrator | Core stays intact, called by API/worker |

---

## Decision log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-28 | Web dashboard as primary product surface | Matches all successful competitors. Telegram is a channel, not the product. |
| 2026-04-28 | Two tiers only (Free + Pro $49/mo) at launch | Avoid decision fatigue. Add tiers when data shows demand. |
| 2026-04-28 | Supabase Auth over Clerk/Auth0 | Already in stack, fewer vendors, lower cost. |
| 2026-04-28 | No Redis/Celery in v1 | Single background worker handles 200 users. Add queue when bottleneck appears. |
| 2026-04-28 | Telegram available to all paid users (not premium-only) | Good for acquisition. May tier-gate later based on usage. |
| 2026-04-28 | Config hash on every scan result | Audit trail for reproducibility. Reviewer recommendation. |
| 2026-04-28 | Split cache by data type | Chain metadata (30 min), quotes (3 min), results (per-user). Reviewer recommendation. |
| 2026-04-28 | Data licensing validation is Phase 0 priority | Commercial redistribution rights must be confirmed before building. Reviewer flagged as biggest risk. |
| 2026-04-28 | Backend API first, frontend after | Validate endpoints and data flow before building UI. Stripe deferred to end of Phase 1. |
| 2026-04-28 | FastAPI backend lives in `backend/` subdirectory | Imports scanner core from project root. Clean separation: scanner = library, backend = web layer. |

---

## How to use this document

**If you are an AI assistant:** Read this file before starting any OptionBot development work. Check the "Status" field of each phase to know where we are. Only work on tasks in the current phase unless KC explicitly asks otherwise. When a phase is completed, update the status and date in this file.

**If you are a developer:** This is the architectural blueprint. The tech stack, database schema, and API endpoints are decided — implement them as specified unless you find a concrete technical reason to deviate (and document the deviation here).

**If you are KC:** Update the phase statuses as work progresses. Add decisions to the decision log. Keep the "Data licensing status" section current as you hear back from Yahoo/Polygon.

# OptionBot SaaS Master Plan

Read `AGENTS.md` and `CURRENT_STATE.md` first; no code changes without my approval.

## 2026-05-02 Addendum

Since the original draft of this plan:
- custom domain is live at `https://app.optionbot.org`
- custom SMTP is working through Resend
- signup email confirmation is working through a token-hash `/auth/confirm` route
- trade workflow isolation for new users has been fixed in active web routes and migration `004`
- scan and parameter pages are working on the live custom domain
- current code defines three beta tiers (`Free`, `Pro`, `Max`) while the original launch plan below says two tiers; treat the original tier language as product direction, not deployed billing reality

For the latest operational truth, prefer `CURRENT_STATE.md` over this plan when the two differ.

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

**Status:** COMPLETE — All tasks done. Task 0.4 research completed May 4, 2026.
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

**0.4 — Research data licensing (CRITICAL — do this first)** ✅ DONE (May 4, 2026)
- ✅ Yahoo Finance ToS reviewed — commercial SaaS use is NOT allowed
- ✅ Polygon.io (now Massive) Business pricing researched — $1,999+/mo for commercial use
- ✅ Alternatives evaluated: CBOE DataShop, Tradier, Unusual Whales, Databento, IEX Cloud (shut down)
- ✅ Findings written to "Data licensing status" section below
- ⚠️ Manual follow-up required: KC needs to contact Polygon sales and CBOE DataShop for quotes

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

Current route truth lives in `docs/API_ROUTES.md` and should be checked before
changing frontend API calls or backend route docs.

Mounted from `backend/app.py` as of 2026-05-15:

```
GET    /health
GET    /me
GET    /config
PUT    /config
GET    /scan/results
POST   /scan/trigger
GET    /scan/status
GET    /scan/results/{index}
GET    /scan/history
GET    /candidates
POST   /candidates/star
POST   /candidates/{candidate_id}/confirm
DELETE /candidates/{candidate_id}
GET    /candidates/portfolio
GET    /candidates/portfolio/summary
POST   /candidates/{trade_id}/close
```

Original planned endpoints from the early SaaS plan:

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

`/auth/*` and `/stripe/*` are not mounted by the current FastAPI backend.
Frontend auth currently uses Supabase directly, with backend JWT verification
in `backend/auth.py`. Stripe/billing remains planned work.

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

**Last researched:** May 4, 2026

### Yahoo Finance — NOT ALLOWED for commercial SaaS

- **Status:** Commercial use is prohibited under Yahoo's Terms of Service.
- **Key ToS language:** "You may not access or reuse the Services for any commercial purpose." Yahoo explicitly prohibits reproducing, selling, trading, distributing, or exploiting for commercial purposes any portion of the Services, including APIs. Additionally, Yahoo states: "You must not redistribute information displayed on or provided by Yahoo Finance."
- **yfinance library:** The `yfinance` Python library is an unofficial, third-party scraper — it is "not affiliated, endorsed, or vetted by Yahoo, Inc." and is "intended for research and educational purposes." Using it for a commercial SaaS product carries significant legal risk.
- **Derived data question:** Yahoo's ToS do not distinguish between raw data redistribution and derived/processed data. The blanket prohibition on commercial use and redistribution likely covers both. This is ambiguous enough that a lawyer might argue derived scores are transformative, but the risk is substantial.
- **Enforcement risk:** Yahoo could revoke access, rate-limit, or take legal action. The `yfinance` library relies on unofficial endpoints that Yahoo has broken before without notice.
- **Conclusion:** Do NOT launch a commercial SaaS product on Yahoo Finance data. It is suitable for personal use and development/testing only.
- **Sources:** [Yahoo API Terms of Use](https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.html), [Yahoo Terms of Service](https://legal.yahoo.com/xw/en/yahoo/terms/otos/index.html), [yfinance PyPI](https://pypi.org/project/yfinance/)

### Polygon.io (now "Massive") — ALLOWED with Business plan ($1,999+/mo)

- **Status:** Commercial SaaS redistribution is explicitly supported, but only on Business or Enterprise tiers.
- **Individual plans (Options):** $0–$199/mo. All individual plans are labeled "Individual use" only and marked "Non-pros only" on the Advanced tier. These do NOT permit commercial redistribution or SaaS use.
- **Business plan (Options):** Pricing is structured per the Stocks Business tier at **$1,999/month** (stocks). Options Business pricing requires contacting sales but is expected to be in the same range. Business plans are labeled "Business use" and include unlimited API calls, real-time data, and no exchange fee surprises.
- **Enterprise plan:** Custom pricing. Includes SLAs, dedicated Slack channel, implementation support, and a customer success team. Contact sales.
- **Startup discount:** Polygon/Massive offers startups up to 50% discount on the first year. Contact sales@massive.com to see if OptionBot qualifies.
- **Options data included:** Greeks, IV, open interest, minute aggregates, WebSockets, snapshot, trades, quotes.
- **Cost impact:** At $1,999/mo for business use, OptionBot would need ~41 Pro subscribers ($49/mo) just to cover the data cost. This changes the unit economics significantly from the original estimate.
- **Next steps:**
  1. Email sales@massive.com to get exact Options Business pricing
  2. Ask about the startup discount program
  3. Clarify whether displaying processed scores/rankings (not raw quotes) qualifies for a cheaper tier
  4. Get written confirmation that their Business license covers SaaS redistribution of derived analytics
- **Sources:** [Polygon.io Pricing](https://polygon.io/pricing?product=options), [Polygon.io Business Pricing](https://polygon.io/business)

### Alternative providers evaluated

**1. Tradier — UNCLEAR, requires brokerage account**
- Real-time options data is only available to Tradier Brokerage account holders. No standalone data-only commercial license found.
- API is free for active traders with a brokerage account, but commercial SaaS redistribution terms are not publicly documented.
- Best suited for brokerage-attached automation, not standalone SaaS data sourcing.
- **Next step:** Contact Tradier enterprise sales to ask about SaaS redistribution licensing.
- **Source:** [Tradier API Docs](https://docs.tradier.com/)

**2. CBOE DataShop (All Access API) — ALLOWED with redistribution license**
- CBOE explicitly offers a redistribution license for their All Access API.
- Allows retransmission of real-time, delayed, and historical non-SIP data into client-facing applications, websites, and data feeds.
- SIP data redistribution requires separate agreements with SIP providers.
- Pricing is tiered but not publicly listed — must contact CBOE sales (+1 800 307-8979 or via datashop.cboe.com contact form).
- This is the most "official" source since CBOE is the exchange itself.
- **Next step:** Contact CBOE DataShop sales for redistribution license pricing. Email via [datashop.cboe.com](https://datashop.cboe.com/) contact form, select "Sales."
- **Source:** [CBOE All Access API](https://datashop.cboe.com/cboe-all-access-api)

**3. Unusual Whales — ALLOWED at enterprise tier**
- Offers 100+ API endpoints covering options flow, dark pool, Greeks, etc.
- Enterprise tier includes redistribution rights — paid tiers unlock higher rate limits and redistribution.
- Historical options trades data: ~$250/month for full market.
- Enterprise pricing is custom — must contact sales for a quote.
- Provides a different type of data (flow/sentiment) vs raw chain data, but could complement a scanner.
- **Next step:** Contact Unusual Whales enterprise sales for SaaS redistribution pricing.
- **Source:** [Unusual Whales Enterprise](https://unusualwhales.com/enterprise), [Unusual Whales Pricing](https://unusualwhales.com/pricing)

**4. Databento — ALLOWED but expensive (professional OPRA: ~$2,000+/mo)**
- Official licensed distributor of options data from all US equity options exchanges.
- Professional subscribers pay at least $2,000/month for real-time OPRA options data.
- Exchange redistribution fees apply on top of Databento's own fees.
- Best suited for institutional-grade needs; likely overkill and overpriced for early-stage SaaS.
- **Source:** [Databento Options](https://databento.com/options), [Databento Pricing](https://databento.com/pricing)

**5. IEX Cloud — SHUT DOWN (August 2024)**
- IEX Cloud officially retired on August 31, 2024. Assets sold to Bluesky API.
- No longer a viable option. Remove from future consideration.
- **Source:** [IEX Cloud Closure Notice](https://iexcloud.org/)

### Revised strategy recommendation

1. **Yahoo Finance is NOT viable for commercial SaaS.** This is now confirmed. It was the biggest risk item and the answer is clear: do not use it for a paid product.

2. **Polygon.io (Massive) Business plan is the most practical path** but at $1,999/mo it significantly changes the economics. The startup discount (up to 50% off year 1) could bring this to ~$1,000/mo, which needs ~21 Pro subscribers to cover.

3. **CBOE DataShop is the most legitimate option** for options data specifically, since it comes directly from the exchange. Worth getting a quote even if it's more expensive — the licensing clarity may be worth the premium.

4. **Phased approach:**
   - **Development & beta (now):** Continue using Yahoo Finance / yfinance for internal testing and development only. Do not charge users while using Yahoo data.
   - **Pre-launch (before accepting payments):** Secure a commercial data license from Polygon/Massive or CBOE. Get the startup discount if possible.
   - **Post-launch:** Re-evaluate data costs as subscriber count grows. Consider CBOE DataShop if Polygon pricing doesn't scale well.

5. **Unit economics revised:**
   - Break-even with Polygon Business: ~41 Pro subscribers at $49/mo (without startup discount) or ~21 with 50% discount
   - Target: reach 50 Pro subscribers within 6 months of launch to achieve healthy margins
   - Consider whether $49/mo Pro pricing is sufficient, or if $69/mo or $79/mo is needed to absorb data costs

### Manual follow-up actions required

| # | Action | Contact | Priority |
|---|--------|---------|----------|
| 1 | Email Polygon/Massive sales for Options Business pricing + startup discount | sales@massive.com | HIGH |
| 2 | Contact CBOE DataShop for redistribution license pricing | [datashop.cboe.com](https://datashop.cboe.com/) contact form → Sales | HIGH |
| 3 | Contact Unusual Whales enterprise for SaaS redistribution quote | [unusualwhales.com/enterprise](https://unusualwhales.com/enterprise) | MEDIUM |
| 4 | Consult a lawyer on derived-data vs raw-data redistribution distinctions | — | MEDIUM |
| 5 | Re-evaluate Pro tier pricing ($49 vs $69 vs $79) given data costs | — | MEDIUM |

---

## Unit economics target

*Updated May 4, 2026 — Yahoo Finance is not viable for commercial use. Data costs revised.*

| Item | Monthly cost | Notes |
|------|-------------|-------|
| Vercel (frontend) | $0–20 | Free tier handles ~100K requests |
| Railway/Render (backend) | $20–40 | Single server with worker |
| Supabase | $25 | Pro plan (8GB, 50K auth users) |
| SendGrid | $0–20 | Free tier: 100 emails/day |
| Data source (Polygon Business) | $1,000–2,000 | $1,999/mo list; ~$1,000/mo with startup discount |
| Stripe fees | 2.9% + $0.30/txn | Standard |
| **Total (with startup discount)** | **~$1,065/mo** | |
| **Total (without discount)** | **~$2,065/mo** | |

**Break-even:** ~21 Pro subscribers at $49/mo (with startup discount) or ~42 without discount. If Pro pricing is raised to $69/mo, break-even drops to ~15 or ~30 respectively.

**Target margin:** At 50 Pro users ($2,450 MRR at $49/mo), infrastructure costs ~$1,065-2,065/mo = 16-57% gross margin. At $69/mo pricing, 50 users = $3,450 MRR = 40-69% gross margin. Margins improve significantly beyond 100 subscribers since data cost is fixed.

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
| 2026-05-04 | Yahoo Finance data cannot be used for commercial SaaS | Yahoo ToS explicitly prohibits commercial use and redistribution. yfinance is unofficial and unsuitable for production SaaS. |
| 2026-05-04 | Polygon.io (Massive) Business plan is primary commercial data path | Individual plans are "Individual use" only. Business tier ($1,999+/mo) required for SaaS. Startup discount (up to 50%) available. |
| 2026-05-04 | CBOE DataShop is secondary commercial data option | Exchange-direct data with explicit redistribution license. Pricing requires sales contact. Most legally clean option. |

---

## How to use this document

**If you are an AI assistant:** Read this file before starting any OptionBot development work. Check the "Status" field of each phase to know where we are. Only work on tasks in the current phase unless KC explicitly asks otherwise. When a phase is completed, update the status and date in this file.

**If you are a developer:** This is the architectural blueprint. The tech stack, database schema, and API endpoints are decided — implement them as specified unless you find a concrete technical reason to deviate (and document the deviation here).

**If you are KC:** Update the phase statuses as work progresses. Add decisions to the decision log. Keep the "Data licensing status" section current as you hear back from Yahoo/Polygon.

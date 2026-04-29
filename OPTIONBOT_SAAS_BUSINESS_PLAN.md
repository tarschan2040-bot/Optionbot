# OptionBot SaaS Business Plan & Monetization Analysis

**Prepared: April 27, 2026**
**Subject: Turning OptionBot into a public, subscription-based options scanning service**

---

## 1. Executive Summary

OptionBot is currently a personal options income scanner running on a Mac Mini, controlled via Telegram, with a Netlify dashboard. It scans for Covered Call and Cash-Secured Put opportunities using a 6-factor scoring engine with custom Black-Scholes Greeks, mean reversion timing, and a full trade workflow (pending → starred → approved → placed).

To go public as a paid SaaS, the system needs transformation across five areas: **multi-tenant architecture, user account management, payment processing, infrastructure scaling, and regulatory compliance**. This document analyzes the competitive landscape, recommends a pricing strategy, and maps out the full operational flow.

---

## 2. Competitive Landscape

### 2.1 Direct Competitors & Pricing

| Platform | Monthly Price | Annual Price | Free Tier | Trial | Key Differentiator |
|---|---|---|---|---|---|
| **Unusual Whales** | $50-75/mo | Yes (discounted) | Yes (delayed) | No | Congress trades, dark pool, massive community |
| **FlowAlgo** | $149/mo | $99/mo (billed yearly) | No | 2-week ($37) | Real-time sweeps, dark pool prints |
| **Cheddar Flow** | $45-85/mo | Yes | No | 7-day free | Clean UI, flow + dark pool |
| **InsiderFinance** | $75/mo | $55/mo (billed yearly) | No | No | Single all-inclusive tier, AI signals |
| **OptionStrat** | $40-100/mo | Yes | Yes (delayed) | 7-day | Visual P&L builder, strategy optimizer |
| **SweepCast** | $40/mo | $250/yr | No | 10-day ($18) | Affordable entry, simple interface |
| **Option Samurai** | $39-75/mo | ~$38/mo (billed yearly) | No | 14-day free | Scanner + screener focused |
| **TrendSpider** | $54-197/mo | 20% off annual | No | No | Advanced TA, auto-patterns |

### 2.2 What OptionBot Has That Others Don't

Your bot has several genuine differentiators worth emphasizing in marketing:

**Unique scoring engine.** Most competitors show raw flow data and leave interpretation to the user. OptionBot's 6-factor weighted scoring (IV 15% + Theta Yield 15% + Delta Safety 20% + Liquidity 10% + Annualised Return 25% + Mean Reversion 15%) produces a single 0-100 score that ranks opportunities. This is a real product advantage — it tells users *what to do*, not just *what's happening*.

**Income strategy focus.** The vast majority of competitors focus on directional flow (buying calls/puts). OptionBot is purpose-built for premium selling (CC + CSP + Wheel), which is an underserved niche. Many retail traders want income strategies but existing tools don't cater specifically to them.

**Telegram-native control.** While competitors require browser/app access, your Telegram interface lets users scan, review, and manage trades from their phone with zero app installation. This is a genuine UX advantage for mobile-first users.

**Transparent methodology.** The custom Black-Scholes Greeks engine and configurable parameters (13+ filters) give advanced users full control and transparency, unlike black-box "AI signal" competitors.

### 2.3 What You Should Adopt From Competitors

**From Unusual Whales:** Build a community (Discord) around the product. Their free tier with delayed data is an extremely effective acquisition funnel — users try it, get hooked on the workflow, then pay for real-time.

**From OptionStrat:** Visual P&L diagrams and strategy visualization. Users want to *see* their risk/reward before entering a trade. Adding a visual payoff diagram for each scored opportunity would be a strong differentiator.

**From InsiderFinance:** The single-tier pricing model is worth considering for launch. It eliminates decision fatigue and simplifies your billing infrastructure. You can always add tiers later.

**From FlowAlgo:** Premium pricing works if the product delivers. Don't underprice yourself — a $39/mo product is perceived as less valuable than a $79/mo product in the trading space.

**From TrendSpider:** Data add-on pricing. If you later integrate OPRA real-time feed, charging separately for that (since the data itself costs you money) is industry-standard.

---

## 3. Recommended Pricing Strategy

### 3.1 Pricing Tiers

Based on competitive analysis, here is the recommended pricing structure:

**Tier 1: Free (Acquisition Funnel)**
- Delayed scan results (previous day's top 5 opportunities)
- Limited to 2 tickers in watchlist
- Basic scoring visible, full detail cards locked
- Community Discord access (read-only)
- Purpose: Get users into the funnel, demonstrate value

**Tier 2: Scanner — $49/month ($39/month billed annually)**
- Real-time scanning (on-demand + 3 daily auto-scans)
- Up to 15 tickers in watchlist
- Full scoring breakdown + detail cards
- Telegram bot access (personal instance)
- Trade workflow (star → approve → track)
- Email/Telegram alerts for high-score opportunities
- Discord community (full access)

**Tier 3: Pro — $89/month ($69/month billed annually)**
- Everything in Scanner
- Unlimited watchlist tickers
- Mean reversion timing signals
- Custom parameter configuration (all 13+ filters)
- Priority scanning (your scans run first)
- AI assistant (/askclaude, /askllama)
- CSV export of scan results
- API access (100 calls/day)
- Web dashboard with live positions + performance tracking

**Tier 4: Institutional / API — $199/month (custom)**
- Everything in Pro
- Unlimited API access
- Webhook delivery of scan results
- Custom scoring weights
- White-label dashboard
- Priority support (Telegram/email, 4-hour response)

### 3.2 Pricing Justification

At $49-89/month, you are positioned in the sweet spot of the market ($40-100 range where most competitors sit). The annual discount (20-22%) is standard and improves cash flow predictability. A trader making even one better trade per month from your scoring easily recoups the subscription cost — the ROI argument is straightforward.

### 3.3 Revenue Projections (Conservative)

| Milestone | Users (paid) | Mix | MRR | ARR |
|---|---|---|---|---|
| Month 6 | 50 | 70% Scanner, 30% Pro | $3,085 | $37,020 |
| Month 12 | 200 | 60% Scanner, 40% Pro | $12,520 | $150,240 |
| Month 24 | 500 | 50% Scanner, 45% Pro, 5% Institutional | $41,475 | $497,700 |

---

## 4. Architecture for Multi-User Operation

### 4.1 Current State vs. Required State

| Component | Current (Single User) | Required (Multi-Tenant SaaS) |
|---|---|---|
| **Auth** | Telegram chat_id check | Auth system (Clerk/Auth0/Supertokens) + JWT |
| **Database** | Flat Supabase tables | Row-level security with `user_id` on every table |
| **Scanning** | Single Mac Mini process | Cloud workers (queue-based, per-user jobs) |
| **Telegram** | 1 bot, 1 admin | Per-user bot instances OR webhook-based routing |
| **Dashboard** | PIN-protected HTML | Authenticated React app with user sessions |
| **Payment** | None | Stripe Subscriptions + webhooks |
| **Data Source** | Yahoo/IBKR direct | Centralized data service (shared market data) |

### 4.2 Recommended Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND LAYER                        │
│                                                         │
│  React Dashboard (Vercel/Netlify)  ←→  Telegram Bots   │
│  - Auth via Clerk/Auth0                                 │
│  - Per-user dashboard                                   │
│  - Stripe Customer Portal                               │
└──────────────┬──────────────────────┬───────────────────┘
               │                      │
               ▼                      ▼
┌─────────────────────────────────────────────────────────┐
│                     API LAYER                            │
│                                                         │
│  FastAPI Backend (Railway / Render / AWS ECS)            │
│  - JWT auth middleware                                   │
│  - Rate limiting per subscription tier                   │
│  - Scan request queuing                                  │
│  - WebSocket for real-time results                       │
└──────────────┬──────────────────────┬───────────────────┘
               │                      │
               ▼                      ▼
┌──────────────────────┐  ┌───────────────────────────────┐
│    SCAN WORKERS       │  │       DATA SERVICES           │
│                       │  │                               │
│  Celery / Redis Queue │  │  Shared Market Data Cache     │
│  - Per-user scan jobs │  │  - Yahoo Finance (free tier)  │
│  - Priority by tier   │  │  - Polygon.io (paid, shared)  │
│  - Isolated configs   │  │  - Redis cache (5-min TTL)    │
│  - Score + rank       │  │  - Greeks engine (shared)     │
└──────────┬────────────┘  └───────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│                  DATABASE LAYER                           │
│                                                         │
│  Supabase PostgreSQL                                     │
│  - Row-Level Security (every table has user_id)          │
│  - Tables: users, subscriptions, watchlists,             │
│    scan_results, trade_candidates, trade_log,            │
│    user_configs, alerts                                  │
│  - Realtime subscriptions for live updates               │
└─────────────────────────────────────────────────────────┘
```

### 4.3 How Scanning Works for Multiple Users

The key challenge is that scanning costs time and API calls. Here's how to handle it efficiently:

**Shared Market Data Layer.** Option chain data for popular tickers (SPY, AAPL, TSLA, NVDA, QQQ, etc.) is fetched once centrally and cached in Redis with a 5-minute TTL. When User A and User B both have TSLA in their watchlist, the data is fetched once and scored twice (with each user's personal filter settings).

**Per-User Scan Jobs.** When a user triggers a scan (or a scheduled scan fires), a job is queued in Redis/Celery with the user's config attached. Workers pull jobs from the queue, apply the user's filters and scoring weights, and write results to Supabase with the user's ID.

**Priority Queuing.** Pro users' scans go into a priority queue. Free/Basic users go into a standard queue. During peak hours (market open, midday, pre-close), this ensures paying users get results first.

**Scheduled Scans.** Instead of 3 fixed times for everyone, users can configure their own scan schedule (within tier limits). The scheduler batches users by scan time and ticker overlap to minimize API calls.

### 4.4 Handling Per-User Telegram Bots

Two approaches, in order of recommendation:

**Option A: Single bot, multi-user routing (simpler, recommended for launch).** One Telegram bot instance. Users register by sending `/start` to the bot, which links their Telegram chat_id to their account. All commands are routed through the same bot but scoped to the authenticated user. The bot checks the user's subscription tier before executing commands.

**Option B: Per-user bot instances (premium feature, later).** For institutional/API tier users, spin up dedicated bot instances. This provides isolation but is operationally complex. Save this for later.

---

## 5. Account & Payment Flow

### 5.1 User Registration Flow

```
1. User visits optionbot.io (marketing site)
2. Clicks "Start Free Trial" → Clerk/Auth0 signup (email + password or Google/Apple SSO)
3. Account created in Supabase (users table) with plan = "free"
4. User connects Telegram: clicks link → bot sends verification code → confirmed
5. User lands on dashboard with free tier features active
6. Prompted to start 7-day Pro trial (credit card required via Stripe Checkout)
```

### 5.2 Subscription Management via Stripe

**Setup:**
- Create Stripe Products: "OptionBot Scanner", "OptionBot Pro", "OptionBot Institutional"
- Each product has two Prices: monthly and annual
- Use Stripe Checkout (hosted payment page) — avoids PCI compliance burden
- Stripe Customer Portal for self-service plan changes, payment method updates, cancellation

**Key Webhooks to Handle:**

| Stripe Event | Action |
|---|---|
| `checkout.session.completed` | Activate subscription, update user tier in Supabase |
| `invoice.paid` | Confirm payment, extend access |
| `invoice.payment_failed` | Send warning email/Telegram, 3-day grace period |
| `customer.subscription.updated` | Handle upgrade/downgrade, adjust features immediately |
| `customer.subscription.deleted` | Downgrade to free tier, preserve data for 90 days |
| `customer.subscription.trial_will_end` | Send reminder 3 days before trial ends |

**Dunning (Failed Payments):**
- Day 0: Payment fails → Stripe Smart Retries (automatic)
- Day 1: Email + Telegram notification to user
- Day 3: Second notification, scanning paused
- Day 7: Downgrade to free tier
- Day 30: Data preserved but account dormant

### 5.3 Feature Gating Implementation

```python
# Middleware example for your FastAPI backend
class SubscriptionGate:
    TIER_FEATURES = {
        "free": {
            "max_watchlist": 2,
            "scan_on_demand": False,
            "auto_scans_per_day": 0,
            "detail_cards": False,
            "custom_config": False,
            "ai_assistant": False,
            "api_access": False,
            "export": False,
        },
        "scanner": {
            "max_watchlist": 15,
            "scan_on_demand": True,
            "auto_scans_per_day": 3,
            "detail_cards": True,
            "custom_config": False,
            "ai_assistant": False,
            "api_access": False,
            "export": False,
        },
        "pro": {
            "max_watchlist": -1,  # unlimited
            "scan_on_demand": True,
            "auto_scans_per_day": 10,
            "detail_cards": True,
            "custom_config": True,
            "ai_assistant": True,
            "api_access": True,
            "export": True,
        },
    }
```

In the Telegram bot, every command handler checks the user's tier before executing:

```python
async def handle_scan(update, context):
    user = get_user_by_chat_id(update.effective_chat.id)
    if not user:
        return await update.message.reply_text("Please register at optionbot.io first")
    
    features = SubscriptionGate.TIER_FEATURES[user.plan]
    if not features["scan_on_demand"]:
        return await update.message.reply_text(
            "On-demand scanning requires Scanner plan ($49/mo). "
            "Upgrade at optionbot.io/upgrade"
        )
    # proceed with scan...
```

---

## 6. Full Operational Flow

### 6.1 Day-to-Day Operations

**Automated (no human intervention):**
- Scheduled scans fire for all users at their configured times
- Stripe handles billing, retries, and plan changes
- Monitoring alerts you to downtime or errors
- User signups and Telegram linking are self-service

**Weekly (your time):**
- Review metrics dashboard: new signups, churn, MRR, scan volume
- Respond to support tickets (email or Discord)
- Monitor infrastructure costs vs. revenue

**Monthly:**
- Review and optimize scanning costs (API calls, server time)
- Analyze churn: why are users leaving? Feature gaps? Performance issues?
- Update marketing content and landing page

### 6.2 Infrastructure Cost Estimates

| Component | Provider | Monthly Cost | Notes |
|---|---|---|---|
| **Backend API** | Railway / Render | $20-50 | Scales with traffic |
| **Scan Workers** | Railway / AWS ECS | $50-100 | 2-4 workers during market hours |
| **Database** | Supabase Pro | $25 | 8GB, row-level security |
| **Redis Cache** | Upstash | $10-30 | Shared market data cache |
| **Market Data** | Yahoo Finance (free) | $0 | Start free, upgrade later |
| **Market Data** | Polygon.io (later) | $99-199 | When you need real-time OPRA |
| **Telegram Bot** | Self-hosted | $0 | Runs on your API server |
| **Auth** | Clerk / Auth0 | $0-25 | Free up to 10K MAU |
| **Monitoring** | Grafana Cloud | $0 | Free tier sufficient |
| **Domain + DNS** | Cloudflare | $10/yr | optionbot.io |
| **Frontend** | Vercel / Netlify | $0-20 | Free tier usually enough |
| **AI (Claude API)** | Anthropic | $20-50 | Per-use, passed to Pro users |
| **Total (launch)** | | **~$150-300/mo** | |
| **Total (at scale)** | | **~$500-1000/mo** | 500+ users |

With 50 paying users at average $60/mo = $3,000 MRR, your infrastructure cost is well under 10% of revenue. This is an excellent margin for a SaaS business.

### 6.3 Launch Sequence (Recommended)

**Phase 1: MVP SaaS (Weeks 1-6)**
- Add user authentication (Clerk + Supabase)
- Add row-level security to all Supabase tables
- Implement Stripe subscription + webhooks
- Multi-user Telegram bot (single bot, user routing)
- Feature gating by tier
- Landing page (optionbot.io)

**Phase 2: Polish & Launch (Weeks 7-10)**
- Web dashboard with auth (upgrade existing Netlify dashboard)
- Onboarding flow (signup → connect Telegram → first scan)
- Email notifications (welcome, trial ending, scan results)
- Discord community setup
- Beta launch to 20-50 users (invite-only, discounted)

**Phase 3: Growth (Months 3-6)**
- Content marketing (YouTube: "How I find options trades with OptionBot")
- SEO: blog posts on options income strategies
- Referral program (give 1 month free, get 1 month free)
- Add visual P&L diagrams to scan results
- API tier for developers/quants

**Phase 4: Scale (Months 6-12)**
- Upgrade to Polygon.io for real-time data
- Mobile-optimized dashboard
- Advanced features: backtesting, portfolio-level risk analysis
- Consider iOS/Android app (React Native)
- Institutional partnerships

---

## 7. Regulatory & Legal Considerations

This is critical and often overlooked by trading tool startups:

**You are NOT providing financial advice.** Your tool provides data analysis and scoring — users make their own decisions. However, you must be explicit about this in your terms of service, marketing, and in-app disclaimers.

**Required disclaimers (every scan result, every marketing page):**
"OptionBot is a scanning and analysis tool. It does not constitute financial advice, investment recommendations, or solicitations to trade. Options trading involves significant risk of loss. Past performance does not guarantee future results. Consult a licensed financial advisor before making trading decisions."

**Terms of Service must include:**
- No guarantee of profits or performance
- User assumes all risk for trades based on scan results
- Data may be delayed or inaccurate
- Service provided "as-is"
- Liability limitation

**You likely do NOT need SEC/FINRA registration** as long as you are providing tools/data and not managing money, executing trades on behalf of users, or providing personalized investment advice. However, consult a securities attorney before launch — the line between "tool" and "advisor" can be blurry and regulators take this seriously.

**Privacy:** Collect minimal personal data. Users' watchlists and trade histories are sensitive — encrypt at rest and clarify in your privacy policy how data is used.

---

## 8. Key Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **Yahoo Finance rate limiting** | High | Cache aggressively, batch requests, upgrade to Polygon.io as revenue grows |
| **Regulatory action** | High | Disclaimers everywhere, consult securities attorney, never promise returns |
| **Data accuracy issues** | Medium | Yahoo's Greeks are estimated — your custom Black-Scholes engine is actually better, but validate regularly |
| **Single point of failure (Mac Mini)** | High | Move scanning to cloud (Railway/AWS) — Mac Mini is not SaaS-grade infrastructure |
| **Churn** | Medium | Monthly win-rate reports showing value, community engagement, continuous feature development |
| **Competition from free tools** | Medium | Your scoring engine is the moat — raw flow data is commodity, scored recommendations are not |
| **Scaling scan load** | Medium | Shared data cache + job queues handle this naturally |

---

## 9. What to Build First (Priority Order)

1. **Move off Mac Mini to cloud infrastructure** — This is non-negotiable for a public service. A Mac Mini at home cannot provide the uptime, scalability, or reliability paying customers expect.

2. **User authentication + Supabase RLS** — The foundation for everything else. Every table needs a `user_id` column with row-level security policies.

3. **Stripe integration** — Subscriptions, webhooks, customer portal. This is well-documented and can be done in a week.

4. **Multi-user Telegram routing** — Modify the existing bot to look up users by `chat_id` and apply their personal config + tier permissions.

5. **Landing page + onboarding** — A clean page at optionbot.io that explains the product, shows pricing, and funnels users into signup.

6. **Monitoring + alerting** — You need to know when scans fail, when the API is slow, when users can't connect. Grafana Cloud free tier is sufficient.

---

## 10. Summary Recommendation

Launch with a **two-tier model** (Scanner at $49/mo + Pro at $89/mo) with a **7-day free Pro trial** requiring a credit card. This maximizes conversion while keeping infrastructure simple. Add the free tier and institutional tier after you have 100+ paying users and understand your cost structure.

Your scoring engine is your competitive moat. No other tool in the market offers a single 0-100 score specifically optimized for premium-selling strategies. Lean into this in all marketing — "Stop scrolling through raw options flow. Get scored, ranked recommendations for income trades."

The total build-out to MVP SaaS is approximately 6 weeks of development work, with infrastructure costs starting under $300/month. At 50 paying users (achievable within 6 months with basic marketing), you're profitable. At 200 users, you're generating $150K+ ARR from a tool you built for yourself.

# Ken — Master Handoff Document
_Last updated: March 30, 2026 — Paste this into any new AI chat to continue without repeating history_

---

## ⚡ QUICK STATUS (Update This Every Session)

```
Current Phase:    Phase 2 — Mac Mini + IB Gateway Live (NEARLY COMPLETE)
Current Priority: Review Supabase + Netlify dashboard after full loop test
Last Completed:   March 30 2026 — Full loop live test PASSED + Yahoo Finance data source
                  ✅ Full loop live test DONE (scan → star → approve → placed → Telegram ✅)
                  ✅ Telegram + IBKR level confirmed working
                  ✅ Yahoo Finance data source added (data/yfinance_fetcher.py)
                  ✅ set data_source yahoo — bot scans 24/7, no IBKR login needed
                  ✅ set data_source ibkr  — switch back to IBKR anytime
                  ⚠️  Supabase write + Netlify dashboard still need confirmation
Mac Mini:         ACTIVE ✅ — bot running on Mac Mini (hinkwongchan@HindeMac-mini)
Data Source:      YAHOO ✅ — default changed to Yahoo Finance (free, no login, 24/7)
IBKR:             LIVE ACCOUNT ✅ — IB Gateway available; use set data_source ibkr if needed
Supabase:         CONNECTED ✅ — needs verification after live loop test
TOS Dashboard:    LIVE ✅ — optionbot.netlify.app — needs verification post loop test
Scanner Bot:      RUNNING ✅ — scheduler.py on Mac Mini
Next session:     1. Verify Supabase: check trade_candidates table after a scan
                  2. Verify Netlify dashboard shows new candidates from the loop test
                  3. Fix Netlify SPA routing (_redirects) for optionbot.netlify.app
                  4. Delete 3 bad "TESLA" rows in Supabase trade_log
                  5. Phase 3 — OpenClaw setup (pending Mac Mini)
```

---

## 🎯 THE FINAL GOAL

Ken's end state — what this entire system is building toward:

> A fully autonomous options income machine that runs 24/7 on a Mac Mini,
> finds the best CC and CSP opportunities on TSLA and other high-IV stocks,
> validates every trade against a strict rule set using AI,
> executes approved trades automatically via IBKR,
> monitors all open positions in real time,
> alerts Ken to any risk event,
> and generates a weekly performance report —
> all without Ken's daily involvement.
>
> This system sustains the family's lifestyle, frees Ken from active work,
> and enables early retirement — funded entirely by systematic options premium income.

**Target income:** $5,000-8,000/month from options premium
**Target timeline to full automation:** 24-36 months
**Foundation:** Wife's $6K/month USDC income covers all family expenses — trading is the accelerator, not the lifeline

---

## ⚠️ SYSTEM INTEGRITY RULE — NON-NEGOTIABLE

> Before making any change to any file, read the actual current file first.
> Never assume field names, function signatures, import paths, or logic from
> memory or other documents. Every change must be validated against the real
> file content. The goal is zero regressions — no existing functionality may
> be broken by any new addition. When in doubt, ask Ken before proceeding.

---

## 🗺️ MASTER SYSTEM ARCHITECTURE

```
═══════════════════════════════════════════════════════════════════
                    KEN'S TRADING OPERATING SYSTEM
═══════════════════════════════════════════════════════════════════

  MARKET DATA SOURCES              CONTROL INTERFACE
  ┌─────────────────┐              ┌─────────────────────────────┐
  │  IBKR TWS /     │              │         TELEGRAM            │
  │  IB Gateway     │              │   Ken's command centre      │
  │  (option chains │              │   scan / star / approve /   │
  │   Greeks, IV)   │              │   placed / alerts / config  │
  └────────┬────────┘              └──────────────┬──────────────┘
           │                                      │
  ┌────────▼────────┐                             │
  │  Yahoo Finance  │                             │
  │  (stock prices  │                             │
  │   + entry price │                             │
  │   on placed)    │                             │
  └────────┬────────┘                             │
           │                                      │
═══════════╪══════════════════════════════════════╪══════════════
           │        MAC LAPTOP (active now)       │
           │        MAC MINI (arriving soon)      │
           │                                      │
  ┌────────▼──────────────────────────────────────▼────────────┐
  │                                                             │
  │   ┌─────────────────────┐    ┌─────────────────────────┐   │
  │   │     OPTIONBOT        │    │       OPENCLAW           │   │
  │   │  (Signal Engine)     │◄───│  (AI Orchestrator)       │   │
  │   │  Mac laptop ✅       │    │  PENDING Mac Mini        │   │
  │   │                     │    │                          │   │
  │   │ • Scans IBKR        │    │ • Runs 24/7             │   │
  │   │ • Calculates Greeks │    │ • Schedules all tasks   │   │
  │   │ • Scores 0-100      │    │ • Triggers optionbot    │   │
  │   │ • Filters by rules  │    │ • Validates trades      │   │
  │   │ • Auto-stars ≥80    │    │ • Monitors positions    │   │
  │   │ • Sends to Telegram │    │ • Sends alerts          │   │
  │   │ • Writes top 10 to  │    │ • Weekly AI review      │   │
  │   │   Supabase ✅        │    │                         │   │
  │   └──────────┬──────────┘    └───────────┬─────────────┘   │
  │              │                            │                  │
  └──────────────┼────────────────────────────┼──────────────────┘
                 │                            │
═════════════════╪════════════════════════════╪══════════════════
                 │                            │
  ┌──────────────▼────────────────────────────▼──────────────────┐
  │                        SUPABASE  ✅                           │
  │                   (Central Database)                          │
  │                                                               │
  │  trade_candidates   trade_log   portfolio_state  risk_alerts  │
  │                                                               │
  │  Candidate status flow:                                       │
  │  pending → starred → approved → placed → (trade_log)         │
  │                                                               │
  │  • Written by optionbot (top 10 after every scan)            │
  │  • Updated by Ken via Telegram workflow commands             │
  │  • Read by TOS dashboard                                     │
  └───────────────────────────────┬──────────────────────────────┘
                                  │
            ┌─────────────────────▼──────────────────────┐
            │            TOS DASHBOARD  ✅                 │
            │   React app — Netlify (free hosting)        │
            │                                             │
            │  File: tos_dashboard.html                   │
            │  Deploy: drag + drop folder to Netlify      │
            │  PIN: 7788 (change in HTML file)            │
            │  Migration: migrate_lovable_trades.py       │
            │                                             │
            │  • Candidates: Starred / Approved / Placed  │
            │  • Open Positions from trade_log            │
            │  • Trade History (all time)                 │
            │  • Performance stats + trading rules        │
            │  • Auto-refresh every 60 seconds            │
            └─────────────────────────────────────────────┘
```

---

## 🧩 WORKFORCE DEFINITIONS AND RELATIONSHIPS

### 1. OPTIONBOT — The Signal Engine
**What it is:** Python-based scanner running on Mac laptop (moving to Mac Mini). Core signal-finding machine.

**What it does:**
- Connects to IBKR TWS / IB Gateway for live option chain data
- Fetches stock prices from Yahoo Finance
- Scans strikes in batches of 30 contracts (~2 min per ticker)
- Calculates Black-Scholes Greeks for every contract
- Filters by 13 configurable parameters (including min_iv ✅)
- Scores every opportunity 0-100 using weighted engine
- Auto-stars candidates scoring ≥ threshold (default 80) at scan time
- Writes top 10 candidates to Supabase after every scan
- Sends results and progress updates to Ken via Telegram

**Talks to:** IBKR, Yahoo Finance, Telegram, Supabase ✅, Claude API ✅, OpenRouter ✅
**Controlled by:** Ken via Telegram commands
**Status:** COMPLETE ✅ — Supabase integrated, trade workflow live, Mac migration done

**Mac launcher files:**
- `START_BOT.command` — double-click, opens Terminal (foreground)
- `START_BOT_BACKGROUND.command` — double-click, runs in background
- Stop via Telegram `/stopbot` → type `killbot`

---

### 2. SUPABASE — The Central Database
**What it is:** Cloud-hosted PostgreSQL database. Single source of truth for all trading data.

**What it stores:**
- `trade_candidates` — scan opportunities, evolving through workflow statuses
- `trade_log` — confirmed placed trades (open and closed)
- `portfolio_state` — snapshots of portfolio health over time
- `risk_alerts` — system-generated risk warnings for open positions

**Candidate status flow in trade_candidates:**
```
pending   → written automatically after every scan (top 10)
starred   → Ken stars a candidate, or auto-starred by score threshold
approved  → Ken approves a starred candidate (decision made)
placed    → Ken confirms order placed in IBKR (entry_price fetched from Yahoo)
rejected  → Ken rejects from starred or approved list
```

**One row per opportunity throughout the entire lifecycle — no duplicates.**
When `placed`, a corresponding row is also written to `trade_log`.

**Status:** FULLY CONNECTED ✅ — writing, reading, workflow all live

---

### 3. TOS DASHBOARD — Visual Dashboard
**Status: BUILT ✅ — Ready to deploy**

**Decision made:** Rebuild as React app on Netlify (free hosting, full control, no subscription).

**Files:**
- `tos_dashboard.html` — the complete dashboard (single HTML file, no build step needed)
- `migrate_lovable_trades.py` — script to import 37 historical Lovable trades into Supabase

**How to deploy:**
1. Create folder `tos-dashboard/`, copy `tos_dashboard.html` into it, rename copy to `index.html`
2. Go to app.netlify.com → drag + drop the folder
3. Done — get URL like `ken-trading-os.netlify.app`
4. Bookmark on phone home screen (works like an app)

**PIN:** `7788` (change in HTML file, line: `PIN : '7788'`)

**Dashboard sections:**
- Candidates tab: Starred / Approved / Placed / Pending sub-tabs
- Positions tab: open trades from trade_log
- History tab: all trades with PnL
- Performance tab: win rate, total PnL, strategy split, trading rules

**Auto-refresh:** every 60 seconds

---

### 4. MAC MINI — The Always-On Hub
**Status:** NOT YET ARRIVED — setup plan ready

Runs everything 24/7: IB Gateway, optionbot/scheduler, OpenClaw, risk engine.

---

### 5. OPENCLAW — The AI Orchestrator
**Status:** NOT YET INSTALLED — pending Mac Mini

Scheduled skills: morning briefing, pre-market scan, position monitor, daily summary, weekly review.
Event skills: score alert, delta alert, TSLA drop, take profit, DTE warning, heat warning.

---

### 6. CLAUDE API — The Primary AI Brain
**Status:** ACTIVE ✅ — Connected via /askclaude in Telegram

---

### 7. OPENROUTER / LLAMA — Secondary LLM
**Status:** ACTIVE ✅ — Connected via /askllama in Telegram
**Model:** meta-llama/llama-3.3-70b-instruct

---

### 8. TELEGRAM — The Control Interface
**Status:** FULLY WORKING ✅

**Current full command set (all require / prefix):**

```
SCAN
  /scan / /scan TSLA / /scan TSLA AAPL NVDA
  /stopscan / /cancelscan / /lastscan

RESULTS NAVIGATION
  /fullresult          page 1 of all results (10 per page)
  /next                next page
  /previous            previous page
  /result <n>          full detail card for opportunity #n

TRADE WORKFLOW
  /star <n>            star result #n from current scan
  /starredlist         show all starred candidates (with scan date)
  /approve <n>         approve starred #n → moves to approved list
  /approvedlist        show all approved candidates
  /placed <n>          confirm order placed for approved #n
                       fetches Yahoo Finance price as entry_price
  /placed <n> 14:35    placed at specific time
  /placedlist          show all placed/open trades
  /unstar <n>          remove #n from starred list
  /reject <n>          reject #n from starred or approved list

AUTO-STAR
  Candidates scoring ≥ autostar threshold automatically starred at scan time
  Default threshold: 80. Change with: /set autostar 75
  Disable with: /set autostar 0

CONFIG
  /config              show all settings + active overrides
  /set <param> <value>        single parameter
  /set p1 v1 p2 v2 p3 v3     multiple parameters, single line
  /set reset           restore all defaults

  Settable parameters:
  min_dte / max_dte / strike_pct / min_premium / min_theta
  min_iv_rank / min_iv / min_ann_return
  cc_delta_min / cc_delta_max / csp_delta_min / csp_delta_max
  min_oi / max_spread / strategy / autostar

MARKET DATA
  /price TSLA / /price BTC / /price GOLD / /price VIX
  /movers

AI ASSISTANTS
  /askclaude <question>   — ask Claude AI (Anthropic claude-sonnet-4-6)
  /askllama <question>    — ask Llama AI (OpenRouter, llama-3.3-70b)

SYSTEM
  /health              full system check (IBKR, Supabase, Claude, OpenRouter, market)
  /stopbot             gracefully stop the bot (password: killbot)
  /help / /score
```

**IMPORTANT:** Plain text messages are silently ignored — only /command messages work.
Password entry for /stopbot (typing `killbot`) is the only exception.

**Single TELEGRAM_CHAT_ID only.** Multi-user access planned for future — not yet built.

---

### 9. IBKR / IB GATEWAY
**Status:** Mac laptop — connect when scanning. Mac Mini setup pending.

```
Enable ActiveX and Socket Clients: ON
Read-Only API: OFF
Port: 7497 (paper) / 7496 (live)
Allow localhost only: ON
```

Known issues:
- Error 10197 — competing session. Fix: close all IBKR sessions, restart Gateway.
- /health shows IBKR ❌ when TWS/IB Gateway is not open — this is normal when not trading.

---

### 10. TRADINGVIEW — Chart Analysis
**Status:** Working ✅ — TSLA Options Dashboard v2 (SMA-based Pine Script)

Signals: SELL PUT / SELL CALL / CC / VOL / SQUEEZE

---

### Current Phase 1 Workflow (How Everything Works Together Now)

```
PHASE 1 — ACTIVE ✅

Scan fires (manual or scheduled: 09:35 / 12:45 / 15:00 ET)
  → Scans IBKR for CC + CSP opportunities
  → Top 10 candidates written to Supabase (status = pending)
  → Candidates scoring ≥ 80 auto-starred (status = starred)
  → Results sent to Telegram
  → 💾 message confirms how many saved + how many auto-starred

Ken reviews results in Telegram
  → /fullresult / /next / /previous to browse
  → /result <n> for full detail card

Ken shortlists
  → /star <n> to save interesting candidates
  → /starredlist to review shortlist (shows date of each)

Ken checks TradingView for technical confirmation

Ken makes decision
  → /approve <n> from starredlist
  → /approvedlist to confirm

Ken places order manually in IBKR
  → /placed <n> confirms execution
  → System fetches Yahoo Finance price as entry_price
  → Trade row written to trade_log in Supabase
  → /placedlist shows all open trades

Ken reviews dashboard (tos_dashboard.html on Netlify)
  → Candidates tab shows starred/approved/placed candidates
  → Positions tab shows all open trades
  → History + Performance tabs for review

Ken updates exit data manually when trade closes
  → Update directly in Supabase (table editor) or future TOS feature
```

---

## 📋 FINALIZED OPTION TRADING RULES

### SCANNER FILTER PARAMETERS (core/config.py — ground truth)

| Parameter | Current Value | Notes |
|-----------|-------------|-------|
| min_dte | 21 | Ideal entry 30-45 DTE |
| max_dte | 45 | Beyond 45 theta decay too slow |
| strike_range_pct | 0.15 | ±15% of current price |
| cc_delta_min | 0.20 | CC minimum delta |
| cc_delta_max | 0.35 | Wider for more candidates — Ken selects lower |
| csp_delta_min | -0.35 | CSP most OTM |
| csp_delta_max | -0.20 | CSP most ITM |
| min_iv_rank | 30 | Set 0 in low-IV periods |
| min_iv | 0.35 | 35% absolute IV floor ✅ now implemented |
| min_premium | 0.25 | $0.25/share minimum |
| min_theta | 0.02 | $2/day per contract |
| min_annualised_return | 0.15 | 15% minimum |
| min_open_interest | 0 | Keep 0 — IBKR delayed data returns OI=0 |
| min_volume | 0 | Disabled |
| max_bid_ask_spread_pct | 0.10 | 10% max spread |

**Two-layer IV filtering:**
```
min_iv_rank 30  → relative filter — where IV sits vs 52-week history
min_iv 0.35     → absolute filter — always require real premium regardless of history

Normal scan:    set min_iv_rank 30  set min_iv 0.35
No IBKR hist:   set min_iv_rank 0   set min_iv 0.40
TSLA/hi-vol:    set min_iv_rank 30  set min_iv 0.50
Wide scan:      set min_iv_rank 0   set min_iv 0
```

---

### SCORING ENGINE (core/scorer.py)

| Factor | Weight |
|--------|--------|
| Theta Yield | 30% |
| IV Rank | 25% |
| Delta Safety | 20% |
| Liquidity | 15% |
| Annualised Return | 10% |

**Auto-star threshold:** Score ≥ 80 = automatically starred at scan time.

---

### ENTRY RULES (Ken applies manually when reviewing candidates)

**Market conditions:**
- [ ] IV Rank >30 OR absolute IV >35% (at least one must be true)
- [ ] Not within 5 days of TSLA earnings announcement
- [ ] VIX not in extreme fear (>40) unless selling puts for premium

**Technical confirmation (TradingView — at least one):**
- [ ] Price near strong support (CSP) or resistance (CC)
- [ ] RSI <35 oversold (CSP) or RSI >65 overbought (CC)
- [ ] TradingView TSLA Options Dashboard showing matching signal

**Position sizing:**
- [ ] Capital at risk ≤5% of total portfolio
- [ ] TSLA options total exposure ≤15% of portfolio
- [ ] Total portfolio heat ≤40%
- [ ] CC: income layer shares only (max 2 contracts)
- [ ] CSP: cash covers full assignment (max 1 contract)

**Preferred entry:**
- Delta: 0.20 (range 0.15-0.25)
- DTE: 30-45 days (ideal 35)
- Premium: >$1.00/share for TSLA
- OTM distance: 8-12% from current price

---

### POSITION MANAGEMENT RULES

**Stop Loss (close immediately):**
- Unrealized loss ≥ 1× entry premium
- Delta > 0.50
- TSLA adverse move >8%
- No averaging down. Ever.

**Take Profit (close early):**
- Premium captured ≥80% AND DTE >15 (preferred)
- Premium captured ≥75% at any time
- IV crush event
- Market shifts against thesis

**DTE Rules:**
- DTE <21: consider closing or rolling
- DTE <15: must close or roll

**Roll Rules:**
- Maximum 1 roll per position
- CC: roll up + out (higher strike, next month)
- CSP: roll down + out (lower strike, next month)
- Never roll to avoid accepting a loss

---

## ✅ MASTER MILESTONE CHECKLIST

### 🔵 PHASE 0 — FOUNDATION (COMPLETE ✅)
- [x] IBKR + Yahoo Finance + Greeks engine working
- [x] CC + CSP strategy filters working
- [x] Composite scorer 0-100 working
- [x] Batch fetching (~2 min per ticker)
- [x] Telegram bot — all commands working
- [x] cancelscan added
- [x] Auto DST timezone detection
- [x] Claude linked to Telegram
- [x] All 26 known bugs fixed
- [x] Lovable TOS web app created
- [x] Supabase tables created (4 tables)
- [x] 37 trades logged in TOS

---

### 🔵 PHASE 1 — SCANNER TO TOS CONNECTION (COMPLETE ✅)

#### Scanner Parameters
- [x] min_iv absolute IV floor added to core/config.py
- [x] min_iv filter applied in covered_call.py
- [x] min_iv filter applied in cash_secured_put.py
- [x] min_iv settable via Telegram (set min_iv 0.40)

#### Mac Migration
- [x] Bot migrated from Windows to Mac laptop
- [x] START_BOT.command + START_BOT_BACKGROUND.command created (double-click launchers)
- [x] Python path auto-detection in background launcher
- [x] requirements.txt updated for Mac
- [x] All core Python code confirmed cross-platform (no changes needed)

#### New Telegram Features (added during Mac migration)
- [x] /health — full system check (IBKR, Supabase, Claude API, OpenRouter, market status)
- [x] /stopbot — password-protected shutdown (password: killbot)
- [x] /askclaude — Claude AI (replaces old /ask)
- [x] /askllama — OpenRouter / Llama 3.3 70B (new)
- [x] Slash gate — plain text ignored, only /commands execute
- [x] Telegram autocomplete menu — all 18 commands registered
- [x] OpenRouter API key added to .env

#### Supabase Integration
- [x] data/supabase_client.py created and deployed
- [x] SUPABASE_URL + SUPABASE_KEY added to .env
- [x] supabase library installed
- [x] Connection test passed
- [x] scheduler.py writes top 10 candidates after every scan
- [x] Auto-star logic — score ≥ threshold written as 'starred' at insert
- [x] find_and_star — no duplicate rows (updates existing pending row)
- [x] Telegram confirms candidates saved + auto-starred count

#### Trade Workflow (Telegram)
- [x] /star <n> — stars from in-memory scan results
- [x] /starredlist — shows all starred with scan date
- [x] /approve <n> — approves from starred list
- [x] /approvedlist — shows all approved
- [x] /placed <n> — confirms order placed, fetches Yahoo price
- [x] /placed <n> HH:MM — placed at specific time
- [x] /placedlist — shows all placed trades
- [x] /unstar <n> — reverts to pending
- [x] /reject <n> — rejects from starred or approved
- [x] Multi-parameter set (single line and multi-line both work)
- [x] /fullresult / /next / /previous navigation
- [x] autostar threshold settable via /set autostar <value>

#### TOS Dashboard
- [x] TOS dashboard decision made — React on Netlify (free, no lock-in)
- [x] tos_dashboard.html built — single HTML file, no build step
- [x] migrate_lovable_trades.py built — imports 37 Lovable trades to Supabase

#### March 23, 2026 — Telegram UX Overhaul + IBKR Live
- [x] Interactive inline keyboard menus — 7 categories (Scan, Results, Config, AI, Market, System, Help)
- [x] Dynamic watchlist management via Telegram (setwatchlist / watchlist)
- [x] Dynamic scan schedule via Telegram (setscantime / scanschedule)
- [x] Portfolio command — shows open trades from trade_log
- [x] Trade detail cards — trade <n> for full detail on any open trade
- [x] Clear list commands — clearstarred, clearapproved, clearplaced (scan history + portfolio never touched)
- [x] Help button fix — _send_long() splits messages at 4000 chars with ``` fence pairing
- [x] Result table improvements: CP → SCP, added Delta column, added Expiry DD/MM column
- [x] Navigation overhaul: result (full list), page <n> (pagination), detail <n> (individual)
- [x] Removed next/previous commands
- [x] Removed / prefix requirement — all commands work without leading slash
- [x] Menu shortcut: m (replaces /menu)
- [x] Config output includes full parameter guide with explanations
- [x] Auto Results menu appears after every scan completion
- [x] Multi-user access: admin (TELEGRAM_CHAT_ID) + viewers (TELEGRAM_VIEWER_IDS)
- [x] Viewer role: read-only, no AI chat, no config changes, no workflow actions
- [x] IBKR live account connected via IB Gateway (port 4001)
- [x] Market data Type 1 (live streaming) when market open
- [x] Read-Only API disabled (bot is read-only by code — no placeOrder calls)
- [x] Portfolio date format changed to DD-Mon (matches placed list)

#### Still Outstanding
- [x] Deploy tos_dashboard.html to Netlify ✅
- [x] Run migrate_lovable_trades.py to import trades ✅ (43 trades in Supabase)
- [x] Lovable UI deployed to optionbot.netlify.app ✅
- [x] Supabase migrated to tarschan account ✅
- [x] Startup drain fix — stale /stopbot no longer fires on restart ✅
- [ ] Full loop live test during US market hours (scan → star → approve → placed → visible in dashboard)
- [ ] Fix Netlify SPA routing (_redirects) for optionbot.netlify.app direct URL access

---

### 🔵 PHASE 2 — MAC MINI + IB GATEWAY LIVE (IN PROGRESS)

- [x] Mac Mini arrived and running ✅
- [x] Homebrew + Python + Git installed ✅
- [x] IB Gateway configured — LIVE account, port 4001, API on, Read-Only OFF ✅
- [x] Scanner bot running on Mac Mini ✅
- [x] Live streaming data Type 1 (real-time when market open) ✅
- [x] Multi-user Telegram access (admin + viewer) ✅
- [x] Viewer user 788460876 added ✅
- [x] Full loop live test PASSED ✅ (Telegram + IBKR level confirmed working)
- [x] Yahoo Finance data source added ✅ (data/yfinance_fetcher.py — no IBKR login needed)
- [x] set data_source yahoo/ibkr command wired in Telegram ✅
- [ ] Verify Supabase write after scan (trade_candidates table)
- [ ] Verify Netlify dashboard shows candidates from loop test
- [ ] Fix Netlify SPA routing (_redirects)
- [ ] Delete 3 bad "TESLA" rows in Supabase trade_log (manual entry typos)

---

### 🔵 PHASE 3 — OPENCLAW SETUP (PENDING)

- [ ] OpenClaw installed and accessible via Telegram
- [ ] Claude API connected as primary LLM
- [ ] Minimax API connected as secondary LLM
- [ ] All scheduled skills running (morning, pre-market, position monitor, daily, weekly)
- [ ] All event-driven alert skills built

---

### 🔵 PHASE 4 — LIVE POSITION MONITORING (PENDING)

- [ ] portfolio_monitor.py created and reading IB Gateway
- [ ] Risk flags written to Supabase every 15 min
- [ ] TOS showing live GREEN/YELLOW/RED per position

---

### 🔵 PHASE 7 — PERFORMANCE VALIDATION

- [x] 37 trades logged
- [ ] 50 trades logged
- [ ] 100 trades logged
- [ ] 150 trades (statistical confidence)
- [ ] Tested through TSLA earnings event
- [ ] Tested through VIX >25 week
- [ ] Tested through TSLA drawdown >15%
- [ ] Monthly income ≥$4,000 for 3 consecutive months

---

### 🔵 PHASE 8 — LIFE PLANNING

- [ ] $65,000 emergency buffer in separate account
- [ ] $20-30K in GBP bank account
- [ ] UK accountant: options income tax classification
- [ ] UK accountant: crypto/BTC tax position
- [ ] Early retirement target date set

---

## 📊 CURRENT PORTFOLIO SNAPSHOT

| Asset | Amount | Approx Value | Role |
|-------|--------|-------------|------|
| TSLA shares | 630 | ~$257,000 | Income engine + long term hold |
| BTC | 1.3428 | ~$111,000 | Long term macro + position trade |
| Cash USD | — | $50,000 | CSP collateral + swing capital |
| Cash USDC | — | $20,000 | Stable reserve |
| **Total** | | **~$438,000** | |

### TSLA 3-Layer Split — CRITICAL

| Layer | Shares | Purpose | Max Options |
|-------|--------|---------|------------|
| Core | 200 | FSD/Robotaxi/Bot thesis 5-10yr | ZERO — never touch |
| Tactical | 200 | Position trading 1-3 months | Occasional CC only |
| Income | 230 | Wheel strategy engine | Max 2 CC + 1 CSP |

---

## 📈 TRADING PERFORMANCE SNAPSHOT

| Metric | Value | Assessment |
|--------|-------|-----------|
| Total trades | 37 | Too small — need 150+ |
| Win rate | 81.1% (30W/7L) | Expected for premium selling |
| Total profit | $24,271 | Strong over 5 months |
| Expectancy | $655.97/trade | Positive edge confirmed |
| Avg win | $986.30 | |
| Avg loss | $759.71 | |
| Risk:Reward | 1:1.30 | Healthy |
| Avg hold | 12.8 days | Efficient capital use |
| Early exit rate | 75.7% | KEY EDGE |
| Return | ~13.5% in 5 months | ~32% annualised |

**Core edge: 75.7% early exit discipline.** Must be preserved by the system.

---

## 📁 FILE STATUS TABLE

| File | Status | Notes |
|------|--------|-------|
| scheduler.py | Latest ✅ | Supabase write, top 10, autostar threshold |
| output/telegram_bot.py | Latest ✅ | /health, /stopbot, /askclaude, /askllama, slash gate |
| data/supabase_client.py | Latest ✅ | Full workflow methods, find_and_star |
| core/config.py | Latest ✅ | min_iv added, two-layer IV filtering |
| strategies/covered_call.py | Latest ✅ | min_iv filter applied |
| strategies/cash_secured_put.py | Latest ✅ | min_iv filter applied |
| tos_dashboard.html | NEW ✅ | React dashboard — deploy to Netlify |
| migrate_lovable_trades.py | NEW ✅ | Import 37 Lovable trades to Supabase |
| START_BOT.command | NEW ✅ | Mac double-click launcher (foreground) |
| START_BOT_BACKGROUND.command | NEW ✅ | Mac double-click launcher (background) |
| START_BOT.sh | NEW ✅ | Mac shell launcher |
| START_BOT_BACKGROUND.sh | NEW ✅ | Mac background launcher with Python auto-detect |
| data/yfinance_fetcher.py | NEW ✅ | Free option chain data — no IBKR, no login, 24/7 |
| core/config.py | Updated ✅ | data_source field added (default: "yahoo") |
| core/scanner.py | Updated ✅ | _build_fetcher() — selects yahoo or ibkr fetcher |
| output/telegram_bot.py | Updated ✅ | data_source in SETTABLE_PARAMS + set validation |

---

## 📍 WHERE TO FIND THINGS

| Thing | Location |
|-------|----------|
| Scanner bot (Mac laptop) | optionbot/ folder on Mac |
| Scanner bot (future) | ~/trading/optionbot/ on Mac Mini |
| TOS dashboard file | optionbot/tos_dashboard.html |
| TOS dashboard (live) | Netlify URL — deploy first |
| Supabase | https://dcmuqcunlenbvgzxgstx.supabase.co |
| TradingView | TSLA chart → TSLA Options Pro Dashboard v2 (SMA) |
| This document | optionbot/KEN_MASTER_HANDOFF.md |

---

## 🔐 SERVICES REFERENCE

Keys stored in .env only. Never paste actual values in this document.

| Service | Key Name | Notes |
|---------|----------|-------|
| IBKR | — | IB Gateway, port 7497 (paper) / 7496 (live) |
| Telegram Bot | TELEGRAM_BOT_TOKEN | In optionbot/.env |
| Telegram Chat | TELEGRAM_CHAT_ID | In optionbot/.env — single user only |
| Supabase URL | SUPABASE_URL | https://eaphmnbbsfvuxzbmsmos.supabase.co |
| Supabase Key | SUPABASE_KEY | Supabase → Settings → API → Publishable API Key |
| Anthropic Claude | ANTHROPIC_API_KEY | In optionbot/.env — powers /askclaude |
| OpenRouter | OPENROUTER_API_KEY | In optionbot/.env — powers /askllama |
| Minimax API | MINIMAX_API_KEY | Add when OpenClaw setup begins |

---

## 🔮 PENDING DECISIONS & FUTURE ITEMS

| Item | Status | Notes |
|------|--------|-------|
| Deploy TOS dashboard to Netlify | COMPLETE ✅ | tos_dashboard.html live on Netlify |
| Deploy Lovable UI to Netlify | COMPLETE ✅ | optionbot.netlify.app via GitHub |
| Import Lovable trades to Supabase | COMPLETE ✅ | 43 trades in new OptionBot project |
| Supabase → tarschan account | COMPLETE ✅ | New project: eaphmnbbsfvuxzbmsmos |
| Full loop live test | PENDING — needs market hours | Run Mon–Fri during trading hours |
| Fix Netlify SPA routing | PENDING | Add _redirects to optionbot.netlify.app repo |
| Mac Mini setup | COMPLETE ✅ — bot running on Mac Mini | scheduler.py active |
| Multi-user Telegram access | DEFERRED | Single chat_id only for now |
| scan_id / slot_label in trade_candidates | FUTURE | Add when multiple daily scans cause confusion |
| Parallel scan support | PHASE 3+ | Needs connection pool + scan queue |
| Portfolio monitor (Phase 4) | PHASE 4 | portfolio_monitor.py — reads IB Gateway live |

---

## 💡 HOW KEN LIKES TO WORK WITH AI

- Deliver **complete rewritten files** — never snippets to paste manually
- Give **step-by-step instructions** with exact file names and full paths
- **Not a developer** — explain every terminal command, assume no prior knowledge
- Always consider the **whole system** before any change — nothing in isolation
- **Read the actual file before changing it** — never assume from memory
- When something fails, **ask for terminal output** before suggesting fixes
- Everything controlled from **Telegram** — minimal terminal interaction needed
- Prefer **free data** (Yahoo Finance) over paid IBKR subscriptions
- Every decision should **move toward automation**
- When uncertain, **ask Ken** — he provides real numbers and real context
- **Update Quick Status box and checklist** at the end of every session

---

## 🔄 HOW TO KEEP THIS DOCUMENT CURRENT

After every session:
1. Update Quick Status box at the top
2. Tick off completed items in the checklist
3. Update File Status Table if files changed
4. Update Pending Decisions if anything resolved or added
5. Save updated file to optionbot/ folder

This is the single source of truth. Any AI reading this continues exactly where the last session ended.

---

_Version: March 30, 2026 | Next priority: Verify Supabase + Netlify → Netlify SPA fix → Clean TESLA rows → Phase 3 OpenClaw_

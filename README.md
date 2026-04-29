# 📊 Sell Option Scanner

A modular, Greeks-aware scanner for **Covered Calls** and **Cash-Secured Puts** on US stocks,
with pluggable data sources (Yahoo Finance free, or Interactive Brokers live).

---

## Architecture

```
optionbot/
│
├── scheduler.py                 # Entry point — daily scan scheduler + Telegram bot
│
├── core/
│   ├── config.py                # All tunable parameters (thresholds, weights)
│   ├── models.py                # Data classes: OptionContract, GreeksResult, ScanOpportunity
│   ├── greeks.py                # Black-Scholes Greeks engine (Delta, Theta, Vega, Gamma, Rho)
│   ├── indicators.py            # Technical indicators (RSI, Z-Score, ROC Rank)
│   ├── scanner.py               # Main orchestrator (fetch → filter → score → rank)
│   └── scorer.py                # 6-factor composite scoring system (0–100)
│
├── strategies/
│   ├── covered_call.py          # Covered Call filter logic
│   └── cash_secured_put.py      # Cash-Secured Put filter logic
│
├── data/
│   ├── yfinance_fetcher.py      # Yahoo Finance data (free, no login, default)
│   ├── ibkr_fetcher.py          # Live IBKR data via ib_insync
│   ├── mock_fetcher.py          # Synthetic data for testing (--dry-run)
│   └── supabase_client.py       # Trade candidate database
│
├── output/
│   ├── reporter.py              # Terminal table + CSV export
│   ├── telegram_notifier.py     # Telegram alert sender
│   └── telegram_bot.py          # Interactive Telegram bot (20+ commands)
│
└── tools/
    ├── test_greeks.py           # Unit tests for Greeks calculator
    ├── check_supabase.py        # Supabase wiring verification
    ├── check_telegram.py        # Telegram connection test
    └── check_connection.py      # IBKR connection test
```

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp env.example .env
# Edit .env with your Telegram bot token & chat ID (required)
# Optionally add SUPABASE_URL/KEY for trade tracking
```

### 3. Test Without Live Data (Dry Run)
```bash
python scheduler.py --dry-run --once
```

### 4. Run Single Scan (Yahoo Finance — Free, No Login)
```bash
python scheduler.py --once
```

### 5. Start Full Scheduler (3 Daily Scans + Telegram Bot)
```bash
python scheduler.py
```
Scans run automatically at 09:35, 12:45, and 15:00 ET on trading days.
Use Telegram commands (`/scan`, `/results`, `/config`, `/set`) to control the bot interactively.

---

## IBKR Setup

1. **Install TWS** (Trader Workstation) or **IB Gateway** from IBKR's website
2. Enable API: `Edit → Global Configuration → API → Settings`
   - ✅ Enable ActiveX and Socket Clients
   - ✅ Allow connections from localhost only
3. Default ports:
   - TWS Paper: `7497`
   - TWS Live: `7496`
   - IB Gateway Paper: `4002`
   - IB Gateway Live: `4001`
4. The scanner auto-detects the port.

---

## Greeks Reference (Seller's Perspective)

| Greek | What it measures | Ideal range for selling |
|-------|-----------------|------------------------|
| **Delta** | Directional exposure (prob of finishing ITM) | Calls: 0.20–0.35 / Puts: -0.35 to -0.20 |
| **Theta** | Daily time decay EARNED (your income) | Higher = better. Max ~30-45 DTE |
| **Vega** | P&L sensitivity to IV changes | Lower = safer. High vega = risk if IV spikes |
| **Gamma** | Rate of delta change | Avoid high gamma near expiry |
| **IV Rank** | How expensive options are vs history (0–100) | Sell when IVR > 30 (ideally > 50) |

---

## Scoring System

Each opportunity is scored 0–100 using a weighted 6-factor composite:

| Factor | Weight | Logic |
|--------|--------|-------|
| IV | 15% | Raw implied volatility — higher = richer premium |
| Theta Yield | 15% | Daily theta / premium received |
| Delta Safety | 20% | How far OTM |
| Liquidity | 10% | Open interest + tight spread |
| Ann. Return | 25% | Return on capital, annualised |
| Mean Reversion | 15% | Price momentum/displacement timing |

When mean reversion is disabled (`set use_mean_reversion false`), the remaining 5 weights are automatically re-normalised.
Adjust weights in `core/config.py` or via Telegram `/set`.

---

## Tuning the Scanner

Edit `core/config.py`:

```python
# Widen delta range to get more results
cc_delta_min = 0.15    # default 0.20
cc_delta_max = 0.45    # default 0.40

# Lower IV Rank threshold
min_iv_rank = 20       # default 30

# Accept lower premium
min_premium = 0.10     # default 0.20
```

---

## Roadmap → Automated Trading Bot

This scanner is designed as **Phase 1** of a full automated trading system:

```
Phase 1 (NOW): Sell Option Scanner ← you are here
      ↓
Phase 2: Add position tracking (open/close management)
      ↓
Phase 3: Auto-execution via IBKR placeOrder()
      ↓
Phase 4: Risk management (portfolio delta, max loss rules)
      ↓
Phase 5: Full Wheel Strategy automation (CSP → CC → repeat)
```

### Adding Auto-Execution (Phase 3 Preview)
```python
# In ibkr_fetcher.py, add:
from ib_insync import MarketOrder, LimitOrder

def place_sell_order(self, contract: OptionContract, limit_price: float):
    ib_contract = Option(
        contract.ticker, contract.expiry.strftime("%Y%m%d"),
        contract.strike, contract.option_type, "SMART"
    )
    order = LimitOrder("SELL", 1, limit_price)  # 1 contract = 100 shares
    trade = self.ib.placeOrder(ib_contract, order)
    return trade
```

---

## Running Tests
```bash
pip install pytest
pytest tools/test_greeks.py -v
```

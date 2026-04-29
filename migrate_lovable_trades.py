"""
migrate_lovable_trades.py — Import historical Lovable trades into Supabase trade_log
=====================================================================================
USE THIS ONCE to import your 37 historical trades from Lovable into Supabase.

HOW TO USE:
  1. Export your trades from Lovable as a CSV file
     (Lovable → your trade journal → Export / Download as CSV)

  2. Save the CSV file in this folder as:   lovable_trades.csv

  3. Run this script:
       python3 migrate_lovable_trades.py

  4. It will show you a preview of what it found, then ask for confirmation
     before writing anything to Supabase.

WHAT IT DOES:
  - Reads your Lovable CSV
  - Maps each row to the trade_log table columns
  - Skips rows that already exist (safe to run multiple times)
  - Shows a full summary before writing

NOTES:
  - Lovable CSV column names may vary — the script tries common names
  - Any columns it cannot map will be shown so you can fix them manually
  - All exit/PnL fields are optional — blank = open trade

REQUIRES:
  - pip3 install supabase python-dotenv
  - .env file with SUPABASE_URL and SUPABASE_KEY
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path

# ── Load .env ─────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # Manual .env read below

if not os.getenv("SUPABASE_URL"):
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# ── Supabase ──────────────────────────────────────────────────────
try:
    from supabase import create_client
except ImportError:
    print("❌  supabase library not installed.  Run:  pip3 install supabase")
    sys.exit(1)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌  SUPABASE_URL or SUPABASE_KEY missing from .env")
    sys.exit(1)

db = create_client(SUPABASE_URL, SUPABASE_KEY)

# ══════════════════════════════════════════════════════════════════
# COLUMN MAPPING
# Lovable may use different column names — we try all common variants
# ══════════════════════════════════════════════════════════════════

# Each entry: (supabase_column, [list of Lovable CSV header names to try])
COLUMN_MAP = [
    ("trade_date",    ["trade_date", "date", "Date", "entry_date", "Trade Date", "Entry Date"]),
    ("ticker",        ["ticker", "Ticker", "symbol", "Symbol", "stock", "Stock"]),
    ("strategy",      ["strategy", "Strategy", "type", "Type", "trade_type", "Trade Type"]),
    ("strike",        ["strike", "Strike", "strike_price", "Strike Price"]),
    ("expiry",        ["expiry", "Expiry", "expiration", "Expiration", "exp_date", "Exp Date"]),
    ("dte_at_entry",  ["dte_at_entry", "dte", "DTE", "days_to_expiry", "Days to Expiry"]),
    ("entry_price",   ["entry_price", "Entry Price", "entry", "Entry", "price", "Price",
                       "underlying_price", "stock_price"]),
    ("contracts",     ["contracts", "Contracts", "quantity", "Quantity", "qty", "Qty"]),
    ("entry_delta",   ["entry_delta", "delta", "Delta"]),
    ("iv_percentile", ["iv_percentile", "iv_rank", "IV Rank", "iv_percentile", "IV%", "IV Percentile"]),
    ("net_premium",   ["net_premium", "Net Premium", "premium", "Premium", "credit", "Credit",
                       "net_credit", "Net Credit", "total_premium", "Total Premium"]),
    # Exit fields — filled manually in TOS, may or may not be in CSV
    ("exit_date",     ["exit_date", "Exit Date", "close_date", "Close Date", "expiry_date"]),
    ("exit_price",    ["exit_price", "Exit Price", "close_price", "Close Price",
                       "buy_back_price", "Buyback Price"]),
    ("pnl",           ["pnl", "PnL", "P&L", "p&l", "profit_loss", "Profit/Loss",
                       "profit", "Profit", "realized_pnl", "Realized PnL",
                       "net_profit", "Net Profit", "P/L"]),
    ("notes",         ["notes", "Notes", "comment", "Comment", "remarks", "Remarks"]),
]


def find_column(headers, candidates):
    """Return the first CSV header that matches any of the candidate names."""
    for c in candidates:
        if c in headers:
            return c
    return None


def normalise_strategy(raw: str) -> str:
    """Normalise strategy string to match bot convention."""
    r = (raw or "").strip().upper().replace("-", "_").replace(" ", "_")
    if "CC" in r or "COVERED" in r or "CALL" in r:
        return "COVERED_CALL"
    if "CSP" in r or "PUT" in r or "SECURED" in r or "CASH" in r:
        return "CASH_SECURED_PUT"
    return raw.strip()  # return as-is if unrecognised


def parse_float(val):
    if val is None or str(val).strip() in ("", "—", "N/A", "n/a", "None"):
        return None
    try:
        return float(str(val).replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def parse_int(val):
    f = parse_float(val)
    return int(f) if f is not None else None


def parse_date(val):
    if not val or str(val).strip() in ("", "—", "N/A"):
        return None
    v = str(val).strip()
    # Try common date formats
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%b %d, %Y",
                "%B %d, %Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return v  # return as-is if unparseable


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    csv_path = Path(__file__).parent / "lovable_trades.csv"
    if not csv_path.exists():
        print(f"""
❌  CSV file not found: {csv_path.name}

Steps:
  1. Export your trades from Lovable as CSV
  2. Save the file in this folder as:  lovable_trades.csv
  3. Run this script again
""")
        sys.exit(1)

    print(f"\n📂  Reading {csv_path.name} ...")

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)
        headers  = reader.fieldnames or []

    if not raw_rows:
        print("❌  CSV file is empty.")
        sys.exit(1)

    print(f"    Found {len(raw_rows)} rows")
    print(f"    CSV headers: {headers}\n")

    # ── Build column mapping for THIS specific CSV ──────────────
    col_map   = {}
    missing   = []
    for supa_col, candidates in COLUMN_MAP:
        found = find_column(headers, candidates)
        if found:
            col_map[supa_col] = found
        else:
            missing.append(supa_col)

    print("✅  Mapped columns:")
    for k, v in col_map.items():
        print(f"    {k:20s} ← CSV column: '{v}'")

    if missing:
        print(f"\n⚠️   Columns NOT found in CSV (will be NULL):")
        for m in missing:
            print(f"    {m}")

    # ── Convert rows ─────────────────────────────────────────────
    records = []
    errors  = []
    for i, row in enumerate(raw_rows, start=1):
        try:
            rec = {}
            for supa_col, csv_col in col_map.items():
                raw = row.get(csv_col)
                if supa_col in ("trade_date", "exit_date"):
                    rec[supa_col] = parse_date(raw)
                elif supa_col in ("strike", "entry_price", "exit_price",
                                   "entry_delta", "iv_percentile", "net_premium", "pnl"):
                    rec[supa_col] = parse_float(raw)
                elif supa_col in ("dte_at_entry", "contracts"):
                    rec[supa_col] = parse_int(raw)
                elif supa_col == "strategy":
                    rec[supa_col] = normalise_strategy(raw)
                else:
                    rec[supa_col] = str(raw).strip() if raw else None

            # Required fields check
            if not rec.get("ticker"):
                errors.append(f"Row {i}: missing ticker — skipped")
                continue
            if not rec.get("trade_date"):
                errors.append(f"Row {i}: missing trade_date — skipped")
                continue

            # Default contracts to 1 if missing
            if rec.get("contracts") is None:
                rec["contracts"] = 1

            records.append(rec)
        except Exception as e:
            errors.append(f"Row {i}: parse error — {e}")

    print(f"\n📋  Preview ({len(records)} valid rows, {len(errors)} skipped):\n")
    print(f"  {'#':>3}  {'Date':<12}  {'Ticker':<6}  {'Strategy':<16}  {'Strike':>8}  {'Expiry':<12}  {'Premium':>10}  {'PnL':>10}")
    print("  " + "─"*85)
    for i, r in enumerate(records[:20], 1):  # show first 20
        print(
            f"  {i:>3}  {str(r.get('trade_date','')):<12}  "
            f"{str(r.get('ticker','')):<6}  "
            f"{str(r.get('strategy','')):<16}  "
            f"{str(r.get('strike','') or '—'):>8}  "
            f"{str(r.get('expiry','') or '—'):<12}  "
            f"{'$'+str(r.get('net_premium','')) if r.get('net_premium') else '—':>10}  "
            f"{'$'+str(r.get('pnl','')) if r.get('pnl') is not None else '—':>10}"
        )
    if len(records) > 20:
        print(f"  ... and {len(records)-20} more rows")

    if errors:
        print(f"\n⚠️   Skipped rows:")
        for e in errors:
            print(f"    {e}")

    # ── Confirm ──────────────────────────────────────────────────
    print(f"\n{'─'*50}")
    print(f"Ready to write {len(records)} trades to Supabase trade_log.")
    answer = input("Proceed? (yes/no): ").strip().lower()
    if answer not in ("yes", "y"):
        print("Cancelled — nothing written.")
        sys.exit(0)

    # ── Write to Supabase ────────────────────────────────────────
    print(f"\n📤  Writing to Supabase...")
    inserted = 0
    updated  = 0
    failed   = 0

    # Exit/PnL fields to update on existing rows
    UPDATE_FIELDS = ["pnl", "exit_date", "exit_price", "notes"]

    for rec in records:
        try:
            # Check if already exists (by ticker + trade_date + strategy)
            existing = (
                db.table("trade_log")
                .select("id")
                .eq("ticker",     rec.get("ticker",""))
                .eq("trade_date", rec.get("trade_date",""))
                .eq("strategy",   rec.get("strategy",""))
                .execute()
            )
            if existing.data:
                # Update exit/PnL fields only (don't overwrite entry data)
                update_payload = {
                    k: rec[k] for k in UPDATE_FIELDS
                    if k in rec and rec[k] is not None
                }
                if update_payload:
                    row_id = existing.data[0]["id"]
                    db.table("trade_log").update(update_payload).eq("id", row_id).execute()
                    updated += 1
                    print(f"  🔄  {rec.get('trade_date')}  {rec.get('ticker')}  updated PnL/exit data")
                continue

            db.table("trade_log").insert(rec).execute()
            inserted += 1
            print(f"  ✅  {rec.get('trade_date')}  {rec.get('ticker')}  {rec.get('strategy')}")
        except Exception as e:
            failed += 1
            print(f"  ❌  {rec.get('trade_date')} {rec.get('ticker')}: {e}")

    print(f"\n{'═'*50}")
    print(f"  Inserted : {inserted}")
    print(f"  Updated  : {updated}  (PnL/exit data filled in)")
    print(f"  Failed   : {failed}")
    print(f"{'═'*50}")

    if inserted > 0:
        print("\n✅  Done! Refresh your TOS dashboard to see the imported trades.")
    else:
        print("\nNo new trades were inserted.")


if __name__ == "__main__":
    main()

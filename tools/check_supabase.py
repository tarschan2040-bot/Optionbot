"""
tools/check_supabase.py — Supabase Wiring Test
==============================================
Run this BEFORE bot startup to verify Supabase is correctly wired.

Tests every operation the bot uses:
  1. Connection / credentials
  2. write_candidates   — insert test row into trade_candidates
  3. get_starred        — read starred rows
  4. star / approve     — status transitions
  5. place_candidate    — write to trade_log
  6. Cleanup            — delete test rows

Usage (Mac Mini):
  cd /path/to/optionbot
  python3 tools/check_supabase.py

Expected output (all green):
  [1/6] ✅ Connection ...
  [2/6] ✅ write_candidates ...
  [3/6] ✅ get_starred ...
  [4/6] ✅ approve_candidate ...
  [5/6] ✅ place_candidate → trade_log ...
  [6/6] ✅ Cleanup ...
  ════════════════════════
  All tests PASSED ✅
"""

import sys
import os

# Allow running from any directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from datetime import datetime, date
from data.supabase_client import SupabaseClient

PASS = "✅"
FAIL = "❌"
SEP  = "════════════════════════════════════════"

errors = []

def check(label, result, detail=""):
    status = PASS if result else FAIL
    print(f"  {status}  {label}" + (f"  — {detail}" if detail else ""))
    if not result:
        errors.append(label)
    return result


print()
print(SEP)
print("  OptionBot Supabase Wiring Test")
print(SEP)
print()

# ── Init ──────────────────────────────────────────────────────────────────────
sb = SupabaseClient()
if not sb.is_enabled():
    print(f"  {FAIL}  Supabase client failed to initialise.")
    print("       Check SUPABASE_URL and SUPABASE_KEY in .env")
    sys.exit(1)

print(f"  {PASS}  Client initialised (URL: {os.getenv('SUPABASE_URL', 'not set')})")
print()

# ── Test 1: Connection ────────────────────────────────────────────────────────
print("[1/6] Connection test")
ok = sb.test_connection()
check("SELECT from trade_candidates", ok,
      "table exists and credentials valid" if ok else "check RLS / anon key")
print()

# ── Test 2: write_candidates (insert) ────────────────────────────────────────
print("[2/6] write_candidates — insert test row")
now = datetime.now()

# Build a minimal fake opportunity object the same way scanner.py does
class FakeContract:
    ticker = "TEST_BOT"
    strategy = "CSP"
    strike = 999.0
    expiry = "2099-01-17"
    dte = 30
    mid = 1.25

class FakeGreeks:
    delta = -0.25
    theta = -0.04

class FakeOpportunity:
    contract = FakeContract()
    greeks = FakeGreeks()
    strategy = "CSP"
    score = 72.5
    iv_rank = 45.0
    annualised_return = 0.18

inserted, auto_starred = sb.write_candidates(
    [FakeOpportunity()],
    scan_time=now,
    top_n=1,
    autostar_threshold=80.0,   # score=72.5 → should be 'pending'
)
check("Insert 1 test candidate", inserted == 1, f"inserted={inserted}")
check("Not auto-starred (score 72.5 < 80)", auto_starred == 0, f"auto_starred={auto_starred}")
print()

# ── Test 3: get_starred (read) ────────────────────────────────────────────────
print("[3/6] get starred/pending candidates")
# The test row is 'pending'; fetch it via direct query
try:
    resp = sb._client.table("trade_candidates") \
        .select("id, ticker, status, score") \
        .eq("ticker", "TEST_BOT") \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()
    rows = resp.data or []
    check("TEST_BOT row found", len(rows) == 1,
          f"status={rows[0]['status']} score={rows[0]['score']}" if rows else "no rows")
    test_id = rows[0]["id"] if rows else None
except Exception as e:
    check("Fetch TEST_BOT row", False, str(e))
    test_id = None
print()

if not test_id:
    print("  ⚠️  No test row ID — skipping remaining tests")
    sys.exit(1)

# ── Test 4: star → approve transitions ───────────────────────────────────────
print("[4/6] Status transitions: pending → starred → approved")
ok = sb.star_candidate(test_id)
check("star_candidate()", ok, "pending → starred")

ok = sb.approve_candidate(test_id)
check("approve_candidate()", ok, "starred → approved")

# Verify it's now in approved list
approved = sb.get_approved()
match = any(r["id"] == test_id for r in approved)
check("Row appears in get_approved()", match, f"{len(approved)} total approved rows")
print()

# ── Test 5: place_candidate → trade_log ──────────────────────────────────────
print("[5/6] place_candidate — write to trade_log")
entry_price = 1.18   # simulated option fill price

ok = sb.place_candidate(test_id, entry_price=entry_price)
check("place_candidate() returned True", ok)

# Verify trade_log row was written
try:
    resp = sb._client.table("trade_log") \
        .select("id, ticker, entry_price, net_premium, candidate_id") \
        .eq("candidate_id", test_id) \
        .execute()
    tl_rows = resp.data or []
    check("trade_log row inserted", len(tl_rows) == 1,
          f"entry_price={tl_rows[0].get('entry_price')} "
          f"net_premium={tl_rows[0].get('net_premium')}" if tl_rows else "no rows")
    tl_id = tl_rows[0]["id"] if tl_rows else None
except Exception as e:
    check("trade_log row inserted", False, str(e))
    tl_id = None
print()

# ── Test 6: Cleanup ───────────────────────────────────────────────────────────
print("[6/6] Cleanup — delete test rows")
cleaned = 0
try:
    if tl_id:
        sb._client.table("trade_log") \
            .delete().eq("id", tl_id).execute()
        cleaned += 1
    sb._client.table("trade_candidates") \
        .delete().eq("ticker", "TEST_BOT").execute()
    cleaned += 1
    check("Test rows deleted", cleaned == 2, f"{cleaned} table(s) cleaned")
except Exception as e:
    check("Cleanup", False, str(e))
print()

# ── Summary ───────────────────────────────────────────────────────────────────
print(SEP)
if not errors:
    print(f"  ✅  All tests PASSED — Supabase wiring is good!")
    print(f"      write_candidates / star / approve / place_candidate / trade_log")
    print(f"      all working against: {os.getenv('SUPABASE_URL', 'unknown')}")
else:
    print(f"  ❌  {len(errors)} test(s) FAILED:")
    for e in errors:
        print(f"      • {e}")
    print()
    print("  Troubleshooting:")
    print("  1. Confirm SUPABASE_URL and SUPABASE_KEY in .env")
    print("  2. Check Supabase table names / column names in SQL editor")
    print("  3. Ensure RLS is disabled (or anon role has insert/select/delete)")
print(SEP)
print()

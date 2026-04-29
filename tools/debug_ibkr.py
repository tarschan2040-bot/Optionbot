import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")

from ib_insync import IB, Stock, Option, util

ib = IB()

print("\n=== Trying to connect to TWS ===")
try:
    ib.connect("127.0.0.1", 7497, clientId=11)
    print("✅ Connected!\n")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    exit(1)

# Test 1: Get SPY price
print("=== Test 1: Getting SPY price ===")
try:
    spy = Stock("SPY", "SMART", "USD")
    ib.qualifyContracts(spy)
    [ticker] = ib.reqTickers(spy)
    price = ticker.marketPrice()
    print(f"✅ SPY price: ${price}\n")
except Exception as e:
    print(f"❌ Failed: {e}\n")

# Test 2: Get option chain for SPY
print("=== Test 2: Getting SPY option chain ===")
try:
    spy = Stock("SPY", "SMART", "USD")
    ib.qualifyContracts(spy)
    chains = ib.reqSecDefOptParams("SPY", "", spy.secType, spy.conId)
    if chains:
        chain = [c for c in chains if c.exchange == "SMART"]
        if chain:
            c = chain[0]
            print(f"✅ Found option chain!")
            print(f"   Expirations (first 5): {list(c.expirations)[:5]}")
            print(f"   Strikes (sample): {sorted(list(c.strikes))[len(list(c.strikes))//2 - 2 : len(list(c.strikes))//2 + 3]}")
        else:
            print(f"❌ No SMART exchange chain found. Available: {[c.exchange for c in chains]}")
    else:
        print("❌ No option chain returned at all")
except Exception as e:
    print(f"❌ Failed: {e}\n")

# Test 3: Get a single option quote
print("\n=== Test 3: Getting a single SPY option quote ===")
try:
    from datetime import date, timedelta
    spy_price = float(str(price).replace("nan", "0") or 510)
    strike = round(spy_price * 0.98 / 5) * 5  # nearest 5-dollar strike ~2% OTM

    # nearest Friday expiry
    today = date.today()
    days_ahead = (4 - today.weekday()) % 7
    if days_ahead < 7:
        days_ahead += 7
    expiry = (today + timedelta(days=days_ahead)).strftime("%Y%m%d")

    print(f"   Trying: SPY PUT strike=${strike} expiry={expiry}")
    opt = Option("SPY", expiry, strike, "P", "SMART", "USD")
    ib.qualifyContracts(opt)
    td = ib.reqMktData(opt, genericTickList="106", snapshot=True)
    ib.sleep(2)
    print(f"   Bid: {td.bid}  Ask: {td.ask}  IV: {td.impliedVolatility}")
    if td.bid and td.bid > 0:
        print("✅ Got live option quote!")
    else:
        print("⚠️  Quote returned but bid=0 — may need market data subscription")
except Exception as e:
    print(f"❌ Failed: {e}")

ib.disconnect()
print("\n=== Debug complete ===")

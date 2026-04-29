import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

"""
debug_prices.py — Run this to see exactly what price data IBKR returns
for each ticker with delayed data mode.
Usage: py -3.11 debug_prices.py
"""

import math
import time

try:
    from ib_insync import IB, Stock
except ImportError:
    print("ERROR: ib_insync not installed")
    sys.exit(1)

TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "AMD"]

ib = IB()
print("Connecting to TWS...")
ib.connect("127.0.0.1", 7497, clientId=99)
print("Connected!")

# Set delayed frozen data
ib.reqMarketDataType(3)
print("Market data type set to 3 (delayed frozen)\n")

for ticker in TICKERS:
    print(f"--- {ticker} ---")
    stock = Stock(ticker, "SMART", "USD")
    ib.qualifyContracts(stock)
    
    td = ib.reqMktData(stock, "", False, False)
    ib.sleep(3)
    
    def safe(v):
        try:
            f = float(v)
            return f"${f:.2f}" if not math.isnan(f) and f > 0 else f"nan/zero ({v})"
        except (TypeError, ValueError):
            return f"N/A ({v})"
    
    print(f"  last:         {safe(td.last)}")
    print(f"  close:        {safe(td.close)}")
    print(f"  bid:          {safe(td.bid)}")
    print(f"  ask:          {safe(td.ask)}")
    print(f"  delayedLast:  {safe(getattr(td, 'delayedLast', 'N/A'))}")
    print(f"  delayedClose: {safe(getattr(td, 'delayedClose', 'N/A'))}")
    
    ib.cancelMktData(stock)
    time.sleep(1)

ib.disconnect()
print("\nDone.")

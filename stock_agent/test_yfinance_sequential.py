import yfinance as yf
import time

tickers = ["AAPL", "MSFT", "GOOG", "AMZN", "NVDA"]

print("Testing sequential yfinance access...")
for ticker in tickers:
    try:
        print(f"Fetching {ticker}...", end=" ", flush=True)
        # Fetch just history start
        # Use a session or just standard call
        # Try to avoid 'info' as it's heavy. History metadata often lighter?
        # Actually 'info' is what we need for IPO date if possible, but history start is better proxy for 'trading'
        
        # Accessing .history()
        # period="max" might trigger big download.
        # But we only need start date.
        
        dat = yf.Ticker(ticker)
        # Fast history check?
        hist = dat.history(period="max")
        if not hist.empty:
            start = hist.index[0]
            print(f"Success. Start: {start.date()}")
        else:
            print("Empty history.")
            
        time.sleep(2) # Be nice
    except Exception as e:
        print(f"Failed: {e}")
        time.sleep(5) # Backoff

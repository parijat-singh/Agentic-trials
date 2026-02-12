import yfinance as yf

try:
    # Fetch max history to check if start date is accessible
    hist = yf.download("AAPL", period="max", progress=False)
    if not hist.empty:
        print(f"Success! History start: {hist.index[0]}")
    else:
        print("Failed: Empty history")
except Exception as e:
    print(f"Failed: {e}")

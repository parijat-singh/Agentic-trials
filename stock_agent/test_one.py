import yfinance as yf
try:
    info = yf.Ticker("AAPL").info
    print(f"Success! AAPL Market Cap: {info.get('marketCap')}")
except Exception as e:
    print(f"Failed: {e}")

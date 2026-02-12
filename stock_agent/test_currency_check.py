import yfinance as yf

def check_currency(symbol):
    print(f"\nChecking {symbol}...")
    try:
        ticker = yf.Ticker(symbol)
        # Access fast_info keys
        # fast_info is a LazyLoader, keys might include 'currency', 'exchange'
        currency = ticker.fast_info.get('currency', 'Unknown')
        exchange = ticker.fast_info.get('exchange', 'Unknown')
        print(f"  Currency: {currency}")
        print(f"  Exchange: {exchange}")
        
        if currency == 'USD':
            print("  -> Passed US Filter")
        else:
            print("  -> Failed US Filter")
            
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == "__main__":
    symbols = ["AAPL", "BRK-B", "0700.HK", "688012.SS", "TSM"] # TSM is ADR (US Traded)
    for s in symbols:
        check_currency(s)

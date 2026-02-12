import yfinance as yf

def get_risk_free_rate():
    """
    Fetches the current 10-Year US Treasury Yield (^TNX) from Yahoo Finance.
    Returns the yield as a decimal (e.g., 0.045 for 4.5%).
    """
    try:
        ticker = yf.Ticker("^TNX")
        # Fetch the most recent day's data
        hist = ticker.history(period="1d")
        
        if hist.empty:
            print("Warning: Could not fetch ^TNX data. Defaulting to 4.0% (0.04)")
            return 0.04
            
        # ^TNX is priced in percentage points (e.g., 4.50 means 4.5%)
        # Close is the yield.
        latest_yield = hist['Close'].iloc[-1]
        
        # Convert to decimal
        return latest_yield / 100.0
        
    except Exception as e:
        print(f"Error fetching risk-free rate: {e}. Defaulting to 4.0%")
        return 0.04

if __name__ == "__main__":
    rate = get_risk_free_rate()
    print(f"Current Risk-Free Rate: {rate:.4f} ({rate*100:.2f}%)")

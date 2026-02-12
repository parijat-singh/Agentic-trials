import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import concurrent.futures
from fetch_tickers import get_all_tickers
import os

TEN_YEARS_AGO = datetime.now() - timedelta(days=10*365)

def get_stock_info(ticker):
    """
    Fetches market cap and first trade date for a ticker.
    Returns a dict or None if error.
    """
    try:
        t = yf.Ticker(ticker)
        # Fast info fetch
        info = t.info
        
        # Check first trade date
        # Note: yfinance info often has 'firstTradeDateEpochUtc'.
        # If not, we might need to check history start.
        first_trade = None
        if 'firstTradeDateEpochUtc' in info and info['firstTradeDateEpochUtc']:
            first_trade = datetime.fromtimestamp(info['firstTradeDateEpochUtc'])
        
        # Fallback: check history metadata if info is missing date (slower)
        if not first_trade:
            hist = t.history(period="max")
            if not hist.empty:
                first_trade = hist.index[0]

        if not first_trade:
            return None

        return {
            "Symbol": ticker,
            "MarketCap": info.get("marketCap", 0),
            "FirstTradeDate": first_trade,
            "CompanyName": info.get("shortName", "")
        }
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

def filter_stocks():
    # 1. Get candidate tickers
    if os.path.exists("tickers.txt"):
        with open("tickers.txt", "r") as f:
            tickers = [line.strip() for line in f.readlines()]
    else:
        tickers = get_all_tickers()
    
    # 2. Fetch Info in Parallel (Reduced workers to avoid rate limiting)
    print(f"Fetching info for {len(tickers)} tickers. This may take a moment...")
    results = []
    from tqdm import tqdm
    
    # Use fewer workers to be polite to the API
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(get_stock_info, t): t for t in tickers}
        
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(tickers), desc="Filtering Stocks"):
            res = future.result()
            if res:
                results.append(res)

    df = pd.DataFrame(results)
    
    # 3. Filter for stocks trading <= 10 years
    # Ensure datetimes are timezone-aware/UTC for comparison
    
    if df.empty:
        print("No stocks found! Check API connection or rate limits.")
        return pd.DataFrame() # Return empty to avoid crash
    
    # 3. Filter for stocks trading <= 10 years
    # Ensure datetimes are timezone-aware/UTC for comparison
    # Convert column to UTC
    df['FirstTradeDate'] = pd.to_datetime(df['FirstTradeDate'], utc=True)
    
    # Make reference date UTC
    ten_years_ago_utc = pd.Timestamp.now(tz='UTC') - pd.DateOffset(years=10)
    
    df_new = df[df['FirstTradeDate'] >= ten_years_ago_utc].copy()
    
    # 4. Sort by Market Cap Desc
    df_sorted = df_new.sort_values(by="MarketCap", ascending=False)
    
    # 5. Take Top 100
    top_100 = df_sorted.head(100)
    
    print(f"\nFound {len(df_sorted)} stocks trading < 10 years.")
    print("Top 5 by Market Cap:")
    print(top_100[['Symbol', 'MarketCap', 'FirstTradeDate']].head().to_string())
    
    # Save to CSV
    top_100.to_csv("top_100_new_stocks.csv", index=False)
    print("Saved to top_100_new_stocks.csv")
    
    return top_100

if __name__ == "__main__":
    filter_stocks()

import pandas as pd
import numpy as np
import os
import sys
import glob
import json
from scipy.optimize import minimize

def _sector_in_industries(sector, industries_list):
    """Case-insensitive check if sector is in industries list."""
    if not sector or not industries_list:
        return False
    s = str(sector).strip().lower()
    return s in [str(i).strip().lower() for i in industries_list]

def load_3y_data(data_dir):
    """
    Loads daily close prices for stocks in data_dir.
    Prefers top_50_stocks.csv (P/E-filtered) when available; otherwise uses top_100_new_stocks.csv.
    Applies industry/sector filter from scraping_stats.json when using top_100.
    Returns: DataFrame of prices (Forward Filled).
    """
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    top_50_file = os.path.join(root_dir, "financial_engine", "top_50_stocks.csv")
    meta_file = os.path.join(data_dir, "top_100_new_stocks.csv")
    csv_files = []
    industries_filter = None
    stats_file = os.path.join(data_dir, "scraping_stats.json")
    if os.path.exists(stats_file):
        try:
            with open(stats_file, 'r') as f:
                params = json.load(f).get("Parameters", {})
            industries_filter = params.get("Industries")
            if industries_filter is not None and not isinstance(industries_filter, list):
                industries_filter = [s.strip() for s in str(industries_filter).split(",") if s.strip()] or None
        except Exception:
            pass

    if os.path.exists(top_50_file):
        meta_df = pd.read_csv(top_50_file)
        sym_col = 'Symbol' if 'Symbol' in meta_df.columns else 'symbol'
        if sym_col in meta_df.columns:
            csv_files = [os.path.join(data_dir, f"{s}.csv") for s in meta_df[sym_col]]
            csv_files = [f for f in csv_files if os.path.exists(f)]
        else:
            csv_files = []
        if csv_files:
            print(f"Using top_50 (P/E-filtered) as candidate universe: {len(csv_files)} stocks")

    if not csv_files and os.path.exists(meta_file):
        meta_df = pd.read_csv(meta_file)
        sym_col = 'symbol' if 'symbol' in meta_df.columns else 'Symbol'
        sector_col = 'sector' if 'sector' in meta_df.columns else ('Sector' if 'Sector' in meta_df.columns else None)

        # Enrich sector from DB if missing and industry filter is active
        if industries_filter and (sector_col is None or (sector_col in meta_df.columns and meta_df[sector_col].isna().all())):
            try:
                sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if sys_path not in sys.path:
                    sys.path.insert(0, sys_path)
                from stock_agent.db_manager import DBManager
                db = DBManager()
                sector_col = 'sector'
                meta_df[sector_col] = meta_df[sym_col].map(lambda s: db.get_sector(s) if isinstance(s, str) else None)
            except Exception:
                sector_col = None

        # Filter by sector when industries specified
        if industries_filter and sector_col and sector_col in meta_df.columns:
            before = len(meta_df)
            meta_df = meta_df[meta_df[sector_col].apply(lambda s: _sector_in_industries(s, industries_filter))]
            if len(meta_df) < before:
                print(f"Industry filter (backtester): {before} -> {len(meta_df)} stocks (sectors: {', '.join(industries_filter)})")

        if sym_col in meta_df.columns:
            csv_files = [os.path.join(data_dir, f"{s}.csv") for s in meta_df[sym_col]]
            csv_files = [f for f in csv_files if os.path.exists(f)]
        else:
            csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    elif not csv_files:
        csv_files = glob.glob(os.path.join(data_dir, "*.csv"))

    print(f"Scanning {len(csv_files)} files (from metadata) in {data_dir}...")
    
    price_data = {}
    
    # Calculate 3 years ago date
    # We'll use a rough 756 trading days approximation or date offset
    three_years_ago = pd.Timestamp.now() - pd.DateOffset(years=3)
    
    import concurrent.futures

    def process_file(file_path):
        """Helper to process a single CSV file."""
        try:
            symbol = os.path.basename(file_path).replace(".csv", "")
            df = pd.read_csv(file_path, parse_dates=['Date'], index_col='Date')
            
            # Force index to datetime
            df.index = pd.to_datetime(df.index, utc=True)
            
            # Ensure index is tz-naive
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            
            # Use data if it has at least 1 year of history
            if len(df) < 252:
                return None
                
            # SANITY CHECK: Minimum price filter (exclude penny stock noise)
            if df['Close'].min() < 0.05:
                # print(f"Skipping {symbol}: Price dropped below $0.05 (too volatile).")
                return None
                
            return (symbol, df['Close'])
            
        except Exception:
            return None

    # Parallel Execution
    print(f"Loading files in parallel with up to 20 threads...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_file = {executor.submit(process_file, fp): fp for fp in csv_files}
        
        completed = 0
        total = len(csv_files)
        
        for future in concurrent.futures.as_completed(future_to_file):
            res = future.result()
            if res:
                symbol, series = res
                price_data[symbol] = series
            
            completed += 1
            if completed % 100 == 0:
                 print(f"Loaded {completed}/{total} files...", end='\r', flush=True)

    print(f"Loaded {len(price_data)} valid stocks. combining...")
    
    # Combine
    prices_df = pd.DataFrame(price_data)
    
    if prices_df.empty:
        print("Error: No stocks passed the initial length filter.")
        return pd.DataFrame()

    # Forward fill
    prices_df = prices_df.ffill()
    
    # Filter to last 3 years (OR max available if less)
    # Find the index that is closest to 3 years ago
    last_date = prices_df.index[-1]
    start_date = last_date - pd.DateOffset(years=3)
    
    # If data doesn't go back 3 years, use what we have
    if start_date < prices_df.index[0]:
        print(f"Warning: Full 3 years not available. Using data since {prices_df.index[0].date()}")
        start_date = prices_df.index[0]
    
    # Slice from start_date
    prices_df = prices_df[prices_df.index >= start_date]
    
    # Drop columns that have too many NaNs in this window (e.g. IPOd recently)
    # We require at least 50% valid data in the window (relaxed from 90%)
    threshold = int(len(prices_df) * 0.5)
    prices_df = prices_df.dropna(axis=1, thresh=threshold)
    
    # Drop remaining rows with NaNs (e.g. holidays)
    prices_df = prices_df.dropna()
    
    if prices_df.empty:
         print("Error: DataFrame empty after filtering NaNs.")
         return pd.DataFrame()

    print(f"Loaded {prices_df.shape[1]} stocks with data since {prices_df.index[0].date()}.")
    return prices_df

def filter_consecutive_growth(prices_df):
    """
    Filters for stocks that had positive returns in Year 1, Year 2, and Year 3 individually.
    """
    if prices_df.empty:
        print("Error: No stocks with sufficient 3-year history found.")
        return [], None

    # 2. Filter for Consistency (Consecutive Annual Growth)
    print("\n--- Step 2: Filtering for Consecutive Growth ---")
    consistent_stocks = []
    
    # Resample to yearly
    yearly_returns = prices_df.resample('YE').last().pct_change().dropna()
    
    # We need at least 3 years of returns to check consistency
    if len(yearly_returns) < 3:
         print(f"Warning: Only {len(yearly_returns)} years of data available. Cannot check 3-year consistency strictness. Skipping filter.")
         consistent_stocks = prices_df.columns.tolist() # Fallback
    else:
        # Check last 3 periods
        last_3_years = yearly_returns.iloc[-3:]
        print(f"Checking consistency for years: {last_3_years.index.strftime('%Y').tolist()}")
        
        for stock in prices_df.columns:
            # Check last 3 periods for positive returns
            years_positive = (last_3_years[stock] > 0).all()
            
            # SANITY CHECK: Check for extreme outliers (e.g. > 10,000% gain in a single year)
            # This often indicates data corruption or reverse splits not handled by provider.
            has_extreme_outlier = (last_3_years[stock] > 100.0).any() 
            
            if years_positive and not has_extreme_outlier:
                consistent_stocks.append(stock)
            elif has_extreme_outlier:
                print(f"Rejecting {stock}: Extreme outlier return detected (>10,000% jump).")

    print(f"Found {len(consistent_stocks)} stocks with consecutive annual growth.")
    
    if not consistent_stocks:
        print("No stocks met the consecutive growth criteria. Relaxing filter to 'Positive Cumulative Return'...")
        total_ret = (prices_df.iloc[-1] / prices_df.iloc[0]) - 1
        consistent_stocks = total_ret[total_ret > 0].index.tolist()
        print(f"Found {len(consistent_stocks)} stocks with positive 3-year cumulative return.")

    if not consistent_stocks:
        print("Error: No stocks found even after relaxing criteria.")
        return [], None
    return prices_df[consistent_stocks]

def optimize_total_return(prices_df):
    """
    Finds weights that maximize Total 3Y Cumulative Return.
    Constraint: Max 20% per stock.
    """
    if prices_df.empty:
        return None
        
    # Calculate Total Return for each stock: (End / Start) - 1
    total_returns = (prices_df.iloc[-1] / prices_df.iloc[0]) - 1
    
    def negative_total_return(weights):
        portfolio_return = np.sum(total_returns * weights)
        return -portfolio_return
        
    num_assets = len(prices_df.columns)
    
    # Constraints
    constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
    bounds = tuple((0.0, 0.2) for asset in range(num_assets))
    init_guess = num_assets * [1. / num_assets,]
    
    print("Optimizing for Maximum Total Return...")
    result = minimize(negative_total_return, init_guess, method='SLSQP', bounds=bounds, constraints=constraints)
    
    if not result.success:
        print("Optimization failed.")
        return None
        
    optimal_weights = result.x
    max_return = -result.fun
    
    return optimal_weights, max_return

if __name__ == "__main__":
    pass

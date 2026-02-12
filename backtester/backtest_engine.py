import pandas as pd
import numpy as np
import os
import glob
from scipy.optimize import minimize

def load_3y_data(data_dir):
    """
    Loads daily close prices for all stocks in data_dir.
    Filters for stocks with at least 3 years of data.
    Returns: DataFrame of prices (Forward Filled).
    """
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    print(f"Scanning {len(csv_files)} files in {data_dir}...")
    
    price_data = {}
    
    # Calculate 3 years ago date
    # We'll use a rough 756 trading days approximation or date offset
    three_years_ago = pd.Timestamp.now() - pd.DateOffset(years=3)
    
    for file_path in csv_files:
        try:
            symbol = os.path.basename(file_path).replace(".csv", "")
            df = pd.read_csv(file_path, parse_dates=['Date'], index_col='Date')
            
            # Ensure index is tz-naive
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            
            # Use data if it has at least 1 year of history
            if len(df) < 252:
                continue
                
            price_data[symbol] = df['Close']
            
        except Exception as e:
            continue
            
    # Combine
    prices_df = pd.DataFrame(price_data)
    
    # Forward fill
    prices_df = prices_df.ffill()
    
    # Filter to last 3 years (if available)
    # Find the index that is closest to 3 years ago
    start_date = prices_df.index[-1] - pd.DateOffset(years=3)
    
    # Slice from start_date
    prices_df = prices_df[prices_df.index >= start_date]
    
    # Drop columns that have too many NaNs in this window (e.g. IPOd recently)
    # We require at least 90% valid data in the 3 year window
    threshold = int(len(prices_df) * 0.9)
    prices_df = prices_df.dropna(axis=1, thresh=threshold)
    
    # Drop remaining rows with NaNs (e.g. holidays)
    prices_df = prices_df.dropna()
    
    print(f"Loaded {prices_df.shape[1]} stocks with data since {prices_df.index[0].date()}.")
    return prices_df

def filter_consecutive_growth(prices_df):
    """
    Filters for stocks that had positive returns in Year 1, Year 2, and Year 3 individually.
    """
    # Resample to Yearly ('YE' or 'Y' depending on pandas version, using 'YE' for future proofing or 'Y')
    # We will just split into 3 chunks to be safe and rigorous about "last 3 years"
    
    # Calculate yearly returns
    yearly_prices = prices_df.resample('YE').last()
    
    # Add the starting price (first row of prices_df) as the base for the first year
    # Actually, simpler: Calculate annual pct_change on yearly_prices
    yearly_returns = yearly_prices.pct_change()
    
    # We need to ensure we look at the last 3 complete periods or just check if all are positive
    # Filter columns where ALL yearly returns > 0 (ignoring the first NaN)
    
    consistent_stocks = []
    
    for symbol in yearly_returns.columns:
        # Get returns, drop NaN
        rets = yearly_returns[symbol].dropna()
        
        # Check if all > 0
        if len(rets) >= 2 and (rets > 0).all(): # At least 2-3 years, all positive
             consistent_stocks.append(symbol)
             
    print(f"Found {len(consistent_stocks)} stocks with consecutive annual growth.")
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

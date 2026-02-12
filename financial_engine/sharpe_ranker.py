import pandas as pd
import numpy as np
import os
import glob

def calculate_sharpe_ratio(df, risk_free_rate):
    """
    Calculates Annualized Sharpe Ratio for a given stock DataFrame.
    Assumes 'Close' is the adjusted close price.
    """
    if df.empty or len(df) < 30: # Need some history
        return None, None, None
        
    # Calculate Daily Returns
    # Formula: (P_t / P_t-1) - 1
    # This is equivalent to Total Return including dividends IF the 'Close' is adjusted (standard in yfinance)
    daily_returns = df['Close'].pct_change().dropna()
    
    if daily_returns.empty:
        return None, None, None

    # Annualize
    # Trading days per year = 252
    avg_daily_return = daily_returns.mean()
    std_dev_daily = daily_returns.std()
    
    if std_dev_daily == 0:
        return 0.0, 0.0, 0.0
        
    annualized_return = avg_daily_return * 252
    annualized_volatility = std_dev_daily * np.sqrt(252)
    
    # Sharpe Ratio
    sharpe_ratio = (annualized_return - risk_free_rate) / annualized_volatility
    
    return sharpe_ratio, annualized_return, annualized_volatility

def rank_stocks(data_dir, risk_free_rate):
    """
    Iterates through CSVs in data_dir, calculates Sharpe, and ranks them.
    Returns: DataFrame of Top 50 Stocks.
    """
    results = []
    
    # Find all CSVs
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    print(f"Found {len(csv_files)} stock files in {data_dir}...")
    
    for file_path in csv_files:
        try:
            # Load Data
            df = pd.read_csv(file_path, parse_dates=['Date'], index_col='Date')
            
            # Extract Symbol from filename
            symbol = os.path.basename(file_path).replace(".csv", "")
            
            # Calculate Metrics
            sharpe, ann_ret, ann_vol = calculate_sharpe_ratio(df, risk_free_rate)
            
            if sharpe is not None:
                results.append({
                    'Symbol': symbol,
                    'Sharpe Ratio': sharpe,
                    'Annualized Return': ann_ret,
                    'Annualized Volatility': ann_vol
                })
                
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            continue
            
    # Create DataFrame
    results_df = pd.DataFrame(results)
    
    if results_df.empty:
        print("No valid data processed.")
        return pd.DataFrame()
        
    # Sort by Sharpe Ratio (Descending)
    ranked_df = results_df.sort_values(by='Sharpe Ratio', ascending=False)
    
    # Filter Top 50
    top_50 = ranked_df.head(50)
    
    return top_50

if __name__ == "__main__":
    # Test with dummy data or just run imported
    pass

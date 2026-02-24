import pandas as pd
import numpy as np
from scipy.optimize import minimize
import os


def load_data_from_db(symbols, db):
    """Load historical Close prices for symbols from ETFDB. Returns DataFrame with symbols as columns."""
    price_data = {}
    for sym in symbols:
        df = db.load_history(sym)
        if df.empty or "Close" not in df.columns:
            continue
        price_data[sym] = df["Close"]
    if not price_data:
        return pd.DataFrame()
    prices_df = pd.DataFrame(price_data)
    prices_df = prices_df.ffill().dropna()
    if prices_df.empty:
        prices_df = pd.DataFrame(price_data).ffill().tail(252).dropna()
    return prices_df


def load_data(top_50_file, data_dir):
    """
    Loads historical adjusted close prices for the top 50 stocks.
    """
    try:
        # Load Top 50 list
        top_50_df = pd.read_csv(top_50_file)
        symbols = top_50_df['Symbol'].tolist()
        
        print(f"Loading data for {len(symbols)} stocks...")
        
        price_data = {}
        for symbol in symbols:
            file_path = os.path.join(data_dir, f"{symbol}.csv")
            if os.path.exists(file_path):
                df = pd.read_csv(file_path, parse_dates=['Date'], index_col='Date')
                # Use 'Close' (Assume Adjusted)
                price_data[symbol] = df['Close']
            else:
                print(f"Warning: File for {symbol} not found.")
                
        # Combine into DataFrame
        prices_df = pd.DataFrame(price_data)
        
        # Forward fill missing data (for mismatched holidays/timezones)
        prices_df = prices_df.ffill().dropna()
        
        # If still empty (no common start), take the last 1 year (252 days)
        if prices_df.empty:
             print("Warning: Data empty after initial alignment. Trying last 252 common days...")
             prices_df = pd.DataFrame(price_data).ffill().tail(252).dropna()
        
        print(f"Data loaded. Shape: {prices_df.shape}")
        return prices_df
        
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()

def optimize_portfolio(prices_df, risk_free_rate):
    """
    Performs Mean-Variance Optimization to maximize Sharpe Ratio.
    """
    # 1. Calculate Expected Returns and Covariance
    # Annualized Returns
    daily_returns = prices_df.pct_change().dropna()
    mean_daily_returns = daily_returns.mean()
    cov_matrix = daily_returns.cov()
    
    # 2. Define Objective Function (Minimize Negative Sharpe)
    def negative_sharpe(weights):
        portfolio_return = np.sum(mean_daily_returns * weights) * 252
        portfolio_std_dev = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))) * np.sqrt(252)
        
        # Avoid division by zero
        if portfolio_std_dev == 0:
            return 0
            
        sharpe_ratio = (portfolio_return - risk_free_rate) / portfolio_std_dev
        return -sharpe_ratio

    # 3. Constraints and Bounds
    num_assets = len(prices_df.columns)
    args = ()
    
    # Sum of weights must equal 1
    constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
    
    # Weights between 0 and 0.2 (Max 20% per stock to ensure diversification)
    bounds = tuple((0.0, 0.2) for asset in range(num_assets))
    
    # Initial Guess (Equal weights)
    init_guess = num_assets * [1. / num_assets,]
    
    # 4. Run Optimization
    print("Running optimization...")
    result = minimize(negative_sharpe, init_guess, method='SLSQP', bounds=bounds, constraints=constraints)
    
    if not result.success:
        print(f"Optimization failed: {result.message}")
        return None
        
    optimal_weights = result.x
    optimal_sharpe = -result.fun
    
    # Calculate Portfolio Metrics
    opt_return = np.sum(mean_daily_returns * optimal_weights) * 252
    opt_volatility = np.sqrt(np.dot(optimal_weights.T, np.dot(cov_matrix, optimal_weights))) * np.sqrt(252)
    
    print(f"Optimization Success!")
    print(f"Optimal Sharpe Ratio: {optimal_sharpe:.4f}")
    print(f"Expected Annual Return: {opt_return:.2%}")
    print(f"Expected Annual Volatility: {opt_volatility:.2%}")
    
    # Calculate Detailed Asset Contributions
    # 1. Contribution to Return
    contrib_return = mean_daily_returns * optimal_weights * 252
    
    # 2. Risk Contribution
    # MCR = (Sigma * w) / sigma_p
    # RC = w * MCR
    sigma_w = np.dot(cov_matrix, optimal_weights)
    daily_vol = opt_volatility / np.sqrt(252)
    
    if daily_vol > 0:
        mcr = sigma_w / daily_vol
    else:
        mcr = np.zeros_like(sigma_w)
        
    risk_contribution = optimal_weights * mcr
    # Annualize risk contribution (kind of proportional, but let's keep it as % of total var or vol)
    # Actually customary to sum to total vol. 
    # Let's simple use: RC_annual = RC_daily * sqrt(252)
    risk_contribution_ann = risk_contribution * np.sqrt(252)
    
    # 3. Correlation with Portfolio
    # rho_i_p = cov(i, p) / (sigma_i * sigma_p)
    # cov(i, p) is sigma_w[i]
    asset_stds = np.sqrt(np.diag(cov_matrix))
    correlations = []
    
    for i in range(len(optimal_weights)):
        if asset_stds[i] > 0 and daily_vol > 0:
             corr = sigma_w[i] / (asset_stds[i] * daily_vol)
        else:
             corr = 0
        correlations.append(corr)
    
    # Create Result DataFrame
    portfolio_df = pd.DataFrame({
        'Symbol': prices_df.columns,
        'Weight': optimal_weights,
        'Return Contrib': contrib_return,
        'Risk Contrib': risk_contribution_ann,
        'Correlation': correlations
    })
    
    # Filter out tiny weights
    portfolio_df = portfolio_df[portfolio_df['Weight'] > 0.0001]
    portfolio_df = portfolio_df.sort_values(by='Weight', ascending=False)
    
    return portfolio_df

if __name__ == "__main__":
    pass

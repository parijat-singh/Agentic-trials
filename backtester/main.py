import backtest_engine
import os
import pandas as pd

DATA_DIR = os.path.join("..", "stock_agent", "data")
OUTPUT_FILE = "best_3y_combination.csv"

def main():
    print("=== Backtester: Best Consecutive 3-Year Combination (Module 4) ===")
    
    # 1. Load Data
    print("\n--- Step 1: Loading 3-Year Data ---")
    prices_df = backtest_engine.load_3y_data(DATA_DIR)
    
    if prices_df.empty:
        print("Error: No data loaded.")
        return

    # 2. Filter Consistency
    print("\n--- Step 2: Filtering for Consecutive Growth ---")
    consistent_df = backtest_engine.filter_consecutive_growth(prices_df)
    
    if consistent_df.empty:
        print("No stocks found with consecutive growth in every year.")
        return

    # 3. Optimize (Hindsight)
    print("\n--- Step 3: Finding Best Historical Combination ---")
    weights, max_ret = backtest_engine.optimize_total_return(consistent_df)
    
    if weights is None:
        return
        
    # 4. Results
    print(f"\nOptimization Success!")
    print(f"Max Cumulative 3-Year Return: {max_ret:.2%}")
    
    # Create Result DataFrame
    portfolio_df = pd.DataFrame({
        'Symbol': consistent_df.columns,
        'Weight': weights
    })
    
    # Filter
    portfolio_df = portfolio_df[portfolio_df['Weight'] > 0.0001]
    portfolio_df = portfolio_df.sort_values(by='Weight', ascending=False)
    
    print("\nOptimal Historical Allocation (Last 3 Years):")
    print(portfolio_df.to_string(index=False, formatters={'Weight': '{:.4%}'.format}))
    
    portfolio_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

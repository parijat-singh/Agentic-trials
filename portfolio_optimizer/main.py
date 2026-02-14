import optimizer
import os
import sys

# Add sibling directory to path to import risk_free_rate from previous module
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from financial_engine import risk_free_rate
import config

# Constants
TOP_50_FILE = os.path.join("..", "financial_engine", "top_50_stocks.csv")
DATA_DIR = config.DATA_DIR
OUTPUT_FILE = "optimal_portfolio.csv"

def main():
    print("=== Portfolio Optimizer (Module 3) ===")
    
    # 1. Fetch Risk-Free Rate
    print("\n--- Step 1: Getting Risk-Free Rate ---")
    rf_rate = risk_free_rate.get_risk_free_rate()
    print(f"Risk-Free Rate: {rf_rate:.2%}")
    
    # 2. Load Data
    print("\n--- Step 2: Loading Data for Top 50 Stocks ---")
    if not os.path.exists(TOP_50_FILE):
        print(f"Error: {TOP_50_FILE} not found. Please run Module 2 first.")
        return
        
    prices_df = optimizer.load_data(TOP_50_FILE, DATA_DIR)
    
    if prices_df.empty:
        print("Error: No price data loaded.")
        return

    # 3. Optimize
    print("\n--- Step 3: Optimizing Portfolio (Mean-Variance Analysis) ---")
    optimal_portfolio = optimizer.optimize_portfolio(prices_df, rf_rate)
    
    if optimal_portfolio is None:
        print("Optimization failed.")
        return
        
    # 4. Save
    print(f"\n--- Step 4: Saving Results to {OUTPUT_FILE} ---")
    optimal_portfolio.to_csv(OUTPUT_FILE, index=False)
    print("Success!")
    
    # 5. Display
    print("\nOptimal Portfolio Allocation:")
    print(optimal_portfolio.to_string(index=False, formatters={'Weight': '{:.4%}'.format}))

if __name__ == "__main__":
    main()

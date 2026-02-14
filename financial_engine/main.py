import risk_free_rate
import sharpe_ranker
import os
import pandas as pd
import sys

# Add parent directory to path to import config
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import config

# Constants
DATA_DIR = config.DATA_DIR
OUTPUT_FILE = "top_50_stocks.csv"

def main():
    print("=== Financial Calculation Engine (Module 2) ===")
    
    # 1. Fetch Risk-Free Rate
    print("\n--- Step 1: Fetching Risk-Free Rate ---")
    rf_rate = risk_free_rate.get_risk_free_rate()
    print(f"Risk-Free Rate (10Y Treasury): {rf_rate:.2%}")
    
    # 2. Process Stocks and Rank
    print("\n--- Step 2: Calculating Sharpe Ratios & Ranking ---")
    if not os.path.exists(DATA_DIR):
        print(f"Error: Data directory not found at {DATA_DIR}")
        return
        
    top_50 = sharpe_ranker.rank_stocks(DATA_DIR, rf_rate)
    
    if top_50.empty:
        print("No stocks passed filtering.")
        return
        
    # 3. Save Results
    print(f"\n--- Step 3: Saving Top 50 to {OUTPUT_FILE} ---")
    top_50.to_csv(OUTPUT_FILE, index=False)
    print("Success!")
    
    # 4. Preview
    print("\nTop 10 Stocks by Sharpe Ratio:")
    print(top_50.head(10).to_string(index=False))

if __name__ == "__main__":
    main()

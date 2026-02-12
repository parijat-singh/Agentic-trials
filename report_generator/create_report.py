import pandas as pd
import os
import datetime

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

FILE_TOP_100 = os.path.join(ROOT_DIR, "stock_agent", "data", "top_100_new_stocks.csv")
FILE_TOP_50 = os.path.join(ROOT_DIR, "financial_engine", "top_50_stocks.csv")
FILE_OPTIMAL = os.path.join(ROOT_DIR, "portfolio_optimizer", "optimal_portfolio.csv")
FILE_BACKTEST = os.path.join(ROOT_DIR, "backtester", "best_3y_combination.csv")
OUTPUT_FILE = os.path.join(ROOT_DIR, "FINAL_REPORT.md")

def generate_markdown():
    print("Generating Final Report...")
    
    with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
        # Title
        f.write(f"# Financial Analysis Report\n")
        f.write(f"**Date:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        
        f.write("---\n\n")
        
        # Section 1: Stock candidates
        f.write("## 1. Candidate Selection (Module 1)\n")
        f.write("Goal: Identify large-cap stocks (<10 years old).\n\n")
        if os.path.exists(FILE_TOP_100):
            df = pd.read_csv(FILE_TOP_100)
            f.write(f"- **Total Candidates Found:** {len(df)}\n")
            f.write(f"- **Criteria:** Market Cap > Initial Threshold, Trading < 10 Years.\n\n")
        else:
            f.write("Status: Data not found.\n\n")
            
        f.write("---\n\n")

        # Section 2: Financial Metrics
        f.write("## 2. Risk-Adjusted Ranking (Module 2)\n")
        f.write("Goal: Filter Top 50 by Sharpe Ratio.\n\n")
        if os.path.exists(FILE_TOP_50):
            df = pd.read_csv(FILE_TOP_50)
            f.write(f"- **Top Stock:** {df.iloc[0]['Symbol']} (Sharpe: {df.iloc[0]['Sharpe Ratio']:.2f})\n\n")
            f.write("**Top 10 Ranked Stocks:**\n\n")
            f.write(df.head(10).to_markdown(index=False))
            f.write("\n\n")
        else:
            f.write("Status: Data not found.\n\n")
            
        f.write("---\n\n")

        # Section 3: Optimal Portfolio
        f.write("## 3. Optimized Portfolio (Module 3)\n")
        f.write("Goal: Maximize forward-looking Sharpe Ratio using Mean-Variance Optimization.\n")
        f.write("Constraint: Max 20% allocation per stock.\n\n")
        if os.path.exists(FILE_OPTIMAL):
            df = pd.read_csv(FILE_OPTIMAL)
            f.write("**Recommended Allocation:**\n\n")
            # Format weights as percentage
            df['Weight'] = df['Weight'].apply(lambda x: f"{x:.2%}")
            f.write(df.to_markdown(index=False))
            f.write("\n\n")
        else:
            f.write("Status: Data not found.\n\n")
            
        f.write("---\n\n")

        # Section 4: Historic Winner
        f.write("## 4. Historical Backtest Criteria (Module 4)\n")
        f.write("Goal: Find the combination with the highest consecutive 3-year return.\n\n")
        if os.path.exists(FILE_BACKTEST):
            df = pd.read_csv(FILE_BACKTEST)
            f.write("**Winning Historical Combination (Past 3 Years):**\n\n")
            df['Weight'] = df['Weight'].apply(lambda x: f"{x:.2%}")
            f.write(df.to_markdown(index=False))
            f.write("\n\n")
        else:
            f.write("Status: Data not found.\n\n")
            
    print(f"Report saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    if not os.path.exists("report_generator"): # Just in case running from root
        pass
    generate_markdown()

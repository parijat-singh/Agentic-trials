import pandas as pd
import numpy as np
import os
import datetime
import shutil

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

FILE_TOP_100 = os.path.join(ROOT_DIR, "stock_agent", "data", "top_100_new_stocks.csv")
FILE_TOP_50 = os.path.join(ROOT_DIR, "financial_engine", "top_50_stocks.csv")
FILE_OPTIMAL = os.path.join(ROOT_DIR, "portfolio_optimizer", "optimal_portfolio.csv")
FILE_BACKTEST = os.path.join(ROOT_DIR, "backtester", "best_3y_combination.csv")
OUTPUT_FILE = os.path.join(ROOT_DIR, "FINAL_REPORT.md")
ARCHIVE_DIR = os.path.join(ROOT_DIR, "reports_archive")
LOG_FILE = os.path.join(ROOT_DIR, "REPORT_LOG.md")
DATA_DIR = os.path.join(ROOT_DIR, "stock_agent", "data")

# --- Helper Functions for Yearly Analysis ---
def load_portfolio(file_path):
    if not os.path.exists(file_path):
        return None
    df = pd.read_csv(file_path)
    if 'Symbol' not in df.columns:
        df.columns = ['Symbol', 'Weight']
    try:
        if df['Weight'].dtype == object and df['Weight'].str.contains('%').any():
            df['Weight'] = df['Weight'].str.rstrip('%').astype(float) / 100.0
    except AttributeError:
        pass
    return df.set_index('Symbol')['Weight'].to_dict()

def get_price_data(symbols, valid_start_date="2023-01-01"):
    data = {}
    for symbol in symbols:
        try:
            path = os.path.join(DATA_DIR, f"{symbol}.csv")
            if not os.path.exists(path): continue
            df = pd.read_csv(path, parse_dates=['Date'], index_col='Date')
            df.index = pd.to_datetime(df.index, utc=True).tz_localize(None)
            data[symbol] = df['Close']
        except Exception:
            continue
    
    if not data: return pd.DataFrame()
    df_prices = pd.DataFrame(data)
    df_prices.sort_index(inplace=True)
    return df_prices[df_prices.index >= valid_start_date]

def calculate_metrics(portfolio_weights, price_data):
    relevant_prices = price_data[list(portfolio_weights.keys())].dropna()
    if relevant_prices.empty: return {}

    total_weight = sum(portfolio_weights.values())
    clean_weights = {k: v/total_weight for k, v in portfolio_weights.items()}
    
    daily_returns = relevant_prices.pct_change().dropna()
    if daily_returns.empty: return {}
        
    portfolio_daily_ret = daily_returns.dot(pd.Series(clean_weights))
    years = portfolio_daily_ret.index.year.unique()
    results = {}
    
    for year in years:
        idx = portfolio_daily_ret.index.year == year
        year_returns = portfolio_daily_ret.loc[idx]
        if len(year_returns) < 10: continue
            
        total_ret = (1 + year_returns).prod() - 1
        vol = year_returns.std() * np.sqrt(252)
        sharpe = (year_returns.mean() * 252) / vol if vol != 0 else 0
        
        results[year] = {
            "Return": total_ret,
            "Volatility": vol,
            "Sharpe": sharpe
        }
    return results

def format_metrics_table(metrics):
    if not metrics:
        return "Insufficient data for yearly analysis.\n"
    
    table = "| Year | Return | Volatility | Sharpe Ratio |\n|:---|---:|---:|---:|\n"
    for year in sorted(metrics.keys(), reverse=True):
        m = metrics[year]
        table += f"| **{year}** | {m['Return']:.2%} | {m['Volatility']:.2%} | {m['Sharpe']:.2f} |\n"
    return table + "\n"

# --- Main Report Generation ---
def generate_markdown(criteria_description="Default Run"):
    print("Generating Final Report...")
    
    # 1. Archive previous report if exists
    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)
    
    report_content = ""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # Title
    report_content += f"# Financial Analysis Report\n"
    report_content += f"**Date:** {timestamp}\n"
    report_content += f"**Criteria:** {criteria_description}\n\n"
    report_content += "---\n\n"
    
    # Section 1
    report_content += "## 1. Candidate Selection (Module 1)\n"
    if os.path.exists(FILE_TOP_100):
        df = pd.read_csv(FILE_TOP_100)
        report_content += f"- **Total Candidates Found:** {len(df)}\n"
        report_content += f"- **Criteria:** {criteria_description}\n\n"
    else:
        report_content += "Status: Data not found.\n\n"
    report_content += "---\n\n"

    # Section 2
    report_content += "## 2. Risk-Adjusted Ranking (Module 2)\n"
    if os.path.exists(FILE_TOP_50):
        df = pd.read_csv(FILE_TOP_50)
        report_content += f"- **Top Stock:** {df.iloc[0]['Symbol']} (Sharpe: {df.iloc[0]['Sharpe Ratio']:.2f})\n\n"
        report_content += "**Top 10 Ranked Stocks:**\n\n"
        report_content += df.head(10).to_markdown(index=False) + "\n\n"
    else:
        report_content += "Status: Data not found.\n\n"
    report_content += "---\n\n"

    # Load Price Data for Analysis (Optimization for both sections)
    p3_weights = load_portfolio(FILE_OPTIMAL)
    p4_weights = load_portfolio(FILE_BACKTEST)
    all_symbols = list(set((list(p3_weights.keys()) if p3_weights else []) + (list(p4_weights.keys()) if p4_weights else [])))
    price_data = get_price_data(all_symbols) if all_symbols else pd.DataFrame()

    # Section 3
    report_content += "## 3. Optimized Portfolio (Module 3)\n"
    if os.path.exists(FILE_OPTIMAL):
        df = pd.read_csv(FILE_OPTIMAL)
        report_content += "**Recommended Allocation:**\n\n"
        df['Weight_Fmt'] = df['Weight'].apply(lambda x: f"{x:.2%}" if isinstance(x, float) else x)
        report_content += df[['Symbol', 'Weight_Fmt']].rename(columns={'Weight_Fmt': 'Weight'}).to_markdown(index=False) + "\n\n"
        
        # Yearly Analysis
        report_content += "### Yearly Performance Analysis\n"
        metrics = calculate_metrics(p3_weights, price_data)
        report_content += format_metrics_table(metrics)
    else:
        report_content += "Status: Data not found.\n\n"
    report_content += "---\n\n"

    # Section 4
    report_content += "## 4. Historical Backtest Criteria (Module 4)\n"
    if os.path.exists(FILE_BACKTEST):
        df = pd.read_csv(FILE_BACKTEST)
        report_content += "**Winning Historical Combination (Past 3 Years):**\n\n"
        df['Weight_Fmt'] = df['Weight'].apply(lambda x: f"{x:.2%}" if isinstance(x, float) else x)
        report_content += df[['Symbol', 'Weight_Fmt']].rename(columns={'Weight_Fmt': 'Weight'}).to_markdown(index=False) + "\n\n"
        
        # Yearly Analysis
        report_content += "### Yearly Performance Analysis\n"
        metrics = calculate_metrics(p4_weights, price_data)
        report_content += format_metrics_table(metrics)
    else:
        report_content += "Status: Data not found.\n\n"

    # Write Report
    with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"Report saved to {OUTPUT_FILE}")
    
    # Archiving
    archive_name = f"REPORT_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    shutil.copy(OUTPUT_FILE, os.path.join(ARCHIVE_DIR, archive_name))
    print(f"Report archived to {os.path.join(ARCHIVE_DIR, archive_name)}")
    
    # Logging
    log_entry = f"| {timestamp} | {archive_name} | {criteria_description} |\n"
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", encoding='utf-8') as f:
            f.write("# Report Log\n\n| Date | Filename | Criteria Description |\n|:---|:---|:---|\n")
    
    with open(LOG_FILE, "a", encoding='utf-8') as f:
        f.write(log_entry)
        
    print("Report Log updated.")

import sys

if __name__ == "__main__":
    description = "Unknown/Manual Run"
    if len(sys.argv) > 1:
        description = sys.argv[1]
    
    generate_markdown(description)

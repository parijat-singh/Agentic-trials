import pandas as pd
import numpy as np
import os
import datetime
import shutil

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

import sys
sys.path.append(ROOT_DIR)
import config
DATA_DIR = config.DATA_DIR
ARCHIVE_DIR = config.ARCHIVE_DIR

FILE_TOP_100 = os.path.join(DATA_DIR, "top_100_new_stocks.csv")
FILE_STATS = os.path.join(DATA_DIR, "scraping_stats.json")
FILE_TOP_50 = os.path.join(ROOT_DIR, "financial_engine", "top_50_stocks.csv")
FILE_OPTIMAL = os.path.join(ROOT_DIR, "portfolio_optimizer", "optimal_portfolio.csv")
FILE_BACKTEST = os.path.join(ROOT_DIR, "backtester", "best_3y_combination.csv")
OUTPUT_FILE = os.path.join(ROOT_DIR, "FINAL_REPORT.md")
LOG_FILE = os.path.join(ROOT_DIR, "REPORT_LOG.md")

import json

def get_waterfall_section():
    stats = {}
    if os.path.exists(FILE_STATS):
        try:
            with open(FILE_STATS, 'r') as f:
                stats = json.load(f)
        except: pass
    
    # Get counts
    count_scanned = stats.get("Scanned", "N/A")
    count_non_us = stats.get("Non_US", 0)
    count_too_old = stats.get("Too_Old", 0)
    count_too_new = stats.get("Too_New", 0)
    count_errors = stats.get("Errors", 0)
    count_selected = stats.get("Selected", 0) # Should be ~100
    
    count_top_50 = 0
    if os.path.exists(FILE_TOP_50):
        try: count_top_50 = len(pd.read_csv(FILE_TOP_50))
        except: pass
        
    count_optimal = 0
    if os.path.exists(FILE_OPTIMAL):
        try: count_optimal = len(pd.read_csv(FILE_OPTIMAL))
        except: pass
        
    count_backtest = 0
    if os.path.exists(FILE_BACKTEST):
        try: count_backtest = len(pd.read_csv(FILE_BACKTEST))
        except: pass

    # Get parameters
    params = stats.get("Parameters", {})
    p_min_hist = params.get("Min_History", 5)
    p_min_ipo = params.get("Min_IPO", 5)
    p_max_ipo = params.get("Max_IPO", 10)
    p_max_pe = params.get("Max_PE", None)

    # Markdown Table
    md = "## Stock Selection Waterfall\n\n"
    md += "| Stage | Description | Count / Reduced By |\n"
    md += "|:---|:---|---:|\n"
    md += f"| **1. Scanned** | Total stocks checked (Market Cap Descending) | {count_scanned} |\n"
    md += f"| *Filter: Non-US* | Excluded non-USD stocks | -{count_non_us} |\n"
    md += f"| *Filter: Too Old* | IPO > {p_max_ipo} Years ago | -{count_too_old} |\n"
    md += f"| *Filter: Too New* | History < {p_min_hist} Years or IPO < {p_min_ipo} Years | -{count_too_new} |\n"
    
    pe_desc = f"P/E > {p_max_pe} or N/A" if p_max_pe else "P/E Filter Disabled"
    if p_max_pe:
         # Need to handle if "Skipped_PE" key exists, else 0
         count_skipped_pe = stats.get("Skipped_PE", 0)
         md += f"| *Filter: P/E Ratio* | {pe_desc} | -{count_skipped_pe} |\n"

    p_min_cap = params.get("Min_Market_Cap", None)
    if p_min_cap:
        count_skipped_cap = stats.get("Skipped_Market_Cap", 0)
        md += f"| *Filter: Market Cap* | Cap < ${p_min_cap}B | -{count_skipped_cap} |\n"
         
    md += f"| *Filter: Errors* | Data fetch errors | -{count_errors} |\n"
    md += f"| **2. Candidates** | Passed all criteria | **{count_selected}** |\n"
    md += f"| **3. Sharpe Ranked** | Top 50 by Risk-Adjusted Return | **{count_top_50}** |\n"
    md += f"| **4. MVO Portfolio** | Optimized Allocation | **{count_optimal}** |\n"
    md += f"| **5. Backtest Winner** | Best Historical Combination | **{count_backtest}** |\n\n"
    md += "---\n\n"
    
    return md

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

# ... (Imports remain same) ...

# ... (Helper Functions) ...

def get_price_data(symbols, valid_start_date="2023-01-01"):
    data = {}
    
    # Ensure SPY is in the list for benchmark
    search_symbols = list(set(symbols + ['SPY']))
    
    for symbol in search_symbols:
        try:
            # Check local first
            path = os.path.join(DATA_DIR, f"{symbol}.csv")
            if os.path.exists(path):
                df = pd.read_csv(path, parse_dates=['Date'], index_col='Date')
                df.index = pd.to_datetime(df.index, utc=True).tz_localize(None)
                data[symbol] = df['Close']
            else:
                # If SPY not found locally, try fetch (it might not be in scanned list)
                if symbol == 'SPY':
                    print(f"Fetching SPY data for benchmark...", flush=True)
                    try:
                        ticker = yf.Ticker("SPY")
                        hist = ticker.history(period="10y")
                        # Normalize to date only to align with other stocks
                        hist.index = pd.to_datetime(hist.index, utc=True).tz_convert('US/Eastern').tz_localize(None).normalize()
                        data[symbol] = hist['Close']
                    except Exception as e:
                        print(f"Error fetching SPY data: {e}", flush=True)
        except Exception:
            continue
    
    if not data: return pd.DataFrame()

    df_prices = pd.DataFrame(data)
    
    # Ensure all indices are normalized just in case
    df_prices.index = pd.to_datetime(df_prices.index).normalize()
    
    # Filter by start date
    return df_prices[df_prices.index >= pd.Timestamp(valid_start_date)]

def calculate_metrics(portfolio_weights, price_data, benchmark_symbol='SPY'):
    """
    Calculate portfolio metrics including Alpha and Beta against a benchmark.
    Returns: Dict keyed by year.
    """
    metrics = {}
    
    if not portfolio_weights or price_data.empty: return {}

    symbols = list(portfolio_weights.keys())
    # Ensure benchmark is in price_data
    if benchmark_symbol not in price_data.columns:
        # If no benchmark, can't calc alpha/beta
        benchmark_series = None
    else:
        benchmark_series = price_data[benchmark_symbol]
        
    relevant_prices = price_data[symbols].dropna()
    if relevant_prices.empty: return {}

    total_weight = sum(portfolio_weights.values())
    clean_weights = {k: v/total_weight for k, v in portfolio_weights.items()}
    
    daily_returns = relevant_prices.pct_change().dropna()
    if daily_returns.empty: return {}
    
    # Align benchmark
    if benchmark_series is not None:
        bench_ret = benchmark_series.pct_change().dropna()
        # Align dates
        common_idx = daily_returns.index.intersection(bench_ret.index)
        daily_returns = daily_returns.loc[common_idx]
        bench_ret = bench_ret.loc[common_idx]
    
    if daily_returns.empty: return {}

    portfolio_daily_ret = daily_returns.dot(pd.Series(clean_weights))
    years = portfolio_daily_ret.index.year.unique()
    results = {}
    
    # Risk Free Rate assumption (annualized)
    rf_rate = 0.04
    daily_rf = (1 + rf_rate)**(1/252) - 1
    
    for year in years:
        idx = portfolio_daily_ret.index.year == year
        year_returns = portfolio_daily_ret.loc[idx]
        if len(year_returns) < 10: continue
            
        # Geometric return compounding with safety jump check
        total_ret = (1 + year_returns).prod() - 1
        
        # Stability check: handle inf/nan immediately
        if np.isinf(total_ret) or np.isnan(total_ret):
            print(f"WARNING: Year {year} return overflow detected. Capping at 10,000x jump.")
            total_ret = 10000.0 # Extreme fallback cap 
            
        vol = year_returns.std() * np.sqrt(252)
        
        # Stability check: avoid divide by zero Sharpes
        if vol < 1e-6 or np.isnan(vol):
            sharpe = 0.0
        else:
            sharpe = ((year_returns.mean() - daily_rf) * 252) / vol
        
        # Alpha / Beta
        alpha = np.nan
        beta = np.nan
        
        if benchmark_series is not None:
            year_bench = bench_ret.loc[idx]
            print(f"DEBUG Year {year}: Returns {len(year_returns)}, Bench {len(year_bench)}", flush=True)
            if not year_bench.empty and len(year_bench) == len(year_returns):
                # Covariance
                cov_matrix = np.cov(year_returns, year_bench)
                cov = cov_matrix[0, 1]
                var_bench = np.var(year_bench, ddof=1)
                
                if var_bench > 1e-9:
                    # Covariance stability
                    if np.isnan(cov) or np.isinf(cov):
                         beta = 0.0
                    else:
                        beta = cov / var_bench
                        
                    # Alpha = Rp - (Rf + Beta * (Rm - Rf)) 
                    bench_total_ret = (1 + year_bench).prod() - 1
                    
                    # Handle bench infinity
                    if np.isinf(bench_total_ret) or np.isnan(bench_total_ret):
                         alpha = np.nan
                    else:
                         alpha = total_ret - (rf_rate + beta * (bench_total_ret - rf_rate))
                else:
                    print(f"DEBUG: var_bench too small: {var_bench}", flush=True)
        
        results[year] = {
            "Return": total_ret,
            "Volatility": vol,
            "Sharpe": sharpe,
            "Alpha": alpha,
            "Beta": beta
        }
    return results

def format_metrics_table(metrics):
    if not metrics:
        return "Insufficient data for yearly analysis.\n"
    
    # Define widths
    w_year = 6
    w_ret = 10
    w_vol = 12
    w_sharpe = 14
    w_alpha = 10
    w_beta = 8
    
    # Header
    table = f"| {'Year':<{w_year}} | {'Return':>{w_ret}} | {'Volatility':>{w_vol}} | {'Sharpe Ratio':>{w_sharpe}} | {'Alpha':>{w_alpha}} | {'Beta':>{w_beta}} |\n"
    table += f"|:{'-'*(w_year)}|{'-'*(w_ret+1)}:|{'-'*(w_vol+1)}:|{'-'*(w_sharpe+1)}:|{'-'*(w_alpha+1)}:|{'-'*(w_beta+1)}:|\n"
    
    for year in sorted(metrics.keys(), reverse=True):
        m = metrics[year]
        alpha_str = f"{m['Alpha']:.2%}" if not np.isnan(m['Alpha']) else "N/A"
        beta_str = f"{m['Beta']:.2f}" if not np.isnan(m['Beta']) else "N/A"
        
        table += f"| {year:<{w_year}} | {m['Return']:>{w_ret}.2%} | {m['Volatility']:>{w_vol}.2%} | {m['Sharpe']:>{w_sharpe}.2f} | {alpha_str:>{w_alpha}} | {beta_str:>{w_beta}} |\n"
    return table + "\n"

# ... (Rest of format functions) ...

# --- Main Report Generation ---
def generate_markdown(criteria_description="Default Run"):
    # ... (Loading Stats) ...
    # Read Parameters from Stats
    stats = {}
    if os.path.exists(FILE_STATS):
        try:
            with open(FILE_STATS, 'r') as f:
                stats = json.load(f)
        except Exception as e:
            print(f"DEBUG: Error loading stats json: {e}")
            
    total_time = stats.get("Total_Time", "N/A")
    
    # ... (Rest of Header/Waterfall) ...
    
    # ... (Section 4 and Final Writing) ...
    
    # ... (Inside generate_markdown, at the end of report content) ...
    if total_time != "N/A":
        report_content += f"\n**Total Analysis Time:** {total_time}\n"
    
    # Write Report
    with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
        f.write(report_content)
    # ... (Rest of Function) ...


import yfinance as yf

def get_financial_ratios(symbols):
    """
    Fetches P/E, PEG, and P/B ratios for a list of symbols.
    Returns a dictionary of dictionaries: {symbol: {'P/E': val, 'PEG': val, 'P/B': val}}
    """
    print(f"Fetching financial ratios for {len(symbols)} stocks...", flush=True)
    ratios = {}
    
    # Use Ticker object for each (no batch info for these specific fields usually reliable in batch download)
    # yfinance batch download is mostly for prices. 
    # For info, we often iterate. To speed up, we could use threads, but 10-15 stocks is fast.
    
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            info = ticker.fast_info # Fast info often has market cap, but ratios are in .info
            # We need standard .info for ratios
            try:
                full_info = ticker.info
            except:
                full_info = {}
                
            # Try multiple keys for PEG
            peg = full_info.get('trailingPegRatio')
            if peg is None:
                peg = full_info.get('pegRatio')
            if peg is None:
                peg = "N/A"
            
            pe = full_info.get('trailingPE', "N/A")
            pb = full_info.get('priceToBook', "N/A")
            
            # Format
            def fmt(val):
                if isinstance(val, (int, float)):
                    return f"{val:.2f}"
                return val
                
            ratios[sym] = {
                'P/E': fmt(pe),
                'PEG': fmt(peg),
                'P/B': fmt(pb)
            }
        except Exception as e:
            print(f"Error fetching info for {sym}: {e}")
            ratios[sym] = {'P/E': 'N/A', 'PEG': 'N/A', 'P/B': 'N/A'}
            
    return ratios

# --- Main Report Generation ---
# --- Main Report Generation ---
def generate_markdown(criteria_description="Default Run"):
    print("Generating Final Report...")
    
    # 1. Archive previous report if exists
    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)
        
    # Read Parameters from Stats
    stats = {}
    if os.path.exists(FILE_STATS):
        try:
            with open(FILE_STATS, 'r') as f:
                stats = json.load(f)
        except Exception as e:
            print(f"DEBUG: Error loading stats json: {e}")
    
    print(f"DEBUG: Loaded Stats Keys: {list(stats.keys())}")
    print(f"DEBUG: Loaded Parameters: {stats.get('Parameters')}")
        
    params = stats.get("Parameters", {})
    p_min_hist = params.get("Min_History", "N/A")
    p_min_ipo = params.get("Min_IPO", "N/A")
    p_max_ipo = params.get("Max_IPO", "N/A")
    p_max_pe = params.get("Max_PE", "Disabled")
    if p_max_pe is None: p_max_pe = "Disabled"
    
    report_content = ""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # Title
    report_content += f"# Financial Analysis Report\n"
    report_content += f"**Date:** {timestamp}\n"
    report_content += f"**Criteria:** {criteria_description}\n\n"
    
    # Run Configuration Section
    p_min_cap = params.get("Min_Market_Cap", "Disabled")
    if p_min_cap is None: p_min_cap = "Disabled"
    else: p_min_cap = f"${p_min_cap}B"

    report_content += "### Run Configuration\n"
    report_content += "| Parameter | Value |\n"
    report_content += "|:---|:---|\n"
    report_content += f"| **Min Trading History** | {p_min_hist} Years |\n"
    report_content += f"| **Min IPO Age** | {p_min_ipo} Years |\n"
    report_content += f"| **Max IPO Age** | {p_max_ipo} Years |\n"
    report_content += f"| **Max P/E Ratio** | {p_max_pe} |\n"
    report_content += f"| **Min Market Cap** | {p_min_cap} |\n\n"
    
    report_content += "---\n\n"
    
    # Waterfall Section
    report_content += get_waterfall_section()
    
    # Top 10 Exclusion Section
    top_10_file = os.path.join(DATA_DIR, "top_10_exclusion.json")
    if os.path.exists(top_10_file):
        try:
            with open(top_10_file, 'r') as f:
                data = json.load(f)
            
            report_content += "## Top 10 Market Cap Companies Analysis\n"
            report_content += "**Why they are (or are not) in the portfolio:**\n\n"
            report_content += "| Rank | Symbol | Name | Status/Reason |\n"
            report_content += "|:---:|:---:|:---|:---|\n"
            
            for item in data:
                report_content += f"| {item['Rank']} | {item['Symbol']} | {item['Name']} | {item['Reason']} |\n"
            
            report_content += "\n---\n\n"
        except Exception as e:
            print(f"Error adding Top 10 section: {e}")
    
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
        try:
            df = pd.read_csv(FILE_TOP_50)
            if not df.empty:
                # Safe access to rows
                top_sym = df.iloc[0]['Symbol'] if 'Symbol' in df.columns else 'N/A'
                top_sharpe = df.iloc[0]['Sharpe Ratio'] if 'Sharpe Ratio' in df.columns else 0.0
                
                report_content += f"- **Top Stock:** {top_sym} (Sharpe: {top_sharpe:.2f})\n\n"
                report_content += "**Top 10 Ranked Stocks:**\n\n"
                report_content += df.head(10).to_markdown(index=False) + "\n\n"
        except Exception as e:
             report_content += f"Error reading Top 50 file: {e}\n\n"
    else:
        report_content += "Status: Data not found.\n\n"
    report_content += "---\n\n"

    # Load Price Data for Analysis (Optimization for both sections)
    p3_weights = load_portfolio(FILE_OPTIMAL)
    p4_weights = load_portfolio(FILE_BACKTEST)
    
    all_symbols_opt = list(p3_weights.keys()) if p3_weights else []
    all_symbols_bt = list(p4_weights.keys()) if p4_weights else []
    
    unique_symbols = list(set(all_symbols_opt + all_symbols_bt))
    price_data = get_price_data(unique_symbols) if unique_symbols else pd.DataFrame()
    
    # Optimization: Fetch Ratios for all unique symbols once
    ratio_data = get_financial_ratios(unique_symbols) if unique_symbols else {}

    # Section 3
    report_content += "## 3. Optimized Portfolio (Module 3)\n"
    if os.path.exists(FILE_OPTIMAL):
        df = pd.read_csv(FILE_OPTIMAL)
        report_content += "**Recommended Allocation:**\n\n"
        
        # Merge Ratios
        if not df.empty and 'Symbol' in df.columns:
            df['P/E'] = df['Symbol'].map(lambda x: ratio_data.get(x, {}).get('P/E', 'N/A'))
            df['PEG'] = df['Symbol'].map(lambda x: ratio_data.get(x, {}).get('PEG', 'N/A'))
            df['P/B'] = df['Symbol'].map(lambda x: ratio_data.get(x, {}).get('P/B', 'N/A'))

        df['Weight_Fmt'] = df['Weight'].apply(lambda x: f"{x:.2%}" if isinstance(x, float) else x)
        
        # Format Contribution Metrics if present
        if 'Return Contrib' in df.columns:
            df['Ret.Stream'] = df['Return Contrib'].apply(lambda x: f"{x:.2%}" if pd.notnull(x) else "")
        if 'Risk Contrib' in df.columns:
            df['Risk.Alloc'] = df['Risk Contrib'].apply(lambda x: f"{x:.2%}" if pd.notnull(x) else "")
        if 'Correlation' in df.columns:
            df['Corr. vs Port'] = df['Correlation'].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "")
            
        # Select columns directly
        # Added Contribution metrics to explain "Why Included"
        cols_to_show = ['Symbol', 'Weight_Fmt', 'Ret.Stream', 'Risk.Alloc', 'Corr. vs Port', 'P/E', 'PEG']
        
        # Check if they exist (in case df was empty or old CSV)
        cols_to_show = [c for c in cols_to_show if c in df.columns]
        
        report_content += df[cols_to_show].rename(columns={'Weight_Fmt': 'Weight'}).to_markdown(index=False) + "\n\n"
        
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
        
         # Merge Ratios
        if not df.empty and 'Symbol' in df.columns:
            df['P/E'] = df['Symbol'].map(lambda x: ratio_data.get(x, {}).get('P/E', 'N/A'))
            df['PEG'] = df['Symbol'].map(lambda x: ratio_data.get(x, {}).get('PEG', 'N/A'))
            df['P/B'] = df['Symbol'].map(lambda x: ratio_data.get(x, {}).get('P/B', 'N/A'))
            
        df['Weight_Fmt'] = df['Weight'].apply(lambda x: f"{x:.2%}" if isinstance(x, float) else x)
        
        cols_to_show = ['Symbol', 'Weight_Fmt', 'P/E', 'PEG', 'P/B']
        cols_to_show = [c for c in cols_to_show if c in df.columns]
        
        report_content += df[cols_to_show].rename(columns={'Weight_Fmt': 'Weight'}).to_markdown(index=False) + "\n\n"
        
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

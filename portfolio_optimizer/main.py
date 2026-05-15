import optimizer
import os
import sys
import json
import argparse
import pandas as pd

# Add sibling directory to path to import risk_free_rate from previous module
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from financial_engine import risk_free_rate
import config

# Constants
TOP_50_FILE = os.path.join("..", "financial_engine", "top_50_stocks.csv")
DATA_DIR = config.DATA_DIR
OUTPUT_FILE = "optimal_portfolio.csv"


def _apply_include_exclude(symbols, include_list, exclude_list):
    """
    Apply include/exclude to the symbol list.
    - Exclude: remove these symbols from the universe.
    - Include: ADD these symbols to the universe (so they are considered even if not in top 50).
    Result: (symbols ∪ include_list) \ exclude_list, order preserved with include_list extras at end.
    """
    def norm(s):
        return (s.upper() if isinstance(s, str) else s)
    exclude_set = {norm(s) for s in (exclude_list or [])}
    symbols = [s for s in symbols if norm(s) not in exclude_set]
    if include_list:
        include_set = {norm(s) for s in include_list}
        already = {norm(s) for s in symbols}
        for s in include_list:
            if norm(s) not in already:
                symbols.append(s)
                already.add(norm(s))
    return symbols


def _parse_args():
    parser = argparse.ArgumentParser(description="Portfolio Optimizer (Module 3)")
    parser.add_argument("--include-stocks", type=str, default=None,
                        help="Comma-separated symbols to include in optimization")
    parser.add_argument("--exclude-stocks", type=str, default=None,
                        help="Comma-separated symbols to exclude from optimization")
    return parser.parse_args()


def main():
    args = _parse_args()
    print("=== Portfolio Optimizer (Module 3) ===")
    
    # 1. Fetch Risk-Free Rate
    print("\n--- Step 1: Getting Risk-Free Rate ---")
    rf_rate = risk_free_rate.get_risk_free_rate()
    print(f"Risk-Free Rate: {rf_rate:.2%}")
    
    # 2. Load Data (with optional include/exclude from CLI or pipeline parameters)
    print("\n--- Step 2: Loading Data for Top 50 Stocks ---")
    if not os.path.exists(TOP_50_FILE):
        print(f"Error: {TOP_50_FILE} not found. Please run Module 2 first.", flush=True)
        sys.exit(1)

    top_50_df = pd.read_csv(TOP_50_FILE)
    # Support both 'Symbol' and 'symbol' column names
    sym_col = "Symbol" if "Symbol" in top_50_df.columns else "symbol"
    symbols = top_50_df[sym_col].tolist()

    include_list = None
    exclude_list = None
    # 1) Sidecar file written by run_pipeline (same dir as this script) - most reliable
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _sidecar_path = os.path.join(_script_dir, ".pipeline_include_exclude.json")
    if os.path.exists(_sidecar_path):
        try:
            with open(_sidecar_path, "r") as f:
                _sidecar = json.load(f)
            include_list = _sidecar.get("Include_Stocks")
            exclude_list = _sidecar.get("Exclude_Stocks")
            if include_list or exclude_list:
                print(f"Include/Exclude from pipeline sidecar: include={include_list}, exclude={exclude_list}", flush=True)
        except Exception as e:
            print(f"Warning: Could not read sidecar {_sidecar_path}: {e}", flush=True)
    # 2) CLI args
    if not include_list and not exclude_list and (args.include_stocks or args.exclude_stocks):
        include_list = [s.strip().upper() for s in (args.include_stocks or "").split(",") if s and s.strip()] or None
        exclude_list = [s.strip().upper() for s in (args.exclude_stocks or "").split(",") if s and s.strip()] or None
    # 3) scraping_stats.json (e.g. when run manually)
    if not include_list and not exclude_list:
        stats_path = os.path.join(config.DATA_DIR, "scraping_stats.json")
        if os.path.exists(stats_path):
            try:
                with open(stats_path, "r") as f:
                    stats = json.load(f)
                params = stats.get("Parameters") or {}
                include_list = params.get("Include_Stocks")
                exclude_list = params.get("Exclude_Stocks")
            except Exception:
                pass
    if include_list or exclude_list:
        before = len(symbols)
        symbols = _apply_include_exclude(symbols, include_list, exclude_list)
        print(f"Include/Exclude filter: {before} -> {len(symbols)} symbols (exclude removed; include added)", flush=True)
        if not symbols:
            print("Error: No symbols left after include/exclude filter. Relax filters or run without them.", flush=True)
            sys.exit(1)
    prices_df = optimizer.load_data(TOP_50_FILE, DATA_DIR, symbols_override=symbols)

    if prices_df.empty:
        print("Error: No price data loaded.", flush=True)
        sys.exit(1)

    # 3. Optimize (pass include_list so those symbols get minimum weight and appear in the portfolio)
    print("\n--- Step 3: Optimizing Portfolio (Mean-Variance Analysis) ---")
    optimal_portfolio = optimizer.optimize_portfolio(prices_df, rf_rate, must_include_symbols=include_list)
    
    if optimal_portfolio is None:
        print("Optimization failed.", flush=True)
        sys.exit(1)
        
    # 4. Save
    print(f"\n--- Step 4: Saving Results to {OUTPUT_FILE} ---")
    optimal_portfolio.to_csv(OUTPUT_FILE, index=False)
    print("Success!")
    
    # 5. Display
    print("\nOptimal Portfolio Allocation:")
    print(optimal_portfolio.to_string(index=False, formatters={'Weight': '{:.4%}'.format}))

if __name__ == "__main__":
    main()

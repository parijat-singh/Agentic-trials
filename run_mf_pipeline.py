"""Mutual Fund Analysis Pipeline - session-based orchestration."""
import argparse
import csv
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from mf_agent.mf_scraper import run_scraper
from mf_agent.mf_data_fetcher import run_fetcher
from mf_agent.mf_filter import run_filter
from mf_engine.mf_sharpe_ranker import run_ranker
from portfolio_optimizer.optimizer import optimize_portfolio, load_data_from_db
from report_generator.mf_report import generate_mf_report
from mf_agent.mf_db import MFDB
import pandas as pd

RISK_FREE_RATE = 0.05


def main():
    parser = argparse.ArgumentParser(description="Mutual Fund Analysis Pipeline")
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--max-expense-ratio", type=float, default=1.5,
                        help="Max expense ratio in percent (e.g. 1.5 = 1.5%%)")
    parser.add_argument("--min-aum", type=float, default=1e9,
                        help="Minimum AUM in dollars (default 1B)")
    parser.add_argument("--min-history-years", type=float, default=5.0)
    parser.add_argument("--categories", type=str, default=None,
                        help="Comma-separated category filter: Equity,Bond,Balanced,Alternative,Money Market")
    parser.add_argument("--skip-scraper", action="store_true")
    parser.add_argument("--skip-fetcher", action="store_true")
    parser.add_argument("--max-pages", type=int, default=80,
                        help="Scraper: max Yahoo Finance pages (default 80 = ~8000 funds)")
    args = parser.parse_args()

    session_id = args.session_id or str(uuid.uuid4())[:8]
    session_dir = os.path.join(config.MF_SESSIONS_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    print(f"\n{'='*60}\nMutual Fund Analysis Pipeline | Session: {session_id}\n{'='*60}\n",
          flush=True)

    # [1/7] Scrape universe
    if not args.skip_scraper:
        print("[1/7] Scraping MF universe...", flush=True)
        run_scraper(max_pages=args.max_pages)
        print("[1/7] Done.\n", flush=True)
    else:
        print("[1/7] Skipping scraper.\n", flush=True)

    # [2/7] Fetch price history & metadata
    if not args.skip_fetcher:
        print("[2/7] Fetching MF data...", flush=True)
        run_fetcher()
        print("[2/7] Done.\n", flush=True)
    else:
        print("[2/7] Skipping fetcher.\n", flush=True)

    # Normalise expense ratio: CLI passes percent (e.g. 1.5), convert to decimal
    max_er = args.max_expense_ratio / 100.0 if args.max_expense_ratio > 0.1 else args.max_expense_ratio
    categories = [c.strip() for c in args.categories.split(",")] if args.categories else None

    # [3/7] Filter
    print("[3/7] Applying filters...", flush=True)
    cand_path, _ = run_filter(
        session_dir,
        max_expense_ratio=max_er,
        min_aum=args.min_aum,
        min_history_years=args.min_history_years,
        categories=categories,
    )
    print("[3/7] Done.\n", flush=True)

    # Check candidates count before ranking
    try:
        with open(cand_path) as _f:
            n_cands = sum(1 for _ in _f) - 1  # subtract header
    except Exception:
        n_cands = 0
    if n_cands <= 0:
        print("Pipeline stopped: 0 candidates passed filters. "
              "Try relaxing Expense Ratio, AUM, History, or Category filters.", flush=True)
        return 1

    # [4/7] Rank by Sharpe
    print("[4/7] Ranking by Sharpe...", flush=True)
    top_path = run_ranker(session_dir, cand_path, risk_free_rate=RISK_FREE_RATE, top_n=50)
    if not top_path:
        print("Pipeline stopped: no ranked mutual funds.", flush=True)
        return 1
    print("[4/7] Done.\n", flush=True)

    # [5/7] Portfolio optimisation (reuse ETF/stock optimizer)
    print("[5/7] Running optimisation...", flush=True)
    top_df = pd.read_csv(top_path)
    symbols = top_df["Symbol"].tolist()
    db = MFDB()
    # load_data_from_db expects an object with .load_history()
    prices_df = load_data_from_db(symbols, db)
    if prices_df.empty:
        print("Pipeline stopped: no price data for optimisation.", flush=True)
        return 1
    port_df = optimize_portfolio(prices_df, RISK_FREE_RATE)
    if port_df is None:
        print("Pipeline stopped: optimisation failed.", flush=True)
        return 1
    opt_path = os.path.join(session_dir, "optimal_portfolio.csv")
    port_df.to_csv(opt_path, index=False)
    print(f"[5/7] Done. Saved to {opt_path}\n", flush=True)

    # [6/7] Performance metrics (embedded in report)
    print("[6/7] Computing performance...", flush=True)
    print("[6/7] Done.\n", flush=True)

    # [7/7] Report
    print("[7/7] Generating report...", flush=True)
    report_path = generate_mf_report(session_dir)
    print(f"[7/7] Done. Report: {report_path}\n", flush=True)

    print(f"Pipeline complete. Session: {session_id}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

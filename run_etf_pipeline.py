"""ETF Analysis Pipeline - session-based orchestration."""
import argparse
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from etf_agent.etf_scraper import run_scraper
from etf_agent.etf_data_fetcher import run_fetcher
from etf_agent.etf_filter import run_filter
from etf_engine.etf_sharpe_ranker import run_ranker
from portfolio_optimizer.optimizer import optimize_portfolio
try:
    from portfolio_optimizer.optimizer import load_data_from_db
except ImportError:
    def load_data_from_db(symbols, db):
        """Load Close prices for symbols from ETFDB when optimizer lacks it."""
        import pandas as pd
        price_data = {}
        for sym in symbols:
            df = db.load_history(sym)
            if not df.empty and "Close" in df.columns:
                price_data[sym] = df["Close"]
        if not price_data:
            return pd.DataFrame()
        prices_df = pd.DataFrame(price_data).ffill().dropna()
        return prices_df if not prices_df.empty else pd.DataFrame(price_data).ffill().tail(252).dropna()
from report_generator.etf_report import generate_etf_report
from etf_agent.etf_db import ETFDB
import pandas as pd

RISK_FREE_RATE = 0.05


def main():
    parser = argparse.ArgumentParser(description="ETF Analysis Pipeline")
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--max-expense-ratio", type=float, default=0.5, help="Max expense ratio in percent (e.g. 0.5)")
    parser.add_argument("--min-aum", type=float, default=1e9)
    parser.add_argument("--min-history-years", type=float, default=3.0)
    parser.add_argument("--no-nyse-nasdaq", action="store_true")
    parser.add_argument("--skip-scraper", action="store_true")
    parser.add_argument("--skip-fetcher", action="store_true")
    parser.add_argument("--max-pages", type=int, default=40, help="Scraper: max pages (default 40)")
    args = parser.parse_args()

    session_id = args.session_id or str(uuid.uuid4())[:8]
    session_dir = os.path.join(config.ETF_SESSIONS_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    print(f"\n{'='*60}\nETF Analysis Pipeline | Session: {session_id}\n{'='*60}\n", flush=True)

    if not args.skip_scraper:
        print("[1/7] Scraping ETF universe...", flush=True)
        run_scraper(max_pages=args.max_pages)
        print("[1/7] Done.\n", flush=True)
    else:
        print("[1/7] Skipping scraper.\n", flush=True)

    if not args.skip_fetcher:
        print("[2/7] Fetching ETF data...", flush=True)
        run_fetcher()
        print("[2/7] Done.\n", flush=True)
    else:
        print("[2/7] Skipping fetcher.\n", flush=True)

    max_er = args.max_expense_ratio / 100.0 if args.max_expense_ratio > 0.1 else args.max_expense_ratio
    print("[3/7] Applying filters...", flush=True)
    cand_path, _ = run_filter(
        session_dir,
        max_expense_ratio=max_er,
        min_aum=args.min_aum,
        min_history_years=args.min_history_years,
        nyse_nasdaq_only=not args.no_nyse_nasdaq,
    )
    print("[3/7] Done.\n", flush=True)

    print("[4/7] Ranking by Sharpe...", flush=True)
    top_path = run_ranker(session_dir, cand_path, risk_free_rate=RISK_FREE_RATE, top_n=50)
    if not top_path:
        print("Pipeline stopped: no ranked ETFs.", flush=True)
        return 1
    print("[4/7] Done.\n", flush=True)

    print("[5/7] Running optimization...", flush=True)
    top_df = pd.read_csv(top_path)
    symbols = top_df["Symbol"].tolist()
    db = ETFDB()
    prices_df = load_data_from_db(symbols, db)
    if prices_df.empty:
        print("Pipeline stopped: no price data.", flush=True)
        return 1
    port_df = optimize_portfolio(prices_df, RISK_FREE_RATE)
    if port_df is None:
        print("Pipeline stopped: optimization failed.", flush=True)
        return 1
    opt_path = os.path.join(session_dir, "optimal_portfolio.csv")
    port_df.to_csv(opt_path, index=False)
    print(f"[5/7] Done. Saved to {opt_path}\n", flush=True)

    print("[6/7] Computing performance...", flush=True)
    print("[6/7] Done.\n", flush=True)

    print("[7/7] Generating report...", flush=True)
    report_path = generate_etf_report(session_dir)
    print(f"[7/7] Done. Report: {report_path}\n", flush=True)

    print(f"Pipeline complete. Session: {session_id}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

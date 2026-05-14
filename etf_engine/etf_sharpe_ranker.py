"""
ETF Sharpe Ranker - load from etf_cache.db, rank by Sharpe, write top 50 to session dir.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from etf_agent.etf_db import ETFDB
from financial_engine.sharpe_ranker import calculate_sharpe_ratio

RISK_FREE_RATE = 0.05


def run_ranker(session_dir, candidates_csv, risk_free_rate=RISK_FREE_RATE, top_n=50):
    """Load candidates, compute Sharpe from DB, rank, write etf_top_50.csv."""
    os.makedirs(session_dir, exist_ok=True)
    if not os.path.exists(candidates_csv):
        print(f"Candidates file not found: {candidates_csv}", flush=True)
        return None
    df = pd.read_csv(candidates_csv)
    symbols = df["symbol"].astype(str).tolist()
    db = ETFDB()
    results = []
    # Single bulk query instead of N individual DB round-trips
    histories = db.load_history_bulk(symbols)
    for sym in symbols:
        hist = histories.get(sym, pd.DataFrame())
        sharpe, ann_ret, ann_vol = calculate_sharpe_ratio(hist, risk_free_rate)
        if sharpe is not None:
            results.append({
                "Symbol": sym,
                "Sharpe Ratio": sharpe,
                "Annualized Return": ann_ret,
                "Annualized Volatility": ann_vol,
            })
    if not results:
        print("No valid Sharpe results.", flush=True)
        return None
    ranked = pd.DataFrame(results).sort_values("Sharpe Ratio", ascending=False).head(top_n)
    out_path = os.path.join(session_dir, "etf_top_50.csv")
    ranked.to_csv(out_path, index=False)
    print(f"Ranked top {len(ranked)} ETFs. Saved to {out_path}", flush=True)
    return out_path

"""
MF Sharpe Ranker - load NAV history from mf_cache.db, rank by Sharpe, write top 50.
"""
import os
import sys

import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from mf_agent.mf_db import MFDB
from financial_engine.sharpe_ranker import calculate_sharpe_ratio

RISK_FREE_RATE = 0.05


def run_ranker(session_dir, candidates_csv, risk_free_rate=RISK_FREE_RATE, top_n=50):
    """Load candidates, compute Sharpe from DB, rank, write mf_top_50.csv."""
    os.makedirs(session_dir, exist_ok=True)
    if not os.path.exists(candidates_csv):
        print(f"Candidates file not found: {candidates_csv}", flush=True)
        return None
    if os.path.getsize(candidates_csv) == 0:
        print("Candidates file is empty — no funds passed filters.", flush=True)
        return None

    df = pd.read_csv(candidates_csv)
    if df.empty:
        print("No candidates to rank.", flush=True)
        return None
    symbols = df["symbol"].astype(str).tolist()
    db = MFDB()
    results = []

    # Build a quick lookup for extra metadata from candidates CSV
    meta_lookup = df.set_index("symbol").to_dict("index")

    # Single bulk query instead of N individual DB round-trips
    histories = db.load_history_bulk(symbols)

    for sym in symbols:
        hist = histories.get(sym, pd.DataFrame())
        if hist.empty or "Close" not in hist.columns:
            continue
        sharpe, ann_ret, ann_vol = calculate_sharpe_ratio(hist, risk_free_rate)
        if sharpe is not None:
            m = meta_lookup.get(sym, {})
            results.append({
                "Symbol": sym,
                "Name": m.get("name", sym),
                "FundFamily": m.get("fund_family", ""),
                "Category": m.get("broad_category", ""),
                "ExpenseRatio": m.get("expense_ratio"),
                "AUM": m.get("aum"),
                "Sharpe Ratio": sharpe,
                "Annualized Return": ann_ret,
                "Annualized Volatility": ann_vol,
            })

    if not results:
        print("No valid Sharpe results for mutual funds.", flush=True)
        return None

    ranked = (
        pd.DataFrame(results)
        .sort_values("Sharpe Ratio", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    out_path = os.path.join(session_dir, "mf_top_50.csv")
    ranked.to_csv(out_path, index=False)
    print(f"Ranked top {len(ranked)} mutual funds. Saved to {out_path}", flush=True)
    return out_path

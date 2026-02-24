"""
ETF Filter - apply expense ratio, AUM, min history, NYSE/NASDAQ filters.
Outputs etf_stats.json and etf_candidates.csv to session dir.
"""
import json
import os
import sys
from datetime import datetime

import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from etf_agent.etf_db import ETFDB
from stock_agent.market_cap_scraper import is_nyse_or_nasdaq


def run_filter(
    session_dir,
    max_expense_ratio=None,
    min_aum=None,
    min_history_years=None,
    nyse_nasdaq_only=True,
):
    """
    Apply filters to ETFs in cache. Write etf_stats.json and etf_candidates.csv.
    """
    os.makedirs(session_dir, exist_ok=True)
    db = ETFDB()
    symbols = db.list_symbols()
    stats = {"Scanned": len(symbols), "Expense": 0, "AUM": 0, "History": 0, "Exchange": 0, "Passed": 0}
    candidates = []
    today = datetime.now().date()

    for sym in symbols:
        meta = db.get_etf_metadata(sym)
        er = meta.get("expense_ratio") if meta else None
        aum = meta.get("aum") if meta else None
        ex = meta.get("exchange") if meta else None

        if max_expense_ratio is not None and er is not None and float(er) > max_expense_ratio:
            stats["Expense"] += 1
            continue
        if min_aum is not None and (aum is None or float(aum) < min_aum):
            stats["AUM"] += 1
            continue
        if nyse_nasdaq_only and not is_nyse_or_nasdaq(ex):
            stats["Exchange"] += 1
            continue

        df = db.load_history(sym)
        if df.empty or len(df) < 30:
            stats["History"] += 1
            continue
        start = df.index.min()
        if hasattr(start, "date"):
            start = start.date()
        years = (today - start).days / 365.25
        if min_history_years is not None and years < min_history_years:
            stats["History"] += 1
            continue

        candidates.append({
            "symbol": sym,
            "name": (meta.get("name") or sym) if meta else sym,
            "expense_ratio": er,
            "aum": aum,
            "exchange": ex,
            "history_years": round(years, 2),
        })

    stats["Passed"] = len(candidates)

    stats_path = os.path.join(session_dir, "etf_stats.json")
    with open(stats_path, "w") as f:
        json.dump({
            "Parameters": {
                "max_expense_ratio": max_expense_ratio,
                "min_aum": min_aum,
                "min_history_years": min_history_years,
                "nyse_nasdaq_only": nyse_nasdaq_only,
            },
            "Waterfall": stats,
        }, f, indent=2)

    cand_path = os.path.join(session_dir, "etf_candidates.csv")
    pd.DataFrame(candidates).to_csv(cand_path, index=False)
    print(f"Filter: {stats['Passed']} candidates. Stats: {stats}", flush=True)
    return cand_path, stats_path

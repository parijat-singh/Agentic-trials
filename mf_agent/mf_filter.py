"""
Mutual Fund Filter - expense ratio, AUM, history length, category filters.
Uses bulk DB queries to avoid N+1 round-trips on slow storage paths.
Outputs mf_stats.json and mf_candidates.csv to session dir.
"""
import json
import os
import sys
from datetime import datetime

import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from mf_agent.mf_db import MFDB

# Broad category groupings used for UI multi-select
CATEGORY_GROUPS = {
    "Equity": [
        "large blend", "large growth", "large value",
        "mid-cap blend", "mid-cap growth", "mid-cap value",
        "small blend", "small growth", "small value",
        "foreign large blend", "foreign large growth", "foreign large value",
        "diversified emerging mkts", "world stock", "global large-stock blend",
        "technology", "health", "real estate", "financial",
        "natural resources", "utilities", "communications",
        "sector equity",
    ],
    "Bond": [
        "intermediate core bond", "intermediate core-plus bond",
        "short-term bond", "long-term bond", "ultrashort bond",
        "high yield bond", "multisector bond", "bank loan",
        "inflation-protected bond", "world bond", "emerging markets bond",
        "corporate bond", "government bond", "muni national",
        "muni short", "muni long",
    ],
    "Balanced": [
        "allocation--15% to 30% equity", "allocation--30% to 50% equity",
        "allocation--50% to 70% equity", "allocation--70% to 85% equity",
        "allocation--85%+ equity", "target-date", "balanced",
        "moderate allocation", "conservative allocation", "world allocation",
    ],
    "Alternative": [
        "long-short equity", "market neutral", "managed futures",
        "multialternative", "volatility", "commodities",
    ],
    "Money Market": ["money market", "prime money market", "government money market"],
}


def _classify_category(raw_category: str) -> str:
    """Map a yfinance/Morningstar category string to one of our broad groups.
    Returns None when category data is missing so the filter can skip it rather
    than incorrectly rejecting the fund.
    """
    if not raw_category:
        return None   # unknown — caller will skip category filter
    lower = raw_category.lower()
    for group, keywords in CATEGORY_GROUPS.items():
        if any(kw in lower for kw in keywords):
            return group
    return "Equity"  # default — most MFs are equity


def run_filter(
    session_dir,
    max_expense_ratio=None,
    min_aum=None,
    min_history_years=None,
    categories=None,          # list of broad groups e.g. ["Equity", "Bond"]
):
    """
    Apply filters to MFs in cache.
    categories=None means all categories are allowed.
    """
    os.makedirs(session_dir, exist_ok=True)
    db = MFDB()
    symbols = db.list_symbols()
    stats = {
        "Scanned": len(symbols),
        "Expense": 0, "AUM": 0, "History": 0, "Category": 0, "Passed": 0,
    }
    candidates = []
    today = datetime.now().date()

    # Bulk-load all metadata and history stats in two queries
    all_meta = db.get_all_metadata()
    history_stats = db.get_history_stats_bulk(symbols)

    for sym in symbols:
        meta = all_meta.get(sym)
        er   = meta.get("expense_ratio") if meta else None
        aum  = meta.get("aum")           if meta else None
        cat_raw   = (meta.get("category")    or "") if meta else ""
        broad_cat = _classify_category(cat_raw)

        # Expense ratio filter
        if max_expense_ratio is not None and er is not None:
            try:
                if float(er) > max_expense_ratio:
                    stats["Expense"] += 1
                    continue
            except (TypeError, ValueError):
                pass

        # AUM filter
        if min_aum is not None and (aum is None or float(aum) < min_aum):
            stats["AUM"] += 1
            continue

        # Category filter — skip if category metadata is absent (broad_cat is None)
        if categories and broad_cat is not None and broad_cat not in categories:
            stats["Category"] += 1
            continue

        # History filter
        hist = history_stats.get(sym)
        if hist is None:
            stats["History"] += 1
            continue
        min_date_str, _max_date_str, row_count = hist
        if row_count < 30:
            stats["History"] += 1
            continue
        try:
            start = datetime.strptime(min_date_str, "%Y-%m-%d").date()
        except Exception:
            stats["History"] += 1
            continue
        years = (today - start).days / 365.25
        if min_history_years is not None and years < min_history_years:
            stats["History"] += 1
            continue

        candidates.append({
            "symbol": sym,
            "name": (meta.get("name") or sym) if meta else sym,
            "fund_family": (meta.get("fund_family") or "") if meta else "",
            "category": cat_raw,
            "broad_category": broad_cat,
            "expense_ratio": er,
            "aum": aum,
            "history_years": round(years, 2),
        })

    stats["Passed"] = len(candidates)

    stats_path = os.path.join(session_dir, "mf_stats.json")
    with open(stats_path, "w") as f:
        json.dump({
            "Parameters": {
                "max_expense_ratio": max_expense_ratio,
                "min_aum": min_aum,
                "min_history_years": min_history_years,
                "categories": categories,
            },
            "Waterfall": stats,
        }, f, indent=2)

    cand_path = os.path.join(session_dir, "mf_candidates.csv")
    pd.DataFrame(candidates).to_csv(cand_path, index=False)
    print(f"Filter: {stats['Passed']} candidates. Stats: {stats}", flush=True)
    return cand_path, stats_path

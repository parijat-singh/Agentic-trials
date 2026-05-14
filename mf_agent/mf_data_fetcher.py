"""
Mutual Fund Data Fetcher - incremental download of NAV history and metadata.
Uses mf_cache.db (DELETE journal mode, safe on Google Drive).
Bulk DB queries avoid N+1 round-trips on slow storage paths.
"""
import os
import sys
import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from mf_agent.mf_db import MFDB

BATCH_SIZE = 30  # MFs are slower to download than ETFs — smaller batches

_OHLCV = frozenset({"Open", "High", "Low", "Close", "Volume",
                    "Adj Close", "Dividends", "Stock Splits"})

_UNIVERSE_PATH = os.path.join(config.MF_STORAGE_ROOT, "mf", "mf_universe.csv")


def _extract_ticker_df(data: pd.DataFrame, sym: str):
    """Extract a single ticker's DataFrame from a multi-ticker yf.download result."""
    if data is None or data.empty:
        return None
    try:
        if not isinstance(data.columns, pd.MultiIndex):
            df = data.dropna(how="all")
            return df if not df.empty else None
        lvl0 = data.columns.get_level_values(0).unique()
        lvl1 = data.columns.get_level_values(1).unique()
        if sym in lvl0:
            df = data[sym].dropna(how="all")
        elif sym in lvl1:
            df = data.xs(sym, axis=1, level=1).dropna(how="all")
        else:
            return None
        return df if not df.empty else None
    except Exception:
        return None


def _download_with_retry(symbols, max_retries=3, **kwargs):
    """yf.download with exponential back-off on rate-limit errors (HTTP 429)."""
    for attempt in range(max_retries):
        try:
            return yf.download(symbols, **kwargs)
        except Exception as e:
            msg = str(e).lower()
            if any(tok in msg for tok in ("rate limit", "too many requests", "429")):
                wait = 30 * (2 ** attempt)
                print(f"  Rate limited — retrying in {wait}s (attempt {attempt+1}/{max_retries})...", flush=True)
                time.sleep(wait)
            else:
                raise
    print("  Exhausted retries after rate-limit errors.", flush=True)
    return pd.DataFrame()


def _fetch_metadata(symbol: str) -> dict:
    """Fetch fund metadata via yfinance."""
    try:
        info = yf.Ticker(symbol).info
        er = info.get("annualReportExpenseRatio") or info.get("expenseRatio")
        aum = info.get("totalAssets") or info.get("netAssets")
        name = info.get("shortName") or info.get("longName") or symbol
        family = info.get("fundFamily") or ""
        # category: yfinance returns morningstar category
        category = info.get("category") or info.get("fundFamilyName") or ""
        return {
            "name": name, "fund_family": family, "category": category,
            "expense_ratio": er, "aum": aum,
        }
    except Exception:
        return {
            "name": symbol, "fund_family": "", "category": "",
            "expense_ratio": None, "aum": None,
        }


def run_fetcher(universe_path=None):
    """
    Fetch/update all MF data. Reads mf_universe.csv, incremental updates to mf_cache.db.
    Returns list of all symbols in cache.
    """
    if universe_path is None:
        universe_path = _UNIVERSE_PATH
    if not os.path.exists(universe_path):
        print(f"MF universe not found: {universe_path}. Run scraper first.", flush=True)
        return []

    df_uni = pd.read_csv(universe_path)
    symbols = df_uni["symbol"].astype(str).str.strip().unique().tolist()
    print(f"Processing {len(symbols)} mutual funds...", flush=True)

    db = MFDB()
    today = datetime.now().date()

    # Bulk cache check — single query instead of N individual connections
    print(f"Checking cache for {len(symbols)} symbols...", flush=True)
    latest_dates = db.get_latest_dates_bulk(symbols)

    symbols_fresh = []
    symbols_update: dict[str, list] = {}
    for sym in symbols:
        last = latest_dates.get(sym)
        if last is None:
            symbols_fresh.append(sym)
        else:
            nxt = last + timedelta(days=1)
            if nxt <= today:
                key = nxt.strftime("%Y-%m-%d")
                symbols_update.setdefault(key, []).append(sym)

    n_update = sum(len(v) for v in symbols_update.values())
    print(
        f"Cache check done: {len(symbols_fresh)} new, "
        f"{n_update} to update, "
        f"{len(latest_dates) - n_update} already current.",
        flush=True,
    )

    # --- Download full history for new symbols ---
    # Metadata is fetched separately in the back-fill step below — keeping price
    # downloads and metadata calls in distinct passes avoids 30 extra HTTP calls
    # per batch and reduces rate-limit exposure.
    for i in range(0, len(symbols_fresh), BATCH_SIZE):
        batch = symbols_fresh[i: i + BATCH_SIZE]
        print(
            f"Downloading full history for {len(batch)} new MFs "
            f"({i+1}-{i+len(batch)}/{len(symbols_fresh)})...",
            flush=True,
        )
        try:
            data = _download_with_retry(
                batch, period="max", group_by="ticker",
                auto_adjust=True, progress=False, threads=True,
            )
            if data.empty:
                continue
            if len(batch) == 1:
                sym = batch[0]
                sub = (_extract_ticker_df(data, sym)
                       if isinstance(data.columns, pd.MultiIndex)
                       else data.dropna(how="all") or None)
                if sub is not None:
                    db.save_history(sym, sub)
            else:
                for sym in batch:
                    sub = _extract_ticker_df(data, sym)
                    if sub is not None:
                        db.save_history(sym, sub)
            time.sleep(1)
        except Exception as e:
            print(f"Batch download failed: {e}", flush=True)

    # --- Incremental updates for existing symbols ---
    for start_str, syms in symbols_update.items():
        print(f"Updating {len(syms)} MFs from {start_str}...", flush=True)
        try:
            data = _download_with_retry(
                syms, start=start_str, group_by="ticker",
                auto_adjust=True, progress=False, threads=True,
            )
            if data.empty:
                continue
            if len(syms) == 1:
                sym = syms[0]
                sub = (_extract_ticker_df(data, sym)
                       if isinstance(data.columns, pd.MultiIndex)
                       else data.dropna(how="all") or None)
                if sub is not None:
                    db.save_history(sym, sub)
            else:
                for sym in syms:
                    sub = _extract_ticker_df(data, sym)
                    if sub is not None:
                        db.save_history(sym, sub)
            time.sleep(0.5)
        except Exception as e:
            print(f"Update failed ({start_str}): {e}", flush=True)

    # Back-fill metadata for any symbol still missing it.
    # This is the only place _fetch_metadata() is called — price downloads above
    # intentionally skip it to avoid 30 extra HTTP calls per batch.
    # Cap at 500 per run to stay within reasonable API rate limits; subsequent
    # runs will fill the remainder incrementally.
    all_syms = db.list_symbols()
    all_meta = db.get_all_metadata()
    missing_meta = [
        s for s in all_syms
        if s not in all_meta
        or (all_meta[s].get("aum") is None and all_meta[s].get("expense_ratio") is None)
    ]
    if missing_meta:
        to_fill = missing_meta[:500]
        print(
            f"Back-filling metadata for {len(to_fill)} symbols "
            f"({len(missing_meta)} total missing)...",
            flush=True,
        )
        for sym in to_fill:
            meta = _fetch_metadata(sym)
            db.save_mf_metadata(sym, **meta)
            time.sleep(0.2)

    print(f"Fetcher complete. {len(all_syms)} symbols in cache.", flush=True)
    return all_syms


if __name__ == "__main__":
    run_fetcher()

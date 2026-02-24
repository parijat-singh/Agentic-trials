"""
ETF Data Fetcher - incremental download of price data and metadata.
Uses etf_cache.db. Full history (period=max) for new symbols.
"""
import os
import sys
import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from etf_agent.etf_db import ETFDB

BATCH_SIZE = 50


def fetch_etf_metadata(symbol):
    """Get expense ratio, AUM, exchange, name from yfinance."""
    try:
        t = yf.Ticker(symbol)
        info = t.info
        er = info.get("annualReportExpenseRatio") or info.get("expenseRatio")
        aum = info.get("totalAssets") or info.get("netAssets")
        ex = info.get("exchange")
        name = info.get("shortName") or info.get("longName") or symbol
        return {"expense_ratio": er, "aum": aum, "exchange": ex, "name": name}
    except Exception:
        return {"expense_ratio": None, "aum": None, "exchange": None, "name": symbol}


def run_fetcher(universe_path=None):
    """Fetch/update all ETF data. Reads etf_universe.csv, incremental updates to etf_cache.db."""
    if universe_path is None:
        universe_path = os.path.join(config.ETF_STORAGE_ROOT, "etf", "etf_universe.csv")
    if not os.path.exists(universe_path):
        print(f"ETF universe not found: {universe_path}. Run scraper first.", flush=True)
        return []
    df = pd.read_csv(universe_path)
    symbols = df["symbol"].astype(str).str.strip().unique().tolist()
    print(f"Processing {len(symbols)} ETFs...", flush=True)
    db = ETFDB()
    today = datetime.now().date()
    symbols_fresh = []
    symbols_update = {}
    for sym in symbols:
        last = db.get_latest_date(sym)
        if last is None:
            symbols_fresh.append(sym)
        else:
            next_day = last + timedelta(days=1)
            if next_day <= today:
                key = next_day.strftime("%Y-%m-%d")
                symbols_update.setdefault(key, []).append(sym)
    for i in range(0, len(symbols_fresh), BATCH_SIZE):
        batch = symbols_fresh[i : i + BATCH_SIZE]
        print(f"Downloading full history for {len(batch)} new ETFs ({i+1}-{i+len(batch)}/{len(symbols_fresh)})...", flush=True)
        try:
            data = yf.download(batch, period="max", group_by="ticker", auto_adjust=True, progress=False, threads=True)
            if data.empty:
                continue
            if len(batch) == 1:
                if not data.empty:
                    db.save_history(batch[0], data)
                meta = fetch_etf_metadata(batch[0])
                db.save_etf_metadata(batch[0], meta["expense_ratio"], meta["aum"], meta["exchange"], meta["name"])
            else:
                for sym in batch:
                    if sym in data.columns.levels[0]:
                        sub = data[sym].dropna(how="all")
                        if not sub.empty:
                            db.save_history(sym, sub)
                    meta = fetch_etf_metadata(sym)
                    db.save_etf_metadata(sym, meta["expense_ratio"], meta["aum"], meta["exchange"], meta["name"])
            time.sleep(1)
        except Exception as e:
            print(f"Batch download failed: {e}", flush=True)
    for start_str, syms in symbols_update.items():
        print(f"Updating {len(syms)} ETFs from {start_str}...", flush=True)
        try:
            data = yf.download(syms, start=start_str, group_by="ticker", auto_adjust=True, progress=False, threads=True)
            if data.empty:
                continue
            if len(syms) == 1:
                if not data.empty:
                    db.save_history(syms[0], data)
            else:
                for sym in syms:
                    if sym in data.columns.levels[0]:
                        sub = data[sym].dropna(how="all")
                        if not sub.empty:
                            db.save_history(sym, sub)
            time.sleep(1)
        except Exception as e:
            print(f"Update failed: {e}", flush=True)
    all_syms = db.list_symbols()
    for sym in all_syms[:200]:
        m = db.get_etf_metadata(sym)
        if m is None or (m.get("aum") is None and m.get("expense_ratio") is None):
            meta = fetch_etf_metadata(sym)
            db.save_etf_metadata(sym, meta["expense_ratio"], meta["aum"], meta["exchange"], meta["name"])
            time.sleep(0.2)
    print(f"Fetcher complete. {len(all_syms)} symbols in cache.", flush=True)
    return all_syms


if __name__ == "__main__":
    run_fetcher()

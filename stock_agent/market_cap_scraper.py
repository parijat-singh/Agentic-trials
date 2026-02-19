import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import random
import yfinance as yf
import json
import argparse
import sys
import os

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# Global Constants
DATA_DIR = config.DATA_DIR

def get_companies_from_page(page_num):
    """
    Scrapes a single page of companiesmarketcap.com.
    Returns a list of dicts: {'rank': int, 'name': str, 'symbol': str, 'market_cap': str}
    """
    url = f"https://companiesmarketcap.com/page/{page_num}/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    print(f"Scraping page {page_num}...")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        companies = []
        
        rows = soup.find_all('tr')
        
        for row in rows:
            if not row.find('td', class_='name-td'):
                continue
                
            try:
                code_div = row.find('div', class_='company-code')
                if not code_div:
                    continue
                symbol = code_div.text.strip()
                
                name_div = row.find('div', class_='company-name')
                name = name_div.text.strip() if name_div else "Unknown"

                cols = row.find_all('td')
                mcap = "N/A"
                for col in cols:
                    if '$' in col.text:
                        mcap = col.text.strip()
                        break
                
                companies.append({
                    'symbol': symbol,
                    'name': name,
                    'market_cap': mcap
                })
            except Exception as e:
                continue
                
        return companies
        
    except Exception as e:
        print(f"Error scraping page {page_num}: {e}")
        return []

def is_likely_us_stock(symbol):
    """
    Heuristic: US stocks usually don't have a dot, or have .A/.B
    """
    if '.' in symbol:
        parts = symbol.split('.')
        suffix = parts[-1]
        if suffix in ['A', 'B']:
            return True
        return False
    return True

def get_pe_ratio(symbol):
    """
    Fetches P/E ratio for a single symbol.
    Returns float or None.
    """
    try:
        ticker = yf.Ticker(symbol)
        # Try fast_info first (sometimes works for basic stats?) - No, usually .info
        # .info is expensive but necessary for P/E
        info = ticker.info
        pe = info.get('trailingPE')
        if pe is None:
            pe = info.get('forwardPE') # Fallback? Maybe strict on trailing.
        return pe
    except Exception:
        return None

def parse_market_cap(mcap_str):
    """
    Parses market cap string like '$1.5 B', '$500 M' to Billions (float).
    Returns None if parsing fails.
    """
    if not mcap_str or mcap_str == 'N/A':
        return None
        
    try:
        # Remove '$' and spacing
        clean_str = mcap_str.replace('$', '').strip()
        
        if clean_str.endswith('B'):
            return float(clean_str[:-1].strip())
        elif clean_str.endswith('T'):
            return float(clean_str[:-1].strip()) * 1000
        elif clean_str.endswith('M'):
            return float(clean_str[:-1].strip()) / 1000
        else:
            return 0.0 # Unknown or small
    except:
        return None

def process_batch(companies, min_history, min_ipo_age, max_ipo_age, max_pe, min_market_cap=None):
    """
    Takes a list of company dicts.
    Filters by Market Cap (Pre-fetch), Date and P/E (Post-fetch).
    Uses SQLite DB to store/retrieve historical data, speeding up subsequent runs.
    """
    try:
        from db_manager import DBManager
    except ImportError:
        # Fallback if running as script from a different dir
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from db_manager import DBManager

    db = DBManager()
    
    today = datetime.now()
    max_start_date_history = today - timedelta(days=int(min_history*365))
    
    max_start_date_ipo = today - timedelta(days=int(min_ipo_age*365))
    min_start_date_ipo = today - timedelta(days=int(max_ipo_age*365))
    
    # 1. pre-filter symbols (US Only AND Market Cap)
    candidates = []
    skipped_non_us = 0
    skipped_mcap = 0
    
    stop_scan = False
    for c in companies:
        if min_market_cap is not None:
            mcap_val = parse_market_cap(c.get('market_cap'))
            if mcap_val is not None and mcap_val < min_market_cap:
                skipped_mcap += 1
                stop_scan = True
                print(f"DEBUG: Scraper Stop Condition Met: {c['symbol']} Market Cap {mcap_val} < {min_market_cap}")
                break 
                
            if mcap_val is None:
                continue

        if is_likely_us_stock(c['symbol']):
            candidates.append(c)
        else:
            skipped_non_us += 1
            
    if not candidates:
        return [], {"Non_US": skipped_non_us}, stop_scan
        
    # 2. Batch Download Strategy
    # Separation into: 
    # A) Fresh Download (Not in DB)
    # B) Incremental Update (In DB, needs latest data)
    
    symbols_fresh = []
    symbols_update = {} # date_str -> list of symbols
    
    # We will load data into this map to process filters later
    # Format: {symbol: dataframe}
    data_map = {} 
    
    print(f"Checking local database for {len(candidates)} candidates...", flush=True)
    
    for c in candidates:
        sym = c['symbol']
        last_date = db.get_latest_date(sym)
        
        if last_date:
            # Check if we need to update
            # If last_date is yesterday or today, we are good.
            # If last_date < today - 1 day, we download.
            # Actually, just download from last_date + 1 day
            
            # Load what we have
            df_existing = db.load_history(sym)
            data_map[sym] = df_existing
            
            next_day = last_date + timedelta(days=1)
            if next_day.date() <= today.date():
                date_str = next_day.strftime('%Y-%m-%d')
                if date_str not in symbols_update:
                    symbols_update[date_str] = []
                symbols_update[date_str].append(sym)
        else:
            symbols_fresh.append(sym)
            
    # Execute Fresh Downloads
    if symbols_fresh:
        print(f"Downloading full history for {len(symbols_fresh)} new stocks...", flush=True)
        try:
            # Use 'max' for fresh
            data = yf.download(symbols_fresh, period="max", group_by='ticker', auto_adjust=True, progress=False, threads=True)
            
            # Save to DB and Update data_map
            if len(symbols_fresh) == 1:
                # data is single DF
                sym = symbols_fresh[0]
                if not data.empty:
                    db.save_history(sym, data)
                    data_map[sym] = data # Use the new data
            else:
                for sym in symbols_fresh:
                    if sym in data.columns.levels[0]:
                        df = data[sym].dropna(how='all')
                        if not df.empty:
                            db.save_history(sym, df)
                            data_map[sym] = df
        except Exception as e:
            print(f"Fresh batch download failed: {e}")

    # Execute Updates
    if symbols_update:
        print(f"Updating {sum(len(v) for v in symbols_update.values())} stocks with new data...", flush=True)
        for start_date, syms in symbols_update.items():
            try:
                # If start date is in future (e.g. today is Sat, last data Fri), yf might return empty.
                data = yf.download(syms, start=start_date, group_by='ticker', auto_adjust=True, progress=False, threads=True)
                
                # Save to DB and Update data_map
                if len(syms) == 1:
                    sym = syms[0]
                    if not data.empty:
                        db.save_history(sym, data)
                        # Merge with existing in data_map
                        if sym in data_map:
                            data_map[sym] = pd.concat([data_map[sym], data])
                            data_map[sym] = data_map[sym][~data_map[sym].index.duplicated(keep='last')]
                else:
                    for sym in syms:
                        if sym in data.columns.levels[0]:
                            df = data[sym].dropna(how='all')
                            if not df.empty:
                                db.save_history(sym, df)
                                if sym in data_map:
                                    data_map[sym] = pd.concat([data_map[sym], df])
                                    data_map[sym] = data_map[sym][~data_map[sym].index.duplicated(keep='last')]
            except Exception as e:
                print(f"Update batch ({start_date}) failed: {e}")

    # 3. Process Logic
    accepted = []
    stats = {
        "Scanned": len(companies),
        "Non_US": skipped_non_us,
        "Too_Old": 0, 
        "Too_New": 0, 
        "Skipped_PE": 0,
        "Skipped_Market_Cap": skipped_mcap,
        "Errors": 0,
        "Selected": 0
    }
    
    for c in candidates:
        sym = c['symbol']
        
        # Get dataframe from map
        df = data_map.get(sym)
        
        if df is None or df.empty:
            stats["Errors"] += 1
            continue
            
        try:
            start_date = df.index[0]
            if start_date.tzinfo:
                start_date = start_date.tz_localize(None)
                
            # Date Checks
            if start_date > max_start_date_ipo: 
                stats["Too_New"] += 1 
                continue

            if start_date < min_start_date_ipo:
                stats["Too_Old"] += 1
                continue
                
            if start_date > max_start_date_history:
                 stats["Too_New"] += 1
                 continue
            
            # P/E Check (Fetch always for downstream, filter if requested)
            pe = get_pe_ratio(sym)
            if max_pe is not None:
                if pe is None or pe > max_pe or pe < 0:
                    stats["Skipped_PE"] += 1
                    continue
            
            # Accepted
            c['start_date'] = str(start_date.date())
            c['pe_ratio'] = pe 
                
            accepted.append(c)
            stats["Selected"] += 1
            
            # Save CSV for downstream modules (Backwards Compatibility)
            if not os.path.exists(DATA_DIR):
                os.makedirs(DATA_DIR)
            df.to_csv(f"{DATA_DIR}/{sym}.csv")
            
            pe_str = f" P/E: {pe:.2f}" if max_pe is not None else ""
            print(f"[MATCH] {sym}: Started {start_date.date()} (Cap: {c['market_cap']}){pe_str}", flush=True)

        except Exception as e:
            print(f"Error processing {sym}: {e}")
            stats["Errors"] += 1
            
    return accepted, stats, stop_scan

def main():
    parser = argparse.ArgumentParser(description="Scrape US Stocks with Filters")
    parser.add_argument("--min-history", type=float, default=5, help="Minimum years of history")
    parser.add_argument("--min-ipo", type=float, default=5, help="Minimum years since IPO")
    parser.add_argument("--max-ipo", type=float, default=10, help="Maximum years since IPO")
    parser.add_argument("--max-pe", type=float, default=None, help="Maximum P/E Ratio (None to disable)")
    parser.add_argument("--min-market-cap", type=float, default=None, help="Minimum Market Cap in Billions")
    parser.add_argument("--max-pages", type=int, default=200, help="Max pages to scan")
    
    args = parser.parse_args()
    
    print(f"=== Stock Data Agent: Scan (IPO {args.min_ipo}-{args.max_ipo}y, Hist {args.min_history}y, P/E < {args.max_pe}, Cap > {args.min_market_cap}B) ===")
    
    collected_stocks = []
    
    total_stats = {
        "Scanned": 0,
        "Non_US": 0,
        "Too_Old": 0,
        "Too_New": 0,
        "Skipped_PE": 0,
        "Skipped_Market_Cap": 0,
        "Errors": 0,
        "Selected": 0
    }
    
    page = 1
    MAX_PAGES = args.max_pages
    
    while page <= MAX_PAGES:
        print(f"\n--- Processing Page {page}/{MAX_PAGES} ---", flush=True)
        companies = get_companies_from_page(page)
        
        if not companies:
            print("No companies found or end of list.")
            break
            
        print(f"Found {len(companies)} companies. Checking filters...", flush=True)
        
        accepted_batch, batch_stats, stop_scan = process_batch(companies, args.min_history, args.min_ipo, args.max_ipo, args.max_pe, args.min_market_cap)
        
        for k, v in batch_stats.items():
            if k in total_stats:
                total_stats[k] += v
            else:
                total_stats[k] = v
                
        collected_stocks.extend(accepted_batch)
        
        print(f"Batch Result: {len(accepted_batch)} matches. Total Collected: {len(collected_stocks)}", flush=True)
        
        if stop_scan:
            print(f"Min Market Cap {args.min_market_cap}B reached. Stopping scan.")
            break
            
        page += 1
        time.sleep(1) 
        
    print(f"\nCollection Complete! Found {len(collected_stocks)} stocks out of {total_stats['Scanned']} scanned.")
    print("Final Stats:", json.dumps(total_stats, indent=2))
    
    df_meta = pd.DataFrame(collected_stocks)
    df_meta.to_csv(os.path.join(DATA_DIR, "top_100_new_stocks.csv"), index=False)
    
    # Save Stats for Waterfall
    total_stats["Parameters"] = {
        "Min_History": args.min_history,
        "Min_IPO": args.min_ipo,
        "Max_IPO": args.max_ipo,
        "Max_PE": args.max_pe,
        "Min_Market_Cap": args.min_market_cap
    }
    
    print(f"DEBUG: Saving stats with parameters: {total_stats['Parameters']}")
    with open(os.path.join(DATA_DIR, "scraping_stats.json"), "w") as f:
        json.dump(total_stats, f, indent=2)
        
    print("Metadata saved to 'top_100_new_stocks.csv'. Stats to 'scraping_stats.json'.")

if __name__ == "__main__":
    main()

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

# Global Constants
DATA_DIR = "data"

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

def process_batch(companies, min_history, min_ipo_age, max_ipo_age, max_pe):
    """
    Takes a list of company dicts.
    Filters by Date and P/E.
    """
    # Filters
    
    # IPO Window: 
    # Must have started BEFORE (Today - Min Age)
    # Must have started AFTER (Today - Max Age)
    
    # History:
    # Must have started BEFORE (Today - Min History)
    
    today = datetime.now()
    max_start_date_history = today - timedelta(days=int(min_history*365))
    
    max_start_date_ipo = today - timedelta(days=int(min_ipo_age*365))
    min_start_date_ipo = today - timedelta(days=int(max_ipo_age*365))
    
    # Combined Date Logic:
    # To pass Filter A (History): Start <= max_start_date_history
    # To pass Filter B (IPO Window): min_start_date_ipo <= Start <= max_start_date_ipo
    
    # 1. pre-filter symbols (US Only)
    candidates = []
    skipped_non_us = 0
    
    for c in companies:
        if is_likely_us_stock(c['symbol']):
            candidates.append(c)
        else:
            skipped_non_us += 1
            
    if not candidates:
        return [], {"Non_US": skipped_non_us}
        
    symbols = [c['symbol'] for c in candidates]
    
    # 2. Batch Download History
    print(f"Downloading batch of {len(symbols)} stocks...", flush=True)
    try:
        data = yf.download(symbols, period="max", group_by='ticker', auto_adjust=True, progress=False)
    except Exception as e:
        print(f"Batch download failed: {e}")
        return [], {"Errors": len(symbols)}

    accepted = []
    stats = {
        "Scanned": len(companies),
        "Non_US": skipped_non_us,
        "Too_Old": 0, # IPO > Max Age
        "Too_New": 0, # IPO < Min Age (or History < Min History)
        "Skipped_PE": 0,
        "Errors": 0,
        "Selected": 0
    }
    
    # 3. Process each ticker
    for c in candidates:
        sym = c['symbol']
        try:
            # dataframe extraction
            if len(symbols) == 1:
                df = data
            else:
                if sym not in data.columns.levels[0]:
                    stats["Errors"] += 1
                    continue
                df = data[sym]
            
            if df.empty:
                stats["Errors"] += 1
                continue
                
            df = df.dropna(how='all')
            if df.empty:
                stats["Errors"] += 1
                continue
                
            start_date = df.index[0]
            if start_date.tzinfo:
                start_date = start_date.tz_localize(None)
                
            # Date Logic
            # Note: We are looking for "IPO between 5 and 10 years ago"
            # AND "Trading history > 5 years"
            # Effectively, if Min History == Min IPO Age, these checks overlap efficiently.
            
            # Check 1: Is it too new? (IPO'd recently)
            # Start Date > (Today - Min IPO Age)
            if start_date > max_start_date_ipo: 
                stats["Too_New"] += 1 
                continue

            # Check 2: Is it too old? (IPO'd long ago)
            # Start Date < (Today - Max IPO Age)
            if start_date < min_start_date_ipo:
                stats["Too_Old"] += 1
                continue
                
            # Check 3: History length (Redundant if Min History <= Min IPO Age, but good for explicit check)
            if start_date > max_start_date_history:
                 stats["Too_New"] += 1
                 continue
            
            # --- DATE CHECKS PASSED ---
            
            # Check 4: P/E Ratio (if enabled)
            if max_pe is not None:
                pe = get_pe_ratio(sym)
                if pe is None or pe > max_pe or pe < 0: # Assuming we want positive P/E for "value"? Or just < max. 
                    # Let's assume < Max. If None (no earnings), skip? Yes, safer.
                    stats["Skipped_PE"] += 1
                    continue
            
            # MATCH!
            c['start_date'] = str(start_date.date())
            if max_pe is not None:
                c['pe_ratio'] = pe 
                
            accepted.append(c)
            stats["Selected"] += 1
            
            # Save CSV
            if not os.path.exists(DATA_DIR):
                os.makedirs(DATA_DIR)
            df.to_csv(f"{DATA_DIR}/{sym}.csv")
            
            pe_str = f" P/E: {pe:.2f}" if max_pe is not None else ""
            print(f"[MATCH] {sym}: Started {start_date.date()} (Cap: {c['market_cap']}){pe_str}", flush=True)

        except Exception as e:
            stats["Errors"] += 1
            
    return accepted, stats

def main():
    parser = argparse.ArgumentParser(description="Scrape US Stocks with Filters")
    parser.add_argument("--min-history", type=float, default=5, help="Minimum years of history")
    parser.add_argument("--min-ipo", type=float, default=5, help="Minimum years since IPO")
    parser.add_argument("--max-ipo", type=float, default=10, help="Maximum years since IPO")
    parser.add_argument("--max-pe", type=float, default=None, help="Maximum P/E Ratio (None to disable)")
    parser.add_argument("--max-pages", type=int, default=200, help="Max pages to scan")
    
    args = parser.parse_args()
    
    print(f"=== Stock Data Agent: Scan (IPO {args.min_ipo}-{args.max_ipo}y, History {args.min_history}y, P/E < {args.max_pe}) ===")
    
    collected_stocks = []
    
    total_stats = {
        "Scanned": 0,
        "Non_US": 0,
        "Too_Old": 0,
        "Too_New": 0,
        "Skipped_PE": 0,
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
        
        accepted_batch, batch_stats = process_batch(companies, args.min_history, args.min_ipo, args.max_ipo, args.max_pe)
        
        for k, v in batch_stats.items():
            if k in total_stats:
                total_stats[k] += v
            else:
                total_stats[k] = v
                
        collected_stocks.extend(accepted_batch)
        
        print(f"Batch Result: {len(accepted_batch)} matches. Total Collected: {len(collected_stocks)}", flush=True)
        
        page += 1
        time.sleep(1) 
        
    print(f"\nCollection Complete! Found {len(collected_stocks)} stocks out of {total_stats['Scanned']} scanned.")
    print("Final Stats:", json.dumps(total_stats, indent=2))
    
    df_meta = pd.DataFrame(collected_stocks)
    df_meta.to_csv("top_100_new_stocks.csv", index=False)
    
    # Save Stats for Waterfall
    total_stats["Parameters"] = {
        "Min_History": args.min_history,
        "Min_IPO": args.min_ipo,
        "Max_IPO": args.max_ipo,
        "Max_PE": args.max_pe
    }
    
    print(f"DEBUG: Saving stats with parameters: {total_stats['Parameters']}")
    with open("scraping_stats.json", "w") as f:
        json.dump(total_stats, f, indent=2)
        
    print("Metadata saved to 'top_100_new_stocks.csv'. Stats to 'scraping_stats.json'.")

if __name__ == "__main__":
    main()

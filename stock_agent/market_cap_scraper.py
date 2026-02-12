import requests
from bs4 import BeautifulSoup
# import pandas_datareader.data as web # Deprecated
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import random

# Global Constants
TARGET_COUNT = 100
TEN_YEARS_AGO = datetime.now() - timedelta(days=10*365)
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
        
        # The table rows are usually in <tr> elements inside <tbody>
        # The structure might vary, but typically:
        # <td class="name-td"><div class="company-name">Name</div><div class="company-code">Symbol</div></td>
        # <td class="td-right">Market Cap</td>
        
        rows = soup.find_all('tr')
        
        for row in rows:
            # Skip header or ad rows
            if not row.find('td', class_='name-td'):
                continue
                
            try:
                # Extract Symbol
                # Usually in <div class="company-code">
                code_div = row.find('div', class_='company-code')
                if not code_div:
                    continue
                symbol = code_div.text.strip()
                
                # Extract Name
                name_div = row.find('div', class_='company-name')
                name = name_div.text.strip() if name_div else "Unknown"

                # Extract Market Cap
                # Usually the 3rd column (index 2) or look for class 'td-right'
                cols = row.find_all('td')
                # Often the first 'td-right' is market cap, or specifically indexed
                # Let's try to find the one that looks like a market cap
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
                # print(f"Error parsing row: {e}")
                continue
                
        return companies
        
    except Exception as e:
        print(f"Error scraping page {page_num}: {e}")
        return []

import yfinance as yf

# Modified Goal: Filter for stocks with at least 5 years of history
FIVE_YEARS_AGO = datetime.now() - timedelta(days=5*365)

def check_history_and_download(symbol):
    """
    Checks if stock started trading > 5 years ago using yfinance.
    If yes, saves to CSV and returns (True, StartDate).
    If no or error, returns (False, None).
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Use yfinance Ticker
            ticker = yf.Ticker(symbol)
            
            # US Filter: Check currency
            try:
                currency = ticker.fast_info.get('currency', 'Unknown')
                if currency != 'USD':
                    return False, None
            except:
                pass

            # Fetch history metadata or full history (period="max")
            # "max" ensures we find the true start date
            hist = ticker.history(period="max", auto_adjust=True)
            
            if hist.empty:
                return False, None
                
            # yfinance returns index in ascending order (oldest first) usually
            # But let's verify
            hist = hist.sort_index()
            first_trade = hist.index[0]
            
            # Check if first trade is OLD enough (<= 5 years ago)
            # Meaning: It started trading BEFORE the cutoff.
            # Convert to tz-naive if needed for comparison, or ensure consistent timezone
            # FIVE_YEARS_AGO is naive (local time). hist.index is usually timezone-aware.
            if first_trade.tzinfo:
                first_trade = first_trade.tz_localize(None)
                
            if first_trade <= FIVE_YEARS_AGO:
                # It's a match!
                if not os.path.exists(DATA_DIR):
                    os.makedirs(DATA_DIR)
                    
                # Save data
                hist.to_csv(f"{DATA_DIR}/{symbol}.csv")
                return True, first_trade
            else:
                return False, first_trade
                
        except Exception as e:
            # print(f"Error checking {symbol} (Attempt {attempt+1}): {e}")
            if "Too Many Requests" in str(e):
                 time.sleep(10 * (attempt + 1)) # Backoff longer
            else:
                 time.sleep(2)
    return False, None

def main():
    print("=== Stock Data Agent: Top 100 New Stocks (Market Cap) ===")
    
    collected_stocks = []
    page = 1
    
    while len(collected_stocks) < TARGET_COUNT:
        print(f"\n--- Processing Page {page} ---")
        companies = get_companies_from_page(page)
        
        if not companies:
            print("No companies found or end of list.")
            break
            
        print(f"Found {len(companies)} companies on page {page}. Checking detailed history...")
        
        for comp in companies:
            if len(collected_stocks) >= TARGET_COUNT:
                break
                
            symbol = comp['symbol']
            
            # Skip if we already have it (unlikely in ordered list but good safety)
            if any(s['symbol'] == symbol for s in collected_stocks):
                continue

            # Check history
            is_new, start_date = check_history_and_download(symbol)
            
            if is_new:
                comp['start_date'] = start_date
                collected_stocks.append(comp)
                print(f"[MATCH] {symbol}: Started {start_date.date()} (Market Cap: {comp['market_cap']}) - Total: {len(collected_stocks)}/{TARGET_COUNT}")
            else:
                # Optional: Verbose logging
                # if start_date:
                #    print(f"[SKIP] {symbol}: Started {start_date.date()} (Too old)")
                pass
            
            # Be polite to yfinance - crucial to avoid 429
            time.sleep(2) 
            
        page += 1
        
    print(f"\nCollection Complete! Found {len(collected_stocks)} stocks.")
    
    # Save metadata
    df_meta = pd.DataFrame(collected_stocks)
    df_meta.to_csv("top_100_new_stocks.csv", index=False)
    print("Metadata saved to 'top_100_new_stocks.csv'. Data in 'data/'.")

if __name__ == "__main__":
    main()

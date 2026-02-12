import pandas as pd

import requests
from io import StringIO

def get_sp500_tickers():
    """Scrapes S&P 500 tickers from Wikipedia."""
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    # Use StringIO to wrap the string content for read_html
    tables = pd.read_html(StringIO(response.text))
    df = tables[0]
    return df['Symbol'].tolist()

def get_nasdaq100_tickers():
    """Scrapes NASDAQ 100 tickers from Wikipedia."""
    url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    tables = pd.read_html(StringIO(response.text))
    # The table index might vary, usually it's the 4th one (index 3) or similar.
    # We look for a table with 'Ticker' or 'Symbol' column.
    for table in tables:
        if 'Ticker' in table.columns:
            return table['Ticker'].tolist()
        if 'Symbol' in table.columns:
            return table['Symbol'].tolist()
    return []

def get_all_tickers():
    print("Fetching S&P 500 tickers...")
    sp500 = get_sp500_tickers()
    print(f"Found {len(sp500)} S&P 500 tickers.")

    print("Fetching NASDAQ 100 tickers...")
    nasdaq100 = get_nasdaq100_tickers()
    print(f"Found {len(nasdaq100)} NASDAQ 100 tickers.")

    # Combine and deduplicate
    all_tickers = list(set(sp500 + nasdaq100))
    # Replace . with - for Yahoo Finance compatibility (e.g. BRK.B -> BRK-B)
    all_tickers = [ticker.replace('.', '-') for ticker in all_tickers]
    
    print(f"Total unique tickers: {len(all_tickers)}")
    
    # Save to file
    with open("tickers.txt", "w") as f:
        for ticker in all_tickers:
            f.write(f"{ticker}\n")
    
    return all_tickers

if __name__ == "__main__":
    get_all_tickers()

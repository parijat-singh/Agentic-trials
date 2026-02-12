import yfinance as yf
import pandas as pd
import os
from datetime import datetime

def download_history():
    if not os.path.exists("top_100_new_stocks.csv"):
        print("Error: top_100_new_stocks.csv not found. Run filter_stocks.py first.")
        return

    df = pd.read_csv("top_100_new_stocks.csv")
    tickers = df['Symbol'].tolist()
    
    if not os.path.exists("data"):
        os.makedirs("data")
    
    print(f"Downloading history for {len(tickers)} stocks...")
    
    # yfinance allows bulk download
    # auto_adjust=True accounts for splits/dividends
    data = yf.download(tickers, period="10y", group_by='ticker', auto_adjust=True)
    
    for ticker in tickers:
        try:
            # Extract individual ticker dataframe
            stock_data = data[ticker]
            # Save to CSV
            file_path = f"data/{ticker}.csv"
            stock_data.to_csv(file_path)
        except Exception as e:
            print(f"Error saving {ticker}: {e}")
            
    print("Download complete. Check 'data/' folder.")

if __name__ == "__main__":
    download_history()

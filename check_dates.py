import pandas as pd
import os
import config

data_dir = config.DATA_DIR
portfolio_file = r"c:\Users\user\OneDrive\Documents\Coding\Agentic-trials\portfolio_optimizer\optimal_portfolio.csv"

# Load portfolio
if not os.path.exists(portfolio_file):
    print(f"Portfolio file not found: {portfolio_file}")
    exit()

df_port = pd.read_csv(portfolio_file)
symbols = df_port['Symbol'].tolist()

print(f"Checking data for {len(symbols)} symbols in {data_dir}...")

for sym in symbols:
    file_path = os.path.join(data_dir, f"{sym}.csv")
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        if 'Date' in df.columns:
            start_date = df['Date'].iloc[0]
            end_date = df['Date'].iloc[-1]
            print(f"{sym}: {start_date} to {end_date}")
        else:
            print(f"{sym}: No 'Date' column found.")
    else:
        print(f"{sym}: CSV file not found.")

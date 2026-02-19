import sys
import os
import glob
import pandas as pd

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from stock_agent.db_manager import DBManager

def main():
    print("=== Populating Database from CSVs ===")
    
    data_dir = config.DATA_DIR
    if not os.path.exists(data_dir):
        print(f"Error: Data directory {data_dir} not found.")
        return
        
    db = DBManager()
    
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    print(f"Found {len(csv_files)} CSV files in {data_dir}")
    
    success_count = 0
    error_count = 0
    
    for file_path in csv_files:
        try:
            symbol = os.path.basename(file_path).replace(".csv", "")
            
            # Skip metadata file
            if symbol == "top_100_new_stocks":
                 continue
                 
            # Check if symbol already has data (optimization)
            # Actually, save_history appends or fails on primary key.
            # We should probably trust save_history to handle it, or check latest date.
            # Let's just try to save.
            
            df = pd.read_csv(file_path)
            
            if df.empty:
                print(f"Skipping empty file: {file_path}")
                continue
                
            # Ensure Date column formatting matches expected
            # yfinance Index was Date. read_csv might make it a column.
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df.set_index('Date', inplace=True)
            elif df.index.name == 'Date':
                # Already index? read_csv usually doesn't set index auto unless specified
                pass
            else:
                 # Check if first column is date-like?
                 # Assuming standard yfinance CSV format: Date,Open,High,Low,Close,Volume...
                 pass
            
            # Convert index to datetime if it's strings
            if not isinstance(df.index, pd.DatetimeIndex):
                 # Maybe 'Date' is a column but not index? 
                 # run_history expects df with columns Open,High,Low,Close,Volume. 
                 # If Date is index, DBManager resets it.
                 pass

            # DBManager.save_history expects a DataFrame. 
            # It checks for 'Date' column or index.
            # Let's verify columns.
            required = {'Open', 'High', 'Low', 'Close', 'Volume'}
            if not required.issubset(df.columns):
                 # maybe it has different case?
                 # yfinance is usually Title Case.
                 pass

            db.save_history(symbol, df)
            success_count += 1
            if success_count % 10 == 0:
                print(f"Imported {success_count} stocks...", flush=True)
                
        except Exception as e:
            print(f"Error importing {file_path}: {e}")
            error_count += 1
            
    print(f"\nImport Complete.")
    print(f"Successfully imported: {success_count}")
    print(f"Errors: {error_count}")

if __name__ == "__main__":
    main()

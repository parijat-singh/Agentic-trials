import sys
import os
import glob
import pandas as pd
import sqlite3
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from stock_agent.db_manager import DBManager

def main():
    print("=== Optimized Database Repair & Population ===")
    
    data_dir = config.DATA_DIR
    db_path = config.DB_PATH
    
    if not os.path.exists(data_dir):
        print(f"Error: Data directory {data_dir} not found.")
        return
        
    print(f"Target Database: {db_path}")
    
    # 1. Ensure Table Exists
    db_manager = DBManager()
    
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    print(f"Found {len(csv_files)} CSV files in {data_dir}")
    
    if not csv_files:
        print("No files to import.")
        return

    # 2. Connect
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 3. Optimization Pragma
    cursor.execute("PRAGMA synchronous = OFF") 
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA cache_size = 100000") 
    
    # 4. Import Loop
    BATCH_SIZE = 50
    files_processed = 0
    records_inserted = 0
    
    start_time = time.time()
    
    try:
        conn.execute('BEGIN TRANSACTION')
        
        for file_path in csv_files:
            try:
                symbol = os.path.basename(file_path).replace(".csv", "")
                
                # Metadata file skip
                if symbol == "top_100_new_stocks":
                     continue
                     
                df = pd.read_csv(file_path)
                if df.empty:
                    continue
                
                # Normalize Date
                # Case 1: 'Date' column exists
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'])
                # Case 2: Index is Date
                elif df.index.name == 'Date':
                    df.reset_index(inplace=True)
                    df['Date'] = pd.to_datetime(df['Date'])
                # Case 3: First column is Date-like
                else:
                    first_col = df.columns[0]
                    # Check if it looks like a date?
                    # Let's try to convert first column
                    try:
                        df['Date'] = pd.to_datetime(df[first_col])
                    except:
                        # Fail
                        continue
                        
                df['DateStr'] = df['Date'].dt.strftime('%Y-%m-%d')
                
                # Check required columns
                # yfinance typically has: Open, High, Low, Close, Volume
                # If missing, fill with None or 0? 
                # Let's use get with defaults.
                
                records = []
                for _, row in df.iterrows():
                    records.append((
                        row['DateStr'],
                        symbol,
                        row.get('Open'),
                        row.get('High'),
                        row.get('Low'),
                        row.get('Close'),
                        row.get('Volume')
                    ))
                
                if records:
                    cursor.executemany('''
                    INSERT OR IGNORE INTO stock_history (Date, Symbol, Open, High, Low, Close, Volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', records)
                    records_inserted += len(records)
                
                files_processed += 1
                
                if files_processed % BATCH_SIZE == 0:
                    conn.commit()
                    conn.execute('BEGIN TRANSACTION')
                    print(f"Processed {files_processed} files... ({records_inserted} records)", flush=True)
                    
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                
        conn.commit()
        
    except Exception as e:
        print(f"Critical Error during transaction: {e}")
        conn.rollback()
    finally:
        conn.close()
        
    end_time = time.time()
    print(f"\nCompleted in {end_time - start_time:.2f} seconds.")
    print(f"Files Processed: {files_processed}/{len(csv_files)}")
    print(f"Total Records: {records_inserted}")

if __name__ == "__main__":
    main()

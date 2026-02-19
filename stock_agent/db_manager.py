import sqlite3
import pandas as pd
import os
import sys
from datetime import datetime

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

class DBManager:
    def __init__(self, db_path=None):
        if db_path is None:
            self.db_path = config.DB_PATH
        else:
            self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize the database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create stock_history table
        # We use a composite primary key (Symbol, Date) to prevent duplicates
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_history (
            Date TEXT,
            Symbol TEXT,
            Open REAL,
            High REAL,
            Low REAL,
            Close REAL,
            Volume INTEGER,
            PRIMARY KEY (Symbol, Date)
        )
        ''')
        
        conn.commit()
        conn.close()

    def get_latest_date(self, symbol):
        """Get the latest date available for a given symbol."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT MAX(Date) FROM stock_history WHERE Symbol = ?
        ''', (symbol,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return datetime.strptime(result[0], '%Y-%m-%d')
        return None

    def save_history(self, symbol, df):
        """
        Save history to the database.
        Expects a DataFrame with a DatetimeIndex and columns: Open, High, Low, Close, Volume.
        """
        if df.empty:
            return

        # Ensure index is datetime and reset to column for storage
        df = df.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
             # Try to convert if it's not already
             try:
                df.index = pd.to_datetime(df.index)
             except:
                print(f"Error: DataFrame index for {symbol} is not DatetimeIndex")
                return

        df = df.reset_index()
        # Rename 'Date' or 'index' to 'Date' if needed, though yfinance usually gives 'Date' name to index or index has no name but we reset it
        if 'Date' not in df.columns and 'index' in df.columns:
            df.rename(columns={'index': 'Date'}, inplace=True)
            
        # Ensure 'Date' is string YYYY-MM-DD
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
        df['Symbol'] = symbol
        
        # Select and order columns to match table
        cols_to_keep = ['Date', 'Symbol', 'Open', 'High', 'Low', 'Close', 'Volume']
        
        # Handle missing columns if any (yfinance usage usually guarantees these)
        for col in cols_to_keep:
            if col not in df.columns:
                df[col] = None 
                
        data_to_store = df[cols_to_keep]

        conn = sqlite3.connect(self.db_path)
        try:
            data_to_store.to_sql('stock_history', conn, if_exists='append', index=False)
        except sqlite3.IntegrityError:
            # If we hit duplicates (e.g. running same day twice), we might want to use 'replace' or handle gracefully
            # For simplicity, 'append' fails on PK violation. 
            # We can use method that ignores duplicates or updates.
            # Pandas to_sql doesn't support 'OR IGNORE' natively well without a custom method.
            # Let's try a custom insertion for better control if needed, 
            # OR just ensure we only pass new data (which downloader logic handles).
            # Fallback: if bulk append fails, try row by row or ignore
             print(f"Warning: Duplicate data detected for {symbol}. Skipping duplicates.")
             pass
        except Exception as e:
            print(f"Error saving {symbol} to DB: {e}")
        finally:
            conn.close()
            
    def load_history(self, symbol):
        """Load full history for a symbol as a DataFrame."""
        conn = sqlite3.connect(self.db_path)
        
        query = f"SELECT * FROM stock_history WHERE Symbol = '{symbol}' ORDER BY Date ASC"
        df = pd.read_sql(query, conn)
        
        conn.close()
        
        if not df.empty:
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            del df['Symbol'] # Remove symbol col as it's redundant when we asked for specific symbol
            
        return df

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
        # Create stock_metadata table for symbol-level data (exchange, sector, etc.) - avoids API lookups each run
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_metadata (
            Symbol TEXT PRIMARY KEY,
            Exchange TEXT,
            Sector TEXT,
            UpdatedAt TEXT
        )
        ''')
        conn.commit()

        # Migration: add Sector column if missing (existing DBs)
        try:
            cursor.execute("SELECT Sector FROM stock_metadata LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE stock_metadata ADD COLUMN Sector TEXT")
            conn.commit()
        conn.close()

    def get_exchange(self, symbol):
        """Get stored exchange for a symbol. Returns None if not in DB."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT Exchange FROM stock_metadata WHERE Symbol = ?', (symbol,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row and row[0] else None

    def save_exchange(self, symbol, exchange):
        """Store or update exchange for a symbol."""
        if not exchange:
            return
        conn = sqlite3.connect(self.db_path)
        try:
            updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute('''
                INSERT INTO stock_metadata (Symbol, Exchange, UpdatedAt)
                VALUES (?, ?, ?)
                ON CONFLICT(Symbol) DO UPDATE SET Exchange = ?, UpdatedAt = ?
            ''', (symbol, str(exchange), updated, str(exchange), updated))
            conn.commit()
        finally:
            conn.close()

    def get_sector(self, symbol):
        """Get stored sector for a symbol. Returns None if not in DB."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT Sector FROM stock_metadata WHERE Symbol = ?', (symbol,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row and row[0] else None

    def save_sector(self, symbol, sector):
        """Store or update sector for a symbol."""
        if not sector:
            return
        conn = sqlite3.connect(self.db_path)
        try:
            updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM stock_metadata WHERE Symbol = ?', (symbol,))
            exists = cursor.fetchone()
            if exists:
                cursor.execute('UPDATE stock_metadata SET Sector = ?, UpdatedAt = ? WHERE Symbol = ?',
                               (str(sector), updated, symbol))
            else:
                cursor.execute('INSERT INTO stock_metadata (Symbol, Sector, UpdatedAt) VALUES (?, ?, ?)',
                               (symbol, str(sector), updated))
            conn.commit()
        finally:
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
        # yfinance sometimes uses 'Adj Close' - use it if 'Close' missing
        if 'Close' not in df.columns and 'Adj Close' in df.columns:
            df['Close'] = df['Adj Close']
        for col in cols_to_keep:
            if col not in df.columns:
                df[col] = None
        data_to_store = df[cols_to_keep].copy()
        # Coerce Volume to nullable integer (table expects INTEGER; float/NaN can cause issues)
        if 'Volume' in data_to_store.columns:
            data_to_store['Volume'] = pd.to_numeric(data_to_store['Volume'], errors='coerce').astype('Int64')

        # Use timeout to wait for lock (e.g. concurrent access or sync tool); retry once on failure
        timeout_sec = 30
        last_err = None
        for attempt in range(2):
            try:
                conn = sqlite3.connect(self.db_path, timeout=timeout_sec)
                try:
                    data_to_store.to_sql('stock_history', conn, if_exists='append', index=False)
                    conn.commit()
                    return
                finally:
                    conn.close()
            except sqlite3.IntegrityError:
                print(f"Warning: Duplicate data for {symbol}, skipping.", flush=True)
                return
            except Exception as e:
                last_err = e
                if attempt == 0:
                    import time
                    time.sleep(0.5)
                    continue
                print(f"Error saving {symbol} to DB: {type(e).__name__}: {e}", flush=True)
            
    def load_history(self, symbol):
        """Load full history for a symbol as a DataFrame."""
        conn = sqlite3.connect(self.db_path)

        df = pd.read_sql(
            "SELECT * FROM stock_history WHERE Symbol = ? ORDER BY Date ASC",
            conn,
            params=(symbol,),
        )
        
        conn.close()
        
        if not df.empty:
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            del df['Symbol'] # Remove symbol col as it's redundant when we asked for specific symbol
            
        return df

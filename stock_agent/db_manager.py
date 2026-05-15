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
            try:
                df.index = pd.to_datetime(df.index)
            except Exception:
                print(f"Error: DataFrame index for {symbol} is not DatetimeIndex", flush=True)
                return

        df = df.reset_index()
        # Normalise the date column: yfinance uses 'Date' (daily) or 'Datetime' (intraday);
        # after reset_index() an unnamed index becomes 'index'.
        for _date_col in ('Datetime', 'index'):
            if 'Date' not in df.columns and _date_col in df.columns:
                df.rename(columns={_date_col: 'Date'}, inplace=True)
                break

        # Ensure 'Date' is string YYYY-MM-DD
        df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
        df['Symbol'] = symbol

        # Select and order columns to match table
        cols_to_keep = ['Date', 'Symbol', 'Open', 'High', 'Low', 'Close', 'Volume']
        # yfinance sometimes uses 'Adj Close' — use it when 'Close' is absent
        if 'Close' not in df.columns and 'Adj Close' in df.columns:
            df['Close'] = df['Adj Close']
        for col in cols_to_keep:
            if col not in df.columns:
                df[col] = None
        data_to_store = df[cols_to_keep].copy()
        # Use float64 for all numeric columns — sqlite3 cannot bind pandas NA/Int64,
        # and NaN in float64 maps cleanly to SQL NULL.
        for col in ('Open', 'High', 'Low', 'Close', 'Volume'):
            data_to_store[col] = pd.to_numeric(data_to_store[col], errors='coerce')

        # Build plain Python tuples: sqlite3 cannot bind numpy/pandas NA types,
        # and pandas wraps IntegrityError inside DatabaseError so catching it is
        # unreliable. Using executemany + INSERT OR IGNORE fixes both problems.
        _INSERT = (
            'INSERT OR IGNORE INTO stock_history '
            '(Date, Symbol, Open, High, Low, Close, Volume) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)'
        )

        def _py(v):
            """Convert a value to a sqlite3-safe Python scalar (NaN/NA → None)."""
            if v is None:
                return None
            try:
                import math
                if isinstance(v, float) and math.isnan(v):
                    return None
            except Exception:
                pass
            try:
                if pd.isna(v):
                    return None
            except Exception:
                pass
            # unwrap numpy scalars to Python natives
            return v.item() if hasattr(v, 'item') else v

        rows = [tuple(_py(v) for v in row)
                for row in data_to_store.itertuples(index=False, name=None)]

        timeout_sec = 30
        for attempt in range(2):
            try:
                conn = sqlite3.connect(self.db_path, timeout=timeout_sec)
                try:
                    conn.executemany(_INSERT, rows)
                    conn.commit()
                    return
                finally:
                    conn.close()
            except Exception as e:
                if attempt == 0:
                    import time
                    time.sleep(0.5)
                    continue
                cause = getattr(e, '__cause__', None) or getattr(e, '__context__', None)
                detail = f" (caused by: {cause})" if cause else ""
                print(f"Error saving {symbol} to DB: {type(e).__name__}: {e}{detail}", flush=True)
            
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

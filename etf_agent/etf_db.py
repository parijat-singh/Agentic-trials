"""
ETF cache database - SQLite with WAL mode for concurrent reads.
Stores ETF price history and metadata. All data on cloud/G Drive path.
"""
import sqlite3
import pandas as pd
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class ETFDB:
    def __init__(self, db_path=None):
        self.db_path = db_path or config.ETF_CACHE_DB
        self.init_db()

    def init_db(self):
        """Initialize database tables.
        Note: WAL mode is intentionally NOT used here — the DB lives on Google Drive,
        which cannot handle WAL's -wal/-shm lock files, causing disk I/O errors.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS etf_history (
                Date TEXT,
                Symbol TEXT,
                Open REAL,
                High REAL,
                Low REAL,
                Close REAL,
                Volume INTEGER,
                PRIMARY KEY (Symbol, Date)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS etf_metadata (
                Symbol TEXT PRIMARY KEY,
                ExpenseRatio REAL,
                AUM REAL,
                Exchange TEXT,
                Name TEXT,
                UpdatedAt TEXT
            )
        """)
        conn.commit()
        conn.close()

    def get_latest_date(self, symbol):
        """Get the latest date available for a symbol."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(Date) FROM etf_history WHERE Symbol = ?", (symbol,))
        result = cursor.fetchone()
        conn.close()
        if result and result[0]:
            return datetime.strptime(result[0], "%Y-%m-%d").date()
        return None

    def get_latest_dates_bulk(self, symbols):
        """Return a dict {symbol: date} of the latest date for each symbol in one query.
        Symbols with no data are absent from the returned dict.
        """
        if not symbols:
            return {}
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # SQLite supports up to ~999 bind params; chunk if needed
        result = {}
        chunk_size = 900
        for i in range(0, len(symbols), chunk_size):
            chunk = symbols[i : i + chunk_size]
            placeholders = ",".join("?" * len(chunk))
            cursor.execute(
                f"SELECT Symbol, MAX(Date) FROM etf_history WHERE Symbol IN ({placeholders}) GROUP BY Symbol",
                chunk,
            )
            for sym, max_date in cursor.fetchall():
                if max_date:
                    result[sym] = datetime.strptime(max_date, "%Y-%m-%d").date()
        conn.close()
        return result

    def save_history(self, symbol, df):
        """Save price history to etf_history. Expects DatetimeIndex, columns: Open, High, Low, Close, Volume."""
        if df is None or df.empty:
            return
        df = df.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        df = df.reset_index()
        if "Date" not in df.columns and "index" in df.columns:
            df = df.rename(columns={"index": "Date"})
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
        df["Symbol"] = symbol
        cols = ["Date", "Symbol", "Open", "High", "Low", "Close", "Volume"]
        for c in cols:
            if c not in df.columns:
                df[c] = None
        data = df[cols]
        conn = sqlite3.connect(self.db_path)
        try:
            data.to_sql("etf_history", conn, if_exists="append", index=False)
        except sqlite3.IntegrityError:
            pass
        except Exception as e:
            print(f"Error saving {symbol}: {e}", flush=True)
        finally:
            conn.close()

    def load_history(self, symbol):
        """Load full history for symbol as DataFrame with Date index."""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql("SELECT * FROM etf_history WHERE Symbol = ? ORDER BY Date ASC", conn, params=(symbol,))
        conn.close()
        if df.empty:
            return pd.DataFrame()
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
        if "Symbol" in df.columns:
            df = df.drop(columns=["Symbol"])
        return df

    def get_all_metadata(self):
        """Return a dict {symbol: {expense_ratio, aum, exchange, name}} for all symbols in one query."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT Symbol, ExpenseRatio, AUM, Exchange, Name, UpdatedAt FROM etf_metadata")
        rows = cursor.fetchall()
        conn.close()
        result = {}
        for sym, er, aum, ex, name, updated_at in rows:
            result[sym] = {
                "symbol": sym,
                "expense_ratio": er,
                "aum": aum,
                "exchange": ex,
                "name": name,
                "updated_at": updated_at,
            }
        return result

    def get_history_stats_bulk(self, symbols):
        """Return a dict {symbol: (min_date, max_date, row_count)} in one query."""
        if not symbols:
            return {}
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        result = {}
        chunk_size = 900
        for i in range(0, len(symbols), chunk_size):
            chunk = symbols[i : i + chunk_size]
            placeholders = ",".join("?" * len(chunk))
            cursor.execute(
                f"SELECT Symbol, MIN(Date), MAX(Date), COUNT(*) FROM etf_history "
                f"WHERE Symbol IN ({placeholders}) GROUP BY Symbol",
                chunk,
            )
            for sym, min_d, max_d, cnt in cursor.fetchall():
                result[sym] = (min_d, max_d, cnt)
        conn.close()
        return result

    def get_etf_metadata(self, symbol):
        """Get stored metadata for symbol. Returns dict or None."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT Symbol, ExpenseRatio, AUM, Exchange, Name, UpdatedAt FROM etf_metadata WHERE Symbol = ?",
            (symbol,),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "symbol": row[0],
            "expense_ratio": row[1],
            "aum": row[2],
            "exchange": row[3],
            "name": row[4],
            "updated_at": row[5],
        }

    def save_etf_metadata(self, symbol, expense_ratio=None, aum=None, exchange=None, name=None):
        """Store or update ETF metadata."""
        updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO etf_metadata (Symbol, ExpenseRatio, AUM, Exchange, Name, UpdatedAt)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(Symbol) DO UPDATE SET
                    ExpenseRatio=excluded.ExpenseRatio,
                    AUM=excluded.AUM,
                    Exchange=excluded.Exchange,
                    Name=excluded.Name,
                    UpdatedAt=excluded.UpdatedAt
                """,
                (symbol, expense_ratio, aum, exchange or "", name or "", updated),
            )
            conn.commit()
        finally:
            conn.close()

    def list_symbols(self):
        """Return list of all symbols in etf_history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT Symbol FROM etf_history")
        symbols = [r[0] for r in cursor.fetchall()]
        conn.close()
        return symbols

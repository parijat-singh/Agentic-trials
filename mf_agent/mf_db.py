"""
Mutual Fund cache database - SQLite with DELETE journal mode.
Stores MF price history (NAV) and metadata. Cloud/Google Drive safe (no WAL).
"""
import sqlite3
import pandas as pd
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class MFDB:
    def __init__(self, db_path=None):
        self.db_path = db_path or config.MF_CACHE_DB
        self.init_db()

    def init_db(self):
        """Initialize database tables. DELETE journal mode — safe on Google Drive."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mf_history (
                Date   TEXT,
                Symbol TEXT,
                Open   REAL,
                High   REAL,
                Low    REAL,
                Close  REAL,
                Volume INTEGER,
                PRIMARY KEY (Symbol, Date)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mf_metadata (
                Symbol       TEXT PRIMARY KEY,
                Name         TEXT,
                FundFamily   TEXT,
                Category     TEXT,
                ExpenseRatio REAL,
                AUM          REAL,
                UpdatedAt    TEXT
            )
        """)
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------ history

    def get_latest_dates_bulk(self, symbols):
        """Return {symbol: date} for all symbols in one query (no N+1)."""
        if not symbols:
            return {}
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        result = {}
        chunk_size = 900
        for i in range(0, len(symbols), chunk_size):
            chunk = symbols[i: i + chunk_size]
            placeholders = ",".join("?" * len(chunk))
            cursor.execute(
                f"SELECT Symbol, MAX(Date) FROM mf_history "
                f"WHERE Symbol IN ({placeholders}) GROUP BY Symbol",
                chunk,
            )
            for sym, max_date in cursor.fetchall():
                if max_date:
                    result[sym] = datetime.strptime(max_date, "%Y-%m-%d").date()
        conn.close()
        return result

    def get_history_stats_bulk(self, symbols):
        """Return {symbol: (min_date, max_date, row_count)} in one query."""
        if not symbols:
            return {}
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        result = {}
        chunk_size = 900
        for i in range(0, len(symbols), chunk_size):
            chunk = symbols[i: i + chunk_size]
            placeholders = ",".join("?" * len(chunk))
            cursor.execute(
                f"SELECT Symbol, MIN(Date), MAX(Date), COUNT(*) FROM mf_history "
                f"WHERE Symbol IN ({placeholders}) GROUP BY Symbol",
                chunk,
            )
            for sym, mn, mx, cnt in cursor.fetchall():
                result[sym] = (mn, mx, cnt)
        conn.close()
        return result

    def save_history(self, symbol, df):
        """Save NAV history. Expects DatetimeIndex with Close (and optionally OHLCV)."""
        if df is None or df.empty:
            return
        df = df.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception:
                return
        df = df.reset_index()
        # Normalise index column name — yfinance may call it Date, Datetime, or index
        for candidate in ("Date", "Datetime", "index"):
            if candidate in df.columns:
                df = df.rename(columns={candidate: "Date"})
                break
        if "Date" not in df.columns:
            return
        # Convert to plain date strings; strip timezone if present
        df["Date"] = pd.to_datetime(df["Date"], utc=True).dt.strftime("%Y-%m-%d")
        df["Symbol"] = symbol

        def _to_float(v):
            try:
                f = float(v)
                return None if (f != f) else f   # NaN → None
            except Exception:
                return None

        def _to_int(v):
            try:
                f = float(v)
                return None if (f != f) else int(f)
            except Exception:
                return None

        rows = []
        for _, row in df.iterrows():
            rows.append((
                row["Date"],
                symbol,
                _to_float(row.get("Open")),
                _to_float(row.get("High")),
                _to_float(row.get("Low")),
                _to_float(row.get("Close")),
                _to_int(row.get("Volume")),
            ))

        if not rows:
            return
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executemany(
                "INSERT OR IGNORE INTO mf_history "
                "(Date, Symbol, Open, High, Low, Close, Volume) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            conn.commit()
        except Exception as e:
            print(f"Error saving {symbol}: {e}", flush=True)
        finally:
            conn.close()

    def load_history(self, symbol):
        """Load full NAV history as DataFrame with DatetimeIndex."""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql(
            "SELECT * FROM mf_history WHERE Symbol = ? ORDER BY Date ASC",
            conn, params=(symbol,)
        )
        conn.close()
        if df.empty:
            return pd.DataFrame()
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
        if "Symbol" in df.columns:
            df = df.drop(columns=["Symbol"])
        return df

    def list_symbols(self):
        """Return all symbols that have price history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT Symbol FROM mf_history")
        symbols = [r[0] for r in cursor.fetchall()]
        conn.close()
        return symbols

    # ----------------------------------------------------------------- metadata

    def get_all_metadata(self):
        """Return {symbol: dict} for all symbols in one query."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT Symbol, Name, FundFamily, Category, ExpenseRatio, AUM, UpdatedAt "
            "FROM mf_metadata"
        )
        rows = cursor.fetchall()
        conn.close()
        result = {}
        for sym, name, family, cat, er, aum, updated in rows:
            result[sym] = {
                "symbol": sym, "name": name, "fund_family": family,
                "category": cat, "expense_ratio": er, "aum": aum,
                "updated_at": updated,
            }
        return result

    def get_mf_metadata(self, symbol):
        """Get metadata for a single symbol."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT Symbol, Name, FundFamily, Category, ExpenseRatio, AUM, UpdatedAt "
            "FROM mf_metadata WHERE Symbol = ?", (symbol,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "symbol": row[0], "name": row[1], "fund_family": row[2],
            "category": row[3], "expense_ratio": row[4], "aum": row[5],
            "updated_at": row[6],
        }

    def save_mf_metadata(self, symbol, name=None, fund_family=None,
                         category=None, expense_ratio=None, aum=None):
        """Upsert metadata for a symbol."""
        updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO mf_metadata
                    (Symbol, Name, FundFamily, Category, ExpenseRatio, AUM, UpdatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(Symbol) DO UPDATE SET
                    Name=excluded.Name,
                    FundFamily=excluded.FundFamily,
                    Category=excluded.Category,
                    ExpenseRatio=excluded.ExpenseRatio,
                    AUM=excluded.AUM,
                    UpdatedAt=excluded.UpdatedAt
                """,
                (symbol, name or "", fund_family or "", category or "",
                 expense_ratio, aum, updated),
            )
            conn.commit()
        finally:
            conn.close()

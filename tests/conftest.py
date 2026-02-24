"""
Pytest configuration and fixtures.
"""
import os
import sys
import tempfile
import shutil
import sqlite3

import pytest
import numpy as np
import pandas as pd

# Add project root to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "portfolio_optimizer"))
sys.path.insert(0, os.path.join(BASE_DIR, "financial_engine"))
sys.path.insert(0, os.path.join(BASE_DIR, "stock_agent"))


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test data."""
    path = tempfile.mkdtemp()
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def sample_prices_df():
    """Sample price DataFrame for Sharpe/optimizer tests."""
    dates = pd.date_range(start="2020-01-01", periods=252, freq="B")
    return pd.DataFrame({
        "Close": [100 * (1.001) ** i + (i % 10) * 0.1 for i in range(252)]
    }, index=dates)


@pytest.fixture
def sample_multi_stock_prices():
    """Multi-stock price DataFrame. Need 5+ stocks for optimizer (max 20% each, sum=1)."""
    dates = pd.date_range(start="2020-01-01", periods=300, freq="B")
    n = len(dates)
    t = np.arange(n, dtype=float)
    return pd.DataFrame({
        "AAPL": 100 + t * 0.1 + np.sin(t / 20) * 2,
        "MSFT": 105 + t * 0.12 + np.cos(t / 15) * 1.5,
        "GOOG": 95 + t * 0.08 + np.sin(t / 25) * 2.5,
        "AMZN": 110 + t * 0.09 + np.sin(t / 18) * 1.8,
        "META": 90 + t * 0.11 + np.cos(t / 22) * 2.2,
    }, index=dates)


@pytest.fixture
def temp_db(temp_dir):
    """Create a temporary SQLite DB for DBManager tests."""
    db_path = os.path.join(temp_dir, "test_stock_data.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_history (
            Date TEXT, Symbol TEXT, Open REAL, High REAL, Low REAL, Close REAL, Volume INTEGER,
            PRIMARY KEY (Symbol, Date)
        )
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def mock_config(monkeypatch, temp_dir):
    """Override config paths to use temp directory."""
    data_dir = os.path.join(temp_dir, "data")
    archive_dir = os.path.join(temp_dir, "reports_archive")
    db_path = os.path.join(temp_dir, "stock_data.db")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(archive_dir, exist_ok=True)
    monkeypatch.setattr("config.DATA_DIR", data_dir)
    monkeypatch.setattr("config.ARCHIVE_DIR", archive_dir)
    monkeypatch.setattr("config.DB_PATH", db_path)
    return {"DATA_DIR": data_dir, "ARCHIVE_DIR": archive_dir, "DB_PATH": db_path}


@pytest.fixture
def mock_etf_config(monkeypatch, temp_dir):
    """Override ETF config paths for ETF module tests."""
    etf_root = os.path.join(temp_dir, "etf_data")
    etf_dir = os.path.join(etf_root, "etf")
    sessions_dir = os.path.join(etf_root, "sessions")
    archive_dir = os.path.join(etf_root, "reports_archive")
    db_path = os.path.join(etf_dir, "etf_cache.db")
    os.makedirs(etf_dir, exist_ok=True)
    os.makedirs(sessions_dir, exist_ok=True)
    os.makedirs(archive_dir, exist_ok=True)
    monkeypatch.setattr("config.ETF_STORAGE_ROOT", etf_root)
    monkeypatch.setattr("config.ETF_CACHE_DB", db_path)
    monkeypatch.setattr("config.ETF_SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr("config.ETF_ARCHIVE_DIR", archive_dir)
    return {"ETF_STORAGE_ROOT": etf_root, "ETF_CACHE_DB": db_path, "ETF_SESSIONS_DIR": sessions_dir, "ETF_ARCHIVE_DIR": archive_dir}


@pytest.fixture
def temp_etf_db(mock_etf_config):
    """Provide a temp ETFDB instance using mock_etf_config."""
    from etf_agent.etf_db import ETFDB
    return ETFDB(db_path=mock_etf_config["ETF_CACHE_DB"])

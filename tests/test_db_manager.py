"""Tests for stock_agent.db_manager."""
import os
import sys
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


def test_db_manager_init(temp_db):
    from stock_agent.db_manager import DBManager
    db = DBManager(db_path=temp_db)
    assert db.db_path == temp_db


def test_db_manager_save_and_load(temp_db, sample_prices_df):
    from stock_agent.db_manager import DBManager
    db = DBManager(db_path=temp_db)
    df = sample_prices_df.copy()
    df["Open"] = df["Close"]
    df["High"] = df["Close"]
    df["Low"] = df["Close"]
    df["Volume"] = 1000000
    db.save_history("TEST", df)
    loaded = db.load_history("TEST")
    assert not loaded.empty
    assert "Close" in loaded.columns


def test_db_manager_get_latest_date(temp_db, sample_prices_df):
    from stock_agent.db_manager import DBManager
    db = DBManager(db_path=temp_db)
    df = sample_prices_df.copy()
    df["Open"] = df["Close"]
    df["High"] = df["Close"]
    df["Low"] = df["Close"]
    df["Volume"] = 1000000
    db.save_history("TEST2", df)
    latest = db.get_latest_date("TEST2")
    assert latest is not None


def test_db_manager_empty_df_no_error(temp_db):
    from stock_agent.db_manager import DBManager
    db = DBManager(db_path=temp_db)
    db.save_history("EMPTY", pd.DataFrame())
    latest = db.get_latest_date("EMPTY")
    assert latest is None

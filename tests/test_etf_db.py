"""Tests for etf_agent.etf_db."""
import os
import pandas as pd
import pytest

def test_etf_db_init(temp_etf_db):
    db = temp_etf_db
    assert db.db_path is not None
    assert os.path.isfile(db.db_path)

def test_etf_db_save_and_load_history(temp_etf_db, sample_prices_df):
    db = temp_etf_db
    df = sample_prices_df.copy()
    df['Open'] = df['Close']
    df['High'] = df['Close']
    df['Low'] = df['Close']
    df['Volume'] = 1000
    db.save_history('SPY', df)
    loaded = db.load_history('SPY')
    assert not loaded.empty
    assert 'Close' in loaded.columns

def test_etf_db_load_history_empty(temp_etf_db):
    assert temp_etf_db.load_history('NONEXISTENT').empty

def test_etf_db_get_latest_date_none(temp_etf_db):
    assert temp_etf_db.get_latest_date('NONE') is None

def test_etf_db_save_metadata_and_get(temp_etf_db):
    db = temp_etf_db
    db.save_etf_metadata('SPY', expense_ratio=0.09, aum=400e9, exchange='NYSE', name='SPDR S&P 500')
    meta = db.get_etf_metadata('SPY')
    assert meta is not None
    assert meta['symbol'] == 'SPY'
    assert meta['expense_ratio'] == 0.09

def test_etf_db_get_metadata_missing(temp_etf_db):
    assert temp_etf_db.get_etf_metadata('MISSING') is None

def test_etf_db_list_symbols(temp_etf_db, sample_prices_df):
    db = temp_etf_db
    df = sample_prices_df.copy()
    df['Open'] = df['High'] = df['Low'] = df['Close']
    df['Volume'] = 1000
    db.save_history('A', df)
    db.save_history('B', df)
    syms = db.list_symbols()
    assert 'A' in syms
    assert 'B' in syms

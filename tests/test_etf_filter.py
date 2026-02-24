"""Tests for etf_agent.etf_filter."""
import os
import json
import pandas as pd
import pytest

def test_run_filter_empty_db(mock_etf_config):
    from etf_agent.etf_filter import run_filter
    session_dir = os.path.join(mock_etf_config["ETF_SESSIONS_DIR"], "test-session")
    cand_path, stats_path = run_filter(session_dir, max_expense_ratio=0.005, min_aum=1e9, min_history_years=3.0, nyse_nasdaq_only=True)
    assert os.path.exists(stats_path)
    assert os.path.exists(cand_path)
    with open(stats_path) as f:
        data = json.load(f)
    assert data["Waterfall"]["Scanned"] == 0
    assert data["Waterfall"]["Passed"] == 0
    if os.path.getsize(cand_path) > 10:
        assert len(pd.read_csv(cand_path)) == 0

def test_run_filter_one_candidate(mock_etf_config, temp_etf_db, sample_prices_df):
    db = temp_etf_db
    df = sample_prices_df.copy()
    df["Open"] = df["High"] = df["Low"] = df["Close"]
    df["Volume"] = 1000
    db.save_history("SPY", df)
    db.save_etf_metadata("SPY", expense_ratio=0.0009, aum=400e9, exchange="NYSE", name="SPDR S&P 500")
    from etf_agent.etf_filter import run_filter
    session_dir = os.path.join(mock_etf_config["ETF_SESSIONS_DIR"], "test-session-2")
    cand_path, stats_path = run_filter(session_dir, max_expense_ratio=0.01, min_aum=1e8, min_history_years=0.5, nyse_nasdaq_only=False)
    assert os.path.exists(cand_path)
    assert os.path.getsize(cand_path) > 10
    cand_df = pd.read_csv(cand_path)
    assert len(cand_df) >= 1
    assert "SPY" in cand_df["symbol"].values
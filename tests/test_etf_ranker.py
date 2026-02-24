"""Tests for etf_engine.etf_sharpe_ranker."""
import os
import pandas as pd
import pytest

def test_run_ranker_missing_file(mock_etf_config):
    from etf_engine.etf_sharpe_ranker import run_ranker
    session_dir = os.path.join(mock_etf_config["ETF_SESSIONS_DIR"], "rank")
    result = run_ranker(session_dir, os.path.join(session_dir, "nonexistent.csv"))
    assert result is None

def test_run_ranker_empty_candidates(mock_etf_config):
    from etf_engine.etf_sharpe_ranker import run_ranker
    session_dir = os.path.join(mock_etf_config["ETF_SESSIONS_DIR"], "rank2")
    os.makedirs(session_dir, exist_ok=True)
    cand_path = os.path.join(session_dir, "candidates.csv")
    pd.DataFrame(columns=["symbol", "name"]).to_csv(cand_path, index=False)
    result = run_ranker(session_dir, cand_path)
    assert result is None

def test_run_ranker_with_data(mock_etf_config, temp_etf_db, sample_prices_df):
    db = temp_etf_db
    df = sample_prices_df.copy()
    df["Open"] = df["High"] = df["Low"] = df["Close"]
    df["Volume"] = 1000
    db.save_history("SPY", df)
    db.save_history("VOO", df)
    session_dir = os.path.join(mock_etf_config["ETF_SESSIONS_DIR"], "rank3")
    os.makedirs(session_dir, exist_ok=True)
    cand_path = os.path.join(session_dir, "candidates.csv")
    pd.DataFrame({"symbol": ["SPY", "VOO"], "name": ["SPDR", "Vanguard"]}).to_csv(cand_path, index=False)
    from etf_engine.etf_sharpe_ranker import run_ranker
    result = run_ranker(session_dir, cand_path, risk_free_rate=0.05, top_n=50)
    assert result is not None
    assert os.path.exists(result)
    out_df = pd.read_csv(result)
    assert not out_df.empty
    assert "Symbol" in out_df.columns
    assert "Sharpe Ratio" in out_df.columns
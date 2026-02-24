"""Tests for etf_agent.etf_data_fetcher."""
import os
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

def test_fetch_etf_metadata_mock():
    from etf_agent.etf_data_fetcher import fetch_etf_metadata
    with patch("etf_agent.etf_data_fetcher.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = {"annualReportExpenseRatio": 0.001, "totalAssets": 400e9, "exchange": "NYSE", "shortName": "SPDR S&P 500"}
        mock_yf.Ticker.return_value = mock_ticker
        result = fetch_etf_metadata("SPY")
    assert result["expense_ratio"] == 0.001
    assert result["aum"] == 400e9
    assert result["exchange"] == "NYSE"

def test_fetch_etf_metadata_exception():
    from etf_agent.etf_data_fetcher import fetch_etf_metadata
    with patch("etf_agent.etf_data_fetcher.yf") as mock_yf:
        mock_yf.Ticker.side_effect = Exception("network error")
        result = fetch_etf_metadata("SPY")
    assert result["expense_ratio"] is None
    assert result["aum"] is None
    assert result["name"] == "SPY"

def test_run_fetcher_missing_universe(mock_etf_config):
    from etf_agent.etf_data_fetcher import run_fetcher
    result = run_fetcher(universe_path=os.path.join(mock_etf_config["ETF_STORAGE_ROOT"], "etf", "nonexistent.csv"))
    assert result == []

def test_run_fetcher_with_csv(mock_etf_config):
    from etf_agent.etf_data_fetcher import run_fetcher
    etf_dir = os.path.join(mock_etf_config["ETF_STORAGE_ROOT"], "etf")
    os.makedirs(etf_dir, exist_ok=True)
    universe_path = os.path.join(etf_dir, "etf_universe.csv")
    pd.DataFrame({"symbol": ["SPY", "VOO"], "name": ["SPDR", "Vanguard"]}).to_csv(universe_path, index=False)
    with patch("etf_agent.etf_data_fetcher.yf") as mock_yf:
        mock_yf.download.return_value = pd.DataFrame()
        result = run_fetcher(universe_path=universe_path)
    assert isinstance(result, list)
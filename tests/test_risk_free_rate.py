"""Tests for financial_engine.risk_free_rate."""
from unittest.mock import patch
import pandas as pd


def test_get_risk_free_rate_success():
    with patch("financial_engine.risk_free_rate.yf") as mock_yf:
        mock_ticker = mock_yf.Ticker.return_value
        mock_ticker.history.return_value = pd.DataFrame({"Close": [4.5]})
        from financial_engine.risk_free_rate import get_risk_free_rate
        rate = get_risk_free_rate()
        assert rate == 0.045


def test_get_risk_free_rate_empty_default():
    with patch("financial_engine.risk_free_rate.yf") as mock_yf:
        mock_ticker = mock_yf.Ticker.return_value
        mock_ticker.history.return_value = pd.DataFrame()
        from financial_engine.risk_free_rate import get_risk_free_rate
        rate = get_risk_free_rate()
        assert rate == 0.04


def test_get_risk_free_rate_exception_default():
    with patch("financial_engine.risk_free_rate.yf") as mock_yf:
        mock_yf.Ticker.side_effect = Exception("network error")
        from financial_engine.risk_free_rate import get_risk_free_rate
        rate = get_risk_free_rate()
        assert rate == 0.04

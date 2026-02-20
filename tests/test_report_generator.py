"""Tests for report_generator.create_report."""
import os
import pandas as pd
import sys
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from report_generator.create_report import load_portfolio, format_metrics_table, get_waterfall_section


def test_load_portfolio_missing_file(temp_dir):
    result = load_portfolio(os.path.join(temp_dir, "nonexistent.csv"))
    assert result is None


def test_load_portfolio_success(temp_dir):
    path = os.path.join(temp_dir, "portfolio.csv")
    pd.DataFrame({"Symbol": ["AAPL", "MSFT"], "Weight": [0.5, 0.5]}).to_csv(path, index=False)
    result = load_portfolio(path)
    assert result is not None
    assert abs(result["AAPL"] - 0.5) < 0.01


def test_format_metrics_table_empty():
    result = format_metrics_table({})
    assert "Insufficient" in result


def test_format_metrics_table_with_data():
    m = {2023: {"Return": 0.1, "Volatility": 0.15, "Sharpe": 0.5, "Alpha": 0.02, "Beta": 1.0}}
    result = format_metrics_table(m)
    assert "2023" in result


def test_get_waterfall_section():
    result = get_waterfall_section()
    assert "Stock Selection Waterfall" in result

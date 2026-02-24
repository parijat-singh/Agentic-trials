"""Tests for report_generator.etf_report."""
import os
import json
import pandas as pd
import pytest

def test_generate_etf_report_minimal(mock_etf_config):
    from report_generator.etf_report import generate_etf_report
    session_dir = os.path.join(mock_etf_config["ETF_SESSIONS_DIR"], "report-session")
    os.makedirs(session_dir, exist_ok=True)
    report_path = generate_etf_report(session_dir)
    assert report_path is not None
    assert os.path.exists(report_path)
    with open(report_path) as f:
        content = f.read()
    assert "ETF" in content

def test_generate_etf_report_with_stats_and_top(mock_etf_config):
    session_dir = os.path.join(mock_etf_config["ETF_SESSIONS_DIR"], "report-full")
    os.makedirs(session_dir, exist_ok=True)
    with open(os.path.join(session_dir, "etf_stats.json"), "w") as f:
        json.dump({"Waterfall": {"Scanned": 100, "Expense": 5, "AUM": 10, "History": 2, "Exchange": 30, "Passed": 53}}, f)
    pd.DataFrame({"Symbol": ["SPY", "VOO"], "Sharpe Ratio": [1.2, 1.1], "Annualized Return": [0.10, 0.09], "Annualized Volatility": [0.15, 0.14]}).to_csv(os.path.join(session_dir, "etf_top_50.csv"), index=False)
    from report_generator.etf_report import generate_etf_report
    report_path = generate_etf_report(session_dir)
    assert os.path.exists(report_path)
    with open(report_path) as f:
        content = f.read()
    assert "53" in content or "Passed" in content
    assert "SPY" in content
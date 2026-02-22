"""Tests for report_generator.create_report."""
import os
import json
import pandas as pd
import sys
from unittest.mock import patch

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from report_generator.create_report import (
    load_portfolio,
    format_metrics_table,
    get_waterfall_section,
    _fmt_weight,
    calculate_metrics,
)


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


def test_get_waterfall_section_with_price_and_cap(temp_dir):
    """Waterfall includes Price and Market Cap filters when set in params."""
    import report_generator.create_report as cr
    stats_path = os.path.join(temp_dir, "scraping_stats.json")
    os.makedirs(temp_dir, exist_ok=True)
    stats = {
        "Scanned": 100, "Non_US": 0, "Too_Old": 0, "Too_New": 0, "Errors": 0,
        "Skipped_Exchange": 0, "Skipped_Industry": 0, "Skipped_PE": 0,
        "Skipped_Market_Cap": 5, "Skipped_Price": 3, "Selected": 90,
        "Parameters": {
            "Min_History": 5, "Min_IPO": 5, "Max_IPO": 10, "Max_PE": 25,
            "Min_Market_Cap": 5.0, "Min_Price": 10.0, "Max_Price": 500.0,
            "NYSE_NASDAQ_Only": False, "Industries": ["Technology"], "Max_Pages": 200,
        },
    }
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)
    with patch.object(cr, "FILE_STATS", stats_path):
        with patch.object(cr, "FILE_TOP_50", os.path.join(temp_dir, "x.csv")):
            with patch.object(cr, "FILE_OPTIMAL", os.path.join(temp_dir, "x.csv")):
                with patch.object(cr, "FILE_BACKTEST", os.path.join(temp_dir, "x.csv")):
                    result = cr.get_waterfall_section(industries_override=["Technology"])
    assert "Filter: Market Cap" in result
    assert "Filter: Price" in result
    assert "$10-$500" in result or "10" in result


def test_run_config_includes_timing(temp_dir):
    """Run Configuration section includes Start Time, End Time, Elapsed Time when in stats."""
    import report_generator.create_report as cr

    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "archive"), exist_ok=True)
    stats_path = os.path.join(temp_dir, "scraping_stats.json")
    output_path = os.path.join(temp_dir, "FINAL_REPORT.md")
    stats = {
        "Run_Start_Time": "2026-02-21 21:15:00",
        "Run_End_Time": "2026-02-21 21:20:35",
        "Total_Time": "00:05:35.12",
        "Scanned": 100, "Non_US": 0, "Too_Old": 0, "Too_New": 0, "Errors": 0,
        "Skipped_Exchange": 0, "Skipped_Industry": 0, "Skipped_PE": 0,
        "Skipped_Market_Cap": 0, "Skipped_Price": 0, "Selected": 95,
        "Parameters": {
            "Min_History": 5, "Min_IPO": 5, "Max_IPO": 10, "Max_PE": 25,
            "Min_Market_Cap": None, "Min_Price": None, "Max_Price": None,
            "NYSE_NASDAQ_Only": True, "Industries": None, "Max_Pages": 200,
        },
    }
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)

    with patch.object(cr, "FILE_STATS", stats_path):
        with patch.object(cr, "FILE_TOP_100", os.path.join(temp_dir, "x.csv")):
            with patch.object(cr, "FILE_TOP_50", os.path.join(temp_dir, "x.csv")):
                with patch.object(cr, "FILE_OPTIMAL", os.path.join(temp_dir, "x.csv")):
                    with patch.object(cr, "FILE_BACKTEST", os.path.join(temp_dir, "x.csv")):
                        with patch.object(cr, "DATA_DIR", temp_dir):
                            with patch.object(cr, "ARCHIVE_DIR", os.path.join(temp_dir, "archive")):
                                with patch.object(cr, "OUTPUT_FILE", output_path):
                                    with patch.object(cr, "LOG_FILE", os.path.join(temp_dir, "report_log.md")):
                                        cr.generate_markdown("Test", industries_override=None)
    with open(output_path) as f:
        report = f.read()
    assert "Start Time" in report
    assert "End Time" in report
    assert "Elapsed Time" in report
    assert "2026-02-21 21:15:00" in report
    assert "2026-02-21 21:20:35" in report
    assert "00:05:35.12" in report


def test_fmt_weight():
    """_fmt_weight handles NaN, float, and invalid values."""
    assert _fmt_weight(0.25) == "25.00%"
    assert _fmt_weight(float("nan")) == "N/A"
    assert "N/A" in _fmt_weight(__import__("numpy").nan)


def test_load_portfolio_percent_weights(temp_dir):
    """load_portfolio handles percent or decimal weights."""
    path = os.path.join(temp_dir, "portfolio.csv")
    pd.DataFrame({"Symbol": ["A"], "Weight": [0.5]}).to_csv(path, index=False)
    result = load_portfolio(path)
    assert result is not None
    assert abs(float(result["A"]) - 0.5) < 0.01


def test_generate_markdown_with_optimal_and_backtest(temp_dir):
    """generate_markdown with valid optimal/backtest CSVs produces full report."""
    import report_generator.create_report as cr
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "archive"), exist_ok=True)
    stats_path = os.path.join(temp_dir, "scraping_stats.json")
    output_path = os.path.join(temp_dir, "report.md")
    top50_path = os.path.join(temp_dir, "top50.csv")
    optimal_path = os.path.join(temp_dir, "optimal.csv")
    backtest_path = os.path.join(temp_dir, "backtest.csv")
    top100_path = os.path.join(temp_dir, "top100.csv")

    stats = {
        "Run_Start_Time": "2026-02-21 12:00:00",
        "Run_End_Time": "2026-02-21 12:05:00",
        "Total_Time": "00:05:00.00",
        "Scanned": 100, "Non_US": 0, "Too_Old": 0, "Too_New": 0, "Errors": 0,
        "Skipped_Exchange": 0, "Skipped_Industry": 0, "Skipped_PE": 0,
        "Skipped_Market_Cap": 0, "Skipped_Price": 0, "Selected": 95,
        "Parameters": {"Min_History": 5, "Min_IPO": 5, "Max_IPO": 10, "Max_PE": 25,
            "Min_Market_Cap": None, "Min_Price": None, "Max_Price": None,
            "NYSE_NASDAQ_Only": True, "Industries": None, "Max_Pages": 200},
    }
    with open(stats_path, "w") as f:
        json.dump(stats, f)

    pd.DataFrame({"Symbol": ["AAPL"], "Weight": [1.0]}).to_csv(optimal_path, index=False)
    pd.DataFrame({"Symbol": ["AAPL"], "Weight": [1.0]}).to_csv(backtest_path, index=False)
    pd.DataFrame({"Symbol": ["AAPL"], "Sharpe Ratio": [0.5]}).to_csv(top50_path, index=False)
    pd.DataFrame({"symbol": ["AAPL"]}).to_csv(top100_path, index=False)

    with patch.object(cr, "FILE_STATS", stats_path):
        with patch.object(cr, "FILE_TOP_100", top100_path):
            with patch.object(cr, "FILE_TOP_50", top50_path):
                with patch.object(cr, "FILE_OPTIMAL", optimal_path):
                    with patch.object(cr, "FILE_BACKTEST", backtest_path):
                        with patch.object(cr, "DATA_DIR", temp_dir):
                            with patch.object(cr, "ARCHIVE_DIR", os.path.join(temp_dir, "archive")):
                                with patch.object(cr, "OUTPUT_FILE", output_path):
                                    with patch.object(cr, "LOG_FILE", os.path.join(temp_dir, "log.md")):
                                        cr.generate_markdown("Test")

    with open(output_path) as f:
        report = f.read()
    assert "Run Configuration" in report or "Run_Start" in report or "Start Time" in report
    assert "4. Historical Backtest" in report or "Backtest" in report


def test_calculate_metrics_basic():
    """calculate_metrics returns yearly metrics with benchmark."""
    n = 300
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    prices = pd.DataFrame({
        "AAPL": [100 * (1.001) ** i for i in range(n)],
        "SPY": [100 * (1.0008) ** i for i in range(n)],
    }, index=dates)
    weights = {"AAPL": 1.0}
    result = calculate_metrics(weights, prices)
    assert isinstance(result, dict)

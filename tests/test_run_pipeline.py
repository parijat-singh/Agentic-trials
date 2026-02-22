"""Tests for run_pipeline timing and stats."""
import os
import json
import sys
from unittest.mock import patch

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)


def test_get_user_input_returns_default():
    from run_pipeline import get_user_input
    with patch("builtins.input", return_value=""):
        assert get_user_input("test", 42, int) == 42


def test_run_script_missing_file():
    from run_pipeline import run_script
    result = run_script(os.path.join(os.path.dirname(__file__), "nonexistent_script_xyz.py"), "test")
    assert result is False


def test_run_pipeline_saves_timing_stats_to_scraping_stats(mock_config):
    """run_pipeline saves Run_Start_Time, Run_End_Time, Total_Time to scraping_stats.json before report."""
    import run_pipeline
    data_dir = mock_config["DATA_DIR"]
    stats_path = os.path.join(data_dir, "scraping_stats.json")
    os.makedirs(data_dir, exist_ok=True)

    # Create minimal top_100 so industry filter and downstream don't fail
    csv_path = os.path.join(data_dir, "top_100_new_stocks.csv")
    import pandas as pd
    pd.DataFrame({"symbol": ["AAPL"], "sector": ["Technology"]}).to_csv(csv_path, index=False)

    orig_argv = sys.argv
    try:
        sys.argv = ["run_pipeline.py", "--skip-scraper", "--industries=Technology"]
        with patch.object(run_pipeline, "run_script", return_value=True):
            run_pipeline.main()
    finally:
        sys.argv = orig_argv

    assert os.path.exists(stats_path)
    with open(stats_path) as f:
        stats = json.load(f)
    assert "Run_Start_Time" in stats
    assert "Run_End_Time" in stats
    assert "Total_Time" in stats
    assert stats["Run_Start_Time"] != "N/A"
    assert stats["Run_End_Time"] != "N/A"


def test_run_pipeline_passes_min_price_industries_to_stats(mock_config):
    """run_pipeline saves min_price and industries in Parameters."""
    import run_pipeline
    data_dir = mock_config["DATA_DIR"]
    stats_path = os.path.join(data_dir, "scraping_stats.json")
    os.makedirs(data_dir, exist_ok=True)
    import pandas as pd
    pd.DataFrame({"symbol": ["AAPL"], "sector": ["Technology"]}).to_csv(
        os.path.join(data_dir, "top_100_new_stocks.csv"), index=False
    )

    orig_argv = sys.argv
    try:
        sys.argv = ["run_pipeline.py", "--skip-scraper", "--min-price=10", "--industries=Technology,Energy"]
        with patch.object(run_pipeline, "run_script", return_value=True):
            run_pipeline.main()
    finally:
        sys.argv = orig_argv

    with open(stats_path) as f:
        stats = json.load(f)
    params = stats.get("Parameters", {})
    assert params.get("Min_Price") == 10
    assert params.get("Industries") == ["Technology", "Energy"]

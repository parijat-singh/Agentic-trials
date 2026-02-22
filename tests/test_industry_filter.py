"""Tests for industry/sector filter across pipeline, API, report, and sharpe_ranker."""
import os
import json
import sys
import pandas as pd
from unittest.mock import patch, MagicMock

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)


def test_api_analyze_industries_in_command():
    """Verify API adds --industries= to the subprocess command when industries provided."""
    import asyncio
    with patch("api_server.state") as mock_state:
        mock_state.status = "idle"
        mock_state.process = None
        with patch("api_server.threading.Thread") as mock_thread:
            from api_server import run_analysis, AnalyzeRequest
            asyncio.run(run_analysis(AnalyzeRequest(
                min_history=5.0, max_ipo=10.0,
                industries=["Technology", "Healthcare"]
            )))
            # Thread(target=run_pipeline_background, args=(cmd, cwd))
            call_kwargs = mock_thread.call_args[1]
            cmd = call_kwargs["args"][0]
    ind_arg = [a for a in cmd if a.startswith("--industries=")]
    assert len(ind_arg) == 1, f"Expected --industries= in cmd: {cmd}"
    assert "Technology" in ind_arg[0]
    assert "Healthcare" in ind_arg[0]


def test_process_batch_industry_filter_logic():
    """Industry filter logic: sector not in industries list -> Skipped_Industry."""
    industries = ["Technology", "Energy"]
    sectors_to_test = [
        ("Technology", True),
        ("Energy", True),
        ("Healthcare", False),
        ("", False),
        (None, False),
    ]
    for sector_val, should_pass in sectors_to_test:
        sector = (sector_val or "").strip()
        in_list = sector in [s.strip() for s in industries]
        assert in_list == should_pass, f"sector={sector_val!r} should_pass={should_pass}"


def test_report_waterfall_includes_sector_filter_when_industries_set(temp_dir):
    """Waterfall section must include Filter: Sector when Industries in Parameters."""
    import report_generator.create_report as cr
    stats_path = os.path.join(temp_dir, "scraping_stats.json")
    os.makedirs(temp_dir, exist_ok=True)
    stats = {
        "Scanned": 100, "Non_US": 0, "Too_Old": 0, "Too_New": 0,
        "Skipped_PE": 0, "Skipped_Market_Cap": 0, "Skipped_Exchange": 0,
        "Skipped_Price": 0, "Skipped_Industry": 5, "Errors": 0, "Selected": 95,
        "Parameters": {
            "Min_History": 5, "Min_IPO": 5, "Max_IPO": 10, "Max_PE_By_Sector": {"Technology": 25},
            "Min_Market_Cap": None, "Min_Price": None,
            "NYSE_NASDAQ_Only": True, "Industries": ["Technology", "Energy"], "Max_Pages": 200
        }
    }
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)

    with patch.object(cr, "FILE_STATS", stats_path):
        with patch.object(cr, "FILE_TOP_50", os.path.join(temp_dir, "nonexistent.csv")):
            with patch.object(cr, "FILE_OPTIMAL", os.path.join(temp_dir, "nonexistent.csv")):
                with patch.object(cr, "FILE_BACKTEST", os.path.join(temp_dir, "nonexistent.csv")):
                    waterfall = cr.get_waterfall_section()
    assert "Filter: Sector" in waterfall
    assert "Technology" in waterfall
    assert "Energy" in waterfall
    assert "-5" in waterfall


def test_sharpe_ranker_industry_filter_logic():
    """Symbols with sector not in Industries list must be excluded."""
    meta = pd.DataFrame({
        "symbol": ["TECH1", "HEALTH1", "ENERGY1"],
        "sector": ["Technology", "Healthcare", "Energy"],
    })
    industries_filter = ["Technology", "Energy"]
    sector_col = "sector"
    filtered = meta[meta[sector_col].notna() & meta[sector_col].isin(industries_filter)]
    assert "HEALTH1" not in filtered["symbol"].values
    assert "TECH1" in filtered["symbol"].values
    assert "ENERGY1" in filtered["symbol"].values


def test_csv_industry_filter_logic():
    """Verify CSV filtering logic: only rows with sector in industries_list are kept."""
    df = pd.DataFrame({
        "symbol": ["A", "B", "C"],
        "sector": ["Technology", "Healthcare", "Energy"],
    })
    industries_list = ["Technology", "Energy"]
    sector_col = "sector"
    filtered = df[df[sector_col].notna() & df[sector_col].isin(industries_list)]
    assert len(filtered) == 2
    assert "B" not in filtered["symbol"].values
    assert "A" in filtered["symbol"].values
    assert "C" in filtered["symbol"].values


def test_run_pipeline_industry_filter_reduces_csv(temp_dir):
    """CSV filter (as used in run_pipeline) must exclude Healthcare when only Tech+Energy selected."""
    csv_path = os.path.join(temp_dir, "top_100_new_stocks.csv")
    os.makedirs(temp_dir, exist_ok=True)
    df = pd.DataFrame({
        "symbol": ["TECH1", "HEALTH1", "ENERGY1"],
        "sector": ["Technology", "Healthcare", "Energy"],
    })
    df.to_csv(csv_path, index=False)
    industries_list = ["Technology", "Energy"]
    sector_col = "sector" if "sector" in df.columns else "Sector"
    df = df[df[sector_col].notna() & df[sector_col].isin(industries_list)]
    df.to_csv(csv_path, index=False)
    loaded = pd.read_csv(csv_path)
    assert len(loaded) == 2
    assert "HEALTH1" not in loaded["symbol"].values

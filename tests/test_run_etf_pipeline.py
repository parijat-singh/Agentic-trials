"""Tests for run_etf_pipeline (orchestration)."""
import os
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

def test_main_skip_scraper_and_fetcher(mock_etf_config, temp_etf_db, sample_prices_df):
    """Run pipeline with skip-scraper and skip-fetcher; mock filter/ranker/optimizer/report."""
    from run_etf_pipeline import main
    session_dir = os.path.join(mock_etf_config["ETF_SESSIONS_DIR"], "pipetest")
    os.makedirs(session_dir, exist_ok=True)
    cand_path = os.path.join(session_dir, "etf_candidates.csv")
    pd.DataFrame({"symbol": ["SPY", "VOO"], "name": ["SPDR", "Vanguard"]}).to_csv(cand_path, index=False)
    top_path = os.path.join(session_dir, "etf_top_50.csv")
    pd.DataFrame({"Symbol": ["SPY", "VOO"], "Sharpe Ratio": [1.0, 0.9], "Annualized Return": [0.1, 0.09], "Annualized Volatility": [0.15, 0.14]}).to_csv(top_path, index=False)
    db = temp_etf_db
    df = sample_prices_df.copy()
    df["Open"] = df["High"] = df["Low"] = df["Close"]
    df["Volume"] = 1000
    for s in ["SPY", "VOO"]:
        db.save_history(s, df)
    with patch("run_etf_pipeline.run_scraper"), patch("run_etf_pipeline.run_fetcher"), patch("run_etf_pipeline.run_filter", return_value=(cand_path, None)), patch("run_etf_pipeline.run_ranker", return_value=top_path), patch("run_etf_pipeline.optimize_portfolio") as mock_opt, patch("run_etf_pipeline.generate_etf_report") as mock_report:
        mock_opt.return_value = pd.DataFrame({"Symbol": ["SPY", "VOO"], "Weight": [0.5, 0.5], "Return Contrib": [0.05, 0.05], "Risk Contrib": [0.5, 0.5], "Correlation": [0.9, 0.9]})
        mock_report.return_value = os.path.join(session_dir, "ETF_REPORT.md")
        with patch("sys.argv", ["run_etf_pipeline.py", "--skip-scraper", "--skip-fetcher", "--session-id=pipetest", "--max-pages=1"]):
            rc = main()
    assert rc == 0
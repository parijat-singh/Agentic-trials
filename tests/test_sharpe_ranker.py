"""Tests for financial_engine.sharpe_ranker."""
import os
import pandas as pd
from financial_engine.sharpe_ranker import calculate_sharpe_ratio, rank_stocks


def test_basic_sharpe(sample_prices_df):
    sharpe, ann_ret, ann_vol = calculate_sharpe_ratio(sample_prices_df, 0.04)
    assert sharpe is not None
    assert ann_ret is not None
    assert ann_vol >= 0


def test_empty_df_returns_none():
    df = pd.DataFrame()
    assert calculate_sharpe_ratio(df, 0.04) == (None, None, None)


def test_insufficient_history():
    df = pd.DataFrame({"Close": [100, 101]})
    df.index = pd.date_range("2024-01-01", periods=2, freq="D")
    assert calculate_sharpe_ratio(df, 0.04) == (None, None, None)


def test_zero_volatility():
    dates = pd.date_range(start="2023-01-01", periods=100)
    df = pd.DataFrame({"Close": [100.0] * 100}, index=dates)
    sharpe, _, ann_vol = calculate_sharpe_ratio(df, 0.04)
    assert sharpe == 0.0
    assert ann_vol == 0.0


def test_rank_stocks_empty_dir(temp_dir):
    """rank_stocks with no CSVs returns empty or minimal result."""
    result = rank_stocks(temp_dir, 0.04)
    assert result is not None
    assert hasattr(result, "empty")


def test_rank_stocks_with_meta_no_db(temp_dir):
    """rank_stocks with meta file but no DB returns DataFrame (possibly empty)."""
    os.makedirs(temp_dir, exist_ok=True)
    meta = pd.DataFrame({"symbol": ["AAPL"], "sector": ["Technology"]})
    meta.to_csv(os.path.join(temp_dir, "top_100_new_stocks.csv"), index=False)
    with open(os.path.join(temp_dir, "scraping_stats.json"), "w") as f:
        import json
        json.dump({"Parameters": {}}, f)

    result = rank_stocks(temp_dir, 0.04)
    assert result is not None
    assert hasattr(result, "empty")

"""Tests for financial_engine.sharpe_ranker."""
import pandas as pd
from financial_engine.sharpe_ranker import calculate_sharpe_ratio


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

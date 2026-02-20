"""Tests for backtester.backtest_engine."""
import pandas as pd
import numpy as np
import pytest

from backtester.backtest_engine import filter_consecutive_growth, optimize_total_return


def _make_3y_prices(positive_y1=True, positive_y2=True, positive_y3=True):
    """Create ~3 years of daily prices with controlled yearly returns."""
    dates = pd.date_range(start="2021-01-01", periods=756, freq="B")
    n = len(dates)
    # Simple growth model
    r1 = 0.1 if positive_y1 else -0.1
    r2 = 0.05 if positive_y2 else -0.05
    r3 = 0.08 if positive_y3 else -0.08
    # 252 trading days per year
    vals = []
    price = 100.0
    for i in range(n):
        if i < 252:
            daily = (1 + r1) ** (1 / 252) - 1
        elif i < 504:
            daily = (1 + r2) ** (1 / 252) - 1
        else:
            daily = (1 + r3) ** (1 / 252) - 1
        price *= 1 + daily
        vals.append(price)
    return pd.DataFrame({"A": vals, "B": [v * 1.01 for v in vals]}, index=dates)


class TestFilterConsecutiveGrowth:
    def test_all_positive(self):
        prices = _make_3y_prices(True, True, True)
        result = filter_consecutive_growth(prices)
        assert result is not None
        if hasattr(result, "empty"):
            assert not result.empty
            assert "A" in result.columns

    def test_one_negative_relaxes(self):
        prices = _make_3y_prices(True, False, True)
        result = filter_consecutive_growth(prices)
        assert result is not None


class TestOptimizeTotalReturn:
    def test_optimize_returns_weights(self):
        # Needs 5+ stocks: backtester uses max 20% per stock, sum must equal 1
        dates = pd.date_range(start="2020-01-01", periods=300, freq="B")
        n = len(dates)
        prices = pd.DataFrame({
            "A": 100 * (1.001) ** np.arange(n),
            "B": 101 * (1.002) ** np.arange(n),
            "C": 102 * (1.0008) ** np.arange(n),
            "D": 103 * (1.0012) ** np.arange(n),
            "E": 104 * (1.0009) ** np.arange(n),
        }, index=dates)
        result = optimize_total_return(prices)
        assert result is not None, "optimize_total_return failed (check constraints)"
        weights, max_ret = result
        assert weights is not None
        assert max_ret is not None
        np.testing.assert_almost_equal(sum(weights), 1.0)

    def test_empty_df_returns_none(self):
        result = optimize_total_return(pd.DataFrame())
        assert result is None

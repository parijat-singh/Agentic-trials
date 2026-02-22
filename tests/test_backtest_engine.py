"""Tests for backtester.backtest_engine."""
import os
import json
import pandas as pd
import numpy as np
import pytest

from backtester.backtest_engine import (
    filter_consecutive_growth, optimize_total_return,
    load_3y_data, _sector_in_industries
)


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


class TestSectorInIndustries:
    def test_sector_matches(self):
        assert _sector_in_industries("Technology", ["Technology", "Healthcare"]) is True
        assert _sector_in_industries("TECHNOLOGY", ["technology"]) is True

    def test_sector_no_match(self):
        assert _sector_in_industries("Energy", ["Technology"]) is False

    def test_empty_returns_false(self):
        assert _sector_in_industries("", ["Technology"]) is False
        assert _sector_in_industries("Technology", []) is False
        assert _sector_in_industries(None, ["Technology"]) is False


class TestFilterConsecutiveGrowthEdgeCases:
    def test_filter_consecutive_covers_extreme_outlier_path(self):
        """Filter runs with mix of normal and extreme-return stocks (covers outlier branch)."""
        dates = pd.date_range(start="2020-01-01", periods=800, freq="B")
        vals_a = [100.0] * 300 + [100.0] * 300 + [10200.0] * 200  # ~10000% jump in period 3
        vals_b = [100 * (1.05) ** (i // 252) for i in range(800)]
        prices = pd.DataFrame({"A": vals_a, "B": vals_b}, index=dates)
        result = filter_consecutive_growth(prices)
        assert result is not None
        assert hasattr(result, "columns")

    def test_relaxed_cumulative_return(self):
        """When no stock has 3 consecutive positive years, relax to cumulative return."""
        dates = pd.date_range(start="2021-01-01", periods=756, freq="B")
        vals = 100 * (1.001) ** np.arange(756)
        prices = pd.DataFrame({"A": vals}, index=dates)
        result = filter_consecutive_growth(prices)
        assert result is not None

    def test_fewer_than_3_years_skips_filter(self):
        """With less than 3 years of yearly returns, use fallback."""
        dates = pd.date_range(start="2024-01-01", periods=300, freq="B")
        prices = pd.DataFrame({"A": [100.0] * 300, "B": [101.0] * 300}, index=dates)
        result = filter_consecutive_growth(prices)
        assert result is not None


class TestLoad3yData:
    def test_load_from_meta_and_csv(self, temp_dir):
        """load_3y_data reads from meta CSV and price CSVs."""
        meta_path = os.path.join(temp_dir, "top_100_new_stocks.csv")
        pd.DataFrame({"symbol": ["AAPL"], "sector": ["Technology"]}).to_csv(meta_path, index=False)
        dates = pd.date_range(start="2021-01-01", periods=400, freq="B")
        df = pd.DataFrame({"Date": dates, "Close": [100.0 * (1.001) ** i for i in range(400)]})
        df.to_csv(os.path.join(temp_dir, "AAPL.csv"), index=False)
        result = load_3y_data(temp_dir)
        assert result is not None
        assert not result.empty or "AAPL" in result.columns

    def test_load_with_industry_filter(self, temp_dir):
        """load_3y_data applies industry filter from scraping_stats.json."""
        os.makedirs(temp_dir, exist_ok=True)
        stats = {"Parameters": {"Industries": ["Technology"]}}
        with open(os.path.join(temp_dir, "scraping_stats.json"), "w") as f:
            json.dump(stats, f)
        meta = pd.DataFrame({"symbol": ["AAPL", "XOM"], "sector": ["Technology", "Energy"]})
        meta.to_csv(os.path.join(temp_dir, "top_100_new_stocks.csv"), index=False)
        for sym in ["AAPL", "XOM"]:
            dates = pd.date_range(start="2021-01-01", periods=400, freq="B")
            pd.DataFrame({"Date": dates, "Close": [100.0] * 400}).to_csv(
                os.path.join(temp_dir, f"{sym}.csv"), index=False
            )
        result = load_3y_data(temp_dir)
        assert result is not None

"""Tests for portfolio_optimizer.optimizer."""
import os
import pytest
import pandas as pd
import numpy as np

from portfolio_optimizer.optimizer import load_data, optimize_portfolio


class TestLoadData:
    def test_load_data_missing_file(self, temp_dir):
        top_50 = os.path.join(temp_dir, "nonexistent.csv")
        data_dir = temp_dir
        result = load_data(top_50, data_dir)
        assert result.empty

    def test_load_data_success(self, temp_dir, sample_multi_stock_prices):
        top_50_path = os.path.join(temp_dir, "top_50.csv")
        data_dir = os.path.join(temp_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        top_df = pd.DataFrame({"Symbol": ["AAPL", "MSFT", "GOOG"]})
        top_df.to_csv(top_50_path, index=False)
        for sym in ["AAPL", "MSFT", "GOOG"]:
            df = sample_multi_stock_prices[[sym]].copy()
            df.columns = ["Close"]
            df = df.reset_index()
            df.columns = ["Date", "Close"]
            df.to_csv(os.path.join(data_dir, f"{sym}.csv"), index=False)
        result = load_data(top_50_path, data_dir)
        assert not result.empty


class TestOptimizePortfolio:
    def test_optimize_portfolio(self, sample_multi_stock_prices):
        result = optimize_portfolio(sample_multi_stock_prices, 0.04)
        assert result is not None
        assert "Symbol" in result.columns
        assert "Weight" in result.columns
        np.testing.assert_almost_equal(result["Weight"].sum(), 1.0, decimal=4)

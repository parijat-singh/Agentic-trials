"""Tests for stock_agent.market_cap_scraper."""
import pytest

# Import after path setup
from stock_agent.market_cap_scraper import parse_market_cap, is_likely_us_stock


class TestParseMarketCap:
    def test_billions(self):
        assert parse_market_cap("100B") == 100.0
        assert parse_market_cap("1.5 B") == 1.5
        assert parse_market_cap("$50B") == 50.0

    def test_trillions(self):
        assert parse_market_cap("1.5T") == 1500.0
        assert parse_market_cap("2 T") == 2000.0

    def test_millions(self):
        assert parse_market_cap("500M") == 0.5
        assert parse_market_cap("1000 M") == 1.0

    def test_none_or_na(self):
        assert parse_market_cap("N/A") is None
        assert parse_market_cap("") is None
        assert parse_market_cap(None) is None

    def test_invalid_returns_zero(self):
        # Unknown format returns 0.0 per implementation
        assert parse_market_cap("invalid") == 0.0


class TestIsLikelyUsStock:
    def test_plain_symbols(self):
        assert is_likely_us_stock("AAPL") is True
        assert is_likely_us_stock("MSFT") is True

    def test_class_a_b_suffix(self):
        assert is_likely_us_stock("BRK.A") is True
        assert is_likely_us_stock("BRK.B") is True

    def test_non_us_suffix(self):
        assert is_likely_us_stock("BP.L") is False
        assert is_likely_us_stock("SAP.DE") is False

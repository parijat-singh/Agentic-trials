"""Tests for stock_agent.market_cap_scraper."""
from unittest.mock import MagicMock, patch
import pytest

# Import after path setup
from stock_agent.market_cap_scraper import (
    parse_market_cap, is_likely_us_stock, get_exchange_cached,
    is_nyse_or_nasdaq
)


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


def test_is_nyse_or_nasdaq():
    assert is_nyse_or_nasdaq("NMS") is True
    assert is_nyse_or_nasdaq("NYQ") is True
    assert is_nyse_or_nasdaq("NASDAQ") is True
    assert is_nyse_or_nasdaq("LSE") is False
    assert is_nyse_or_nasdaq("") is False
    assert is_nyse_or_nasdaq(None) is False


def test_get_exchange_cached_uses_db_first(temp_db):
    from stock_agent.db_manager import DBManager
    db = DBManager(db_path=temp_db)
    db.save_exchange("TEST", "NMS")
    with patch("stock_agent.market_cap_scraper.yf") as mock_yf:
        result = get_exchange_cached("TEST", db)
        assert result == "NMS"
        mock_yf.Ticker.assert_not_called()


def test_get_exchange_cached_fetches_and_saves_when_missing(temp_db):
    from stock_agent.db_manager import DBManager
    db = DBManager(db_path=temp_db)
    with patch("stock_agent.market_cap_scraper.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = {"exchange": "NMS"}
        mock_yf.Ticker.return_value = mock_ticker
        result = get_exchange_cached("NEW", db)
        assert result == "NMS"
        assert db.get_exchange("NEW") == "NMS"

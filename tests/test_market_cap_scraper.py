"""Tests for stock_agent.market_cap_scraper."""
from unittest.mock import MagicMock, patch
import os
import pandas as pd
import pytest

# Import after path setup
from stock_agent.market_cap_scraper import (
    parse_market_cap, is_likely_us_stock, get_exchange_cached,
    is_nyse_or_nasdaq, get_current_price, get_metadata_cached,
    get_pe_ratio, get_companies_from_page, process_batch
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

    def test_parse_exception_returns_none(self):
        # Malformed string triggers except, returns None
        assert parse_market_cap("$B") is None


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


def test_get_current_price_success():
    with patch("stock_agent.market_cap_scraper.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = {"regularMarketPrice": 150.0}
        mock_yf.Ticker.return_value = mock_ticker
        assert get_current_price("AAPL") == 150.0


def test_get_current_price_fallback_keys():
    with patch("stock_agent.market_cap_scraper.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = {"currentPrice": 100.0}
        mock_yf.Ticker.return_value = mock_ticker
        assert get_current_price("MSFT") == 100.0


def test_get_current_price_exception_returns_none():
    with patch("stock_agent.market_cap_scraper.yf") as mock_yf:
        mock_yf.Ticker.side_effect = Exception("network error")
        assert get_current_price("XYZ") is None


def test_get_pe_ratio_success():
    with patch("stock_agent.market_cap_scraper.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = {"trailingPE": 25.5}
        mock_yf.Ticker.return_value = mock_ticker
        assert get_pe_ratio("AAPL") == 25.5


def test_get_pe_ratio_forward_fallback():
    with patch("stock_agent.market_cap_scraper.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = {"trailingPE": None, "forwardPE": 20.0}
        mock_yf.Ticker.return_value = mock_ticker
        assert get_pe_ratio("MSFT") == 20.0


def test_get_metadata_cached_from_db(temp_db):
    from stock_agent.db_manager import DBManager
    db = DBManager(db_path=temp_db)
    db.save_exchange("X", "NMS")
    db.save_sector("X", "Technology")
    ex, sec = get_metadata_cached("X", db)
    assert ex == "NMS"
    assert sec == "Technology"


def test_get_metadata_cached_exception_returns_existing(temp_db):
    from stock_agent.db_manager import DBManager
    db = DBManager(db_path=temp_db)
    db.save_exchange("Z", "NYQ")
    with patch("stock_agent.market_cap_scraper.yf") as mock_yf:
        mock_yf.Ticker.side_effect = Exception("api error")
        ex, sec = get_metadata_cached("Z", db)
        assert ex == "NYQ"
        assert sec is None


def test_get_metadata_cached_fetches_when_missing(temp_db):
    from stock_agent.db_manager import DBManager
    db = DBManager(db_path=temp_db)
    with patch("stock_agent.market_cap_scraper.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = {"exchange": "NYQ", "sector": "Healthcare"}
        mock_yf.Ticker.return_value = mock_ticker
        ex, sec = get_metadata_cached("Y", db)
        assert ex == "NYQ"
        assert sec == "Healthcare"
        assert db.get_exchange("Y") == "NYQ"
        assert db.get_sector("Y") == "Healthcare"


def test_get_companies_from_page_mocked_response():
    mock_html = """
    <html><body><table>
    <tr>
        <td class="name-td">
            <div class="company-code">AAPL</div>
            <div class="company-name">Apple Inc</div>
        </td>
        <td>$3T</td>
    </tr>
    </table></body></html>
    """
    with patch("stock_agent.market_cap_scraper.requests") as mock_req:
        mock_resp = MagicMock()
        mock_resp.text = mock_html
        mock_resp.raise_for_status = MagicMock()
        mock_req.get.return_value = mock_resp
        companies = get_companies_from_page(1)
        assert len(companies) >= 1
        assert companies[0]["symbol"] == "AAPL"
        assert companies[0]["name"] == "Apple Inc"


def test_get_companies_from_page_request_error():
    with patch("stock_agent.market_cap_scraper.requests") as mock_req:
        mock_req.get.side_effect = Exception("Connection error")
        companies = get_companies_from_page(1)
        assert companies == []


def test_process_batch_industry_filter(mock_config):
    """process_batch skips stocks when sector not in industries list."""
    from stock_agent.db_manager import DBManager
    db = DBManager(db_path=mock_config["DB_PATH"])
    dates = pd.date_range(start="2015-01-01", periods=500, freq="B")
    df = pd.DataFrame({"Close": [100.0] * 500}, index=dates)
    db.save_history("AAPL", df)
    companies = [{"symbol": "AAPL", "name": "Apple", "market_cap": "$3B"}]
    with patch("stock_agent.market_cap_scraper.DATA_DIR", mock_config["DATA_DIR"]):
        with patch("stock_agent.db_manager.DBManager") as MockDB:
            MockDB.return_value = db
            with patch("stock_agent.market_cap_scraper.get_metadata_cached") as mock_meta:
                with patch("stock_agent.market_cap_scraper.get_pe_ratio", return_value=20.0):
                    with patch("stock_agent.market_cap_scraper.get_current_price", return_value=150.0):
                        mock_meta.return_value = ("NMS", "Healthcare")
                        accepted, stats, _ = process_batch(
                            companies, min_history=3, min_ipo_age=3, max_ipo_age=20,
                            max_pe=25, nyse_nasdaq_only=True, industries=["Technology"]
                        )
                        assert stats["Skipped_Industry"] == 1
                        assert len(accepted) == 0


def test_process_batch_empty_candidates():
    companies = [{"symbol": "BP.L", "name": "BP", "market_cap": "$100B"}]
    accepted, stats, stop = process_batch(
        companies, min_history=5, min_ipo_age=5, max_ipo_age=10,
        max_pe=None, min_market_cap=None
    )
    assert len(accepted) == 0
    assert stats["Non_US"] == 1


def test_process_batch_min_market_cap_stop_condition(mock_config):
    companies = [
        {"symbol": "SMALL", "name": "Small Cap", "market_cap": "$0.5B"},
        {"symbol": "TINY", "name": "Tiny", "market_cap": "$0.1B"},
    ]
    with patch("stock_agent.market_cap_scraper.DATA_DIR", mock_config["DATA_DIR"]):
        accepted, stats, stop = process_batch(
            companies, min_history=5, min_ipo_age=5, max_ipo_age=10,
            max_pe=None, min_market_cap=1.0
        )
        assert stop is True
        assert "Skipped_Market_Cap" in stats or len(accepted) == 0


def test_process_batch_with_mocked_yfinance(mock_config):
    from stock_agent.db_manager import DBManager
    data_dir = mock_config["DATA_DIR"]
    db_path = mock_config["DB_PATH"]
    db = DBManager(db_path=db_path)
    os.makedirs(data_dir, exist_ok=True)

    dates = pd.date_range(start="2015-01-01", periods=500, freq="B")
    df_history = pd.DataFrame({"Close": [100.0 * (1.001) ** i for i in range(500)]}, index=dates)
    df_history.index = pd.to_datetime(df_history.index)
    db.save_history("AAPL", df_history)

    companies = [{"symbol": "AAPL", "name": "Apple", "market_cap": "$3B"}]
    with patch("stock_agent.market_cap_scraper.DATA_DIR", data_dir):
        with patch("stock_agent.db_manager.DBManager") as MockDB:
            MockDB.return_value = db
            with patch("stock_agent.market_cap_scraper.get_metadata_cached") as mock_meta:
                with patch("stock_agent.market_cap_scraper.get_pe_ratio", return_value=20.0):
                    with patch("stock_agent.market_cap_scraper.get_current_price", return_value=150.0):
                        mock_meta.return_value = ("NMS", "Technology")
                        accepted, stats, stop = process_batch(
                            companies, min_history=3, min_ipo_age=3, max_ipo_age=20,
                            max_pe=25, min_market_cap=None, nyse_nasdaq_only=True,
                            industries=None
                        )
    assert "Scanned" in stats
    assert stats["Scanned"] == 1


def test_process_batch_fresh_download_mocked(mock_config):
    """process_batch with symbols not in DB uses yf.download (mocked)."""
    from stock_agent.db_manager import DBManager
    data_dir = mock_config["DATA_DIR"]
    db = DBManager(db_path=mock_config["DB_PATH"])
    os.makedirs(data_dir, exist_ok=True)

    companies = [{"symbol": "NEWSTOCK", "name": "New", "market_cap": "$5B"}]
    mock_df = pd.DataFrame(
        {"Close": [100.0 * (1.001) ** i for i in range(500)]},
        index=pd.date_range("2015-01-01", periods=500, freq="B")
    )
    with patch("stock_agent.market_cap_scraper.DATA_DIR", data_dir):
        with patch("stock_agent.db_manager.DBManager") as MockDB:
            MockDB.return_value = db
            with patch("stock_agent.market_cap_scraper.yf.download", return_value=mock_df):
                with patch("stock_agent.market_cap_scraper.get_metadata_cached") as mock_meta:
                    with patch("stock_agent.market_cap_scraper.get_pe_ratio", return_value=15.0):
                        with patch("stock_agent.market_cap_scraper.get_current_price", return_value=50.0):
                            mock_meta.return_value = ("NMS", "Technology")
                            accepted, stats, stop = process_batch(
                                companies, min_history=3, min_ipo_age=3, max_ipo_age=20,
                                max_pe=30, min_market_cap=None, nyse_nasdaq_only=True
                            )
    assert "Scanned" in stats

"""Tests for etf_agent.etf_scraper."""
import os
import pytest


def test_parse_symbol_plain():
    from etf_agent.etf_scraper import _parse_symbol_from_link_text
    assert _parse_symbol_from_link_text("SPDR S&P 500 ETFSPY") == "SPY"
    assert _parse_symbol_from_link_text("Vanguard S&P 500 ETFVOO") == "VOO"
    assert _parse_symbol_from_link_text("Invesco QQQ TrustQQQ") == "QQQ"
    assert _parse_symbol_from_link_text("Vanguard Total Stock Market Index Fund ETF SharesVTI") == "VTI"


def test_parse_symbol_suffix():
    from etf_agent.etf_scraper import _parse_symbol_from_link_text
    result = _parse_symbol_from_link_text("iShares Core S&P 500 UCITS ETF USD (Acc)SXR8.DE")
    assert result in ("SXR8.DE", "DE"), "suffix ticker with .XX"


def test_parse_symbol_none_empty():
    from etf_agent.etf_scraper import _parse_symbol_from_link_text
    assert _parse_symbol_from_link_text("") is None
    assert _parse_symbol_from_link_text(None) is None


def test_parse_symbol_no_ticker():
    from etf_agent.etf_scraper import _parse_symbol_from_link_text
    assert _parse_symbol_from_link_text("No ticker at end!") is None


def test_scrape_etf_page_mock():
    from unittest.mock import patch, MagicMock
    from etf_agent.etf_scraper import scrape_etf_page
    html = "<html><body><a href=\"/vanguard-sp-500-etf/marketcap/\">Vanguard S&P 500 ETFVOO</a><a href=\"/spdr-sp-500-etf/marketcap/\">SPDR S&P 500 ETFSPY</a></body></html>"
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()
    with patch("etf_agent.etf_scraper.requests.get", return_value=mock_resp):
        result = scrape_etf_page("https://companiesmarketcap.com/etfs/largest-etfs-by-marketcap/")
    assert len(result) >= 2
    symbols = {r["symbol"] for r in result}
    assert "VOO" in symbols
    assert "SPY" in symbols
    for r in result:
        assert "symbol" in r and "name" in r


def test_scrape_etf_page_request_error():
    from unittest.mock import patch
    from etf_agent.etf_scraper import scrape_etf_page
    import requests
    with patch("etf_agent.etf_scraper.requests.get", side_effect=requests.HTTPError("500")):
        result = scrape_etf_page("https://companiesmarketcap.com/etfs/largest-etfs-by-marketcap/")
    assert result == []


def test_run_scraper_max_pages_1(mock_etf_config):
    from unittest.mock import patch, MagicMock
    from etf_agent.etf_scraper import run_scraper
    mock_resp = MagicMock()
    mock_resp.text = "<html><body><p>No links</p></body></html>"
    mock_resp.raise_for_status = MagicMock()
    with patch("etf_agent.etf_scraper.requests.get", return_value=mock_resp), patch("etf_agent.etf_scraper.time.sleep"):
        path = run_scraper(max_pages=1)
    assert path is not None
    assert path.endswith("etf_universe.csv")
    assert os.path.exists(path)
    import pandas as pd
    df = pd.read_csv(path)
    assert not df.empty
    assert "symbol" in df.columns and "name" in df.columns

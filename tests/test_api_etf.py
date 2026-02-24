"""Tests for ETF API endpoints."""
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_server import app
client = TestClient(app)

def test_etf_analyze_post():
    from unittest.mock import patch
    with patch("api_server.run_etf_pipeline_background"):
        r = client.post("/etf-analyze", json={"max_expense_ratio": 0.005, "min_aum": 1e9, "min_history_years": 3.0, "nyse_nasdaq_only": True, "skip_scraper": False, "skip_fetcher": False})
    assert r.status_code == 200
    assert "session_id" in r.json() and "status" in r.json()

def test_etf_status_404():
    assert client.get("/etf-status/nonexistent-99").status_code == 404

def test_etf_log_404():
    assert client.get("/etf-log/nonexistent-99").status_code == 404

"""Tests for api_server FastAPI app."""
from fastapi.testclient import TestClient
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_server import app

client = TestClient(app)


def test_read_root_redirects():
    response = client.get("/")
    assert response.status_code in (200, 307, 308)


def test_status_endpoint():
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "logs" in data


def test_analyze_post():
    response = client.post("/analyze", json={})
    assert response.status_code in (200, 400)


def test_stop_endpoint():
    response = client.post("/stop")
    assert response.status_code == 200
    assert "status" in response.json()


def test_static_no_cache_headers():
    """Verify static assets receive Cache-Control no-cache headers."""
    response = client.get("/static/index.html")
    assert response.status_code == 200
    cache = response.headers.get("cache-control", "") or response.headers.get("Cache-Control", "")
    assert "no-cache" in cache.lower() or "no-store" in cache.lower()


def test_analyze_with_min_price_and_industries():
    """Verify /analyze builds cmd with --min-price and --industries when provided."""
    from unittest.mock import patch
    with patch("api_server.state") as mock_state:
        mock_state.status = "idle"
        mock_state.process = None
        with patch("api_server.threading.Thread") as mock_thread:
            response = client.post("/analyze", json={
                "min_price": 1.0,
                "industries": ["Technology", "Energy"],
                "skip_scraper": True
            })
            assert response.status_code == 200
            call_kwargs = mock_thread.call_args[1]
            cmd = call_kwargs["args"][0]
    assert any("--min-price=1.0" in arg for arg in cmd)
    ind_arg = [a for a in cmd if a.startswith("--industries=")]
    assert len(ind_arg) == 1
    assert "Technology" in ind_arg[0] and "Energy" in ind_arg[0]

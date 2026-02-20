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

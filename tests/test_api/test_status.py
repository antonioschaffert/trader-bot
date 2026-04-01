from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_status_returns_running_with_recent_scan():
    mock_db = MagicMock()
    scan_col = MagicMock()
    settings_col = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=lambda name: {"scan_rejections": scan_col, "settings": settings_col}[name])
    scan_col.find_one.return_value = {"timestamp": datetime(2026, 4, 1, 15, 0, 0, tzinfo=timezone.utc), "symbol": "SPY"}
    settings_col.find_one.return_value = {"_id": "config", "symbols": ["SPY", "QQQ"]}
    with patch("api.routes.status.get_db", return_value=mock_db):
        resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbols"] == ["SPY", "QQQ"]

def test_status_returns_not_running_when_no_scans():
    mock_db = MagicMock()
    scan_col = MagicMock()
    settings_col = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=lambda name: {"scan_rejections": scan_col, "settings": settings_col}[name])
    scan_col.find_one.return_value = None
    settings_col.find_one.return_value = None
    with patch("api.routes.status.get_db", return_value=mock_db):
        resp = client.get("/api/status")
    assert resp.status_code == 200
    assert resp.json()["running"] is False

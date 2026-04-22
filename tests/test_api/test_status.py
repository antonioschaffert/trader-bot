from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def _mock_db(scan_doc=None, settings_doc=None, heartbeat_doc=None):
    mock = MagicMock()
    accounts_col = MagicMock()
    accounts_col.find.return_value = []
    collections = {
        "scan_rejections": MagicMock(),
        "settings": MagicMock(),
        "heartbeat": MagicMock(),
        "accounts": accounts_col,
    }
    mock.__getitem__ = MagicMock(side_effect=lambda name: collections[name])
    collections["scan_rejections"].find_one.return_value = scan_doc
    collections["settings"].find_one.return_value = settings_doc
    collections["heartbeat"].find_one.return_value = heartbeat_doc
    return mock

def test_status_returns_running_with_recent_scan():
    db = _mock_db(
        scan_doc={"timestamp": datetime(2026, 4, 1, 15, 0, 0, tzinfo=timezone.utc), "symbol": "SPY"},
        settings_doc={"_id": "config", "symbols": ["SPY", "QQQ"]},
        heartbeat_doc={"_id": "bot", "timestamp": datetime.now(timezone.utc), "market_hours": True},
    )
    with patch("api.routes.status.get_db", return_value=db):
        resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbols"] == ["SPY", "QQQ"]
    assert data["running"] is True

def test_status_returns_not_running_when_no_scans():
    db = _mock_db()
    with patch("api.routes.status.get_db", return_value=db):
        resp = client.get("/api/status")
    assert resp.status_code == 200
    assert resp.json()["running"] is False

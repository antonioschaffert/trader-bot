import copy
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_get_settings():
    mock_db = MagicMock()
    col = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=col)
    col.find_one.return_value = {"_id": "config", "symbols": ["SPY", "QQQ"], "updated_at": datetime(2026, 4, 1, 15, 0, tzinfo=timezone.utc)}
    with patch("api.routes.settings.get_db", return_value=mock_db):
        resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbols"] == ["SPY", "QQQ"]
    assert "_id" not in data

def test_put_settings_merges():
    mock_db = MagicMock()
    col = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=col)
    col.find_one.return_value = {"_id": "config", "symbols": ["SPY", "QQQ"], "risk": {"daily_loss_limit": 500}, "updated_at": datetime(2026, 4, 1, 16, 0, tzinfo=timezone.utc)}
    with patch("api.routes.settings.get_db", return_value=mock_db):
        resp = client.put("/api/settings", json={"risk": {"daily_loss_limit": 500}})
    assert resp.status_code == 200
    col.update_one.assert_called_once()

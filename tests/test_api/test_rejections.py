from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_rejections_returns_items():
    mock_db = MagicMock()
    col = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=col)
    col.count_documents.return_value = 1
    col.find.return_value.sort.return_value.limit.return_value = [
        {"_id": "abc123", "symbol": "SPY", "timestamp": datetime(2026, 4, 1, 15, 0, tzinfo=timezone.utc),
         "market_snapshot": {"price": 656.66},
         "rejections": [{"strategy": "swing", "reason": "iv_rank_unavailable", "variables": {}}]}
    ]
    with patch("api.routes.rejections.get_db", return_value=mock_db):
        resp = client.get("/api/rejections?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["symbol"] == "SPY"

def test_rejections_filters_by_symbol():
    mock_db = MagicMock()
    col = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=col)
    col.count_documents.return_value = 0
    col.find.return_value.sort.return_value.limit.return_value = []
    with patch("api.routes.rejections.get_db", return_value=mock_db):
        resp = client.get("/api/rejections?symbol=QQQ")
    assert resp.status_code == 200
    col.find.assert_called_once_with({"symbol": "QQQ"})

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.db.mongo import MongoStore


@patch("src.db.mongo.MongoClient")
def test_mongo_store_connects(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    store = MongoStore("mongodb://localhost:27017", "test_db")
    mock_client_cls.assert_called_once_with("mongodb://localhost:27017")
    assert store.db == mock_client["test_db"]


@patch("src.db.mongo.MongoClient")
def test_save_iv_record(mock_client_cls):
    mock_db = MagicMock()
    mock_client_cls.return_value.__getitem__ = MagicMock(return_value=mock_db)
    store = MongoStore("mongodb://localhost:27017", "test_db")
    record = {"symbol": "SPY", "iv": 0.25, "timestamp": datetime.now(timezone.utc)}
    store.save_iv_record(record)
    mock_db["iv_history"].insert_one.assert_called_once_with(record)


@patch("src.db.mongo.MongoClient")
def test_get_iv_history(mock_client_cls):
    mock_db = MagicMock()
    mock_client_cls.return_value.__getitem__ = MagicMock(return_value=mock_db)
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = [
        {"symbol": "SPY", "iv": 0.20},
        {"symbol": "SPY", "iv": 0.25},
    ]
    mock_db["iv_history"].find.return_value = mock_cursor
    store = MongoStore("mongodb://localhost:27017", "test_db")
    since = datetime(2025, 1, 1, tzinfo=timezone.utc)
    result = store.get_iv_history("SPY", since)
    mock_db["iv_history"].find.assert_called_once_with(
        {"symbol": "SPY", "timestamp": {"$gte": since}}
    )
    assert len(result) == 2


@patch("src.db.mongo.MongoClient")
def test_save_trade(mock_client_cls):
    mock_db = MagicMock()
    mock_client_cls.return_value.__getitem__ = MagicMock(return_value=mock_db)
    store = MongoStore("mongodb://localhost:27017", "test_db")
    trade = {"symbol": "SPY", "type": "put_spread", "premium": 1.50}
    store.save_trade(trade)
    mock_db["trades"].insert_one.assert_called_once_with(trade)


@patch("src.db.mongo.MongoClient")
def test_get_todays_trades(mock_client_cls):
    mock_db = MagicMock()
    mock_client_cls.return_value.__getitem__ = MagicMock(return_value=mock_db)
    mock_db["trades"].find.return_value = [
        {"symbol": "SPY", "pnl": 50.0},
        {"symbol": "QQQ", "pnl": -20.0},
    ]
    store = MongoStore("mongodb://localhost:27017", "test_db")
    result = store.get_todays_trades()
    assert len(result) == 2

from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

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


# ---- Settings tests ----


def _make_store():
    """Create a MongoStore with a fake in-memory settings collection."""
    with patch("src.db.mongo.MongoClient") as mock_client_cls:
        mock_db = MagicMock()
        mock_client_cls.return_value.__getitem__ = MagicMock(return_value=mock_db)

        # Use a real dict to back the settings collection so tests can
        # exercise get/save/seed interactions end-to-end without hitting Mongo.
        _docs: dict[str, dict] = {}

        def _find_one(query):
            _id = query.get("_id")
            doc = _docs.get(_id)
            if doc is None:
                return None
            return dict(doc)  # return a copy

        def _update_one(query, update, upsert=False):
            _id = query.get("_id")
            if _id not in _docs and upsert:
                _docs[_id] = {"_id": _id}
            if _id in _docs:
                _docs[_id].update(update.get("$set", {}))

        settings_col = MagicMock()
        settings_col.find_one = MagicMock(side_effect=_find_one)
        settings_col.update_one = MagicMock(side_effect=_update_one)

        mock_db.__getitem__ = lambda self, key: settings_col if key == "settings" else MagicMock()

        store = MongoStore("mongodb://localhost:27017", "test_db")
        return store


def test_get_settings_returns_none_when_empty():
    store = _make_store()
    result = store.get_settings()
    assert result is None


def test_save_settings_upserts():
    store = _make_store()
    result = store.save_settings({"max_positions": 5})
    assert result is not None
    assert result["max_positions"] == 5
    assert "updated_at" in result
    assert "_id" not in result


def test_save_settings_merges():
    store = _make_store()
    store.save_settings({"max_positions": 5, "symbol": "SPY"})
    result = store.save_settings({"max_positions": 10})
    assert result["max_positions"] == 10
    assert result["symbol"] == "SPY"  # first save's key preserved


def test_seed_settings_does_not_overwrite():
    store = _make_store()
    store.save_settings({"max_positions": 5})
    store.seed_settings({"max_positions": 99, "new_key": "hello"})
    result = store.get_settings()
    assert result["max_positions"] == 5  # original value preserved
    assert "new_key" not in result  # seed did not write

import logging
from datetime import datetime, time, timezone

from pymongo import MongoClient

logger = logging.getLogger(__name__)


class MongoStore:
    def __init__(self, uri: str, db_name: str):
        self._client = MongoClient(uri)
        self.db = self._client[db_name]

    def save_iv_record(self, record: dict) -> None:
        self.db["iv_history"].insert_one(record)

    def get_iv_history(self, symbol: str, since: datetime) -> list[dict]:
        cursor = self.db["iv_history"].find(
            {"symbol": symbol, "timestamp": {"$gte": since}}
        )
        return list(cursor.sort("timestamp", 1))

    def save_trade(self, trade: dict) -> None:
        self.db["trades"].insert_one(trade)

    def update_trade(self, trade_id: str, update: dict) -> None:
        self.db["trades"].update_one({"_id": trade_id}, {"$set": update})

    def get_todays_trades(self) -> list[dict]:
        today_start = datetime.combine(
            datetime.now(timezone.utc).date(), time.min
        ).replace(tzinfo=timezone.utc)
        return list(self.db["trades"].find({"opened_at": {"$gte": today_start}}))

    def save_options_snapshot(self, snapshot: dict) -> None:
        self.db["options_snapshots"].insert_one(snapshot)

    def save_order_log(self, order: dict) -> None:
        self.db["order_logs"].insert_one(order)

    def save_scan_rejection(self, record: dict) -> None:
        self.db["scan_rejections"].insert_one(record)

    def get_settings(self) -> dict | None:
        doc = self.db["settings"].find_one({"_id": "config"})
        if doc is None:
            return None
        doc.pop("_id", None)
        return doc

    def save_settings(self, settings: dict) -> dict:
        self.db["settings"].update_one(
            {"_id": "config"},
            {"$set": {**settings, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        return self.get_settings()

    def seed_settings(self, defaults: dict) -> None:
        if self.get_settings() is None:
            self.save_settings(defaults)

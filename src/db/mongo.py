import logging
from datetime import datetime, time, timezone

from pymongo import MongoClient

logger = logging.getLogger(__name__)


class MongoStore:
    def __init__(self, uri: str, db_name: str):
        self._client = MongoClient(uri)
        self.db = self._client[db_name]

    # --- IV History ---
    def save_iv_record(self, record: dict) -> None:
        self.db["iv_history"].insert_one(record)

    def get_iv_history(self, symbol: str, since: datetime) -> list[dict]:
        cursor = self.db["iv_history"].find(
            {"symbol": symbol, "timestamp": {"$gte": since}}
        )
        return list(cursor.sort("timestamp", 1))

    # --- Trades ---
    def save_trade(self, trade: dict) -> None:
        self.db["trades"].insert_one(trade)

    def update_trade(self, trade_id: str, update: dict) -> None:
        self.db["trades"].update_one({"_id": trade_id}, {"$set": update})

    def get_todays_trades(self) -> list[dict]:
        today_start = datetime.combine(
            datetime.now(timezone.utc).date(), time.min
        ).replace(tzinfo=timezone.utc)
        return list(self.db["trades"].find({"opened_at": {"$gte": today_start}}))

    # --- Options Snapshots ---
    def save_options_snapshot(self, snapshot: dict) -> None:
        self.db["options_snapshots"].insert_one(snapshot)

    # --- Order Logs ---
    def save_order_log(self, order: dict) -> None:
        self.db["order_logs"].insert_one(order)

    # --- Scan Rejections ---
    def save_scan_rejection(self, record: dict) -> None:
        self.db["scan_rejections"].insert_one(record)

    # --- Settings ---
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

    # --- Market Regime ---
    def save_regime_snapshot(self, snapshot: dict) -> None:
        """Save a market regime snapshot. Upserts on a single doc for latest."""
        self.db["regime"].update_one(
            {"_id": "latest"},
            {"$set": {**snapshot, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        # Also save to history for trend analysis
        self.db["regime_history"].insert_one(snapshot)

    def get_regime_snapshot(self) -> dict | None:
        doc = self.db["regime"].find_one({"_id": "latest"})
        if doc:
            doc.pop("_id", None)
        return doc

    def get_regime_history(self, limit: int = 100) -> list[dict]:
        cursor = self.db["regime_history"].find().sort("timestamp", -1).limit(limit)
        results = list(cursor)
        for r in results:
            r["_id"] = str(r["_id"])
        return results

    # --- Portfolio Greeks ---
    def save_portfolio_greeks(self, greeks: dict) -> None:
        self.db["portfolio_greeks"].update_one(
            {"_id": "latest"},
            {"$set": {**greeks, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    def get_portfolio_greeks(self) -> dict | None:
        doc = self.db["portfolio_greeks"].find_one({"_id": "latest"})
        if doc:
            doc.pop("_id", None)
        return doc

    # --- Drawdown State ---
    def save_drawdown_state(self, state: dict) -> None:
        self.db["drawdown"].update_one(
            {"_id": "state"},
            {"$set": {**state, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    def get_drawdown_state(self) -> dict | None:
        doc = self.db["drawdown"].find_one({"_id": "state"})
        if doc:
            doc.pop("_id", None)
        return doc

    # --- Wheel State ---
    def save_wheel_state(self, state: dict) -> None:
        self.db["wheel_state"].update_one(
            {"symbol": state["symbol"]},
            {"$set": {**state, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    def get_wheel_states(self) -> list[dict]:
        results = list(self.db["wheel_state"].find())
        for r in results:
            r["_id"] = str(r["_id"])
        return results

    def get_wheel_state(self, symbol: str) -> dict | None:
        doc = self.db["wheel_state"].find_one({"symbol": symbol})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    # --- Performance Analytics (cached) ---
    def save_performance_cache(self, report: dict) -> None:
        self.db["performance"].update_one(
            {"_id": "latest"},
            {"$set": {**report, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    def get_performance_cache(self) -> dict | None:
        doc = self.db["performance"].find_one({"_id": "latest"})
        if doc:
            doc.pop("_id", None)
        return doc

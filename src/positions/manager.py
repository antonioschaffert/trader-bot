import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from src.db.mongo import MongoStore
from src.event_bus import EventBus
from src.signals.models import SpreadLeg

logger = logging.getLogger(__name__)


@dataclass
class TrackedSpread:
    order_id: str
    strategy_mode: str
    symbol: str
    spread_type: str
    legs: list[SpreadLeg]
    expiration: date
    entry_premium: float
    profit_target_pct: int
    opened_at: datetime
    current_value: float = 0.0
    unrealized_pnl: float = 0.0


class PositionManager:
    def __init__(self, db: MongoStore, event_bus: EventBus):
        self._db = db
        self._bus = event_bus
        self.open_positions: list[TrackedSpread] = []
        self.daily_pnl: float = 0.0
        self._closed_today: list[dict] = []
        self._bus.subscribe("OrderFilled", self._on_order_filled)

    def _on_order_filled(self, data: dict) -> None:
        signal = data["signal"]
        spread = TrackedSpread(
            order_id=data["order_id"], strategy_mode=signal.strategy_mode,
            symbol=signal.symbol, spread_type=signal.spread_type,
            legs=signal.legs, expiration=signal.expiration,
            entry_premium=data.get("filled_price", signal.target_premium),
            profit_target_pct=signal.profit_target_pct,
            opened_at=datetime.now(timezone.utc),
        )
        self.add_position(spread)

    def add_position(self, spread: TrackedSpread) -> None:
        self.open_positions.append(spread)
        logger.info(
            f"Opened {spread.spread_type} on {spread.symbol} "
            f"(premium: ${spread.entry_premium:.2f}, exp: {spread.expiration})"
        )

    def close_position(self, order_id: str, close_premium: float, reason: str) -> None:
        spread = next((p for p in self.open_positions if p.order_id == order_id), None)
        if spread is None:
            logger.warning(f"Position {order_id} not found")
            return

        pnl = (spread.entry_premium - close_premium) * 100
        self.daily_pnl += pnl

        trade_record = {
            "order_id": spread.order_id, "strategy_mode": spread.strategy_mode,
            "symbol": spread.symbol, "spread_type": spread.spread_type,
            "expiration": str(spread.expiration), "entry_premium": spread.entry_premium,
            "close_premium": close_premium, "pnl": pnl, "reason": reason,
            "opened_at": spread.opened_at, "closed_at": datetime.now(timezone.utc),
        }
        self._db.save_trade(trade_record)
        self._closed_today.append(trade_record)
        self.open_positions = [p for p in self.open_positions if p.order_id != order_id]
        self._bus.publish("PositionClosed", trade_record)
        logger.info(f"Closed {spread.symbol} {spread.spread_type}: P&L ${pnl:.2f} ({reason})")

    def get_positions_by_symbol(self, symbol: str) -> list[TrackedSpread]:
        return [p for p in self.open_positions if p.symbol == symbol]

    def reset_daily(self) -> None:
        self.daily_pnl = 0.0
        self._closed_today = []

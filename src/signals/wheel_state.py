"""
Wheel State Manager - Persistent State Machine

Tracks per-symbol wheel phase:
  idle -> selling_csp -> (assigned) -> holding_shares -> selling_cc -> (called away) -> idle

State persists to MongoDB so the wheel survives bot restarts.
"""

import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone

from src.db.mongo import MongoStore

logger = logging.getLogger(__name__)

# Valid phase transitions
VALID_TRANSITIONS = {
    "idle": ["selling_csp"],
    "selling_csp": ["idle", "holding_shares"],       # expired OTM -> idle, assigned -> holding
    "holding_shares": ["selling_cc"],
    "selling_cc": ["holding_shares", "idle"],         # expired OTM -> holding, called away -> idle
}


@dataclass
class WheelPosition:
    symbol: str
    phase: str = "idle"
    shares_held: int = 0
    cost_basis: float = 0.0                          # avg cost per share (strike - premium)
    total_premium_collected: float = 0.0             # cumulative premium this cycle
    current_option_order_id: str = ""
    current_option_symbol: str = ""
    current_option_strike: float = 0.0
    current_option_expiration: date | None = None
    current_option_entry_premium: float = 0.0
    current_option_entry_delta: float = 0.0
    current_option_quantity: int = 0
    cycles_completed: int = 0
    started_at: datetime | None = None
    last_updated: datetime | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        # Convert dates to strings for MongoDB
        if d["current_option_expiration"]:
            d["current_option_expiration"] = str(d["current_option_expiration"])
        if d["started_at"]:
            d["started_at"] = d["started_at"].isoformat()
        if d["last_updated"]:
            d["last_updated"] = d["last_updated"].isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "WheelPosition":
        d = dict(d)
        d.pop("_id", None)
        d.pop("updated_at", None)
        # Parse dates back
        exp = d.get("current_option_expiration")
        if exp and isinstance(exp, str) and exp != "None":
            d["current_option_expiration"] = date.fromisoformat(exp)
        else:
            d["current_option_expiration"] = None
        for key in ("started_at", "last_updated"):
            val = d.get(key)
            if val and isinstance(val, str):
                d["current_option_expiration"]  # leave as-is if already datetime
                try:
                    d[key] = datetime.fromisoformat(val)
                except (ValueError, TypeError):
                    d[key] = None
            elif not isinstance(val, datetime):
                d[key] = None
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class WheelStateManager:
    def __init__(self, db: MongoStore):
        self._db = db
        self._positions: dict[str, WheelPosition] = {}

    def load_state(self) -> None:
        """Load all wheel states from MongoDB on startup."""
        states = self._db.get_wheel_states()
        for s in states:
            try:
                pos = WheelPosition.from_dict(s)
                self._positions[pos.symbol] = pos
                logger.info(f"Wheel state loaded: {pos.symbol} phase={pos.phase}")
            except Exception:
                logger.exception(f"Failed to load wheel state for {s.get('symbol')}")

    def save_state(self, symbol: str) -> None:
        """Persist a single symbol's wheel state to MongoDB."""
        pos = self._positions.get(symbol)
        if pos:
            self._db.save_wheel_state(pos.to_dict())

    def get_position(self, symbol: str) -> WheelPosition:
        """Get or create a wheel position for a symbol."""
        if symbol not in self._positions:
            self._positions[symbol] = WheelPosition(symbol=symbol)
        return self._positions[symbol]

    def get_all_positions(self) -> list[WheelPosition]:
        return list(self._positions.values())

    def get_active_positions(self) -> list[WheelPosition]:
        return [p for p in self._positions.values() if p.phase != "idle"]

    def transition(self, symbol: str, new_phase: str, **kwargs) -> None:
        """Transition a symbol to a new wheel phase with validation."""
        pos = self.get_position(symbol)
        old_phase = pos.phase

        allowed = VALID_TRANSITIONS.get(old_phase, [])
        if new_phase not in allowed:
            logger.error(
                f"Invalid wheel transition for {symbol}: {old_phase} -> {new_phase} "
                f"(allowed: {allowed})"
            )
            return

        pos.phase = new_phase
        pos.last_updated = datetime.now(timezone.utc)

        # Apply any additional state changes
        for key, value in kwargs.items():
            if hasattr(pos, key):
                setattr(pos, key, value)

        # Phase-specific logic
        if new_phase == "selling_csp" and not pos.started_at:
            pos.started_at = datetime.now(timezone.utc)

        if new_phase == "idle" and old_phase == "selling_cc":
            # Full cycle completed (shares called away)
            pos.cycles_completed += 1
            pos.shares_held = 0
            pos.cost_basis = 0.0
            pos.current_option_order_id = ""
            pos.current_option_symbol = ""
            pos.current_option_strike = 0.0
            pos.current_option_expiration = None
            pos.current_option_entry_premium = 0.0
            pos.current_option_entry_delta = 0.0
            pos.current_option_quantity = 0

        if new_phase == "idle" and old_phase == "selling_csp":
            # CSP expired OTM, reset option fields
            pos.current_option_order_id = ""
            pos.current_option_symbol = ""
            pos.current_option_strike = 0.0
            pos.current_option_expiration = None
            pos.current_option_entry_premium = 0.0
            pos.current_option_entry_delta = 0.0
            pos.current_option_quantity = 0

        if new_phase == "holding_shares" and old_phase == "selling_csp":
            # Assigned on CSP
            pos.current_option_order_id = ""
            pos.current_option_symbol = ""
            pos.current_option_expiration = None
            pos.current_option_entry_premium = 0.0
            pos.current_option_entry_delta = 0.0

        if new_phase == "holding_shares" and old_phase == "selling_cc":
            # CC expired OTM, reset option fields but keep shares
            pos.current_option_order_id = ""
            pos.current_option_symbol = ""
            pos.current_option_strike = 0.0
            pos.current_option_expiration = None
            pos.current_option_entry_premium = 0.0
            pos.current_option_entry_delta = 0.0
            pos.current_option_quantity = 0

        self.save_state(symbol)
        logger.info(f"Wheel transition: {symbol} {old_phase} -> {new_phase}")

    def clear_option(self, symbol: str) -> None:
        """Clear current option fields without changing phase."""
        pos = self.get_position(symbol)
        pos.current_option_order_id = ""
        pos.current_option_symbol = ""
        pos.current_option_strike = 0.0
        pos.current_option_expiration = None
        pos.current_option_entry_premium = 0.0
        pos.current_option_entry_delta = 0.0
        pos.current_option_quantity = 0
        pos.last_updated = datetime.now(timezone.utc)
        self.save_state(symbol)

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.event_bus import EventBus
from src.positions.manager import PositionManager, TrackedSpread
from src.signals.models import SpreadLeg, TradeSignal


@pytest.fixture
def mock_db():
    return MagicMock()


def _make_spread():
    return TrackedSpread(
        order_id="order-123", strategy_mode="swing", symbol="SPY", spread_type="put_spread",
        legs=[
            SpreadLeg("SPY260410P00495000", 495.0, "put", "sell", -0.20),
            SpreadLeg("SPY260410P00490000", 490.0, "put", "buy", -0.10),
        ],
        expiration=date(2026, 4, 10), entry_premium=1.50, profit_target_pct=50,
        opened_at=datetime.now(timezone.utc),
    )


def test_add_position(mock_db, event_bus):
    pm = PositionManager(mock_db, event_bus)
    spread = _make_spread()
    pm.add_position(spread)
    assert len(pm.open_positions) == 1
    assert pm.open_positions[0].order_id == "order-123"


def test_remove_position(mock_db, event_bus):
    pm = PositionManager(mock_db, event_bus)
    spread = _make_spread()
    pm.add_position(spread)
    pm.close_position("order-123", close_premium=0.50, reason="profit_target")
    assert len(pm.open_positions) == 0
    mock_db.save_trade.assert_called_once()


def test_close_records_pnl(mock_db, event_bus):
    pm = PositionManager(mock_db, event_bus)
    spread = _make_spread()
    pm.add_position(spread)
    pm.close_position("order-123", close_premium=0.50, reason="profit_target")
    trade_record = mock_db.save_trade.call_args[0][0]
    assert trade_record["pnl"] == pytest.approx(100.0)


def test_daily_pnl(mock_db, event_bus):
    pm = PositionManager(mock_db, event_bus)
    spread = _make_spread()
    pm.add_position(spread)
    pm.close_position("order-123", close_premium=0.50, reason="profit_target")
    assert pm.daily_pnl == pytest.approx(100.0)


def test_get_positions_by_symbol(mock_db, event_bus):
    pm = PositionManager(mock_db, event_bus)
    spread1 = _make_spread()
    spread2 = _make_spread()
    spread2.order_id = "order-456"
    spread2.symbol = "QQQ"
    pm.add_position(spread1)
    pm.add_position(spread2)
    spy_positions = pm.get_positions_by_symbol("SPY")
    assert len(spy_positions) == 1


def test_on_order_filled_creates_position(mock_db, event_bus):
    pm = PositionManager(mock_db, event_bus)
    signal = TradeSignal(
        strategy_mode="swing", symbol="SPY", spread_type="put_spread",
        legs=[
            SpreadLeg("SPY260410P00495000", 495.0, "put", "sell", -0.20),
            SpreadLeg("SPY260410P00490000", 490.0, "put", "buy", -0.10),
        ],
        expiration=date(2026, 4, 10), target_premium=1.50, profit_target_pct=50,
    )
    event_bus.publish("OrderFilled", {"order_id": "order-789", "signal": signal, "filled_price": 1.45})
    assert len(pm.open_positions) == 1
    assert pm.open_positions[0].entry_premium == 1.45

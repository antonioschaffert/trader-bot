from datetime import date
from unittest.mock import MagicMock, patch, call

import pytest

from src.event_bus import EventBus
from src.execution.executor import OrderExecutor
from src.signals.models import SpreadLeg, TradeSignal


@pytest.fixture
def exec_config():
    return {"price_adjustment_interval": 30, "price_adjustment_step": 0.01, "fill_timeout": 300}


@pytest.fixture
def mock_trading_client():
    client = MagicMock()
    order = MagicMock()
    order.id = "order-123"
    order.status = "filled"
    order.filled_avg_price = 1.45
    client.submit_order.return_value = order
    return client


@pytest.fixture
def mock_db():
    return MagicMock()


def _make_signal():
    return TradeSignal(
        strategy_mode="swing", symbol="SPY", spread_type="put_spread",
        legs=[
            SpreadLeg(symbol="SPY260410P00495000", strike_price=495.0, contract_type="put", side="sell", delta=-0.20),
            SpreadLeg(symbol="SPY260410P00490000", strike_price=490.0, contract_type="put", side="buy", delta=-0.10),
        ],
        expiration=date(2026, 4, 10), target_premium=1.50, profit_target_pct=50,
    )


def test_submit_spread_order(mock_trading_client, mock_db, exec_config, event_bus):
    executor = OrderExecutor(mock_trading_client, mock_db, exec_config, event_bus)
    signal = _make_signal()
    result = executor.submit_spread_order(signal)
    mock_trading_client.submit_order.assert_called_once()
    assert result is not None
    assert result.id == "order-123"


def test_submit_spread_uses_limit_order(mock_trading_client, mock_db, exec_config, event_bus):
    executor = OrderExecutor(mock_trading_client, mock_db, exec_config, event_bus)
    signal = _make_signal()
    executor.submit_spread_order(signal)
    call_args = mock_trading_client.submit_order.call_args
    order_data = call_args[0][0] if call_args[0] else call_args[1].get("order_data")
    assert order_data.order_class.value == "mleg"
    assert order_data.limit_price is not None


def test_submit_spread_has_correct_legs(mock_trading_client, mock_db, exec_config, event_bus):
    executor = OrderExecutor(mock_trading_client, mock_db, exec_config, event_bus)
    signal = _make_signal()
    executor.submit_spread_order(signal)
    call_args = mock_trading_client.submit_order.call_args
    order_data = call_args[0][0] if call_args[0] else call_args[1].get("order_data")
    assert len(order_data.legs) == 2


def test_submit_logs_to_db(mock_trading_client, mock_db, exec_config, event_bus):
    executor = OrderExecutor(mock_trading_client, mock_db, exec_config, event_bus)
    signal = _make_signal()
    executor.submit_spread_order(signal)
    mock_db.save_order_log.assert_called_once()


def test_publishes_order_filled_event(mock_trading_client, mock_db, exec_config, event_bus):
    received = []
    event_bus.subscribe("OrderFilled", lambda data: received.append(data))
    executor = OrderExecutor(mock_trading_client, mock_db, exec_config, event_bus)
    signal = _make_signal()
    executor.submit_spread_order(signal)
    assert len(received) == 1
    assert received[0]["order_id"] == "order-123"


def test_submit_close_order(mock_trading_client, mock_db, exec_config, event_bus):
    executor = OrderExecutor(mock_trading_client, mock_db, exec_config, event_bus)
    legs = [
        SpreadLeg("SPY260410P00495000", 495.0, "put", "sell", -0.20),
        SpreadLeg("SPY260410P00490000", 490.0, "put", "buy", -0.10),
    ]
    result = executor.submit_close_order(legs, limit_price=0.50)
    mock_trading_client.submit_order.assert_called_once()
    assert result is not None

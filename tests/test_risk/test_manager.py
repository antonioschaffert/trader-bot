from datetime import date
from unittest.mock import MagicMock

import pytest

from src.event_bus import EventBus
from src.risk.manager import RiskManager, ValidationResult
from src.signals.models import SpreadLeg, TradeSignal


@pytest.fixture
def risk_config():
    return {
        "max_concurrent_spreads": 10,
        "max_risk_per_trade_pct": 5,
        "max_buying_power_usage_pct": 60,
        "stop_loss_multiplier": 2.0,
        "roll_delta_threshold": 0.50,
        "dte_exit": 1,
        "daily_loss_limit": 1000,
        "daily_income_target": 500,
        "max_same_direction_per_symbol": 3,
        "max_portfolio_delta_per_symbol": 0.30,
    }


def _make_signal(symbol="SPY", spread_type="put_spread", premium=1.50):
    return TradeSignal(
        strategy_mode="swing", symbol=symbol, spread_type=spread_type,
        legs=[
            SpreadLeg(symbol=f"{symbol}260410P00495000", strike_price=495.0, contract_type="put", side="sell", delta=-0.20),
            SpreadLeg(symbol=f"{symbol}260410P00490000", strike_price=490.0, contract_type="put", side="buy", delta=-0.10),
        ],
        expiration=date(2026, 4, 10), target_premium=premium, profit_target_pct=50,
    )


@pytest.fixture
def mock_account():
    account = MagicMock()
    account.buying_power = 50000.0
    account.equity = 50000.0
    return account


def test_validate_signal_passes(risk_config, event_bus, mock_account):
    rm = RiskManager(risk_config, event_bus)
    signal = _make_signal()
    result = rm.validate_signal(signal, open_positions=[], account=mock_account, daily_pnl=0.0)
    assert result.approved is True


def test_reject_max_concurrent_spreads(risk_config, event_bus, mock_account):
    risk_config["max_concurrent_spreads"] = 2
    rm = RiskManager(risk_config, event_bus)
    signal = _make_signal()
    open_positions = [MagicMock() for _ in range(2)]
    result = rm.validate_signal(signal, open_positions=open_positions, account=mock_account, daily_pnl=0.0)
    assert result.approved is False
    assert "max concurrent" in result.reason.lower()


def test_reject_daily_loss_exceeded(risk_config, event_bus, mock_account):
    rm = RiskManager(risk_config, event_bus)
    signal = _make_signal()
    result = rm.validate_signal(signal, open_positions=[], account=mock_account, daily_pnl=-1100.0)
    assert result.approved is False
    assert "daily loss" in result.reason.lower()


def test_reject_daily_target_met(risk_config, event_bus, mock_account):
    rm = RiskManager(risk_config, event_bus)
    signal = _make_signal()
    result = rm.validate_signal(signal, open_positions=[], account=mock_account, daily_pnl=600.0)
    assert result.approved is False
    assert "daily target" in result.reason.lower()


def test_reject_max_same_direction(risk_config, event_bus, mock_account):
    risk_config["max_same_direction_per_symbol"] = 1
    rm = RiskManager(risk_config, event_bus)
    signal = _make_signal(spread_type="put_spread")
    existing = MagicMock()
    existing.symbol = "SPY"
    existing.spread_type = "put_spread"
    result = rm.validate_signal(signal, open_positions=[existing], account=mock_account, daily_pnl=0.0)
    assert result.approved is False


def test_reject_max_risk_per_trade(risk_config, event_bus, mock_account):
    rm = RiskManager(risk_config, event_bus)
    signal = _make_signal(premium=1.50)
    result = rm.validate_signal(signal, open_positions=[], account=mock_account, daily_pnl=0.0)
    assert result.approved is True
    mock_account.equity = 1000.0
    result = rm.validate_signal(signal, open_positions=[], account=mock_account, daily_pnl=0.0)
    assert result.approved is False


def test_check_profit_target():
    rm = RiskManager({}, EventBus())
    assert rm.check_profit_target(current_value=0.50, entry_premium=1.00, target_pct=50) is True
    assert rm.check_profit_target(current_value=0.80, entry_premium=1.00, target_pct=50) is False


def test_check_stop_loss():
    rm = RiskManager({"stop_loss_multiplier": 2.0}, EventBus())
    assert rm.check_stop_loss(current_value=3.50, entry_premium=1.00, multiplier=2.0) is True
    assert rm.check_stop_loss(current_value=1.50, entry_premium=1.00, multiplier=2.0) is False


def test_check_roll_needed():
    rm = RiskManager({"roll_delta_threshold": 0.50}, EventBus())
    assert rm.check_roll_needed(short_delta=0.55, threshold=0.50) is True
    assert rm.check_roll_needed(short_delta=0.30, threshold=0.50) is False

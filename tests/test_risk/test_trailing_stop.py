from src.event_bus import EventBus
from src.risk.manager import RiskManager


def _rm(**cfg):
    base = {
        "max_concurrent_spreads": 10, "max_risk_per_trade_pct": 5,
        "max_buying_power_usage_pct": 60, "stop_loss_multiplier": 2.0,
        "roll_delta_threshold": 0.5, "dte_exit": 1,
        "daily_loss_limit": 1000, "daily_income_target": 500,
        "max_same_direction_per_symbol": 3, "max_portfolio_delta_per_symbol": 0.30,
    }
    base.update(cfg)
    return RiskManager(base, EventBus())


def test_trailing_stop_disabled_when_activation_zero():
    rm = _rm(trailing_stop_activation_pct=0, trailing_stop_giveback_pct=50)
    # Even with a huge peak and big giveback, disabled means no trigger.
    assert rm.check_trailing_stop(current_value=0.8, entry_premium=1.0, peak_profit_pct=0.9) is False


def test_trailing_stop_not_triggered_before_activation():
    rm = _rm(trailing_stop_activation_pct=40, trailing_stop_giveback_pct=50)
    # Peak only 30% — under activation threshold of 40%.
    assert rm.check_trailing_stop(current_value=0.80, entry_premium=1.0, peak_profit_pct=0.30) is False


def test_trailing_stop_triggers_on_giveback():
    rm = _rm(trailing_stop_activation_pct=40, trailing_stop_giveback_pct=50)
    # Peak was 60% profit. Price now at 0.75 of entry -> profit_pct = 0.25.
    # trigger = peak * (1 - giveback) = 0.60 * 0.5 = 0.30. 0.25 <= 0.30 -> trigger.
    assert rm.check_trailing_stop(current_value=0.75, entry_premium=1.0, peak_profit_pct=0.60) is True


def test_trailing_stop_not_triggered_when_still_above_giveback():
    rm = _rm(trailing_stop_activation_pct=40, trailing_stop_giveback_pct=50)
    # Peak 60%, current profit ~40% (price 0.60). trigger = 0.30. 0.40 > 0.30, so no exit.
    assert rm.check_trailing_stop(current_value=0.60, entry_premium=1.0, peak_profit_pct=0.60) is False


def test_slippage_buffer_shrinks_sized_quantity():
    """With a bigger slippage buffer, risk-per-contract grows, so base_qty shrinks."""
    from datetime import date
    from src.signals.models import SpreadLeg, TradeSignal

    signal = TradeSignal(
        strategy_mode="swing", symbol="SPY", spread_type="put_spread",
        legs=[
            SpreadLeg(symbol="A", strike_price=495.0, contract_type="put", side="sell"),
            SpreadLeg(symbol="B", strike_price=490.0, contract_type="put", side="buy"),
        ],
        expiration=date(2026, 4, 10), target_premium=1.0, profit_target_pct=50,
        conviction_score=70.0,
    )
    rm_small = _rm(slippage_buffer_pct=0.0, max_contracts_per_trade=100)
    rm_big = _rm(slippage_buffer_pct=0.30, max_contracts_per_trade=100)
    q_small = rm_small._calculate_dynamic_quantity(signal, equity=50000)
    q_big = rm_big._calculate_dynamic_quantity(signal, equity=50000)
    assert q_big <= q_small

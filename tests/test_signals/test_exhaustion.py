from datetime import date, datetime, timezone, time as dtime

import pytest

from src.event_bus import EventBus
from src.market_data.models import (
    Bar, Indicators, MarketSnapshot, OptionContract, OptionsChain,
)
from src.signals.exhaustion import ExhaustionSignalGenerator
from src.signals.models import TradeSignal


@pytest.fixture
def exhaustion_config():
    return {
        "enabled": True,
        "target_dte": [1, 2],
        "spread_width": {"SPY": 5, "QQQ": 3},
        "min_premium": 0.25,
        "profit_target_pct": 20,
        "stop_loss_multiplier": 1.5,
        "time_window_start": "11:00",
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "intraday_timeframe": "5min",
        "min_signals_required": 2,
        "close_by_eod": True,
    }


def _make_call(strike, delta=0.20, bid=0.80, ask=1.00, oi=200):
    return OptionContract(
        symbol=f"SPY260401C{int(strike*1000):08d}",
        underlying_symbol="SPY",
        expiration_date=date(2026, 4, 1),
        strike_price=strike,
        contract_type="call",
        bid_price=bid,
        ask_price=ask,
        delta=delta,
        open_interest=oi,
        volume=50,
    )


def _make_put(strike, delta=-0.20, bid=0.80, ask=1.00, oi=200):
    return OptionContract(
        symbol=f"SPY260401P{int(strike*1000):08d}",
        underlying_symbol="SPY",
        expiration_date=date(2026, 4, 1),
        strike_price=strike,
        contract_type="put",
        bid_price=bid,
        ask_price=ask,
        delta=delta,
        open_interest=oi,
        volume=50,
    )


def _make_snapshot_upside_exhaustion():
    return MarketSnapshot(
        symbol="SPY",
        price=505.0,
        bars=[],
        options_chain=OptionsChain(
            underlying_symbol="SPY",
            calls=[
                _make_call(505.0, delta=0.50, bid=1.20, ask=1.40),
                _make_call(510.0, delta=0.30, bid=0.50, ask=0.70),
            ],
            puts=[],
        ),
        indicators=Indicators(),
        high_of_day=506.0,
        low_of_day=498.0,
        intraday_indicators=Indicators(
            rsi=75.0,
            vwap=500.0,
            upper_bollinger=505.5,
            lower_bollinger=496.0,
        ),
    )


def _make_snapshot_downside_exhaustion():
    return MarketSnapshot(
        symbol="SPY",
        price=495.0,
        bars=[],
        options_chain=OptionsChain(
            underlying_symbol="SPY",
            calls=[],
            puts=[
                _make_put(495.0, delta=-0.50, bid=1.20, ask=1.40),
                _make_put(490.0, delta=-0.30, bid=0.50, ask=0.70),
            ],
        ),
        indicators=Indicators(),
        high_of_day=502.0,
        low_of_day=494.0,
        intraday_indicators=Indicators(
            rsi=25.0,
            vwap=500.0,
            upper_bollinger=505.0,
            lower_bollinger=495.5,
        ),
    )


def test_upside_exhaustion_generates_call_spread(exhaustion_config, event_bus):
    snapshot = _make_snapshot_upside_exhaustion()
    gen = ExhaustionSignalGenerator(exhaustion_config, event_bus)
    signals = gen.evaluate(snapshot, current_time=dtime(11, 30))
    assert len(signals) == 1
    assert signals[0].spread_type == "call_spread"
    assert signals[0].strategy_mode == "exhaustion"
    assert signals[0].profit_target_pct == 20


def test_downside_exhaustion_generates_put_spread(exhaustion_config, event_bus):
    snapshot = _make_snapshot_downside_exhaustion()
    gen = ExhaustionSignalGenerator(exhaustion_config, event_bus)
    signals = gen.evaluate(snapshot, current_time=dtime(11, 30))
    assert len(signals) == 1
    assert signals[0].spread_type == "put_spread"


def test_no_signal_before_time_window(exhaustion_config, event_bus):
    snapshot = _make_snapshot_upside_exhaustion()
    gen = ExhaustionSignalGenerator(exhaustion_config, event_bus)
    signals = gen.evaluate(snapshot, current_time=dtime(10, 0))
    assert len(signals) == 0


def test_no_signal_when_disabled(exhaustion_config, event_bus):
    exhaustion_config["enabled"] = False
    snapshot = _make_snapshot_upside_exhaustion()
    gen = ExhaustionSignalGenerator(exhaustion_config, event_bus)
    signals = gen.evaluate(snapshot, current_time=dtime(11, 30))
    assert len(signals) == 0


def test_no_signal_insufficient_exhaustion_signals(exhaustion_config, event_bus):
    snapshot = MarketSnapshot(
        symbol="SPY",
        price=500.0,
        bars=[],
        options_chain=OptionsChain(underlying_symbol="SPY", calls=[], puts=[]),
        indicators=Indicators(),
        high_of_day=501.0,
        low_of_day=499.0,
        intraday_indicators=Indicators(
            rsi=50.0,
            vwap=500.0,
            upper_bollinger=510.0,
            lower_bollinger=490.0,
        ),
    )
    gen = ExhaustionSignalGenerator(exhaustion_config, event_bus)
    signals = gen.evaluate(snapshot, current_time=dtime(11, 30))
    assert len(signals) == 0

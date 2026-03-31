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
        "min_move_from_open_pct": 0.8,
        "strong_move_pct": 1.5,
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


def _make_intraday_bars_rally():
    """Simulate a morning rally that exhausts: big early bars, small late bars, declining volume."""
    base = datetime(2026, 3, 31, 14, 0, tzinfo=timezone.utc)
    bars = []
    # First 3 bars: strong move up, high volume
    for i in range(3):
        bars.append(Bar(
            timestamp=base,
            open=500.0 + i * 2.0,
            high=502.0 + i * 2.0,
            low=499.5 + i * 2.0,
            close=502.0 + i * 2.0,
            volume=500000 - i * 50000,
            vwap=501.0 + i * 2.0,
        ))
    # Last 3 bars: stalling, low volume, small ranges
    for i in range(3):
        bars.append(Bar(
            timestamp=base,
            open=506.0 + i * 0.1,
            high=506.2 + i * 0.1,
            low=505.8 + i * 0.1,
            close=506.0 + i * 0.1,
            volume=150000 - i * 10000,
            vwap=505.5,
        ))
    return bars


def _make_intraday_bars_selloff():
    """Simulate a morning selloff that exhausts."""
    base = datetime(2026, 3, 31, 14, 0, tzinfo=timezone.utc)
    bars = []
    # First 3: strong selling, high volume
    for i in range(3):
        bars.append(Bar(
            timestamp=base,
            open=500.0 - i * 2.0,
            high=500.5 - i * 2.0,
            low=498.0 - i * 2.0,
            close=498.0 - i * 2.0,
            volume=500000 - i * 50000,
            vwap=499.0 - i * 2.0,
        ))
    # Last 3: stalling, low volume
    for i in range(3):
        bars.append(Bar(
            timestamp=base,
            open=494.0 - i * 0.1,
            high=494.2 - i * 0.1,
            low=493.8 - i * 0.1,
            close=494.0 - i * 0.1,
            volume=150000 - i * 10000,
            vwap=494.5,
        ))
    return bars


def _make_snapshot_upside_exhaustion():
    """SPY rallied from 500 to 506 (+1.2%), RSI overbought, volume declining, momentum stalling."""
    return MarketSnapshot(
        symbol="SPY",
        price=506.0,
        bars=[],
        options_chain=OptionsChain(
            underlying_symbol="SPY",
            calls=[
                _make_call(506.0, delta=0.50, bid=1.20, ask=1.40),
                _make_call(511.0, delta=0.30, bid=0.50, ask=0.70),
            ],
            puts=[],
        ),
        indicators=Indicators(),
        high_of_day=506.2,
        low_of_day=499.5,
        open_price=500.0,
        prev_close=499.0,
        intraday_bars=_make_intraday_bars_rally(),
        intraday_indicators=Indicators(
            rsi=75.0,
            vwap=502.0,
            upper_bollinger=506.5,
            lower_bollinger=496.0,
        ),
    )


def _make_snapshot_downside_exhaustion():
    """SPY sold off from 500 to 494 (-1.2%), RSI oversold, volume declining."""
    return MarketSnapshot(
        symbol="SPY",
        price=494.0,
        bars=[],
        options_chain=OptionsChain(
            underlying_symbol="SPY",
            calls=[],
            puts=[
                _make_put(494.0, delta=-0.50, bid=1.20, ask=1.40),
                _make_put(489.0, delta=-0.30, bid=0.50, ask=0.70),
            ],
        ),
        indicators=Indicators(),
        high_of_day=500.5,
        low_of_day=493.8,
        open_price=500.0,
        prev_close=501.0,
        intraday_bars=_make_intraday_bars_selloff(),
        intraday_indicators=Indicators(
            rsi=25.0,
            vwap=497.0,
            upper_bollinger=505.0,
            lower_bollinger=494.5,
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
    """Neutral price, no move, RSI neutral — nothing to fade."""
    snapshot = MarketSnapshot(
        symbol="SPY",
        price=500.0,
        bars=[],
        options_chain=OptionsChain(underlying_symbol="SPY", calls=[], puts=[]),
        indicators=Indicators(),
        high_of_day=501.0,
        low_of_day=499.0,
        open_price=500.0,
        intraday_indicators=Indicators(
            rsi=50.0, vwap=500.0, upper_bollinger=510.0, lower_bollinger=490.0,
        ),
    )
    gen = ExhaustionSignalGenerator(exhaustion_config, event_bus)
    signals = gen.evaluate(snapshot, current_time=dtime(11, 30))
    assert len(signals) == 0


def test_no_signal_small_move(exhaustion_config, event_bus):
    """Move from open is only 0.3% — below 0.8% threshold, don't even check signals."""
    snapshot = MarketSnapshot(
        symbol="SPY",
        price=501.5,
        bars=[],
        options_chain=OptionsChain(underlying_symbol="SPY", calls=[], puts=[]),
        indicators=Indicators(),
        high_of_day=501.5,
        low_of_day=499.5,
        open_price=500.0,
        intraday_indicators=Indicators(rsi=75.0, vwap=500.0, upper_bollinger=502.0, lower_bollinger=498.0),
    )
    gen = ExhaustionSignalGenerator(exhaustion_config, event_bus)
    signals = gen.evaluate(snapshot, current_time=dtime(11, 30))
    assert len(signals) == 0


def test_volume_declining_detection(exhaustion_config, event_bus):
    """Verify volume declining is detected in the signal reasoning."""
    snapshot = _make_snapshot_upside_exhaustion()
    gen = ExhaustionSignalGenerator(exhaustion_config, event_bus)
    signals = gen.evaluate(snapshot, current_time=dtime(11, 30))
    assert len(signals) == 1
    reasoning = " ".join(signals[0].reasoning)
    assert "Volume declining: True" in reasoning


def test_reasoning_includes_move_from_open(exhaustion_config, event_bus):
    snapshot = _make_snapshot_upside_exhaustion()
    gen = ExhaustionSignalGenerator(exhaustion_config, event_bus)
    signals = gen.evaluate(snapshot, current_time=dtime(11, 30))
    assert len(signals) == 1
    reasoning = " ".join(signals[0].reasoning)
    assert "from open" in reasoning
    assert "500.00" in reasoning  # open price

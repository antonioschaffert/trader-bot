from datetime import date, datetime, timezone

import pytest

from src.event_bus import EventBus
from src.market_data.models import (
    Bar, Indicators, MarketSnapshot, OptionContract, OptionsChain,
)
from src.signals.models import TradeSignal
from src.signals.swing import SwingSignalGenerator


@pytest.fixture
def swing_config():
    return {
        "target_dte": [7, 10],
        "short_strike_delta": [0.15, 0.30],
        "spread_width": {"SPY": 5, "QQQ": 3},
        "min_premium": 0.50,
        "iv_rank_threshold": 30,
        "profit_target_pct": 50,
    }


def _make_put_contract(strike, delta, bid=1.50, ask=1.70, oi=500):
    return OptionContract(
        symbol=f"SPY260410P{int(strike*1000):08d}",
        underlying_symbol="SPY",
        expiration_date=date(2026, 4, 10),
        strike_price=strike,
        contract_type="put",
        bid_price=bid,
        ask_price=ask,
        delta=delta,
        open_interest=oi,
        volume=100,
    )


def _make_call_contract(strike, delta, bid=1.50, ask=1.70, oi=500):
    return OptionContract(
        symbol=f"SPY260410C{int(strike*1000):08d}",
        underlying_symbol="SPY",
        expiration_date=date(2026, 4, 10),
        strike_price=strike,
        contract_type="call",
        bid_price=bid,
        ask_price=ask,
        delta=delta,
        open_interest=oi,
        volume=100,
    )


def _make_snapshot(price, rsi, sma_50, iv_rank, puts=None, calls=None):
    return MarketSnapshot(
        symbol="SPY",
        price=price,
        bars=[],
        options_chain=OptionsChain(
            underlying_symbol="SPY",
            puts=puts or [],
            calls=calls or [],
        ),
        indicators=Indicators(rsi=rsi, sma_50=sma_50),
        iv_rank=iv_rank,
    )


def test_bullish_generates_put_spread(swing_config, event_bus):
    puts = [
        _make_put_contract(495.0, -0.20, bid=1.50, ask=1.70),
        _make_put_contract(490.0, -0.10, bid=0.60, ask=0.80),
    ]
    snapshot = _make_snapshot(price=500.0, rsi=55.0, sma_50=495.0, iv_rank=40.0, puts=puts)
    gen = SwingSignalGenerator(swing_config, event_bus)
    signals = gen.evaluate(snapshot)
    assert len(signals) >= 1
    signal = signals[0]
    assert signal.spread_type == "put_spread"
    assert signal.strategy_mode == "swing"
    assert signal.profit_target_pct == 50


def test_bearish_generates_call_spread(swing_config, event_bus):
    calls = [
        _make_call_contract(505.0, 0.20, bid=1.50, ask=1.70),
        _make_call_contract(510.0, 0.10, bid=0.60, ask=0.80),
    ]
    snapshot = _make_snapshot(price=490.0, rsi=45.0, sma_50=495.0, iv_rank=40.0, calls=calls)
    gen = SwingSignalGenerator(swing_config, event_bus)
    signals = gen.evaluate(snapshot)
    assert len(signals) >= 1
    assert signals[0].spread_type == "call_spread"


def test_low_iv_rank_no_signal(swing_config, event_bus):
    puts = [_make_put_contract(495.0, -0.20), _make_put_contract(490.0, -0.10)]
    snapshot = _make_snapshot(price=500.0, rsi=55.0, sma_50=495.0, iv_rank=20.0, puts=puts)
    gen = SwingSignalGenerator(swing_config, event_bus)
    signals = gen.evaluate(snapshot)
    assert len(signals) == 0


def test_signal_has_two_legs(swing_config, event_bus):
    puts = [
        _make_put_contract(495.0, -0.20, bid=1.50, ask=1.70),
        _make_put_contract(490.0, -0.10, bid=0.60, ask=0.80),
    ]
    snapshot = _make_snapshot(price=500.0, rsi=55.0, sma_50=495.0, iv_rank=40.0, puts=puts)
    gen = SwingSignalGenerator(swing_config, event_bus)
    signals = gen.evaluate(snapshot)
    assert len(signals[0].legs) == 2
    sides = {leg.side for leg in signals[0].legs}
    assert sides == {"sell", "buy"}


def test_min_premium_filter(swing_config, event_bus):
    puts = [
        _make_put_contract(495.0, -0.20, bid=0.20, ask=0.30),
        _make_put_contract(490.0, -0.10, bid=0.10, ask=0.15),
    ]
    snapshot = _make_snapshot(price=500.0, rsi=55.0, sma_50=495.0, iv_rank=40.0, puts=puts)
    gen = SwingSignalGenerator(swing_config, event_bus)
    signals = gen.evaluate(snapshot)
    assert len(signals) == 0

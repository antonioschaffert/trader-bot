from datetime import datetime, timedelta, timezone

import pytest

from src.market_data.indicators import compute_indicators, compute_iv_rank
from src.market_data.models import Bar, Indicators

_BASE_DATE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_bars(closes: list[float]) -> list[Bar]:
    return [
        Bar(
            timestamp=_BASE_DATE + timedelta(days=i),
            open=c - 0.5,
            high=c + 1.0,
            low=c - 1.0,
            close=c,
            volume=1000000,
            vwap=c,
        )
        for i, c in enumerate(closes)
    ]


def test_compute_indicators_returns_indicators():
    bars = _make_bars([100 + i * 0.5 for i in range(60)])
    result = compute_indicators(bars)
    assert isinstance(result, Indicators)


def test_compute_indicators_sma_50():
    closes = [100 + i * 0.5 for i in range(60)]
    bars = _make_bars(closes)
    result = compute_indicators(bars)
    assert result.sma_50 is not None
    assert result.sma_50 == pytest.approx(sum(closes[-50:]) / 50, abs=0.01)


def test_compute_indicators_rsi_not_none():
    bars = _make_bars([100 + i * 0.5 for i in range(60)])
    result = compute_indicators(bars)
    assert result.rsi is not None
    assert 0 <= result.rsi <= 100


def test_compute_indicators_bollinger_bands():
    bars = _make_bars([100 + i * 0.5 for i in range(60)])
    result = compute_indicators(bars)
    assert result.upper_bollinger is not None
    assert result.lower_bollinger is not None
    assert result.upper_bollinger > result.lower_bollinger


def test_compute_indicators_too_few_bars():
    bars = _make_bars([100, 101, 102])
    result = compute_indicators(bars)
    assert result.sma_50 is None


def test_compute_iv_rank():
    history = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45]
    rank = compute_iv_rank(0.30, history)
    assert rank == pytest.approx(50.0, abs=0.1)


def test_compute_iv_rank_at_low():
    history = [0.15, 0.20, 0.25, 0.30]
    rank = compute_iv_rank(0.15, history)
    assert rank == pytest.approx(0.0, abs=0.1)


def test_compute_iv_rank_empty_history():
    rank = compute_iv_rank(0.25, [])
    assert rank is None

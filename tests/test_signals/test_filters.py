from datetime import date

from src.market_data.models import OptionContract
from src.signals.filters import filter_liquid, passes_liquidity, realistic_net_credit


def _c(strike=100.0, bid=1.0, ask=1.10, oi=500, volume=50):
    return OptionContract(
        symbol=f"SPY260410P{int(strike*1000):08d}",
        underlying_symbol="SPY",
        expiration_date=date(2026, 4, 10),
        strike_price=strike,
        contract_type="put",
        bid_price=bid,
        ask_price=ask,
        open_interest=oi,
        volume=volume,
    )


def test_passes_liquidity_rejects_low_oi():
    c = _c(oi=50)
    assert passes_liquidity(c, min_open_interest=200) is False
    assert passes_liquidity(c, min_open_interest=10) is True


def test_passes_liquidity_rejects_wide_spread():
    # mid = 1.05, spread = 0.50, spread_pct ~ 0.48
    c = _c(bid=0.80, ask=1.30)
    assert passes_liquidity(c, max_spread_pct=0.25) is False
    assert passes_liquidity(c, max_spread_pct=0.60) is True


def test_passes_liquidity_accepts_tight_spread():
    c = _c(bid=1.00, ask=1.10)  # spread_pct ~ 9.5%
    assert passes_liquidity(c, max_spread_pct=0.25) is True


def test_filter_liquid_drops_bad_contracts():
    good = _c(bid=1.00, ask=1.05, oi=500)
    illiquid_oi = _c(bid=1.00, ask=1.05, oi=5)
    wide_spread = _c(bid=0.50, ask=2.00, oi=500)
    result = filter_liquid([good, illiquid_oi, wide_spread], min_open_interest=200, max_spread_pct=0.25)
    assert good in result
    assert illiquid_oi not in result
    assert wide_spread not in result


def test_realistic_net_credit_haircuts_mid():
    short = _c(bid=1.00, ask=1.50)  # mid=1.25, bid-weighted=1.125
    long = _c(bid=0.40, ask=0.60)   # mid=0.50,  ask-weighted=0.55
    raw_mid = short.mid_price - long.mid_price  # 0.75
    realistic = realistic_net_credit(short, long, slippage_pct=0.0)
    assert realistic < raw_mid
    assert realistic == short.bid_price * 0.75 + short.ask_price * 0.25 \
        - (long.bid_price * 0.25 + long.ask_price * 0.75)


def test_realistic_net_credit_applies_slippage():
    short = _c(bid=1.00, ask=1.50)
    long = _c(bid=0.40, ask=0.60)
    base = realistic_net_credit(short, long, slippage_pct=0.0)
    with_slip = realistic_net_credit(short, long, slippage_pct=0.10)
    assert abs(with_slip - base * 0.9) < 1e-9

"""
Shared option-contract filters used by signal generators.

These enforce minimum liquidity and maximum bid-ask spread so that
downstream premium math is executable, not theoretical.
"""

from src.market_data.models import OptionContract


def passes_liquidity(
    contract: OptionContract,
    min_open_interest: int = 0,
    max_spread_pct: float = 0.0,
    min_volume: int = 0,
) -> bool:
    """
    True if the contract meets the configured liquidity bar.

    - min_open_interest: reject if OI < threshold
    - max_spread_pct: reject if (ask-bid)/mid exceeds this fraction (e.g. 0.25 = 25%)
    - min_volume: reject if volume < threshold (0 disables)

    A non-positive max_spread_pct disables the spread filter.
    """
    if contract.mid_price <= 0:
        return False
    if min_open_interest > 0 and contract.open_interest < min_open_interest:
        return False
    if min_volume > 0 and contract.volume < min_volume:
        return False
    if max_spread_pct > 0 and contract.ask_price > 0 and contract.bid_price > 0:
        spread = contract.ask_price - contract.bid_price
        if spread < 0:
            return False
        mid = contract.mid_price
        if mid > 0 and (spread / mid) > max_spread_pct:
            return False
    return True


def filter_liquid(
    contracts: list[OptionContract],
    min_open_interest: int = 0,
    max_spread_pct: float = 0.0,
    min_volume: int = 0,
) -> list[OptionContract]:
    return [
        c for c in contracts
        if passes_liquidity(c, min_open_interest, max_spread_pct, min_volume)
    ]


def realistic_net_credit(
    short: OptionContract, long: OptionContract, slippage_pct: float = 0.0
) -> float:
    """
    Net credit assuming you cross half the bid-ask on each leg, then
    shave an additional slippage_pct.

    Short leg: sold at bid-side of mid (you'd prefer to sell at ask,
    but assume you give up half the spread).
    Long leg: bought at ask-side of mid (you give up half the spread).
    """
    short_fill = short.mid_price
    long_fill = long.mid_price
    # If quotes are available, apply half-spread haircut
    if short.bid_price > 0 and short.ask_price > 0:
        short_fill = (short.bid_price * 3 + short.ask_price) / 4  # closer to bid
    if long.bid_price > 0 and long.ask_price > 0:
        long_fill = (long.bid_price + long.ask_price * 3) / 4  # closer to ask
    net = short_fill - long_fill
    if slippage_pct > 0:
        net *= (1.0 - slippage_pct)
    return net

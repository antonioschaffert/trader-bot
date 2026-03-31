import logging

from src.event_bus import EventBus
from src.market_data.models import MarketSnapshot, OptionContract
from src.signals.models import SpreadLeg, TradeSignal

logger = logging.getLogger(__name__)


class SwingSignalGenerator:
    def __init__(self, config: dict, event_bus: EventBus):
        self._config = config
        self._bus = event_bus

    def evaluate(self, snapshot: MarketSnapshot) -> list[TradeSignal]:
        signals = []

        if snapshot.iv_rank is None or snapshot.iv_rank < self._config["iv_rank_threshold"]:
            return signals

        bias = self._get_bias(snapshot)

        if bias in ("bullish", "neutral"):
            signal = self._build_put_spread(snapshot)
            if signal:
                signals.append(signal)

        if bias in ("bearish", "neutral"):
            signal = self._build_call_spread(snapshot)
            if signal:
                signals.append(signal)

        return signals

    def _get_bias(self, snapshot: MarketSnapshot) -> str:
        ind = snapshot.indicators
        if ind.sma_50 is None or ind.rsi is None:
            return "neutral"

        above_sma = snapshot.price > ind.sma_50
        rsi = ind.rsi

        if above_sma and rsi < 70:
            return "bullish"
        elif not above_sma and rsi > 30:
            return "bearish"
        else:
            return "neutral"

    def _build_put_spread(self, snapshot: MarketSnapshot) -> TradeSignal | None:
        symbol = snapshot.symbol
        spread_width = self._config["spread_width"].get(symbol, 5)
        delta_range = self._config["short_strike_delta"]
        min_premium = self._config["min_premium"]

        short_put = self._find_short_strike(snapshot.options_chain.puts, delta_range)
        if not short_put:
            return None

        target_long_strike = short_put.strike_price - spread_width
        long_put = self._find_nearest_strike(snapshot.options_chain.puts, target_long_strike)
        if not long_put:
            return None

        net_credit = short_put.mid_price - long_put.mid_price
        if net_credit < min_premium:
            return None

        reasoning = [
            f"IV rank {snapshot.iv_rank:.0f}% above threshold {self._config['iv_rank_threshold']}%",
            f"Bullish bias: price {snapshot.price} above SMA50 {snapshot.indicators.sma_50:.2f}",
            f"Short {short_put.strike_price} put (delta {short_put.delta:.2f}), long {long_put.strike_price} put",
            f"Net credit: ${net_credit:.2f}",
        ]

        return TradeSignal(
            strategy_mode="swing",
            symbol=symbol,
            spread_type="put_spread",
            legs=[
                SpreadLeg(symbol=short_put.symbol, strike_price=short_put.strike_price, contract_type="put", side="sell", delta=short_put.delta),
                SpreadLeg(symbol=long_put.symbol, strike_price=long_put.strike_price, contract_type="put", side="buy", delta=long_put.delta),
            ],
            expiration=short_put.expiration_date,
            target_premium=net_credit,
            profit_target_pct=self._config["profit_target_pct"],
            reasoning=reasoning,
        )

    def _build_call_spread(self, snapshot: MarketSnapshot) -> TradeSignal | None:
        symbol = snapshot.symbol
        spread_width = self._config["spread_width"].get(symbol, 5)
        delta_range = self._config["short_strike_delta"]
        min_premium = self._config["min_premium"]

        short_call = self._find_short_strike(snapshot.options_chain.calls, delta_range)
        if not short_call:
            return None

        target_long_strike = short_call.strike_price + spread_width
        long_call = self._find_nearest_strike(snapshot.options_chain.calls, target_long_strike)
        if not long_call:
            return None

        net_credit = short_call.mid_price - long_call.mid_price
        if net_credit < min_premium:
            return None

        reasoning = [
            f"IV rank {snapshot.iv_rank:.0f}% above threshold {self._config['iv_rank_threshold']}%",
            f"Bearish bias: price {snapshot.price} below SMA50 {snapshot.indicators.sma_50:.2f}",
            f"Short {short_call.strike_price} call (delta {short_call.delta:.2f}), long {long_call.strike_price} call",
            f"Net credit: ${net_credit:.2f}",
        ]

        return TradeSignal(
            strategy_mode="swing",
            symbol=symbol,
            spread_type="call_spread",
            legs=[
                SpreadLeg(symbol=short_call.symbol, strike_price=short_call.strike_price, contract_type="call", side="sell", delta=short_call.delta),
                SpreadLeg(symbol=long_call.symbol, strike_price=long_call.strike_price, contract_type="call", side="buy", delta=long_call.delta),
            ],
            expiration=short_call.expiration_date,
            target_premium=net_credit,
            profit_target_pct=self._config["profit_target_pct"],
            reasoning=reasoning,
        )

    def _find_short_strike(self, contracts: list[OptionContract], delta_range: list[float]) -> OptionContract | None:
        min_delta, max_delta = delta_range
        candidates = [
            c for c in contracts
            if min_delta <= abs(c.delta) <= max_delta and c.open_interest > 0 and c.mid_price > 0
        ]
        if not candidates:
            return None
        target = (min_delta + max_delta) / 2
        return min(candidates, key=lambda c: abs(abs(c.delta) - target))

    def _find_nearest_strike(self, contracts: list[OptionContract], target_strike: float) -> OptionContract | None:
        if not contracts:
            return None
        return min(contracts, key=lambda c: abs(c.strike_price - target_strike))

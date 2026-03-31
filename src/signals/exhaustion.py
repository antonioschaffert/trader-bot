import logging
from datetime import datetime, time as dtime

from src.event_bus import EventBus
from src.market_data.models import MarketSnapshot, OptionContract
from src.signals.models import SpreadLeg, TradeSignal

logger = logging.getLogger(__name__)


class ExhaustionSignalGenerator:
    def __init__(self, config: dict, event_bus: EventBus):
        self._config = config
        self._bus = event_bus

    def evaluate(self, snapshot: MarketSnapshot, current_time: dtime | None = None) -> list[TradeSignal]:
        if not self._config.get("enabled", True):
            return []

        if current_time is None:
            current_time = datetime.now().time()

        window_start = dtime.fromisoformat(self._config["time_window_start"])
        if current_time < window_start:
            return []

        if snapshot.intraday_indicators is None:
            return []

        upside_signals = self._count_upside_exhaustion_signals(snapshot)
        downside_signals = self._count_downside_exhaustion_signals(snapshot)

        min_required = self._config["min_signals_required"]
        signals = []

        if upside_signals >= min_required:
            signal = self._build_call_spread(snapshot, upside_signals)
            if signal:
                signals.append(signal)

        if downside_signals >= min_required:
            signal = self._build_put_spread(snapshot, downside_signals)
            if signal:
                signals.append(signal)

        return signals

    def _count_upside_exhaustion_signals(self, snapshot: MarketSnapshot) -> int:
        ind = snapshot.intraday_indicators
        count = 0
        if ind.rsi is not None and ind.rsi > self._config["rsi_overbought"]:
            count += 1
        if ind.vwap is not None and snapshot.price > ind.vwap * 1.005:
            count += 1
        if ind.upper_bollinger is not None and snapshot.price >= ind.upper_bollinger * 0.998:
            count += 1
        if snapshot.high_of_day > 0 and snapshot.price >= snapshot.high_of_day * 0.998:
            count += 1
        return count

    def _count_downside_exhaustion_signals(self, snapshot: MarketSnapshot) -> int:
        ind = snapshot.intraday_indicators
        count = 0
        if ind.rsi is not None and ind.rsi < self._config["rsi_oversold"]:
            count += 1
        if ind.vwap is not None and snapshot.price < ind.vwap * 0.995:
            count += 1
        if ind.lower_bollinger is not None and snapshot.price <= ind.lower_bollinger * 1.002:
            count += 1
        if snapshot.low_of_day > 0 and snapshot.price <= snapshot.low_of_day * 1.002:
            count += 1
        return count

    def _build_call_spread(self, snapshot: MarketSnapshot, signal_count: int) -> TradeSignal | None:
        symbol = snapshot.symbol
        spread_width = self._config["spread_width"].get(symbol, 5)
        min_premium = self._config["min_premium"]

        target_short_strike = snapshot.price
        short_call = self._find_nearest_at_or_above(snapshot.options_chain.calls, target_short_strike)
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
            f"Upside exhaustion detected ({signal_count} signals)",
            f"Price {snapshot.price} near high of day {snapshot.high_of_day}",
            f"Intraday RSI: {snapshot.intraday_indicators.rsi:.0f}",
            f"Net credit: ${net_credit:.2f}",
        ]

        return TradeSignal(
            strategy_mode="exhaustion",
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

    def _build_put_spread(self, snapshot: MarketSnapshot, signal_count: int) -> TradeSignal | None:
        symbol = snapshot.symbol
        spread_width = self._config["spread_width"].get(symbol, 5)
        min_premium = self._config["min_premium"]

        target_short_strike = snapshot.price
        short_put = self._find_nearest_at_or_below(snapshot.options_chain.puts, target_short_strike)
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
            f"Downside exhaustion detected ({signal_count} signals)",
            f"Price {snapshot.price} near low of day {snapshot.low_of_day}",
            f"Intraday RSI: {snapshot.intraday_indicators.rsi:.0f}",
            f"Net credit: ${net_credit:.2f}",
        ]

        return TradeSignal(
            strategy_mode="exhaustion",
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

    def _find_nearest_at_or_above(self, contracts: list[OptionContract], target: float) -> OptionContract | None:
        above = [c for c in contracts if c.strike_price >= target and c.mid_price > 0]
        if not above:
            return None
        return min(above, key=lambda c: c.strike_price)

    def _find_nearest_at_or_below(self, contracts: list[OptionContract], target: float) -> OptionContract | None:
        below = [c for c in contracts if c.strike_price <= target and c.mid_price > 0]
        if not below:
            return None
        return max(below, key=lambda c: c.strike_price)

    def _find_nearest_strike(self, contracts: list[OptionContract], target: float) -> OptionContract | None:
        if not contracts:
            return None
        return min(contracts, key=lambda c: abs(c.strike_price - target))

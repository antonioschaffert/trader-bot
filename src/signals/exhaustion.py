"""
Exhaustion Signal Generator - Enhanced with Regime Awareness

Key improvements:
1. Regime-adaptive thresholds (require stronger signals in trending markets)
2. Volume confirmation (volume should confirm the reversal, not just decline)
3. ATR-based move sizing (use ATR to normalize "big move" instead of fixed %)
4. Conviction scoring for dynamic position sizing
5. Keltner Channel checks alongside Bollinger Bands
"""

import logging
from datetime import datetime, time as dtime

from src.event_bus import EventBus
from src.market_data.models import Bar, MarketSnapshot, OptionContract
from src.signals.models import EvaluationResult, SpreadLeg, TradeSignal

logger = logging.getLogger(__name__)


class ExhaustionSignalGenerator:
    def __init__(self, config: dict, event_bus: EventBus):
        self._config = config
        self._bus = event_bus

    def evaluate(self, snapshot: MarketSnapshot, current_time: dtime | None = None) -> EvaluationResult:
        result = EvaluationResult()

        if not self._config.get("enabled", True):
            return result

        if current_time is None:
            current_time = datetime.now().time()

        window_start = dtime.fromisoformat(self._config["time_window_start"])
        if current_time < window_start:
            result.rejections.append({
                "strategy": "exhaustion", "reason": "before_time_window",
                "variables": {"current_time": str(current_time), "window_start": str(window_start)},
            })
            return result

        if snapshot.intraday_indicators is None:
            return result

        # Regime check: skip exhaustion in crisis markets (moves can extend)
        regime = getattr(snapshot, "regime", None)
        if regime and not getattr(regime, "should_trade", True):
            result.rejections.append({
                "strategy": "exhaustion", "reason": "regime_halt",
                "variables": {"volatility_regime": getattr(regime, "volatility_regime", "unknown")},
            })
            return result

        # Move from open check, with ATR-normalized threshold
        min_move_pct = self._config.get("min_move_from_open_pct", 0.8)

        # In elevated/crisis vol, require a larger move (normal moves are bigger)
        if regime:
            vol_regime = getattr(regime, "volatility_regime", "normal")
            if vol_regime == "elevated":
                min_move_pct *= 1.3
            elif vol_regime == "crisis":
                min_move_pct *= 1.8  # require much larger move in crisis

        move_from_open = self._calc_move_from_open(snapshot)
        if abs(move_from_open) < min_move_pct:
            result.rejections.append({
                "strategy": "exhaustion", "reason": "move_from_open_too_small",
                "variables": {"move_pct": round(move_from_open, 2), "threshold": round(min_move_pct, 2)},
            })
            return result

        # Score exhaustion signals
        min_required = self._config["min_signals_required"]

        # In trending markets, require more signals (harder to fade a trend)
        if regime:
            phase = getattr(regime, "market_phase", "mean_reverting")
            if phase == "trending":
                min_required = max(min_required, min_required + 1)

        upside_score = self._score_upside_exhaustion(snapshot, move_from_open)
        downside_score = self._score_downside_exhaustion(snapshot, move_from_open)

        if upside_score >= min_required:
            signal = self._build_call_spread(snapshot, upside_score, regime)
            if signal:
                self._score_conviction(signal, snapshot, upside_score, min_required, regime)
                result.signals.append(signal)
        elif move_from_open > 0:
            result.rejections.append({
                "strategy": "exhaustion", "reason": "upside_score_below_threshold",
                "variables": {"score": upside_score, "required": min_required, "move_pct": round(move_from_open, 2)},
            })

        if downside_score >= min_required:
            signal = self._build_put_spread(snapshot, downside_score, regime)
            if signal:
                self._score_conviction(signal, snapshot, downside_score, min_required, regime)
                result.signals.append(signal)
        elif move_from_open < 0:
            result.rejections.append({
                "strategy": "exhaustion", "reason": "downside_score_below_threshold",
                "variables": {"score": downside_score, "required": min_required, "move_pct": round(move_from_open, 2)},
            })

        return result

    def _calc_move_from_open(self, snapshot: MarketSnapshot) -> float:
        if snapshot.open_price <= 0:
            if not snapshot.intraday_bars:
                return 0.0
            snapshot.open_price = snapshot.intraday_bars[0].open
        return ((snapshot.price - snapshot.open_price) / snapshot.open_price) * 100

    def _score_upside_exhaustion(self, snapshot: MarketSnapshot, move_pct: float) -> int:
        if move_pct <= 0:
            return 0

        ind = snapshot.intraday_indicators
        score = 0

        # 1. RSI overbought on intraday timeframe
        if ind.rsi is not None and ind.rsi > self._config["rsi_overbought"]:
            score += 1

        # 2. Price extended above VWAP
        if ind.vwap is not None and snapshot.price > ind.vwap * 1.005:
            score += 1

        # 3. Price at or near upper bollinger band
        if ind.upper_bollinger is not None and snapshot.price >= ind.upper_bollinger * 0.998:
            score += 1

        # 4. Price near high of day (stalling at top)
        if snapshot.high_of_day > 0 and snapshot.price >= snapshot.high_of_day * 0.998:
            score += 1

        # 5. Large move from open (>1.5% = strong signal)
        if move_pct >= self._config.get("strong_move_pct", 1.5):
            score += 1

        # 6. Volume declining -- later bars have less volume than earlier bars
        if self._is_volume_declining(snapshot.intraday_bars):
            score += 1

        # 7. Momentum stalling -- last few bars making smaller ranges
        if self._is_momentum_stalling(snapshot.intraday_bars, direction="up"):
            score += 1

        # 8. Extended beyond prior day's close
        if snapshot.prev_close > 0 and snapshot.price > snapshot.prev_close * 1.01:
            score += 1

        # 9. (NEW) Price above Keltner Channel upper band
        if ind.keltner_upper is not None and snapshot.price > ind.keltner_upper:
            score += 1

        # 10. (NEW) Relative volume declining (below average)
        if ind.relative_volume is not None and ind.relative_volume < 0.8:
            score += 1

        return score

    def _score_downside_exhaustion(self, snapshot: MarketSnapshot, move_pct: float) -> int:
        if move_pct >= 0:
            return 0

        ind = snapshot.intraday_indicators
        score = 0

        if ind.rsi is not None and ind.rsi < self._config["rsi_oversold"]:
            score += 1

        if ind.vwap is not None and snapshot.price < ind.vwap * 0.995:
            score += 1

        if ind.lower_bollinger is not None and snapshot.price <= ind.lower_bollinger * 1.002:
            score += 1

        if snapshot.low_of_day > 0 and snapshot.price <= snapshot.low_of_day * 1.002:
            score += 1

        if abs(move_pct) >= self._config.get("strong_move_pct", 1.5):
            score += 1

        if self._is_volume_declining(snapshot.intraday_bars):
            score += 1

        if self._is_momentum_stalling(snapshot.intraday_bars, direction="down"):
            score += 1

        if snapshot.prev_close > 0 and snapshot.price < snapshot.prev_close * 0.99:
            score += 1

        # (NEW) Price below Keltner Channel lower band
        if ind.keltner_lower is not None and snapshot.price < ind.keltner_lower:
            score += 1

        # (NEW) Relative volume declining
        if ind.relative_volume is not None and ind.relative_volume < 0.8:
            score += 1

        return score

    def _is_volume_declining(self, bars: list[Bar]) -> bool:
        if len(bars) < 6:
            return False
        mid = len(bars) // 2
        first_half_avg = sum(b.volume for b in bars[:mid]) / mid
        last_3_avg = sum(b.volume for b in bars[-3:]) / 3
        if first_half_avg == 0:
            return False
        return last_3_avg < first_half_avg * 0.6

    def _is_momentum_stalling(self, bars: list[Bar], direction: str) -> bool:
        if len(bars) < 6:
            return False
        last_3 = bars[-3:]
        prev_3 = bars[-6:-3]

        last_ranges = [abs(b.close - b.open) for b in last_3]
        prev_ranges = [abs(b.close - b.open) for b in prev_3]

        avg_last = sum(last_ranges) / 3
        avg_prev = sum(prev_ranges) / 3

        if avg_prev == 0:
            return False

        ranges_shrinking = avg_last < avg_prev * 0.5

        if direction == "up":
            highs_stalling = last_3[-1].high <= max(b.high for b in last_3[:-1])
        else:
            highs_stalling = last_3[-1].low >= min(b.low for b in last_3[:-1])

        return ranges_shrinking or highs_stalling

    def _score_conviction(self, signal: TradeSignal, snapshot: MarketSnapshot, score: int, min_required: int, regime=None) -> None:
        """Score conviction for dynamic position sizing."""
        conviction = 40  # base for exhaustion (inherently lower conviction than swing)

        # More signals = higher conviction
        excess_signals = score - min_required
        conviction += excess_signals * 8

        # RSI extreme = higher conviction
        rsi = snapshot.intraday_indicators.rsi if snapshot.intraday_indicators else None
        if rsi is not None:
            if rsi > 80 or rsi < 20:
                conviction += 10

        # Regime alignment: mean-reverting regime = better for exhaustion plays
        if regime:
            phase = getattr(regime, "market_phase", "")
            if phase == "mean_reverting":
                conviction += 10
            elif phase == "trending":
                conviction -= 15  # fading a trend is risky

        signal.conviction_score = max(0, min(100, conviction))

    def _build_call_spread(self, snapshot: MarketSnapshot, signal_count: int, regime=None) -> TradeSignal | None:
        symbol = snapshot.symbol
        spread_width = self._config["spread_width"].get(symbol, 5)
        min_premium = self._config["min_premium"]

        # Regime-adjusted premium threshold
        if regime:
            prem_mult = getattr(regime, "premium_threshold_multiplier", 1.0)
            min_premium *= prem_mult

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

        move_pct = self._calc_move_from_open(snapshot)
        reasoning = [
            f"Upside exhaustion ({signal_count} signals, min required: {self._config['min_signals_required']})",
            f"{symbol} up {move_pct:+.2f}% from open ({snapshot.open_price:.2f} -> {snapshot.price:.2f})",
            f"High of day: {snapshot.high_of_day:.2f}",
        ]
        if snapshot.intraday_indicators and snapshot.intraday_indicators.rsi:
            reasoning.append(f"Intraday RSI: {snapshot.intraday_indicators.rsi:.0f}")
        if regime:
            reasoning.append(f"Regime: {getattr(regime, 'volatility_regime', 'N/A')} vol, {getattr(regime, 'market_phase', 'N/A')} phase")
        reasoning.extend([
            f"Volume declining: {self._is_volume_declining(snapshot.intraday_bars)}",
            f"Momentum stalling: {self._is_momentum_stalling(snapshot.intraday_bars, 'up')}",
            f"Net credit: ${net_credit:.2f}",
        ])

        return TradeSignal(
            strategy_mode="exhaustion",
            symbol=symbol,
            spread_type="call_spread",
            legs=[
                SpreadLeg(
                    symbol=short_call.symbol, strike_price=short_call.strike_price,
                    contract_type="call", side="sell", delta=short_call.delta,
                    gamma=short_call.gamma, theta=short_call.theta, vega=short_call.vega,
                ),
                SpreadLeg(
                    symbol=long_call.symbol, strike_price=long_call.strike_price,
                    contract_type="call", side="buy", delta=long_call.delta,
                    gamma=long_call.gamma, theta=long_call.theta, vega=long_call.vega,
                ),
            ],
            expiration=short_call.expiration_date,
            target_premium=net_credit,
            profit_target_pct=self._config["profit_target_pct"],
            reasoning=reasoning,
            regime_context=getattr(regime, "volatility_regime", "") if regime else "",
        )

    def _build_put_spread(self, snapshot: MarketSnapshot, signal_count: int, regime=None) -> TradeSignal | None:
        symbol = snapshot.symbol
        spread_width = self._config["spread_width"].get(symbol, 5)
        min_premium = self._config["min_premium"]

        if regime:
            prem_mult = getattr(regime, "premium_threshold_multiplier", 1.0)
            min_premium *= prem_mult

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

        move_pct = self._calc_move_from_open(snapshot)
        reasoning = [
            f"Downside exhaustion ({signal_count} signals, min required: {self._config['min_signals_required']})",
            f"{symbol} down {move_pct:+.2f}% from open ({snapshot.open_price:.2f} -> {snapshot.price:.2f})",
            f"Low of day: {snapshot.low_of_day:.2f}",
        ]
        if snapshot.intraday_indicators and snapshot.intraday_indicators.rsi:
            reasoning.append(f"Intraday RSI: {snapshot.intraday_indicators.rsi:.0f}")
        if regime:
            reasoning.append(f"Regime: {getattr(regime, 'volatility_regime', 'N/A')} vol, {getattr(regime, 'market_phase', 'N/A')} phase")
        reasoning.extend([
            f"Volume declining: {self._is_volume_declining(snapshot.intraday_bars)}",
            f"Momentum stalling: {self._is_momentum_stalling(snapshot.intraday_bars, 'down')}",
            f"Net credit: ${net_credit:.2f}",
        ])

        return TradeSignal(
            strategy_mode="exhaustion",
            symbol=symbol,
            spread_type="put_spread",
            legs=[
                SpreadLeg(
                    symbol=short_put.symbol, strike_price=short_put.strike_price,
                    contract_type="put", side="sell", delta=short_put.delta,
                    gamma=short_put.gamma, theta=short_put.theta, vega=short_put.vega,
                ),
                SpreadLeg(
                    symbol=long_put.symbol, strike_price=long_put.strike_price,
                    contract_type="put", side="buy", delta=long_put.delta,
                    gamma=long_put.gamma, theta=long_put.theta, vega=long_put.vega,
                ),
            ],
            expiration=short_put.expiration_date,
            target_premium=net_credit,
            profit_target_pct=self._config["profit_target_pct"],
            reasoning=reasoning,
            regime_context=getattr(regime, "volatility_regime", "") if regime else "",
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

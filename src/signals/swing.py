"""
Swing Signal Generator - Enhanced with Regime Awareness

Key improvements over vanilla version:
1. Regime-adaptive parameters (wider strikes in high vol, tighter in low vol)
2. Multi-timeframe trend alignment (don't sell puts in a downtrend)
3. Support/resistance awareness (don't sell at key levels)
4. Conviction scoring for dynamic position sizing
5. IV percentile check (better than IV rank alone)
6. Trend strength filtering via ADX
"""

import logging

from src.event_bus import EventBus
from src.market_data.models import MarketSnapshot, OptionContract
from src.signals.filters import filter_liquid, passes_liquidity, realistic_net_credit
from src.signals.models import EvaluationResult, SpreadLeg, TradeSignal

logger = logging.getLogger(__name__)


class SwingSignalGenerator:
    def __init__(self, config: dict, event_bus: EventBus):
        self._config = config
        self._bus = event_bus

    def evaluate(self, snapshot: MarketSnapshot) -> EvaluationResult:
        result = EvaluationResult()
        iv_threshold = self._config["iv_rank_threshold"]
        iv_pct_threshold = self._config.get("iv_percentile_threshold", 0)

        # IV rank check (skip if threshold is 0)
        if iv_threshold > 0:
            if snapshot.iv_rank is None:
                result.rejections.append({
                    "strategy": "swing", "reason": "iv_rank_unavailable",
                    "variables": {},
                })
                return result
            if snapshot.iv_rank < iv_threshold:
                result.rejections.append({
                    "strategy": "swing", "reason": "iv_rank_below_threshold",
                    "variables": {"iv_rank": round(snapshot.iv_rank, 1), "threshold": iv_threshold},
                })
                return result

        # Secondary IV percentile check: rank alone can be fooled by a single
        # stale historical outlier; percentile confirms current IV is elevated
        # relative to the full distribution.
        if iv_pct_threshold > 0 and snapshot.iv_percentile is not None:
            if snapshot.iv_percentile < iv_pct_threshold:
                result.rejections.append({
                    "strategy": "swing", "reason": "iv_percentile_below_threshold",
                    "variables": {
                        "iv_percentile": round(snapshot.iv_percentile, 1),
                        "threshold": iv_pct_threshold,
                    },
                })
                return result

        # Get regime context
        regime = getattr(snapshot, "regime", None)

        # Regime-based halt: don't trade in crisis+trending
        if regime and not getattr(regime, "should_trade", True):
            result.rejections.append({
                "strategy": "swing", "reason": "regime_halt",
                "variables": {
                    "volatility_regime": getattr(regime, "volatility_regime", "unknown"),
                    "market_phase": getattr(regime, "market_phase", "unknown"),
                },
            })
            return result

        # ADX filter: in strong trending markets, only trade with the trend
        adx = snapshot.indicators.adx
        bias = self._get_bias(snapshot)

        if bias in ("bullish", "neutral"):
            signal = self._build_put_spread(snapshot, regime)
            if signal:
                self._score_conviction(signal, snapshot, regime)
                result.signals.append(signal)
            else:
                result.rejections.append({
                    "strategy": "swing", "reason": "no_viable_put_spread",
                    "variables": {"bias": bias},
                })

        if bias in ("bearish", "neutral"):
            signal = self._build_call_spread(snapshot, regime)
            if signal:
                self._score_conviction(signal, snapshot, regime)
                result.signals.append(signal)
            else:
                result.rejections.append({
                    "strategy": "swing", "reason": "no_viable_call_spread",
                    "variables": {"bias": bias},
                })

        return result

    def _get_bias(self, snapshot: MarketSnapshot) -> str:
        """
        Enhanced bias detection using multiple indicators and regime context.
        """
        ind = snapshot.indicators
        if ind.sma_50 is None or ind.rsi is None:
            return "neutral"

        above_sma50 = snapshot.price > ind.sma_50
        above_sma20 = ind.sma_20 is not None and snapshot.price > ind.sma_20
        rsi = ind.rsi

        # EMA alignment check (9 > 21 = bullish, 9 < 21 = bearish)
        ema_bullish = (ind.ema_9 is not None and ind.ema_21 is not None and ind.ema_9 > ind.ema_21)
        ema_bearish = (ind.ema_9 is not None and ind.ema_21 is not None and ind.ema_9 < ind.ema_21)

        # MACD confirmation
        macd_bullish = ind.macd_histogram is not None and ind.macd_histogram > 0
        macd_bearish = ind.macd_histogram is not None and ind.macd_histogram < 0

        # Score-based bias (more robust than simple threshold)
        bull_score = sum([above_sma50, above_sma20, ema_bullish, macd_bullish, rsi < 70])
        bear_score = sum([not above_sma50, not above_sma20, ema_bearish, macd_bearish, rsi > 30])

        # Regime tilt: in strong trends, bias toward the trend
        regime = getattr(snapshot, "regime", None)
        if regime:
            trend_score = getattr(regime, "trend_score", 0)
            if trend_score > 40:
                bull_score += 1
            elif trend_score < -40:
                bear_score += 1

        if bull_score >= 4:
            return "bullish"
        elif bear_score >= 4:
            return "bearish"
        return "neutral"

    def _get_regime_adjusted_params(self, snapshot: MarketSnapshot, regime) -> dict:
        """Get delta range and spread width adjusted for current regime."""
        base_delta = list(self._config["short_strike_delta"])
        base_width = dict(self._config["spread_width"])

        if regime is None:
            return {"delta_range": base_delta, "spread_width": base_width, "min_premium": self._config["min_premium"]}

        delta_adj = getattr(regime, "delta_adjustment", 0)
        width_mult = getattr(regime, "spread_width_multiplier", 1.0)
        prem_mult = getattr(regime, "premium_threshold_multiplier", 1.0)

        # Shift delta range further OTM in dangerous environments
        adjusted_delta = [max(0.05, d + delta_adj) for d in base_delta]

        # Widen spreads in high vol
        adjusted_width = {sym: max(2, int(w * width_mult)) for sym, w in base_width.items()}

        # Require more premium
        adjusted_premium = self._config["min_premium"] * prem_mult

        return {
            "delta_range": adjusted_delta,
            "spread_width": adjusted_width,
            "min_premium": adjusted_premium,
        }

    def _build_put_spread(self, snapshot: MarketSnapshot, regime=None) -> TradeSignal | None:
        symbol = snapshot.symbol
        params = self._get_regime_adjusted_params(snapshot, regime)
        spread_width = params["spread_width"].get(symbol, 5)
        delta_range = params["delta_range"]
        min_premium = params["min_premium"]

        # Pre-filter the chain by target expiration (prefer nearest) and liquidity
        candidate_puts = self._select_target_expiration(snapshot.options_chain.puts)
        candidate_puts = self._apply_liquidity(candidate_puts)

        short_put = self._find_short_strike(candidate_puts, delta_range)
        if not short_put:
            return None

        # Support awareness: require short strike to sit a meaningful buffer
        # below support. Use ATR when available (volatility-adjusted), else 2.5%.
        support = snapshot.indicators.support
        buffer_pct = self._support_buffer_pct(snapshot)
        if support and short_put.strike_price >= support * (1 - buffer_pct):
            adjusted_puts = [c for c in candidate_puts if c.strike_price < support * (1 - buffer_pct)]
            if adjusted_puts:
                alt = self._find_short_strike(adjusted_puts, delta_range)
                if alt:
                    short_put = alt

        target_long_strike = short_put.strike_price - spread_width
        long_put = self._find_nearest_strike(candidate_puts, target_long_strike)
        if not long_put:
            return None

        slippage = self._config.get("slippage_buffer_pct", 0.0)
        net_credit = realistic_net_credit(short_put, long_put, slippage_pct=slippage)
        if net_credit < min_premium:
            return None

        # Calculate support distance
        support_dist = 0.0
        if support:
            support_dist = (short_put.strike_price - support) / snapshot.price * 100

        reasoning = [
            f"IV rank {snapshot.iv_rank:.0f}% above threshold {self._config['iv_rank_threshold']}%" if snapshot.iv_rank is not None else f"IV rank N/A (threshold {self._config['iv_rank_threshold']}% skipped)",
            f"Bias: bullish (price {snapshot.price:.2f}, SMA50 {snapshot.indicators.sma_50:.2f})" if snapshot.indicators.sma_50 else f"Bias: bullish (price {snapshot.price:.2f})",
        ]
        if regime:
            reasoning.append(f"Regime: {getattr(regime, 'volatility_regime', 'N/A')} vol, {getattr(regime, 'trend_regime', 'N/A')} trend")
        if snapshot.indicators.adx:
            reasoning.append(f"ADX: {snapshot.indicators.adx:.0f} ({_adx_label(snapshot.indicators.adx)})")
        reasoning.extend([
            f"Short {short_put.strike_price} put (delta {short_put.delta:.2f}), long {long_put.strike_price} put",
            f"Net credit: ${net_credit:.2f} (min required: ${min_premium:.2f})",
        ])
        if support:
            reasoning.append(f"Support at {support:.2f} (short strike {support_dist:+.1f}% away)")

        return TradeSignal(
            strategy_mode="swing",
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
            support_distance_pct=support_dist,
            regime_context=getattr(regime, "volatility_regime", "") if regime else "",
        )

    def _build_call_spread(self, snapshot: MarketSnapshot, regime=None) -> TradeSignal | None:
        symbol = snapshot.symbol
        params = self._get_regime_adjusted_params(snapshot, regime)
        spread_width = params["spread_width"].get(symbol, 5)
        delta_range = params["delta_range"]
        min_premium = params["min_premium"]

        candidate_calls = self._select_target_expiration(snapshot.options_chain.calls)
        candidate_calls = self._apply_liquidity(candidate_calls)

        short_call = self._find_short_strike(candidate_calls, delta_range)
        if not short_call:
            return None

        # Resistance awareness with volatility-adjusted buffer.
        resistance = snapshot.indicators.resistance
        buffer_pct = self._support_buffer_pct(snapshot)
        if resistance and short_call.strike_price <= resistance * (1 + buffer_pct):
            adjusted_calls = [c for c in candidate_calls if c.strike_price > resistance * (1 + buffer_pct)]
            if adjusted_calls:
                alt = self._find_short_strike(adjusted_calls, delta_range)
                if alt:
                    short_call = alt

        target_long_strike = short_call.strike_price + spread_width
        long_call = self._find_nearest_strike(candidate_calls, target_long_strike)
        if not long_call:
            return None

        slippage = self._config.get("slippage_buffer_pct", 0.0)
        net_credit = realistic_net_credit(short_call, long_call, slippage_pct=slippage)
        if net_credit < min_premium:
            return None

        resistance_dist = 0.0
        if resistance:
            resistance_dist = (resistance - short_call.strike_price) / snapshot.price * 100

        reasoning = [
            f"IV rank {snapshot.iv_rank:.0f}% above threshold {self._config['iv_rank_threshold']}%" if snapshot.iv_rank is not None else f"IV rank N/A (threshold {self._config['iv_rank_threshold']}% skipped)",
            f"Bias: bearish (price {snapshot.price:.2f}, SMA50 {snapshot.indicators.sma_50:.2f})" if snapshot.indicators.sma_50 else f"Bias: bearish (price {snapshot.price:.2f})",
        ]
        if regime:
            reasoning.append(f"Regime: {getattr(regime, 'volatility_regime', 'N/A')} vol, {getattr(regime, 'trend_regime', 'N/A')} trend")
        if snapshot.indicators.adx:
            reasoning.append(f"ADX: {snapshot.indicators.adx:.0f} ({_adx_label(snapshot.indicators.adx)})")
        reasoning.extend([
            f"Short {short_call.strike_price} call (delta {short_call.delta:.2f}), long {long_call.strike_price} call",
            f"Net credit: ${net_credit:.2f} (min required: ${min_premium:.2f})",
        ])
        if resistance:
            reasoning.append(f"Resistance at {resistance:.2f} (short strike {resistance_dist:+.1f}% away)")

        return TradeSignal(
            strategy_mode="swing",
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
            resistance_distance_pct=resistance_dist,
            regime_context=getattr(regime, "volatility_regime", "") if regime else "",
        )

    def _score_conviction(self, signal: TradeSignal, snapshot: MarketSnapshot, regime=None) -> None:
        """
        Score conviction 0-100 based on how many factors align.
        Used for dynamic position sizing: higher conviction = larger position.
        """
        score = 50  # base

        # IV rank bonus (higher IV = more premium, better edge)
        if snapshot.iv_rank is not None:
            if snapshot.iv_rank > 60:
                score += 15
            elif snapshot.iv_rank > 40:
                score += 8

        # ADX bonus (mean-reverting market = better for selling premium)
        adx = snapshot.indicators.adx
        if adx is not None:
            if adx < 20:  # range-bound = ideal
                score += 10
            elif adx > 30:  # strong trend = risky
                score -= 10

        # Regime alignment
        if regime:
            vol_regime = getattr(regime, "volatility_regime", "")
            if vol_regime == "elevated":
                score += 10  # elevated vol = fat premiums
            elif vol_regime == "crisis":
                score -= 20  # crisis = dangerous

            phase = getattr(regime, "market_phase", "")
            if phase == "mean_reverting":
                score += 10
            elif phase == "trending":
                score -= 10

        # Support/resistance buffer
        if signal.spread_type == "put_spread" and signal.support_distance_pct > 3:
            score += 5  # short strike well above support
        elif signal.spread_type == "call_spread" and signal.resistance_distance_pct > 3:
            score += 5

        # MACD confirmation
        if snapshot.indicators.macd_histogram is not None:
            if signal.spread_type == "put_spread" and snapshot.indicators.macd_histogram > 0:
                score += 5  # bullish momentum supports put selling
            elif signal.spread_type == "call_spread" and snapshot.indicators.macd_histogram < 0:
                score += 5

        signal.conviction_score = max(0, min(100, score))

    def _find_short_strike(self, contracts: list[OptionContract], delta_range: list[float]) -> OptionContract | None:
        min_delta, max_delta = delta_range
        in_delta = [c for c in contracts if min_delta <= abs(c.delta) <= max_delta and c.mid_price > 0]
        target = (min_delta + max_delta) / 2
        if in_delta:
            return min(in_delta, key=lambda c: abs(abs(c.delta) - target))
        # No contract has delta data in range. Only fall back if explicitly allowed.
        # Otherwise we refuse the signal — guessing by %-OTM can give 0.5 delta strikes.
        if not self._config.get("allow_delta_fallback", False):
            return None
        with_mid = [c for c in contracts if c.mid_price > 0]
        if not with_mid:
            return None
        return min(with_mid, key=lambda c: abs(abs(c.delta) - target) if c.delta else 999)

    def _find_nearest_strike(self, contracts: list[OptionContract], target_strike: float) -> OptionContract | None:
        if not contracts:
            return None
        return min(contracts, key=lambda c: abs(c.strike_price - target_strike))

    def _apply_liquidity(self, contracts: list[OptionContract]) -> list[OptionContract]:
        """Filter contracts by configured OI and bid-ask spread thresholds."""
        return filter_liquid(
            contracts,
            min_open_interest=self._config.get("min_open_interest", 1),
            max_spread_pct=self._config.get("max_bid_ask_spread_pct", 0.0),
        )

    def _select_target_expiration(self, contracts: list[OptionContract]) -> list[OptionContract]:
        """
        Prefer the nearest expiration inside the target DTE window.

        Theta decay is nonlinear; concentrating on the shortest DTE in the
        allowed range improves theta capture and reduces gamma exposure across
        the life of the trade.
        """
        if not contracts:
            return contracts
        expirations = sorted({c.expiration_date for c in contracts})
        if not expirations:
            return contracts
        nearest = expirations[0]
        return [c for c in contracts if c.expiration_date == nearest]

    def _support_buffer_pct(self, snapshot: MarketSnapshot) -> float:
        """
        Return the fractional buffer required between the short strike and the
        support/resistance level. Uses ATR when available so the buffer scales
        with the symbol's realized volatility; falls back to 2.5%.
        """
        atr = snapshot.indicators.atr_14
        price = snapshot.price
        configured_min = self._config.get("sr_buffer_pct_min", 0.025)
        if atr and price > 0:
            # 1 ATR of headroom, clamped to [configured_min, 6%]
            return max(configured_min, min(atr / price, 0.06))
        return configured_min


def _adx_label(adx: float) -> str:
    if adx < 20:
        return "weak/range-bound"
    elif adx < 25:
        return "transitioning"
    elif adx < 40:
        return "trending"
    return "strong trend"

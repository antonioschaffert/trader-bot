"""
Wheel Signal Generator - Options Wheel Strategy (Third Strategy)

The wheel strategy cycles through:
1. Sell Cash-Secured Puts (CSPs) to collect premium
2. If assigned, hold shares and sell Covered Calls (CCs)
3. If called away, return to step 1

Parameters follow the Alpaca wheel strategy guide:
- CSP delta: -0.42 to -0.18 (OTM puts)
- CC delta: 0.18 to 0.42 (OTM calls)
- DTE: 14-35 days
- Open interest >= 200
- CSP strike within 5% of current price
- CC strike above upper Bollinger Band
- Max 10% of buying power per position

Rolling triggers:
- Delta >= 2x entry delta
- Option price <= 50% of entry premium (profit target)
"""

import logging

from src.event_bus import EventBus
from src.market_data.models import MarketSnapshot, OptionContract
from src.signals.models import EvaluationResult, WheelSignal
from src.signals.wheel_state import WheelStateManager

logger = logging.getLogger(__name__)


class WheelSignalGenerator:
    def __init__(self, config: dict, event_bus: EventBus, wheel_state: WheelStateManager):
        self._config = config
        self._bus = event_bus
        self._state = wheel_state

    def evaluate(self, snapshot: MarketSnapshot, account) -> EvaluationResult:
        """
        Evaluate the wheel strategy for a symbol based on its current phase.

        Returns EvaluationResult with wheel_signals (not spread signals).
        """
        result = EvaluationResult()
        symbol = snapshot.symbol

        if not self._config.get("enabled", False):
            return result

        # Regime halt check
        regime = getattr(snapshot, "regime", None)
        if regime and not getattr(regime, "should_trade", True):
            result.rejections.append({
                "strategy": "wheel",
                "reason": "regime_halt",
                "variables": {
                    "volatility_regime": str(getattr(regime, "volatility_regime", "unknown")),
                    "market_phase": str(getattr(regime, "market_phase", "unknown")),
                },
            })
            return result

        position = self._state.get_position(symbol)

        if position.phase == "idle":
            # Check if we can start a new CSP
            max_positions = self._config.get("max_positions", 2)
            active = len(self._state.get_active_positions())
            if active >= max_positions:
                result.rejections.append({
                    "strategy": "wheel", "reason": "max_wheel_positions_reached",
                    "variables": {"active": active, "max": max_positions},
                })
                return result

            signal = self._evaluate_csp(snapshot, position, account)
            if signal:
                self._score_conviction(signal, snapshot, regime)
                result.wheel_signals.append(signal)
            else:
                result.rejections.append({
                    "strategy": "wheel", "reason": "no_viable_csp",
                    "variables": {"symbol": symbol, "phase": "idle"},
                })

        elif position.phase == "holding_shares":
            signal = self._evaluate_covered_call(snapshot, position, account)
            if signal:
                self._score_conviction(signal, snapshot, regime)
                result.wheel_signals.append(signal)
            else:
                result.rejections.append({
                    "strategy": "wheel", "reason": "no_viable_covered_call",
                    "variables": {"symbol": symbol, "shares": position.shares_held},
                })

        elif position.phase in ("selling_csp", "selling_cc"):
            # Already have an active option, nothing to do in evaluation
            pass

        return result

    def _evaluate_csp(self, snapshot: MarketSnapshot, position, account) -> WheelSignal | None:
        """Find and return a cash-secured put signal."""
        symbol = snapshot.symbol
        equity = float(getattr(account, "equity", 0))
        if equity <= 0:
            return None

        # Buying power check: need enough to buy 100 shares at strike
        max_bp_pct = self._config.get("max_buying_power_pct", 10.0)
        max_cost = equity * (max_bp_pct / 100)

        # Strike range: within csp_strike_range_pct of current price
        strike_range_pct = self._config.get("csp_strike_range_pct", 5.0)
        min_strike = snapshot.price * (1 - strike_range_pct / 100)
        max_strike = snapshot.price * (1 + strike_range_pct / 100)

        # Delta range
        delta_range = self._config.get("csp_delta_range", [0.18, 0.42])
        min_delta, max_delta = delta_range

        # Min open interest
        min_oi = self._config.get("min_open_interest", 200)

        # Filter puts
        candidates = [
            c for c in snapshot.options_chain.puts
            if min_strike <= c.strike_price <= max_strike
            and c.open_interest >= min_oi
            and c.mid_price > 0
            and c.strike_price * 100 <= max_cost  # can afford assignment
        ]

        if not candidates:
            return None

        # Prefer delta-based selection
        delta_candidates = [
            c for c in candidates
            if c.delta != 0 and min_delta <= abs(c.delta) <= max_delta
        ]

        if delta_candidates:
            # Pick closest to target delta (midpoint of range)
            target_delta = (min_delta + max_delta) / 2
            best = min(delta_candidates, key=lambda c: abs(abs(c.delta) - target_delta))
        else:
            # Fallback: pick the put closest to 3% OTM
            target_strike = snapshot.price * 0.97
            best = min(candidates, key=lambda c: abs(c.strike_price - target_strike))

        # Quantity: how many contracts can we afford?
        cost_per_contract = best.strike_price * 100
        max_qty = max(1, int(max_cost / cost_per_contract))
        qty = min(max_qty, 1)  # Start conservative with 1 contract

        reasoning = [
            f"Wheel CSP: {symbol} @ ${best.strike_price}",
            f"Price ${snapshot.price:.2f}, strike {((snapshot.price - best.strike_price) / snapshot.price * 100):.1f}% OTM",
            f"Premium ${best.mid_price:.2f}, delta {best.delta:.2f}",
            f"OI: {best.open_interest}, exp: {best.expiration_date}",
            f"Cash required: ${cost_per_contract:.0f} ({cost_per_contract/equity*100:.1f}% of equity)",
        ]

        return WheelSignal(
            symbol=symbol,
            phase="csp",
            option_contract=best.symbol,
            strike_price=best.strike_price,
            contract_type="put",
            expiration=best.expiration_date,
            target_premium=best.mid_price,
            quantity=qty,
            delta=best.delta,
            reasoning=reasoning,
        )

    def _evaluate_covered_call(self, snapshot: MarketSnapshot, position, account) -> WheelSignal | None:
        """Find and return a covered call signal."""
        symbol = snapshot.symbol

        if position.shares_held < 100:
            return None

        # Delta range
        delta_range = self._config.get("cc_delta_range", [0.18, 0.42])
        min_delta, max_delta = delta_range

        # Min open interest
        min_oi = self._config.get("min_open_interest", 200)

        # CC strike filter: above upper Bollinger Band if configured
        cc_above_bb = self._config.get("cc_above_bollinger", True)
        upper_bb = snapshot.indicators.upper_bollinger

        # Also require strike above cost basis for profitable exit
        min_strike = position.cost_basis if position.cost_basis > 0 else snapshot.price

        candidates = [
            c for c in snapshot.options_chain.calls
            if c.strike_price >= min_strike
            and c.open_interest >= min_oi
            and c.mid_price > 0
        ]

        # Apply Bollinger Band filter
        if cc_above_bb and upper_bb and upper_bb > 0:
            bb_candidates = [c for c in candidates if c.strike_price >= upper_bb]
            if bb_candidates:
                candidates = bb_candidates
            # If no candidates above BB, fall through and use all candidates

        if not candidates:
            return None

        # Delta-based selection
        delta_candidates = [
            c for c in candidates
            if c.delta != 0 and min_delta <= abs(c.delta) <= max_delta
        ]

        if delta_candidates:
            target_delta = (min_delta + max_delta) / 2
            best = min(delta_candidates, key=lambda c: abs(abs(c.delta) - target_delta))
        else:
            # Fallback: pick call closest to 3% OTM
            target_strike = snapshot.price * 1.03
            best = min(candidates, key=lambda c: abs(c.strike_price - target_strike))

        # Quantity: 1 contract per 100 shares
        qty = position.shares_held // 100

        reasoning = [
            f"Wheel CC: {symbol} @ ${best.strike_price}",
            f"Price ${snapshot.price:.2f}, strike {((best.strike_price - snapshot.price) / snapshot.price * 100):.1f}% OTM",
            f"Premium ${best.mid_price:.2f}, delta {best.delta:.2f}",
            f"Cost basis ${position.cost_basis:.2f}, OI: {best.open_interest}",
            f"Exp: {best.expiration_date}",
        ]
        if upper_bb:
            reasoning.append(f"Upper BB: ${upper_bb:.2f} (strike {'above' if best.strike_price >= upper_bb else 'below'})")

        return WheelSignal(
            symbol=symbol,
            phase="covered_call",
            option_contract=best.symbol,
            strike_price=best.strike_price,
            contract_type="call",
            expiration=best.expiration_date,
            target_premium=best.mid_price,
            quantity=qty,
            delta=best.delta,
            reasoning=reasoning,
        )

    def _score_conviction(self, signal: WheelSignal, snapshot: MarketSnapshot, regime=None) -> None:
        """Score conviction 0-100 for wheel signals."""
        score = 50

        # IV rank bonus
        if snapshot.iv_rank is not None:
            if snapshot.iv_rank > 60:
                score += 15
            elif snapshot.iv_rank > 40:
                score += 8

        # ADX: mean-reverting is better for premium selling
        adx = snapshot.indicators.adx
        if adx is not None:
            if adx < 20:
                score += 10
            elif adx > 30:
                score -= 10

        # Regime alignment
        if regime:
            vol_regime = str(getattr(regime, "volatility_regime", ""))
            if "elevated" in vol_regime:
                score += 10
            elif "crisis" in vol_regime:
                score -= 20
            phase = str(getattr(regime, "market_phase", ""))
            if "mean_reverting" in phase:
                score += 10
            elif "trending" in phase:
                score -= 5

        # For CSP: support buffer is good
        if signal.phase == "csp":
            support = snapshot.indicators.support
            if support and signal.strike_price < support:
                score += 10  # strike below support

        # For CC: distance above price is good
        if signal.phase == "covered_call":
            otm_pct = (signal.strike_price - snapshot.price) / snapshot.price * 100
            if otm_pct > 3:
                score += 5

        signal.conviction_score = max(0, min(100, score))

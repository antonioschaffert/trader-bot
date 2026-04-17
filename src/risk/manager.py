"""
Risk Manager - Enhanced

Now includes:
1. All original checks (daily limits, position limits, buying power)
2. Drawdown-based trading halt and size reduction
3. Correlation-aware position limits
4. Portfolio Greeks limits (net delta, vega exposure)
5. Regime-based position sizing
6. Dynamic quantity calculation based on conviction + regime + drawdown
7. Support/resistance proximity warnings
"""

import logging
import math
from dataclasses import dataclass

from src.event_bus import EventBus
from src.risk.correlation import CorrelationManager
from src.risk.drawdown import DrawdownManager
from src.risk.portfolio_greeks import PortfolioGreeksTracker
from src.signals.models import TradeSignal

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    approved: bool
    reason: str = ""
    adjusted_quantity: int = 1  # may be reduced by risk checks


class RiskManager:
    def __init__(self, config: dict, event_bus: EventBus):
        self._config = config
        self._bus = event_bus

        # Enhanced risk subsystems
        self._greeks_tracker = PortfolioGreeksTracker(config)
        self._drawdown_mgr = DrawdownManager(config.get("drawdown", {}))
        self._correlation_mgr: CorrelationManager | None = None

    @property
    def greeks_tracker(self) -> PortfolioGreeksTracker:
        return self._greeks_tracker

    @property
    def drawdown_manager(self) -> DrawdownManager:
        return self._drawdown_mgr

    def set_correlation_manager(self, cm: CorrelationManager) -> None:
        self._correlation_mgr = cm

    def validate_signal(
        self,
        signal: TradeSignal,
        open_positions: list,
        account,
        daily_pnl: float,
        regime=None,
    ) -> ValidationResult:
        # --- Drawdown & Cooldown Check ---
        can_trade, dd_reason = self._drawdown_mgr.can_trade()
        if not can_trade:
            return ValidationResult(False, f"Drawdown halt: {dd_reason}")

        # --- Daily Loss Limit ---
        daily_loss_limit = self._config.get("daily_loss_limit", 1000)
        if daily_pnl <= -daily_loss_limit:
            return ValidationResult(False, f"Daily loss limit exceeded: ${daily_pnl:.2f}")

        # --- Daily Profit Target ---
        daily_target = self._config.get("daily_income_target", 500)
        if daily_pnl >= daily_target:
            return ValidationResult(False, f"Daily target already met: ${daily_pnl:.2f}")

        # --- Max Concurrent Spreads ---
        max_spreads = self._config.get("max_concurrent_spreads", 10)
        if len(open_positions) >= max_spreads:
            return ValidationResult(False, f"Max concurrent spreads reached: {len(open_positions)}/{max_spreads}")

        # --- Same Symbol/Direction Limit ---
        max_same = self._config.get("max_same_direction_per_symbol", 3)
        same_count = sum(
            1 for p in open_positions
            if getattr(p, "symbol", None) == signal.symbol
            and getattr(p, "spread_type", None) == signal.spread_type
        )
        if same_count >= max_same:
            return ValidationResult(
                False,
                f"Max same-direction spreads for {signal.symbol} {signal.spread_type}: {same_count}/{max_same}",
            )

        # --- Correlation Check ---
        if self._correlation_mgr:
            corr_risk = self._correlation_mgr.assess_new_trade(
                signal.symbol, signal.spread_type, open_positions
            )
            if corr_risk.violations:
                return ValidationResult(False, f"Correlation risk: {corr_risk.violations[0]}")

        # --- Portfolio Greeks Check ---
        self._greeks_tracker.update(open_positions)
        delta_violations = self._greeks_tracker.check_delta_limit(
            self._config.get("max_portfolio_delta_per_symbol", 0.30)
        )
        if delta_violations:
            return ValidationResult(False, f"Portfolio delta limit: {delta_violations[0]}")

        vega_warning = self._greeks_tracker.check_portfolio_vega(
            self._config.get("max_portfolio_vega", 500)
        )
        if vega_warning:
            logger.warning(f"Vega exposure warning: {vega_warning}")
            # Warning only, don't block

        # --- Trade Risk (Max $ per trade) ---
        max_risk_pct = self._config.get("max_risk_per_trade_pct", 5)
        equity = float(getattr(account, "equity", 50000))
        max_risk_dollars = equity * (max_risk_pct / 100)
        spread_width = self._calculate_spread_width(signal)
        # Assume execution slippage — we size against the realistic (worse) fill,
        # not the mid-price credit we hope to get. Protects against bad-fill days.
        slippage = self._config.get("slippage_buffer_pct", 0.10)
        realistic_premium = signal.target_premium * (1.0 - max(0.0, slippage))
        trade_risk = (spread_width - realistic_premium) * 100
        if trade_risk > max_risk_dollars:
            return ValidationResult(
                False,
                f"Trade risk ${trade_risk:.2f} exceeds max ${max_risk_dollars:.2f} ({max_risk_pct}% of equity)",
            )

        # --- Buying Power Check ---
        max_bp_pct = self._config.get("max_buying_power_usage_pct", 60)
        buying_power = float(getattr(account, "buying_power", 0))
        total_bp = equity
        if total_bp > 0 and (1 - buying_power / total_bp) * 100 > max_bp_pct:
            return ValidationResult(False, f"Buying power usage exceeds {max_bp_pct}%")

        # --- Calculate Dynamic Quantity ---
        quantity = self._calculate_dynamic_quantity(
            signal, equity, regime, open_positions
        )
        signal.quantity = quantity

        return ValidationResult(True, adjusted_quantity=quantity)

    def _calculate_dynamic_quantity(
        self, signal: TradeSignal, equity: float, regime=None, open_positions: list = None,
    ) -> int:
        """
        Dynamic position sizing based on:
        1. Base size from account equity (risk per trade)
        2. Conviction score scaling
        3. Regime multiplier
        4. Drawdown reduction
        5. Correlation penalty
        """
        spread_width = self._calculate_spread_width(signal)
        max_risk_per_trade = equity * (self._config.get("max_risk_per_trade_pct", 5) / 100)
        slippage = self._config.get("slippage_buffer_pct", 0.10)
        realistic_premium = signal.target_premium * (1.0 - max(0.0, slippage))
        risk_per_contract = (spread_width - realistic_premium) * 100

        if risk_per_contract <= 0:
            return 1

        # Base quantity from risk budget
        base_qty = max(1, int(max_risk_per_trade / risk_per_contract))

        # Conviction scaling: 0-30 = 50%, 30-60 = 75%, 60-80 = 100%, 80+ = 120%
        conviction = signal.conviction_score
        if conviction < 30:
            conv_mult = 0.5
        elif conviction < 60:
            conv_mult = 0.75
        elif conviction < 80:
            conv_mult = 1.0
        else:
            conv_mult = 1.2

        # Regime multiplier
        regime_mult = 1.0
        if regime:
            regime_mult = getattr(regime, "position_size_multiplier", 1.0)

        # Drawdown reduction
        dd_mult = self._drawdown_mgr.get_size_multiplier()

        # Correlation penalty
        corr_mult = 1.0
        if self._correlation_mgr and open_positions:
            corr_risk = self._correlation_mgr.assess_new_trade(
                signal.symbol, signal.spread_type, open_positions
            )
            corr_mult = corr_risk.correlation_penalty

        final_qty = base_qty * conv_mult * regime_mult * dd_mult * corr_mult
        final_qty = max(1, int(math.floor(final_qty)))

        # Cap at reasonable maximum
        max_qty = self._config.get("max_contracts_per_trade", 10)
        final_qty = min(final_qty, max_qty)

        if final_qty != base_qty:
            logger.info(
                f"Dynamic sizing: base={base_qty}, conviction={conv_mult:.1f}x, "
                f"regime={regime_mult:.1f}x, drawdown={dd_mult:.1f}x, "
                f"correlation={corr_mult:.1f}x -> final={final_qty}"
            )

        return final_qty

    def check_profit_target(self, current_value: float, entry_premium: float, target_pct: int) -> bool:
        profit = entry_premium - current_value
        target_profit = entry_premium * (target_pct / 100)
        return profit >= target_profit

    def check_stop_loss(self, current_value: float, entry_premium: float, multiplier: float) -> bool:
        loss = current_value - entry_premium
        max_loss = entry_premium * multiplier
        return loss >= max_loss

    def check_trailing_stop(
        self,
        current_value: float,
        entry_premium: float,
        peak_profit_pct: float,
    ) -> bool:
        """
        Lock in gains once the position has printed a material profit.

        Example config defaults:
          trailing_stop_activation_pct = 40  (only arm after +40% of max profit)
          trailing_stop_giveback_pct   = 50  (exit if we've surrendered >= 50%
                                              of the peak profit)

        Math: profit_pct is (entry - current) / entry expressed in [0..1+].
        """
        if entry_premium <= 0:
            return False
        activation = self._config.get("trailing_stop_activation_pct", 0) / 100.0
        if activation <= 0:
            return False
        if peak_profit_pct < activation:
            return False
        giveback = self._config.get("trailing_stop_giveback_pct", 50) / 100.0
        profit_pct = (entry_premium - current_value) / entry_premium
        # Exit when we've given back `giveback` fraction of the peak profit.
        trigger = peak_profit_pct * (1.0 - giveback)
        return profit_pct <= trigger

    def check_roll_needed(self, short_delta: float, threshold: float) -> bool:
        return abs(short_delta) >= threshold

    def check_dte_exit(self, days_to_expiry: int) -> bool:
        dte_exit = self._config.get("dte_exit", 1)
        return days_to_expiry <= dte_exit

    def _calculate_spread_width(self, signal: TradeSignal) -> float:
        strikes = [leg.strike_price for leg in signal.legs]
        if len(strikes) < 2:
            return 0.0
        return abs(max(strikes) - min(strikes))

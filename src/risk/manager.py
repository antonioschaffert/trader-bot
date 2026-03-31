import logging
from dataclasses import dataclass

from src.event_bus import EventBus
from src.signals.models import TradeSignal

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    approved: bool
    reason: str = ""


class RiskManager:
    def __init__(self, config: dict, event_bus: EventBus):
        self._config = config
        self._bus = event_bus

    def validate_signal(self, signal: TradeSignal, open_positions: list, account, daily_pnl: float) -> ValidationResult:
        daily_loss_limit = self._config.get("daily_loss_limit", 1000)
        if daily_pnl <= -daily_loss_limit:
            return ValidationResult(False, f"Daily loss limit exceeded: ${daily_pnl:.2f}")

        daily_target = self._config.get("daily_income_target", 500)
        if daily_pnl >= daily_target:
            return ValidationResult(False, f"Daily target already met: ${daily_pnl:.2f}")

        max_spreads = self._config.get("max_concurrent_spreads", 10)
        if len(open_positions) >= max_spreads:
            return ValidationResult(False, f"Max concurrent spreads reached: {len(open_positions)}/{max_spreads}")

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

        max_risk_pct = self._config.get("max_risk_per_trade_pct", 5)
        equity = float(getattr(account, "equity", 50000))
        max_risk_dollars = equity * (max_risk_pct / 100)
        spread_width = self._calculate_spread_width(signal)
        trade_risk = (spread_width - signal.target_premium) * 100
        if trade_risk > max_risk_dollars:
            return ValidationResult(
                False,
                f"Trade risk ${trade_risk:.2f} exceeds max ${max_risk_dollars:.2f} ({max_risk_pct}% of equity)",
            )

        max_bp_pct = self._config.get("max_buying_power_usage_pct", 60)
        buying_power = float(getattr(account, "buying_power", 0))
        total_bp = equity
        if total_bp > 0 and (1 - buying_power / total_bp) * 100 > max_bp_pct:
            return ValidationResult(False, f"Buying power usage exceeds {max_bp_pct}%")

        return ValidationResult(True)

    def check_profit_target(self, current_value: float, entry_premium: float, target_pct: int) -> bool:
        """Return True when the position has reached its profit target."""
        profit = entry_premium - current_value
        target_profit = entry_premium * (target_pct / 100)
        return profit >= target_profit

    def check_stop_loss(self, current_value: float, entry_premium: float, multiplier: float) -> bool:
        """Return True when the position has breached the stop-loss threshold."""
        loss = current_value - entry_premium
        max_loss = entry_premium * multiplier
        return loss >= max_loss

    def check_roll_needed(self, short_delta: float, threshold: float) -> bool:
        """Return True when the short leg delta has breached the roll threshold."""
        return abs(short_delta) >= threshold

    def check_dte_exit(self, days_to_expiry: int) -> bool:
        """Return True when the position should be closed due to approaching expiration."""
        dte_exit = self._config.get("dte_exit", 1)
        return days_to_expiry <= dte_exit

    def _calculate_spread_width(self, signal: TradeSignal) -> float:
        strikes = [leg.strike_price for leg in signal.legs]
        if len(strikes) < 2:
            return 0.0
        return abs(max(strikes) - min(strikes))

"""
Drawdown Protection & Consecutive Loss Cooldown

Professional risk management isn't just about individual trade sizing.
It's about recognizing when you're in a losing streak and stepping back
before it becomes catastrophic.

This module implements:
1. Peak-to-trough drawdown tracking with alerts at thresholds
2. Consecutive loss counting with automatic cooldown periods
3. Progressive position size reduction during drawdowns
4. Recovery tracking to know when it's safe to size back up
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


@dataclass
class DrawdownState:
    peak_equity: float = 0.0
    current_equity: float = 0.0
    drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    longest_losing_streak: int = 0
    cooldown_until: datetime | None = None
    is_in_cooldown: bool = False
    size_reduction_factor: float = 1.0  # 1.0 = full size, 0.0 = no trading
    total_trades: int = 0
    win_count: int = 0
    loss_count: int = 0

    def to_dict(self) -> dict:
        return {
            "peak_equity": round(self.peak_equity, 2),
            "current_equity": round(self.current_equity, 2),
            "drawdown_pct": round(self.drawdown_pct, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "consecutive_losses": self.consecutive_losses,
            "consecutive_wins": self.consecutive_wins,
            "longest_losing_streak": self.longest_losing_streak,
            "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
            "is_in_cooldown": self.is_in_cooldown,
            "size_reduction_factor": round(self.size_reduction_factor, 2),
            "total_trades": self.total_trades,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "win_rate": round(self.win_count / self.total_trades * 100, 1) if self.total_trades > 0 else 0,
        }


class DrawdownManager:
    """
    Tracks drawdown and losing streaks. Automatically reduces position size
    and enforces cooldown periods when things go wrong.

    Thresholds (configurable):
    - 3 consecutive losses: reduce size by 50%
    - 5 consecutive losses: stop trading for 1 hour
    - 5% drawdown: reduce size by 30%
    - 10% drawdown: reduce size by 60%
    - 15% drawdown: halt trading entirely
    """

    def __init__(self, config: dict | None = None):
        self._config = config or {}
        self._state = DrawdownState()

        # Configurable thresholds
        self._loss_streak_reduce = self._config.get("loss_streak_reduce", 3)
        self._loss_streak_halt = self._config.get("loss_streak_halt", 5)
        self._cooldown_minutes = self._config.get("cooldown_minutes", 60)
        self._dd_reduce_threshold = self._config.get("drawdown_reduce_pct", 5.0)
        self._dd_severe_threshold = self._config.get("drawdown_severe_pct", 10.0)
        self._dd_halt_threshold = self._config.get("drawdown_halt_pct", 15.0)

    @property
    def state(self) -> DrawdownState:
        return self._state

    def update_equity(self, equity: float) -> None:
        self._state.current_equity = equity
        if equity > self._state.peak_equity:
            self._state.peak_equity = equity

        if self._state.peak_equity > 0:
            self._state.drawdown_pct = (
                (self._state.peak_equity - equity) / self._state.peak_equity * 100
            )
            self._state.max_drawdown_pct = max(
                self._state.max_drawdown_pct, self._state.drawdown_pct
            )

        self._recalc_size_factor()

    def record_trade_result(self, pnl: float) -> None:
        self._state.total_trades += 1

        if pnl >= 0:
            self._state.win_count += 1
            self._state.consecutive_wins += 1
            self._state.consecutive_losses = 0

            # After 3 consecutive wins coming out of drawdown, ease back in
            if self._state.consecutive_wins >= 3 and self._state.drawdown_pct < self._dd_reduce_threshold:
                self._state.size_reduction_factor = min(
                    self._state.size_reduction_factor + 0.2, 1.0
                )
        else:
            self._state.loss_count += 1
            self._state.consecutive_losses += 1
            self._state.consecutive_wins = 0
            self._state.longest_losing_streak = max(
                self._state.longest_losing_streak, self._state.consecutive_losses
            )

            # Consecutive loss cooldown
            if self._state.consecutive_losses >= self._loss_streak_halt:
                self._enter_cooldown()
                logger.warning(
                    f"DRAWDOWN: {self._state.consecutive_losses} consecutive losses. "
                    f"Entering {self._cooldown_minutes}min cooldown."
                )

        self._recalc_size_factor()

    def can_trade(self) -> tuple[bool, str]:
        """Check if trading is allowed. Returns (allowed, reason)."""
        now = datetime.now(timezone.utc)

        # Check cooldown
        if self._state.cooldown_until and now < self._state.cooldown_until:
            remaining = (self._state.cooldown_until - now).total_seconds() / 60
            self._state.is_in_cooldown = True
            return False, f"In cooldown ({remaining:.0f}min remaining) after {self._state.consecutive_losses} consecutive losses"
        else:
            self._state.is_in_cooldown = False
            self._state.cooldown_until = None

        # Check drawdown halt
        if self._state.drawdown_pct >= self._dd_halt_threshold:
            return False, f"Drawdown {self._state.drawdown_pct:.1f}% exceeds halt threshold {self._dd_halt_threshold}%"

        return True, ""

    def get_size_multiplier(self) -> float:
        """Get the current position size reduction factor."""
        return self._state.size_reduction_factor

    def _enter_cooldown(self) -> None:
        self._state.cooldown_until = datetime.now(timezone.utc) + timedelta(
            minutes=self._cooldown_minutes
        )
        self._state.is_in_cooldown = True

    def _recalc_size_factor(self) -> None:
        factor = 1.0

        # Consecutive loss reduction
        if self._state.consecutive_losses >= self._loss_streak_reduce:
            factor *= 0.5
            logger.info(f"DRAWDOWN: {self._state.consecutive_losses} losses in a row. Size reduced to 50%.")

        # Drawdown-based reduction (progressive)
        dd = self._state.drawdown_pct
        if dd >= self._dd_severe_threshold:
            factor *= 0.4  # 60% reduction
            logger.info(f"DRAWDOWN: {dd:.1f}% drawdown. Severe size reduction.")
        elif dd >= self._dd_reduce_threshold:
            factor *= 0.7  # 30% reduction
            logger.info(f"DRAWDOWN: {dd:.1f}% drawdown. Moderate size reduction.")

        self._state.size_reduction_factor = round(max(factor, 0.0), 2)

    def reset_daily(self) -> None:
        """Soft reset for new trading day. Keeps drawdown state but resets cooldown."""
        self._state.is_in_cooldown = False
        self._state.cooldown_until = None

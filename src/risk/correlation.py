"""
Correlation-Aware Risk Management

SPY and QQQ are 85-95% correlated. Treating them as independent risk
is a rookie mistake that can blow up your account when both move against you.

This module:
1. Tracks rolling correlation between symbols
2. Penalizes position sizing when correlated positions exist
3. Prevents stacking same-direction bets across correlated assets
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Historical average correlations (updated periodically from price data)
DEFAULT_CORRELATIONS = {
    ("SPY", "QQQ"): 0.92,
    ("QQQ", "SPY"): 0.92,
}


@dataclass
class CorrelationRisk:
    correlated_exposure: float = 0.0  # effective delta considering correlations
    correlation_penalty: float = 1.0  # multiplier for position sizing (< 1.0 = reduce)
    violations: list[str] = None

    def __post_init__(self):
        if self.violations is None:
            self.violations = []

    def to_dict(self) -> dict:
        return {
            "correlated_exposure": round(self.correlated_exposure, 2),
            "correlation_penalty": round(self.correlation_penalty, 2),
            "violations": self.violations,
        }


class CorrelationManager:
    """
    Manages correlation-aware risk across symbols.
    """

    def __init__(self, symbols: list[str], config: dict | None = None):
        self._symbols = symbols
        self._config = config or {}
        self._correlations: dict[tuple[str, str], float] = dict(DEFAULT_CORRELATIONS)
        self._max_correlated_same_direction = self._config.get(
            "max_correlated_same_direction", 4
        )

    def update_correlations(self, daily_bars: dict[str, list]) -> None:
        """Compute rolling 30-day correlation from daily close prices."""
        symbols = list(daily_bars.keys())
        for i, sym_a in enumerate(symbols):
            for sym_b in symbols[i + 1:]:
                bars_a = daily_bars[sym_a]
                bars_b = daily_bars[sym_b]
                corr = self._compute_correlation(bars_a, bars_b)
                if corr is not None:
                    self._correlations[(sym_a, sym_b)] = corr
                    self._correlations[(sym_b, sym_a)] = corr

    def assess_new_trade(
        self,
        symbol: str,
        spread_type: str,
        open_positions: list,
    ) -> CorrelationRisk:
        """
        Assess whether a new trade would create dangerous correlated exposure.
        """
        risk = CorrelationRisk()

        # Count same-direction positions across correlated symbols
        direction = "put" if "put" in spread_type else "call"
        same_direction_count = 0

        for pos in open_positions:
            pos_symbol = getattr(pos, "symbol", "")
            pos_type = getattr(pos, "spread_type", "")
            pos_direction = "put" if "put" in pos_type else "call"

            if pos_direction != direction:
                continue

            # Check if the position's symbol is correlated with our target
            corr = self._get_correlation(symbol, pos_symbol)
            if corr > 0.7:  # Treat as meaningfully correlated
                same_direction_count += 1

        if same_direction_count >= self._max_correlated_same_direction:
            risk.violations.append(
                f"Already {same_direction_count} correlated {direction} spreads "
                f"across {symbol} and correlated assets (max: {self._max_correlated_same_direction})"
            )

        # Compute correlation penalty: reduce size as correlated exposure grows
        if same_direction_count > 0:
            # Each additional correlated position reduces sizing by 15%
            risk.correlation_penalty = max(0.3, 1.0 - (same_direction_count * 0.15))

        # Compute correlated delta exposure
        risk.correlated_exposure = self._compute_correlated_delta(symbol, open_positions)

        return risk

    def _get_correlation(self, sym_a: str, sym_b: str) -> float:
        if sym_a == sym_b:
            return 1.0
        return self._correlations.get((sym_a, sym_b), 0.5)

    def _compute_correlation(self, bars_a: list, bars_b: list) -> float | None:
        """Simple Pearson correlation of daily returns."""
        min_len = min(len(bars_a), len(bars_b), 30)
        if min_len < 10:
            return None

        returns_a = [
            (bars_a[i].close - bars_a[i - 1].close) / bars_a[i - 1].close
            for i in range(len(bars_a) - min_len, len(bars_a))
        ]
        returns_b = [
            (bars_b[i].close - bars_b[i - 1].close) / bars_b[i - 1].close
            for i in range(len(bars_b) - min_len, len(bars_b))
        ]

        n = len(returns_a)
        mean_a = sum(returns_a) / n
        mean_b = sum(returns_b) / n

        cov = sum((a - mean_a) * (b - mean_b) for a, b in zip(returns_a, returns_b)) / n
        std_a = (sum((a - mean_a) ** 2 for a in returns_a) / n) ** 0.5
        std_b = (sum((b - mean_b) ** 2 for b in returns_b) / n) ** 0.5

        if std_a == 0 or std_b == 0:
            return None

        return cov / (std_a * std_b)

    def _compute_correlated_delta(self, symbol: str, positions: list) -> float:
        """Effective delta exposure considering correlations."""
        total = 0.0
        for pos in positions:
            pos_symbol = getattr(pos, "symbol", "")
            corr = self._get_correlation(symbol, pos_symbol)
            for leg in getattr(pos, "legs", []):
                delta = getattr(leg, "delta", 0.0)
                mult = -1 if leg.side == "sell" else 1
                total += delta * mult * corr * 100
        return total

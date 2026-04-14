"""
Portfolio-level Greeks aggregation and monitoring.

A professional options trader ALWAYS knows their aggregate portfolio exposure.
This module tracks net delta, gamma, theta, vega across all open positions
and provides risk alerts when exposure gets dangerous.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PortfolioGreeks:
    net_delta: float = 0.0     # directional exposure (+long, -short)
    net_gamma: float = 0.0     # rate of delta change (convexity risk)
    net_theta: float = 0.0     # daily time decay P&L (+ = earning, - = paying)
    net_vega: float = 0.0      # volatility exposure (+ = long vol, - = short vol)
    total_premium_at_risk: float = 0.0  # max loss across all positions
    theta_to_delta_ratio: float = 0.0   # how much theta we earn per unit of delta risk
    per_symbol: dict = field(default_factory=dict)  # Greeks broken down by symbol

    def to_dict(self) -> dict:
        return {
            "net_delta": round(self.net_delta, 4),
            "net_gamma": round(self.net_gamma, 4),
            "net_theta": round(self.net_theta, 2),
            "net_vega": round(self.net_vega, 4),
            "total_premium_at_risk": round(self.total_premium_at_risk, 2),
            "theta_to_delta_ratio": round(self.theta_to_delta_ratio, 2),
            "per_symbol": {
                sym: {k: round(v, 4) for k, v in greeks.items()}
                for sym, greeks in self.per_symbol.items()
            },
        }


class PortfolioGreeksTracker:
    """
    Aggregates Greeks across all open positions and flags dangerous exposure.
    """

    def __init__(self, config: dict | None = None):
        self._config = config or {}
        self._current: PortfolioGreeks = PortfolioGreeks()

    @property
    def current(self) -> PortfolioGreeks:
        return self._current

    def update(self, open_positions: list) -> PortfolioGreeks:
        greeks = PortfolioGreeks()
        per_symbol: dict[str, dict] = {}

        for position in open_positions:
            symbol = getattr(position, "symbol", "UNKNOWN")
            if symbol not in per_symbol:
                per_symbol[symbol] = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

            for leg in getattr(position, "legs", []):
                delta = getattr(leg, "delta", 0.0)
                gamma = getattr(leg, "gamma", 0.0)
                theta = getattr(leg, "theta", 0.0)
                vega = getattr(leg, "vega", 0.0)

                # Multiply by 100 for contract multiplier, negate for short legs
                multiplier = -100 if leg.side == "sell" else 100

                greeks.net_delta += delta * multiplier
                greeks.net_gamma += gamma * multiplier
                greeks.net_theta += theta * multiplier
                greeks.net_vega += vega * multiplier

                per_symbol[symbol]["delta"] += delta * multiplier
                per_symbol[symbol]["gamma"] += gamma * multiplier
                per_symbol[symbol]["theta"] += theta * multiplier
                per_symbol[symbol]["vega"] += vega * multiplier

            # Total premium at risk
            entry = getattr(position, "entry_premium", 0)
            spread_width = self._calc_spread_width(position)
            max_loss = (spread_width - entry) * 100
            greeks.total_premium_at_risk += max_loss

        greeks.per_symbol = per_symbol

        # Theta-to-delta ratio: how efficiently we earn theta per unit of delta risk
        if abs(greeks.net_delta) > 0.01:
            greeks.theta_to_delta_ratio = abs(greeks.net_theta) / abs(greeks.net_delta)

        self._current = greeks
        return greeks

    def check_delta_limit(self, max_delta_per_symbol: float) -> list[str]:
        """Return list of symbols exceeding delta limits."""
        violations = []
        for symbol, greeks in self._current.per_symbol.items():
            if abs(greeks["delta"]) > max_delta_per_symbol * 100:
                violations.append(
                    f"{symbol}: net delta {greeks['delta']:.0f} exceeds "
                    f"limit {max_delta_per_symbol * 100:.0f}"
                )
        return violations

    def check_portfolio_vega(self, max_vega: float = 500) -> str | None:
        """Alert if portfolio is too exposed to vol changes."""
        if abs(self._current.net_vega) > max_vega:
            return (
                f"Portfolio vega {self._current.net_vega:.0f} exceeds limit {max_vega}. "
                f"A 1-point IV move costs ${abs(self._current.net_vega):.0f}."
            )
        return None

    def _calc_spread_width(self, position) -> float:
        strikes = [leg.strike_price for leg in getattr(position, "legs", [])]
        if len(strikes) < 2:
            return 0.0
        return abs(max(strikes) - min(strikes))

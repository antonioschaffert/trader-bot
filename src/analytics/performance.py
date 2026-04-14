"""
Performance Analytics Engine

A trading bot without analytics is flying blind. This module computes:
- Win rate, average win/loss, expectancy
- Sharpe ratio and Sortino ratio
- Profit factor
- Per-strategy breakdown
- Equity curve tracking
- Rolling performance windows (7d, 30d, 90d)
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


@dataclass
class StrategyMetrics:
    strategy: str = ""
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    total_pnl: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0  # expected $ per trade

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(self.win_rate, 1),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "largest_win": round(self.largest_win, 2),
            "largest_loss": round(self.largest_loss, 2),
            "total_pnl": round(self.total_pnl, 2),
            "profit_factor": round(self.profit_factor, 2),
            "expectancy": round(self.expectancy, 2),
        }


@dataclass
class PerformanceReport:
    # Overall metrics
    total_trades: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    avg_trade_duration_hours: float = 0.0

    # Rolling windows
    pnl_7d: float = 0.0
    pnl_30d: float = 0.0
    trades_7d: int = 0
    trades_30d: int = 0
    win_rate_7d: float = 0.0
    win_rate_30d: float = 0.0

    # Per-strategy breakdown
    by_strategy: list[StrategyMetrics] = field(default_factory=list)

    # Per-symbol breakdown
    by_symbol: dict = field(default_factory=dict)

    # Equity curve (daily P&L)
    equity_curve: list[dict] = field(default_factory=list)

    # Best/worst
    best_day: float = 0.0
    worst_day: float = 0.0
    avg_daily_pnl: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_trades": self.total_trades,
            "total_pnl": round(self.total_pnl, 2),
            "win_rate": round(self.win_rate, 1),
            "profit_factor": round(self.profit_factor, 2),
            "expectancy": round(self.expectancy, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "avg_trade_duration_hours": round(self.avg_trade_duration_hours, 1),
            "pnl_7d": round(self.pnl_7d, 2),
            "pnl_30d": round(self.pnl_30d, 2),
            "trades_7d": self.trades_7d,
            "trades_30d": self.trades_30d,
            "win_rate_7d": round(self.win_rate_7d, 1),
            "win_rate_30d": round(self.win_rate_30d, 1),
            "by_strategy": [s.to_dict() for s in self.by_strategy],
            "by_symbol": self.by_symbol,
            "equity_curve": self.equity_curve,
            "best_day": round(self.best_day, 2),
            "worst_day": round(self.worst_day, 2),
            "avg_daily_pnl": round(self.avg_daily_pnl, 2),
        }


class PerformanceAnalytics:
    """
    Computes comprehensive performance metrics from trade history.
    """

    def __init__(self, db):
        self._db = db

    def generate_report(self, days: int = 90) -> PerformanceReport:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        trades = self._get_closed_trades(since)

        report = PerformanceReport()
        if not trades:
            return report

        pnls = [t.get("pnl", 0) for t in trades]
        report.total_trades = len(trades)
        report.total_pnl = sum(pnls)

        wins = [p for p in pnls if p >= 0]
        losses = [p for p in pnls if p < 0]

        if report.total_trades > 0:
            report.win_rate = len(wins) / report.total_trades * 100

        # Profit factor
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        report.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

        # Expectancy
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        win_rate_frac = len(wins) / report.total_trades if report.total_trades > 0 else 0
        report.expectancy = (win_rate_frac * avg_win) + ((1 - win_rate_frac) * avg_loss)

        # Sharpe and Sortino ratios (annualized, using daily returns)
        daily_pnls = self._aggregate_daily_pnl(trades)
        if len(daily_pnls) >= 5:
            report.sharpe_ratio = self._sharpe_ratio(daily_pnls)
            report.sortino_ratio = self._sortino_ratio(daily_pnls)
            report.best_day = max(daily_pnls)
            report.worst_day = min(daily_pnls)
            report.avg_daily_pnl = sum(daily_pnls) / len(daily_pnls)

        # Average trade duration
        durations = []
        for t in trades:
            opened = t.get("opened_at")
            closed = t.get("closed_at")
            if opened and closed and isinstance(opened, datetime) and isinstance(closed, datetime):
                durations.append((closed - opened).total_seconds() / 3600)
        if durations:
            report.avg_trade_duration_hours = sum(durations) / len(durations)

        # Rolling windows
        now = datetime.now(timezone.utc)
        trades_7d = [t for t in trades if self._trade_closed_after(t, now - timedelta(days=7))]
        trades_30d = [t for t in trades if self._trade_closed_after(t, now - timedelta(days=30))]

        report.trades_7d = len(trades_7d)
        report.pnl_7d = sum(t.get("pnl", 0) for t in trades_7d)
        wins_7d = [t for t in trades_7d if t.get("pnl", 0) >= 0]
        report.win_rate_7d = len(wins_7d) / len(trades_7d) * 100 if trades_7d else 0

        report.trades_30d = len(trades_30d)
        report.pnl_30d = sum(t.get("pnl", 0) for t in trades_30d)
        wins_30d = [t for t in trades_30d if t.get("pnl", 0) >= 0]
        report.win_rate_30d = len(wins_30d) / len(trades_30d) * 100 if trades_30d else 0

        # Per-strategy breakdown
        report.by_strategy = self._breakdown_by_strategy(trades)

        # Per-symbol breakdown
        report.by_symbol = self._breakdown_by_symbol(trades)

        # Equity curve
        report.equity_curve = self._build_equity_curve(trades)

        return report

    def _get_closed_trades(self, since: datetime) -> list[dict]:
        cursor = self._db.db["trades"].find(
            {"closed_at": {"$gte": since}}
        ).sort("closed_at", 1)
        return list(cursor)

    def _aggregate_daily_pnl(self, trades: list[dict]) -> list[float]:
        """Group trade P&L by close date to get daily P&L series."""
        daily: dict[str, float] = {}
        for t in trades:
            closed = t.get("closed_at")
            if closed and isinstance(closed, datetime):
                day = closed.strftime("%Y-%m-%d")
                daily[day] = daily.get(day, 0) + t.get("pnl", 0)
        return list(daily.values())

    def _sharpe_ratio(self, daily_pnls: list[float]) -> float:
        if len(daily_pnls) < 2:
            return 0.0
        mean = sum(daily_pnls) / len(daily_pnls)
        std = (sum((p - mean) ** 2 for p in daily_pnls) / (len(daily_pnls) - 1)) ** 0.5
        if std == 0:
            return 0.0
        # Annualize: 252 trading days
        return (mean / std) * math.sqrt(252)

    def _sortino_ratio(self, daily_pnls: list[float]) -> float:
        if len(daily_pnls) < 2:
            return 0.0
        mean = sum(daily_pnls) / len(daily_pnls)
        neg = [p for p in daily_pnls if p < 0]
        if not neg:
            return float("inf") if mean > 0 else 0.0
        downside_std = (sum(p ** 2 for p in neg) / len(neg)) ** 0.5
        if downside_std == 0:
            return 0.0
        return (mean / downside_std) * math.sqrt(252)

    def _breakdown_by_strategy(self, trades: list[dict]) -> list[StrategyMetrics]:
        strategies: dict[str, list[dict]] = {}
        for t in trades:
            strat = t.get("strategy_mode", "unknown")
            strategies.setdefault(strat, []).append(t)

        results = []
        for strat, strat_trades in strategies.items():
            m = self._compute_strategy_metrics(strat, strat_trades)
            results.append(m)
        return results

    def _compute_strategy_metrics(self, strategy: str, trades: list[dict]) -> StrategyMetrics:
        m = StrategyMetrics(strategy=strategy)
        m.total_trades = len(trades)
        pnls = [t.get("pnl", 0) for t in trades]

        wins = [p for p in pnls if p >= 0]
        losses = [p for p in pnls if p < 0]

        m.wins = len(wins)
        m.losses = len(losses)
        m.win_rate = m.wins / m.total_trades * 100 if m.total_trades > 0 else 0
        m.avg_win = sum(wins) / len(wins) if wins else 0
        m.avg_loss = sum(losses) / len(losses) if losses else 0
        m.largest_win = max(wins) if wins else 0
        m.largest_loss = min(losses) if losses else 0
        m.total_pnl = sum(pnls)

        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        m.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

        win_rate_frac = m.wins / m.total_trades if m.total_trades > 0 else 0
        m.expectancy = (win_rate_frac * m.avg_win) + ((1 - win_rate_frac) * m.avg_loss)

        return m

    def _breakdown_by_symbol(self, trades: list[dict]) -> dict:
        symbols: dict[str, list[float]] = {}
        for t in trades:
            sym = t.get("symbol", "UNKNOWN")
            symbols.setdefault(sym, []).append(t.get("pnl", 0))

        return {
            sym: {
                "trades": len(pnls),
                "pnl": round(sum(pnls), 2),
                "win_rate": round(len([p for p in pnls if p >= 0]) / len(pnls) * 100, 1) if pnls else 0,
            }
            for sym, pnls in symbols.items()
        }

    def _build_equity_curve(self, trades: list[dict]) -> list[dict]:
        """Build cumulative P&L curve by day."""
        daily: dict[str, float] = {}
        for t in trades:
            closed = t.get("closed_at")
            if closed and isinstance(closed, datetime):
                day = closed.strftime("%Y-%m-%d")
                daily[day] = daily.get(day, 0) + t.get("pnl", 0)

        cumulative = 0.0
        curve = []
        for day in sorted(daily.keys()):
            cumulative += daily[day]
            curve.append({
                "date": day,
                "daily_pnl": round(daily[day], 2),
                "cumulative_pnl": round(cumulative, 2),
            })
        return curve

    def _trade_closed_after(self, trade: dict, after: datetime) -> bool:
        closed = trade.get("closed_at")
        if not closed or not isinstance(closed, datetime):
            return False
        if closed.tzinfo is None:
            closed = closed.replace(tzinfo=timezone.utc)
        return closed >= after

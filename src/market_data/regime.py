"""
Market Regime Detection Engine

Classifies the current market environment across multiple dimensions:
- Volatility regime (low/normal/elevated/crisis) via VIX levels and term structure
- Trend regime (strong_bull/bull/neutral/bear/strong_bear) via multi-timeframe analysis
- Mean-reversion vs momentum regime via ADX and autocorrelation

A pro options seller must adapt to the environment:
- Low vol + range-bound = sell premium aggressively, tight strikes
- High vol + trending = widen strikes, reduce size, favor the trend
- Crisis = stop selling premium, or go very wide and very small
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class VolatilityRegime(str, Enum):
    LOW = "low"              # VIX < 14: complacency, low premiums
    NORMAL = "normal"        # VIX 14-20: healthy market
    ELEVATED = "elevated"    # VIX 20-30: fear rising, juicy premiums
    CRISIS = "crisis"        # VIX > 30: panic, widen or sit out


class TrendRegime(str, Enum):
    STRONG_BULL = "strong_bull"  # All timeframes aligned up, ADX > 25
    BULL = "bull"                # Mostly up, moderate trend
    NEUTRAL = "neutral"          # Choppy, no clear direction
    BEAR = "bear"                # Mostly down, moderate trend
    STRONG_BEAR = "strong_bear"  # All timeframes aligned down, ADX > 25


class MarketPhase(str, Enum):
    TRENDING = "trending"        # ADX > 25: strong directional move
    MEAN_REVERTING = "mean_reverting"  # ADX < 20: range-bound, sell premium
    TRANSITIONING = "transitioning"    # ADX 20-25: watch for breakout


@dataclass
class RegimeSnapshot:
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    volatility_regime: VolatilityRegime = VolatilityRegime.NORMAL
    trend_regime: TrendRegime = TrendRegime.NEUTRAL
    market_phase: MarketPhase = MarketPhase.MEAN_REVERTING

    # VIX data
    vix_current: float = 0.0
    vix_sma_10: float = 0.0
    vix_percentile_30d: float = 50.0  # where VIX sits relative to last 30 days
    vix_term_structure: str = "contango"  # contango = normal, backwardation = fear

    # Trend data
    trend_score: float = 0.0  # -100 (max bearish) to +100 (max bullish)
    adx: float = 0.0
    weekly_trend: str = "neutral"
    daily_trend: str = "neutral"
    intraday_trend: str = "neutral"

    # Derived trading parameters
    position_size_multiplier: float = 1.0  # 0.0 to 1.5
    spread_width_multiplier: float = 1.0   # wider in high vol
    delta_adjustment: float = 0.0           # shift strikes further OTM in crisis
    premium_threshold_multiplier: float = 1.0  # require more premium in bad regimes
    should_trade: bool = True  # False = sit on hands

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "volatility_regime": self.volatility_regime.value,
            "trend_regime": self.trend_regime.value,
            "market_phase": self.market_phase.value,
            "vix_current": round(self.vix_current, 2),
            "vix_sma_10": round(self.vix_sma_10, 2),
            "vix_percentile_30d": round(self.vix_percentile_30d, 1),
            "vix_term_structure": self.vix_term_structure,
            "trend_score": round(self.trend_score, 1),
            "adx": round(self.adx, 1),
            "weekly_trend": self.weekly_trend,
            "daily_trend": self.daily_trend,
            "intraday_trend": self.intraday_trend,
            "position_size_multiplier": round(self.position_size_multiplier, 2),
            "spread_width_multiplier": round(self.spread_width_multiplier, 2),
            "delta_adjustment": round(self.delta_adjustment, 3),
            "premium_threshold_multiplier": round(self.premium_threshold_multiplier, 2),
            "should_trade": self.should_trade,
        }


class RegimeDetector:
    """
    Analyzes VIX, price action, and trend indicators to classify the market
    environment and produce regime-adaptive trading parameters.
    """

    # VIX thresholds (calibrated to historical percentiles)
    VIX_LOW = 14.0
    VIX_ELEVATED = 20.0
    VIX_CRISIS = 30.0

    # ADX thresholds for trend strength
    ADX_WEAK = 20.0
    ADX_STRONG = 25.0

    def __init__(self, config: dict | None = None):
        self._config = config or {}
        self._last_regime: RegimeSnapshot | None = None

    def analyze(
        self,
        vix_price: float,
        vix_bars: list,  # list of Bar objects for VIX history
        spy_daily_bars: list,
        spy_weekly_bars: list | None = None,
        spy_intraday_bars: list | None = None,
        adx_value: float | None = None,
    ) -> RegimeSnapshot:
        regime = RegimeSnapshot()
        regime.vix_current = vix_price

        # --- Volatility Regime ---
        regime.volatility_regime = self._classify_volatility(vix_price)

        # VIX SMA and percentile
        if vix_bars and len(vix_bars) >= 10:
            vix_closes = [b.close for b in vix_bars]
            regime.vix_sma_10 = sum(vix_closes[-10:]) / 10
            regime.vix_percentile_30d = self._percentile_rank(vix_price, vix_closes[-30:] if len(vix_closes) >= 30 else vix_closes)

        # VIX term structure (rising VIX with recent spike = backwardation proxy)
        if vix_bars and len(vix_bars) >= 5:
            recent_avg = sum(b.close for b in vix_bars[-5:]) / 5
            older_avg = sum(b.close for b in vix_bars[-20:-5]) / 15 if len(vix_bars) >= 20 else recent_avg
            regime.vix_term_structure = "backwardation" if recent_avg > older_avg * 1.1 else "contango"

        # --- Trend Regime ---
        regime.daily_trend = self._classify_trend_from_bars(spy_daily_bars)
        if spy_weekly_bars:
            regime.weekly_trend = self._classify_trend_from_bars(spy_weekly_bars)
        if spy_intraday_bars:
            regime.intraday_trend = self._classify_trend_from_bars(spy_intraday_bars)

        regime.trend_score = self._compute_trend_score(
            regime.weekly_trend, regime.daily_trend, regime.intraday_trend
        )
        regime.trend_regime = self._classify_trend_regime(regime.trend_score, adx_value)

        # --- Market Phase (ADX-based) ---
        if adx_value is not None:
            regime.adx = adx_value
            if adx_value > self.ADX_STRONG:
                regime.market_phase = MarketPhase.TRENDING
            elif adx_value < self.ADX_WEAK:
                regime.market_phase = MarketPhase.MEAN_REVERTING
            else:
                regime.market_phase = MarketPhase.TRANSITIONING

        # --- Derive Trading Parameters ---
        self._compute_trading_params(regime)

        self._last_regime = regime
        return regime

    def _classify_volatility(self, vix: float) -> VolatilityRegime:
        if vix < self.VIX_LOW:
            return VolatilityRegime.LOW
        elif vix < self.VIX_ELEVATED:
            return VolatilityRegime.NORMAL
        elif vix < self.VIX_CRISIS:
            return VolatilityRegime.ELEVATED
        else:
            return VolatilityRegime.CRISIS

    def _classify_trend_from_bars(self, bars: list) -> str:
        if not bars or len(bars) < 20:
            return "neutral"

        closes = [b.close for b in bars]
        current = closes[-1]

        # SMA crossover system
        sma_10 = sum(closes[-10:]) / 10
        sma_20 = sum(closes[-20:]) / 20
        sma_50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else sma_20

        # Price relative to moving averages
        above_10 = current > sma_10
        above_20 = current > sma_20
        above_50 = current > sma_50
        sma_10_above_20 = sma_10 > sma_20

        # Rate of change (momentum)
        roc_10 = (current - closes[-10]) / closes[-10] * 100 if len(closes) >= 10 else 0

        bull_signals = sum([above_10, above_20, above_50, sma_10_above_20, roc_10 > 1])
        bear_signals = sum([not above_10, not above_20, not above_50, not sma_10_above_20, roc_10 < -1])

        if bull_signals >= 4:
            return "bullish"
        elif bear_signals >= 4:
            return "bearish"
        return "neutral"

    def _compute_trend_score(self, weekly: str, daily: str, intraday: str) -> float:
        """Weighted trend score: weekly (50%) > daily (35%) > intraday (15%)."""
        weights = {"weekly": 50, "daily": 35, "intraday": 15}
        scores = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}

        score = (
            weights["weekly"] * scores.get(weekly, 0)
            + weights["daily"] * scores.get(daily, 0)
            + weights["intraday"] * scores.get(intraday, 0)
        )
        return score  # Range: -100 to +100

    def _classify_trend_regime(self, trend_score: float, adx: float | None) -> TrendRegime:
        strong_threshold = 60
        mild_threshold = 20

        if trend_score >= strong_threshold and (adx is None or adx > self.ADX_STRONG):
            return TrendRegime.STRONG_BULL
        elif trend_score >= mild_threshold:
            return TrendRegime.BULL
        elif trend_score <= -strong_threshold and (adx is None or adx > self.ADX_STRONG):
            return TrendRegime.STRONG_BEAR
        elif trend_score <= -mild_threshold:
            return TrendRegime.BEAR
        return TrendRegime.NEUTRAL

    def _percentile_rank(self, value: float, history: list[float]) -> float:
        if not history:
            return 50.0
        count_below = sum(1 for h in history if h < value)
        return (count_below / len(history)) * 100

    def _compute_trading_params(self, regime: RegimeSnapshot) -> None:
        """
        The heart of regime-adaptive trading. Every parameter adjusts based on
        what the market is telling us right now.
        """
        vol = regime.volatility_regime
        trend = regime.trend_regime
        phase = regime.market_phase

        # === Position Size Multiplier ===
        # Low vol = normal size, high vol = reduce, crisis = minimal or zero
        vol_size = {
            VolatilityRegime.LOW: 1.0,
            VolatilityRegime.NORMAL: 1.0,
            VolatilityRegime.ELEVATED: 0.7,
            VolatilityRegime.CRISIS: 0.3,
        }
        size_mult = vol_size[vol]

        # Mean-reverting markets are ideal for premium selling
        if phase == MarketPhase.MEAN_REVERTING:
            size_mult *= 1.2
        elif phase == MarketPhase.TRENDING:
            size_mult *= 0.8

        # Strong trends in either direction = reduce size
        if trend in (TrendRegime.STRONG_BULL, TrendRegime.STRONG_BEAR):
            size_mult *= 0.7

        regime.position_size_multiplier = round(min(max(size_mult, 0.0), 1.5), 2)

        # === Spread Width Multiplier ===
        # Widen spreads in high vol (bigger moves expected)
        width_mult = {
            VolatilityRegime.LOW: 0.8,    # can tighten in calm markets
            VolatilityRegime.NORMAL: 1.0,
            VolatilityRegime.ELEVATED: 1.3,
            VolatilityRegime.CRISIS: 1.5,  # much wider to limit tail risk
        }
        regime.spread_width_multiplier = width_mult[vol]

        # === Delta Adjustment ===
        # Push strikes further OTM in dangerous environments
        delta_adj = {
            VolatilityRegime.LOW: 0.0,
            VolatilityRegime.NORMAL: 0.0,
            VolatilityRegime.ELEVATED: -0.03,  # shift 3 delta points further OTM
            VolatilityRegime.CRISIS: -0.07,     # shift 7 delta points further OTM
        }
        regime.delta_adjustment = delta_adj[vol]

        # In strong trends, shift the "with trend" side closer and "against trend" further
        if trend == TrendRegime.STRONG_BEAR:
            regime.delta_adjustment -= 0.02  # extra caution on put side

        # === Premium Threshold Multiplier ===
        # Require more premium in risky environments to justify the trade
        prem_mult = {
            VolatilityRegime.LOW: 0.9,     # accept slightly less in low vol
            VolatilityRegime.NORMAL: 1.0,
            VolatilityRegime.ELEVATED: 1.3,  # demand 30% more premium
            VolatilityRegime.CRISIS: 1.8,    # demand 80% more premium
        }
        regime.premium_threshold_multiplier = prem_mult[vol]

        # === Should Trade ===
        # Circuit breaker: don't trade in extreme crisis with backwardation
        if vol == VolatilityRegime.CRISIS and regime.vix_term_structure == "backwardation":
            regime.should_trade = False
            regime.position_size_multiplier = 0.0
            logger.warning("REGIME: Crisis + backwardation detected. Trading halted.")

        # Don't sell premium in strong trending market with high vol
        if vol == VolatilityRegime.CRISIS and phase == MarketPhase.TRENDING:
            regime.should_trade = False
            regime.position_size_multiplier = 0.0
            logger.warning("REGIME: Crisis + trending market. Trading halted.")

    @property
    def last_regime(self) -> RegimeSnapshot | None:
        return self._last_regime

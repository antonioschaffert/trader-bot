from dataclasses import dataclass, field
from datetime import date


@dataclass
class SpreadLeg:
    symbol: str
    strike_price: float
    contract_type: str  # "call" or "put"
    side: str  # "sell" or "buy"
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0


@dataclass
class TradeSignal:
    strategy_mode: str  # "swing" or "exhaustion"
    symbol: str
    spread_type: str  # "put_spread", "call_spread", "iron_condor"
    legs: list[SpreadLeg]
    expiration: date
    target_premium: float
    profit_target_pct: int
    reasoning: list[str] = field(default_factory=list)
    # Enhanced fields
    quantity: int = 1                    # dynamic position size (number of spreads)
    conviction_score: float = 0.0        # 0-100, used for position sizing
    regime_context: str = ""             # market regime at time of signal
    support_distance_pct: float = 0.0    # how far from support (for put spreads)
    resistance_distance_pct: float = 0.0  # how far from resistance (for call spreads)


@dataclass
class EvaluationResult:
    """Result of a signal generator evaluation, including signals and rejection reasons."""
    signals: list[TradeSignal] = field(default_factory=list)
    rejections: list[dict] = field(default_factory=list)

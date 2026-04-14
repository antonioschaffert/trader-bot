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
    strategy_mode: str  # "swing", "exhaustion", or "wheel"
    symbol: str
    spread_type: str  # "put_spread", "call_spread", "iron_condor", "cash_secured_put", "covered_call"
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
class WheelSignal:
    """Signal for the wheel strategy (single-leg CSP or covered call)."""
    strategy_mode: str = "wheel"
    symbol: str = ""                     # underlying (e.g., "SPY")
    phase: str = ""                      # "csp" or "covered_call"
    option_contract: str = ""            # option symbol (e.g., "SPY250502P00540000")
    strike_price: float = 0.0
    contract_type: str = ""              # "put" or "call"
    expiration: date = field(default_factory=date.today)
    target_premium: float = 0.0          # credit received per contract
    quantity: int = 1                    # number of contracts
    delta: float = 0.0                   # delta at entry (for roll tracking)
    conviction_score: float = 0.0
    reasoning: list[str] = field(default_factory=list)
    regime_context: str = ""


@dataclass
class EvaluationResult:
    """Result of a signal generator evaluation, including signals and rejection reasons."""
    signals: list[TradeSignal] = field(default_factory=list)
    rejections: list[dict] = field(default_factory=list)
    wheel_signals: list[WheelSignal] = field(default_factory=list)

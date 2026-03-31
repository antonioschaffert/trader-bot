from dataclasses import dataclass, field
from datetime import date


@dataclass
class SpreadLeg:
    symbol: str
    strike_price: float
    contract_type: str  # "call" or "put"
    side: str  # "sell" or "buy"
    delta: float = 0.0


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

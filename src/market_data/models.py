from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class OptionContract:
    symbol: str
    underlying_symbol: str
    expiration_date: date
    strike_price: float
    contract_type: str  # "call" or "put"
    bid_price: float = 0.0
    ask_price: float = 0.0
    mid_price: float = 0.0
    open_interest: int = 0
    volume: int = 0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    implied_volatility: float = 0.0

    def __post_init__(self):
        if self.mid_price == 0.0 and (self.bid_price or self.ask_price):
            self.mid_price = (self.bid_price + self.ask_price) / 2


@dataclass
class OptionsChain:
    underlying_symbol: str
    calls: list[OptionContract] = field(default_factory=list)
    puts: list[OptionContract] = field(default_factory=list)

    def get_by_expiration(self, exp_date: date, contract_type: str) -> list[OptionContract]:
        contracts = self.calls if contract_type == "call" else self.puts
        return [c for c in contracts if c.expiration_date == exp_date]

    def get_expirations(self) -> list[date]:
        all_exp = {c.expiration_date for c in self.calls + self.puts}
        return sorted(all_exp)


@dataclass
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float = 0.0


@dataclass
class Indicators:
    rsi: float | None = None
    sma_50: float | None = None
    sma_20: float | None = None
    upper_bollinger: float | None = None
    lower_bollinger: float | None = None
    vwap: float | None = None


@dataclass
class MarketSnapshot:
    symbol: str
    price: float
    bars: list[Bar]
    options_chain: OptionsChain
    indicators: Indicators
    iv_rank: float | None = None
    high_of_day: float = 0.0
    low_of_day: float = 0.0
    open_price: float = 0.0
    prev_close: float = 0.0
    intraday_bars: list[Bar] = field(default_factory=list)
    intraday_indicators: Indicators | None = None

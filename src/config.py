import copy
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass
class SwingConfig:
    target_dte: list[int]
    short_strike_delta: list[float]
    spread_width: dict[str, int]
    min_premium: float
    iv_rank_threshold: int
    profit_target_pct: int
    # Quality / execution filters
    iv_percentile_threshold: int = 0
    min_open_interest: int = 0
    max_bid_ask_spread_pct: float = 0.0
    slippage_buffer_pct: float = 0.0
    sr_buffer_pct_min: float = 0.025
    allow_delta_fallback: bool = False


@dataclass
class ExhaustionConfig:
    enabled: bool
    target_dte: list[int]
    spread_width: dict[str, int]
    min_premium: float
    profit_target_pct: int
    stop_loss_multiplier: float
    time_window_start: str
    rsi_overbought: int
    rsi_oversold: int
    intraday_timeframe: str
    min_signals_required: int
    min_move_from_open_pct: float
    strong_move_pct: float
    close_by_eod: bool
    min_open_interest: int = 0
    max_bid_ask_spread_pct: float = 0.0
    slippage_buffer_pct: float = 0.0


@dataclass
class DrawdownConfig:
    loss_streak_reduce: int = 3
    loss_streak_halt: int = 5
    cooldown_minutes: int = 60
    drawdown_reduce_pct: float = 5.0
    drawdown_severe_pct: float = 10.0
    drawdown_halt_pct: float = 15.0


@dataclass
class RiskConfig:
    max_concurrent_spreads: int
    max_risk_per_trade_pct: int
    max_buying_power_usage_pct: int
    stop_loss_multiplier: float
    roll_delta_threshold: float
    dte_exit: int
    daily_loss_limit: int
    daily_income_target: int
    max_same_direction_per_symbol: int
    max_portfolio_delta_per_symbol: float
    # Enhanced risk settings
    max_correlated_same_direction: int = 4
    max_portfolio_vega: float = 500.0
    max_contracts_per_trade: int = 10
    slippage_buffer_pct: float = 0.10
    trailing_stop_activation_pct: int = 0     # 0 disables
    trailing_stop_giveback_pct: int = 50
    drawdown: DrawdownConfig = field(default_factory=DrawdownConfig)


@dataclass
class WheelConfig:
    enabled: bool = False
    symbols: list[str] = field(default_factory=lambda: ["SPY"])
    target_dte: list[int] = field(default_factory=lambda: [14, 35])
    csp_delta_range: list[float] = field(default_factory=lambda: [0.18, 0.42])
    cc_delta_range: list[float] = field(default_factory=lambda: [0.18, 0.42])
    min_open_interest: int = 200
    csp_strike_range_pct: float = 5.0
    cc_above_bollinger: bool = True
    max_buying_power_pct: float = 10.0
    roll_delta_multiplier: float = 2.0
    roll_profit_pct: float = 50.0
    profit_target_pct: int = 50
    max_positions: int = 2


@dataclass
class RegimeConfig:
    enabled: bool = True
    vix_symbol: str = "VIX"   # VIX proxy for Alpaca (uses VIXY or VIX bars)
    vix_low: float = 14.0
    vix_elevated: float = 20.0
    vix_crisis: float = 30.0
    adx_weak: float = 20.0
    adx_strong: float = 25.0
    halt_on_crisis_backwardation: bool = True
    halt_on_crisis_trending: bool = True


@dataclass
class ExecutionConfig:
    price_adjustment_interval: int
    price_adjustment_step: float
    fill_timeout: int


@dataclass
class ScheduleConfig:
    scan_interval_minutes: int
    market_hours_only: bool


@dataclass
class NotificationsConfig:
    sms_enabled: bool
    email_enabled: bool
    sms_events: list[str]
    email_events: list[str]


@dataclass
class AppConfig:
    symbols: list[str]
    swing: SwingConfig
    exhaustion: ExhaustionConfig
    risk: RiskConfig
    execution: ExecutionConfig
    schedule: ScheduleConfig
    notifications: NotificationsConfig
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    wheel: WheelConfig = field(default_factory=WheelConfig)

    # From environment variables
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    alpaca_paper: bool = True
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "auto_trader"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    twilio_to_number: str = ""
    email_host: str = ""
    email_port: int = 587
    email_username: str = ""
    email_password: str = ""
    email_to: str = ""


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge override into a copy of base. Does NOT mutate base."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _build_risk_config(raw_risk: dict) -> RiskConfig:
    """Build RiskConfig, extracting nested drawdown config."""
    dd_raw = raw_risk.pop("drawdown", {})
    dd = DrawdownConfig(**dd_raw) if dd_raw else DrawdownConfig()
    return RiskConfig(**raw_risk, drawdown=dd)


def load_config(config_path: str = "config/config.yaml", db=None) -> AppConfig:
    env_path = Path(config_path).parent / ".env"
    if env_path.exists():
        load_dotenv(str(env_path))

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    if db is not None:
        settings = db.get_settings()
        if settings:
            settings.pop("updated_at", None)
            raw = _deep_merge(raw, settings)
        else:
            db.seed_settings(raw)

    # Build regime config with defaults for missing fields
    regime_raw = raw.get("regime", {})
    regime = RegimeConfig(**{k: v for k, v in regime_raw.items() if k in RegimeConfig.__dataclass_fields__})

    # Build wheel config with defaults for missing fields
    wheel_raw = raw.get("wheel", {})
    wheel = WheelConfig(**{k: v for k, v in wheel_raw.items() if k in WheelConfig.__dataclass_fields__})

    # Build risk config with nested drawdown
    risk_raw = dict(raw["risk"])
    risk = _build_risk_config(risk_raw)

    return AppConfig(
        symbols=raw["symbols"],
        swing=SwingConfig(**raw["swing"]),
        exhaustion=ExhaustionConfig(**raw["exhaustion"]),
        risk=risk,
        execution=ExecutionConfig(**raw["execution"]),
        schedule=ScheduleConfig(**raw["schedule"]),
        notifications=NotificationsConfig(**raw["notifications"]),
        regime=regime,
        wheel=wheel,
        alpaca_api_key=os.getenv("ALPACA_API_KEY", ""),
        alpaca_api_secret=os.getenv("ALPACA_API_SECRET", ""),
        alpaca_paper=os.getenv("ALPACA_PAPER", "true").lower() == "true",
        mongodb_uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        mongodb_db_name=os.getenv("MONGODB_DB_NAME", "auto_trader"),
        twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
        twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
        twilio_from_number=os.getenv("TWILIO_FROM_NUMBER", ""),
        twilio_to_number=os.getenv("TWILIO_TO_NUMBER", ""),
        email_host=os.getenv("EMAIL_HOST", ""),
        email_port=int(os.getenv("EMAIL_PORT", "587")),
        email_username=os.getenv("EMAIL_USERNAME", ""),
        email_password=os.getenv("EMAIL_PASSWORD", ""),
        email_to=os.getenv("EMAIL_TO", ""),
    )

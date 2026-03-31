# Auto-Trader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully automated Python bot that sells SPY/QQQ option spreads via Alpaca, using two concurrent strategies (swing 7-10 DTE + intraday exhaustion 1-2 DTE) with risk management, position tracking, and notifications.

**Architecture:** Event-driven modular application. Modules communicate through an in-process pub/sub event bus. The scheduler triggers scans during market hours, market data feeds into signal generators, signals pass through risk checks, validated signals get executed via Alpaca, and positions are tracked and managed through their lifecycle.

**Tech Stack:** Python 3.11+, alpaca-py, pandas, ta, pymongo, twilio, pyyaml, python-dotenv, apscheduler, pytest

---

## File Structure

```
auto-trader/
├── config/
│   ├── config.yaml              # all tunable strategy/risk/execution parameters
│   └── .env.example             # template for secrets
├── src/
│   ├── __init__.py
│   ├── main.py                  # entry point — wires modules and starts scheduler
│   ├── event_bus.py             # lightweight in-process pub/sub
│   ├── config.py                # loads YAML config + .env, exposes typed settings
│   ├── scheduler.py             # APScheduler-based scan loop, market-hours aware
│   ├── market_data/
│   │   ├── __init__.py
│   │   ├── client.py            # wraps Alpaca data APIs (stocks + options)
│   │   ├── indicators.py        # computes RSI, MA, bollinger, VWAP from bars
│   │   └── models.py            # dataclasses: OptionContract, OptionsChain, Bar, MarketSnapshot
│   ├── signals/
│   │   ├── __init__.py
│   │   ├── models.py            # TradeSignal dataclass
│   │   ├── swing.py             # swing strategy (7-10 DTE)
│   │   └── exhaustion.py        # intraday exhaustion strategy (1-2 DTE)
│   ├── risk/
│   │   ├── __init__.py
│   │   └── manager.py           # pre-trade validation + post-trade management rules
│   ├── execution/
│   │   ├── __init__.py
│   │   └── executor.py          # builds + submits multi-leg orders, monitors fills
│   ├── positions/
│   │   ├── __init__.py
│   │   └── manager.py           # tracks open spreads, syncs with Alpaca, emits events
│   ├── notifications/
│   │   ├── __init__.py
│   │   ├── sms.py               # Twilio SMS alerts
│   │   └── email_notifier.py    # SMTP email summaries
│   └── db/
│       ├── __init__.py
│       └── mongo.py             # MongoDB connection, collections, CRUD helpers
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # shared fixtures (event bus, config, mock Alpaca client)
│   ├── test_event_bus.py
│   ├── test_config.py
│   ├── test_db.py
│   ├── test_market_data/
│   │   ├── __init__.py
│   │   ├── test_client.py
│   │   └── test_indicators.py
│   ├── test_signals/
│   │   ├── __init__.py
│   │   ├── test_swing.py
│   │   └── test_exhaustion.py
│   ├── test_risk/
│   │   ├── __init__.py
│   │   └── test_manager.py
│   ├── test_execution/
│   │   ├── __init__.py
│   │   └── test_executor.py
│   ├── test_positions/
│   │   ├── __init__.py
│   │   └── test_manager.py
│   └── test_notifications/
│       ├── __init__.py
│       ├── test_sms.py
│       └── test_email.py
├── .gitignore
├── pytest.ini
└── requirements.txt
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `.gitignore`
- Create: `config/config.yaml`
- Create: `config/.env.example`
- Create: all `__init__.py` files for packages

- [ ] **Step 1: Create `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/
*.egg
.env
config/.env
.venv/
venv/
.pytest_cache/
.mypy_cache/
*.log
```

- [ ] **Step 2: Create `requirements.txt`**

```
alpaca-py>=0.35.0
pandas>=2.2.0
ta>=0.11.0
pymongo>=4.9.0
twilio>=9.0.0
pyyaml>=6.0.2
python-dotenv>=1.0.1
APScheduler>=3.10.4
pytest>=8.3.0
pytest-mock>=3.14.0
```

- [ ] **Step 3: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 4: Create `config/config.yaml`**

```yaml
symbols: ["SPY", "QQQ"]

swing:
  target_dte: [7, 10]
  short_strike_delta: [0.15, 0.30]
  spread_width:
    SPY: 5
    QQQ: 3
  min_premium: 0.50
  iv_rank_threshold: 30
  profit_target_pct: 50

exhaustion:
  enabled: true
  target_dte: [1, 2]
  spread_width:
    SPY: 5
    QQQ: 3
  min_premium: 0.25
  profit_target_pct: 20
  stop_loss_multiplier: 1.5
  time_window_start: "11:00"
  rsi_overbought: 70
  rsi_oversold: 30
  intraday_timeframe: "5min"
  min_signals_required: 2
  close_by_eod: true

risk:
  max_concurrent_spreads: 10
  max_risk_per_trade_pct: 5
  max_buying_power_usage_pct: 60
  stop_loss_multiplier: 2.0
  roll_delta_threshold: 0.50
  dte_exit: 1
  daily_loss_limit: 1000
  daily_income_target: 500
  max_same_direction_per_symbol: 3
  max_portfolio_delta_per_symbol: 0.30

execution:
  price_adjustment_interval: 30
  price_adjustment_step: 0.01
  fill_timeout: 300

schedule:
  scan_interval_minutes: 5
  market_hours_only: true

notifications:
  sms_enabled: true
  email_enabled: true
  sms_events: ["fill", "stop_loss", "roll", "circuit_breaker", "error"]
  email_events: ["daily_summary", "weekly_recap"]
```

- [ ] **Step 5: Create `config/.env.example`**

```env
ALPACA_API_KEY=your_api_key_here
ALPACA_API_SECRET=your_api_secret_here
ALPACA_PAPER=true

MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=auto_trader

TWILIO_ACCOUNT_SID=your_sid_here
TWILIO_AUTH_TOKEN=your_token_here
TWILIO_FROM_NUMBER=+1234567890
TWILIO_TO_NUMBER=+1234567890

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_TO=your_email@gmail.com
```

- [ ] **Step 6: Create all `__init__.py` files**

Create empty `__init__.py` in:
- `src/`
- `src/market_data/`
- `src/signals/`
- `src/risk/`
- `src/execution/`
- `src/positions/`
- `src/notifications/`
- `src/db/`
- `tests/`
- `tests/test_market_data/`
- `tests/test_signals/`
- `tests/test_risk/`
- `tests/test_execution/`
- `tests/test_positions/`
- `tests/test_notifications/`

- [ ] **Step 7: Install dependencies and verify**

Run: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
Expected: All packages install successfully

- [ ] **Step 8: Verify pytest runs**

Run: `pytest --co`
Expected: "no tests ran" (no test files yet, but pytest discovers the test directory)

- [ ] **Step 9: Commit**

```bash
git add .gitignore requirements.txt pytest.ini config/ src/ tests/
git commit -m "feat: project scaffolding with dependencies and config"
```

---

### Task 2: Event Bus

**Files:**
- Create: `src/event_bus.py`
- Create: `tests/test_event_bus.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/test_event_bus.py`

```python
from src.event_bus import EventBus


def test_subscribe_and_publish():
    bus = EventBus()
    received = []
    bus.subscribe("TestEvent", lambda data: received.append(data))
    bus.publish("TestEvent", {"key": "value"})
    assert received == [{"key": "value"}]


def test_multiple_subscribers():
    bus = EventBus()
    results_a = []
    results_b = []
    bus.subscribe("TestEvent", lambda data: results_a.append(data))
    bus.subscribe("TestEvent", lambda data: results_b.append(data))
    bus.publish("TestEvent", {"x": 1})
    assert results_a == [{"x": 1}]
    assert results_b == [{"x": 1}]


def test_publish_no_subscribers():
    bus = EventBus()
    bus.publish("NoOneListening", {"x": 1})  # should not raise


def test_different_events_isolated():
    bus = EventBus()
    received_a = []
    received_b = []
    bus.subscribe("EventA", lambda data: received_a.append(data))
    bus.subscribe("EventB", lambda data: received_b.append(data))
    bus.publish("EventA", "hello")
    assert received_a == ["hello"]
    assert received_b == []


def test_unsubscribe():
    bus = EventBus()
    received = []
    handler = lambda data: received.append(data)
    bus.subscribe("TestEvent", handler)
    bus.unsubscribe("TestEvent", handler)
    bus.publish("TestEvent", "should not appear")
    assert received == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_event_bus.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.event_bus'`

- [ ] **Step 3: Implement EventBus**

File: `src/event_bus.py`

```python
import logging
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)

Handler = Callable[[Any], None]


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._subscribers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: Handler) -> None:
        self._subscribers[event_name].remove(handler)

    def publish(self, event_name: str, data: Any = None) -> None:
        for handler in self._subscribers.get(event_name, []):
            try:
                handler(data)
            except Exception:
                logger.exception(f"Error in handler for event '{event_name}'")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_event_bus.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/event_bus.py tests/test_event_bus.py
git commit -m "feat: add in-process pub/sub event bus"
```

---

### Task 3: Config Loader

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/test_config.py`

```python
import os
import tempfile
from pathlib import Path

import yaml

from src.config import load_config, AppConfig


def _write_config(tmp_dir: Path, overrides: dict | None = None) -> Path:
    base = {
        "symbols": ["SPY", "QQQ"],
        "swing": {
            "target_dte": [7, 10],
            "short_strike_delta": [0.15, 0.30],
            "spread_width": {"SPY": 5, "QQQ": 3},
            "min_premium": 0.50,
            "iv_rank_threshold": 30,
            "profit_target_pct": 50,
        },
        "exhaustion": {
            "enabled": True,
            "target_dte": [1, 2],
            "spread_width": {"SPY": 5, "QQQ": 3},
            "min_premium": 0.25,
            "profit_target_pct": 20,
            "stop_loss_multiplier": 1.5,
            "time_window_start": "11:00",
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "intraday_timeframe": "5min",
            "min_signals_required": 2,
            "close_by_eod": True,
        },
        "risk": {
            "max_concurrent_spreads": 10,
            "max_risk_per_trade_pct": 5,
            "max_buying_power_usage_pct": 60,
            "stop_loss_multiplier": 2.0,
            "roll_delta_threshold": 0.50,
            "dte_exit": 1,
            "daily_loss_limit": 1000,
            "daily_income_target": 500,
            "max_same_direction_per_symbol": 3,
            "max_portfolio_delta_per_symbol": 0.30,
        },
        "execution": {
            "price_adjustment_interval": 30,
            "price_adjustment_step": 0.01,
            "fill_timeout": 300,
        },
        "schedule": {
            "scan_interval_minutes": 5,
            "market_hours_only": True,
        },
        "notifications": {
            "sms_enabled": True,
            "email_enabled": True,
            "sms_events": ["fill", "stop_loss"],
            "email_events": ["daily_summary"],
        },
    }
    if overrides:
        base.update(overrides)
    config_path = tmp_dir / "config.yaml"
    config_path.write_text(yaml.dump(base))
    return config_path


def test_load_config_returns_app_config():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_config(Path(tmp))
        cfg = load_config(str(path))
        assert isinstance(cfg, AppConfig)


def test_load_config_symbols():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_config(Path(tmp))
        cfg = load_config(str(path))
        assert cfg.symbols == ["SPY", "QQQ"]


def test_load_config_swing_values():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_config(Path(tmp))
        cfg = load_config(str(path))
        assert cfg.swing.target_dte == [7, 10]
        assert cfg.swing.min_premium == 0.50
        assert cfg.swing.spread_width == {"SPY": 5, "QQQ": 3}


def test_load_config_exhaustion_values():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_config(Path(tmp))
        cfg = load_config(str(path))
        assert cfg.exhaustion.enabled is True
        assert cfg.exhaustion.profit_target_pct == 20
        assert cfg.exhaustion.min_signals_required == 2


def test_load_config_risk_values():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_config(Path(tmp))
        cfg = load_config(str(path))
        assert cfg.risk.daily_income_target == 500
        assert cfg.risk.max_concurrent_spreads == 10


def test_load_config_env_vars(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "test_key")
    monkeypatch.setenv("ALPACA_API_SECRET", "test_secret")
    monkeypatch.setenv("ALPACA_PAPER", "true")
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGODB_DB_NAME", "test_db")
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_config(Path(tmp))
        cfg = load_config(str(path))
        assert cfg.alpaca_api_key == "test_key"
        assert cfg.alpaca_api_secret == "test_secret"
        assert cfg.alpaca_paper is True
        assert cfg.mongodb_uri == "mongodb://localhost:27017"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement config loader**

File: `src/config.py`

```python
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
    close_by_eod: bool


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


def load_config(config_path: str = "config/config.yaml") -> AppConfig:
    env_path = Path(config_path).parent / ".env"
    if env_path.exists():
        load_dotenv(str(env_path))

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    return AppConfig(
        symbols=raw["symbols"],
        swing=SwingConfig(**raw["swing"]),
        exhaustion=ExhaustionConfig(**raw["exhaustion"]),
        risk=RiskConfig(**raw["risk"]),
        execution=ExecutionConfig(**raw["execution"]),
        schedule=ScheduleConfig(**raw["schedule"]),
        notifications=NotificationsConfig(**raw["notifications"]),
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add YAML + env config loader with typed dataclasses"
```

---

### Task 4: MongoDB Data Access Layer

**Files:**
- Create: `src/db/mongo.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/test_db.py`

```python
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.db.mongo import MongoStore


@patch("src.db.mongo.MongoClient")
def test_mongo_store_connects(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    store = MongoStore("mongodb://localhost:27017", "test_db")
    mock_client_cls.assert_called_once_with("mongodb://localhost:27017")
    assert store.db == mock_client["test_db"]


@patch("src.db.mongo.MongoClient")
def test_save_iv_record(mock_client_cls):
    mock_db = MagicMock()
    mock_client_cls.return_value.__getitem__ = MagicMock(return_value=mock_db)
    store = MongoStore("mongodb://localhost:27017", "test_db")
    record = {"symbol": "SPY", "iv": 0.25, "timestamp": datetime.now(timezone.utc)}
    store.save_iv_record(record)
    mock_db["iv_history"].insert_one.assert_called_once_with(record)


@patch("src.db.mongo.MongoClient")
def test_get_iv_history(mock_client_cls):
    mock_db = MagicMock()
    mock_client_cls.return_value.__getitem__ = MagicMock(return_value=mock_db)
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = [
        {"symbol": "SPY", "iv": 0.20},
        {"symbol": "SPY", "iv": 0.25},
    ]
    mock_db["iv_history"].find.return_value = mock_cursor
    store = MongoStore("mongodb://localhost:27017", "test_db")
    since = datetime(2025, 1, 1, tzinfo=timezone.utc)
    result = store.get_iv_history("SPY", since)
    mock_db["iv_history"].find.assert_called_once_with(
        {"symbol": "SPY", "timestamp": {"$gte": since}}
    )
    assert len(result) == 2


@patch("src.db.mongo.MongoClient")
def test_save_trade(mock_client_cls):
    mock_db = MagicMock()
    mock_client_cls.return_value.__getitem__ = MagicMock(return_value=mock_db)
    store = MongoStore("mongodb://localhost:27017", "test_db")
    trade = {"symbol": "SPY", "type": "put_spread", "premium": 1.50}
    store.save_trade(trade)
    mock_db["trades"].insert_one.assert_called_once_with(trade)


@patch("src.db.mongo.MongoClient")
def test_get_todays_trades(mock_client_cls):
    mock_db = MagicMock()
    mock_client_cls.return_value.__getitem__ = MagicMock(return_value=mock_db)
    mock_db["trades"].find.return_value = [
        {"symbol": "SPY", "pnl": 50.0},
        {"symbol": "QQQ", "pnl": -20.0},
    ]
    store = MongoStore("mongodb://localhost:27017", "test_db")
    result = store.get_todays_trades()
    assert len(result) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement MongoStore**

File: `src/db/mongo.py`

```python
import logging
from datetime import datetime, time, timezone

from pymongo import MongoClient

logger = logging.getLogger(__name__)


class MongoStore:
    def __init__(self, uri: str, db_name: str):
        self._client = MongoClient(uri)
        self.db = self._client[db_name]

    def save_iv_record(self, record: dict) -> None:
        self.db["iv_history"].insert_one(record)

    def get_iv_history(self, symbol: str, since: datetime) -> list[dict]:
        cursor = self.db["iv_history"].find(
            {"symbol": symbol, "timestamp": {"$gte": since}}
        )
        return list(cursor.sort("timestamp", 1))

    def save_trade(self, trade: dict) -> None:
        self.db["trades"].insert_one(trade)

    def update_trade(self, trade_id: str, update: dict) -> None:
        self.db["trades"].update_one({"_id": trade_id}, {"$set": update})

    def get_todays_trades(self) -> list[dict]:
        today_start = datetime.combine(
            datetime.now(timezone.utc).date(), time.min
        ).replace(tzinfo=timezone.utc)
        return list(self.db["trades"].find({"opened_at": {"$gte": today_start}}))

    def save_options_snapshot(self, snapshot: dict) -> None:
        self.db["options_snapshots"].insert_one(snapshot)

    def save_order_log(self, order: dict) -> None:
        self.db["order_logs"].insert_one(order)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/db/mongo.py tests/test_db.py
git commit -m "feat: add MongoDB data access layer"
```

---

### Task 5: Market Data Models

**Files:**
- Create: `src/market_data/models.py`

- [ ] **Step 1: Create market data models**

File: `src/market_data/models.py`

```python
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
    intraday_bars: list[Bar] = field(default_factory=list)
    intraday_indicators: Indicators | None = None
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from src.market_data.models import MarketSnapshot, OptionContract, OptionsChain, Bar, Indicators; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/market_data/models.py
git commit -m "feat: add market data models (OptionContract, OptionsChain, Bar, MarketSnapshot)"
```

---

### Task 6: Market Data Client

**Files:**
- Create: `src/market_data/client.py`
- Create: `tests/test_market_data/test_client.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write shared test fixtures**

File: `tests/conftest.py`

```python
import pytest

from src.event_bus import EventBus


@pytest.fixture
def event_bus():
    return EventBus()
```

- [ ] **Step 2: Write the failing tests**

File: `tests/test_market_data/test_client.py`

```python
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.market_data.client import MarketDataClient
from src.market_data.models import OptionsChain, OptionContract, Bar


@pytest.fixture
def mock_trading_client():
    return MagicMock()


@pytest.fixture
def mock_stock_client():
    return MagicMock()


@pytest.fixture
def mock_option_client():
    return MagicMock()


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_trading_client, mock_stock_client, mock_option_client, mock_db):
    return MarketDataClient(
        trading_client=mock_trading_client,
        stock_client=mock_stock_client,
        option_client=mock_option_client,
        db=mock_db,
        symbols=["SPY"],
    )


def test_get_options_chain_returns_chain(client, mock_trading_client):
    mock_contract = MagicMock()
    mock_contract.symbol = "SPY260410P00500000"
    mock_contract.underlying_symbol = "SPY"
    mock_contract.expiration_date = date(2026, 4, 10)
    mock_contract.strike_price = 500.0
    mock_contract.type = "put"
    mock_contract.open_interest = 1000
    mock_contract.close_price = 2.50

    mock_response = MagicMock()
    mock_response.option_contracts = [mock_contract]
    mock_trading_client.get_option_contracts.return_value = mock_response

    chain = client.get_options_chain("SPY", min_dte=1, max_dte=10)
    assert isinstance(chain, OptionsChain)
    assert chain.underlying_symbol == "SPY"


def test_get_daily_bars_returns_bars(client, mock_stock_client):
    mock_bar = MagicMock()
    mock_bar.timestamp = datetime(2026, 3, 30, tzinfo=timezone.utc)
    mock_bar.open = 500.0
    mock_bar.high = 505.0
    mock_bar.low = 498.0
    mock_bar.close = 503.0
    mock_bar.volume = 1000000
    mock_bar.vwap = 501.5

    mock_stock_client.get_stock_bars.return_value = {"SPY": [mock_bar]}

    bars = client.get_daily_bars("SPY", limit=50)
    assert len(bars) == 1
    assert isinstance(bars[0], Bar)
    assert bars[0].close == 503.0


def test_get_latest_price(client, mock_stock_client):
    mock_quote = MagicMock()
    mock_quote.ask_price = 500.50
    mock_quote.bid_price = 500.40
    mock_stock_client.get_stock_latest_quote.return_value = {"SPY": mock_quote}

    price = client.get_latest_price("SPY")
    assert price == pytest.approx(500.45, abs=0.01)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_market_data/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement MarketDataClient**

File: `src/market_data/client.py`

```python
import logging
from datetime import date, datetime, timedelta, timezone

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import (
    StockBarsRequest,
    StockLatestQuoteRequest,
    OptionChainRequest,
    OptionLatestQuoteRequest,
)
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOptionContractsRequest
from alpaca.trading.enums import AssetStatus

from src.db.mongo import MongoStore
from src.market_data.models import Bar, OptionContract, OptionsChain

logger = logging.getLogger(__name__)


class MarketDataClient:
    def __init__(
        self,
        trading_client: TradingClient,
        stock_client: StockHistoricalDataClient,
        option_client: OptionHistoricalDataClient,
        db: MongoStore,
        symbols: list[str],
    ):
        self._trading = trading_client
        self._stock = stock_client
        self._option = option_client
        self._db = db
        self._symbols = symbols

    def get_options_chain(
        self, symbol: str, min_dte: int, max_dte: int
    ) -> OptionsChain:
        today = date.today()
        min_exp = today + timedelta(days=min_dte)
        max_exp = today + timedelta(days=max_dte)

        req = GetOptionContractsRequest(
            underlying_symbols=[symbol],
            status=AssetStatus.ACTIVE,
            expiration_date_gte=min_exp,
            expiration_date_lte=max_exp,
        )
        response = self._trading.get_option_contracts(req)

        calls = []
        puts = []
        for c in response.option_contracts:
            contract = OptionContract(
                symbol=c.symbol,
                underlying_symbol=c.underlying_symbol,
                expiration_date=c.expiration_date,
                strike_price=float(c.strike_price),
                contract_type=str(c.type),
                open_interest=int(c.open_interest or 0),
            )
            if contract.contract_type == "call":
                calls.append(contract)
            else:
                puts.append(contract)

        chain = OptionsChain(
            underlying_symbol=symbol, calls=calls, puts=puts
        )
        return chain

    def enrich_chain_with_quotes(self, chain: OptionsChain) -> None:
        all_symbols = [c.symbol for c in chain.calls + chain.puts]
        if not all_symbols:
            return

        for batch_start in range(0, len(all_symbols), 100):
            batch = all_symbols[batch_start : batch_start + 100]
            req = OptionLatestQuoteRequest(symbol_or_symbols=batch)
            quotes = self._option.get_option_latest_quote(req)

            contract_map = {
                c.symbol: c for c in chain.calls + chain.puts
            }
            for sym, quote in quotes.items():
                if sym in contract_map:
                    contract_map[sym].bid_price = float(quote.bid_price or 0)
                    contract_map[sym].ask_price = float(quote.ask_price or 0)
                    contract_map[sym].mid_price = (
                        contract_map[sym].bid_price + contract_map[sym].ask_price
                    ) / 2

    def get_daily_bars(self, symbol: str, limit: int = 60) -> list[Bar]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=limit * 2)  # buffer for weekends/holidays
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            limit=limit,
        )
        response = self._stock.get_stock_bars(req)
        raw_bars = response.get(symbol, [])

        return [
            Bar(
                timestamp=b.timestamp,
                open=float(b.open),
                high=float(b.high),
                low=float(b.low),
                close=float(b.close),
                volume=int(b.volume),
                vwap=float(getattr(b, "vwap", 0) or 0),
            )
            for b in raw_bars
        ]

    def get_intraday_bars(
        self, symbol: str, timeframe_minutes: int = 5, limit: int = 78
    ) -> list[Bar]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=8)
        tf = TimeFrame.Minute if timeframe_minutes == 1 else TimeFrame(timeframe_minutes, "Min")
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start,
            end=end,
            limit=limit,
        )
        response = self._stock.get_stock_bars(req)
        raw_bars = response.get(symbol, [])

        return [
            Bar(
                timestamp=b.timestamp,
                open=float(b.open),
                high=float(b.high),
                low=float(b.low),
                close=float(b.close),
                volume=int(b.volume),
                vwap=float(getattr(b, "vwap", 0) or 0),
            )
            for b in raw_bars
        ]

    def get_latest_price(self, symbol: str) -> float:
        req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        quotes = self._stock.get_stock_latest_quote(req)
        quote = quotes[symbol]
        return (float(quote.ask_price) + float(quote.bid_price)) / 2
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_market_data/test_client.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/market_data/client.py tests/test_market_data/test_client.py tests/conftest.py
git commit -m "feat: add Alpaca market data client with options chain and bar fetching"
```

---

### Task 7: Technical Indicators

**Files:**
- Create: `src/market_data/indicators.py`
- Create: `tests/test_market_data/test_indicators.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/test_market_data/test_indicators.py`

```python
from datetime import datetime, timezone

import pytest

from src.market_data.indicators import compute_indicators, compute_iv_rank
from src.market_data.models import Bar, Indicators


def _make_bars(closes: list[float]) -> list[Bar]:
    return [
        Bar(
            timestamp=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
            open=c - 0.5,
            high=c + 1.0,
            low=c - 1.0,
            close=c,
            volume=1000000,
            vwap=c,
        )
        for i, c in enumerate(closes)
    ]


def test_compute_indicators_returns_indicators():
    # 60 bars is enough for 50 SMA and 14-period RSI
    bars = _make_bars([100 + i * 0.5 for i in range(60)])
    result = compute_indicators(bars)
    assert isinstance(result, Indicators)


def test_compute_indicators_sma_50():
    closes = [100 + i * 0.5 for i in range(60)]
    bars = _make_bars(closes)
    result = compute_indicators(bars)
    assert result.sma_50 is not None
    assert result.sma_50 == pytest.approx(sum(closes[-50:]) / 50, abs=0.01)


def test_compute_indicators_rsi_not_none():
    bars = _make_bars([100 + i * 0.5 for i in range(60)])
    result = compute_indicators(bars)
    assert result.rsi is not None
    assert 0 <= result.rsi <= 100


def test_compute_indicators_bollinger_bands():
    bars = _make_bars([100 + i * 0.5 for i in range(60)])
    result = compute_indicators(bars)
    assert result.upper_bollinger is not None
    assert result.lower_bollinger is not None
    assert result.upper_bollinger > result.lower_bollinger


def test_compute_indicators_too_few_bars():
    bars = _make_bars([100, 101, 102])
    result = compute_indicators(bars)
    assert result.sma_50 is None  # not enough data


def test_compute_iv_rank():
    # Current IV at 0.30, historical range 0.15 to 0.45
    history = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45]
    rank = compute_iv_rank(0.30, history)
    # (0.30 - 0.15) / (0.45 - 0.15) = 0.15 / 0.30 = 50%
    assert rank == pytest.approx(50.0, abs=0.1)


def test_compute_iv_rank_at_low():
    history = [0.15, 0.20, 0.25, 0.30]
    rank = compute_iv_rank(0.15, history)
    assert rank == pytest.approx(0.0, abs=0.1)


def test_compute_iv_rank_empty_history():
    rank = compute_iv_rank(0.25, [])
    assert rank is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_market_data/test_indicators.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement indicators**

File: `src/market_data/indicators.py`

```python
import pandas as pd
import ta

from src.market_data.models import Bar, Indicators


def compute_indicators(bars: list[Bar]) -> Indicators:
    if len(bars) < 15:
        return Indicators()

    df = pd.DataFrame(
        {
            "close": [b.close for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "volume": [b.volume for b in bars],
        }
    )

    result = Indicators()

    if len(df) >= 50:
        result.sma_50 = df["close"].rolling(50).mean().iloc[-1]

    if len(df) >= 20:
        result.sma_20 = df["close"].rolling(20).mean().iloc[-1]
        bb = ta.volatility.BollingerBands(close=df["close"], window=20, window_dev=2)
        result.upper_bollinger = bb.bollinger_hband().iloc[-1]
        result.lower_bollinger = bb.bollinger_lband().iloc[-1]

    rsi_indicator = ta.momentum.RSIIndicator(close=df["close"], window=14)
    rsi_series = rsi_indicator.rsi()
    if not rsi_series.isna().iloc[-1]:
        result.rsi = rsi_series.iloc[-1]

    if bars[-1].vwap:
        result.vwap = bars[-1].vwap

    return result


def compute_iv_rank(
    current_iv: float, iv_history: list[float]
) -> float | None:
    if not iv_history:
        return None
    iv_min = min(iv_history)
    iv_max = max(iv_history)
    if iv_max == iv_min:
        return 50.0
    return ((current_iv - iv_min) / (iv_max - iv_min)) * 100
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_market_data/test_indicators.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/market_data/indicators.py tests/test_market_data/test_indicators.py
git commit -m "feat: add technical indicators (RSI, SMA, bollinger) and IV rank"
```

---

### Task 8: Signal Models + Swing Signal Generator

**Files:**
- Create: `src/signals/models.py`
- Create: `src/signals/swing.py`
- Create: `tests/test_signals/test_swing.py`

- [ ] **Step 1: Create signal models**

File: `src/signals/models.py`

```python
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
```

- [ ] **Step 2: Write the failing tests for swing generator**

File: `tests/test_signals/test_swing.py`

```python
from datetime import date, datetime, timezone

import pytest

from src.event_bus import EventBus
from src.market_data.models import (
    Bar,
    Indicators,
    MarketSnapshot,
    OptionContract,
    OptionsChain,
)
from src.signals.models import TradeSignal
from src.signals.swing import SwingSignalGenerator


@pytest.fixture
def swing_config():
    return {
        "target_dte": [7, 10],
        "short_strike_delta": [0.15, 0.30],
        "spread_width": {"SPY": 5, "QQQ": 3},
        "min_premium": 0.50,
        "iv_rank_threshold": 30,
        "profit_target_pct": 50,
    }


def _make_put_contract(strike, delta, bid=1.50, ask=1.70, oi=500):
    return OptionContract(
        symbol=f"SPY260410P{int(strike*1000):08d}",
        underlying_symbol="SPY",
        expiration_date=date(2026, 4, 10),
        strike_price=strike,
        contract_type="put",
        bid_price=bid,
        ask_price=ask,
        delta=delta,
        open_interest=oi,
        volume=100,
    )


def _make_call_contract(strike, delta, bid=1.50, ask=1.70, oi=500):
    return OptionContract(
        symbol=f"SPY260410C{int(strike*1000):08d}",
        underlying_symbol="SPY",
        expiration_date=date(2026, 4, 10),
        strike_price=strike,
        contract_type="call",
        bid_price=bid,
        ask_price=ask,
        delta=delta,
        open_interest=oi,
        volume=100,
    )


def _make_snapshot(price, rsi, sma_50, iv_rank, puts=None, calls=None):
    return MarketSnapshot(
        symbol="SPY",
        price=price,
        bars=[],
        options_chain=OptionsChain(
            underlying_symbol="SPY",
            puts=puts or [],
            calls=calls or [],
        ),
        indicators=Indicators(rsi=rsi, sma_50=sma_50),
        iv_rank=iv_rank,
    )


def test_bullish_generates_put_spread(swing_config, event_bus):
    # Price above SMA, RSI not overbought -> bullish -> sell put spread
    puts = [
        _make_put_contract(495.0, -0.20, bid=1.50, ask=1.70),
        _make_put_contract(490.0, -0.10, bid=0.60, ask=0.80),
    ]
    snapshot = _make_snapshot(
        price=500.0, rsi=55.0, sma_50=495.0, iv_rank=40.0, puts=puts
    )
    gen = SwingSignalGenerator(swing_config, event_bus)
    signals = gen.evaluate(snapshot)
    assert len(signals) >= 1
    signal = signals[0]
    assert signal.spread_type == "put_spread"
    assert signal.strategy_mode == "swing"
    assert signal.profit_target_pct == 50


def test_bearish_generates_call_spread(swing_config, event_bus):
    # Price below SMA, RSI not oversold -> bearish -> sell call spread
    calls = [
        _make_call_contract(505.0, 0.20, bid=1.50, ask=1.70),
        _make_call_contract(510.0, 0.10, bid=0.60, ask=0.80),
    ]
    snapshot = _make_snapshot(
        price=490.0, rsi=45.0, sma_50=495.0, iv_rank=40.0, calls=calls
    )
    gen = SwingSignalGenerator(swing_config, event_bus)
    signals = gen.evaluate(snapshot)
    assert len(signals) >= 1
    assert signals[0].spread_type == "call_spread"


def test_low_iv_rank_no_signal(swing_config, event_bus):
    # IV rank below threshold -> no trades
    puts = [
        _make_put_contract(495.0, -0.20),
        _make_put_contract(490.0, -0.10),
    ]
    snapshot = _make_snapshot(
        price=500.0, rsi=55.0, sma_50=495.0, iv_rank=20.0, puts=puts
    )
    gen = SwingSignalGenerator(swing_config, event_bus)
    signals = gen.evaluate(snapshot)
    assert len(signals) == 0


def test_signal_has_two_legs(swing_config, event_bus):
    puts = [
        _make_put_contract(495.0, -0.20, bid=1.50, ask=1.70),
        _make_put_contract(490.0, -0.10, bid=0.60, ask=0.80),
    ]
    snapshot = _make_snapshot(
        price=500.0, rsi=55.0, sma_50=495.0, iv_rank=40.0, puts=puts
    )
    gen = SwingSignalGenerator(swing_config, event_bus)
    signals = gen.evaluate(snapshot)
    assert len(signals[0].legs) == 2
    sides = {leg.side for leg in signals[0].legs}
    assert sides == {"sell", "buy"}


def test_min_premium_filter(swing_config, event_bus):
    # Premium too low -> no signal
    puts = [
        _make_put_contract(495.0, -0.20, bid=0.20, ask=0.30),
        _make_put_contract(490.0, -0.10, bid=0.10, ask=0.15),
    ]
    snapshot = _make_snapshot(
        price=500.0, rsi=55.0, sma_50=495.0, iv_rank=40.0, puts=puts
    )
    gen = SwingSignalGenerator(swing_config, event_bus)
    signals = gen.evaluate(snapshot)
    assert len(signals) == 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_signals/test_swing.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement SwingSignalGenerator**

File: `src/signals/swing.py`

```python
import logging

from src.event_bus import EventBus
from src.market_data.models import MarketSnapshot, OptionContract
from src.signals.models import SpreadLeg, TradeSignal

logger = logging.getLogger(__name__)


class SwingSignalGenerator:
    def __init__(self, config: dict, event_bus: EventBus):
        self._config = config
        self._bus = event_bus

    def evaluate(self, snapshot: MarketSnapshot) -> list[TradeSignal]:
        signals = []

        # 1. IV rank filter
        if snapshot.iv_rank is None or snapshot.iv_rank < self._config["iv_rank_threshold"]:
            return signals

        # 2. Determine directional bias
        bias = self._get_bias(snapshot)

        # 3. Generate signals based on bias
        if bias in ("bullish", "neutral"):
            signal = self._build_put_spread(snapshot)
            if signal:
                signals.append(signal)

        if bias in ("bearish", "neutral"):
            signal = self._build_call_spread(snapshot)
            if signal:
                signals.append(signal)

        return signals

    def _get_bias(self, snapshot: MarketSnapshot) -> str:
        ind = snapshot.indicators
        if ind.sma_50 is None or ind.rsi is None:
            return "neutral"

        above_sma = snapshot.price > ind.sma_50
        rsi = ind.rsi

        if above_sma and rsi < 70:
            return "bullish"
        elif not above_sma and rsi > 30:
            return "bearish"
        else:
            return "neutral"

    def _build_put_spread(self, snapshot: MarketSnapshot) -> TradeSignal | None:
        symbol = snapshot.symbol
        spread_width = self._config["spread_width"].get(symbol, 5)
        delta_range = self._config["short_strike_delta"]
        min_premium = self._config["min_premium"]

        # Find short put: delta in target range
        short_put = self._find_short_strike(
            snapshot.options_chain.puts, delta_range
        )
        if not short_put:
            return None

        # Find long put: short strike - spread_width
        target_long_strike = short_put.strike_price - spread_width
        long_put = self._find_nearest_strike(
            snapshot.options_chain.puts, target_long_strike
        )
        if not long_put:
            return None

        # Calculate net credit
        net_credit = short_put.mid_price - long_put.mid_price
        if net_credit < min_premium:
            return None

        reasoning = [
            f"IV rank {snapshot.iv_rank:.0f}% above threshold {self._config['iv_rank_threshold']}%",
            f"Bullish bias: price {snapshot.price} above SMA50 {snapshot.indicators.sma_50:.2f}",
            f"Short {short_put.strike_price} put (delta {short_put.delta:.2f}), long {long_put.strike_price} put",
            f"Net credit: ${net_credit:.2f}",
        ]

        return TradeSignal(
            strategy_mode="swing",
            symbol=symbol,
            spread_type="put_spread",
            legs=[
                SpreadLeg(
                    symbol=short_put.symbol,
                    strike_price=short_put.strike_price,
                    contract_type="put",
                    side="sell",
                    delta=short_put.delta,
                ),
                SpreadLeg(
                    symbol=long_put.symbol,
                    strike_price=long_put.strike_price,
                    contract_type="put",
                    side="buy",
                    delta=long_put.delta,
                ),
            ],
            expiration=short_put.expiration_date,
            target_premium=net_credit,
            profit_target_pct=self._config["profit_target_pct"],
            reasoning=reasoning,
        )

    def _build_call_spread(self, snapshot: MarketSnapshot) -> TradeSignal | None:
        symbol = snapshot.symbol
        spread_width = self._config["spread_width"].get(symbol, 5)
        delta_range = self._config["short_strike_delta"]
        min_premium = self._config["min_premium"]

        short_call = self._find_short_strike(
            snapshot.options_chain.calls, delta_range
        )
        if not short_call:
            return None

        target_long_strike = short_call.strike_price + spread_width
        long_call = self._find_nearest_strike(
            snapshot.options_chain.calls, target_long_strike
        )
        if not long_call:
            return None

        net_credit = short_call.mid_price - long_call.mid_price
        if net_credit < min_premium:
            return None

        reasoning = [
            f"IV rank {snapshot.iv_rank:.0f}% above threshold {self._config['iv_rank_threshold']}%",
            f"Bearish bias: price {snapshot.price} below SMA50 {snapshot.indicators.sma_50:.2f}",
            f"Short {short_call.strike_price} call (delta {short_call.delta:.2f}), long {long_call.strike_price} call",
            f"Net credit: ${net_credit:.2f}",
        ]

        return TradeSignal(
            strategy_mode="swing",
            symbol=symbol,
            spread_type="call_spread",
            legs=[
                SpreadLeg(
                    symbol=short_call.symbol,
                    strike_price=short_call.strike_price,
                    contract_type="call",
                    side="sell",
                    delta=short_call.delta,
                ),
                SpreadLeg(
                    symbol=long_call.symbol,
                    strike_price=long_call.strike_price,
                    contract_type="call",
                    side="buy",
                    delta=long_call.delta,
                ),
            ],
            expiration=short_call.expiration_date,
            target_premium=net_credit,
            profit_target_pct=self._config["profit_target_pct"],
            reasoning=reasoning,
        )

    def _find_short_strike(
        self, contracts: list[OptionContract], delta_range: list[float]
    ) -> OptionContract | None:
        min_delta, max_delta = delta_range
        candidates = [
            c
            for c in contracts
            if min_delta <= abs(c.delta) <= max_delta
            and c.open_interest > 0
            and c.mid_price > 0
        ]
        if not candidates:
            return None
        # Pick the one closest to mid-range delta
        target = (min_delta + max_delta) / 2
        return min(candidates, key=lambda c: abs(abs(c.delta) - target))

    def _find_nearest_strike(
        self, contracts: list[OptionContract], target_strike: float
    ) -> OptionContract | None:
        if not contracts:
            return None
        return min(contracts, key=lambda c: abs(c.strike_price - target_strike))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_signals/test_swing.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add src/signals/models.py src/signals/swing.py tests/test_signals/test_swing.py
git commit -m "feat: add signal models and swing strategy signal generator"
```

---

### Task 9: Exhaustion Signal Generator

**Files:**
- Create: `src/signals/exhaustion.py`
- Create: `tests/test_signals/test_exhaustion.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/test_signals/test_exhaustion.py`

```python
from datetime import date, datetime, timezone, time as dtime

import pytest

from src.event_bus import EventBus
from src.market_data.models import (
    Bar,
    Indicators,
    MarketSnapshot,
    OptionContract,
    OptionsChain,
)
from src.signals.exhaustion import ExhaustionSignalGenerator
from src.signals.models import TradeSignal


@pytest.fixture
def exhaustion_config():
    return {
        "enabled": True,
        "target_dte": [1, 2],
        "spread_width": {"SPY": 5, "QQQ": 3},
        "min_premium": 0.25,
        "profit_target_pct": 20,
        "stop_loss_multiplier": 1.5,
        "time_window_start": "11:00",
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "intraday_timeframe": "5min",
        "min_signals_required": 2,
        "close_by_eod": True,
    }


def _make_call(strike, delta=0.20, bid=0.80, ask=1.00, oi=200):
    return OptionContract(
        symbol=f"SPY260401C{int(strike*1000):08d}",
        underlying_symbol="SPY",
        expiration_date=date(2026, 4, 1),
        strike_price=strike,
        contract_type="call",
        bid_price=bid,
        ask_price=ask,
        delta=delta,
        open_interest=oi,
        volume=50,
    )


def _make_put(strike, delta=-0.20, bid=0.80, ask=1.00, oi=200):
    return OptionContract(
        symbol=f"SPY260401P{int(strike*1000):08d}",
        underlying_symbol="SPY",
        expiration_date=date(2026, 4, 1),
        strike_price=strike,
        contract_type="put",
        bid_price=bid,
        ask_price=ask,
        delta=delta,
        open_interest=oi,
        volume=50,
    )


def _make_snapshot_upside_exhaustion():
    """Price rallied, RSI overbought, above VWAP, near upper bollinger"""
    return MarketSnapshot(
        symbol="SPY",
        price=505.0,
        bars=[],
        options_chain=OptionsChain(
            underlying_symbol="SPY",
            calls=[
                _make_call(505.0, delta=0.50, bid=1.20, ask=1.40),
                _make_call(510.0, delta=0.30, bid=0.50, ask=0.70),
            ],
            puts=[],
        ),
        indicators=Indicators(),
        high_of_day=506.0,
        low_of_day=498.0,
        intraday_indicators=Indicators(
            rsi=75.0,
            vwap=500.0,
            upper_bollinger=505.5,
            lower_bollinger=496.0,
        ),
    )


def _make_snapshot_downside_exhaustion():
    """Price sold off, RSI oversold, below VWAP, near lower bollinger"""
    return MarketSnapshot(
        symbol="SPY",
        price=495.0,
        bars=[],
        options_chain=OptionsChain(
            underlying_symbol="SPY",
            calls=[],
            puts=[
                _make_put(495.0, delta=-0.50, bid=1.20, ask=1.40),
                _make_put(490.0, delta=-0.30, bid=0.50, ask=0.70),
            ],
        ),
        indicators=Indicators(),
        high_of_day=502.0,
        low_of_day=494.0,
        intraday_indicators=Indicators(
            rsi=25.0,
            vwap=500.0,
            upper_bollinger=505.0,
            lower_bollinger=495.5,
        ),
    )


def test_upside_exhaustion_generates_call_spread(exhaustion_config, event_bus):
    snapshot = _make_snapshot_upside_exhaustion()
    gen = ExhaustionSignalGenerator(exhaustion_config, event_bus)
    # Simulate current time after 11am ET
    signals = gen.evaluate(snapshot, current_time=dtime(11, 30))
    assert len(signals) == 1
    assert signals[0].spread_type == "call_spread"
    assert signals[0].strategy_mode == "exhaustion"
    assert signals[0].profit_target_pct == 20


def test_downside_exhaustion_generates_put_spread(exhaustion_config, event_bus):
    snapshot = _make_snapshot_downside_exhaustion()
    gen = ExhaustionSignalGenerator(exhaustion_config, event_bus)
    signals = gen.evaluate(snapshot, current_time=dtime(11, 30))
    assert len(signals) == 1
    assert signals[0].spread_type == "put_spread"


def test_no_signal_before_time_window(exhaustion_config, event_bus):
    snapshot = _make_snapshot_upside_exhaustion()
    gen = ExhaustionSignalGenerator(exhaustion_config, event_bus)
    signals = gen.evaluate(snapshot, current_time=dtime(10, 0))
    assert len(signals) == 0


def test_no_signal_when_disabled(exhaustion_config, event_bus):
    exhaustion_config["enabled"] = False
    snapshot = _make_snapshot_upside_exhaustion()
    gen = ExhaustionSignalGenerator(exhaustion_config, event_bus)
    signals = gen.evaluate(snapshot, current_time=dtime(11, 30))
    assert len(signals) == 0


def test_no_signal_insufficient_exhaustion_signals(exhaustion_config, event_bus):
    # RSI neutral, not near bollinger -> not enough signals
    snapshot = MarketSnapshot(
        symbol="SPY",
        price=500.0,
        bars=[],
        options_chain=OptionsChain(underlying_symbol="SPY", calls=[], puts=[]),
        indicators=Indicators(),
        high_of_day=501.0,
        low_of_day=499.0,
        intraday_indicators=Indicators(
            rsi=50.0,
            vwap=500.0,
            upper_bollinger=510.0,
            lower_bollinger=490.0,
        ),
    )
    gen = ExhaustionSignalGenerator(exhaustion_config, event_bus)
    signals = gen.evaluate(snapshot, current_time=dtime(11, 30))
    assert len(signals) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_signals/test_exhaustion.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ExhaustionSignalGenerator**

File: `src/signals/exhaustion.py`

```python
import logging
from datetime import datetime, time as dtime

from src.event_bus import EventBus
from src.market_data.models import MarketSnapshot, OptionContract
from src.signals.models import SpreadLeg, TradeSignal

logger = logging.getLogger(__name__)


class ExhaustionSignalGenerator:
    def __init__(self, config: dict, event_bus: EventBus):
        self._config = config
        self._bus = event_bus

    def evaluate(
        self,
        snapshot: MarketSnapshot,
        current_time: dtime | None = None,
    ) -> list[TradeSignal]:
        if not self._config.get("enabled", True):
            return []

        if current_time is None:
            current_time = datetime.now().time()

        # Check time window
        window_start = dtime.fromisoformat(self._config["time_window_start"])
        if current_time < window_start:
            return []

        if snapshot.intraday_indicators is None:
            return []

        upside_signals = self._count_upside_exhaustion_signals(snapshot)
        downside_signals = self._count_downside_exhaustion_signals(snapshot)

        min_required = self._config["min_signals_required"]
        signals = []

        if upside_signals >= min_required:
            signal = self._build_call_spread(snapshot, upside_signals)
            if signal:
                signals.append(signal)

        if downside_signals >= min_required:
            signal = self._build_put_spread(snapshot, downside_signals)
            if signal:
                signals.append(signal)

        return signals

    def _count_upside_exhaustion_signals(self, snapshot: MarketSnapshot) -> int:
        ind = snapshot.intraday_indicators
        count = 0

        # RSI overbought
        if ind.rsi is not None and ind.rsi > self._config["rsi_overbought"]:
            count += 1

        # Price extended above VWAP
        if ind.vwap is not None and snapshot.price > ind.vwap * 1.005:
            count += 1

        # Price near upper bollinger
        if ind.upper_bollinger is not None and snapshot.price >= ind.upper_bollinger * 0.998:
            count += 1

        # Near high of day
        if snapshot.high_of_day > 0 and snapshot.price >= snapshot.high_of_day * 0.998:
            count += 1

        return count

    def _count_downside_exhaustion_signals(self, snapshot: MarketSnapshot) -> int:
        ind = snapshot.intraday_indicators
        count = 0

        if ind.rsi is not None and ind.rsi < self._config["rsi_oversold"]:
            count += 1

        if ind.vwap is not None and snapshot.price < ind.vwap * 0.995:
            count += 1

        if ind.lower_bollinger is not None and snapshot.price <= ind.lower_bollinger * 1.002:
            count += 1

        if snapshot.low_of_day > 0 and snapshot.price <= snapshot.low_of_day * 1.002:
            count += 1

        return count

    def _build_call_spread(
        self, snapshot: MarketSnapshot, signal_count: int
    ) -> TradeSignal | None:
        symbol = snapshot.symbol
        spread_width = self._config["spread_width"].get(symbol, 5)
        min_premium = self._config["min_premium"]

        # Short call near/above high of day
        target_short_strike = snapshot.high_of_day
        short_call = self._find_nearest_at_or_above(
            snapshot.options_chain.calls, target_short_strike
        )
        if not short_call:
            return None

        target_long_strike = short_call.strike_price + spread_width
        long_call = self._find_nearest_strike(
            snapshot.options_chain.calls, target_long_strike
        )
        if not long_call:
            return None

        net_credit = short_call.mid_price - long_call.mid_price
        if net_credit < min_premium:
            return None

        reasoning = [
            f"Upside exhaustion detected ({signal_count} signals)",
            f"Price {snapshot.price} near high of day {snapshot.high_of_day}",
            f"Intraday RSI: {snapshot.intraday_indicators.rsi:.0f}",
            f"Net credit: ${net_credit:.2f}",
        ]

        return TradeSignal(
            strategy_mode="exhaustion",
            symbol=symbol,
            spread_type="call_spread",
            legs=[
                SpreadLeg(
                    symbol=short_call.symbol,
                    strike_price=short_call.strike_price,
                    contract_type="call",
                    side="sell",
                    delta=short_call.delta,
                ),
                SpreadLeg(
                    symbol=long_call.symbol,
                    strike_price=long_call.strike_price,
                    contract_type="call",
                    side="buy",
                    delta=long_call.delta,
                ),
            ],
            expiration=short_call.expiration_date,
            target_premium=net_credit,
            profit_target_pct=self._config["profit_target_pct"],
            reasoning=reasoning,
        )

    def _build_put_spread(
        self, snapshot: MarketSnapshot, signal_count: int
    ) -> TradeSignal | None:
        symbol = snapshot.symbol
        spread_width = self._config["spread_width"].get(symbol, 5)
        min_premium = self._config["min_premium"]

        target_short_strike = snapshot.low_of_day
        short_put = self._find_nearest_at_or_below(
            snapshot.options_chain.puts, target_short_strike
        )
        if not short_put:
            return None

        target_long_strike = short_put.strike_price - spread_width
        long_put = self._find_nearest_strike(
            snapshot.options_chain.puts, target_long_strike
        )
        if not long_put:
            return None

        net_credit = short_put.mid_price - long_put.mid_price
        if net_credit < min_premium:
            return None

        reasoning = [
            f"Downside exhaustion detected ({signal_count} signals)",
            f"Price {snapshot.price} near low of day {snapshot.low_of_day}",
            f"Intraday RSI: {snapshot.intraday_indicators.rsi:.0f}",
            f"Net credit: ${net_credit:.2f}",
        ]

        return TradeSignal(
            strategy_mode="exhaustion",
            symbol=symbol,
            spread_type="put_spread",
            legs=[
                SpreadLeg(
                    symbol=short_put.symbol,
                    strike_price=short_put.strike_price,
                    contract_type="put",
                    side="sell",
                    delta=short_put.delta,
                ),
                SpreadLeg(
                    symbol=long_put.symbol,
                    strike_price=long_put.strike_price,
                    contract_type="put",
                    side="buy",
                    delta=long_put.delta,
                ),
            ],
            expiration=short_put.expiration_date,
            target_premium=net_credit,
            profit_target_pct=self._config["profit_target_pct"],
            reasoning=reasoning,
        )

    def _find_nearest_at_or_above(
        self, contracts: list[OptionContract], target: float
    ) -> OptionContract | None:
        above = [c for c in contracts if c.strike_price >= target and c.mid_price > 0]
        if not above:
            return None
        return min(above, key=lambda c: c.strike_price)

    def _find_nearest_at_or_below(
        self, contracts: list[OptionContract], target: float
    ) -> OptionContract | None:
        below = [c for c in contracts if c.strike_price <= target and c.mid_price > 0]
        if not below:
            return None
        return max(below, key=lambda c: c.strike_price)

    def _find_nearest_strike(
        self, contracts: list[OptionContract], target: float
    ) -> OptionContract | None:
        if not contracts:
            return None
        return min(contracts, key=lambda c: abs(c.strike_price - target))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_signals/test_exhaustion.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/signals/exhaustion.py tests/test_signals/test_exhaustion.py
git commit -m "feat: add intraday exhaustion signal generator (1-2 DTE)"
```

---

### Task 10: Risk Manager

**Files:**
- Create: `src/risk/manager.py`
- Create: `tests/test_risk/test_manager.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/test_risk/test_manager.py`

```python
from datetime import date
from unittest.mock import MagicMock

import pytest

from src.event_bus import EventBus
from src.risk.manager import RiskManager
from src.signals.models import SpreadLeg, TradeSignal


@pytest.fixture
def risk_config():
    return {
        "max_concurrent_spreads": 10,
        "max_risk_per_trade_pct": 5,
        "max_buying_power_usage_pct": 60,
        "stop_loss_multiplier": 2.0,
        "roll_delta_threshold": 0.50,
        "dte_exit": 1,
        "daily_loss_limit": 1000,
        "daily_income_target": 500,
        "max_same_direction_per_symbol": 3,
        "max_portfolio_delta_per_symbol": 0.30,
    }


def _make_signal(symbol="SPY", spread_type="put_spread", premium=1.50):
    return TradeSignal(
        strategy_mode="swing",
        symbol=symbol,
        spread_type=spread_type,
        legs=[
            SpreadLeg(
                symbol=f"{symbol}260410P00495000",
                strike_price=495.0,
                contract_type="put",
                side="sell",
                delta=-0.20,
            ),
            SpreadLeg(
                symbol=f"{symbol}260410P00490000",
                strike_price=490.0,
                contract_type="put",
                side="buy",
                delta=-0.10,
            ),
        ],
        expiration=date(2026, 4, 10),
        target_premium=premium,
        profit_target_pct=50,
    )


@pytest.fixture
def mock_account():
    account = MagicMock()
    account.buying_power = 50000.0
    account.equity = 50000.0
    return account


def test_validate_signal_passes(risk_config, event_bus, mock_account):
    rm = RiskManager(risk_config, event_bus)
    signal = _make_signal()
    result = rm.validate_signal(signal, open_positions=[], account=mock_account, daily_pnl=0.0)
    assert result.approved is True


def test_reject_max_concurrent_spreads(risk_config, event_bus, mock_account):
    risk_config["max_concurrent_spreads"] = 2
    rm = RiskManager(risk_config, event_bus)
    signal = _make_signal()
    open_positions = [MagicMock() for _ in range(2)]
    result = rm.validate_signal(signal, open_positions=open_positions, account=mock_account, daily_pnl=0.0)
    assert result.approved is False
    assert "max concurrent" in result.reason.lower()


def test_reject_daily_loss_exceeded(risk_config, event_bus, mock_account):
    rm = RiskManager(risk_config, event_bus)
    signal = _make_signal()
    result = rm.validate_signal(signal, open_positions=[], account=mock_account, daily_pnl=-1100.0)
    assert result.approved is False
    assert "daily loss" in result.reason.lower()


def test_reject_daily_target_met(risk_config, event_bus, mock_account):
    rm = RiskManager(risk_config, event_bus)
    signal = _make_signal()
    result = rm.validate_signal(signal, open_positions=[], account=mock_account, daily_pnl=600.0)
    assert result.approved is False
    assert "daily target" in result.reason.lower()


def test_reject_max_same_direction(risk_config, event_bus, mock_account):
    risk_config["max_same_direction_per_symbol"] = 1
    rm = RiskManager(risk_config, event_bus)
    signal = _make_signal(spread_type="put_spread")
    existing = MagicMock()
    existing.symbol = "SPY"
    existing.spread_type = "put_spread"
    result = rm.validate_signal(signal, open_positions=[existing], account=mock_account, daily_pnl=0.0)
    assert result.approved is False


def test_reject_max_risk_per_trade(risk_config, event_bus, mock_account):
    rm = RiskManager(risk_config, event_bus)
    # Spread width is 5 (495 - 490), risk = (5 - 1.50) * 100 = $350
    # 5% of 50000 = 2500, so this should pass
    signal = _make_signal(premium=1.50)
    result = rm.validate_signal(signal, open_positions=[], account=mock_account, daily_pnl=0.0)
    assert result.approved is True

    # Now make account small enough that it fails
    mock_account.equity = 1000.0  # 5% = $50, risk = $350 -> rejected
    result = rm.validate_signal(signal, open_positions=[], account=mock_account, daily_pnl=0.0)
    assert result.approved is False


def test_check_profit_target():
    rm = RiskManager({}, EventBus())
    assert rm.check_profit_target(current_value=0.50, entry_premium=1.00, target_pct=50) is True
    assert rm.check_profit_target(current_value=0.80, entry_premium=1.00, target_pct=50) is False


def test_check_stop_loss():
    rm = RiskManager({"stop_loss_multiplier": 2.0}, EventBus())
    # Loss exceeds 2x premium
    assert rm.check_stop_loss(current_value=3.50, entry_premium=1.00, multiplier=2.0) is True
    assert rm.check_stop_loss(current_value=1.50, entry_premium=1.00, multiplier=2.0) is False


def test_check_roll_needed():
    rm = RiskManager({"roll_delta_threshold": 0.50}, EventBus())
    assert rm.check_roll_needed(short_delta=0.55, threshold=0.50) is True
    assert rm.check_roll_needed(short_delta=0.30, threshold=0.50) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_risk/test_manager.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement RiskManager**

File: `src/risk/manager.py`

```python
import logging
from dataclasses import dataclass

from src.event_bus import EventBus
from src.signals.models import TradeSignal

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    approved: bool
    reason: str = ""


class RiskManager:
    def __init__(self, config: dict, event_bus: EventBus):
        self._config = config
        self._bus = event_bus

    def validate_signal(
        self,
        signal: TradeSignal,
        open_positions: list,
        account,
        daily_pnl: float,
    ) -> ValidationResult:
        # 1. Daily loss circuit breaker
        daily_loss_limit = self._config.get("daily_loss_limit", 1000)
        if daily_pnl <= -daily_loss_limit:
            return ValidationResult(False, f"Daily loss limit exceeded: ${daily_pnl:.2f}")

        # 2. Daily income target met
        daily_target = self._config.get("daily_income_target", 500)
        if daily_pnl >= daily_target:
            return ValidationResult(False, f"Daily target already met: ${daily_pnl:.2f}")

        # 3. Max concurrent spreads
        max_spreads = self._config.get("max_concurrent_spreads", 10)
        if len(open_positions) >= max_spreads:
            return ValidationResult(
                False, f"Max concurrent spreads reached: {len(open_positions)}/{max_spreads}"
            )

        # 4. Max same direction per symbol
        max_same = self._config.get("max_same_direction_per_symbol", 3)
        same_count = sum(
            1
            for p in open_positions
            if getattr(p, "symbol", None) == signal.symbol
            and getattr(p, "spread_type", None) == signal.spread_type
        )
        if same_count >= max_same:
            return ValidationResult(
                False,
                f"Max same-direction spreads for {signal.symbol} {signal.spread_type}: {same_count}/{max_same}",
            )

        # 5. Max risk per trade
        max_risk_pct = self._config.get("max_risk_per_trade_pct", 5)
        equity = float(getattr(account, "equity", 50000))
        max_risk_dollars = equity * (max_risk_pct / 100)
        spread_width = self._calculate_spread_width(signal)
        trade_risk = (spread_width - signal.target_premium) * 100  # per contract
        if trade_risk > max_risk_dollars:
            return ValidationResult(
                False,
                f"Trade risk ${trade_risk:.2f} exceeds max ${max_risk_dollars:.2f} ({max_risk_pct}% of equity)",
            )

        # 6. Buying power check
        max_bp_pct = self._config.get("max_buying_power_usage_pct", 60)
        buying_power = float(getattr(account, "buying_power", 0))
        total_bp = equity  # approximate total BP
        if total_bp > 0 and (1 - buying_power / total_bp) * 100 > max_bp_pct:
            return ValidationResult(
                False, f"Buying power usage exceeds {max_bp_pct}%"
            )

        return ValidationResult(True)

    def check_profit_target(
        self, current_value: float, entry_premium: float, target_pct: int
    ) -> bool:
        profit = entry_premium - current_value
        target_profit = entry_premium * (target_pct / 100)
        return profit >= target_profit

    def check_stop_loss(
        self, current_value: float, entry_premium: float, multiplier: float
    ) -> bool:
        loss = current_value - entry_premium
        max_loss = entry_premium * multiplier
        return loss >= max_loss

    def check_roll_needed(self, short_delta: float, threshold: float) -> bool:
        return abs(short_delta) >= threshold

    def check_dte_exit(self, days_to_expiry: int) -> bool:
        dte_exit = self._config.get("dte_exit", 1)
        return days_to_expiry <= dte_exit

    def _calculate_spread_width(self, signal: TradeSignal) -> float:
        strikes = [leg.strike_price for leg in signal.legs]
        if len(strikes) < 2:
            return 0.0
        return abs(max(strikes) - min(strikes))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_risk/test_manager.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add src/risk/manager.py tests/test_risk/test_manager.py
git commit -m "feat: add risk manager with pre-trade validation and post-trade checks"
```

---

### Task 11: Order Executor

**Files:**
- Create: `src/execution/executor.py`
- Create: `tests/test_execution/test_executor.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/test_execution/test_executor.py`

```python
from datetime import date
from unittest.mock import MagicMock, patch, call

import pytest

from src.event_bus import EventBus
from src.execution.executor import OrderExecutor
from src.signals.models import SpreadLeg, TradeSignal


@pytest.fixture
def exec_config():
    return {
        "price_adjustment_interval": 30,
        "price_adjustment_step": 0.01,
        "fill_timeout": 300,
    }


@pytest.fixture
def mock_trading_client():
    client = MagicMock()
    order = MagicMock()
    order.id = "order-123"
    order.status = "filled"
    order.filled_avg_price = 1.45
    client.submit_order.return_value = order
    return client


@pytest.fixture
def mock_db():
    return MagicMock()


def _make_signal():
    return TradeSignal(
        strategy_mode="swing",
        symbol="SPY",
        spread_type="put_spread",
        legs=[
            SpreadLeg(
                symbol="SPY260410P00495000",
                strike_price=495.0,
                contract_type="put",
                side="sell",
                delta=-0.20,
            ),
            SpreadLeg(
                symbol="SPY260410P00490000",
                strike_price=490.0,
                contract_type="put",
                side="buy",
                delta=-0.10,
            ),
        ],
        expiration=date(2026, 4, 10),
        target_premium=1.50,
        profit_target_pct=50,
    )


def test_submit_spread_order(mock_trading_client, mock_db, exec_config, event_bus):
    executor = OrderExecutor(mock_trading_client, mock_db, exec_config, event_bus)
    signal = _make_signal()
    result = executor.submit_spread_order(signal)
    mock_trading_client.submit_order.assert_called_once()
    assert result is not None
    assert result.id == "order-123"


def test_submit_spread_uses_limit_order(mock_trading_client, mock_db, exec_config, event_bus):
    executor = OrderExecutor(mock_trading_client, mock_db, exec_config, event_bus)
    signal = _make_signal()
    executor.submit_spread_order(signal)
    call_args = mock_trading_client.submit_order.call_args
    order_data = call_args[0][0] if call_args[0] else call_args[1].get("order_data")
    # Should be a LimitOrderRequest with MLEG class
    assert order_data.order_class.value == "mleg"
    assert order_data.limit_price is not None


def test_submit_spread_has_correct_legs(mock_trading_client, mock_db, exec_config, event_bus):
    executor = OrderExecutor(mock_trading_client, mock_db, exec_config, event_bus)
    signal = _make_signal()
    executor.submit_spread_order(signal)
    call_args = mock_trading_client.submit_order.call_args
    order_data = call_args[0][0] if call_args[0] else call_args[1].get("order_data")
    assert len(order_data.legs) == 2


def test_submit_logs_to_db(mock_trading_client, mock_db, exec_config, event_bus):
    executor = OrderExecutor(mock_trading_client, mock_db, exec_config, event_bus)
    signal = _make_signal()
    executor.submit_spread_order(signal)
    mock_db.save_order_log.assert_called_once()


def test_publishes_order_filled_event(mock_trading_client, mock_db, exec_config, event_bus):
    received = []
    event_bus.subscribe("OrderFilled", lambda data: received.append(data))
    executor = OrderExecutor(mock_trading_client, mock_db, exec_config, event_bus)
    signal = _make_signal()
    executor.submit_spread_order(signal)
    assert len(received) == 1
    assert received[0]["order_id"] == "order-123"


def test_submit_close_order(mock_trading_client, mock_db, exec_config, event_bus):
    executor = OrderExecutor(mock_trading_client, mock_db, exec_config, event_bus)
    legs = [
        SpreadLeg("SPY260410P00495000", 495.0, "put", "sell", -0.20),
        SpreadLeg("SPY260410P00490000", 490.0, "put", "buy", -0.10),
    ]
    result = executor.submit_close_order(legs, limit_price=0.50)
    mock_trading_client.submit_order.assert_called_once()
    assert result is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_execution/test_executor.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement OrderExecutor**

File: `src/execution/executor.py`

```python
import logging
from datetime import datetime, timezone

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest

from src.db.mongo import MongoStore
from src.event_bus import EventBus
from src.signals.models import SpreadLeg, TradeSignal

logger = logging.getLogger(__name__)


class OrderExecutor:
    def __init__(
        self,
        trading_client: TradingClient,
        db: MongoStore,
        config: dict,
        event_bus: EventBus,
    ):
        self._client = trading_client
        self._db = db
        self._config = config
        self._bus = event_bus

    def submit_spread_order(self, signal: TradeSignal):
        legs = [
            OptionLegRequest(
                symbol=leg.symbol,
                side=OrderSide.SELL if leg.side == "sell" else OrderSide.BUY,
                ratio_qty=1,
            )
            for leg in signal.legs
        ]

        order_request = LimitOrderRequest(
            qty=1,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.MLEG,
            limit_price=round(signal.target_premium, 2),
            legs=legs,
        )

        order = self._client.submit_order(order_request)

        self._db.save_order_log(
            {
                "order_id": str(order.id),
                "signal": {
                    "strategy_mode": signal.strategy_mode,
                    "symbol": signal.symbol,
                    "spread_type": signal.spread_type,
                    "target_premium": signal.target_premium,
                    "expiration": str(signal.expiration),
                },
                "status": str(order.status),
                "timestamp": datetime.now(timezone.utc),
            }
        )

        if str(order.status) in ("filled", "partially_filled"):
            self._bus.publish(
                "OrderFilled",
                {
                    "order_id": str(order.id),
                    "signal": signal,
                    "filled_price": float(getattr(order, "filled_avg_price", 0) or 0),
                },
            )
        else:
            self._bus.publish(
                "OrderSubmitted",
                {"order_id": str(order.id), "signal": signal},
            )

        return order

    def submit_close_order(
        self, legs: list[SpreadLeg], limit_price: float
    ):
        # Reverse the sides to close
        close_legs = [
            OptionLegRequest(
                symbol=leg.symbol,
                side=OrderSide.BUY if leg.side == "sell" else OrderSide.SELL,
                ratio_qty=1,
            )
            for leg in legs
        ]

        order_request = LimitOrderRequest(
            qty=1,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.MLEG,
            limit_price=round(limit_price, 2),
            legs=close_legs,
        )

        order = self._client.submit_order(order_request)

        self._db.save_order_log(
            {
                "order_id": str(order.id),
                "action": "close",
                "status": str(order.status),
                "limit_price": limit_price,
                "timestamp": datetime.now(timezone.utc),
            }
        )

        return order

    def cancel_order(self, order_id: str):
        self._client.cancel_order_by_id(order_id)
        logger.info(f"Cancelled order {order_id}")

    def get_order_status(self, order_id: str):
        return self._client.get_order_by_id(order_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_execution/test_executor.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/execution/executor.py tests/test_execution/test_executor.py
git commit -m "feat: add order executor for multi-leg spread orders via Alpaca"
```

---

### Task 12: Position Manager

**Files:**
- Create: `src/positions/manager.py`
- Create: `tests/test_positions/test_manager.py`

- [ ] **Step 1: Write the failing tests**

File: `tests/test_positions/test_manager.py`

```python
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.event_bus import EventBus
from src.positions.manager import PositionManager, TrackedSpread
from src.signals.models import SpreadLeg, TradeSignal


@pytest.fixture
def mock_db():
    return MagicMock()


def _make_spread():
    return TrackedSpread(
        order_id="order-123",
        strategy_mode="swing",
        symbol="SPY",
        spread_type="put_spread",
        legs=[
            SpreadLeg("SPY260410P00495000", 495.0, "put", "sell", -0.20),
            SpreadLeg("SPY260410P00490000", 490.0, "put", "buy", -0.10),
        ],
        expiration=date(2026, 4, 10),
        entry_premium=1.50,
        profit_target_pct=50,
        opened_at=datetime.now(timezone.utc),
    )


def test_add_position(mock_db, event_bus):
    pm = PositionManager(mock_db, event_bus)
    spread = _make_spread()
    pm.add_position(spread)
    assert len(pm.open_positions) == 1
    assert pm.open_positions[0].order_id == "order-123"


def test_remove_position(mock_db, event_bus):
    pm = PositionManager(mock_db, event_bus)
    spread = _make_spread()
    pm.add_position(spread)
    pm.close_position("order-123", close_premium=0.50, reason="profit_target")
    assert len(pm.open_positions) == 0
    mock_db.save_trade.assert_called_once()


def test_close_records_pnl(mock_db, event_bus):
    pm = PositionManager(mock_db, event_bus)
    spread = _make_spread()
    pm.add_position(spread)
    pm.close_position("order-123", close_premium=0.50, reason="profit_target")
    trade_record = mock_db.save_trade.call_args[0][0]
    # PnL = (entry - close) * 100 = (1.50 - 0.50) * 100 = $100
    assert trade_record["pnl"] == pytest.approx(100.0)


def test_daily_pnl(mock_db, event_bus):
    pm = PositionManager(mock_db, event_bus)
    spread = _make_spread()
    pm.add_position(spread)
    pm.close_position("order-123", close_premium=0.50, reason="profit_target")
    assert pm.daily_pnl == pytest.approx(100.0)


def test_get_positions_by_symbol(mock_db, event_bus):
    pm = PositionManager(mock_db, event_bus)
    spread1 = _make_spread()
    spread2 = _make_spread()
    spread2.order_id = "order-456"
    spread2.symbol = "QQQ"
    pm.add_position(spread1)
    pm.add_position(spread2)
    spy_positions = pm.get_positions_by_symbol("SPY")
    assert len(spy_positions) == 1


def test_on_order_filled_creates_position(mock_db, event_bus):
    pm = PositionManager(mock_db, event_bus)
    signal = TradeSignal(
        strategy_mode="swing",
        symbol="SPY",
        spread_type="put_spread",
        legs=[
            SpreadLeg("SPY260410P00495000", 495.0, "put", "sell", -0.20),
            SpreadLeg("SPY260410P00490000", 490.0, "put", "buy", -0.10),
        ],
        expiration=date(2026, 4, 10),
        target_premium=1.50,
        profit_target_pct=50,
    )
    event_bus.publish("OrderFilled", {
        "order_id": "order-789",
        "signal": signal,
        "filled_price": 1.45,
    })
    assert len(pm.open_positions) == 1
    assert pm.open_positions[0].entry_premium == 1.45
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_positions/test_manager.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement PositionManager**

File: `src/positions/manager.py`

```python
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from src.db.mongo import MongoStore
from src.event_bus import EventBus
from src.signals.models import SpreadLeg

logger = logging.getLogger(__name__)


@dataclass
class TrackedSpread:
    order_id: str
    strategy_mode: str
    symbol: str
    spread_type: str
    legs: list[SpreadLeg]
    expiration: date
    entry_premium: float
    profit_target_pct: int
    opened_at: datetime
    current_value: float = 0.0
    unrealized_pnl: float = 0.0


class PositionManager:
    def __init__(self, db: MongoStore, event_bus: EventBus):
        self._db = db
        self._bus = event_bus
        self.open_positions: list[TrackedSpread] = []
        self.daily_pnl: float = 0.0
        self._closed_today: list[dict] = []

        self._bus.subscribe("OrderFilled", self._on_order_filled)

    def _on_order_filled(self, data: dict) -> None:
        signal = data["signal"]
        spread = TrackedSpread(
            order_id=data["order_id"],
            strategy_mode=signal.strategy_mode,
            symbol=signal.symbol,
            spread_type=signal.spread_type,
            legs=signal.legs,
            expiration=signal.expiration,
            entry_premium=data.get("filled_price", signal.target_premium),
            profit_target_pct=signal.profit_target_pct,
            opened_at=datetime.now(timezone.utc),
        )
        self.add_position(spread)

    def add_position(self, spread: TrackedSpread) -> None:
        self.open_positions.append(spread)
        logger.info(
            f"Opened {spread.spread_type} on {spread.symbol} "
            f"(premium: ${spread.entry_premium:.2f}, exp: {spread.expiration})"
        )

    def close_position(
        self, order_id: str, close_premium: float, reason: str
    ) -> None:
        spread = next(
            (p for p in self.open_positions if p.order_id == order_id), None
        )
        if spread is None:
            logger.warning(f"Position {order_id} not found")
            return

        pnl = (spread.entry_premium - close_premium) * 100
        self.daily_pnl += pnl

        trade_record = {
            "order_id": spread.order_id,
            "strategy_mode": spread.strategy_mode,
            "symbol": spread.symbol,
            "spread_type": spread.spread_type,
            "expiration": str(spread.expiration),
            "entry_premium": spread.entry_premium,
            "close_premium": close_premium,
            "pnl": pnl,
            "reason": reason,
            "opened_at": spread.opened_at,
            "closed_at": datetime.now(timezone.utc),
        }
        self._db.save_trade(trade_record)
        self._closed_today.append(trade_record)
        self.open_positions = [
            p for p in self.open_positions if p.order_id != order_id
        ]

        self._bus.publish("PositionClosed", trade_record)
        logger.info(
            f"Closed {spread.symbol} {spread.spread_type}: "
            f"P&L ${pnl:.2f} ({reason})"
        )

    def get_positions_by_symbol(self, symbol: str) -> list[TrackedSpread]:
        return [p for p in self.open_positions if p.symbol == symbol]

    def reset_daily(self) -> None:
        self.daily_pnl = 0.0
        self._closed_today = []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_positions/test_manager.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/positions/manager.py tests/test_positions/test_manager.py
git commit -m "feat: add position manager with P&L tracking and lifecycle management"
```

---

### Task 13: Notifications (SMS + Email)

**Files:**
- Create: `src/notifications/sms.py`
- Create: `src/notifications/email_notifier.py`
- Create: `tests/test_notifications/test_sms.py`
- Create: `tests/test_notifications/test_email.py`

- [ ] **Step 1: Write SMS failing tests**

File: `tests/test_notifications/test_sms.py`

```python
from unittest.mock import MagicMock, patch

import pytest

from src.notifications.sms import SmsNotifier


@patch("src.notifications.sms.Client")
def test_send_sms(mock_twilio_cls):
    mock_client = MagicMock()
    mock_twilio_cls.return_value = mock_client
    notifier = SmsNotifier(
        account_sid="sid",
        auth_token="token",
        from_number="+1111",
        to_number="+2222",
    )
    notifier.send("Test message")
    mock_client.messages.create.assert_called_once_with(
        body="Test message",
        from_="+1111",
        to="+2222",
    )


@patch("src.notifications.sms.Client")
def test_notify_fill(mock_twilio_cls):
    mock_client = MagicMock()
    mock_twilio_cls.return_value = mock_client
    notifier = SmsNotifier("sid", "token", "+1111", "+2222")
    notifier.notify_fill("SPY", "put_spread", 1.50)
    call_args = mock_client.messages.create.call_args
    assert "SPY" in call_args[1]["body"]
    assert "put_spread" in call_args[1]["body"]


@patch("src.notifications.sms.Client")
def test_notify_stop_loss(mock_twilio_cls):
    mock_client = MagicMock()
    mock_twilio_cls.return_value = mock_client
    notifier = SmsNotifier("sid", "token", "+1111", "+2222")
    notifier.notify_stop_loss("QQQ", "call_spread", -150.0)
    call_args = mock_client.messages.create.call_args
    assert "STOP LOSS" in call_args[1]["body"].upper()
```

- [ ] **Step 2: Write Email failing tests**

File: `tests/test_notifications/test_email.py`

```python
from unittest.mock import MagicMock, patch

import pytest

from src.notifications.email_notifier import EmailNotifier


@patch("src.notifications.email_notifier.smtplib.SMTP")
def test_send_daily_summary(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

    notifier = EmailNotifier(
        host="smtp.test.com",
        port=587,
        username="user@test.com",
        password="pass",
        to_email="dest@test.com",
    )
    notifier.send_daily_summary(
        daily_pnl=250.0,
        open_positions=3,
        closed_trades=5,
        win_rate=80.0,
        target=500,
    )
    mock_smtp.send_message.assert_called_once()


@patch("src.notifications.email_notifier.smtplib.SMTP")
def test_daily_summary_contains_pnl(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

    notifier = EmailNotifier("smtp.test.com", 587, "u@t.com", "p", "d@t.com")
    notifier.send_daily_summary(
        daily_pnl=250.0, open_positions=3, closed_trades=5, win_rate=80.0, target=500
    )
    msg = mock_smtp.send_message.call_args[0][0]
    body = msg.get_content()
    assert "250.00" in body
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_notifications/ -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement SmsNotifier**

File: `src/notifications/sms.py`

```python
import logging

from twilio.rest import Client

logger = logging.getLogger(__name__)


class SmsNotifier:
    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        to_number: str,
    ):
        self._client = Client(account_sid, auth_token)
        self._from = from_number
        self._to = to_number

    def send(self, message: str) -> None:
        try:
            self._client.messages.create(
                body=message, from_=self._from, to=self._to
            )
        except Exception:
            logger.exception("Failed to send SMS")

    def notify_fill(self, symbol: str, spread_type: str, premium: float) -> None:
        self.send(
            f"FILLED: {symbol} {spread_type} for ${premium:.2f} credit"
        )

    def notify_stop_loss(self, symbol: str, spread_type: str, pnl: float) -> None:
        self.send(
            f"STOP LOSS: {symbol} {spread_type} closed at ${pnl:.2f}"
        )

    def notify_roll(self, symbol: str, spread_type: str) -> None:
        self.send(f"ROLLED: {symbol} {spread_type} to next expiration")

    def notify_circuit_breaker(self, daily_pnl: float) -> None:
        self.send(
            f"CIRCUIT BREAKER: Trading halted. Daily P&L: ${daily_pnl:.2f}"
        )

    def notify_error(self, error: str) -> None:
        self.send(f"BOT ERROR: {error}")
```

- [ ] **Step 5: Implement EmailNotifier**

File: `src/notifications/email_notifier.py`

```python
import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        to_email: str,
    ):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._to = to_email

    def _send(self, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._username
        msg["To"] = self._to
        msg.set_content(body)

        try:
            with smtplib.SMTP(self._host, self._port) as server:
                server.starttls()
                server.login(self._username, self._password)
                server.send_message(msg)
        except Exception:
            logger.exception("Failed to send email")

    def send_daily_summary(
        self,
        daily_pnl: float,
        open_positions: int,
        closed_trades: int,
        win_rate: float,
        target: int,
    ) -> None:
        progress = (daily_pnl / target * 100) if target > 0 else 0
        body = (
            f"Auto-Trader Daily Summary\n"
            f"{'=' * 30}\n\n"
            f"Daily P&L: ${daily_pnl:.2f} ({progress:.0f}% of ${target} target)\n"
            f"Open Positions: {open_positions}\n"
            f"Trades Closed Today: {closed_trades}\n"
            f"Win Rate: {win_rate:.1f}%\n"
        )
        self._send(f"Auto-Trader: ${daily_pnl:.2f} P&L", body)

    def send_weekly_recap(
        self,
        weekly_pnl: float,
        total_trades: int,
        win_rate: float,
    ) -> None:
        body = (
            f"Auto-Trader Weekly Recap\n"
            f"{'=' * 30}\n\n"
            f"Weekly P&L: ${weekly_pnl:.2f}\n"
            f"Total Trades: {total_trades}\n"
            f"Win Rate: {win_rate:.1f}%\n"
        )
        self._send(f"Auto-Trader Weekly: ${weekly_pnl:.2f}", body)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_notifications/ -v`
Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
git add src/notifications/sms.py src/notifications/email_notifier.py tests/test_notifications/test_sms.py tests/test_notifications/test_email.py
git commit -m "feat: add SMS (Twilio) and email notification services"
```

---

### Task 14: Scheduler + Main Entry Point

**Files:**
- Create: `src/scheduler.py`
- Create: `src/main.py`

- [ ] **Step 1: Implement the Scheduler**

File: `src/scheduler.py`

```python
import logging
from datetime import datetime, time as dtime, timezone, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler

from src.config import AppConfig
from src.event_bus import EventBus
from src.execution.executor import OrderExecutor
from src.market_data.client import MarketDataClient
from src.market_data.indicators import compute_indicators, compute_iv_rank
from src.market_data.models import MarketSnapshot
from src.positions.manager import PositionManager
from src.risk.manager import RiskManager
from src.signals.exhaustion import ExhaustionSignalGenerator
from src.signals.swing import SwingSignalGenerator

logger = logging.getLogger(__name__)

MARKET_OPEN = dtime(9, 30)
MARKET_CLOSE = dtime(16, 0)


class TradingScheduler:
    def __init__(
        self,
        config: AppConfig,
        event_bus: EventBus,
        market_data: MarketDataClient,
        swing_gen: SwingSignalGenerator,
        exhaustion_gen: ExhaustionSignalGenerator,
        risk_manager: RiskManager,
        executor: OrderExecutor,
        position_manager: PositionManager,
        trading_client,
        option_client,
        db,
    ):
        self._config = config
        self._bus = event_bus
        self._market_data = market_data
        self._swing_gen = swing_gen
        self._exhaustion_gen = exhaustion_gen
        self._risk_manager = risk_manager
        self._executor = executor
        self._positions = position_manager
        self._trading_client = trading_client
        self._option_client = option_client
        self._db = db
        self._scheduler = BlockingScheduler()

    def start(self) -> None:
        interval = self._config.schedule.scan_interval_minutes
        self._scheduler.add_job(
            self._scan_loop,
            "interval",
            minutes=interval,
            id="scan_loop",
        )
        self._scheduler.add_job(
            self._position_check_loop,
            "interval",
            minutes=1,
            id="position_check",
        )
        self._scheduler.add_job(
            self._daily_reset,
            "cron",
            hour=9,
            minute=25,
            id="daily_reset",
        )
        logger.info(f"Scheduler started (scan interval: {interval}min)")
        self._scheduler.start()

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)

    def _is_market_hours(self) -> bool:
        if not self._config.schedule.market_hours_only:
            return True
        now_et = datetime.now(timezone(timedelta(hours=-4))).time()
        return MARKET_OPEN <= now_et <= MARKET_CLOSE

    def _scan_loop(self) -> None:
        if not self._is_market_hours():
            return

        for symbol in self._config.symbols:
            try:
                self._scan_symbol(symbol)
            except Exception:
                logger.exception(f"Error scanning {symbol}")

    def _scan_symbol(self, symbol: str) -> None:
        logger.info(f"Scanning {symbol}")

        # Fetch market data
        price = self._market_data.get_latest_price(symbol)
        daily_bars = self._market_data.get_daily_bars(symbol, limit=60)
        indicators = compute_indicators(daily_bars)

        # Compute IV rank from DB history
        since = datetime.now(timezone.utc) - timedelta(weeks=52)
        iv_records = self._db.get_iv_history(symbol, since)
        iv_history_values = [r["iv"] for r in iv_records]

        # Get current ATM IV from options chain (use swing chain)
        current_iv = self._get_atm_iv(symbol, price)
        if current_iv > 0:
            self._db.save_iv_record({
                "symbol": symbol,
                "iv": current_iv,
                "timestamp": datetime.now(timezone.utc),
            })
        iv_rank = compute_iv_rank(current_iv, iv_history_values) if iv_history_values and current_iv > 0 else None

        # Swing strategy: 7-10 DTE chain
        swing_chain = self._market_data.get_options_chain(
            symbol,
            min_dte=self._config.swing.target_dte[0],
            max_dte=self._config.swing.target_dte[1],
        )
        self._market_data.enrich_chain_with_quotes(swing_chain)

        swing_snapshot = MarketSnapshot(
            symbol=symbol,
            price=price,
            bars=daily_bars,
            options_chain=swing_chain,
            indicators=indicators,
            iv_rank=iv_rank,
        )

        # Generate and process swing signals
        swing_signals = self._swing_gen.evaluate(swing_snapshot)
        self._process_signals(swing_signals)

        # Exhaustion strategy: 1-2 DTE chain + intraday data
        if self._config.exhaustion.enabled:
            exhaustion_chain = self._market_data.get_options_chain(
                symbol,
                min_dte=self._config.exhaustion.target_dte[0],
                max_dte=self._config.exhaustion.target_dte[1],
            )
            self._market_data.enrich_chain_with_quotes(exhaustion_chain)

            intraday_bars = self._market_data.get_intraday_bars(symbol)
            intraday_indicators = compute_indicators(intraday_bars)

            exhaustion_snapshot = MarketSnapshot(
                symbol=symbol,
                price=price,
                bars=daily_bars,
                options_chain=exhaustion_chain,
                indicators=indicators,
                iv_rank=iv_rank,
                high_of_day=max((b.high for b in intraday_bars), default=0),
                low_of_day=min((b.low for b in intraday_bars), default=0),
                intraday_bars=intraday_bars,
                intraday_indicators=intraday_indicators,
            )

            exhaustion_signals = self._exhaustion_gen.evaluate(exhaustion_snapshot)
            self._process_signals(exhaustion_signals)

    def _process_signals(self, signals) -> None:
        account = self._trading_client.get_account()
        for signal in signals:
            result = self._risk_manager.validate_signal(
                signal,
                open_positions=self._positions.open_positions,
                account=account,
                daily_pnl=self._positions.daily_pnl,
            )
            if result.approved:
                logger.info(f"Signal approved: {signal.symbol} {signal.spread_type}")
                self._executor.submit_spread_order(signal)
                self._bus.publish("SignalValidated", {"signal": signal})
            else:
                logger.info(f"Signal rejected: {result.reason}")
                self._bus.publish(
                    "SignalRejected",
                    {"signal": signal, "reason": result.reason},
                )

    def _position_check_loop(self) -> None:
        if not self._is_market_hours():
            return

        for position in list(self._positions.open_positions):
            try:
                self._check_position(position)
            except Exception:
                logger.exception(f"Error checking position {position.order_id}")

    def _check_position(self, position) -> None:
        # Update current spread value from live quotes
        self._update_position_value(position)

        days_to_exp = (position.expiration - datetime.now(timezone.utc).date()).days

        # DTE exit
        if self._risk_manager.check_dte_exit(days_to_exp):
            logger.info(f"DTE exit for {position.order_id}")
            self._executor.submit_close_order(
                position.legs, limit_price=position.current_value
            )
            self._positions.close_position(
                position.order_id, position.current_value, "dte_exit"
            )
            return

        # Profit target
        if self._risk_manager.check_profit_target(
            position.current_value, position.entry_premium, position.profit_target_pct
        ):
            self._executor.submit_close_order(
                position.legs, limit_price=position.current_value
            )
            self._positions.close_position(
                position.order_id, position.current_value, "profit_target"
            )
            self._bus.publish("ProfitTargetHit", {"position": position})
            return

        # Roll check (only for swing, not exhaustion — exhaustion closes at EOD)
        if position.strategy_mode == "swing":
            short_leg = next((l for l in position.legs if l.side == "sell"), None)
            if short_leg and self._risk_manager.check_roll_needed(
                abs(short_leg.delta), self._config.risk.roll_delta_threshold
            ):
                logger.info(f"Rolling {position.order_id}: short delta {short_leg.delta:.2f}")
                # Close current spread
                self._executor.submit_close_order(
                    position.legs, limit_price=position.current_value
                )
                self._positions.close_position(
                    position.order_id, position.current_value, "rolled"
                )
                self._bus.publish("RollTriggered", {"position": position})
                # The next scan cycle will open a new spread at a later expiration
                return

        # Stop loss
        multiplier = self._config.risk.stop_loss_multiplier
        if position.strategy_mode == "exhaustion":
            multiplier = self._config.exhaustion.stop_loss_multiplier
        if self._risk_manager.check_stop_loss(
            position.current_value, position.entry_premium, multiplier
        ):
            self._executor.submit_close_order(
                position.legs, limit_price=position.current_value
            )
            self._positions.close_position(
                position.order_id, position.current_value, "stop_loss"
            )
            self._bus.publish("StopLossHit", {"position": position})
            return

    def _update_position_value(self, position) -> None:
        """Fetch latest quotes for spread legs and update current value."""
        try:
            from alpaca.data.requests import OptionLatestQuoteRequest
            leg_symbols = [leg.symbol for leg in position.legs]
            req = OptionLatestQuoteRequest(symbol_or_symbols=leg_symbols)
            quotes = self._option_client.get_option_latest_quote(req)

            total_value = 0.0
            for leg in position.legs:
                if leg.symbol in quotes:
                    q = quotes[leg.symbol]
                    mid = (float(q.bid_price) + float(q.ask_price)) / 2
                    if leg.side == "sell":
                        total_value += mid  # we owe this
                    else:
                        total_value -= mid  # we own this
                    # Update leg delta from quote if available
            position.current_value = total_value
            position.unrealized_pnl = (position.entry_premium - total_value) * 100
        except Exception:
            logger.exception(f"Failed to update position value for {position.order_id}")

    def _get_atm_iv(self, symbol: str, price: float) -> float:
        """Get implied volatility of the nearest ATM option."""
        try:
            chain = self._market_data.get_options_chain(symbol, min_dte=20, max_dte=40)
            self._market_data.enrich_chain_with_quotes(chain)
            all_contracts = chain.calls + chain.puts
            if not all_contracts:
                return 0.0
            atm = min(all_contracts, key=lambda c: abs(c.strike_price - price))
            return atm.implied_volatility
        except Exception:
            logger.exception(f"Failed to get ATM IV for {symbol}")
            return 0.0

    def _daily_reset(self) -> None:
        self._positions.reset_daily()
        logger.info("Daily reset complete")
```

- [ ] **Step 2: Implement main entry point**

File: `src/main.py`

```python
import logging
import sys

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.trading.client import TradingClient

from src.config import load_config
from src.db.mongo import MongoStore
from src.event_bus import EventBus
from src.execution.executor import OrderExecutor
from src.market_data.client import MarketDataClient
from src.notifications.email_notifier import EmailNotifier
from src.notifications.sms import SmsNotifier
from src.positions.manager import PositionManager
from src.risk.manager import RiskManager
from src.scheduler import TradingScheduler
from src.signals.exhaustion import ExhaustionSignalGenerator
from src.signals.swing import SwingSignalGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("auto-trader.log"),
    ],
)
logger = logging.getLogger(__name__)


def main():
    config = load_config()
    logger.info("Config loaded")

    # Core infrastructure
    event_bus = EventBus()
    db = MongoStore(config.mongodb_uri, config.mongodb_db_name)

    # Alpaca clients
    trading_client = TradingClient(
        config.alpaca_api_key,
        config.alpaca_api_secret,
        paper=config.alpaca_paper,
    )
    stock_client = StockHistoricalDataClient(
        config.alpaca_api_key, config.alpaca_api_secret
    )
    option_client = OptionHistoricalDataClient(
        config.alpaca_api_key, config.alpaca_api_secret
    )

    # Modules
    market_data = MarketDataClient(
        trading_client=trading_client,
        stock_client=stock_client,
        option_client=option_client,
        db=db,
        symbols=config.symbols,
    )

    swing_config = {
        "target_dte": config.swing.target_dte,
        "short_strike_delta": config.swing.short_strike_delta,
        "spread_width": config.swing.spread_width,
        "min_premium": config.swing.min_premium,
        "iv_rank_threshold": config.swing.iv_rank_threshold,
        "profit_target_pct": config.swing.profit_target_pct,
    }
    swing_gen = SwingSignalGenerator(swing_config, event_bus)

    exhaustion_config = {
        "enabled": config.exhaustion.enabled,
        "target_dte": config.exhaustion.target_dte,
        "spread_width": config.exhaustion.spread_width,
        "min_premium": config.exhaustion.min_premium,
        "profit_target_pct": config.exhaustion.profit_target_pct,
        "stop_loss_multiplier": config.exhaustion.stop_loss_multiplier,
        "time_window_start": config.exhaustion.time_window_start,
        "rsi_overbought": config.exhaustion.rsi_overbought,
        "rsi_oversold": config.exhaustion.rsi_oversold,
        "intraday_timeframe": config.exhaustion.intraday_timeframe,
        "min_signals_required": config.exhaustion.min_signals_required,
        "close_by_eod": config.exhaustion.close_by_eod,
    }
    exhaustion_gen = ExhaustionSignalGenerator(exhaustion_config, event_bus)

    risk_config = {
        "max_concurrent_spreads": config.risk.max_concurrent_spreads,
        "max_risk_per_trade_pct": config.risk.max_risk_per_trade_pct,
        "max_buying_power_usage_pct": config.risk.max_buying_power_usage_pct,
        "stop_loss_multiplier": config.risk.stop_loss_multiplier,
        "roll_delta_threshold": config.risk.roll_delta_threshold,
        "dte_exit": config.risk.dte_exit,
        "daily_loss_limit": config.risk.daily_loss_limit,
        "daily_income_target": config.risk.daily_income_target,
        "max_same_direction_per_symbol": config.risk.max_same_direction_per_symbol,
        "max_portfolio_delta_per_symbol": config.risk.max_portfolio_delta_per_symbol,
    }
    risk_manager = RiskManager(risk_config, event_bus)

    exec_config = {
        "price_adjustment_interval": config.execution.price_adjustment_interval,
        "price_adjustment_step": config.execution.price_adjustment_step,
        "fill_timeout": config.execution.fill_timeout,
    }
    executor = OrderExecutor(trading_client, db, exec_config, event_bus)
    position_manager = PositionManager(db, event_bus)

    # Notifications
    if config.notifications.sms_enabled and config.twilio_account_sid:
        sms = SmsNotifier(
            config.twilio_account_sid,
            config.twilio_auth_token,
            config.twilio_from_number,
            config.twilio_to_number,
        )
        event_bus.subscribe(
            "OrderFilled",
            lambda d: sms.notify_fill(
                d["signal"].symbol, d["signal"].spread_type, d.get("filled_price", 0)
            ),
        )
        event_bus.subscribe(
            "StopLossHit",
            lambda d: sms.notify_stop_loss(
                d["position"].symbol,
                d["position"].spread_type,
                d["position"].unrealized_pnl,
            ),
        )
        event_bus.subscribe(
            "CircuitBreakerTriggered",
            lambda d: sms.notify_circuit_breaker(d.get("daily_pnl", 0)),
        )

    # Scheduler
    scheduler = TradingScheduler(
        config=config,
        event_bus=event_bus,
        market_data=market_data,
        swing_gen=swing_gen,
        exhaustion_gen=exhaustion_gen,
        risk_manager=risk_manager,
        executor=executor,
        position_manager=position_manager,
        trading_client=trading_client,
        option_client=option_client,
        db=db,
    )

    logger.info("Auto-Trader starting...")
    logger.info(f"Symbols: {config.symbols}")
    logger.info(f"Paper trading: {config.alpaca_paper}")
    logger.info(f"Swing DTE: {config.swing.target_dte}")
    logger.info(f"Exhaustion enabled: {config.exhaustion.enabled}")
    logger.info(f"Daily target: ${config.risk.daily_income_target}")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        scheduler.stop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify imports work**

Run: `python -c "from src.main import main; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Run all tests to verify nothing is broken**

Run: `pytest -v`
Expected: All tests pass (34 total)

- [ ] **Step 5: Commit**

```bash
git add src/scheduler.py src/main.py
git commit -m "feat: add scheduler and main entry point wiring all modules together"
```

---

### Task 15: Full Integration Smoke Test

**Files:**
- No new files — run the full suite and verify the bot starts in paper mode

- [ ] **Step 1: Run full test suite**

Run: `pytest -v --tb=short`
Expected: All tests pass

- [ ] **Step 2: Verify bot starts with paper trading (will fail without API keys, but should get past imports)**

Run: `python -c "from src.main import main; print('All modules imported successfully')"`
Expected: `All modules imported successfully`

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete auto-trader bot with all modules integrated"
```

# React Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a React + shadcn/ui dashboard with a FastAPI backend that displays live market data, scan rejections, trades, and allows editing all bot settings (persisted to MongoDB).

**Architecture:** FastAPI (`api/`) reads/writes MongoDB and serves JSON to a Vite React app (`frontend/`). The bot's `load_config()` is modified to check MongoDB `settings` collection for overrides on each scan cycle. Frontend polls every 60s.

**Tech Stack:** React 18, TypeScript, Vite, shadcn/ui, Tailwind CSS, FastAPI, pymongo, MongoDB

**Spec:** `docs/superpowers/specs/2026-04-01-react-dashboard-design.md`

---

## File Map

### New files — API layer
| File | Responsibility |
|------|---------------|
| `api/__init__.py` | Package marker |
| `api/main.py` | FastAPI app, CORS, lifespan (MongoDB connection) |
| `api/db.py` | MongoDB connection helper, shared db reference |
| `api/routes/__init__.py` | Package marker |
| `api/routes/status.py` | `GET /api/status` — bot running state, last scan time |
| `api/routes/market.py` | `GET /api/market` — latest market snapshot per symbol |
| `api/routes/rejections.py` | `GET /api/rejections` — scan rejection history |
| `api/routes/trades.py` | `GET /api/trades` — open/closed trades, daily P&L |
| `api/routes/iv_history.py` | `GET /api/iv-history` — IV history for a symbol |
| `api/routes/settings.py` | `GET/PUT /api/settings` — read/write bot config |
| `api/requirements.txt` | FastAPI + uvicorn deps |

### New files — Frontend
| File | Responsibility |
|------|---------------|
| `frontend/package.json` | Deps and scripts |
| `frontend/tsconfig.json` | TypeScript config |
| `frontend/vite.config.ts` | Vite config with proxy to API |
| `frontend/tailwind.config.js` | Tailwind config |
| `frontend/index.html` | HTML entry |
| `frontend/src/main.tsx` | React entry |
| `frontend/src/App.tsx` | Layout composing all dashboard sections |
| `frontend/src/lib/api.ts` | Typed fetch wrappers for all API endpoints |
| `frontend/src/hooks/usePolling.ts` | Generic polling hook (60s) |
| `frontend/src/components/StatusBar.tsx` | Top bar: uptime, mode, last scan, prices |
| `frontend/src/components/MarketOverview.tsx` | Per-symbol cards: price, RSI, IV rank, SMAs |
| `frontend/src/components/RejectionTable.tsx` | Rejection log table with expandable rows |
| `frontend/src/components/TradeHistory.tsx` | Open positions + closed trades tables |
| `frontend/src/components/SettingsPanel.tsx` | Slide-out settings editor with tabbed sections |

### Modified files — Bot
| File | Change |
|------|--------|
| `src/db/mongo.py` | Add `get_settings()`, `save_settings()`, `seed_settings()` methods |
| `src/config.py` | Add `load_config_from_db()` that deep-merges MongoDB over YAML defaults |
| `src/scheduler.py` | Re-read config from DB at start of each `_scan_loop` cycle |

### Test files
| File | Tests |
|------|-------|
| `tests/test_api/test_status.py` | Status endpoint |
| `tests/test_api/test_market.py` | Market endpoint |
| `tests/test_api/test_rejections.py` | Rejections endpoint with filtering |
| `tests/test_api/test_trades.py` | Trades endpoint |
| `tests/test_api/test_settings.py` | Settings GET/PUT and merge logic |
| `tests/test_config_db.py` | Config loading with MongoDB override |

---

## Task 1: MongoDB Settings Methods

**Files:**
- Modify: `src/db/mongo.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write tests for settings methods**

Add to `tests/test_db.py`:

```python
def test_get_settings_returns_none_when_empty(mock_db):
    store = MongoStore.__new__(MongoStore)
    store._client = mock_db._client
    store.db = mock_db.db
    result = store.get_settings()
    assert result is None


def test_save_settings_upserts(mock_db):
    store = MongoStore.__new__(MongoStore)
    store._client = mock_db._client
    store.db = mock_db.db
    store.save_settings({"symbols": ["SPY"], "risk": {"daily_loss_limit": 500}})
    result = store.get_settings()
    assert result["symbols"] == ["SPY"]
    assert result["risk"]["daily_loss_limit"] == 500


def test_save_settings_merges(mock_db):
    store = MongoStore.__new__(MongoStore)
    store._client = mock_db._client
    store.db = mock_db.db
    store.save_settings({"symbols": ["SPY"], "risk": {"daily_loss_limit": 500}})
    store.save_settings({"risk": {"daily_loss_limit": 1000}})
    result = store.get_settings()
    assert result["symbols"] == ["SPY"]
    assert result["risk"]["daily_loss_limit"] == 1000


def test_seed_settings_does_not_overwrite(mock_db):
    store = MongoStore.__new__(MongoStore)
    store._client = mock_db._client
    store.db = mock_db.db
    store.save_settings({"symbols": ["AAPL"]})
    store.seed_settings({"symbols": ["SPY", "QQQ"], "risk": {"daily_loss_limit": 500}})
    result = store.get_settings()
    assert result["symbols"] == ["AAPL"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_db.py -v -k "settings"`
Expected: FAIL — `AttributeError: 'MongoStore' object has no attribute 'get_settings'`

- [ ] **Step 3: Implement settings methods in MongoStore**

Add to `src/db/mongo.py`:

```python
from datetime import datetime, timezone

# Add these methods to the MongoStore class:

def get_settings(self) -> dict | None:
    doc = self.db["settings"].find_one({"_id": "config"})
    if doc:
        doc.pop("_id", None)
    return doc

def save_settings(self, settings: dict) -> dict:
    settings["updated_at"] = datetime.now(timezone.utc)
    self.db["settings"].update_one(
        {"_id": "config"},
        {"$set": settings},
        upsert=True,
    )
    return self.get_settings()

def seed_settings(self, defaults: dict) -> None:
    existing = self.get_settings()
    if existing is not None:
        return
    self.save_settings(defaults)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_db.py -v -k "settings"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/db/mongo.py tests/test_db.py
git commit -m "feat: add MongoDB settings get/save/seed methods"
```

---

## Task 2: Config Loading from MongoDB

**Files:**
- Modify: `src/config.py`
- Create: `tests/test_config_db.py`

- [ ] **Step 1: Write tests for DB-backed config loading**

Create `tests/test_config_db.py`:

```python
import tempfile
import os
import pytest
from unittest.mock import MagicMock
from src.config import load_config, _deep_merge


def test_deep_merge_overwrites_scalar():
    base = {"a": 1, "b": 2}
    override = {"b": 3}
    result = _deep_merge(base, override)
    assert result == {"a": 1, "b": 3}


def test_deep_merge_recurses_dicts():
    base = {"risk": {"daily_loss_limit": 1000, "dte_exit": 1}}
    override = {"risk": {"daily_loss_limit": 500}}
    result = _deep_merge(base, override)
    assert result == {"risk": {"daily_loss_limit": 500, "dte_exit": 1}}


def test_deep_merge_does_not_mutate_base():
    base = {"a": {"b": 1}}
    override = {"a": {"b": 2}}
    _deep_merge(base, override)
    assert base == {"a": {"b": 1}}


def test_load_config_uses_db_override(tmp_path):
    yaml_content = """
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
  min_signals_required: 3
  min_move_from_open_pct: 0.8
  strong_move_pct: 1.5
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
  scan_interval_minutes: 2
  market_hours_only: true
notifications:
  sms_enabled: true
  email_enabled: true
  sms_events: ["fill", "stop_loss", "roll", "circuit_breaker", "error"]
  email_events: ["daily_summary", "weekly_recap"]
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)

    mock_db = MagicMock()
    mock_db.get_settings.return_value = {
        "risk": {"daily_loss_limit": 500},
    }

    config = load_config(config_path=str(config_file), db=mock_db)
    assert config.risk.daily_loss_limit == 500
    assert config.risk.max_concurrent_spreads == 10  # unchanged
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_config_db.py -v`
Expected: FAIL — `_deep_merge` not found, `load_config` doesn't accept `db` param

- [ ] **Step 3: Add `_deep_merge` and update `load_config` in `src/config.py`**

Add the `_deep_merge` helper and update `load_config`:

```python
import copy

def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(config_path: str = "config/config.yaml", db=None) -> AppConfig:
    env_path = Path(config_path).parent / ".env"
    if env_path.exists():
        load_dotenv(str(env_path))

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    # Apply MongoDB overrides if available
    if db is not None:
        db_settings = db.get_settings()
        if db_settings is not None:
            db_settings.pop("updated_at", None)
            raw = _deep_merge(raw, db_settings)
        else:
            db.seed_settings(raw)

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

Run: `python3 -m pytest tests/test_config_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config_db.py
git commit -m "feat: add MongoDB config override with deep merge"
```

---

## Task 3: Bot Re-reads Config Each Scan Cycle

**Files:**
- Modify: `src/scheduler.py`
- Modify: `src/main.py`

- [ ] **Step 1: Update scheduler to reload config from DB each scan**

In `src/scheduler.py`, update `_scan_loop` to reload config at the start:

```python
# At the top of _scan_loop, add:
def _scan_loop(self) -> None:
    if not self._is_market_hours():
        return
    # Reload config from DB
    try:
        from src.config import load_config
        self._config = load_config(db=self._db)
    except Exception:
        logger.exception("Failed to reload config from DB, using cached config")
    for symbol in self._config.symbols:
        try:
            self._scan_symbol(symbol)
        except Exception:
            logger.exception(f"Error scanning {symbol}")
```

- [ ] **Step 2: Update `src/main.py` to pass `db` to `load_config`**

In `src/main.py`, update the initial config load to pass db and seed settings:

```python
# After creating MongoStore, reload config with DB:
db = MongoStore(config.mongodb_uri, config.mongodb_db_name)
config = load_config(db=db)  # Now includes DB overrides, seeds if first run
```

- [ ] **Step 3: Run existing tests to verify no regressions**

Run: `python3 -m pytest tests/ -v`
Expected: All existing tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/scheduler.py src/main.py
git commit -m "feat: bot reloads config from MongoDB each scan cycle"
```

---

## Task 4: FastAPI App Skeleton + DB Connection

**Files:**
- Create: `api/__init__.py`
- Create: `api/main.py`
- Create: `api/db.py`
- Create: `api/routes/__init__.py`
- Create: `api/requirements.txt`

- [ ] **Step 1: Create `api/requirements.txt`**

```
fastapi>=0.115.0
uvicorn>=0.34.0
pymongo>=4.9.0
python-dotenv>=1.0.1
pyyaml>=6.0.2
```

- [ ] **Step 2: Install API dependencies**

Run: `python3 -m pip install fastapi uvicorn`

- [ ] **Step 3: Create `api/__init__.py`**

Empty file.

- [ ] **Step 4: Create `api/routes/__init__.py`**

Empty file.

- [ ] **Step 5: Create `api/db.py`**

```python
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("config/.env")

_client: MongoClient | None = None


def get_db():
    global _client
    if _client is None:
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGODB_DB_NAME", "auto_trader")
        _client = MongoClient(uri)
    db_name = os.getenv("MONGODB_DB_NAME", "auto_trader")
    return _client[db_name]
```

- [ ] **Step 6: Create `api/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import status, market, rejections, trades, iv_history, settings

app = FastAPI(title="Auto-Trader Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(status.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(rejections.router, prefix="/api")
app.include_router(trades.router, prefix="/api")
app.include_router(iv_history.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
```

- [ ] **Step 7: Commit**

```bash
git add api/
git commit -m "feat: FastAPI app skeleton with CORS and DB connection"
```

---

## Task 5: API Status Endpoint

**Files:**
- Create: `api/routes/status.py`
- Create: `tests/test_api/__init__.py`
- Create: `tests/test_api/test_status.py`

- [ ] **Step 1: Write test**

Create `tests/test_api/__init__.py` (empty) and `tests/test_api/test_status.py`:

```python
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_status_returns_running_with_recent_scan():
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock()
    scan_col = MagicMock()
    settings_col = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: {
        "scan_rejections": scan_col,
        "settings": settings_col,
    }[name]

    scan_col.find_one.return_value = {
        "timestamp": datetime(2026, 4, 1, 15, 0, 0, tzinfo=timezone.utc),
        "symbol": "SPY",
    }
    settings_col.find_one.return_value = {
        "_id": "config",
        "symbols": ["SPY", "QQQ"],
    }

    with patch("api.routes.status.get_db", return_value=mock_db):
        resp = client.get("/api/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["running"] is True
    assert data["symbols"] == ["SPY", "QQQ"]
    assert "last_scan_time" in data


def test_status_returns_not_running_when_no_scans():
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock()
    scan_col = MagicMock()
    settings_col = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: {
        "scan_rejections": scan_col,
        "settings": settings_col,
    }[name]

    scan_col.find_one.return_value = None
    settings_col.find_one.return_value = None

    with patch("api.routes.status.get_db", return_value=mock_db):
        resp = client.get("/api/status")

    assert resp.status_code == 200
    assert resp.json()["running"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_api/test_status.py -v`
Expected: FAIL — module `api.routes.status` not found

- [ ] **Step 3: Implement status route**

Create `api/routes/status.py`:

```python
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from api.db import get_db

router = APIRouter()


@router.get("/status")
def get_status():
    db = get_db()
    last_scan = db["scan_rejections"].find_one(
        sort=[("timestamp", -1)]
    )

    running = False
    last_scan_time = None
    if last_scan and "timestamp" in last_scan:
        last_scan_time = last_scan["timestamp"].isoformat() if last_scan["timestamp"] else None
        age = datetime.now(timezone.utc) - last_scan["timestamp"].replace(tzinfo=timezone.utc)
        running = age < timedelta(minutes=5)

    paper_mode = os.getenv("ALPACA_PAPER", "true").lower() == "true"

    settings_doc = db["settings"].find_one({"_id": "config"})
    symbols = settings_doc.get("symbols", []) if settings_doc else []

    return {
        "running": running,
        "paper_mode": paper_mode,
        "last_scan_time": last_scan_time,
        "symbols": symbols,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_api/test_status.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/routes/status.py tests/test_api/
git commit -m "feat: add /api/status endpoint"
```

---

## Task 6: API Market, Rejections, Trades, IV History Endpoints

**Files:**
- Create: `api/routes/market.py`
- Create: `api/routes/rejections.py`
- Create: `api/routes/trades.py`
- Create: `api/routes/iv_history.py`
- Create: `tests/test_api/test_market.py`
- Create: `tests/test_api/test_rejections.py`
- Create: `tests/test_api/test_trades.py`

- [ ] **Step 1: Create `api/routes/market.py`**

```python
from fastapi import APIRouter
from api.db import get_db

router = APIRouter()


@router.get("/market")
def get_market():
    db = get_db()
    pipeline = [
        {"$sort": {"timestamp": -1}},
        {"$group": {
            "_id": "$symbol",
            "symbol": {"$first": "$symbol"},
            "timestamp": {"$first": "$timestamp"},
            "market_snapshot": {"$first": "$market_snapshot"},
        }},
    ]
    results = list(db["scan_rejections"].aggregate(pipeline))
    return [
        {
            "symbol": r["symbol"],
            "timestamp": r["timestamp"].isoformat() if r.get("timestamp") else None,
            **(r.get("market_snapshot") or {}),
        }
        for r in results
    ]
```

- [ ] **Step 2: Create `api/routes/rejections.py`**

```python
from fastapi import APIRouter, Query
from api.db import get_db

router = APIRouter()


@router.get("/rejections")
def get_rejections(
    limit: int = Query(50, ge=1, le=500),
    symbol: str = Query(""),
    strategy: str = Query(""),
):
    db = get_db()
    query = {}
    if symbol:
        query["symbol"] = symbol
    if strategy:
        query["rejections.strategy"] = strategy

    total = db["scan_rejections"].count_documents(query)
    cursor = db["scan_rejections"].find(query).sort("timestamp", -1).limit(limit)
    items = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if "timestamp" in doc:
            doc["timestamp"] = doc["timestamp"].isoformat()
        items.append(doc)

    return {"items": items, "total": total}
```

- [ ] **Step 3: Create `api/routes/trades.py`**

```python
from datetime import datetime, time, timezone
from fastapi import APIRouter
from api.db import get_db

router = APIRouter()


@router.get("/trades")
def get_trades():
    db = get_db()
    today_start = datetime.combine(
        datetime.now(timezone.utc).date(), time.min
    ).replace(tzinfo=timezone.utc)

    all_trades = list(db["trades"].find().sort("opened_at", -1))
    open_trades = []
    closed_trades = []
    daily_pnl = 0.0

    for t in all_trades:
        t["_id"] = str(t["_id"])
        for key in ("opened_at", "closed_at"):
            if key in t and t[key]:
                t[key] = t[key].isoformat()
        if "expiration" in t and t["expiration"]:
            t["expiration"] = str(t["expiration"])

        if t.get("closed_at"):
            closed_trades.append(t)
            closed_time = t.get("closed_at", "")
            if closed_time and closed_time >= today_start.isoformat():
                daily_pnl += t.get("realized_pnl", 0.0)
        else:
            open_trades.append(t)

    return {
        "open": open_trades,
        "closed": closed_trades,
        "daily_pnl": round(daily_pnl, 2),
    }
```

- [ ] **Step 4: Create `api/routes/iv_history.py`**

```python
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query
from api.db import get_db

router = APIRouter()


@router.get("/iv-history")
def get_iv_history(symbol: str = Query("SPY"), days: int = Query(30, ge=1, le=365)):
    db = get_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)
    cursor = db["iv_history"].find(
        {"symbol": symbol, "timestamp": {"$gte": since}}
    ).sort("timestamp", 1)

    return [
        {"timestamp": r["timestamp"].isoformat(), "iv": r["iv"]}
        for r in cursor
    ]
```

- [ ] **Step 5: Write test for rejections endpoint**

Create `tests/test_api/test_rejections.py`:

```python
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_rejections_returns_items():
    mock_db = MagicMock()
    col = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=col)
    col.count_documents.return_value = 1
    col.find.return_value.sort.return_value.limit.return_value = [
        {
            "_id": "abc123",
            "symbol": "SPY",
            "timestamp": datetime(2026, 4, 1, 15, 0, tzinfo=timezone.utc),
            "market_snapshot": {"price": 656.66},
            "rejections": [{"strategy": "swing", "reason": "iv_rank_unavailable", "variables": {}}],
        }
    ]

    with patch("api.routes.rejections.get_db", return_value=mock_db):
        resp = client.get("/api/rejections?limit=10")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["symbol"] == "SPY"


def test_rejections_filters_by_symbol():
    mock_db = MagicMock()
    col = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=col)
    col.count_documents.return_value = 0
    col.find.return_value.sort.return_value.limit.return_value = []

    with patch("api.routes.rejections.get_db", return_value=mock_db):
        resp = client.get("/api/rejections?symbol=QQQ")

    assert resp.status_code == 200
    col.find.assert_called_once_with({"symbol": "QQQ"})
```

- [ ] **Step 6: Run all API tests**

Run: `python3 -m pytest tests/test_api/ -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add api/routes/ tests/test_api/
git commit -m "feat: add market, rejections, trades, iv-history API endpoints"
```

---

## Task 7: API Settings Endpoint

**Files:**
- Create: `api/routes/settings.py`
- Create: `tests/test_api/test_settings.py`

- [ ] **Step 1: Write tests**

Create `tests/test_api/test_settings.py`:

```python
import copy
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

SAMPLE_SETTINGS = {
    "symbols": ["SPY", "QQQ"],
    "swing": {"target_dte": [7, 10], "min_premium": 0.50},
    "risk": {"daily_loss_limit": 1000},
    "updated_at": datetime(2026, 4, 1, 15, 0, tzinfo=timezone.utc),
}


def test_get_settings():
    mock_db = MagicMock()
    col = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=col)
    doc = {"_id": "config", **copy.deepcopy(SAMPLE_SETTINGS)}
    col.find_one.return_value = doc

    with patch("api.routes.settings.get_db", return_value=mock_db):
        resp = client.get("/api/settings")

    assert resp.status_code == 200
    data = resp.json()
    assert data["symbols"] == ["SPY", "QQQ"]
    assert "_id" not in data


def test_put_settings_merges():
    mock_db = MagicMock()
    col = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=col)

    updated = {"_id": "config", "symbols": ["SPY", "QQQ"], "risk": {"daily_loss_limit": 500}, "updated_at": datetime(2026, 4, 1, 16, 0, tzinfo=timezone.utc)}
    col.find_one.return_value = updated

    with patch("api.routes.settings.get_db", return_value=mock_db):
        resp = client.put("/api/settings", json={"risk": {"daily_loss_limit": 500}})

    assert resp.status_code == 200
    col.update_one.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_api/test_settings.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement settings route**

Create `api/routes/settings.py`:

```python
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from api.db import get_db

router = APIRouter()


@router.get("/settings")
def get_settings():
    db = get_db()
    doc = db["settings"].find_one({"_id": "config"})
    if not doc:
        return {}
    doc.pop("_id", None)
    if "updated_at" in doc:
        doc["updated_at"] = doc["updated_at"].isoformat()
    return doc


@router.put("/settings")
async def put_settings(request: Request):
    db = get_db()
    body = await request.json()
    body["updated_at"] = datetime.now(timezone.utc)
    db["settings"].update_one(
        {"_id": "config"},
        {"$set": body},
        upsert=True,
    )
    doc = db["settings"].find_one({"_id": "config"})
    doc.pop("_id", None)
    if "updated_at" in doc:
        doc["updated_at"] = doc["updated_at"].isoformat()
    return doc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_api/test_settings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/routes/settings.py tests/test_api/test_settings.py
git commit -m "feat: add GET/PUT /api/settings endpoint"
```

---

## Task 8: Scaffold React + Vite + shadcn/ui + Tailwind

**Files:**
- Create: `frontend/` (entire scaffold)

- [ ] **Step 1: Create Vite React TypeScript project**

```bash
cd /Users/antonioschaffert/workspace/auto-trader
npm create vite@latest frontend -- --template react-ts
```

- [ ] **Step 2: Install dependencies**

```bash
cd frontend
npm install
npm install tailwindcss @tailwindcss/vite
```

- [ ] **Step 3: Configure Tailwind in `frontend/vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
```

- [ ] **Step 4: Add Tailwind import to `frontend/src/index.css`**

Replace contents with:

```css
@import "tailwindcss";
```

- [ ] **Step 5: Initialize shadcn/ui**

```bash
cd frontend
npx shadcn@latest init -d
```

- [ ] **Step 6: Add shadcn/ui components**

```bash
cd frontend
npx shadcn@latest add card table badge collapsible select skeleton sheet tabs input switch label separator
```

- [ ] **Step 7: Verify dev server starts**

Run: `cd frontend && npm run dev`
Expected: Vite dev server starts on http://localhost:5173

- [ ] **Step 8: Commit**

```bash
cd /Users/antonioschaffert/workspace/auto-trader
git add frontend/
git commit -m "feat: scaffold React + Vite + Tailwind + shadcn/ui frontend"
```

---

## Task 9: API Client + Polling Hook

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/hooks/usePolling.ts`

- [ ] **Step 1: Create `frontend/src/lib/api.ts`**

```typescript
export interface StatusData {
  running: boolean;
  paper_mode: boolean;
  last_scan_time: string | null;
  symbols: string[];
}

export interface MarketData {
  symbol: string;
  price: number;
  iv_rank: number | null;
  rsi: number | null;
  sma_50: number | null;
  sma_20: number | null;
  current_iv: number | null;
  timestamp: string;
}

export interface Rejection {
  strategy: string;
  reason: string;
  spread_type?: string;
  variables: Record<string, unknown>;
}

export interface ScanRejection {
  _id: string;
  symbol: string;
  timestamp: string;
  market_snapshot: Record<string, unknown>;
  rejections: Rejection[];
}

export interface RejectionsResponse {
  items: ScanRejection[];
  total: number;
}

export interface TradesResponse {
  open: Record<string, unknown>[];
  closed: Record<string, unknown>[];
  daily_pnl: number;
}

export interface IvPoint {
  timestamp: string;
  iv: number;
}

export interface Settings {
  symbols: string[];
  swing: Record<string, unknown>;
  exhaustion: Record<string, unknown>;
  risk: Record<string, unknown>;
  execution: Record<string, unknown>;
  schedule: Record<string, unknown>;
  notifications: Record<string, unknown>;
  updated_at?: string;
}

const BASE = "/api";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  getStatus: () => fetchJson<StatusData>("/status"),
  getMarket: () => fetchJson<MarketData[]>("/market"),
  getRejections: (limit = 50, symbol = "", strategy = "") => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (symbol) params.set("symbol", symbol);
    if (strategy) params.set("strategy", strategy);
    return fetchJson<RejectionsResponse>(`/rejections?${params}`);
  },
  getTrades: () => fetchJson<TradesResponse>("/trades"),
  getIvHistory: (symbol: string, days = 30) =>
    fetchJson<IvPoint[]>(`/iv-history?symbol=${symbol}&days=${days}`),
  getSettings: () => fetchJson<Settings>("/settings"),
  putSettings: async (settings: Partial<Settings>): Promise<Settings> => {
    const res = await fetch(`${BASE}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  },
};
```

- [ ] **Step 2: Create `frontend/src/hooks/usePolling.ts`**

```typescript
import { useState, useEffect, useCallback } from "react";

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number = 60_000,
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const result = await fetcher();
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [fetcher]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, intervalMs);
    return () => clearInterval(id);
  }, [refresh, intervalMs]);

  return { data, error, loading, refresh };
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/antonioschaffert/workspace/auto-trader
git add frontend/src/lib/ frontend/src/hooks/
git commit -m "feat: add API client and polling hook"
```

---

## Task 10: StatusBar Component

**Files:**
- Create: `frontend/src/components/StatusBar.tsx`

- [ ] **Step 1: Create StatusBar component**

```tsx
import { Badge } from "@/components/ui/badge";
import { StatusData, MarketData } from "@/lib/api";

interface Props {
  status: StatusData | null;
  market: MarketData[] | null;
  onOpenSettings: () => void;
}

export function StatusBar({ status, market, onOpenSettings }: Props) {
  const lastScan = status?.last_scan_time
    ? new Date(status.last_scan_time).toLocaleTimeString()
    : "—";

  return (
    <div className="flex items-center justify-between border-b px-6 py-3 bg-background">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div
            className={`h-2.5 w-2.5 rounded-full ${status?.running ? "bg-green-500" : "bg-red-500"}`}
          />
          <span className="text-sm font-medium">
            {status?.running ? "Running" : "Stopped"}
          </span>
        </div>
        <Badge variant={status?.paper_mode ? "secondary" : "destructive"}>
          {status?.paper_mode ? "Paper" : "Live"}
        </Badge>
        <span className="text-sm text-muted-foreground">
          Last scan: {lastScan}
        </span>
      </div>
      <div className="flex items-center gap-4">
        {market?.map((m) => (
          <span key={m.symbol} className="text-sm font-mono">
            {m.symbol}{" "}
            <span className="font-semibold">${m.price?.toFixed(2)}</span>
          </span>
        ))}
        <button
          onClick={onOpenSettings}
          className="text-muted-foreground hover:text-foreground transition-colors"
          title="Settings"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/StatusBar.tsx
git commit -m "feat: add StatusBar component"
```

---

## Task 11: MarketOverview Component

**Files:**
- Create: `frontend/src/components/MarketOverview.tsx`

- [ ] **Step 1: Create MarketOverview component**

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MarketData } from "@/lib/api";

interface Props {
  market: MarketData[] | null;
}

function getBias(m: MarketData): { label: string; variant: "default" | "secondary" | "destructive" } {
  if (m.sma_50 == null || m.rsi == null) return { label: "Neutral", variant: "secondary" };
  const aboveSma = m.price > m.sma_50;
  if (aboveSma && m.rsi < 70) return { label: "Bullish", variant: "default" };
  if (!aboveSma && m.rsi > 30) return { label: "Bearish", variant: "destructive" };
  return { label: "Neutral", variant: "secondary" };
}

function rsiColor(rsi: number | null): string {
  if (rsi == null) return "text-muted-foreground";
  if (rsi > 70) return "text-red-500";
  if (rsi < 30) return "text-green-500";
  return "text-foreground";
}

export function MarketOverview({ market }: Props) {
  if (!market || market.length === 0) {
    return null;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {market.map((m) => {
        const bias = getBias(m);
        return (
          <Card key={m.symbol}>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">{m.symbol}</CardTitle>
                <Badge variant={bias.variant}>{bias.label}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-y-1 text-sm">
                <div className="text-muted-foreground">Price</div>
                <div className="text-right font-mono font-semibold">
                  ${m.price?.toFixed(2)}
                </div>
                <div className="text-muted-foreground">RSI (14)</div>
                <div className={`text-right font-mono ${rsiColor(m.rsi)}`}>
                  {m.rsi?.toFixed(1) ?? "—"}
                </div>
                <div className="text-muted-foreground">IV Rank</div>
                <div className="text-right font-mono">
                  {m.iv_rank != null ? `${m.iv_rank.toFixed(0)}%` : "—"}
                </div>
                <div className="text-muted-foreground">SMA 50</div>
                <div className="text-right font-mono">
                  {m.sma_50 != null ? `$${m.sma_50.toFixed(2)}` : "—"}
                </div>
                <div className="text-muted-foreground">SMA 20</div>
                <div className="text-right font-mono">
                  {m.sma_20 != null ? `$${m.sma_20.toFixed(2)}` : "—"}
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/MarketOverview.tsx
git commit -m "feat: add MarketOverview component"
```

---

## Task 12: RejectionTable Component

**Files:**
- Create: `frontend/src/components/RejectionTable.tsx`

- [ ] **Step 1: Create RejectionTable component**

```tsx
import { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RejectionsResponse } from "@/lib/api";

interface Props {
  data: RejectionsResponse | null;
  onFilterChange: (symbol: string, strategy: string) => void;
  symbols: string[];
}

export function RejectionTable({ data, onFilterChange, symbols }: Props) {
  const [symbolFilter, setSymbolFilter] = useState("");
  const [strategyFilter, setStrategyFilter] = useState("");
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const toggleRow = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSymbol = (val: string) => {
    const v = val === "all" ? "" : val;
    setSymbolFilter(v);
    onFilterChange(v, strategyFilter);
  };

  const handleStrategy = (val: string) => {
    const v = val === "all" ? "" : val;
    setStrategyFilter(v);
    onFilterChange(symbolFilter, v);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold">Scan Rejections</h2>
        <div className="flex gap-2">
          <Select value={symbolFilter || "all"} onValueChange={handleSymbol}>
            <SelectTrigger className="w-[120px]">
              <SelectValue placeholder="Symbol" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              {symbols.map((s) => (
                <SelectItem key={s} value={s}>{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={strategyFilter || "all"} onValueChange={handleStrategy}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Strategy" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="swing">Swing</SelectItem>
              <SelectItem value="exhaustion">Exhaustion</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="text-sm text-muted-foreground mb-2">
        {data?.total ?? 0} total rejections
      </div>
      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[180px]">Time</TableHead>
              <TableHead className="w-[80px]">Symbol</TableHead>
              <TableHead className="w-[100px]">Strategy</TableHead>
              <TableHead>Reason</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.items.map((scan) =>
              scan.rejections.map((rej, i) => {
                const rowId = `${scan._id}-${i}`;
                const isExpanded = expandedRows.has(rowId);
                return (
                  <Collapsible key={rowId} open={isExpanded} onOpenChange={() => toggleRow(rowId)} asChild>
                    <>
                      <CollapsibleTrigger asChild>
                        <TableRow className="cursor-pointer hover:bg-muted/50">
                          <TableCell className="font-mono text-xs">
                            {new Date(scan.timestamp).toLocaleString()}
                          </TableCell>
                          <TableCell>{scan.symbol}</TableCell>
                          <TableCell>
                            <Badge variant="outline">{rej.strategy}</Badge>
                          </TableCell>
                          <TableCell>{rej.reason}</TableCell>
                        </TableRow>
                      </CollapsibleTrigger>
                      <CollapsibleContent asChild>
                        <TableRow>
                          <TableCell colSpan={4} className="bg-muted/30 p-4">
                            <pre className="text-xs font-mono whitespace-pre-wrap">
                              {JSON.stringify(rej.variables, null, 2)}
                            </pre>
                          </TableCell>
                        </TableRow>
                      </CollapsibleContent>
                    </>
                  </Collapsible>
                );
              })
            )}
            {(!data || data.items.length === 0) && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                  No rejections recorded yet
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/RejectionTable.tsx
git commit -m "feat: add RejectionTable component"
```

---

## Task 13: TradeHistory Component

**Files:**
- Create: `frontend/src/components/TradeHistory.tsx`

- [ ] **Step 1: Create TradeHistory component**

```tsx
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TradesResponse } from "@/lib/api";

interface Props {
  data: TradesResponse | null;
}

export function TradeHistory({ data }: Props) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Trade History</h2>
        <Card className="px-4 py-2">
          <span className="text-sm text-muted-foreground">Daily P&L: </span>
          <span
            className={`font-mono font-semibold ${
              (data?.daily_pnl ?? 0) >= 0 ? "text-green-500" : "text-red-500"
            }`}
          >
            ${data?.daily_pnl?.toFixed(2) ?? "0.00"}
          </span>
        </Card>
      </div>

      {(data?.open?.length ?? 0) > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-2">Open Positions</h3>
          <div className="border rounded-md">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Entry</TableHead>
                  <TableHead>Current</TableHead>
                  <TableHead>P&L</TableHead>
                  <TableHead>Expiration</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.open.map((t, i) => (
                  <TableRow key={i}>
                    <TableCell>{String(t.symbol ?? "")}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{String(t.spread_type ?? "")}</Badge>
                    </TableCell>
                    <TableCell className="font-mono">
                      ${Number(t.entry_premium ?? 0).toFixed(2)}
                    </TableCell>
                    <TableCell className="font-mono">
                      ${Number(t.current_value ?? 0).toFixed(2)}
                    </TableCell>
                    <TableCell
                      className={`font-mono ${
                        Number(t.unrealized_pnl ?? 0) >= 0
                          ? "text-green-500"
                          : "text-red-500"
                      }`}
                    >
                      ${Number(t.unrealized_pnl ?? 0).toFixed(2)}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {String(t.expiration ?? "")}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      <div>
        <h3 className="text-sm font-medium text-muted-foreground mb-2">Closed Trades</h3>
        <div className="border rounded-md">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Symbol</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Entry</TableHead>
                <TableHead>Exit</TableHead>
                <TableHead>P&L</TableHead>
                <TableHead>Reason</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.closed.map((t, i) => (
                <TableRow key={i}>
                  <TableCell>{String(t.symbol ?? "")}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{String(t.spread_type ?? "")}</Badge>
                  </TableCell>
                  <TableCell className="font-mono">
                    ${Number(t.entry_premium ?? 0).toFixed(2)}
                  </TableCell>
                  <TableCell className="font-mono">
                    ${Number(t.close_premium ?? 0).toFixed(2)}
                  </TableCell>
                  <TableCell
                    className={`font-mono ${
                      Number(t.realized_pnl ?? 0) >= 0
                        ? "text-green-500"
                        : "text-red-500"
                    }`}
                  >
                    ${Number(t.realized_pnl ?? 0).toFixed(2)}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{String(t.close_reason ?? "")}</Badge>
                  </TableCell>
                </TableRow>
              ))}
              {(!data?.closed || data.closed.length === 0) && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                    No closed trades yet
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/TradeHistory.tsx
git commit -m "feat: add TradeHistory component"
```

---

## Task 14: SettingsPanel Component

**Files:**
- Create: `frontend/src/components/SettingsPanel.tsx`

- [ ] **Step 1: Create SettingsPanel component**

```tsx
import { useState, useEffect } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Settings, api } from "@/lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
  settings: Settings | null;
  onSaved: () => void;
}

function Field({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string | number;
  onChange: (v: string) => void;
  type?: string;
}) {
  return (
    <div className="grid grid-cols-2 items-center gap-2">
      <Label className="text-sm">{label}</Label>
      <Input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8"
      />
    </div>
  );
}

function ToggleField({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between">
      <Label className="text-sm">{label}</Label>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}

export function SettingsPanel({ open, onClose, settings, onSaved }: Props) {
  const [local, setLocal] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  useEffect(() => {
    if (settings) setLocal(structuredClone(settings));
  }, [settings]);

  if (!local) return null;

  const update = (section: string, key: string, value: unknown) => {
    setLocal((prev) => {
      if (!prev) return prev;
      const next = structuredClone(prev);
      (next as Record<string, Record<string, unknown>>)[section][key] = value;
      return next;
    });
  };

  const save = async (section: string) => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {};
      if (section === "general") {
        payload.symbols = local.symbols;
        payload.schedule = local.schedule;
      } else {
        payload[section] = (local as Record<string, unknown>)[section];
      }
      await api.putSettings(payload as Partial<Settings>);
      setSavedAt(new Date().toLocaleTimeString());
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  const swing = local.swing as Record<string, unknown>;
  const exhaustion = local.exhaustion as Record<string, unknown>;
  const risk = local.risk as Record<string, unknown>;
  const execution = local.execution as Record<string, unknown>;
  const schedule = local.schedule as Record<string, unknown>;
  const notifications = local.notifications as Record<string, unknown>;

  return (
    <Sheet open={open} onOpenChange={onClose}>
      <SheetContent className="w-[450px] sm:w-[500px] overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Settings</SheetTitle>
          {savedAt && (
            <p className="text-xs text-muted-foreground">Last saved: {savedAt}</p>
          )}
        </SheetHeader>
        <Tabs defaultValue="general" className="mt-4">
          <TabsList className="grid grid-cols-3 mb-4">
            <TabsTrigger value="general">General</TabsTrigger>
            <TabsTrigger value="swing">Swing</TabsTrigger>
            <TabsTrigger value="exhaustion">Exhaust.</TabsTrigger>
          </TabsList>
          <TabsList className="grid grid-cols-3 mb-4">
            <TabsTrigger value="risk">Risk</TabsTrigger>
            <TabsTrigger value="execution">Execution</TabsTrigger>
            <TabsTrigger value="notifications">Notif.</TabsTrigger>
          </TabsList>

          <TabsContent value="general" className="space-y-3">
            <Field
              label="Symbols"
              value={local.symbols.join(", ")}
              onChange={(v) =>
                setLocal((p) => p ? { ...p, symbols: v.split(",").map((s) => s.trim()).filter(Boolean) } : p)
              }
            />
            <Field
              label="Scan Interval (min)"
              value={Number(schedule.scan_interval_minutes)}
              onChange={(v) => update("schedule", "scan_interval_minutes", Number(v))}
              type="number"
            />
            <ToggleField
              label="Market Hours Only"
              checked={Boolean(schedule.market_hours_only)}
              onChange={(v) => update("schedule", "market_hours_only", v)}
            />
            <Separator />
            <button onClick={() => save("general")} disabled={saving}
              className="w-full bg-primary text-primary-foreground rounded-md py-2 text-sm hover:bg-primary/90 disabled:opacity-50">
              {saving ? "Saving..." : "Save General"}
            </button>
          </TabsContent>

          <TabsContent value="swing" className="space-y-3">
            <Field label="Min Premium" value={Number(swing.min_premium)} onChange={(v) => update("swing", "min_premium", Number(v))} type="number" />
            <Field label="IV Rank Threshold" value={Number(swing.iv_rank_threshold)} onChange={(v) => update("swing", "iv_rank_threshold", Number(v))} type="number" />
            <Field label="Profit Target %" value={Number(swing.profit_target_pct)} onChange={(v) => update("swing", "profit_target_pct", Number(v))} type="number" />
            <Separator />
            <button onClick={() => save("swing")} disabled={saving}
              className="w-full bg-primary text-primary-foreground rounded-md py-2 text-sm hover:bg-primary/90 disabled:opacity-50">
              {saving ? "Saving..." : "Save Swing"}
            </button>
          </TabsContent>

          <TabsContent value="exhaustion" className="space-y-3">
            <ToggleField label="Enabled" checked={Boolean(exhaustion.enabled)} onChange={(v) => update("exhaustion", "enabled", v)} />
            <Field label="Min Premium" value={Number(exhaustion.min_premium)} onChange={(v) => update("exhaustion", "min_premium", Number(v))} type="number" />
            <Field label="Profit Target %" value={Number(exhaustion.profit_target_pct)} onChange={(v) => update("exhaustion", "profit_target_pct", Number(v))} type="number" />
            <Field label="Stop Loss Multiplier" value={Number(exhaustion.stop_loss_multiplier)} onChange={(v) => update("exhaustion", "stop_loss_multiplier", Number(v))} type="number" />
            <Field label="Time Window Start" value={String(exhaustion.time_window_start)} onChange={(v) => update("exhaustion", "time_window_start", v)} />
            <Field label="RSI Overbought" value={Number(exhaustion.rsi_overbought)} onChange={(v) => update("exhaustion", "rsi_overbought", Number(v))} type="number" />
            <Field label="RSI Oversold" value={Number(exhaustion.rsi_oversold)} onChange={(v) => update("exhaustion", "rsi_oversold", Number(v))} type="number" />
            <Field label="Min Move From Open %" value={Number(exhaustion.min_move_from_open_pct)} onChange={(v) => update("exhaustion", "min_move_from_open_pct", Number(v))} type="number" />
            <Field label="Strong Move %" value={Number(exhaustion.strong_move_pct)} onChange={(v) => update("exhaustion", "strong_move_pct", Number(v))} type="number" />
            <Field label="Min Signals Required" value={Number(exhaustion.min_signals_required)} onChange={(v) => update("exhaustion", "min_signals_required", Number(v))} type="number" />
            <ToggleField label="Close by EOD" checked={Boolean(exhaustion.close_by_eod)} onChange={(v) => update("exhaustion", "close_by_eod", v)} />
            <Separator />
            <button onClick={() => save("exhaustion")} disabled={saving}
              className="w-full bg-primary text-primary-foreground rounded-md py-2 text-sm hover:bg-primary/90 disabled:opacity-50">
              {saving ? "Saving..." : "Save Exhaustion"}
            </button>
          </TabsContent>

          <TabsContent value="risk" className="space-y-3">
            <Field label="Max Concurrent Spreads" value={Number(risk.max_concurrent_spreads)} onChange={(v) => update("risk", "max_concurrent_spreads", Number(v))} type="number" />
            <Field label="Max Risk Per Trade %" value={Number(risk.max_risk_per_trade_pct)} onChange={(v) => update("risk", "max_risk_per_trade_pct", Number(v))} type="number" />
            <Field label="Max Buying Power %" value={Number(risk.max_buying_power_usage_pct)} onChange={(v) => update("risk", "max_buying_power_usage_pct", Number(v))} type="number" />
            <Field label="Stop Loss Multiplier" value={Number(risk.stop_loss_multiplier)} onChange={(v) => update("risk", "stop_loss_multiplier", Number(v))} type="number" />
            <Field label="Roll Delta Threshold" value={Number(risk.roll_delta_threshold)} onChange={(v) => update("risk", "roll_delta_threshold", Number(v))} type="number" />
            <Field label="DTE Exit" value={Number(risk.dte_exit)} onChange={(v) => update("risk", "dte_exit", Number(v))} type="number" />
            <Field label="Daily Loss Limit $" value={Number(risk.daily_loss_limit)} onChange={(v) => update("risk", "daily_loss_limit", Number(v))} type="number" />
            <Field label="Daily Income Target $" value={Number(risk.daily_income_target)} onChange={(v) => update("risk", "daily_income_target", Number(v))} type="number" />
            <Field label="Max Same Direction/Symbol" value={Number(risk.max_same_direction_per_symbol)} onChange={(v) => update("risk", "max_same_direction_per_symbol", Number(v))} type="number" />
            <Field label="Max Portfolio Delta/Symbol" value={Number(risk.max_portfolio_delta_per_symbol)} onChange={(v) => update("risk", "max_portfolio_delta_per_symbol", Number(v))} type="number" />
            <Separator />
            <button onClick={() => save("risk")} disabled={saving}
              className="w-full bg-primary text-primary-foreground rounded-md py-2 text-sm hover:bg-primary/90 disabled:opacity-50">
              {saving ? "Saving..." : "Save Risk"}
            </button>
          </TabsContent>

          <TabsContent value="execution" className="space-y-3">
            <Field label="Price Adj. Interval (s)" value={Number(execution.price_adjustment_interval)} onChange={(v) => update("execution", "price_adjustment_interval", Number(v))} type="number" />
            <Field label="Price Adj. Step $" value={Number(execution.price_adjustment_step)} onChange={(v) => update("execution", "price_adjustment_step", Number(v))} type="number" />
            <Field label="Fill Timeout (s)" value={Number(execution.fill_timeout)} onChange={(v) => update("execution", "fill_timeout", Number(v))} type="number" />
            <Separator />
            <button onClick={() => save("execution")} disabled={saving}
              className="w-full bg-primary text-primary-foreground rounded-md py-2 text-sm hover:bg-primary/90 disabled:opacity-50">
              {saving ? "Saving..." : "Save Execution"}
            </button>
          </TabsContent>

          <TabsContent value="notifications" className="space-y-3">
            <ToggleField label="SMS Enabled" checked={Boolean(notifications.sms_enabled)} onChange={(v) => update("notifications", "sms_enabled", v)} />
            <ToggleField label="Email Enabled" checked={Boolean(notifications.email_enabled)} onChange={(v) => update("notifications", "email_enabled", v)} />
            <Separator />
            <button onClick={() => save("notifications")} disabled={saving}
              className="w-full bg-primary text-primary-foreground rounded-md py-2 text-sm hover:bg-primary/90 disabled:opacity-50">
              {saving ? "Saving..." : "Save Notifications"}
            </button>
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/SettingsPanel.tsx
git commit -m "feat: add SettingsPanel component with tabbed sections"
```

---

## Task 15: App.tsx — Wire Everything Together

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Replace `frontend/src/App.tsx` contents**

```tsx
import { useState, useCallback } from "react";
import { api } from "@/lib/api";
import { usePolling } from "@/hooks/usePolling";
import { StatusBar } from "@/components/StatusBar";
import { MarketOverview } from "@/components/MarketOverview";
import { RejectionTable } from "@/components/RejectionTable";
import { TradeHistory } from "@/components/TradeHistory";
import { SettingsPanel } from "@/components/SettingsPanel";

export default function App() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [rejSymbol, setRejSymbol] = useState("");
  const [rejStrategy, setRejStrategy] = useState("");

  const { data: status, refresh: refreshStatus } = usePolling(api.getStatus);
  const { data: market } = usePolling(api.getMarket);
  const { data: trades } = usePolling(api.getTrades);
  const { data: settings, refresh: refreshSettings } = usePolling(api.getSettings);

  const rejFetcher = useCallback(
    () => api.getRejections(50, rejSymbol, rejStrategy),
    [rejSymbol, rejStrategy],
  );
  const { data: rejections } = usePolling(rejFetcher);

  const handleFilterChange = (symbol: string, strategy: string) => {
    setRejSymbol(symbol);
    setRejStrategy(strategy);
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <StatusBar
        status={status}
        market={market}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <main className="max-w-7xl mx-auto px-6 py-6 space-y-8">
        <MarketOverview market={market} />
        <RejectionTable
          data={rejections}
          onFilterChange={handleFilterChange}
          symbols={status?.symbols ?? []}
        />
        <TradeHistory data={trades} />
      </main>
      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        settings={settings}
        onSaved={() => {
          refreshSettings();
          refreshStatus();
        }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Clean up default Vite files**

Delete `frontend/src/App.css` if it exists. Remove the logo import and default content from `frontend/src/main.tsx` — keep only:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/
git commit -m "feat: wire up App.tsx with all dashboard sections"
```

---

## Task 16: End-to-End Smoke Test

- [ ] **Step 1: Start the API server**

```bash
cd /Users/antonioschaffert/workspace/auto-trader
python3 -m uvicorn api.main:app --reload --port 8000
```

Verify: `curl http://localhost:8000/api/status` returns JSON.

- [ ] **Step 2: Start the frontend dev server**

In another terminal:
```bash
cd /Users/antonioschaffert/workspace/auto-trader/frontend
npm run dev
```

- [ ] **Step 3: Open http://localhost:5173 in browser**

Verify:
- Status bar shows bot running/stopped state, paper mode badge, prices
- Market overview cards show SPY/QQQ data from latest scan
- Rejection table shows scan rejection history with expandable details
- Settings gear icon opens slide-out panel with all config sections
- Saving a setting (e.g., changing daily loss limit) persists to MongoDB

- [ ] **Step 4: Commit final state**

```bash
git add -A
git commit -m "feat: complete React dashboard with monitoring and settings"
```

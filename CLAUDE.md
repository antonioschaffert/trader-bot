# Auto-Trader (Enhanced v2)

Automated options spread trading bot with a React dashboard. Paper trading on Alpaca.
Features: market regime detection, VIX-aware trading, portfolio Greeks, dynamic position sizing,
drawdown protection, correlation-aware risk, performance analytics.

## Setup

```bash
# Install Python deps
python3 -m pip install -r requirements.txt
python3 -m pip install -r api/requirements.txt

# Install frontend deps
cd frontend && npm install && cd ..

# Copy config/.env.example to config/.env and fill in API keys
```

## How to Run

Three processes needed (all from project root):

```bash
# 1. Bot (scans market, places trades)
python3 -m src.main

# 2. API (FastAPI, serves dashboard data)
python3 -m uvicorn api.main:app --port 8000

# 3. Frontend (React dashboard)
cd frontend && npm run dev
```

Dashboard at http://localhost:5173, API docs at http://localhost:8000/docs

## Architecture

```
src/                    - Python trading bot (APScheduler, Alpaca API, MongoDB)
  market_data/          - Price data, options chains, indicators, regime detection
    regime.py           - VIX-based volatility/trend/phase classification
    indicators.py       - RSI, SMA, ATR, ADX, support/resistance, Keltner, etc.
  signals/              - Strategy signal generators (regime-adaptive)
    swing.py            - Multi-timeframe trend + IV rank + support/resistance
    exhaustion.py       - Intraday mean-reversion with regime awareness
  risk/                 - Risk management subsystems
    manager.py          - Central risk validation + dynamic position sizing
    portfolio_greeks.py - Portfolio-level delta/gamma/theta/vega tracking
    drawdown.py         - Peak-to-trough drawdown + consecutive loss cooldown
    correlation.py      - SPY/QQQ correlation-aware position limits
  analytics/            - Performance metrics (Sharpe, win rate, expectancy)
  execution/            - Alpaca multi-leg order submission
  positions/            - Open position tracking and P&L
api/                    - FastAPI read/write layer over MongoDB
  routes/regime.py      - Market regime endpoint
  routes/analytics.py   - Performance analytics, portfolio Greeks, drawdown
frontend/               - React + Vite + shadcn/ui + Tailwind dashboard
  components/MarketRegime.tsx    - Regime display (vol, trend, phase, VIX)
  components/PerformancePanel.tsx - Analytics, Greeks, strategy breakdown
config/                 - config.yaml (defaults) and .env (secrets)
Dockerfile              - API service container (uvicorn on $PORT)
Dockerfile.bot          - Bot worker container (python3 -m src.main)
```

## Railway Deployment

Project: `auto-trader` on Railway (3 services under one project)

| Service | Type | URL |
|---------|------|-----|
| **api** | Dockerfile | https://api-production-7a8ab.up.railway.app |
| **frontend** | Node/Railpack | https://frontend-production-6312.up.railway.app |
| **bot** | Dockerfile.bot | (worker, no public URL) |

### How to deploy

```bash
# Deploy API (from project root)
railway up --service api

# Deploy frontend (from project root, uses frontend/ as root)
railway up --service frontend --path-as-root frontend

# Deploy bot (from project root)
railway up --service bot
```

### Service configuration

- **api**: Uses `Dockerfile` at project root. Env vars: `ALPACA_*`, `MONGODB_*`, `ALLOWED_ORIGINS`
- **bot**: Uses `Dockerfile.bot` via `RAILWAY_DOCKERFILE_PATH=Dockerfile.bot`. Env vars: `ALPACA_*`, `MONGODB_*`, `TWILIO_*`
- **frontend**: Railpack auto-detects Node from `frontend/package.json`. Build: `npm ci && npm run build`. Start: `npm run start` (serve). Env var: `VITE_API_URL` (set to api service URL, baked in at build time)

### Key env vars (Railway)

| Variable | Services | Purpose |
|----------|----------|---------|
| `VITE_API_URL` | frontend | API base URL, e.g. `https://api-production-7a8ab.up.railway.app` |
| `ALLOWED_ORIGINS` | api | Comma-separated CORS origins (frontend URL + localhost) |
| `RAILWAY_DOCKERFILE_PATH` | bot | Points to `Dockerfile.bot` |

### Notes

- `VITE_API_URL` is baked into the frontend at build time. If the API URL changes, redeploy frontend.
- `ALLOWED_ORIGINS` on the API must include the frontend Railway URL for CORS.
- Railway uses Railpack (not Nixpacks). Python services use Dockerfiles; Node services auto-detect from package.json.
- Bot runs as a worker (no port). API exposes `$PORT` via Railway injection.

## Config System

- `config/config.yaml` is the seed/defaults
- MongoDB `settings` collection is the source of truth (overrides YAML)
- Dashboard writes to MongoDB via `PUT /api/settings`
- Bot reloads config from MongoDB at the start of each scan cycle (no restart needed)

## Current Settings

Live settings are in MongoDB (source of truth). View/edit via dashboard or:

```bash
curl http://localhost:8000/api/settings | python3 -m json.tool
```

Currently configured with aggressive settings for paper testing (low thresholds, wide risk limits).

## Key Fixes Applied

1. **IEX data feed** - Alpaca free tier requires `DataFeed.IEX` (not SIP). Applied in `src/market_data/client.py`.
2. **BarSet API** - alpaca-py v0.43 returns `response.data.get(symbol)` not `response.get(symbol)`.
3. **TimeFrame construction** - Use `TimeFrame(n, TimeFrameUnit.Minute)` not `TimeFrame(n, "Min")`.
4. **Options chain pagination** - Alpaca caps at 100 results. Fetch calls and puts in separate requests to get full chain.
5. **Delta fallback** - Free tier doesn't provide Greeks. When delta=0, fall back to OTM strike selection by price distance (~4% OTM).
6. **IV rank threshold=0** - When threshold is 0, skip IV rank check entirely (even if iv_rank is None).
7. **ExhaustionConfig fields** - `min_move_from_open_pct` and `strong_move_pct` were added to config.yaml but missing from the dataclass.

## Market Regime System

The bot classifies the market across three dimensions every scan cycle:

| Dimension | Values | Impact |
|-----------|--------|--------|
| **Volatility** | low / normal / elevated / crisis | Position size, spread width, delta shift |
| **Trend** | strong_bull / bull / neutral / bear / strong_bear | Bias direction, signal filtering |
| **Phase** | trending / mean_reverting / transitioning | Strategy selection, signal threshold |

### Regime-Adaptive Behavior

| Regime | Position Size | Spread Width | Premium Threshold | Trading |
|--------|--------------|--------------|-------------------|---------|
| Low vol + Range-bound | 120% | 80% | 90% | Aggressive |
| Normal | 100% | 100% | 100% | Normal |
| Elevated + Range-bound | 84% | 130% | 130% | Selective |
| Crisis + Trending | 0% | N/A | N/A | **HALTED** |
| Crisis + Backwardation | 0% | N/A | N/A | **HALTED** |

### Drawdown Protection

- 3 consecutive losses: size reduced by 50%
- 5 consecutive losses: 60-minute cooldown (no trading)
- 5% drawdown: size reduced by 30%
- 10% drawdown: size reduced by 60%
- 15% drawdown: trading halted entirely
- Recovery: after 3 consecutive wins + drawdown < 5%, size gradually restored

### Dynamic Position Sizing

Quantity per trade = `base_qty * conviction * regime * drawdown * correlation`
- **base_qty**: from risk-per-trade % of equity
- **conviction**: 50-120% based on signal quality (IV rank, ADX, regime alignment)
- **regime**: 0-150% from volatility and trend regime
- **drawdown**: 0-100% from drawdown manager
- **correlation**: 30-100% penalty for correlated positions (SPY+QQQ)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Bot running state, last scan time, symbols |
| `/api/market` | GET | Latest price, RSI, IV rank, SMAs per symbol |
| `/api/rejections` | GET | Scan rejection history (filterable by symbol/strategy) |
| `/api/trades` | GET | Open positions, closed trades, daily P&L |
| `/api/iv-history` | GET | IV history for sparkline charts |
| `/api/settings` | GET/PUT | Read/write all bot settings |
| `/api/regime` | GET | Current market regime (vol, trend, phase, VIX) |
| `/api/regime/history` | GET | Historical regime snapshots |
| `/api/analytics` | GET | Performance metrics (win rate, Sharpe, expectancy) |
| `/api/portfolio-greeks` | GET | Portfolio-level delta/gamma/theta/vega |
| `/api/drawdown` | GET | Drawdown state, streak, cooldown status |

## MongoDB Collections

- `settings` - Single doc (`_id: "config"`) with all bot settings
- `scan_rejections` - Every scan logs why trades were NOT placed, with variables
- `trades` - Open and closed trade records
- `iv_history` - IV records per symbol over time
- `order_logs` - Order submission logs
- `options_snapshots` - Options chain snapshots
- `regime` - Latest market regime snapshot (single doc)
- `regime_history` - Historical regime snapshots
- `portfolio_greeks` - Latest portfolio Greeks (single doc)
- `drawdown` - Drawdown/streak state (single doc)
- `performance` - Cached performance analytics (single doc)

## Rejection Reasons (what to look for)

| Reason | Strategy | Meaning |
|--------|----------|---------|
| `iv_rank_unavailable` | swing | No IV history yet (builds over time) |
| `iv_rank_below_threshold` | swing | IV rank too low for premium selling |
| `no_short_strike_found` | both | No suitable OTM contracts found |
| `no_long_strike_found` | both | Can't find protective leg |
| `premium_too_low` | both | Net credit below minimum |
| `move_from_open_too_small` | exhaustion | Intraday move below threshold |
| `before_time_window` | exhaustion | Too early in the day |
| `upside/downside_score_below_threshold` | exhaustion | Not enough exhaustion signals |
| `risk_rejected: *` | both | Risk manager blocked (daily limit, max spreads, etc.) |

## Tech Stack

- Python 3.11, alpaca-py 0.43, APScheduler, pymongo, pandas, ta
- FastAPI, uvicorn
- React 18, TypeScript, Vite, shadcn/ui, Tailwind CSS
- MongoDB Atlas

## Environment

Secrets in `config/.env` (not committed):
- `ALPACA_API_KEY`, `ALPACA_API_SECRET`, `ALPACA_PAPER=true`
- `MONGODB_URI`, `MONGODB_DB_NAME`
- `TWILIO_*` (SMS notifications)

## Testing

```bash
python3 -m pytest tests/ -v
```

To check latest scan rejections (why trades aren't being placed):

```bash
curl "http://localhost:8000/api/rejections?limit=4" | python3 -m json.tool
```

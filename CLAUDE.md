# Auto-Trader

Automated options spread trading bot with a React dashboard. Paper trading on Alpaca.

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
src/           - Python trading bot (APScheduler, Alpaca API, MongoDB)
api/           - FastAPI read/write layer over MongoDB
frontend/      - React + Vite + shadcn/ui + Tailwind dashboard
config/        - config.yaml (defaults) and .env (secrets)
Dockerfile     - API service container (uvicorn on $PORT)
Dockerfile.bot - Bot worker container (python3 -m src.main)
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

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Bot running state, last scan time, symbols |
| `/api/market` | GET | Latest price, RSI, IV rank, SMAs per symbol |
| `/api/rejections` | GET | Scan rejection history (filterable by symbol/strategy) |
| `/api/trades` | GET | Open positions, closed trades, daily P&L |
| `/api/iv-history` | GET | IV history for sparkline charts |
| `/api/settings` | GET/PUT | Read/write all bot settings |

## MongoDB Collections

- `settings` - Single doc (`_id: "config"`) with all bot settings
- `scan_rejections` - Every scan logs why trades were NOT placed, with variables
- `trades` - Open and closed trade records
- `iv_history` - IV records per symbol over time
- `order_logs` - Order submission logs
- `options_snapshots` - Options chain snapshots

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

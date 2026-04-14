# React Dashboard Design

## Overview

Monitoring and configuration dashboard for the auto-trader bot. Displays live market data, scan rejection history, and trade activity. Allows editing all bot settings. Polls the API every 60 seconds.

## Architecture

```
React (Vite + shadcn/ui)  -->  FastAPI  -->  MongoDB
     :5173                      :8000        (existing)
```

- **Frontend**: `frontend/` — Vite + React + TypeScript + shadcn/ui + Tailwind CSS
- **API**: `api/` — FastAPI, reads from and writes settings to MongoDB
- **Config precedence**: MongoDB overrides `config.yaml`. On first run, `config.yaml` seeds the `settings` collection. All subsequent changes go through the dashboard and are persisted to MongoDB. The bot reads settings from MongoDB at the start of each scan cycle.
- **Polling interval**: 60 seconds

## Frontend Structure

```
frontend/
  src/
    components/
      StatusBar.tsx        # Bot status, mode badge, last scan, prices
      MarketOverview.tsx   # Per-symbol cards (price, RSI, IV rank, SMA50, bias)
      RejectionTable.tsx   # Scan rejection log with expandable details
      TradeHistory.tsx     # Open positions + closed trades
      SettingsPanel.tsx    # Editable settings form (all config sections)
    hooks/
      usePolling.ts        # Generic polling hook (60s interval)
    lib/
      api.ts               # API client functions
    App.tsx                # Single-page layout composing all sections
    main.tsx
```

### Dashboard Layout (single page, 4 sections)

1. **Status Bar** (top strip)
   - Bot uptime indicator (green/red dot)
   - Paper/Live mode badge
   - Last scan timestamp
   - SPY and QQQ current prices

2. **Market Overview** (card grid, 1 card per symbol)
   - Current price
   - RSI (with overbought/oversold color coding)
   - IV rank (with threshold indicator)
   - SMA 50 and SMA 20
   - Inferred bias (bullish/bearish/neutral)
   - Move from open %

3. **Scan Rejections** (data table)
   - Columns: timestamp, symbol, strategy, reason
   - Expandable rows showing full rejection variables
   - Filterable by symbol and strategy
   - Most recent first, paginated (default 50 rows)

4. **Trade History** (data table)
   - Open positions: symbol, spread type, entry premium, current value, unrealized P&L, expiration
   - Closed trades: symbol, spread type, entry/exit premium, realized P&L, close reason
   - Daily P&L summary at top

5. **Settings Panel** (collapsible sidebar or modal, accessed via gear icon in status bar)
   - Grouped into sections matching config structure:
     - **General**: symbols list, scan interval, market hours only
     - **Swing Strategy**: target DTE, delta range, spread width per symbol, min premium, IV rank threshold, profit target %
     - **Exhaustion Strategy**: enabled toggle, target DTE, spread width, min premium, profit target %, stop loss multiplier, time window, RSI thresholds, min move %, strong move %, min signals required, close by EOD
     - **Risk Management**: max concurrent spreads, max risk per trade %, max buying power %, stop loss multiplier, roll delta threshold, DTE exit, daily loss limit, daily income target, max same direction per symbol, max portfolio delta per symbol
     - **Execution**: price adjustment interval, price adjustment step, fill timeout
     - **Notifications**: SMS/email enabled toggles, event lists
   - Each section collapsible, with a Save button per section
   - Shows "saved" confirmation with timestamp of last update
   - Changes take effect on the bot's next scan cycle (no restart)

### UI Components (shadcn/ui)

- `Card` — market overview cards
- `Table` — rejection and trade tables
- `Badge` — status indicators (paper/live, strategy type, bias)
- `Collapsible` — expandable rejection variable details, settings sections
- `Select` — symbol/strategy filters
- `Input` / `Switch` / `Slider` — settings form controls
- `Sheet` — settings panel (slide-out sidebar)
- `Skeleton` — loading states
- `Tabs` — settings section navigation

## API Layer

```
api/
  main.py          # FastAPI app, CORS config, lifespan
  routes/
    status.py      # GET /api/status
    market.py      # GET /api/market
    rejections.py  # GET /api/rejections
    trades.py      # GET /api/trades
    iv_history.py  # GET /api/iv-history
    settings.py    # GET/PUT /api/settings
  db.py            # MongoDB connection (reuses existing URI/db)
```

### Endpoints

#### `GET /api/status`
Returns bot operational status.
```json
{
  "running": true,
  "paper_mode": true,
  "last_scan_time": "2026-04-01T15:32:07Z",
  "symbols": ["SPY", "QQQ"]
}
```
Source: Derived from latest `scan_rejections` timestamp.

#### `GET /api/market`
Returns latest market snapshot per symbol.
```json
[
  {
    "symbol": "SPY",
    "price": 656.66,
    "iv_rank": null,
    "rsi": 48.61,
    "sma_50": 687.91,
    "sma_20": 687.37,
    "timestamp": "2026-04-01T15:32:07Z"
  }
]
```
Source: Latest `scan_rejections` document per symbol (uses `market_snapshot` field).

#### `GET /api/rejections?limit=50&symbol=&strategy=`
Returns scan rejection history.
```json
{
  "items": [
    {
      "symbol": "SPY",
      "timestamp": "2026-04-01T15:32:07Z",
      "market_snapshot": { "price": 656.66, "rsi": 48.61, "..." : "..." },
      "rejections": [
        {
          "strategy": "swing",
          "reason": "iv_rank_unavailable",
          "variables": { "iv_rank": null }
        }
      ]
    }
  ],
  "total": 142
}
```
Source: `scan_rejections` collection.

#### `GET /api/trades`
Returns open and closed trades.
```json
{
  "open": [],
  "closed": [],
  "daily_pnl": 0.0
}
```
Source: `trades` collection.

#### `GET /api/iv-history?symbol=SPY&days=30`
Returns IV history for sparkline display.
```json
[
  { "timestamp": "2026-04-01T15:32:07Z", "iv": 0.18 }
]
```
Source: `iv_history` collection.

#### `GET /api/settings`
Returns current settings (from MongoDB `settings` collection, single document).
```json
{
  "symbols": ["SPY", "QQQ"],
  "swing": {
    "target_dte": [7, 10],
    "short_strike_delta": [0.15, 0.30],
    "spread_width": { "SPY": 5, "QQQ": 3 },
    "min_premium": 0.50,
    "iv_rank_threshold": 30,
    "profit_target_pct": 50
  },
  "exhaustion": { "..." : "..." },
  "risk": { "..." : "..." },
  "execution": { "..." : "..." },
  "schedule": { "..." : "..." },
  "notifications": { "..." : "..." },
  "updated_at": "2026-04-01T15:32:07Z"
}
```
Source: `settings` collection (single document, upserted).

#### `PUT /api/settings`
Updates settings. Accepts a partial or full settings object. Merges into existing settings document.
```json
{
  "risk": {
    "daily_loss_limit": 500
  }
}
```
Response: full updated settings object. Sets `updated_at` to current time.

## Config Loading (bot changes)

The bot's `load_config()` function is modified to:
1. Load `config.yaml` as defaults
2. Check MongoDB `settings` collection for overrides
3. If `settings` document exists, deep-merge it over the YAML defaults
4. If `settings` document does not exist, seed it from `config.yaml` values

The bot re-reads settings from MongoDB at the start of each `_scan_loop` cycle, so dashboard changes take effect within one scan interval (2 minutes) without restart.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend framework | React 18 + TypeScript |
| Build tool | Vite |
| UI components | shadcn/ui |
| Styling | Tailwind CSS |
| API framework | FastAPI |
| Database | MongoDB (existing instance) |
| HTTP client | fetch (built-in) |

## Dependencies

### Frontend
- react, react-dom
- vite, @vitejs/plugin-react
- typescript
- tailwindcss, @tailwindcss/vite
- shadcn/ui components (card, table, badge, collapsible, select, skeleton)

### API
- fastapi
- uvicorn
- pymongo (already installed)
- python-dotenv (already installed)

## Non-Goals

- Authentication (local/trusted network only)
- Real-time WebSocket streaming
- Mobile-responsive design (desktop-first)
- Charts or complex visualizations (text/tables for now)

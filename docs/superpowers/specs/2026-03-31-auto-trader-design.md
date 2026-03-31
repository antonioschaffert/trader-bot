# Auto-Trader: SPY/QQQ Spread-Selling Bot — Design Spec

## Overview

A fully automated Python trading bot that sells option spreads (credit put spreads, credit call spreads, and iron condors) on SPY and QQQ via the Alpaca Trading API. The bot uses a combination of volatility, technical indicators, and rules-based logic to decide what and when to sell. It manages open positions through profit targets, stop-losses, and rolling.

**Goals:**
- Collect premium by selling spreads on SPY and QQQ
- Daily income target: $500 (configurable)
- Account size: $10k-$100k, starting moderate risk
- Fully automated: scan, decide, execute, manage, close/roll — no manual intervention required

**Tech stack:**
- Python
- Alpaca Trading API + Market Data API
- MongoDB (data storage)
- Twilio (SMS alerts)
- Email (daily/weekly summaries)

## Architecture

Event-driven modular architecture. A single Python application with internal modules communicating through a lightweight in-process pub/sub event bus.

### Modules

1. **Scheduler** — orchestrates the main loop, triggers scans during market hours
2. **Market Data Module** — fetches prices, options chains, IV, technicals from Alpaca
3. **Signal Generator** — analyzes market data and emits trade signals
4. **Risk Manager** — validates signals against portfolio limits, manages open positions
5. **Order Executor** — submits and monitors orders via Alpaca Trading API
6. **Position Manager** — tracks open positions, P&L, lifecycle
7. **Notifications** — SMS (Twilio) and email alerts

### Data Flow

```
Scheduler (triggers scan)
    → Market Data (fetches prices, chains, IV, indicators)
    → Signal Generator (analyzes data, emits TradeSignal)
    → Risk Manager (validates against limits, sizing)
    → Order Executor (submits spread order to Alpaca)
    → Position Manager (tracks position, monitors P&L)
    → Risk Manager (triggers close/roll when thresholds hit)
    → Order Executor (submits close/roll order)
    → Notifications (alerts via SMS/email)
```

### Event Bus

Lightweight in-process pub/sub. Not an external message queue. Modules publish and subscribe to events:

- `MarketDataUpdated` — new data available for a symbol
- `SignalGenerated` — trade signal emitted by Signal Generator
- `SignalValidated` — signal approved by Risk Manager
- `SignalRejected` — signal blocked by Risk Manager (with reason)
- `OrderSubmitted` — order sent to Alpaca
- `OrderFilled` — order filled
- `OrderRejected` — order rejected by Alpaca
- `PositionUpdated` — position P&L or greeks changed
- `ProfitTargetHit` — position reached profit target
- `StopLossHit` — position exceeded loss threshold
- `RollTriggered` — short strike delta exceeded roll threshold
- `DTEExit` — position approaching expiration
- `DailyTargetMet` — daily income target reached
- `CircuitBreakerTriggered` — daily loss limit exceeded

## Market Data Module

**Data sources (all via Alpaca APIs):**

- Options chains — strikes, expirations, bid/ask, open interest, volume for QQQ and SPY
- Underlying price — current price, daily OHLCV bars
- Implied volatility — per-strike IV from options chain, used to calculate IV rank/percentile
- Historical bars — for computing technical indicators

**Responsibilities:**

- Fetch and cache options chains (refreshed on each scan cycle)
- Compute IV rank/percentile by tracking historical IV over a rolling window (52 weeks)
- Compute technical indicators using `pandas` + `ta` library (RSI, moving averages, bollinger bands)
- Normalize data into clean internal models
- Handle API rate limits and errors with retry/backoff

**Data storage (MongoDB):**

- IV history — for IV rank/percentile calculations, persists across restarts
- Options chain snapshots — for backtesting and analysis

**Configuration:**

- `scan_interval_minutes`: how often to fetch data (default: 5)
- `symbols`: list of symbols to scan (default: `["SPY", "QQQ"]`)
- `iv_lookback_weeks`: historical window for IV rank (default: 52)
- Technical indicator parameters (MA periods, RSI period, etc.)

## Signal Generator

Takes market data and outputs trade signals. This is the decision engine.

### Decision Logic (layered)

**1. Volatility filter:**
- Check IV rank/percentile for the symbol
- Only sell premium when IV rank > configurable threshold (default: 30th percentile)
- Higher IV = fatter premiums = better risk/reward

**2. Directional bias (technical indicators):**
- Bullish (price above 50 MA, RSI not overbought) → sell **put spreads**
- Bearish (price below 50 MA, RSI not oversold) → sell **call spreads**
- Neutral / high IV on both sides → sell **iron condors**

**3. Strike selection:**
- Short strike delta: 0.15-0.30 (configurable range)
- Spread width: $5 on SPY, $3 on QQQ (configurable per symbol)
- Target DTE: 7-10 days (configurable range)

**4. Entry rules:**
- Minimum premium: $0.50 per spread (configurable)
- Sufficient open interest and volume on selected strikes
- Not already at max positions for that symbol/direction

### Output

`TradeSignal` event containing:
- Symbol (SPY or QQQ)
- Spread type (put spread, call spread, iron condor)
- Strikes (short strike, long strike, expiration)
- Target premium
- Reasoning (which signals triggered the trade)

All thresholds and parameters are configurable via YAML — no code changes needed to tune.

## Risk Manager

Every trade signal passes through the Risk Manager before execution. Also monitors open positions.

### Pre-Trade Checks

- **Max concurrent spreads**: limit total open spreads (default: 10)
- **Max risk per trade**: cap max loss on any single spread (default: 5% of account)
- **Max daily risk**: stop opening new trades if unrealized losses exceed threshold (default: -$1,000)
- **Correlation guard**: limit same-direction spreads on same symbol (default: max 3 put spreads on SPY)
- **Buying power check**: ensure sufficient margin before submitting
- **Daily target check**: throttle new entries when daily income target ($500) is met

### Post-Trade Management

- **Profit target**: close spread when it captures X% of max profit (default: 50%)
- **Stop-loss**: close if loss exceeds a multiple of premium received (default: 2x premium)
- **Roll trigger**: if short strike delta > threshold (default: 0.50), roll to a later expiration
- **DTE exit**: close any spread within N days of expiration (default: 1 DTE) to avoid assignment

### Account-Level Limits

- **Max portfolio delta**: keep overall directional exposure bounded (default: max 0.30 net delta per symbol)
- **Max buying power usage**: never deploy more than X% of account (default: 60%)
- **Daily loss circuit breaker**: stop all trading if daily losses exceed hard limit

## Order Executor

Handles all communication with Alpaca's Trading API.

### Responsibilities

- Submit multi-leg spread orders (credit spreads, iron condors) as single orders
- Use limit orders targeting mid-price
- Price adjustment: step down by $0.01 every 30 seconds if not filled (configurable)
- Monitor order status, emit fill/rejection events
- Execute closing and rolling orders when triggered by Risk Manager
- Retry logic for transient API failures, rate limits, timeouts

### Order Flow

1. Receive validated signal from Risk Manager
2. Build multi-leg order with target limit price
3. Submit to Alpaca
4. Monitor for fill (configurable timeout, default: 300 seconds)
5. If not filled within timeout, adjust price or cancel
6. Emit events for Position Manager

### Safety

- All orders are limit orders — never market orders on spreads
- Validate order parameters before submission
- Log every order attempt and result to MongoDB

## Position Manager

Tracks all open positions and coordinates with Risk Manager.

### Responsibilities

- Track open spreads: entry price, current P&L, greeks, DTE remaining
- Sync with Alpaca positions API periodically to catch discrepancies
- Real-time unrealized P&L per position and daily/cumulative totals
- Emit management events when positions hit thresholds
- Record complete trade log to MongoDB

### Position Lifecycle

```
Opened → Monitoring → [Profit Target | Stop-Loss | Roll | DTE Exit] → Closed/Rolled
```

### Dashboard Data (logged/available for querying)

- Current open positions with live P&L
- Daily P&L vs. $500 target
- Win rate, average premium collected, average hold time
- Rolling 30-day performance

## Notifications

### SMS (Twilio)

Immediate alerts for:
- Spread filled or closed
- Stop-loss triggered
- Roll executed
- Daily loss circuit breaker hit
- Bot errors or connectivity issues

### Email (SendGrid or SMTP)

Summaries:
- Daily performance summary (P&L, open positions, win rate, progress toward $500 target)
- Weekly recap
- Trade log digest

Both channels are configurable — toggle which events trigger which channel.

## Configuration

All tunable parameters in a single YAML config file:

```yaml
# symbols
symbols: ["SPY", "QQQ"]

# strategy
target_dte: [7, 10]
short_strike_delta: [0.15, 0.30]
spread_width:
  SPY: 5
  QQQ: 3
min_premium: 0.50
iv_rank_threshold: 30

# risk
max_concurrent_spreads: 10
max_risk_per_trade_pct: 5
max_buying_power_usage_pct: 60
profit_target_pct: 50
stop_loss_multiplier: 2.0
roll_delta_threshold: 0.50
dte_exit: 1
daily_loss_limit: 1000
daily_income_target: 500

# execution
price_adjustment_interval: 30    # seconds
price_adjustment_step: 0.01
fill_timeout: 300                # seconds

# schedule
scan_interval_minutes: 5
market_hours_only: true

# notifications
sms_enabled: true
email_enabled: true
sms_events: ["fill", "stop_loss", "roll", "circuit_breaker", "error"]
email_events: ["daily_summary", "weekly_recap"]
```

Secrets in `.env`:
- `ALPACA_API_KEY`
- `ALPACA_API_SECRET`
- `ALPACA_BASE_URL` (paper vs live)
- `MONGODB_URI`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER`
- `TWILIO_TO_NUMBER`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_USERNAME`
- `EMAIL_PASSWORD`
- `EMAIL_TO`

## Project Structure

```
auto-trader/
├── config/
│   ├── config.yaml          # all tunable parameters
│   └── .env                 # secrets (API keys, Twilio, email, MongoDB)
├── src/
│   ├── main.py              # entry point, initializes and starts scheduler
│   ├── event_bus.py         # lightweight pub/sub for module communication
│   ├── scheduler.py         # orchestrates scan loop during market hours
│   ├── market_data/
│   │   ├── client.py        # Alpaca market data API wrapper
│   │   ├── indicators.py    # technical indicator calculations
│   │   └── models.py        # data models (OptionsChain, Bar, etc.)
│   ├── signals/
│   │   ├── generator.py     # signal generation logic
│   │   └── models.py        # TradeSignal model
│   ├── risk/
│   │   ├── manager.py       # pre-trade checks + post-trade rules
│   │   └── models.py        # risk parameters, limits
│   ├── execution/
│   │   ├── executor.py      # Alpaca order submission + fill monitoring
│   │   └── models.py        # Order, Fill models
│   ├── positions/
│   │   ├── manager.py       # position tracking, P&L, lifecycle
│   │   └── models.py        # Position, Spread models
│   ├── notifications/
│   │   ├── sms.py           # Twilio integration
│   │   └── email.py         # email summaries
│   └── db/
│       └── mongo.py         # MongoDB connection + data access
├── tests/                   # unit + integration tests
├── docs/
├── requirements.txt
└── README.md
```

## Key Dependencies

- `alpaca-py` — Alpaca SDK for trading and market data
- `pandas` — data manipulation
- `ta` — technical analysis indicators
- `pymongo` — MongoDB driver
- `twilio` — SMS notifications
- `pyyaml` — config parsing
- `python-dotenv` — environment variable loading
- `schedule` or `apscheduler` — task scheduling
- `pytest` — testing

## Development & Deployment

**Local (development):**
- Run with paper trading API (`ALPACA_BASE_URL` set to paper endpoint)
- Local MongoDB instance
- `python src/main.py`

**Cloud (production):**
- Deploy to AWS/GCP/Azure
- MongoDB Atlas for database
- Live Alpaca API keys
- Process manager (systemd, supervisor, or container)
- Logging to file + cloud logging service

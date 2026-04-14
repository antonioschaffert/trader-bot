# Railway Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy all three auto-trader services (bot worker, FastAPI API, React frontend) to Railway under one project using the Railway CLI.

**Architecture:** Three Railway services share one repo — bot (worker, no port), api (HTTP, port=$PORT), frontend (static build served via `serve`). API URL is baked into the frontend at build time via `VITE_API_URL`. CORS origins on the API are controlled by `ALLOWED_ORIGINS` env var.

**Tech Stack:** Railway CLI, Python/Nixpacks, Node/Vite/Nixpacks, `serve` npm package

---

## Files

| File | Action | Purpose |
|------|--------|---------|
| `api/main.py` | Modify | CORS origins from env var instead of hardcoded localhost |
| `frontend/src/lib/api.ts` | Modify | Use `VITE_API_URL` env var as base URL |
| `frontend/package.json` | Modify | Add `serve` dependency + `start` script for Railway |

No new files needed — Railway reads start/build commands from service config, not config files.

---

### Task 1: Install Railway CLI

- [ ] **Step 1: Install via Homebrew**

```bash
brew install railway
```

Expected output: `railway` installed to `/opt/homebrew/bin/railway`

- [ ] **Step 2: Verify**

```bash
railway --version
```

Expected: prints version like `railway 3.x.x`

---

### Task 2: Update API CORS to use env var

**Files:**
- Modify: `api/main.py`

- [ ] **Step 1: Read current CORS config**

Open `api/main.py`. The current `allow_origins` is hardcoded to `["http://localhost:5173"]`.

- [ ] **Step 2: Update CORS to read from env var**

Replace the `CORSMiddleware` block in `api/main.py`:

```python
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import status, market, rejections, trades, iv_history, settings

app = FastAPI(title="Auto-Trader Dashboard API")

_raw = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173")
origins = [o.strip() for o in _raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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

- [ ] **Step 3: Commit**

```bash
git add api/main.py
git commit -m "feat: read CORS allowed origins from ALLOWED_ORIGINS env var"
```

---

### Task 3: Update frontend API client to support production URL

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Update BASE to use VITE_API_URL**

Change line 61 in `frontend/src/lib/api.ts` from:

```typescript
const BASE = "/api";
```

to:

```typescript
const BASE = `${import.meta.env.VITE_API_URL ?? ""}/api`;
```

This means:
- **Dev** (no `VITE_API_URL`): `BASE = "/api"` → hits Vite proxy → `localhost:8000/api` ✓
- **Prod** (`VITE_API_URL=https://api-xxx.up.railway.app`): `BASE = "https://api-xxx.up.railway.app/api"` ✓

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: use VITE_API_URL env var as API base URL for production"
```

---

### Task 4: Add static file server to frontend for Railway

**Files:**
- Modify: `frontend/package.json`

Railway needs a running process (not just static files). Add the `serve` package so Railway can serve the Vite build.

- [ ] **Step 1: Add serve and start script**

In `frontend/package.json`, add to `scripts`:

```json
"start": "serve -s dist -l $PORT"
```

And add to `devDependencies`:

```json
"serve": "^14.2.4"
```

The full updated `scripts` block:

```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "lint": "eslint .",
  "preview": "vite preview",
  "start": "serve -s dist -l $PORT"
}
```

- [ ] **Step 2: Install serve locally to update package-lock**

```bash
cd frontend && npm install serve --save-dev && cd ..
```

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "feat: add serve package and start script for Railway static hosting"
```

---

### Task 5: Login and create Railway project

- [ ] **Step 1: Login**

```bash
railway login
```

This opens a browser window. Authenticate with GitHub or email.

- [ ] **Step 2: Initialize project in repo root**

```bash
railway init
```

When prompted:
- Select **Create new project**
- Name it: `auto-trader`

This creates a `.railway` link file (gitignored by Railway, no commit needed).

---

### Task 6: Create and deploy the API service

Deploy API first so we can get its URL for the frontend's `VITE_API_URL`.

- [ ] **Step 1: Create the API service**

```bash
railway service create --name api
```

- [ ] **Step 2: Set API service build/start commands**

```bash
railway service update api \
  --build-command "pip install -r requirements.txt -r api/requirements.txt" \
  --start-command "uvicorn api.main:app --host 0.0.0.0 --port \$PORT"
```

> Note: `$PORT` is escaped so the shell doesn't expand it — Railway injects it at runtime.

- [ ] **Step 3: Set API environment variables**

Replace `<value>` with values from your `config/.env`:

```bash
railway variables set --service api \
  ALPACA_API_KEY=<value> \
  ALPACA_API_SECRET=<value> \
  ALPACA_PAPER=true \
  MONGODB_URI=<value> \
  MONGODB_DB_NAME=<value>
```

- [ ] **Step 4: Deploy the API**

```bash
railway up --service api
```

Watch the build logs. When complete, get the public URL:

```bash
railway domain --service api
```

Note this URL (e.g. `https://api-xxxx.up.railway.app`) — you'll need it for the next task.

---

### Task 7: Create and deploy the frontend service

- [ ] **Step 1: Create the frontend service**

```bash
railway service create --name frontend
```

- [ ] **Step 2: Set frontend service config**

Replace `https://api-xxxx.up.railway.app` with the URL from Task 6 Step 4:

```bash
railway service update frontend \
  --root-directory frontend \
  --build-command "npm install && npm run build" \
  --start-command "npm run start"
```

- [ ] **Step 3: Set VITE_API_URL**

```bash
railway variables set --service frontend \
  VITE_API_URL=https://api-xxxx.up.railway.app
```

- [ ] **Step 4: Set API's ALLOWED_ORIGINS**

First get the frontend's Railway domain (may not exist yet — run `railway up` then come back):

```bash
railway domain --service frontend
```

Then set CORS on the API to allow the frontend:

```bash
railway variables set --service api \
  ALLOWED_ORIGINS=http://localhost:5173,https://frontend-xxxx.up.railway.app
```

- [ ] **Step 5: Deploy the frontend**

```bash
railway up --service frontend
```

---

### Task 8: Create and deploy the bot worker

- [ ] **Step 1: Create the bot service**

```bash
railway service create --name bot
```

- [ ] **Step 2: Set bot start command (no port needed)**

```bash
railway service update bot \
  --build-command "pip install -r requirements.txt" \
  --start-command "python3 -m src.main"
```

- [ ] **Step 3: Set bot environment variables**

```bash
railway variables set --service bot \
  ALPACA_API_KEY=<value> \
  ALPACA_API_SECRET=<value> \
  ALPACA_PAPER=true \
  MONGODB_URI=<value> \
  MONGODB_DB_NAME=<value> \
  TWILIO_ACCOUNT_SID=<value> \
  TWILIO_AUTH_TOKEN=<value> \
  TWILIO_FROM_NUMBER=<value> \
  TWILIO_TO_NUMBER=<value>
```

- [ ] **Step 4: Deploy the bot**

```bash
railway up --service bot
```

- [ ] **Step 5: Verify bot is running**

```bash
railway logs --service bot
```

Expected: scheduler startup logs, scan cycle logs. No `ModuleNotFoundError`.

---

### Task 9: Smoke test the deployment

- [ ] **Step 1: Hit the API health endpoint**

```bash
curl https://api-xxxx.up.railway.app/api/status
```

Expected: JSON with `running`, `paper_mode`, `symbols` fields.

- [ ] **Step 2: Open the frontend**

Visit the frontend Railway URL in a browser. Dashboard should load, charts should populate.

- [ ] **Step 3: Verify CORS is not blocking**

Open browser DevTools → Network tab. Confirm no `CORS` errors on `/api/*` requests.

- [ ] **Step 4: Redeploy frontend if VITE_API_URL needs update**

If the API URL changed, update it and redeploy:

```bash
railway variables set --service frontend VITE_API_URL=https://new-api-url.up.railway.app
railway up --service frontend
```

---

## Deployment Order Summary

```
1. brew install railway
2. Make code changes (Tasks 2–4) → commit
3. railway login && railway init
4. Deploy API → note URL
5. Deploy frontend (with VITE_API_URL set) → note URL
6. Update API ALLOWED_ORIGINS with frontend URL → redeploy API
7. Deploy bot worker
8. Smoke test
```

## Environment Variables Reference

| Service | Variable | Source |
|---------|----------|--------|
| api, bot | `ALPACA_API_KEY` | `config/.env` |
| api, bot | `ALPACA_API_SECRET` | `config/.env` |
| api, bot | `ALPACA_PAPER` | `true` |
| api, bot | `MONGODB_URI` | `config/.env` |
| api, bot | `MONGODB_DB_NAME` | `config/.env` |
| bot | `TWILIO_*` | `config/.env` |
| api | `ALLOWED_ORIGINS` | frontend Railway URL + localhost |
| frontend | `VITE_API_URL` | api Railway URL (no trailing slash) |

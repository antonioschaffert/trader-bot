import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query
from api.db import get_db

router = APIRouter()

@router.get("/status")
def get_status(account_id: str = Query("", description="Filter by account")):
    db = get_db()

    # Find last scan (optionally filtered by account)
    scan_query = {}
    if account_id:
        scan_query["account_id"] = account_id
    last_scan = db["scan_rejections"].find_one(scan_query, sort=[("timestamp", -1)])

    last_scan_time = None
    scanning = False
    if last_scan and "timestamp" in last_scan:
        ts = last_scan["timestamp"]
        last_scan_time = ts.isoformat() if ts else None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - ts
        scanning = age < timedelta(minutes=5)

    # Bot process heartbeat (account-aware)
    if account_id:
        heartbeat = db["heartbeat"].find_one({"_id": f"bot_{account_id}"})
    else:
        # Fallback: try legacy key, then any heartbeat
        heartbeat = db["heartbeat"].find_one({"_id": "bot"})
        if not heartbeat:
            heartbeat = db["heartbeat"].find_one(sort=[("timestamp", -1)])

    bot_alive = False
    market_hours = False
    regime = None
    drawdown = None
    if heartbeat and "timestamp" in heartbeat:
        hb_ts = heartbeat["timestamp"]
        if hb_ts.tzinfo is None:
            hb_ts = hb_ts.replace(tzinfo=timezone.utc)
        bot_alive = (datetime.now(timezone.utc) - hb_ts) < timedelta(minutes=2)
        market_hours = heartbeat.get("market_hours", False)
        regime = heartbeat.get("regime")
        drawdown = heartbeat.get("drawdown")

    paper_mode = os.getenv("ALPACA_PAPER", "true").lower() == "true"
    settings_doc = db["settings"].find_one({"_id": "config"})
    symbols = settings_doc.get("symbols", []) if settings_doc else []

    # Per-account status summary
    accounts_status = []
    all_accounts = list(db["accounts"].find())
    for acct in all_accounts:
        aid = acct["account_id"]
        hb = db["heartbeat"].find_one({"_id": f"bot_{aid}"})
        running = False
        if hb and "timestamp" in hb:
            hb_ts = hb["timestamp"]
            if hb_ts.tzinfo is None:
                hb_ts = hb_ts.replace(tzinfo=timezone.utc)
            running = (datetime.now(timezone.utc) - hb_ts) < timedelta(minutes=2)
        accounts_status.append({
            "account_id": aid,
            "name": acct.get("name", aid),
            "is_paper": acct.get("is_paper", True),
            "enabled": acct.get("enabled", False),
            "running": running,
            "strategies": acct.get("strategies", {}),
        })

    return {
        "running": bot_alive,
        "scanning": scanning,
        "market_hours": market_hours,
        "paper_mode": paper_mode,
        "last_scan_time": last_scan_time,
        "symbols": symbols,
        "regime": regime,
        "drawdown": drawdown,
        "accounts": accounts_status,
    }

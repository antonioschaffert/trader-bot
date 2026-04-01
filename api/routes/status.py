import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter
from api.db import get_db

router = APIRouter()

@router.get("/status")
def get_status():
    db = get_db()
    last_scan = db["scan_rejections"].find_one(sort=[("timestamp", -1)])

    running = False
    last_scan_time = None
    if last_scan and "timestamp" in last_scan:
        ts = last_scan["timestamp"]
        last_scan_time = ts.isoformat() if ts else None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - ts
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

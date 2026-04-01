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
    return [{"timestamp": r["timestamp"].isoformat(), "iv": r["iv"]} for r in cursor]

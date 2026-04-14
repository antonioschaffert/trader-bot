from datetime import datetime, time, timezone
from fastapi import APIRouter, Query
from api.db import get_db

router = APIRouter()

@router.get("/trades")
def get_trades(account_id: str = Query("", description="Filter by account")):
    db = get_db()
    today_start = datetime.combine(
        datetime.now(timezone.utc).date(), time.min
    ).replace(tzinfo=timezone.utc)

    query = {}
    if account_id:
        query["account_id"] = account_id

    all_trades = list(db["trades"].find(query).sort("opened_at", -1))
    open_trades = []
    closed_trades = []
    daily_pnl = 0.0

    for t in all_trades:
        t["_id"] = str(t["_id"])
        for key in ("opened_at", "closed_at"):
            if key in t and t[key]:
                t[key] = t[key].isoformat() if hasattr(t[key], "isoformat") else str(t[key])
        if "expiration" in t and t["expiration"]:
            t["expiration"] = str(t["expiration"])

        if t.get("closed_at"):
            closed_trades.append(t)
            closed_time = t.get("closed_at", "")
            if closed_time and closed_time >= today_start.isoformat():
                daily_pnl += t.get("realized_pnl", t.get("pnl", 0.0))
        else:
            open_trades.append(t)

    return {"open": open_trades, "closed": closed_trades, "daily_pnl": round(daily_pnl, 2)}


@router.get("/order-logs")
def get_order_logs(
    account_id: str = Query("", description="Filter by account"),
    limit: int = Query(100, ge=1, le=500),
):
    """Return chronological order activity (opens and closes)."""
    db = get_db()
    query = {}
    if account_id:
        query["account_id"] = account_id

    logs = list(db["order_logs"].find(query).sort("timestamp", -1).limit(limit))
    for log in logs:
        log["_id"] = str(log["_id"])
        if "timestamp" in log and hasattr(log["timestamp"], "isoformat"):
            log["timestamp"] = log["timestamp"].isoformat()
        # Normalize action field
        if "action" not in log:
            log["action"] = "open"

    return {"logs": logs}

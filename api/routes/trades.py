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

    return {"open": open_trades, "closed": closed_trades, "daily_pnl": round(daily_pnl, 2)}

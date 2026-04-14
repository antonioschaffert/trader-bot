from datetime import datetime, time, timezone

from fastapi import APIRouter, Query

from api.db import get_db

router = APIRouter()


@router.get("/wheel")
def get_wheel_status(account_id: str = Query("", description="Filter by account")):
    """Return current wheel state for all symbols."""
    db = get_db()
    query = {}
    if account_id:
        query["account_id"] = account_id
    states = list(db["wheel_state"].find(query))
    for s in states:
        s["_id"] = str(s["_id"])
        # Serialize datetime fields
        for key in ("started_at", "last_updated", "updated_at"):
            if key in s and s[key]:
                s[key] = s[key].isoformat() if hasattr(s[key], "isoformat") else str(s[key])
        if "current_option_expiration" in s and s["current_option_expiration"]:
            s["current_option_expiration"] = str(s["current_option_expiration"])
    return {"positions": states}


@router.get("/wheel/history")
def get_wheel_history(
    symbol: str = Query("", description="Filter by symbol"),
    account_id: str = Query("", description="Filter by account"),
    limit: int = Query(50, ge=1, le=200),
):
    """Return completed wheel trades (CSP/CC legs)."""
    db = get_db()
    query = {"strategy_mode": "wheel"}
    if account_id:
        query["account_id"] = account_id
    if symbol:
        query["symbol"] = symbol

    trades = list(
        db["trades"]
        .find(query)
        .sort("closed_at", -1)
        .limit(limit)
    )

    for t in trades:
        t["_id"] = str(t["_id"])
        for key in ("opened_at", "closed_at"):
            if key in t and t[key]:
                t[key] = t[key].isoformat() if hasattr(t[key], "isoformat") else str(t[key])

    # Summary stats
    total_pnl = sum(t.get("pnl", 0) for t in trades)
    total_premium = sum(t.get("entry_premium", 0) for t in trades)
    assignments = sum(1 for t in trades if t.get("reason") == "assigned")
    cycles = sum(1 for t in trades if t.get("reason") == "called_away")

    return {
        "trades": trades,
        "summary": {
            "total_trades": len(trades),
            "total_pnl": round(total_pnl, 2),
            "total_premium_collected": round(total_premium, 2),
            "assignments": assignments,
            "cycles_completed": cycles,
        },
    }

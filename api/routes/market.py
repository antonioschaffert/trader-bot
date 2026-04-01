from fastapi import APIRouter
from api.db import get_db

router = APIRouter()

@router.get("/market")
def get_market():
    db = get_db()
    pipeline = [
        {"$sort": {"timestamp": -1}},
        {"$group": {
            "_id": "$symbol",
            "symbol": {"$first": "$symbol"},
            "timestamp": {"$first": "$timestamp"},
            "market_snapshot": {"$first": "$market_snapshot"},
        }},
    ]
    results = list(db["scan_rejections"].aggregate(pipeline))
    return [
        {
            "symbol": r["symbol"],
            "timestamp": r["timestamp"].isoformat() if r.get("timestamp") else None,
            **(r.get("market_snapshot") or {}),
        }
        for r in results
    ]

from fastapi import APIRouter
from api.db import get_db

router = APIRouter()


@router.get("/regime")
def get_regime():
    """Get current market regime snapshot."""
    db = get_db()
    regime = db["regime"].find_one({"_id": "latest"})
    if regime:
        regime.pop("_id", None)
    return regime or {}


@router.get("/regime/history")
def get_regime_history(limit: int = 50):
    """Get historical regime snapshots for trend analysis."""
    db = get_db()
    cursor = db["regime_history"].find().sort("timestamp", -1).limit(limit)
    results = []
    for r in cursor:
        r["_id"] = str(r["_id"])
        results.append(r)
    return results

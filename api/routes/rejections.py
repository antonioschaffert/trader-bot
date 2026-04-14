from fastapi import APIRouter, Query
from api.db import get_db

router = APIRouter()

@router.get("/rejections")
def get_rejections(
    limit: int = Query(50, ge=1, le=500),
    symbol: str = Query(""),
    strategy: str = Query(""),
    account_id: str = Query(""),
):
    db = get_db()
    query = {}
    if account_id:
        query["account_id"] = account_id
    if symbol:
        query["symbol"] = symbol
    if strategy:
        query["rejections.strategy"] = strategy

    total = db["scan_rejections"].count_documents(query)
    cursor = db["scan_rejections"].find(query).sort("timestamp", -1).limit(limit)
    items = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if "timestamp" in doc:
            doc["timestamp"] = doc["timestamp"].isoformat()
        items.append(doc)

    return {"items": items, "total": total}

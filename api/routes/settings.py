from datetime import datetime, timezone
from fastapi import APIRouter, Request
from api.db import get_db

router = APIRouter()

@router.get("/settings")
def get_settings():
    db = get_db()
    doc = db["settings"].find_one({"_id": "config"})
    if not doc:
        return {}
    doc.pop("_id", None)
    if "updated_at" in doc:
        doc["updated_at"] = doc["updated_at"].isoformat()
    return doc

@router.put("/settings")
async def put_settings(request: Request):
    db = get_db()
    body = await request.json()
    body["updated_at"] = datetime.now(timezone.utc)
    db["settings"].update_one({"_id": "config"}, {"$set": body}, upsert=True)
    doc = db["settings"].find_one({"_id": "config"})
    doc.pop("_id", None)
    if "updated_at" in doc:
        doc["updated_at"] = doc["updated_at"].isoformat()
    return doc

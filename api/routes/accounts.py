from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from api.db import get_db

router = APIRouter()


def _mask_secret(secret: str) -> str:
    """Mask API secrets for display — show first 4 and last 2 chars."""
    if not secret or len(secret) < 8:
        return "***"
    return secret[:4] + "***" + secret[-2:]


def _serialize_account(acct: dict) -> dict:
    """Prepare account for API response — mask secrets, serialize dates."""
    acct["_id"] = str(acct["_id"]) if "_id" in acct else ""
    acct["api_key_masked"] = _mask_secret(acct.get("api_key", ""))
    acct["api_secret_masked"] = _mask_secret(acct.get("api_secret", ""))
    # Never return raw secrets
    acct.pop("api_key", None)
    acct.pop("api_secret", None)
    for key in ("created_at", "updated_at"):
        if key in acct and hasattr(acct[key], "isoformat"):
            acct[key] = acct[key].isoformat()
    return acct


@router.get("/accounts")
def list_accounts():
    """List all accounts (secrets masked)."""
    db = get_db()
    accounts = list(db["accounts"].find())
    return {"accounts": [_serialize_account(a) for a in accounts]}


@router.post("/accounts")
async def create_account(request: Request):
    """Create a new account."""
    body = await request.json()

    required = ["account_id", "name", "api_key", "api_secret"]
    for field in required:
        if not body.get(field):
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    db = get_db()
    existing = db["accounts"].find_one({"account_id": body["account_id"]})
    if existing:
        raise HTTPException(status_code=409, detail=f"Account '{body['account_id']}' already exists")

    account = {
        "account_id": body["account_id"],
        "name": body["name"],
        "api_key": body["api_key"],
        "api_secret": body["api_secret"],
        "is_paper": body.get("is_paper", True),
        "enabled": body.get("enabled", False),
        "strategies": body.get("strategies", {
            "swing": True,
            "exhaustion": True,
            "wheel": False,
        }),
        "symbols": body.get("symbols", ["SPY", "QQQ"]),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    db["accounts"].insert_one(account)
    account = db["accounts"].find_one({"account_id": body["account_id"]})
    return {"account": _serialize_account(account)}


@router.put("/accounts/{account_id}")
async def update_account(account_id: str, request: Request):
    """Update an account (name, strategies, enabled, symbols). Secrets optional."""
    db = get_db()
    existing = db["accounts"].find_one({"account_id": account_id})
    if not existing:
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' not found")

    body = await request.json()
    update = {"updated_at": datetime.now(timezone.utc)}

    # Allow updating these fields
    for field in ("name", "is_paper", "enabled", "strategies", "symbols"):
        if field in body:
            update[field] = body[field]

    # Only update secrets if explicitly provided (non-empty)
    if body.get("api_key"):
        update["api_key"] = body["api_key"]
    if body.get("api_secret"):
        update["api_secret"] = body["api_secret"]

    db["accounts"].update_one({"account_id": account_id}, {"$set": update})

    account = db["accounts"].find_one({"account_id": account_id})
    return {"account": _serialize_account(account)}


@router.delete("/accounts/{account_id}")
def delete_account(account_id: str):
    """Delete an account."""
    db = get_db()
    result = db["accounts"].delete_one({"account_id": account_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' not found")
    return {"deleted": True, "account_id": account_id}


@router.post("/accounts/{account_id}/toggle")
def toggle_account(account_id: str):
    """Toggle an account's enabled state."""
    db = get_db()
    account = db["accounts"].find_one({"account_id": account_id})
    if not account:
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' not found")

    new_state = not account.get("enabled", False)
    db["accounts"].update_one(
        {"account_id": account_id},
        {"$set": {"enabled": new_state, "updated_at": datetime.now(timezone.utc)}},
    )

    return {"account_id": account_id, "enabled": new_state}

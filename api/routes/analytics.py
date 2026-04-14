from fastapi import APIRouter, Query
from api.db import get_db

router = APIRouter()


@router.get("/analytics")
def get_analytics(account_id: str = Query("", description="Filter by account")):
    """Get cached performance analytics report."""
    db = get_db()
    query = {"_id": f"latest_{account_id}"} if account_id else {"_id": "latest"}
    report = db["performance"].find_one(query)
    if not report and account_id:
        report = db["performance"].find_one({"_id": "latest"})
    if report:
        report.pop("_id", None)
    return report or {}


@router.get("/portfolio-greeks")
def get_portfolio_greeks(account_id: str = Query("", description="Filter by account")):
    """Get current portfolio Greeks."""
    db = get_db()
    query = {"_id": f"latest_{account_id}"} if account_id else {"_id": "latest"}
    greeks = db["portfolio_greeks"].find_one(query)
    if not greeks and account_id:
        greeks = db["portfolio_greeks"].find_one({"_id": "latest"})
    if greeks:
        greeks.pop("_id", None)
    return greeks or {}


@router.get("/drawdown")
def get_drawdown(account_id: str = Query("", description="Filter by account")):
    """Get current drawdown state."""
    db = get_db()
    query = {"_id": f"state_{account_id}"} if account_id else {"_id": "state"}
    state = db["drawdown"].find_one(query)
    if not state and account_id:
        state = db["drawdown"].find_one({"_id": "state"})
    if state:
        state.pop("_id", None)
    return state or {}

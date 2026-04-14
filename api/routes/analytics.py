from fastapi import APIRouter
from api.db import get_db

router = APIRouter()


@router.get("/analytics")
def get_analytics():
    """Get cached performance analytics report."""
    db = get_db()
    report = db["performance"].find_one({"_id": "latest"})
    if report:
        report.pop("_id", None)
    return report or {}


@router.get("/portfolio-greeks")
def get_portfolio_greeks():
    """Get current portfolio Greeks."""
    db = get_db()
    greeks = db["portfolio_greeks"].find_one({"_id": "latest"})
    if greeks:
        greeks.pop("_id", None)
    return greeks or {}


@router.get("/drawdown")
def get_drawdown():
    """Get current drawdown state."""
    db = get_db()
    state = db["drawdown"].find_one({"_id": "state"})
    if state:
        state.pop("_id", None)
    return state or {}

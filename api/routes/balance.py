from fastapi import APIRouter, Query, HTTPException
from api.db import get_db
from alpaca.trading.client import TradingClient

router = APIRouter()


def _get_alpaca_client(db, account_id: str) -> TradingClient:
    """Get an Alpaca TradingClient for the given account."""
    if not account_id:
        # Use first enabled account
        acct = db["accounts"].find_one({"enabled": True})
    else:
        acct = db["accounts"].find_one({"account_id": account_id})

    if not acct or not acct.get("api_key"):
        raise HTTPException(status_code=404, detail="Account not found or missing credentials")

    return TradingClient(acct["api_key"], acct["api_secret"], paper=acct.get("is_paper", True))


@router.get("/balance")
def get_balance(account_id: str = Query("", description="Account to query")):
    db = get_db()
    try:
        client = _get_alpaca_client(db, account_id)
        acct = client.get_account()
        return {
            "equity": float(acct.equity),
            "cash": float(acct.cash),
            "buying_power": float(acct.buying_power),
            "portfolio_value": float(acct.portfolio_value),
            "day_trade_count": int(acct.daytrade_count),
            "currency": acct.currency,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Alpaca API error: {str(e)}")


@router.get("/positions")
def get_positions(account_id: str = Query("", description="Account to query")):
    db = get_db()
    try:
        client = _get_alpaca_client(db, account_id)
        positions = client.get_all_positions()
        return [
            {
                "symbol": p.symbol,
                "qty": int(p.qty),
                "side": str(p.side.value) if hasattr(p.side, 'value') else str(p.side),
                "market_value": float(p.market_value),
                "cost_basis": float(p.cost_basis),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc) * 100,
                "current_price": float(p.current_price),
                "avg_entry_price": float(p.avg_entry_price),
            }
            for p in positions
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Alpaca API error: {str(e)}")

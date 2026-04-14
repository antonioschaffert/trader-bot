import logging
from datetime import datetime, timezone

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest

from src.db.mongo import MongoStore
from src.event_bus import EventBus
from src.signals.models import SpreadLeg, TradeSignal, WheelSignal

logger = logging.getLogger(__name__)


class OrderExecutor:
    def __init__(self, trading_client: TradingClient, db: MongoStore, config: dict, event_bus: EventBus):
        self._client = trading_client
        self._db = db
        self._config = config
        self._bus = event_bus

    def submit_spread_order(self, signal: TradeSignal):
        legs = [
            OptionLegRequest(
                symbol=leg.symbol,
                side=OrderSide.SELL if leg.side == "sell" else OrderSide.BUY,
                ratio_qty=1,
            )
            for leg in signal.legs
        ]

        quantity = getattr(signal, "quantity", 1) or 1
        order_request = LimitOrderRequest(
            qty=quantity,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.MLEG,
            limit_price=round(signal.target_premium, 2),
            legs=legs,
        )

        order = self._client.submit_order(order_request)

        self._db.save_order_log({
            "order_id": str(order.id),
            "signal": {
                "strategy_mode": signal.strategy_mode,
                "symbol": signal.symbol,
                "spread_type": signal.spread_type,
                "target_premium": signal.target_premium,
                "expiration": str(signal.expiration),
            },
            "status": str(order.status),
            "timestamp": datetime.now(timezone.utc),
        })

        if str(order.status) in ("filled", "partially_filled"):
            self._bus.publish("OrderFilled", {
                "order_id": str(order.id),
                "signal": signal,
                "filled_price": float(getattr(order, "filled_avg_price", 0) or 0),
            })
        else:
            self._bus.publish("OrderSubmitted", {"order_id": str(order.id), "signal": signal})

        return order

    def submit_close_order(self, legs: list[SpreadLeg], limit_price: float):
        close_legs = [
            OptionLegRequest(
                symbol=leg.symbol,
                side=OrderSide.BUY if leg.side == "sell" else OrderSide.SELL,
                ratio_qty=1,
            )
            for leg in legs
        ]

        order_request = LimitOrderRequest(
            qty=1,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.MLEG,
            limit_price=round(limit_price, 2),
            legs=close_legs,
        )

        order = self._client.submit_order(order_request)

        self._db.save_order_log({
            "order_id": str(order.id),
            "action": "close",
            "status": str(order.status),
            "limit_price": limit_price,
            "timestamp": datetime.now(timezone.utc),
        })

        return order

    # --- Wheel Strategy: Single-Leg Option Orders ---

    def submit_wheel_order(self, signal: WheelSignal):
        """Submit a single-leg sell-to-open order for wheel CSP or CC."""
        order_request = LimitOrderRequest(
            symbol=signal.option_contract,
            qty=signal.quantity,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            limit_price=round(signal.target_premium, 2),
        )

        order = self._client.submit_order(order_request)

        self._db.save_order_log({
            "order_id": str(order.id),
            "signal": {
                "strategy_mode": "wheel",
                "symbol": signal.symbol,
                "phase": signal.phase,
                "option_contract": signal.option_contract,
                "strike_price": signal.strike_price,
                "contract_type": signal.contract_type,
                "target_premium": signal.target_premium,
                "expiration": str(signal.expiration),
            },
            "status": str(order.status),
            "timestamp": datetime.now(timezone.utc),
        })

        if str(order.status) in ("filled", "partially_filled"):
            self._bus.publish("WheelOrderFilled", {
                "order_id": str(order.id),
                "signal": signal,
                "filled_price": float(getattr(order, "filled_avg_price", 0) or 0),
            })
        else:
            self._bus.publish("OrderSubmitted", {"order_id": str(order.id), "signal": signal})

        return order

    def submit_wheel_close_order(self, option_symbol: str, quantity: int, limit_price: float):
        """Buy-to-close a single-leg option (for rolling or profit target)."""
        order_request = LimitOrderRequest(
            symbol=option_symbol,
            qty=quantity,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            limit_price=round(limit_price, 2),
        )

        order = self._client.submit_order(order_request)

        self._db.save_order_log({
            "order_id": str(order.id),
            "action": "wheel_close",
            "option_symbol": option_symbol,
            "status": str(order.status),
            "limit_price": limit_price,
            "timestamp": datetime.now(timezone.utc),
        })

        return order

    def cancel_order(self, order_id: str):
        self._client.cancel_order_by_id(order_id)
        logger.info(f"Cancelled order {order_id}")

    def get_order_status(self, order_id: str):
        return self._client.get_order_by_id(order_id)

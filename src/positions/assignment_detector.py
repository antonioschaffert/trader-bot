"""
Assignment Detector - Polls Alpaca for Option Assignment Events

Detects when:
1. CSP is assigned -> shares appear in account (transition to holding_shares)
2. CC is assigned -> shares disappear from account (transition to idle, cycle complete)
3. Options expire OTM -> option position disappears without shares changing

Runs on a 2-minute interval alongside the existing position check loop.
"""

import logging
from datetime import date, datetime, timezone

from alpaca.trading.client import TradingClient

from src.db.mongo import MongoStore
from src.event_bus import EventBus
from src.signals.wheel_state import WheelStateManager

logger = logging.getLogger(__name__)


class AssignmentDetector:
    def __init__(
        self,
        trading_client: TradingClient,
        wheel_state: WheelStateManager,
        event_bus: EventBus,
        db: MongoStore,
        wheel_symbols: list[str],
    ):
        self._client = trading_client
        self._state = wheel_state
        self._bus = event_bus
        self._db = db
        self._wheel_symbols = wheel_symbols

    def check(self) -> None:
        """Main check: detect assignments and expirations for all wheel symbols."""
        try:
            positions = self._client.get_all_positions()
        except Exception:
            logger.exception("Failed to fetch Alpaca positions for assignment detection")
            return

        # Build a map of current stock holdings
        stock_holdings: dict[str, int] = {}
        option_holdings: set[str] = set()
        for pos in positions:
            asset_class = str(getattr(pos, "asset_class", ""))
            sym = str(getattr(pos, "symbol", ""))
            qty = int(float(getattr(pos, "qty", 0)))
            avg_price = float(getattr(pos, "avg_entry_price", 0))

            if asset_class == "us_equity" and sym in self._wheel_symbols:
                stock_holdings[sym] = qty
            elif asset_class == "us_option":
                option_holdings.add(sym)

        # Check each wheel position
        for symbol in self._wheel_symbols:
            wheel_pos = self._state.get_position(symbol)
            shares_in_account = stock_holdings.get(symbol, 0)

            if wheel_pos.phase == "selling_csp":
                self._check_csp_assignment(wheel_pos, shares_in_account, option_holdings, positions)

            elif wheel_pos.phase == "selling_cc":
                self._check_cc_assignment(wheel_pos, shares_in_account, option_holdings)

    def _check_csp_assignment(self, wheel_pos, shares_in_account: int, option_holdings: set, all_positions) -> None:
        """Check if a CSP has been assigned (shares appeared in account)."""
        symbol = wheel_pos.symbol
        option_sym = wheel_pos.current_option_symbol

        # Assignment: shares appeared AND option is gone
        if shares_in_account >= 100 and option_sym and option_sym not in option_holdings:
            # Find the avg entry price from positions
            cost_basis = wheel_pos.current_option_strike
            for pos in all_positions:
                if str(getattr(pos, "symbol", "")) == symbol and str(getattr(pos, "asset_class", "")) == "us_equity":
                    cost_basis = float(getattr(pos, "avg_entry_price", wheel_pos.current_option_strike))
                    break

            # Effective cost basis accounts for premium collected
            effective_basis = cost_basis - wheel_pos.current_option_entry_premium

            logger.info(
                f"WHEEL ASSIGNMENT: {symbol} CSP assigned. "
                f"Shares: {shares_in_account}, cost basis: ${cost_basis:.2f}, "
                f"effective (after premium): ${effective_basis:.2f}"
            )

            self._state.transition(
                symbol, "holding_shares",
                shares_held=shares_in_account,
                cost_basis=effective_basis,
            )

            self._bus.publish("WheelAssignment", {
                "symbol": symbol,
                "shares": shares_in_account,
                "strike": wheel_pos.current_option_strike,
                "cost_basis": effective_basis,
                "premium_collected": wheel_pos.current_option_entry_premium,
            })

            # Log the CSP leg as a trade
            self._db.save_trade({
                "order_id": wheel_pos.current_option_order_id,
                "strategy_mode": "wheel",
                "symbol": symbol,
                "spread_type": "cash_secured_put",
                "entry_premium": wheel_pos.current_option_entry_premium,
                "close_premium": 0,  # assigned, no close
                "pnl": 0,  # P&L realized when shares eventually sold
                "reason": "assigned",
                "opened_at": wheel_pos.started_at,
                "closed_at": datetime.now(timezone.utc),
                "strike": wheel_pos.current_option_strike,
                "expiration": str(wheel_pos.current_option_expiration),
            })

        # Option expired OTM: option gone but no shares
        elif shares_in_account < 100 and option_sym and option_sym not in option_holdings:
            # Check if past expiration
            exp = wheel_pos.current_option_expiration
            if exp and date.today() > exp:
                logger.info(f"WHEEL: {symbol} CSP expired OTM. Premium kept: ${wheel_pos.current_option_entry_premium:.2f}")

                premium = wheel_pos.current_option_entry_premium
                self._state.get_position(symbol).total_premium_collected += premium * 100

                self._state.transition(symbol, "idle")

                self._bus.publish("WheelCSPExpired", {
                    "symbol": symbol,
                    "strike": wheel_pos.current_option_strike,
                    "premium_kept": premium,
                })

                self._db.save_trade({
                    "order_id": wheel_pos.current_option_order_id,
                    "strategy_mode": "wheel",
                    "symbol": symbol,
                    "spread_type": "cash_secured_put",
                    "entry_premium": premium,
                    "close_premium": 0,
                    "pnl": premium * 100,
                    "reason": "expired_otm",
                    "opened_at": wheel_pos.started_at,
                    "closed_at": datetime.now(timezone.utc),
                    "strike": wheel_pos.current_option_strike,
                    "expiration": str(wheel_pos.current_option_expiration),
                })

    def _check_cc_assignment(self, wheel_pos, shares_in_account: int, option_holdings: set) -> None:
        """Check if a CC has been assigned (shares disappeared from account)."""
        symbol = wheel_pos.symbol
        option_sym = wheel_pos.current_option_symbol

        # Called away: shares gone AND option gone
        if shares_in_account < 100 and option_sym and option_sym not in option_holdings:
            # Profit from selling shares at strike
            share_profit = (wheel_pos.current_option_strike - wheel_pos.cost_basis) * wheel_pos.shares_held
            premium = wheel_pos.current_option_entry_premium
            total_cycle_pnl = share_profit + wheel_pos.total_premium_collected

            logger.info(
                f"WHEEL CALLED AWAY: {symbol}. "
                f"Sold {wheel_pos.shares_held} shares @ ${wheel_pos.current_option_strike:.2f}. "
                f"Share P&L: ${share_profit:.2f}, total cycle P&L: ${total_cycle_pnl:.2f}"
            )

            self._state.transition(symbol, "idle")

            self._bus.publish("WheelSharesCalledAway", {
                "symbol": symbol,
                "shares": wheel_pos.shares_held,
                "strike": wheel_pos.current_option_strike,
                "cost_basis": wheel_pos.cost_basis,
                "share_profit": share_profit,
                "total_premium": wheel_pos.total_premium_collected,
                "cycles_completed": wheel_pos.cycles_completed,
            })

            self._db.save_trade({
                "order_id": wheel_pos.current_option_order_id,
                "strategy_mode": "wheel",
                "symbol": symbol,
                "spread_type": "covered_call",
                "entry_premium": premium,
                "close_premium": 0,
                "pnl": share_profit + premium * 100,
                "reason": "called_away",
                "opened_at": wheel_pos.last_updated,
                "closed_at": datetime.now(timezone.utc),
                "strike": wheel_pos.current_option_strike,
                "expiration": str(wheel_pos.current_option_expiration),
                "cycle_pnl": total_cycle_pnl,
            })

            self._bus.publish("WheelCycleCompleted", {
                "symbol": symbol,
                "total_pnl": total_cycle_pnl,
                "cycles": wheel_pos.cycles_completed,
            })

        # CC expired OTM: option gone but shares remain
        elif shares_in_account >= 100 and option_sym and option_sym not in option_holdings:
            exp = wheel_pos.current_option_expiration
            if exp and date.today() > exp:
                premium = wheel_pos.current_option_entry_premium
                logger.info(f"WHEEL: {symbol} CC expired OTM. Premium kept: ${premium:.2f}")

                self._state.get_position(symbol).total_premium_collected += premium * 100

                self._state.transition(symbol, "holding_shares")

                self._bus.publish("WheelCCExpired", {
                    "symbol": symbol,
                    "strike": wheel_pos.current_option_strike,
                    "premium_kept": premium,
                })

                self._db.save_trade({
                    "order_id": wheel_pos.current_option_order_id,
                    "strategy_mode": "wheel",
                    "symbol": symbol,
                    "spread_type": "covered_call",
                    "entry_premium": premium,
                    "close_premium": 0,
                    "pnl": premium * 100,
                    "reason": "expired_otm",
                    "opened_at": wheel_pos.last_updated,
                    "closed_at": datetime.now(timezone.utc),
                    "strike": wheel_pos.current_option_strike,
                    "expiration": str(wheel_pos.current_option_expiration),
                })

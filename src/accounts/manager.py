"""
Account Manager - Multi-Account Orchestrator

Manages multiple Alpaca accounts, each with its own:
- TradingClient (for orders)
- PositionManager (tracks open positions)
- RiskManager (per-account risk limits)
- Signal generators (swing/exhaustion/wheel, independently toggleable)
- OrderExecutor
- EventBus
- TradingScheduler (runs in its own thread)

Shared across all accounts:
- MarketDataClient (market data is the same for everyone)
- OptionHistoricalDataClient (shared data client)
- MongoStore (single DB, data tagged with account_id)
- RegimeDetector (runs once globally)
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from alpaca.trading.client import TradingClient

from src.config import AppConfig
from src.db.mongo import MongoStore
from src.event_bus import EventBus
from src.execution.executor import OrderExecutor
from src.positions.assignment_detector import AssignmentDetector
from src.positions.manager import PositionManager
from src.risk.manager import RiskManager
from src.scheduler import TradingScheduler
from src.signals.exhaustion import ExhaustionSignalGenerator
from src.signals.swing import SwingSignalGenerator
from src.signals.wheel import WheelSignalGenerator
from src.signals.wheel_state import WheelStateManager

logger = logging.getLogger(__name__)


@dataclass
class AccountContext:
    """Everything needed to run one account's bot."""
    account_id: str
    name: str
    is_paper: bool
    trading_client: TradingClient
    position_manager: PositionManager
    risk_manager: RiskManager
    executor: OrderExecutor
    event_bus: EventBus
    scheduler: TradingScheduler | None = None
    thread: threading.Thread | None = None
    strategies_enabled: dict = field(default_factory=lambda: {
        "swing": True, "exhaustion": True, "wheel": False,
    })
    symbols: list[str] = field(default_factory=list)


class AccountManager:
    def __init__(self, db: MongoStore, market_data, option_client, config: AppConfig):
        self._db = db
        self._market_data = market_data
        self._option_client = option_client
        self._config = config
        self._accounts: dict[str, AccountContext] = {}
        self._lock = threading.Lock()

    def load_accounts(self) -> list[dict]:
        """Load all accounts from MongoDB. Auto-create default if none exist."""
        accounts = self._db.get_accounts()

        if not accounts and self._config.alpaca_api_key:
            logger.info("No accounts in DB — creating default from env vars")
            default = {
                "account_id": "default",
                "name": "Default (from env)",
                "api_key": self._config.alpaca_api_key,
                "api_secret": self._config.alpaca_api_secret,
                "is_paper": self._config.alpaca_paper,
                "enabled": True,
                "strategies": {
                    "swing": True,
                    "exhaustion": self._config.exhaustion.enabled,
                    "wheel": self._config.wheel.enabled,
                },
                "symbols": self._config.symbols,
                "created_at": datetime.now(timezone.utc),
            }
            self._db.save_account(default)
            accounts = [default]

        return accounts

    def start_all(self) -> None:
        """Start schedulers for all enabled accounts."""
        accounts = self.load_accounts()
        for acct in accounts:
            if acct.get("enabled", False):
                try:
                    self.start_account(acct)
                except Exception:
                    logger.exception(f"Failed to start account {acct['account_id']}")

    def start_account(self, acct: dict) -> None:
        """Create a full bot stack for one account and start it in a thread."""
        account_id = acct["account_id"]

        with self._lock:
            if account_id in self._accounts:
                logger.warning(f"Account {account_id} already running")
                return

        api_key = acct["api_key"]
        api_secret = acct["api_secret"]
        is_paper = acct.get("is_paper", True)
        strategies = acct.get("strategies", {})
        symbols = acct.get("symbols", self._config.symbols)

        trading_client = TradingClient(api_key, api_secret, paper=is_paper)
        event_bus = EventBus()

        # Build risk manager
        risk_config = {
            "max_concurrent_spreads": self._config.risk.max_concurrent_spreads,
            "max_risk_per_trade_pct": self._config.risk.max_risk_per_trade_pct,
            "max_buying_power_usage_pct": self._config.risk.max_buying_power_usage_pct,
            "stop_loss_multiplier": self._config.risk.stop_loss_multiplier,
            "roll_delta_threshold": self._config.risk.roll_delta_threshold,
            "dte_exit": self._config.risk.dte_exit,
            "daily_loss_limit": self._config.risk.daily_loss_limit,
            "daily_income_target": self._config.risk.daily_income_target,
            "max_same_direction_per_symbol": self._config.risk.max_same_direction_per_symbol,
            "max_portfolio_delta_per_symbol": self._config.risk.max_portfolio_delta_per_symbol,
            "max_correlated_same_direction": self._config.risk.max_correlated_same_direction,
            "max_portfolio_vega": self._config.risk.max_portfolio_vega,
            "max_contracts_per_trade": self._config.risk.max_contracts_per_trade,
        }
        risk_manager = RiskManager(risk_config, event_bus)

        # Build executor
        exec_config = {
            "price_adjustment_interval": self._config.execution.price_adjustment_interval,
            "price_adjustment_step": self._config.execution.price_adjustment_step,
            "fill_timeout": self._config.execution.fill_timeout,
        }
        executor = OrderExecutor(trading_client, self._db, exec_config, event_bus)

        # Build position manager and sync existing positions from Alpaca
        position_manager = PositionManager(self._db, event_bus)
        position_manager.sync_from_alpaca(trading_client)

        # Build signal generators
        swing_gen = SwingSignalGenerator({
            "target_dte": self._config.swing.target_dte,
            "short_strike_delta": self._config.swing.short_strike_delta,
            "spread_width": self._config.swing.spread_width,
            "min_premium": self._config.swing.min_premium,
            "iv_rank_threshold": self._config.swing.iv_rank_threshold,
            "profit_target_pct": self._config.swing.profit_target_pct,
        }, event_bus)

        exhaustion_gen = ExhaustionSignalGenerator({
            "enabled": strategies.get("exhaustion", False),
            "target_dte": self._config.exhaustion.target_dte,
            "spread_width": self._config.exhaustion.spread_width,
            "min_premium": self._config.exhaustion.min_premium,
            "profit_target_pct": self._config.exhaustion.profit_target_pct,
            "stop_loss_multiplier": self._config.exhaustion.stop_loss_multiplier,
            "time_window_start": self._config.exhaustion.time_window_start,
            "rsi_overbought": self._config.exhaustion.rsi_overbought,
            "rsi_oversold": self._config.exhaustion.rsi_oversold,
            "intraday_timeframe": self._config.exhaustion.intraday_timeframe,
            "min_signals_required": self._config.exhaustion.min_signals_required,
            "min_move_from_open_pct": self._config.exhaustion.min_move_from_open_pct,
            "strong_move_pct": self._config.exhaustion.strong_move_pct,
            "close_by_eod": self._config.exhaustion.close_by_eod,
        }, event_bus)

        # Wheel components (if wheel strategy enabled for this account)
        wheel_gen = None
        wheel_state = None
        assignment_detector = None
        if strategies.get("wheel", False):
            wheel_state = WheelStateManager(self._db)
            wheel_state.load_state()
            wheel_config = {
                "enabled": True,
                "symbols": self._config.wheel.symbols,
                "target_dte": self._config.wheel.target_dte,
                "csp_delta_range": self._config.wheel.csp_delta_range,
                "cc_delta_range": self._config.wheel.cc_delta_range,
                "min_open_interest": self._config.wheel.min_open_interest,
                "csp_strike_range_pct": self._config.wheel.csp_strike_range_pct,
                "cc_above_bollinger": self._config.wheel.cc_above_bollinger,
                "max_buying_power_pct": self._config.wheel.max_buying_power_pct,
                "roll_delta_multiplier": self._config.wheel.roll_delta_multiplier,
                "roll_profit_pct": self._config.wheel.roll_profit_pct,
                "profit_target_pct": self._config.wheel.profit_target_pct,
                "max_positions": self._config.wheel.max_positions,
            }
            wheel_gen = WheelSignalGenerator(wheel_config, event_bus, wheel_state)
            assignment_detector = AssignmentDetector(
                trading_client, wheel_state, event_bus, self._db,
                self._config.wheel.symbols,
            )

        # Override config symbols for this account
        account_config = AppConfig(
            symbols=symbols,
            swing=self._config.swing,
            exhaustion=self._config.exhaustion,
            risk=self._config.risk,
            execution=self._config.execution,
            schedule=self._config.schedule,
            notifications=self._config.notifications,
            regime=self._config.regime,
            wheel=self._config.wheel,
        )

        scheduler = TradingScheduler(
            config=account_config, event_bus=event_bus,
            market_data=self._market_data,
            swing_gen=swing_gen, exhaustion_gen=exhaustion_gen,
            risk_manager=risk_manager, executor=executor,
            position_manager=position_manager,
            trading_client=trading_client,
            option_client=self._option_client, db=self._db,
            wheel_gen=wheel_gen, wheel_state=wheel_state,
            assignment_detector=assignment_detector,
            account_id=account_id,
            strategies_enabled=strategies,
        )

        ctx = AccountContext(
            account_id=account_id,
            name=acct.get("name", account_id),
            is_paper=is_paper,
            trading_client=trading_client,
            position_manager=position_manager,
            risk_manager=risk_manager,
            executor=executor,
            event_bus=event_bus,
            scheduler=scheduler,
            strategies_enabled=strategies,
            symbols=symbols,
        )

        # Start scheduler in a thread (BlockingScheduler.start() blocks)
        thread = threading.Thread(
            target=self._run_scheduler,
            args=(scheduler, account_id),
            daemon=True,
            name=f"scheduler-{account_id}",
        )
        ctx.thread = thread

        with self._lock:
            self._accounts[account_id] = ctx

        thread.start()
        logger.info(
            f"Account {account_id} ({acct.get('name', '')}) started "
            f"[paper={is_paper}, strategies={strategies}]"
        )

    def _run_scheduler(self, scheduler: TradingScheduler, account_id: str) -> None:
        """Run a scheduler in a thread. Catches exceptions so other accounts keep running."""
        try:
            scheduler.start()
        except Exception:
            logger.exception(f"Scheduler for account {account_id} crashed")

    def stop_account(self, account_id: str) -> None:
        """Stop a running account's scheduler."""
        with self._lock:
            ctx = self._accounts.pop(account_id, None)

        if ctx and ctx.scheduler:
            try:
                ctx.scheduler.stop()
            except Exception:
                logger.exception(f"Error stopping scheduler for {account_id}")
            logger.info(f"Account {account_id} stopped")

    def stop_all(self) -> None:
        """Stop all running account schedulers."""
        account_ids = list(self._accounts.keys())
        for aid in account_ids:
            self.stop_account(aid)

    def restart_account(self, account_id: str) -> None:
        """Stop and restart an account (for config changes)."""
        self.stop_account(account_id)
        acct = self._db.get_account(account_id)
        if acct and acct.get("enabled", False):
            self.start_account(acct)

    def get_running_accounts(self) -> list[str]:
        """Return list of currently running account IDs."""
        with self._lock:
            return list(self._accounts.keys())

    def get_context(self, account_id: str) -> AccountContext | None:
        """Get the running context for an account."""
        with self._lock:
            return self._accounts.get(account_id)

    def get_status(self) -> list[dict]:
        """Return status of all accounts (both running and DB-stored)."""
        all_accounts = self._db.get_accounts()
        running = self.get_running_accounts()

        result = []
        for acct in all_accounts:
            aid = acct["account_id"]
            status = {
                "account_id": aid,
                "name": acct.get("name", aid),
                "is_paper": acct.get("is_paper", True),
                "enabled": acct.get("enabled", False),
                "running": aid in running,
                "strategies": acct.get("strategies", {}),
                "symbols": acct.get("symbols", []),
            }
            result.append(status)

        return result

import logging
from datetime import datetime, time as dtime, timezone, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler

from src.config import AppConfig
from src.event_bus import EventBus
from src.execution.executor import OrderExecutor
from src.market_data.client import MarketDataClient
from src.market_data.indicators import compute_indicators, compute_iv_rank
from src.market_data.models import MarketSnapshot
from src.positions.manager import PositionManager
from src.risk.manager import RiskManager
from src.signals.exhaustion import ExhaustionSignalGenerator
from src.signals.swing import SwingSignalGenerator

logger = logging.getLogger(__name__)

MARKET_OPEN = dtime(9, 30)
MARKET_CLOSE = dtime(16, 0)


class TradingScheduler:
    def __init__(
        self, config: AppConfig, event_bus: EventBus, market_data: MarketDataClient,
        swing_gen: SwingSignalGenerator, exhaustion_gen: ExhaustionSignalGenerator,
        risk_manager: RiskManager, executor: OrderExecutor,
        position_manager: PositionManager, trading_client, option_client, db,
    ):
        self._config = config
        self._bus = event_bus
        self._market_data = market_data
        self._swing_gen = swing_gen
        self._exhaustion_gen = exhaustion_gen
        self._risk_manager = risk_manager
        self._executor = executor
        self._positions = position_manager
        self._trading_client = trading_client
        self._option_client = option_client
        self._db = db
        self._scheduler = BlockingScheduler()

    def start(self) -> None:
        interval = self._config.schedule.scan_interval_minutes
        self._scheduler.add_job(self._scan_loop, "interval", minutes=interval, id="scan_loop")
        self._scheduler.add_job(self._position_check_loop, "interval", minutes=1, id="position_check")
        self._scheduler.add_job(self._daily_reset, "cron", hour=9, minute=25, id="daily_reset")
        logger.info(f"Scheduler started (scan interval: {interval}min)")
        self._scheduler.start()

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)

    def _is_market_hours(self) -> bool:
        if not self._config.schedule.market_hours_only:
            return True
        now_et = datetime.now(timezone(timedelta(hours=-4))).time()
        return MARKET_OPEN <= now_et <= MARKET_CLOSE

    def _scan_loop(self) -> None:
        if not self._is_market_hours():
            return
        for symbol in self._config.symbols:
            try:
                self._scan_symbol(symbol)
            except Exception:
                logger.exception(f"Error scanning {symbol}")

    def _scan_symbol(self, symbol: str) -> None:
        logger.info(f"Scanning {symbol}")
        price = self._market_data.get_latest_price(symbol)
        daily_bars = self._market_data.get_daily_bars(symbol, limit=60)
        indicators = compute_indicators(daily_bars)

        since = datetime.now(timezone.utc) - timedelta(weeks=52)
        iv_records = self._db.get_iv_history(symbol, since)
        iv_history_values = [r["iv"] for r in iv_records]
        current_iv = self._get_atm_iv(symbol, price)
        if current_iv > 0:
            self._db.save_iv_record({"symbol": symbol, "iv": current_iv, "timestamp": datetime.now(timezone.utc)})
        iv_rank = compute_iv_rank(current_iv, iv_history_values) if iv_history_values and current_iv > 0 else None

        # Swing strategy
        swing_chain = self._market_data.get_options_chain(symbol, min_dte=self._config.swing.target_dte[0], max_dte=self._config.swing.target_dte[1])
        self._market_data.enrich_chain_with_quotes(swing_chain)
        swing_snapshot = MarketSnapshot(symbol=symbol, price=price, bars=daily_bars, options_chain=swing_chain, indicators=indicators, iv_rank=iv_rank)
        swing_signals = self._swing_gen.evaluate(swing_snapshot)
        self._process_signals(swing_signals)

        # Exhaustion strategy
        if self._config.exhaustion.enabled:
            exhaustion_chain = self._market_data.get_options_chain(symbol, min_dte=self._config.exhaustion.target_dte[0], max_dte=self._config.exhaustion.target_dte[1])
            self._market_data.enrich_chain_with_quotes(exhaustion_chain)
            intraday_bars = self._market_data.get_intraday_bars(symbol)
            intraday_indicators = compute_indicators(intraday_bars)
            exhaustion_snapshot = MarketSnapshot(
                symbol=symbol, price=price, bars=daily_bars, options_chain=exhaustion_chain,
                indicators=indicators, iv_rank=iv_rank,
                high_of_day=max((b.high for b in intraday_bars), default=0),
                low_of_day=min((b.low for b in intraday_bars), default=0),
                intraday_bars=intraday_bars, intraday_indicators=intraday_indicators,
            )
            exhaustion_signals = self._exhaustion_gen.evaluate(exhaustion_snapshot)
            self._process_signals(exhaustion_signals)

    def _process_signals(self, signals) -> None:
        account = self._trading_client.get_account()
        for signal in signals:
            result = self._risk_manager.validate_signal(signal, open_positions=self._positions.open_positions, account=account, daily_pnl=self._positions.daily_pnl)
            if result.approved:
                logger.info(f"Signal approved: {signal.symbol} {signal.spread_type}")
                self._executor.submit_spread_order(signal)
                self._bus.publish("SignalValidated", {"signal": signal})
            else:
                logger.info(f"Signal rejected: {result.reason}")
                self._bus.publish("SignalRejected", {"signal": signal, "reason": result.reason})

    def _position_check_loop(self) -> None:
        if not self._is_market_hours():
            return
        for position in list(self._positions.open_positions):
            try:
                self._check_position(position)
            except Exception:
                logger.exception(f"Error checking position {position.order_id}")

    def _check_position(self, position) -> None:
        self._update_position_value(position)
        days_to_exp = (position.expiration - datetime.now(timezone.utc).date()).days

        if self._risk_manager.check_dte_exit(days_to_exp):
            logger.info(f"DTE exit for {position.order_id}")
            self._executor.submit_close_order(position.legs, limit_price=position.current_value)
            self._positions.close_position(position.order_id, position.current_value, "dte_exit")
            return

        if self._risk_manager.check_profit_target(position.current_value, position.entry_premium, position.profit_target_pct):
            self._executor.submit_close_order(position.legs, limit_price=position.current_value)
            self._positions.close_position(position.order_id, position.current_value, "profit_target")
            self._bus.publish("ProfitTargetHit", {"position": position})
            return

        if position.strategy_mode == "swing":
            short_leg = next((l for l in position.legs if l.side == "sell"), None)
            if short_leg and self._risk_manager.check_roll_needed(abs(short_leg.delta), self._config.risk.roll_delta_threshold):
                logger.info(f"Rolling {position.order_id}: short delta {short_leg.delta:.2f}")
                self._executor.submit_close_order(position.legs, limit_price=position.current_value)
                self._positions.close_position(position.order_id, position.current_value, "rolled")
                self._bus.publish("RollTriggered", {"position": position})
                return

        multiplier = self._config.risk.stop_loss_multiplier
        if position.strategy_mode == "exhaustion":
            multiplier = self._config.exhaustion.stop_loss_multiplier
        if self._risk_manager.check_stop_loss(position.current_value, position.entry_premium, multiplier):
            self._executor.submit_close_order(position.legs, limit_price=position.current_value)
            self._positions.close_position(position.order_id, position.current_value, "stop_loss")
            self._bus.publish("StopLossHit", {"position": position})
            return

    def _update_position_value(self, position) -> None:
        try:
            from alpaca.data.requests import OptionLatestQuoteRequest
            leg_symbols = [leg.symbol for leg in position.legs]
            req = OptionLatestQuoteRequest(symbol_or_symbols=leg_symbols)
            quotes = self._option_client.get_option_latest_quote(req)
            total_value = 0.0
            for leg in position.legs:
                if leg.symbol in quotes:
                    q = quotes[leg.symbol]
                    mid = (float(q.bid_price) + float(q.ask_price)) / 2
                    if leg.side == "sell":
                        total_value += mid
                    else:
                        total_value -= mid
            position.current_value = total_value
            position.unrealized_pnl = (position.entry_premium - total_value) * 100
        except Exception:
            logger.exception(f"Failed to update position value for {position.order_id}")

    def _get_atm_iv(self, symbol: str, price: float) -> float:
        try:
            chain = self._market_data.get_options_chain(symbol, min_dte=20, max_dte=40)
            self._market_data.enrich_chain_with_quotes(chain)
            all_contracts = chain.calls + chain.puts
            if not all_contracts:
                return 0.0
            atm = min(all_contracts, key=lambda c: abs(c.strike_price - price))
            return atm.implied_volatility
        except Exception:
            logger.exception(f"Failed to get ATM IV for {symbol}")
            return 0.0

    def _daily_reset(self) -> None:
        self._positions.reset_daily()
        logger.info("Daily reset complete")

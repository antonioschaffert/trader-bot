"""
Trading Scheduler - Enhanced

Now orchestrates:
1. Market regime detection (VIX fetch, trend analysis)
2. Regime-adaptive signal generation (swing, exhaustion, wheel)
3. Portfolio Greeks tracking and persistence
4. Drawdown monitoring with trade result recording
5. Correlation updates
6. Performance analytics (computed periodically)
7. Wheel strategy: CSP/CC scanning, rolling, assignment detection
"""

import logging
from datetime import datetime, time as dtime, timezone, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler

from src.analytics.performance import PerformanceAnalytics
from src.config import AppConfig
from src.event_bus import EventBus
from src.execution.executor import OrderExecutor
from src.market_data.client import MarketDataClient
from src.market_data.indicators import compute_indicators, compute_iv_rank, compute_iv_percentile
from src.market_data.models import MarketSnapshot
from src.market_data.regime import RegimeDetector
from src.positions.manager import PositionManager
from src.risk.correlation import CorrelationManager
from src.risk.manager import RiskManager
from src.positions.assignment_detector import AssignmentDetector
from src.signals.exhaustion import ExhaustionSignalGenerator
from src.signals.swing import SwingSignalGenerator
from src.signals.wheel import WheelSignalGenerator
from src.signals.wheel_state import WheelStateManager

logger = logging.getLogger(__name__)

MARKET_OPEN = dtime(9, 30)
MARKET_CLOSE = dtime(16, 0)


class TradingScheduler:
    def __init__(
        self, config: AppConfig, event_bus: EventBus, market_data: MarketDataClient,
        swing_gen: SwingSignalGenerator, exhaustion_gen: ExhaustionSignalGenerator,
        risk_manager: RiskManager, executor: OrderExecutor,
        position_manager: PositionManager, trading_client, option_client, db,
        wheel_gen: WheelSignalGenerator | None = None,
        wheel_state: WheelStateManager | None = None,
        assignment_detector: AssignmentDetector | None = None,
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

        # Enhanced components
        self._regime_detector = RegimeDetector()
        self._correlation_mgr = CorrelationManager(config.symbols)
        self._risk_manager.set_correlation_manager(self._correlation_mgr)
        self._analytics = PerformanceAnalytics(db)
        self._current_regime = None

        # Wheel strategy components (third strategy)
        self._wheel_gen = wheel_gen
        self._wheel_state = wheel_state
        self._assignment_detector = assignment_detector

        # Track daily bars per symbol for correlation updates
        self._daily_bars_cache: dict[str, list] = {}

        # Subscribe to trade close events for drawdown tracking
        self._bus.subscribe("PositionClosed", self._on_position_closed)

    def start(self) -> None:
        interval = self._config.schedule.scan_interval_minutes
        self._scheduler.add_job(self._scan_loop, "interval", minutes=interval, id="scan_loop")
        self._scheduler.add_job(self._position_check_loop, "interval", minutes=1, id="position_check")
        self._scheduler.add_job(self._heartbeat, "interval", seconds=30, id="heartbeat")
        self._scheduler.add_job(self._daily_reset, "cron", hour=9, minute=25, id="daily_reset")
        # Compute analytics every 30 minutes
        self._scheduler.add_job(self._update_analytics, "interval", minutes=30, id="analytics")

        # Wheel strategy jobs (third strategy)
        if self._config.wheel.enabled and self._wheel_gen:
            self._scheduler.add_job(self._wheel_scan_loop, "interval", minutes=interval, id="wheel_scan")
            self._scheduler.add_job(self._wheel_position_check, "interval", minutes=1, id="wheel_position_check")
            self._scheduler.add_job(self._assignment_check_loop, "interval", minutes=2, id="assignment_check")
            logger.info(f"Wheel strategy enabled: symbols={self._config.wheel.symbols}")

        self._heartbeat()
        logger.info(f"Scheduler started (scan interval: {interval}min)")
        self._scheduler.start()

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)

    def _is_market_hours(self) -> bool:
        if not self._config.schedule.market_hours_only:
            return True
        now_et = datetime.now(timezone(timedelta(hours=-4))).time()
        return MARKET_OPEN <= now_et <= MARKET_CLOSE

    def _on_position_closed(self, trade_record: dict) -> None:
        """Track trade results for drawdown management."""
        pnl = trade_record.get("pnl", 0)
        self._risk_manager.drawdown_manager.record_trade_result(pnl)
        # Persist drawdown state
        self._db.save_drawdown_state(self._risk_manager.drawdown_manager.state.to_dict())

    def _scan_loop(self) -> None:
        if not self._is_market_hours():
            return

        # Reload config from DB
        try:
            from src.config import load_config
            self._config = load_config(db=self._db)
            self._propagate_config()
        except Exception:
            logger.exception("Failed to reload config from DB, using cached config")

        # Update equity for drawdown tracking
        try:
            account = self._trading_client.get_account()
            equity = float(getattr(account, "equity", 0))
            if equity > 0:
                self._risk_manager.drawdown_manager.update_equity(equity)
        except Exception:
            logger.exception("Failed to fetch account for drawdown tracking")

        # Detect market regime FIRST (informs all downstream decisions)
        self._update_regime()

        # Update correlations
        self._update_correlations()

        # Scan each symbol
        for symbol in self._config.symbols:
            try:
                self._scan_symbol(symbol)
            except Exception:
                logger.exception(f"Error scanning {symbol}")

        # Update portfolio Greeks
        self._update_portfolio_greeks()

    def _update_regime(self) -> None:
        """Fetch VIX data and run regime detection."""
        if not self._config.regime.enabled:
            return

        try:
            vix_symbol = self._config.regime.vix_symbol
            vix_price = self._market_data.get_latest_price(vix_symbol)
            vix_bars = self._market_data.get_daily_bars(vix_symbol, limit=30)

            # Get SPY bars for trend analysis
            spy_daily = self._market_data.get_daily_bars("SPY", limit=60)
            spy_intraday = self._market_data.get_intraday_bars("SPY")

            # Compute ADX from SPY daily bars
            spy_indicators = compute_indicators(spy_daily)
            adx_value = spy_indicators.adx

            self._current_regime = self._regime_detector.analyze(
                vix_price=vix_price,
                vix_bars=vix_bars,
                spy_daily_bars=spy_daily,
                spy_intraday_bars=spy_intraday,
                adx_value=adx_value,
            )

            # Persist regime snapshot
            self._db.save_regime_snapshot(self._current_regime.to_dict())

            logger.info(
                f"REGIME: vol={self._current_regime.volatility_regime.value}, "
                f"trend={self._current_regime.trend_regime.value}, "
                f"phase={self._current_regime.market_phase.value}, "
                f"VIX={self._current_regime.vix_current:.1f}, "
                f"size_mult={self._current_regime.position_size_multiplier:.2f}, "
                f"should_trade={self._current_regime.should_trade}"
            )

        except Exception:
            logger.exception("Failed to update market regime (continuing with last known)")

    def _update_correlations(self) -> None:
        """Update correlation matrix from recent daily bars."""
        try:
            for symbol in self._config.symbols:
                if symbol not in self._daily_bars_cache:
                    self._daily_bars_cache[symbol] = self._market_data.get_daily_bars(symbol, limit=60)
            self._correlation_mgr.update_correlations(self._daily_bars_cache)
        except Exception:
            logger.exception("Failed to update correlations")

    def _update_portfolio_greeks(self) -> None:
        """Compute and persist portfolio Greeks."""
        try:
            greeks = self._risk_manager.greeks_tracker.update(self._positions.open_positions)
            self._db.save_portfolio_greeks(greeks.to_dict())

            if abs(greeks.net_delta) > 50:
                logger.warning(f"GREEKS: High portfolio delta: {greeks.net_delta:.0f}")
        except Exception:
            logger.exception("Failed to update portfolio Greeks")

    def _scan_symbol(self, symbol: str) -> None:
        logger.info(f"Scanning {symbol}")
        scan_time = datetime.now(timezone.utc)
        price = self._market_data.get_latest_price(symbol)
        daily_bars = self._market_data.get_daily_bars(symbol, limit=60)
        indicators = compute_indicators(daily_bars)

        # Cache daily bars for correlation computation
        self._daily_bars_cache[symbol] = daily_bars

        since = datetime.now(timezone.utc) - timedelta(weeks=52)
        iv_records = self._db.get_iv_history(symbol, since)
        iv_history_values = [r["iv"] for r in iv_records]
        current_iv = self._get_atm_iv(symbol, price)
        if current_iv > 0:
            self._db.save_iv_record({"symbol": symbol, "iv": current_iv, "timestamp": scan_time})
        iv_rank = compute_iv_rank(current_iv, iv_history_values) if iv_history_values and current_iv > 0 else None
        iv_percentile = compute_iv_percentile(current_iv, iv_history_values) if iv_history_values and current_iv > 0 else None

        all_rejections = []

        # Swing strategy
        swing_chain = self._market_data.get_options_chain(symbol, min_dte=self._config.swing.target_dte[0], max_dte=self._config.swing.target_dte[1])
        self._market_data.enrich_chain_with_quotes(swing_chain)
        swing_snapshot = MarketSnapshot(
            symbol=symbol, price=price, bars=daily_bars, options_chain=swing_chain,
            indicators=indicators, iv_rank=iv_rank, iv_percentile=iv_percentile,
            regime=self._current_regime,
        )
        swing_result = self._swing_gen.evaluate(swing_snapshot)
        all_rejections.extend(swing_result.rejections)
        self._process_signals(swing_result.signals, symbol, scan_time, all_rejections)

        # Exhaustion strategy
        if self._config.exhaustion.enabled:
            exhaustion_chain = self._market_data.get_options_chain(symbol, min_dte=self._config.exhaustion.target_dte[0], max_dte=self._config.exhaustion.target_dte[1])
            self._market_data.enrich_chain_with_quotes(exhaustion_chain)
            intraday_bars = self._market_data.get_intraday_bars(symbol)
            intraday_indicators = compute_indicators(intraday_bars)
            exhaustion_snapshot = MarketSnapshot(
                symbol=symbol, price=price, bars=daily_bars, options_chain=exhaustion_chain,
                indicators=indicators, iv_rank=iv_rank, iv_percentile=iv_percentile,
                high_of_day=max((b.high for b in intraday_bars), default=0),
                low_of_day=min((b.low for b in intraday_bars), default=0),
                intraday_bars=intraday_bars, intraday_indicators=intraday_indicators,
                regime=self._current_regime,
            )
            exhaustion_result = self._exhaustion_gen.evaluate(exhaustion_snapshot)
            all_rejections.extend(exhaustion_result.rejections)
            self._process_signals(exhaustion_result.signals, symbol, scan_time, all_rejections)

        # Save rejections with enhanced snapshot data
        if all_rejections:
            snapshot_vars = {
                "price": round(price, 2),
                "iv_rank": round(iv_rank, 2) if iv_rank is not None else None,
                "iv_percentile": round(iv_percentile, 1) if iv_percentile is not None else None,
                "current_iv": round(current_iv, 4) if current_iv else None,
                "rsi": round(indicators.rsi, 2) if indicators.rsi is not None else None,
                "sma_50": round(indicators.sma_50, 2) if indicators.sma_50 is not None else None,
                "sma_20": round(indicators.sma_20, 2) if indicators.sma_20 is not None else None,
                "adx": round(indicators.adx, 1) if indicators.adx is not None else None,
                "atr": round(indicators.atr_14, 2) if indicators.atr_14 is not None else None,
                "support": round(indicators.support, 2) if indicators.support is not None else None,
                "resistance": round(indicators.resistance, 2) if indicators.resistance is not None else None,
            }
            # Add regime context
            if self._current_regime:
                snapshot_vars["regime"] = {
                    "volatility": self._current_regime.volatility_regime.value,
                    "trend": self._current_regime.trend_regime.value,
                    "phase": self._current_regime.market_phase.value,
                    "vix": round(self._current_regime.vix_current, 1),
                }
            self._db.save_scan_rejection({
                "symbol": symbol,
                "timestamp": scan_time,
                "market_snapshot": snapshot_vars,
                "rejections": all_rejections,
            })

    def _process_signals(self, signals, symbol: str, scan_time: datetime, rejections: list) -> None:
        if not signals:
            return
        account = self._trading_client.get_account()
        for signal in signals:
            result = self._risk_manager.validate_signal(
                signal,
                open_positions=self._positions.open_positions,
                account=account,
                daily_pnl=self._positions.daily_pnl,
                regime=self._current_regime,
            )
            if result.approved:
                logger.info(
                    f"Signal approved: {signal.symbol} {signal.spread_type} "
                    f"x{signal.quantity} (conviction: {signal.conviction_score:.0f})"
                )
                self._executor.submit_spread_order(signal)
                self._bus.publish("SignalValidated", {"signal": signal})
            else:
                logger.info(f"Signal rejected: {result.reason}")
                self._bus.publish("SignalRejected", {"signal": signal, "reason": result.reason})
                rejections.append({
                    "strategy": signal.strategy_mode,
                    "spread_type": signal.spread_type,
                    "reason": f"risk_rejected: {result.reason}",
                    "variables": {
                        "target_premium": round(signal.target_premium, 4),
                        "expiration": str(signal.expiration),
                        "conviction": round(signal.conviction_score, 0),
                        "quantity": signal.quantity,
                    },
                })

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

    # --- Wheel Strategy (Third Strategy) ---

    def _wheel_scan_loop(self) -> None:
        """Scan wheel symbols for CSP or CC opportunities."""
        if not self._is_market_hours() or not self._wheel_gen:
            return

        try:
            account = self._trading_client.get_account()
        except Exception:
            logger.exception("Failed to fetch account for wheel scan")
            return

        for symbol in self._config.wheel.symbols:
            try:
                self._wheel_scan_symbol(symbol, account)
            except Exception:
                logger.exception(f"Error in wheel scan for {symbol}")

    def _wheel_scan_symbol(self, symbol: str, account) -> None:
        """Evaluate wheel strategy for a single symbol."""
        position = self._wheel_state.get_position(symbol)

        # Skip if already have an active option (selling_csp or selling_cc)
        if position.phase in ("selling_csp", "selling_cc"):
            return

        scan_time = datetime.now(timezone.utc)
        price = self._market_data.get_latest_price(symbol)
        daily_bars = self._market_data.get_daily_bars(symbol, limit=60)
        indicators = compute_indicators(daily_bars)

        # Cache bars for correlation
        self._daily_bars_cache[symbol] = daily_bars

        # IV data for conviction scoring
        since = datetime.now(timezone.utc) - timedelta(weeks=52)
        iv_records = self._db.get_iv_history(symbol, since)
        iv_history_values = [r["iv"] for r in iv_records]
        current_iv = self._get_atm_iv(symbol, price)
        iv_rank = compute_iv_rank(current_iv, iv_history_values) if iv_history_values and current_iv > 0 else None
        iv_percentile = compute_iv_percentile(current_iv, iv_history_values) if iv_history_values and current_iv > 0 else None

        # Get options chain for wheel DTE range
        wheel_chain = self._market_data.get_options_chain(
            symbol,
            min_dte=self._config.wheel.target_dte[0],
            max_dte=self._config.wheel.target_dte[1],
        )
        self._market_data.enrich_chain_with_quotes(wheel_chain)

        snapshot = MarketSnapshot(
            symbol=symbol, price=price, bars=daily_bars, options_chain=wheel_chain,
            indicators=indicators, iv_rank=iv_rank, iv_percentile=iv_percentile,
            regime=self._current_regime,
        )

        result = self._wheel_gen.evaluate(snapshot, account)

        # Process wheel signals
        for signal in result.wheel_signals:
            # Check drawdown/regime halts
            can_trade, dd_reason = self._risk_manager.drawdown_manager.can_trade()
            if not can_trade:
                logger.info(f"Wheel signal rejected (drawdown): {dd_reason}")
                result.rejections.append({
                    "strategy": "wheel", "reason": f"drawdown_halt: {dd_reason}",
                    "variables": {"symbol": symbol, "phase": signal.phase},
                })
                continue

            # Check daily limits
            daily_loss_limit = self._risk_manager._config.get("daily_loss_limit", 1000)
            if self._positions.daily_pnl <= -daily_loss_limit:
                logger.info("Wheel signal rejected: daily loss limit")
                continue

            logger.info(
                f"Wheel signal approved: {signal.symbol} {signal.phase} "
                f"@ ${signal.strike_price} exp {signal.expiration} "
                f"premium ${signal.target_premium:.2f} (conviction: {signal.conviction_score:.0f})"
            )

            order = self._executor.submit_wheel_order(signal)

            # Update wheel state
            new_phase = "selling_csp" if signal.phase == "csp" else "selling_cc"
            self._wheel_state.transition(
                symbol, new_phase,
                current_option_order_id=str(order.id),
                current_option_symbol=signal.option_contract,
                current_option_strike=signal.strike_price,
                current_option_expiration=signal.expiration,
                current_option_entry_premium=signal.target_premium,
                current_option_entry_delta=signal.delta,
                current_option_quantity=signal.quantity,
            )

            # Add premium to tracking
            pos = self._wheel_state.get_position(symbol)
            pos.total_premium_collected += signal.target_premium * 100
            self._wheel_state.save_state(symbol)

            event_name = "WheelCSPOpened" if signal.phase == "csp" else "WheelCCOpened"
            self._bus.publish(event_name, {"signal": signal, "order_id": str(order.id)})

        # Save rejections
        if result.rejections:
            self._db.save_scan_rejection({
                "symbol": symbol,
                "timestamp": scan_time,
                "market_snapshot": {"price": round(price, 2), "strategy": "wheel"},
                "rejections": result.rejections,
            })

    def _wheel_position_check(self) -> None:
        """Check active wheel options for rolling triggers or profit targets."""
        if not self._is_market_hours() or not self._wheel_state:
            return

        for position in self._wheel_state.get_active_positions():
            if position.phase not in ("selling_csp", "selling_cc"):
                continue
            if not position.current_option_symbol:
                continue

            try:
                self._check_wheel_option(position)
            except Exception:
                logger.exception(f"Error checking wheel position for {position.symbol}")

    def _check_wheel_option(self, position) -> None:
        """Check a single wheel option for roll/profit/expiry triggers."""
        from alpaca.data.requests import OptionLatestQuoteRequest

        option_sym = position.current_option_symbol
        try:
            req = OptionLatestQuoteRequest(symbol_or_symbols=[option_sym])
            quotes = self._option_client.get_option_latest_quote(req)
        except Exception:
            logger.exception(f"Failed to get quote for wheel option {option_sym}")
            return

        if option_sym not in quotes:
            return

        q = quotes[option_sym]
        current_price = (float(q.bid_price) + float(q.ask_price)) / 2
        entry_premium = position.current_option_entry_premium

        if entry_premium <= 0:
            return

        # Profit target: close at configured % of max profit
        profit_target_pct = self._config.wheel.profit_target_pct
        profit_pct = (entry_premium - current_price) / entry_premium * 100
        if profit_pct >= profit_target_pct:
            logger.info(
                f"WHEEL PROFIT TARGET: {position.symbol} {position.phase} "
                f"profit {profit_pct:.0f}% >= {profit_target_pct}%"
            )
            self._executor.submit_wheel_close_order(
                option_sym, position.current_option_quantity, current_price
            )
            # Transition back
            if position.phase == "selling_csp":
                self._wheel_state.transition(position.symbol, "idle")
            else:
                self._wheel_state.transition(position.symbol, "holding_shares")

            self._db.save_trade({
                "order_id": position.current_option_order_id,
                "strategy_mode": "wheel",
                "symbol": position.symbol,
                "spread_type": "cash_secured_put" if position.phase == "selling_csp" else "covered_call",
                "entry_premium": entry_premium,
                "close_premium": current_price,
                "pnl": (entry_premium - current_price) * 100 * position.current_option_quantity,
                "reason": "profit_target",
                "closed_at": datetime.now(timezone.utc),
            })
            self._bus.publish("WheelProfitTarget", {"symbol": position.symbol, "phase": position.phase})
            return

        # Roll trigger: delta >= 2x entry delta
        # We'd need to fetch current Greeks for this; use snapshot API
        roll_mult = self._config.wheel.roll_delta_multiplier
        entry_delta = abs(position.current_option_entry_delta)
        if entry_delta > 0:
            try:
                from alpaca.data.requests import OptionSnapshotRequest
                snap_req = OptionSnapshotRequest(symbol_or_symbols=[option_sym])
                snaps = self._option_client.get_option_snapshot(snap_req)
                if option_sym in snaps:
                    snap = snaps[option_sym]
                    current_delta = abs(float(snap.greeks.delta or 0)) if snap.greeks else 0
                    if current_delta >= entry_delta * roll_mult:
                        logger.info(
                            f"WHEEL ROLL TRIGGER: {position.symbol} delta {current_delta:.2f} "
                            f">= {entry_delta:.2f} * {roll_mult}"
                        )
                        self._executor.submit_wheel_close_order(
                            option_sym, position.current_option_quantity, current_price
                        )
                        # Clear option but stay in same logical phase for re-entry
                        if position.phase == "selling_csp":
                            self._wheel_state.transition(position.symbol, "idle")
                        else:
                            self._wheel_state.transition(position.symbol, "holding_shares")

                        self._bus.publish("WheelRolled", {
                            "symbol": position.symbol,
                            "phase": position.phase,
                            "old_delta": entry_delta,
                            "new_delta": current_delta,
                        })
                        return
            except Exception:
                logger.debug(f"Could not fetch Greeks for roll check on {option_sym}")

    def _assignment_check_loop(self) -> None:
        """Poll Alpaca for assignment events."""
        if not self._is_market_hours() or not self._assignment_detector:
            return
        try:
            self._assignment_detector.check()
        except Exception:
            logger.exception("Error in assignment detection")

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

    def _update_analytics(self) -> None:
        """Compute and cache performance analytics."""
        try:
            report = self._analytics.generate_report(days=90)
            self._db.save_performance_cache(report.to_dict())
            logger.info(
                f"ANALYTICS: {report.total_trades} trades, "
                f"win rate {report.win_rate:.0f}%, "
                f"P&L ${report.total_pnl:.2f}, "
                f"Sharpe {report.sharpe_ratio:.2f}"
            )
        except Exception:
            logger.exception("Failed to update analytics")

    def _heartbeat(self) -> None:
        try:
            heartbeat_data = {
                "timestamp": datetime.now(timezone.utc),
                "market_hours": self._is_market_hours(),
            }
            # Include regime in heartbeat for dashboard
            if self._current_regime:
                heartbeat_data["regime"] = self._current_regime.to_dict()
            # Include drawdown state
            dd_state = self._risk_manager.drawdown_manager.state
            heartbeat_data["drawdown"] = dd_state.to_dict()

            self._db.db["heartbeat"].update_one(
                {"_id": "bot"},
                {"$set": heartbeat_data},
                upsert=True,
            )
        except Exception:
            logger.exception("Failed to write heartbeat")

    def _daily_reset(self) -> None:
        self._positions.reset_daily()
        self._risk_manager.drawdown_manager.reset_daily()
        self._daily_bars_cache = {}
        # Compute fresh analytics at start of day
        self._update_analytics()
        logger.info("Daily reset complete")

    def _propagate_config(self) -> None:
        """Push updated config to all sub-components."""
        c = self._config
        self._swing_gen._config = {
            "target_dte": c.swing.target_dte, "short_strike_delta": c.swing.short_strike_delta,
            "spread_width": c.swing.spread_width, "min_premium": c.swing.min_premium,
            "iv_rank_threshold": c.swing.iv_rank_threshold, "profit_target_pct": c.swing.profit_target_pct,
        }
        self._exhaustion_gen._config = {
            "enabled": c.exhaustion.enabled, "target_dte": c.exhaustion.target_dte,
            "spread_width": c.exhaustion.spread_width, "min_premium": c.exhaustion.min_premium,
            "profit_target_pct": c.exhaustion.profit_target_pct,
            "stop_loss_multiplier": c.exhaustion.stop_loss_multiplier,
            "time_window_start": c.exhaustion.time_window_start,
            "rsi_overbought": c.exhaustion.rsi_overbought, "rsi_oversold": c.exhaustion.rsi_oversold,
            "intraday_timeframe": c.exhaustion.intraday_timeframe,
            "min_signals_required": c.exhaustion.min_signals_required,
            "min_move_from_open_pct": c.exhaustion.min_move_from_open_pct,
            "strong_move_pct": c.exhaustion.strong_move_pct,
            "close_by_eod": c.exhaustion.close_by_eod,
        }
        self._risk_manager._config = {
            "max_concurrent_spreads": c.risk.max_concurrent_spreads,
            "max_risk_per_trade_pct": c.risk.max_risk_per_trade_pct,
            "max_buying_power_usage_pct": c.risk.max_buying_power_usage_pct,
            "stop_loss_multiplier": c.risk.stop_loss_multiplier,
            "roll_delta_threshold": c.risk.roll_delta_threshold, "dte_exit": c.risk.dte_exit,
            "daily_loss_limit": c.risk.daily_loss_limit, "daily_income_target": c.risk.daily_income_target,
            "max_same_direction_per_symbol": c.risk.max_same_direction_per_symbol,
            "max_portfolio_delta_per_symbol": c.risk.max_portfolio_delta_per_symbol,
            "max_correlated_same_direction": c.risk.max_correlated_same_direction,
            "max_portfolio_vega": c.risk.max_portfolio_vega,
            "max_contracts_per_trade": c.risk.max_contracts_per_trade,
        }
        # Wheel strategy config
        if self._wheel_gen:
            self._wheel_gen._config = {
                "enabled": c.wheel.enabled,
                "symbols": c.wheel.symbols,
                "target_dte": c.wheel.target_dte,
                "csp_delta_range": c.wheel.csp_delta_range,
                "cc_delta_range": c.wheel.cc_delta_range,
                "min_open_interest": c.wheel.min_open_interest,
                "csp_strike_range_pct": c.wheel.csp_strike_range_pct,
                "cc_above_bollinger": c.wheel.cc_above_bollinger,
                "max_buying_power_pct": c.wheel.max_buying_power_pct,
                "roll_delta_multiplier": c.wheel.roll_delta_multiplier,
                "roll_profit_pct": c.wheel.roll_profit_pct,
                "profit_target_pct": c.wheel.profit_target_pct,
                "max_positions": c.wheel.max_positions,
            }

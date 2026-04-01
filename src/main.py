import logging
import sys

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.trading.client import TradingClient

from src.config import load_config
from src.db.mongo import MongoStore
from src.event_bus import EventBus
from src.execution.executor import OrderExecutor
from src.market_data.client import MarketDataClient
from src.notifications.email_notifier import EmailNotifier
from src.notifications.sms import SmsNotifier
from src.positions.manager import PositionManager
from src.risk.manager import RiskManager
from src.scheduler import TradingScheduler
from src.signals.exhaustion import ExhaustionSignalGenerator
from src.signals.swing import SwingSignalGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("auto-trader.log")],
)
logger = logging.getLogger(__name__)


def main():
    config = load_config()
    logger.info("Config loaded")

    event_bus = EventBus()
    db = MongoStore(config.mongodb_uri, config.mongodb_db_name)
    config = load_config(db=db)

    trading_client = TradingClient(config.alpaca_api_key, config.alpaca_api_secret, paper=config.alpaca_paper)
    stock_client = StockHistoricalDataClient(config.alpaca_api_key, config.alpaca_api_secret)
    option_client = OptionHistoricalDataClient(config.alpaca_api_key, config.alpaca_api_secret)

    market_data = MarketDataClient(
        trading_client=trading_client, stock_client=stock_client,
        option_client=option_client, db=db, symbols=config.symbols,
    )

    swing_config = {
        "target_dte": config.swing.target_dte, "short_strike_delta": config.swing.short_strike_delta,
        "spread_width": config.swing.spread_width, "min_premium": config.swing.min_premium,
        "iv_rank_threshold": config.swing.iv_rank_threshold, "profit_target_pct": config.swing.profit_target_pct,
    }
    swing_gen = SwingSignalGenerator(swing_config, event_bus)

    exhaustion_config = {
        "enabled": config.exhaustion.enabled, "target_dte": config.exhaustion.target_dte,
        "spread_width": config.exhaustion.spread_width, "min_premium": config.exhaustion.min_premium,
        "profit_target_pct": config.exhaustion.profit_target_pct,
        "stop_loss_multiplier": config.exhaustion.stop_loss_multiplier,
        "time_window_start": config.exhaustion.time_window_start,
        "rsi_overbought": config.exhaustion.rsi_overbought, "rsi_oversold": config.exhaustion.rsi_oversold,
        "intraday_timeframe": config.exhaustion.intraday_timeframe,
        "min_signals_required": config.exhaustion.min_signals_required,
        "close_by_eod": config.exhaustion.close_by_eod,
    }
    exhaustion_gen = ExhaustionSignalGenerator(exhaustion_config, event_bus)

    risk_config = {
        "max_concurrent_spreads": config.risk.max_concurrent_spreads,
        "max_risk_per_trade_pct": config.risk.max_risk_per_trade_pct,
        "max_buying_power_usage_pct": config.risk.max_buying_power_usage_pct,
        "stop_loss_multiplier": config.risk.stop_loss_multiplier,
        "roll_delta_threshold": config.risk.roll_delta_threshold, "dte_exit": config.risk.dte_exit,
        "daily_loss_limit": config.risk.daily_loss_limit, "daily_income_target": config.risk.daily_income_target,
        "max_same_direction_per_symbol": config.risk.max_same_direction_per_symbol,
        "max_portfolio_delta_per_symbol": config.risk.max_portfolio_delta_per_symbol,
    }
    risk_manager = RiskManager(risk_config, event_bus)

    exec_config = {
        "price_adjustment_interval": config.execution.price_adjustment_interval,
        "price_adjustment_step": config.execution.price_adjustment_step,
        "fill_timeout": config.execution.fill_timeout,
    }
    executor = OrderExecutor(trading_client, db, exec_config, event_bus)
    position_manager = PositionManager(db, event_bus)

    if config.notifications.sms_enabled and config.twilio_account_sid:
        sms = SmsNotifier(config.twilio_account_sid, config.twilio_auth_token, config.twilio_from_number, config.twilio_to_number)
        event_bus.subscribe("OrderFilled", lambda d: sms.notify_fill(d["signal"].symbol, d["signal"].spread_type, d.get("filled_price", 0)))
        event_bus.subscribe("StopLossHit", lambda d: sms.notify_stop_loss(d["position"].symbol, d["position"].spread_type, d["position"].unrealized_pnl))
        event_bus.subscribe("CircuitBreakerTriggered", lambda d: sms.notify_circuit_breaker(d.get("daily_pnl", 0)))

    scheduler = TradingScheduler(
        config=config, event_bus=event_bus, market_data=market_data,
        swing_gen=swing_gen, exhaustion_gen=exhaustion_gen,
        risk_manager=risk_manager, executor=executor,
        position_manager=position_manager, trading_client=trading_client,
        option_client=option_client, db=db,
    )

    logger.info("Auto-Trader starting...")
    logger.info(f"Symbols: {config.symbols}")
    logger.info(f"Paper trading: {config.alpaca_paper}")
    logger.info(f"Swing DTE: {config.swing.target_dte}")
    logger.info(f"Exhaustion enabled: {config.exhaustion.enabled}")
    logger.info(f"Daily target: ${config.risk.daily_income_target}")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        scheduler.stop()


if __name__ == "__main__":
    main()

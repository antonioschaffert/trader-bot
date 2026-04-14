import logging
import signal
import sys

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient

from src.accounts.manager import AccountManager
from src.config import load_config
from src.db.mongo import MongoStore
from src.market_data.client import MarketDataClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("auto-trader.log")],
)
logger = logging.getLogger(__name__)

# Global reference for API access
_account_manager: AccountManager | None = None


def get_account_manager() -> AccountManager | None:
    return _account_manager


def main():
    global _account_manager

    config = load_config()
    logger.info("Config loaded")

    db = MongoStore(config.mongodb_uri, config.mongodb_db_name)
    config = load_config(db=db)

    # Shared market data clients (same data for all accounts)
    # Use env var credentials for market data (or first account's credentials)
    stock_client = StockHistoricalDataClient(config.alpaca_api_key, config.alpaca_api_secret)
    option_client = OptionHistoricalDataClient(config.alpaca_api_key, config.alpaca_api_secret)

    # MarketDataClient needs a trading_client for some calls - create a lightweight one
    from alpaca.trading.client import TradingClient
    data_trading_client = TradingClient(config.alpaca_api_key, config.alpaca_api_secret, paper=config.alpaca_paper)

    market_data = MarketDataClient(
        trading_client=data_trading_client, stock_client=stock_client,
        option_client=option_client, db=db, symbols=config.symbols,
    )

    # Account manager orchestrates all accounts
    account_manager = AccountManager(db, market_data, option_client, config)
    _account_manager = account_manager

    logger.info("Auto-Trader starting (Enhanced v3 - Multi-Account)...")
    logger.info(f"Global symbols: {config.symbols}")
    logger.info(f"Regime detection: {config.regime.enabled}")
    logger.info(f"Drawdown halt at: {config.risk.drawdown.drawdown_halt_pct}%")

    # Load and start all enabled accounts
    accounts = account_manager.load_accounts()
    logger.info(f"Found {len(accounts)} account(s) in database")
    for acct in accounts:
        status = "ENABLED" if acct.get("enabled") else "disabled"
        logger.info(
            f"  Account '{acct.get('name', acct['account_id'])}' "
            f"[{'paper' if acct.get('is_paper') else 'LIVE'}] - {status} "
            f"strategies={acct.get('strategies', {})}"
        )

    account_manager.start_all()

    running = account_manager.get_running_accounts()
    logger.info(f"{len(running)} account(s) running: {running}")

    # Keep main thread alive, handle graceful shutdown
    def shutdown_handler(signum, frame):
        logger.info("Shutdown signal received...")
        account_manager.stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Block main thread (daemon threads keep running)
    try:
        signal.pause()
    except AttributeError:
        # Windows doesn't have signal.pause
        import time
        while True:
            time.sleep(60)


if __name__ == "__main__":
    main()

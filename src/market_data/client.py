import logging
from datetime import date, datetime, timedelta, timezone

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import (
    StockBarsRequest,
    StockLatestQuoteRequest,
    OptionChainRequest,
    OptionLatestQuoteRequest,
    OptionSnapshotRequest,
)
from alpaca.data.enums import DataFeed
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOptionContractsRequest
from alpaca.trading.enums import AssetStatus, ContractType

from src.db.mongo import MongoStore
from src.market_data.models import Bar, OptionContract, OptionsChain

logger = logging.getLogger(__name__)


class MarketDataClient:
    def __init__(
        self,
        trading_client: TradingClient,
        stock_client: StockHistoricalDataClient,
        option_client: OptionHistoricalDataClient,
        db: MongoStore,
        symbols: list[str],
    ):
        self._trading = trading_client
        self._stock = stock_client
        self._option = option_client
        self._db = db
        self._symbols = symbols

    def get_options_chain(
        self, symbol: str, min_dte: int, max_dte: int
    ) -> OptionsChain:
        today = date.today()
        min_exp = today + timedelta(days=min_dte)
        max_exp = today + timedelta(days=max_dte)

        calls = []
        puts = []
        for ct in (ContractType.CALL, ContractType.PUT):
            req = GetOptionContractsRequest(
                underlying_symbols=[symbol],
                status=AssetStatus.ACTIVE,
                type=ct,
                expiration_date_gte=min_exp,
                expiration_date_lte=max_exp,
            )
            response = self._trading.get_option_contracts(req)
            for c in response.option_contracts or []:
                contract = OptionContract(
                    symbol=c.symbol,
                    underlying_symbol=c.underlying_symbol,
                    expiration_date=c.expiration_date,
                    strike_price=float(c.strike_price),
                    contract_type=str(c.type),
                    open_interest=int(c.open_interest or 0),
                )
                if ct == ContractType.CALL:
                    calls.append(contract)
                else:
                    puts.append(contract)

        chain = OptionsChain(
            underlying_symbol=symbol, calls=calls, puts=puts
        )
        return chain

    def enrich_chain_with_quotes(self, chain: OptionsChain) -> None:
        """Enrich option contracts with quotes, IV, and Greeks via snapshots."""
        all_symbols = [c.symbol for c in chain.calls + chain.puts]
        if not all_symbols:
            return

        contract_map = {c.symbol: c for c in chain.calls + chain.puts}

        for batch_start in range(0, len(all_symbols), 100):
            batch = all_symbols[batch_start : batch_start + 100]
            try:
                req = OptionSnapshotRequest(symbol_or_symbols=batch)
                snapshots = self._option.get_option_snapshot(req)
                for sym, snap in snapshots.items():
                    if sym not in contract_map:
                        continue
                    c = contract_map[sym]
                    if snap.latest_quote:
                        c.bid_price = float(snap.latest_quote.bid_price or 0)
                        c.ask_price = float(snap.latest_quote.ask_price or 0)
                        c.mid_price = (c.bid_price + c.ask_price) / 2
                    if snap.implied_volatility is not None:
                        c.implied_volatility = float(snap.implied_volatility)
                    if snap.greeks:
                        c.delta = float(snap.greeks.delta or 0)
                        c.gamma = float(snap.greeks.gamma or 0)
                        c.theta = float(snap.greeks.theta or 0)
                        c.vega = float(snap.greeks.vega or 0)
            except Exception:
                logger.warning("Snapshot API failed, falling back to quotes")
                req = OptionLatestQuoteRequest(symbol_or_symbols=batch)
                quotes = self._option.get_option_latest_quote(req)
                for sym, quote in quotes.items():
                    if sym in contract_map:
                        contract_map[sym].bid_price = float(quote.bid_price or 0)
                        contract_map[sym].ask_price = float(quote.ask_price or 0)
                        contract_map[sym].mid_price = (
                            contract_map[sym].bid_price + contract_map[sym].ask_price
                        ) / 2

    def get_daily_bars(self, symbol: str, limit: int = 60) -> list[Bar]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=limit * 2)
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            limit=limit,
            feed=DataFeed.SIP,
        )
        response = self._stock.get_stock_bars(req)
        raw_bars = response.data.get(symbol, [])

        return [
            Bar(
                timestamp=b.timestamp,
                open=float(b.open),
                high=float(b.high),
                low=float(b.low),
                close=float(b.close),
                volume=int(b.volume),
                vwap=float(getattr(b, "vwap", 0) or 0),
            )
            for b in raw_bars
        ]

    def get_intraday_bars(
        self, symbol: str, timeframe_minutes: int = 5, limit: int = 78
    ) -> list[Bar]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=8)
        tf = TimeFrame.Minute if timeframe_minutes == 1 else TimeFrame(timeframe_minutes, TimeFrameUnit.Minute)
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start,
            end=end,
            limit=limit,
            feed=DataFeed.SIP,
        )
        response = self._stock.get_stock_bars(req)
        raw_bars = response.data.get(symbol, [])

        return [
            Bar(
                timestamp=b.timestamp,
                open=float(b.open),
                high=float(b.high),
                low=float(b.low),
                close=float(b.close),
                volume=int(b.volume),
                vwap=float(getattr(b, "vwap", 0) or 0),
            )
            for b in raw_bars
        ]

    def get_latest_price(self, symbol: str) -> float:
        req = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=DataFeed.SIP)
        quotes = self._stock.get_stock_latest_quote(req)
        quote = quotes[symbol]
        return (float(quote.ask_price) + float(quote.bid_price)) / 2

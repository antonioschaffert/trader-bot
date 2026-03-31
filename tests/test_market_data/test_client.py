from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.market_data.client import MarketDataClient
from src.market_data.models import OptionsChain, OptionContract, Bar


@pytest.fixture
def mock_trading_client():
    return MagicMock()


@pytest.fixture
def mock_stock_client():
    return MagicMock()


@pytest.fixture
def mock_option_client():
    return MagicMock()


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_trading_client, mock_stock_client, mock_option_client, mock_db):
    return MarketDataClient(
        trading_client=mock_trading_client,
        stock_client=mock_stock_client,
        option_client=mock_option_client,
        db=mock_db,
        symbols=["SPY"],
    )


def test_get_options_chain_returns_chain(client, mock_trading_client):
    mock_contract = MagicMock()
    mock_contract.symbol = "SPY260410P00500000"
    mock_contract.underlying_symbol = "SPY"
    mock_contract.expiration_date = date(2026, 4, 10)
    mock_contract.strike_price = 500.0
    mock_contract.type = "put"
    mock_contract.open_interest = 1000
    mock_contract.close_price = 2.50

    mock_response = MagicMock()
    mock_response.option_contracts = [mock_contract]
    mock_trading_client.get_option_contracts.return_value = mock_response

    chain = client.get_options_chain("SPY", min_dte=1, max_dte=10)
    assert isinstance(chain, OptionsChain)
    assert chain.underlying_symbol == "SPY"


def test_get_daily_bars_returns_bars(client, mock_stock_client):
    mock_bar = MagicMock()
    mock_bar.timestamp = datetime(2026, 3, 30, tzinfo=timezone.utc)
    mock_bar.open = 500.0
    mock_bar.high = 505.0
    mock_bar.low = 498.0
    mock_bar.close = 503.0
    mock_bar.volume = 1000000
    mock_bar.vwap = 501.5

    mock_stock_client.get_stock_bars.return_value = {"SPY": [mock_bar]}

    bars = client.get_daily_bars("SPY", limit=50)
    assert len(bars) == 1
    assert isinstance(bars[0], Bar)
    assert bars[0].close == 503.0


def test_get_latest_price(client, mock_stock_client):
    mock_quote = MagicMock()
    mock_quote.ask_price = 500.50
    mock_quote.bid_price = 500.40
    mock_stock_client.get_stock_latest_quote.return_value = {"SPY": mock_quote}

    price = client.get_latest_price("SPY")
    assert price == pytest.approx(500.45, abs=0.01)

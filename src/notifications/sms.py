import logging

from twilio.rest import Client

logger = logging.getLogger(__name__)


class SmsNotifier:
    def __init__(self, account_sid: str, auth_token: str, from_number: str, to_number: str):
        self._client = Client(account_sid, auth_token)
        self._from = from_number
        self._to = to_number

    def send(self, message: str) -> None:
        try:
            self._client.messages.create(body=message, from_=self._from, to=self._to)
        except Exception:
            logger.exception("Failed to send SMS")

    def notify_fill(self, symbol: str, spread_type: str, premium: float) -> None:
        self.send(f"FILLED: {symbol} {spread_type} for ${premium:.2f} credit")

    def notify_stop_loss(self, symbol: str, spread_type: str, pnl: float) -> None:
        self.send(f"STOP LOSS: {symbol} {spread_type} closed at ${pnl:.2f}")

    def notify_roll(self, symbol: str, spread_type: str) -> None:
        self.send(f"ROLLED: {symbol} {spread_type} to next expiration")

    def notify_circuit_breaker(self, daily_pnl: float) -> None:
        self.send(f"CIRCUIT BREAKER: Trading halted. Daily P&L: ${daily_pnl:.2f}")

    def notify_error(self, error: str) -> None:
        self.send(f"BOT ERROR: {error}")

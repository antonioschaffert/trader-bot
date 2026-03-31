import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(self, host: str, port: int, username: str, password: str, to_email: str):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._to = to_email

    def _send(self, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._username
        msg["To"] = self._to
        msg.set_content(body)
        try:
            with smtplib.SMTP(self._host, self._port) as server:
                server.starttls()
                server.login(self._username, self._password)
                server.send_message(msg)
        except Exception:
            logger.exception("Failed to send email")

    def send_daily_summary(self, daily_pnl: float, open_positions: int, closed_trades: int, win_rate: float, target: int) -> None:
        progress = (daily_pnl / target * 100) if target > 0 else 0
        body = (
            f"Auto-Trader Daily Summary\n"
            f"{'=' * 30}\n\n"
            f"Daily P&L: ${daily_pnl:.2f} ({progress:.0f}% of ${target} target)\n"
            f"Open Positions: {open_positions}\n"
            f"Trades Closed Today: {closed_trades}\n"
            f"Win Rate: {win_rate:.1f}%\n"
        )
        self._send(f"Auto-Trader: ${daily_pnl:.2f} P&L", body)

    def send_weekly_recap(self, weekly_pnl: float, total_trades: int, win_rate: float) -> None:
        body = (
            f"Auto-Trader Weekly Recap\n"
            f"{'=' * 30}\n\n"
            f"Weekly P&L: ${weekly_pnl:.2f}\n"
            f"Total Trades: {total_trades}\n"
            f"Win Rate: {win_rate:.1f}%\n"
        )
        self._send(f"Auto-Trader Weekly: ${weekly_pnl:.2f}", body)

from unittest.mock import MagicMock, patch

from src.notifications.email_notifier import EmailNotifier


@patch("src.notifications.email_notifier.smtplib.SMTP")
def test_send_daily_summary(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
    notifier = EmailNotifier(host="smtp.test.com", port=587, username="user@test.com", password="pass", to_email="dest@test.com")
    notifier.send_daily_summary(daily_pnl=250.0, open_positions=3, closed_trades=5, win_rate=80.0, target=500)
    mock_smtp.send_message.assert_called_once()


@patch("src.notifications.email_notifier.smtplib.SMTP")
def test_daily_summary_contains_pnl(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
    notifier = EmailNotifier("smtp.test.com", 587, "u@t.com", "p", "d@t.com")
    notifier.send_daily_summary(daily_pnl=250.0, open_positions=3, closed_trades=5, win_rate=80.0, target=500)
    msg = mock_smtp.send_message.call_args[0][0]
    body = msg.get_content()
    assert "250.00" in body

from unittest.mock import MagicMock, patch

from src.notifications.sms import SmsNotifier


@patch("src.notifications.sms.Client")
def test_send_sms(mock_twilio_cls):
    mock_client = MagicMock()
    mock_twilio_cls.return_value = mock_client
    notifier = SmsNotifier(account_sid="sid", auth_token="token", from_number="+1111", to_number="+2222")
    notifier.send("Test message")
    mock_client.messages.create.assert_called_once_with(body="Test message", from_="+1111", to="+2222")


@patch("src.notifications.sms.Client")
def test_notify_fill(mock_twilio_cls):
    mock_client = MagicMock()
    mock_twilio_cls.return_value = mock_client
    notifier = SmsNotifier("sid", "token", "+1111", "+2222")
    notifier.notify_fill("SPY", "put_spread", 1.50)
    call_args = mock_client.messages.create.call_args
    assert "SPY" in call_args[1]["body"]
    assert "put_spread" in call_args[1]["body"]


@patch("src.notifications.sms.Client")
def test_notify_stop_loss(mock_twilio_cls):
    mock_client = MagicMock()
    mock_twilio_cls.return_value = mock_client
    notifier = SmsNotifier("sid", "token", "+1111", "+2222")
    notifier.notify_stop_loss("QQQ", "call_spread", -150.0)
    call_args = mock_client.messages.create.call_args
    assert "STOP LOSS" in call_args[1]["body"].upper()

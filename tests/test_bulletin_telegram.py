"""Test cho send_telegram_report (scripts/run_morning.py) — không gọi mạng
thật, chỉ mock notifications.telegram.send_message."""
from unittest.mock import patch

from run_morning import send_telegram_report


def test_skips_silently_when_not_configured(monkeypatch):
    monkeypatch.setattr("common.env.get_env", lambda key, default=None: None)
    with patch("notifications.telegram.send_message") as mock_send:
        send_telegram_report("nội dung bản tin")
    mock_send.assert_not_called()


def test_sends_when_token_and_chat_id_present(monkeypatch):
    values = {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "123"}
    monkeypatch.setattr("common.env.get_env", lambda key, default=None: values.get(key, default))
    with patch("notifications.telegram.send_message", return_value={"message_id": 42}) as mock_send:
        send_telegram_report("nội dung bản tin")
    mock_send.assert_called_once_with("tok", "123", "nội dung bản tin")


def test_failure_is_caught_and_does_not_raise(monkeypatch):
    from notifications.telegram import TelegramError

    values = {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "123"}
    monkeypatch.setattr("common.env.get_env", lambda key, default=None: values.get(key, default))
    with patch("notifications.telegram.send_message", side_effect=TelegramError("boom")):
        send_telegram_report("nội dung bản tin")  # không raise ra ngoài

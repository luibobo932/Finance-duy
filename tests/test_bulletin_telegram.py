"""Test cho send_telegram_report (scripts/run_morning.py) — không gọi mạng
thật, chỉ mock notifications.telegram.send_message."""
from unittest.mock import patch

from run_morning import send_telegram_report


def test_skips_silently_when_not_configured(monkeypatch):
    monkeypatch.setattr("common.env.get_env", lambda key, default=None: None)
    with patch("notifications.telegram.send_message") as mock_send:
        send_telegram_report("nội dung bản tin")
    mock_send.assert_not_called()


def test_sends_html_formatted_when_configured(monkeypatch):
    values = {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "123"}
    monkeypatch.setattr("common.env.get_env", lambda key, default=None: values.get(key, default))
    with patch("notifications.telegram.send_message", return_value={"message_id": 42}) as mock_send:
        send_telegram_report("## VÀNG\n**GIỮ**")
    mock_send.assert_called_once_with("tok", "123", "<b>🥇 VÀNG</b>\n<b>GIỮ</b>", parse_mode="HTML")


def test_falls_back_to_plain_text_when_html_rejected(monkeypatch):
    from notifications.telegram import TelegramError

    values = {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "123"}
    monkeypatch.setattr("common.env.get_env", lambda key, default=None: values.get(key, default))
    with patch("notifications.telegram.send_message",
               side_effect=[TelegramError("can't parse entities"), {"message_id": 43}]) as mock_send:
        send_telegram_report("nội dung bản tin")
    assert mock_send.call_count == 2
    # Lần 2 (fallback) phải là text thô, không parse_mode
    assert mock_send.call_args_list[1].args == ("tok", "123", "nội dung bản tin")


def test_failure_is_caught_and_does_not_raise(monkeypatch):
    from notifications.telegram import TelegramError

    values = {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "123"}
    monkeypatch.setattr("common.env.get_env", lambda key, default=None: values.get(key, default))
    with patch("notifications.telegram.send_message", side_effect=TelegramError("boom")):
        send_telegram_report("nội dung bản tin")  # không raise ra ngoài

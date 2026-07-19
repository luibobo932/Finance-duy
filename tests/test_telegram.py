"""Test cho notifications/telegram.py và common/env.py — chỉ phần logic
thuần túy (không gọi mạng thật, vì api.telegram.org bị chặn network policy
trong môi trường này)."""
from common.env import load_env
from notifications.telegram import find_latest_chat_id


def test_find_latest_chat_id_from_start_message():
    updates = [
        {"update_id": 1, "message": {"chat": {"id": 123456789}, "text": "/start"}},
    ]
    assert find_latest_chat_id(updates) == 123456789


def test_find_latest_chat_id_picks_most_recent():
    updates = [
        {"update_id": 1, "message": {"chat": {"id": 111}, "text": "/start"}},
        {"update_id": 2, "message": {"chat": {"id": 222}, "text": "hello"}},
    ]
    assert find_latest_chat_id(updates) == 222


def test_find_latest_chat_id_empty_returns_none():
    assert find_latest_chat_id([]) is None


def test_find_latest_chat_id_ignores_updates_without_message():
    updates = [{"update_id": 1, "my_chat_member": {}}]
    assert find_latest_chat_id(updates) is None


def test_find_latest_chat_id_handles_channel_post():
    updates = [{"update_id": 1, "channel_post": {"chat": {"id": -1001234}}}]
    assert find_latest_chat_id(updates) == -1001234


def test_load_env_parses_key_value(tmp_path):
    p = tmp_path / ".env"
    p.write_text("TELEGRAM_BOT_TOKEN=abc123\nTELEGRAM_CHAT_ID=987\n# comment\n\n", encoding="utf-8")
    values = load_env(p)
    assert values["TELEGRAM_BOT_TOKEN"] == "abc123"
    assert values["TELEGRAM_CHAT_ID"] == "987"


def test_load_env_missing_file_returns_empty(tmp_path):
    assert load_env(tmp_path / "nope.env") == {}


def test_load_env_ignores_comments_and_blank_lines(tmp_path):
    p = tmp_path / ".env"
    p.write_text("# header\n\nKEY=value\n", encoding="utf-8")
    assert load_env(p) == {"KEY": "value"}

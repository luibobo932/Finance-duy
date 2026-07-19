#!/usr/bin/env python3
"""Gửi bản tin qua Telegram bot @Tintucstock_bot.

Yêu cầu:
  1. .env có TELEGRAM_BOT_TOKEN (xem .env.example)
  2. Bạn đã bấm /start với bot ít nhất 1 lần (để bot có quyền nhắn cho bạn)
  3. Network policy của môi trường cho phép api.telegram.org — MẶC ĐỊNH
     BỊ CHẶN trong môi trường sandbox này (đã xác nhận qua log proxy:
     "gateway answered 403 to CONNECT... host: api.telegram.org:443").
     Cần bật domain này trong cấu hình Network policy của environment
     trên claude.ai trước khi các lệnh dưới đây chạy được.

Cách dùng:
  python3 notifications/telegram.py whoami          # lấy chat_id từ /start, lưu vào .env
  python3 notifications/telegram.py send "nội dung"  # gửi tin nhắn
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.env import ENV_PATH, get_env  # noqa: E402

API_BASE = "https://api.telegram.org/bot{token}/{method}"
NETWORK_HINT = (
    "Không gọi được api.telegram.org. Trong môi trường Claude Code sandbox, domain này "
    "thường bị chặn theo network policy mặc định — vào cấu hình Network policy của "
    "environment trên claude.ai và thêm 'api.telegram.org' vào danh sách cho phép, "
    "sau đó thử lại."
)


class TelegramError(RuntimeError):
    pass


def _call(token: str, method: str, params: dict | None = None) -> dict:
    url = API_BASE.format(token=token, method=method)
    data = urllib.parse.urlencode(params or {}).encode()
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
    except urllib.error.URLError as e:
        raise TelegramError(f"{NETWORK_HINT}\nChi tiết lỗi: {e}") from e
    if not body.get("ok"):
        raise TelegramError(f"Telegram API báo lỗi: {body}")
    return body["result"]


def get_updates(token: str) -> list[dict]:
    return _call(token, "getUpdates")


def find_latest_chat_id(updates: list[dict]) -> int | None:
    for u in reversed(updates):
        msg = u.get("message") or u.get("channel_post")
        if msg and msg.get("chat", {}).get("id") is not None:
            return msg["chat"]["id"]
    return None


def send_message(token: str, chat_id: int | str, text: str, parse_mode: str = "Markdown") -> dict:
    # Telegram giới hạn 4096 ký tự/tin nhắn — cắt bớt an toàn nếu vượt
    if len(text) > 4000:
        text = text[:3990] + "\n\n…(cắt bớt, xem đầy đủ trong bản tin gốc)"
    return _call(token, "sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": parse_mode})


def _save_chat_id(chat_id: int) -> None:
    lines = []
    found = False
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.startswith("TELEGRAM_CHAT_ID="):
                lines.append(f"TELEGRAM_CHAT_ID={chat_id}")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"TELEGRAM_CHAT_ID={chat_id}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ENV_PATH.chmod(0o600)


def cmd_whoami() -> None:
    token = get_env("TELEGRAM_BOT_TOKEN")
    if not token:
        sys.exit("Chưa có TELEGRAM_BOT_TOKEN trong .env")
    try:
        updates = get_updates(token)
    except TelegramError as e:
        sys.exit(str(e))
    if not updates:
        sys.exit("Chưa có tin nhắn nào tới bot. Mở Telegram, bấm /start với bot rồi thử lại.")
    chat_id = find_latest_chat_id(updates)
    if chat_id is None:
        sys.exit("Không tìm thấy chat_id trong updates.")
    _save_chat_id(chat_id)
    print(f"Đã lưu TELEGRAM_CHAT_ID={chat_id} vào .env")


def cmd_send(text: str) -> None:
    token = get_env("TELEGRAM_BOT_TOKEN")
    chat_id = get_env("TELEGRAM_CHAT_ID")
    if not token:
        sys.exit("Chưa có TELEGRAM_BOT_TOKEN trong .env")
    if not chat_id:
        sys.exit("Chưa có TELEGRAM_CHAT_ID trong .env — chạy 'whoami' trước.")
    try:
        result = send_message(token, chat_id, text)
    except TelegramError as e:
        sys.exit(str(e))
    print(f"Đã gửi tin nhắn (message_id={result.get('message_id')})")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "whoami":
        cmd_whoami()
    elif sys.argv[1] == "send" and len(sys.argv) > 2:
        cmd_send(sys.argv[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()

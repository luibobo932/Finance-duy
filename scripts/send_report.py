#!/usr/bin/env python3
"""Gửi một BÁO CÁO (không phải bản tin định kỳ) qua Telegram.

    python3 scripts/send_report.py plan        # kế hoạch: sức mua + mục tiêu 10 tỷ
    python3 scripts/send_report.py morning     # bản tin sáng
    python3 scripts/send_report.py evening     # bản tin chiều
    python3 scripts/send_report.py --preview plan   # in ra màn hình, KHÔNG gửi

`--preview` chạy được ở mọi nơi. Việc gửi cần `api.telegram.org` mở — trong
sandbox claude.ai domain này bị network policy chặn (xác nhận: CONNECT tunnel
403), nên lệnh gửi phải chạy trên laptop, nơi automation buổi chiều vẫn gửi
được hằng ngày.

Cần trong `.env`:
    TELEGRAM_BOT_TOKEN=...   (đã có)
    TELEGRAM_CHAT_ID=...     (lấy bằng: python3 notifications/telegram.py whoami
                              sau khi bấm /start với bot)
"""
from __future__ import annotations

import io
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

REPORTS = {
    "plan": ("Kế hoạch tài sản", "plan"),
    "morning": ("Bản tin sáng", "run_morning"),
    "evening": ("Bản tin chiều", "run_evening"),
}


def render(name: str) -> str:
    """Chạy script báo cáo và thu lại phần in ra.

    Gọi qua subprocess thay vì import + redirect: các orchestrator có side
    effect (sinh dashboard, ghi quyết định) và một số tự gửi Telegram — chạy
    tách tiến trình để việc "xem trước" không vô tình kích hoạt những thứ đó
    hai lần.
    """
    _title, module = REPORTS[name]
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / f"{module}.py")],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if proc.returncode != 0:
        raise SystemExit(f"Không dựng được báo cáo '{name}':\n{proc.stderr}")
    return proc.stdout.strip()


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    preview = "--preview" in sys.argv[1:]
    name = args[0] if args else "plan"
    if name not in REPORTS:
        raise SystemExit(f"Báo cáo không hợp lệ: {name}. Chọn: {', '.join(REPORTS)}")

    from notifications.formatting import split_for_telegram, to_telegram_html

    title, _ = REPORTS[name]
    body = render(name)
    html_text = to_telegram_html(f"# {title}\n\n{body}")
    parts = split_for_telegram(html_text)

    if preview:
        print(f"[XEM TRƯỚC] {title} — {len(html_text)} ký tự → {len(parts)} tin nhắn\n")
        for i, p in enumerate(parts, 1):
            print(f"───── phần {i}/{len(parts)} ({len(p)} ký tự) " + "─" * 20)
            print(p)
            print()
        return

    from common.env import get_env
    from notifications.telegram import TelegramError, send_message_parts

    token, chat_id = get_env("TELEGRAM_BOT_TOKEN"), get_env("TELEGRAM_CHAT_ID")
    missing = [k for k, v in (("TELEGRAM_BOT_TOKEN", token), ("TELEGRAM_CHAT_ID", chat_id)) if not v]
    if missing:
        raise SystemExit(
            f"Thiếu trong .env: {', '.join(missing)}.\n"
            "Lấy chat_id: bấm /start với bot rồi chạy "
            "`python3 notifications/telegram.py whoami` (tự ghi vào .env).\n"
            "Muốn xem nội dung mà chưa gửi: thêm --preview."
        )
    try:
        results = send_message_parts(token, chat_id, html_text, parse_mode="HTML")
    except TelegramError as e:
        # Fallback text thô: báo cáo tới nơi quan trọng hơn định dạng đẹp.
        print(f"⚠️  Gửi bản HTML thất bại ({e}) — gửi lại dạng text thô.")
        results = send_message_parts(token, chat_id, f"{title}\n\n{body}")
    print(f"Đã gửi '{title}' — {len(results)} tin nhắn "
          f"(message_id: {', '.join(str(r.get('message_id')) for r in results)})")


if __name__ == "__main__":
    main()

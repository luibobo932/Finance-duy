"""Định dạng bản tin cho Telegram (parse_mode HTML).

Vì sao HTML chứ không phải Markdown: chế độ Markdown legacy của Telegram coi
"_" và "*" lẻ cặp là LỖI CÚ PHÁP và từ chối gửi cả tin — trong khi nội dung
bản tin luôn có nhãn kiểu TRUNG_TINH, DO_NOT_BUY_MORE. HTML chỉ cần escape
< > & là an toàn tuyệt đối, in đậm bằng <b> hoạt động ổn định.
"""
from __future__ import annotations

import html
import re

# Icon cho từng mục bản tin — mục mới chưa khai báo sẽ dùng DEFAULT_ICON.
SECTION_ICONS: dict[str, str] = {
    "TỔNG QUAN HÀNH ĐỘNG": "🧭",
    "TÀI SẢN RÒNG": "💰",
    "VÀNG": "🥇",
    "TIỀN GỬI": "🏦",
    "CHỨNG KHOÁN": "📈",
    "CẢNH BÁO NGƯỠNG GIÁ": "🚨",
    "THAY ĐỔI SO VỚI BẢN TIN TRƯỚC": "🔄",
}
DEFAULT_ICON = "▪️"
DIVIDER = "─────────────────"

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def to_telegram_html(text: str) -> str:
    """Chuyển bản tin dạng markdown-ish của orchestrator sang Telegram HTML.

    - `# Tiêu đề`  → <b>📊 Tiêu đề</b>
    - `## Mục`     → đường phân cách + <b><icon> Mục</b>
    - `**đậm**`    → <b>đậm</b>
    - Mọi ký tự < > & trong nội dung được escape trước khi thêm tag.
    """
    lines_out: list[str] = []
    seen_section = False
    for raw in text.splitlines():
        line = html.escape(raw, quote=False)
        if raw.startswith("## "):
            title = raw[3:].strip()
            icon = SECTION_ICONS.get(title, DEFAULT_ICON)
            if seen_section:
                lines_out.append(DIVIDER)
            seen_section = True
            lines_out.append(f"<b>{icon} {html.escape(title, quote=False)}</b>")
            continue
        if raw.startswith("# "):
            lines_out.append(f"<b>📊 {html.escape(raw[2:].strip(), quote=False)}</b>")
            continue
        line = _BOLD_RE.sub(r"<b>\1</b>", line)
        lines_out.append(line)
    return "\n".join(lines_out)

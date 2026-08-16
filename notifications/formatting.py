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
    "BỐI CẢNH THỊ TRƯỜNG": "🧿",
    "CHỨNG KHOÁN": "📈",
    "CẢNH BÁO NGƯỠNG GIÁ": "🚨",
    "THAY ĐỔI SO VỚI BẢN TIN TRƯỚC": "🔄",
}
DEFAULT_ICON = "▪️"
DIVIDER = "─────────────────"

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_BOLD_TAG_RE = re.compile(r"</?b>")


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
        # `### Tiểu mục` — reporting/diff_report.py sinh ra mức này. Trước đây
        # không xử lý nên nó hiện NGUYÊN VĂN "### Thị trường" trong tin nhắn
        # (nhìn thấy trong ảnh chụp màn hình của chủ danh mục ngày 15/8).
        if raw.startswith("### "):
            lines_out.append(f"<b>{html.escape(raw[4:].strip(), quote=False)}</b>")
            continue
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
    return wrap_aligned_blocks(lines_out)


# Dòng "thẳng hàng": có từ 2 khoảng trắng liên tiếp trở lên, xuất hiện ít nhất
# 2 lần — dấu hiệu của bảng canh cột bằng dấu cách.
_ALIGNED_RE = re.compile(r"\S {2,}\S")


def _is_aligned(line: str) -> bool:
    return len(_ALIGNED_RE.findall(line)) >= 2


def wrap_aligned_blocks(lines: list[str]) -> str:
    """Bọc các khối bảng canh cột vào <pre> để Telegram giữ font đều.

    Vì sao cần: Telegram hiển thị tin nhắn bằng font TỶ LỆ, nên mọi bảng canh
    cột bằng dấu cách (bảng thời hạn, bảng độ nhạy — phần đáng đọc nhất của
    báo cáo) sẽ vỡ hàng thành một đống chữ trên điện thoại. `<pre>` là font
    đều, giữ đúng cột.

    Thẻ <b> bị gỡ bên trong <pre>: Telegram không xử lý định dạng lồng trong
    khối mã một cách nhất quán, và một thẻ hỏng làm hỏng CẢ tin.
    """
    out: list[str] = []
    block: list[str] = []

    def flush() -> None:
        if not block:
            return
        # Khối 1 dòng thì không đáng bọc — <pre> cho một dòng lẻ trông như lỗi.
        if len(block) == 1:
            out.append(block[0])
        else:
            body = "\n".join(_BOLD_TAG_RE.sub("", b) for b in block)
            out.append(f"<pre>{body}</pre>")
        block.clear()

    for line in lines:
        if _is_aligned(line):
            block.append(line)
        else:
            flush()
            out.append(line)
    flush()
    return "\n".join(out)


# --- Cắt tin dài: Telegram giới hạn 4096 ký tự/tin --------------------------
#
# Lỗi THẬT đang xảy ra trước khi có phần này: `send_message` cắt cụt ở 4000 ký
# tự rồi ghi "…(cắt bớt, xem đầy đủ trong bản tin gốc)". Bản tin hiện dài
# 7.438 ký tự, nên MỌI bản tin laptop đã gửi đều mất gần một nửa — và câu
# "xem đầy đủ trong bản tin gốc" là lời khuyên không thực hiện được: người
# đọc đang cầm điện thoại, không có bản gốc nào để mở.
#
# Báo cáo phải tới ĐỦ. Cắt thành nhiều tin theo ranh giới dòng, không cắt cụt.

TELEGRAM_LIMIT = 4096
# Chừa chỗ cho nhãn "(phần k/n)" cộng vài ký tự an toàn.
SAFE_LIMIT = 3900


def split_for_telegram(text: str, limit: int = SAFE_LIMIT) -> list[str]:
    """Cắt văn bản thành các tin ≤ `limit`, LUÔN cắt ở ranh giới dòng.

    Cắt giữa dòng sẽ xé đôi một cặp thẻ `<b>…</b>` và Telegram từ chối cả tin
    vì HTML không hợp lệ — mỗi tin phải tự nó là HTML đúng. `to_telegram_html`
    chỉ mở/đóng thẻ TRONG một dòng, nên cắt theo dòng là đủ để mọi phần hợp lệ.

    Ưu tiên cắt ở đường phân cách giữa các mục để mỗi tin là một khối đọc
    được, thay vì đứt giữa chừng một bảng số.
    """
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    current: list[str] = []
    size = 0
    for line in text.splitlines():
        # Dòng đơn lẻ dài quá giới hạn: cắt cứng, nhưng chỉ khi nó KHÔNG chứa
        # thẻ HTML — có thẻ thì giữ nguyên cả dòng, thà một tin hơi dài hơn
        # giới hạn mềm còn hơn gửi HTML gãy (giới hạn cứng vẫn còn 196 ký tự đệm).
        if len(line) > limit and "<" not in line:
            for i in range(0, len(line), limit):
                chunk = line[i:i + limit]
                if size + len(chunk) + 1 > limit and current:
                    parts.append("\n".join(current))
                    current, size = [], 0
                current.append(chunk)
                size += len(chunk) + 1
            continue
        if size + len(line) + 1 > limit and current:
            parts.append("\n".join(current))
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        parts.append("\n".join(current))

    if len(parts) <= 1:
        return parts
    total = len(parts)
    return [f"{p}\n\n<i>(phần {i + 1}/{total})</i>" for i, p in enumerate(parts)]

"""Test cho notifications/formatting.py — chuyển bản tin markdown-ish sang
Telegram HTML có icon, an toàn với ký tự đặc biệt."""
from notifications.formatting import to_telegram_html


def test_title_line_becomes_bold_with_icon():
    out = to_telegram_html("# BẢN TIN ĐẦU TƯ SÁNG — 2026-07-20")
    assert "<b>📊 BẢN TIN ĐẦU TƯ SÁNG — 2026-07-20</b>" in out
    assert "# " not in out


def test_section_header_gets_icon_and_bold():
    out = to_telegram_html("## VÀNG")
    assert "<b>🥇 VÀNG</b>" in out
    assert "##" not in out


def test_unknown_section_still_bold_with_default_icon():
    out = to_telegram_html("## MỤC LẠ CHƯA ĐẶT ICON")
    assert "<b>▪️ MỤC LẠ CHƯA ĐẶT ICON</b>" in out


def test_double_asterisk_becomes_bold_tag():
    out = to_telegram_html("Vàng: **GIỮ** (tin cậy 92/100)")
    assert "<b>GIỮ</b>" in out
    assert "**" not in out


def test_html_special_chars_escaped():
    # Dữ liệu thật có thể chứa < > & (VD "khoản <1 tỷ") — phải escape để
    # Telegram không hiểu nhầm thành tag
    out = to_telegram_html("Tiền gửi khoản <1 tỷ & lãi >7%")
    assert "&lt;1 tỷ" in out
    assert "&amp;" in out
    assert "&gt;7%" in out


def test_underscores_survive_unchanged():
    # Lý do bỏ Markdown legacy: nhãn TRUNG_TINH làm hỏng parse. HTML thì vô hại.
    out = to_telegram_html("Xu hướng kỹ thuật: TRUNG_TINH")
    assert "TRUNG_TINH" in out


def test_sections_separated_by_divider():
    text = "## VÀNG\nnội dung\n\n## TIỀN GỬI\nnội dung"
    out = to_telegram_html(text)
    assert out.count("─") > 0  # có đường phân cách trước mục mới (trừ mục đầu)

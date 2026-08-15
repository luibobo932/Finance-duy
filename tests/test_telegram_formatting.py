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


# --- Tin dài phải TỚI ĐỦ, không bị cắt cụt ---------------------------------
#
# Lỗi thật trước khi có phần này: send_message cắt cụt ở 4000 ký tự rồi ghi
# "…(cắt bớt, xem đầy đủ trong bản tin gốc)". Bản tin dài 7.438 ký tự nên MỌI
# bản tin đã gửi đều mất gần một nửa — và "xem bản tin gốc" là lời khuyên
# không thực hiện được khi người đọc đang cầm điện thoại.

def test_tin_ngan_khong_bi_cat():
    from notifications.formatting import split_for_telegram

    assert split_for_telegram("ngắn") == ["ngắn"]


def test_tin_dai_duoc_cat_thanh_NHIEU_TIN_khong_bi_cut():
    from notifications.formatting import split_for_telegram

    text = "\n".join(f"dòng số {i} " + "x" * 80 for i in range(200))
    parts = split_for_telegram(text)
    assert len(parts) > 1
    # Không mất dòng nào: mọi dòng gốc phải xuất hiện lại
    joined = "\n".join(parts)
    for i in (0, 99, 199):
        assert f"dòng số {i} " in joined


def test_moi_phan_deu_duoi_gioi_han_cung_cua_telegram():
    from notifications.formatting import TELEGRAM_LIMIT, split_for_telegram

    text = "\n".join(f"dòng {i} " + "y" * 100 for i in range(300))
    assert all(len(p) <= TELEGRAM_LIMIT for p in split_for_telegram(text))


def test_cat_o_RANH_GIOI_DONG_de_the_HTML_khong_gay():
    """Cắt giữa dòng sẽ xé đôi <b>…</b> và Telegram từ chối CẢ tin."""
    from notifications.formatting import split_for_telegram

    text = "\n".join(f"<b>mục {i}</b> nội dung " + "z" * 60 for i in range(200))
    for p in split_for_telegram(text):
        assert p.count("<b>") == p.count("</b>")


def test_danh_so_phan_de_biet_thu_tu():
    from notifications.formatting import split_for_telegram

    parts = split_for_telegram("\n".join("a" * 100 for _ in range(100)))
    assert "phần 1/" in parts[0] and f"phần {len(parts)}/{len(parts)}" in parts[-1]


def test_dong_don_le_qua_dai_van_cat_duoc():
    from notifications.formatting import TELEGRAM_LIMIT, split_for_telegram

    assert all(len(p) <= TELEGRAM_LIMIT for p in split_for_telegram("q" * 12000))


def test_dong_dai_CO_THE_HTML_thi_giu_nguyen_khong_xe_the():
    """Thà một tin hơi vượt giới hạn mềm còn hơn gửi HTML gãy."""
    from notifications.formatting import split_for_telegram

    line = "<b>" + "w" * 4000 + "</b>"
    for p in split_for_telegram(line):
        assert p.count("<b>") == p.count("</b>")


# --- Bảng canh cột phải giữ được cột trên điện thoại -----------------------

def test_bang_canh_cot_duoc_boc_vao_pre():
    """Telegram dùng font TỶ LỆ nên bảng canh cột bằng dấu cách sẽ vỡ hàng —
    mà bảng thời hạn là phần đáng đọc nhất của báo cáo."""
    from notifications.formatting import to_telegram_html

    md = ("## MỤC TIÊU\n"
          "  5 năm     53,52%    112,6 tr\n"
          " 10 năm     23,90%     40,8 tr\n"
          " 20 năm     11,31%      7,7 tr\n")
    out = to_telegram_html(md)
    assert "<pre>" in out and "</pre>" in out
    assert out.count("<pre>") == out.count("</pre>")


def test_van_ban_thuong_KHONG_bi_boc_pre():
    from notifications.formatting import to_telegram_html

    out = to_telegram_html("Đây là một câu văn bình thường, không phải bảng.")
    assert "<pre>" not in out


def test_mot_dong_le_khong_dang_boc_pre():
    """<pre> cho một dòng lẻ trông như lỗi hiển thị."""
    from notifications.formatting import to_telegram_html

    out = to_telegram_html("Tổng   1.173 tr   76,0%\nCâu văn bình thường theo sau.")
    assert "<pre>" not in out


def test_go_the_b_ben_trong_pre():
    """Telegram xử lý định dạng lồng trong khối mã không nhất quán; một thẻ
    hỏng làm hỏng CẢ tin."""
    from notifications.formatting import to_telegram_html

    md = ("  5 năm     **53,52%**    112,6 tr\n"
          " 10 năm     **23,90%**     40,8 tr\n")
    out = to_telegram_html(md)
    assert "<pre>" in out and "<b>" not in out


def test_bao_cao_that_cat_va_boc_dung():
    """Chạy trên chính báo cáo kế hoạch đang dùng."""
    import subprocess
    import sys
    from pathlib import Path

    from notifications.formatting import (TELEGRAM_LIMIT, split_for_telegram,
                                          to_telegram_html)

    root = Path(__file__).resolve().parent.parent
    proc = subprocess.run([sys.executable, str(root / "scripts" / "plan.py")],
                          capture_output=True, text=True, cwd=str(root))
    if proc.returncode != 0:
        import pytest

        pytest.skip("không dựng được báo cáo kế hoạch")
    html_text = to_telegram_html(proc.stdout)
    for p in split_for_telegram(html_text):
        assert len(p) <= TELEGRAM_LIMIT
        assert p.count("<pre>") == p.count("</pre>")
        assert p.count("<b>") == p.count("</b>")

"""Quỹ khẩn cấp không được chừa hai lần.

Quỹ khẩn cấp là yêu cầu ở tầng DANH MỤC (`config/risk_limits.yaml:
minimum_cash_buffer_vnd`), không phải yêu cầu riêng của khoản tiết kiệm — tiền
mặt đang nắm đã tính vào đó rồi.

Lỗi thật, đo ngày 30/08 trên chính config của dự án:

    hạn mức quỹ khẩn cấp                                   30 tr
    tiền mặt 35 tr − 30 tr → "khả dụng ngay 5 tr"                  ✓ đúng
    tiết kiệm 246 tr − 30 tr → chia kỳ hạn trên 216 tr             ✗ chừa lần hai
    ─────────────────────────────────────────────────────────────
    tổng đã chừa                                           60 tr

Gấp đôi mức hạn mức yêu cầu. Hệ quả: 30 tr tiết kiệm nằm ngoài kế hoạch, và ở
mức tốt nhất đo được 8,00%/năm đó là **2,4 tr/năm tiền lãi bỏ lỡ** — trong đúng
module sinh ra để tối đa hoá lãi tiền gửi.
"""
import pytest

from deposits.strategy import buffer_needed_from_savings


def test_tien_mat_du_quy_thi_KHONG_chua_them_tu_tiet_kiem():
    assert buffer_needed_from_savings(30_000_000, 35_000_000) == 0


def test_tien_mat_dung_bang_quy_cung_khong_chua_them():
    assert buffer_needed_from_savings(30_000_000, 30_000_000) == 0


def test_tien_mat_thieu_thi_chua_dung_phan_con_thieu():
    assert buffer_needed_from_savings(30_000_000, 12_000_000) == 18_000_000


def test_khong_co_tien_mat_thi_chua_nguyen_muc_quy():
    assert buffer_needed_from_savings(30_000_000, 0) == 30_000_000


def test_khong_bao_gio_tra_so_am():
    assert buffer_needed_from_savings(30_000_000, 500_000_000) == 0


def test_thieu_cau_hinh_thi_coi_nhu_0_chu_khong_no():
    assert buffer_needed_from_savings(None, None) == 0
    assert buffer_needed_from_savings(0, None) == 0


# --- Trên cấu hình THẬT của dự án -------------------------------------------

def test_tren_config_that_toan_bo_tiet_kiem_duoc_dua_vao_ke_hoach():
    from deposits.ranking import load_normalized, rank
    from deposits.strategy import split_strategy
    from portfolio.loader import load_portfolio, load_risk_limits

    port, limits = load_portfolio(), load_risk_limits()
    ranked = rank(load_normalized())
    if not ranked:
        pytest.skip("chưa có bảng lãi suất chuẩn hoá")

    buffer = buffer_needed_from_savings(
        limits.get("minimum_cash_buffer_vnd", 0), port.cash_amount_vnd)
    assert buffer == 0, "tiền mặt đã đủ quỹ khẩn cấp mà vẫn chừa thêm từ tiết kiệm"

    dung = split_strategy(port.savings_principal_vnd, buffer, ranked)
    chua_hai_lan = split_strategy(
        port.savings_principal_vnd, limits.get("minimum_cash_buffer_vnd", 0), ranked)
    assert sum(a.amount_vnd for a in dung) > sum(a.amount_vnd for a in chua_hai_lan)


def test_lai_bo_lo_khi_chua_hai_lan_duoc_do_bang_tien():
    """Nêu rõ cái giá, để về sau đọc lại còn thấy vì sao đáng sửa."""
    from deposits.ranking import load_normalized, rank

    ranked = rank(load_normalized())
    if not ranked:
        pytest.skip("chưa có bảng lãi suất chuẩn hoá")
    bo_lo = 30_000_000 * ranked[0]["rate_pct"] / 100
    assert bo_lo > 2_000_000  # ~2,4 tr/năm ở mức 8,00%


def test_deposits_report_khong_con_chua_hai_lan():
    """Chống tái phát: caller phải đi qua buffer_needed_from_savings()."""
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "scripts" / "deposits_report.py"
           ).read_text(encoding="utf-8")
    assert "buffer_needed_from_savings" in src
    for line in src.splitlines():
        code = line.split("#", 1)[0]
        if "split_strategy(" in code and "def " not in code:
            assert "buffer_needed_from_savings" not in code  # đã tính ở trên
            assert "minimum_cash_buffer_vnd" not in code, "truyền thẳng hạn mức vào lại rồi"

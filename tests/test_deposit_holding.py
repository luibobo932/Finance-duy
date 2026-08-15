"""Test deposits/holding.py — 21% tài sản mà hệ thống chưa biết gì về nó.

`config/portfolio.yaml` khai báo đúng một dòng cho khoản tiết kiệm: số gốc
246tr. Không lãi suất, không ngân hàng, không kỳ hạn, không ngày gửi. Hệ quả
đo được: chênh lệch lãi suất trên khoản đó là 1,2–8,6 tr/năm, mà đầu trên của
khoảng ấy còn LỚN HƠN phần lãi thêm của cả kế hoạch bán vàng về 69% (7,7
tr/năm) — thứ hệ thống đã nhắc 19 kỳ liên tiếp.
"""
from datetime import date

import pytest

from deposits.holding import (
    DepositHolding,
    from_portfolio,
    maturity_alert,
    rate_gap_table,
    undeclared_note,
)

TODAY = date(2026, 8, 14)


def _declared(**kw):
    base = dict(principal_vnd=246_000_000, bank="VIB", rate_pct=6.5,
                term_months=12, start_date=date(2026, 1, 10), channel="online")
    base.update(kw)
    return DepositHolding(**base)


# --- Chưa khai báo: báo thiếu, KHÔNG đoán -----------------------------------

def test_chua_khai_bao_thi_khong_bia_lai_suat():
    h = DepositHolding(principal_vnd=246_000_000)
    assert h.is_declared is False
    assert h.accrued_interest_vnd(TODAY) is None
    assert h.maturity_date is None


def test_thieu_lai_suat_tra_None_chu_khong_tra_0():
    """0 sẽ bị đọc thành 'chưa sinh lãi đồng nào', khác hẳn 'chưa biết'."""
    assert DepositHolding(principal_vnd=246_000_000).accrued_interest_vnd(TODAY) is None


def test_chua_khai_bao_thi_dinh_gia_bang_GOC_huong_sai_an_toan():
    """Thấp hơn thực tế là hướng sai an toàn — không bao giờ báo tài sản cao
    hơn số có thật."""
    h = DepositHolding(principal_vnd=246_000_000)
    assert h.value_at(TODAY) == 246_000_000


# --- Đã khai báo: tính được lãi và đáo hạn ---------------------------------

def test_lai_tich_luy_tinh_theo_so_ngay_thuc():
    h = _declared(principal_vnd=100_000_000, rate_pct=10.0, start_date=date(2025, 8, 14))
    assert h.accrued_interest_vnd(TODAY) == pytest.approx(10_000_000, rel=0.01)


def test_gia_tri_bang_goc_cong_lai():
    h = _declared(principal_vnd=100_000_000, rate_pct=10.0, start_date=date(2025, 8, 14))
    assert h.value_at(TODAY) > h.principal_vnd


def test_ngay_gui_trong_tuong_lai_khong_ra_lai_AM():
    h = _declared(start_date=date(2026, 12, 1))
    assert h.accrued_interest_vnd(TODAY) == 0.0


def test_ngay_dao_han_tu_ky_han():
    h = _declared(start_date=date(2026, 1, 10), term_months=12)
    assert h.maturity_date == date(2027, 1, 5)  # 12 x 30 ngày


# --- Cảnh báo đáo hạn -------------------------------------------------------

def test_con_xa_thi_khong_canh_bao():
    assert maturity_alert(_declared(start_date=date(2026, 6, 1), term_months=12), TODAY) is None


def test_sap_dao_han_thi_canh_bao_kem_ly_do_tu_quay_vong():
    """Sổ đến hạn không tất toán thường tái tục theo lãi suất TẠI QUẦY — thấp
    hơn hẳn mức online đã ký. Đây là khoản rò rỉ tiền im lặng."""
    h = _declared(start_date=date(2025, 8, 20), term_months=12)  # đáo hạn 15/8/2026
    a = maturity_alert(h, TODAY)
    assert a is not None and a.level == "warning"
    assert "tại quầy" in a.message.lower()


def test_da_qua_han_thi_muc_critical():
    h = _declared(start_date=date(2025, 7, 1), term_months=12)
    a = maturity_alert(h, TODAY)
    assert a is not None and a.level == "critical" and a.days_left < 0


def test_thieu_ngay_gui_thi_KHONG_canh_bao_duoc():
    """Chính điều này là lý do cần khai báo — không có dữ liệu thì không có
    cảnh báo, chứ không phải 'không có rủi ro'."""
    assert maturity_alert(DepositHolding(principal_vnd=246_000_000), TODAY) is None


# --- Bảng lượng hóa khoảng chưa biết ---------------------------------------

def test_bang_chenh_lech_tinh_dung_tien_moi_nam():
    rows = rate_gap_table(246_000_000, 8.0, assumed_rates_pct=(5.5,))
    assert rows[0].gap_per_year_vnd == pytest.approx(246_000_000 * 2.5 / 100)


def test_muc_da_bang_hoac_tot_hon_thi_khong_co_khoang_trong():
    assert rate_gap_table(100_000_000, 6.0, assumed_rates_pct=(6.0, 7.0)) == []


def test_khong_co_muc_tot_nhat_thi_khong_bia_bang():
    assert rate_gap_table(246_000_000, None) == []


def test_bang_KHONG_phai_uoc_tinh_lai_suat_cua_chu_danh_muc():
    """Mỗi dòng là một GIẢ ĐỊNH để đo khoảng chưa biết, không phải phán đoán
    về mức thật — nên phải có nhiều dòng, không phải một con số duy nhất."""
    assert len(rate_gap_table(246_000_000, 8.0)) >= 3


def test_loi_de_nghi_khai_bao_phai_KEM_CON_SO():
    """Lời nhắc chung chung đã bị bỏ qua 19 kỳ ở chỗ khác rồi."""
    rows = rate_gap_table(246_000_000, 8.0)
    note = undeclared_note(246_000_000, rows)
    assert "tr/năm" in note and "246 tr" in note
    assert "portfolio.yaml" in note


def test_loi_de_nghi_van_chay_khi_chua_co_lai_suat_thi_truong():
    note = undeclared_note(246_000_000, [])
    assert "Chưa khai báo" in note and "246 tr" in note


# --- Nạp từ config thật -----------------------------------------------------

def test_nap_duoc_tu_portfolio_yaml_that():
    from portfolio.loader import load_portfolio

    port = load_portfolio()
    h = from_portfolio(port, deposit_cfg=port.savings_raw)
    assert h.principal_vnd == port.savings_principal_vnd
    # Các trường mới phải TỒN TẠI trong config (dù còn null) để việc điền số
    # sau này không cần sửa code.
    for key in ("bank", "rate_pct", "term_months", "start_date"):
        assert key in port.savings_raw


def test_khoang_chenh_lech_that_lon_hon_loi_ich_ban_vang_muc_dau():
    """Phát hiện thúc đẩy cả module: hệ thống nhắc 19 kỳ về khoản lãi thêm 7,7
    tr/năm từ bán vàng, trong khi khoảng chưa biết ở tiền gửi có thể lớn hơn."""
    rows = rate_gap_table(246_000_000, 8.0)
    assert max(r.gap_per_year_vnd for r in rows) / 1_000_000 > 7.7

"""Test planning/feasibility.py — mục tiêu 10 tỷ cần GÌ để khả thi.

Chủ danh mục đặt mục tiêu nâng tổng tài sản lên 10 tỷ (15/08/2026). Hiện có
1.173 tr → cần gấp 8,53 lần. Câu hỏi đúng không phải "mua mã nào" mà là: với
ba biến — thời hạn, tiền gửi thêm mỗi tháng, lợi suất — cố định hai cái thì
cái thứ ba phải bằng bao nhiêu.
"""
import pytest

from planning.feasibility import (
    AGGRESSIVE_CEILING_PCT,
    DEFAULT_HORIZONS_YEARS,
    GoalReality,
    best_lever,
    classify,
    horizon_table,
    required_monthly_trieu,
    required_return_pct,
    required_years,
)

CUR, TGT, INFL, SAFE = 1172.7, 10_000.0, 4.39, 8.0


# --- Lợi suất cần, nếu không gửi thêm --------------------------------------

def test_10_nam_doi_muc_loi_suat_bat_kha_thi_ben_vung():
    r = required_return_pct(CUR, TGT, 10)
    assert r == pytest.approx(23.90, abs=0.05)
    assert classify(r, SAFE) == "unrealistic"


def test_30_nam_chi_doi_muc_gan_bang_tien_gui():
    r = required_return_pct(CUR, TGT, 30)
    assert r == pytest.approx(7.41, abs=0.05)
    assert classify(r, SAFE) == "risk_free"  # thấp hơn lãi tiền gửi 8%


def test_thoi_han_cang_dai_loi_suat_can_cang_thap():
    rs = [required_return_pct(CUR, TGT, y) for y in DEFAULT_HORIZONS_YEARS]
    assert rs == sorted(rs, reverse=True)


def test_khong_co_tai_san_thi_khong_tinh_duoc_loi_suat():
    """Không thể nhân 0 lên 10 tỷ bằng bất kỳ lợi suất nào."""
    assert required_return_pct(0, TGT, 10) is None


# --- Tiền gửi thêm mỗi tháng, ở lợi suất an toàn ---------------------------

def test_20_nam_chi_can_gui_them_muc_kha_thi():
    """Đây là con số quan trọng nhất của cả module: với tiền gửi 8% (KHÔNG rủi
    ro), 20 năm chỉ cần thêm ~7,7 tr/tháng."""
    m = required_monthly_trieu(CUR, TGT, 20, SAFE)
    assert m == pytest.approx(7.7, abs=0.3)


def test_10_nam_doi_muc_gui_them_gap_hon_5_lan():
    m10 = required_monthly_trieu(CUR, TGT, 10, SAFE)
    m20 = required_monthly_trieu(CUR, TGT, 20, SAFE)
    assert m10 / m20 > 5


def test_30_nam_thi_KHONG_can_gui_them_dong_nao():
    """Trả 0.0, khác hẳn None — 'đã đủ' và 'không tính được' là hai chuyện."""
    assert required_monthly_trieu(CUR, TGT, 30, SAFE) == 0.0


def test_loi_suat_0_van_tinh_duoc_khong_chia_cho_0():
    m = required_monthly_trieu(100.0, 1000.0, 10, 0.0)
    assert m == pytest.approx((1000 - 100) / 120)


# --- Bao nhiêu năm thì tới ---------------------------------------------------

def test_so_nam_toi_dich_voi_muc_gui_them_cu_the():
    y = required_years(CUR, TGT, SAFE, monthly_trieu=10.0)
    assert y is not None and 15 <= y <= 20


def test_khong_bao_gio_toi_thi_tra_None_khong_tra_so_khong_lo():
    """Trả 999 sẽ bị đọc thành 'rồi cũng tới', trong khi sự thật là kế hoạch
    không hoạt động."""
    assert required_years(100.0, TGT, 0.0, monthly_trieu=0.0) is None


def test_da_du_thi_0_nam():
    assert required_years(TGT + 1, TGT, 5.0) == 0


# --- Phân loại: mốc đầu là SỐ ĐO, các mốc sau là NHẬN ĐỊNH ------------------

def test_moc_dau_neo_vao_lai_suat_tien_gui_THAT():
    assert classify(7.0, SAFE) == "risk_free"
    assert classify(8.0, SAFE) == "risk_free"
    assert classify(8.5, SAFE) == "moderate"


def test_khong_co_moc_tien_gui_thi_van_phan_loai_duoc():
    assert classify(9.0, None) == "moderate"


def test_muc_qua_cao_bi_goi_dung_ten():
    assert classify(AGGRESSIVE_CEILING_PCT + 1, SAFE) == "unrealistic"
    assert classify(None, SAFE) == "unrealistic"


# --- Bảng thời hạn ----------------------------------------------------------

def test_bang_thoi_han_day_du_cot():
    rows = horizon_table(CUR, TGT, INFL, risk_free_pct=SAFE)
    assert len(rows) == len(DEFAULT_HORIZONS_YEARS)
    r20 = next(r for r in rows if r.years == 20)
    assert r20.required_return_pct > r20.required_real_return_pct
    assert r20.required_monthly_trieu > 0
    assert r20.value_from_current_trieu > CUR
    assert r20.band_label


def test_bang_cho_thay_tai_san_hien_co_tu_len_bao_nhieu():
    """Phần này quan trọng: ở 20 năm, riêng 1.173 tr hiện có đã tự lên ~5.466 tr
    với lãi tiền gửi — hơn nửa quãng đường, mà không cần làm gì thêm."""
    rows = horizon_table(CUR, TGT, INFL, risk_free_pct=SAFE)
    r20 = next(r for r in rows if r.years == 20)
    assert r20.value_from_current_trieu == pytest.approx(5466, abs=30)


# --- Danh nghĩa vs sức mua: HAI mục tiêu khác nhau -------------------------

def test_10_ty_sau_20_nam_chi_mua_duoc_bang_hon_4_ty_hom_nay():
    g = GoalReality(TGT, 20, INFL)
    assert g.purchasing_power_today_trieu == pytest.approx(4230, abs=60)


def test_muon_10_ty_THEO_SUC_MUA_thi_danh_nghia_phai_cao_hon_nhieu():
    g = GoalReality(TGT, 20, INFL)
    assert g.nominal_needed_for_same_power_trieu > 23_000


def test_note_neu_ro_ca_hai_thang():
    n = GoalReality(TGT, 20, INFL).note
    assert "danh nghĩa" in n and "SỨC MUA HÔM NAY" in n


def test_thoi_han_0_thi_hai_thang_bang_nhau():
    g = GoalReality(TGT, 0, INFL)
    assert g.purchasing_power_today_trieu == pytest.approx(TGT)


# --- Kết luận: đòn bẩy mạnh nhất ------------------------------------------

def test_ket_luan_do_bang_chinh_bang_so_khong_phai_nhan_dinh_chung():
    rows = horizon_table(CUR, TGT, INFL, risk_free_pct=SAFE)
    s = best_lever(rows)
    assert "lần" in s and "tr/tháng" in s
    assert "THỜI HẠN" in s


def test_ket_luan_khong_no_khi_bang_qua_ngan():
    assert best_lever([]) == ""


# --- Chạy trên danh mục + mục tiêu THẬT ------------------------------------

def test_chay_duoc_tren_muc_tieu_that_trong_config():
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "scripts"))
    from networth import compute
    from planning.plan import load_plan

    plan = load_plan()
    goal = plan.goals[0]
    _p, _l, _m, _parts, total, _pr, _s = compute()
    rows = horizon_table(total, goal.target_vnd / 1_000_000, plan.inflation_pct,
                         risk_free_pct=SAFE)
    # Với danh mục và mục tiêu thật: thời hạn ngắn là bất khả thi, dài thì không
    assert rows[0].band == "unrealistic"
    assert rows[-1].band == "risk_free"

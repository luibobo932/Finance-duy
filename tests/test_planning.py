"""Test planning/ — tầng SỨC MUA, thứ toàn bộ hệ thống đang thiếu.

Mọi con số hệ thống đã nói cho tới nay đều là danh nghĩa: "tiền gửi 8%/năm",
"lãi thêm 11 tr/năm", "danh mục 1.173 tr". Với CPI 7 tháng 2026 là +4,39%,
khoảng cách giữa danh nghĩa và thực là khoảng cách giữa hai kết luận trái
ngược — 35 tr tiền mặt "không đổi" thực ra đang mất 1,47 tr sức mua mỗi năm.
"""
from datetime import date

import pytest

from planning.plan import (
    SENSITIVITY_NOMINAL_PCT,
    Goal,
    Plan,
    check_goal,
    emergency_fund_months,
    load_plan,
    project,
    sensitivity,
)
from planning.real_return import (
    RealReturn,
    doubling_years,
    erosion_trieu,
    nominal_needed_for,
    portfolio_real_return,
    purchasing_power_trieu,
    real_pct,
)

INFL = 4.39


# --- Fisher chính xác, KHÔNG phải phép trừ ---------------------------------

def test_loi_suat_thuc_dung_cong_thuc_Fisher_khong_phai_phep_tru():
    """Phép trừ cho 3,61%; công thức đúng cho 3,46%. Sai số 0,15 điểm % luôn
    lệch về phía LẠC QUAN — đúng hướng nguy hiểm."""
    exact = real_pct(8.0, INFL)
    assert exact == pytest.approx(3.4583, abs=0.001)
    assert exact < 8.0 - INFL


def test_lai_suat_bang_lam_phat_thi_thuc_bang_0():
    assert real_pct(INFL, INFL) == pytest.approx(0.0, abs=1e-9)


def test_tien_mat_0_phan_tram_la_LO_THAT():
    """0% danh nghĩa không phải 'không đổi' — đó là −4,21%/năm sức mua."""
    r = RealReturn("Tiền mặt", 0.0, INFL, 35.0)
    assert r.real_pct == pytest.approx(-4.206, abs=0.01)
    assert r.real_change_trieu == pytest.approx(-1.47, abs=0.01)
    assert "MẤT" in r.verdict


def test_gui_4_phay_5_gan_nhu_dung_yen():
    """Nghe như đang sinh lời, thực tế sức mua không nhúc nhích."""
    r = RealReturn("Tiết kiệm", 4.5, INFL, 246.0)
    assert 0 < r.real_pct < 0.5
    assert "đứng yên" in r.verdict


def test_cau_hoi_nguoc_can_bao_nhieu_de_thuc_2_phan_tram():
    n = nominal_needed_for(2.0, INFL)
    assert n == pytest.approx(6.478, abs=0.01)
    assert real_pct(n, INFL) == pytest.approx(2.0, abs=1e-9)


# --- Bào mòn sức mua --------------------------------------------------------

def test_bao_mon_mot_nam_dung_bang_phan_mat_sức_mua():
    assert erosion_trieu(35.0, INFL, 1) == pytest.approx(1.472, abs=0.01)


def test_bao_mon_LUY_KE_theo_nhieu_nam():
    assert erosion_trieu(35.0, INFL, 10) > erosion_trieu(35.0, INFL, 1) * 5


def test_suc_mua_10_nam_cua_danh_muc_that():
    """1.173 tr để yên 10 năm chỉ còn mua được lượng hàng của ~763 tr hôm nay."""
    assert purchasing_power_trieu(1172.7, INFL, 10) == pytest.approx(763, abs=3)


def test_gap_doi_suc_mua_khong_co_nghia_khi_loi_suat_thuc_am():
    """Trả một con số khổng lồ ở đây sẽ gây hiểu nhầm là 'rồi cũng gấp đôi'."""
    assert doubling_years(-4.2) is None
    assert doubling_years(0) is None
    assert doubling_years(3.46) == pytest.approx(20.4, abs=0.5)


# --- Chưa khai báo KHÁC bằng 0 ---------------------------------------------

def test_phan_chua_khai_bao_KHONG_bi_gan_0_phan_tram():
    """Gán 0% cho cái chưa biết sẽ kéo tụt lợi suất danh mục một cách bịa đặt —
    và ở danh mục này phần chưa biết là 97% tài sản."""
    pf = portfolio_real_return(
        [("Vàng", 891.7, None), ("Tiết kiệm", 246.0, None), ("Tiền mặt", 35.0, 0.0)], INFL)
    assert pf["known_weight_pct"] == pytest.approx(3.0, abs=0.1)
    assert [n for n, _ in pf["unknown"]] == ["Vàng", "Tiết kiệm"]
    assert pf["real_pct"] == pytest.approx(-4.206, abs=0.01)


def test_phan_chua_biet_giu_ca_GIA_TRI_khong_chi_giu_ten():
    """Biết 'Vàng chưa khai báo' mà không biết nó là 892 tr thì không thấy được
    vấn đề lớn tới đâu."""
    pf = portfolio_real_return([("Vàng", 891.7, None), ("Tiền mặt", 35.0, 0.0)], INFL)
    assert pf["unknown"][0] == ("Vàng", 891.7)


def test_danh_muc_rong_khong_lam_no():
    pf = portfolio_real_return([], INFL)
    assert pf["real_pct"] is None and pf["known_weight_pct"] == 0.0


# --- Chiếu tương lai: LUÔN kèm cột sức mua ---------------------------------

def test_chieu_tuong_lai_tra_ca_danh_nghia_lan_suc_mua():
    rows = project(1000.0, 8.0, INFL, 10)
    assert rows[0].nominal_trieu == rows[0].real_trieu == 1000.0
    assert rows[-1].nominal_trieu > rows[-1].real_trieu


def test_loi_suat_bang_lam_phat_thi_suc_mua_dung_yen():
    rows = project(1000.0, INFL, INFL, 10)
    assert rows[-1].real_trieu == pytest.approx(1000.0, abs=0.01)
    assert rows[-1].nominal_trieu > 1500  # danh nghĩa vẫn "tăng" hơn 50%


def test_gui_them_hang_thang_duoc_cong_vao():
    a = project(1000.0, 5.0, INFL, 5)[-1].nominal_trieu
    b = project(1000.0, 5.0, INFL, 5, monthly_add_trieu=5.0)[-1].nominal_trieu
    assert b > a


def test_bang_do_nhay_bay_ca_DAI_thay_vi_chon_ho_mot_so():
    """Hệ thống KHÔNG dự báo lợi suất. Thiếu giả định thì bày độ nhạy."""
    rows = sensitivity(1172.7, INFL, 10)
    assert len(rows) == len(SENSITIVITY_NOMINAL_PCT)
    assert rows[0][0] == 0.0  # phải có kịch bản "không sinh lời"
    assert rows[0][2] < rows[0][1]  # sức mua thấp hơn danh nghĩa


# --- Mục tiêu: quy đổi lạm phát trước khi so -------------------------------

def _plan(goals=()):
    return Plan(inflation_pct=INFL, inflation_source="test", inflation_as_of="2026-07-31",
                goals=list(goals))


def test_muc_tieu_khai_theo_suc_mua_HOM_NAY_duoc_quy_len_danh_nghia():
    """'3 tỷ năm 2041' vô nghĩa nếu không nói 3 tỷ đó mua được gì. So thẳng
    số hôm nay với tài sản tương lai là so hai đơn vị khác nhau."""
    g = Goal("Hưu trí", 3_000_000_000, 2041)
    c = check_goal(g, 1172.7, _plan(), 2026)
    assert c.years == 15
    assert c.target_today_trieu == 3000.0
    assert c.target_nominal_trieu > 5700  # 3.000 tr sau 15 năm lạm phát


def test_loi_suat_can_thiet_tinh_ca_hai_thang():
    c = check_goal(Goal("X", 3_000_000_000, 2041), 1172.7, _plan(), 2026)
    assert c.required_nominal_pct > c.required_real_pct
    assert real_pct(c.required_nominal_pct, INFL) == pytest.approx(c.required_real_pct)


def test_da_du_tai_san_thi_khong_doi_loi_suat_duong():
    c = check_goal(Goal("X", 100_000_000, 2041), 1172.7, _plan(), 2026)
    assert c.required_nominal_pct <= 0
    assert "Đã đủ" in c.reachable_note


def test_thieu_hut_tinh_theo_suc_mua_hom_nay():
    c = check_goal(Goal("X", 3_000_000_000, 2041), 1172.7, _plan(), 2026)
    assert c.shortfall_today_trieu == pytest.approx(3000.0 - 1172.7, abs=0.1)


# --- Quỹ khẩn cấp: ngưỡng tuyệt đối là ngưỡng vô nghĩa ---------------------

def test_quy_khan_cap_tinh_theo_SO_THANG_chi_tieu():
    """30 tr là 6 tháng với người tiêu 5 tr/tháng và 1 tháng với người tiêu
    30 tr/tháng — cùng ngưỡng, hai mức an toàn hoàn toàn khác nhau."""
    assert emergency_fund_months(35.0, 5_000_000) == pytest.approx(7.0)
    assert emergency_fund_months(35.0, 30_000_000) == pytest.approx(1.167, abs=0.01)


def test_chua_khai_chi_tieu_thi_KHONG_doan():
    assert emergency_fund_months(35.0, None) is None


# --- Config thật ------------------------------------------------------------

def test_config_plan_yaml_co_lam_phat_co_nguon():
    """Lạm phát là số liệu THẬT có nguồn, khác hẳn lợi suất kỳ vọng (giả định)."""
    p = load_plan()
    assert p.inflation_pct > 0
    assert p.inflation_source and p.inflation_as_of


def test_loi_suat_ky_vong_de_null_va_KHONG_bi_dien_ho():
    """Hệ thống không tự dự báo lợi suất — đó là giả định của chủ danh mục."""
    p = load_plan()
    assert p.expected_for("gold") is None
    assert p.expected_for("cash") == 0.0  # tiền mặt 0% là sự thật, không phải giả định


def test_chua_khai_muc_tieu_thi_bao_ro_thay_vi_bia_mot_cai():
    assert load_plan().has_goals is False


def test_chay_duoc_tren_danh_muc_that():
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "scripts"))
    from plan import build

    d = build()
    assert d["inflation"]["pct"] > 0
    assert d["cash_erosion_trieu_per_year"] > 0
    assert len(d["sensitivity_10y"]) >= 4
    assert d["purchasing_power_10y_trieu"] < d["total_trieu"]

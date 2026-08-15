"""Test khuyến nghị MUA cổ phiếu — biên an toàn + cỡ lệnh + rào lợi suất.

Lỗi cấu trúc trước phần này: `derive_initial_action` cho equity chỉ ra
BUY_SMALL khi `margin_of_safety_pct > 20`, mà **không caller production nào
truyền trường đó** (grep toàn repo trả rỗng). Nhánh cổ phiếu vì thế KHÔNG THỂ
khuyến nghị mua, mọi mã vĩnh viễn dừng ở ĐỨNG NGOÀI — một hệ thống theo dõi
cổ phiếu mà không bao giờ nói được "mua" thì chỉ là cái đồng hồ báo giá.

Nhưng mở được nút MUA cũng là lúc nguy hiểm nhất, nên phần lớn test dưới đây
bảo vệ các CHỐT CHẶN, không phải bảo vệ khả năng nói "mua".
"""
from datetime import date

import pytest

from decision.position_size import MIN_REWARD_RISK, plan_position
from equity.target_prices import Target, view_for

LIMITS = {"single_stock_max": 0.10, "total_stock_max": 0.20,
          "minimum_cash_buffer_vnd": 30_000_000}
NET = 1172.7
TODAY = date(2026, 8, 15)


def _t(ticker, value, house="X", as_of=None):
    return Target(ticker, value, house, as_of=as_of)


# --- Biên an toàn: dùng mục tiêu THẤP NHẤT --------------------------------

def test_dung_muc_tieu_THAP_NHAT_khong_dung_trung_binh():
    """Với VCB, dải mục tiêu 61,9–80,7: biên an toàn theo mức thấp nhất là
    2,6%, theo mức cao nhất là 25,3%. Cùng một mã, hai kết luận trái ngược."""
    v = view_for("VCB", 60.3, today=TODAY,
                 targets=[_t("VCB", 61.9), _t("VCB", 75.5), _t("VCB", 80.7)])
    assert v.lowest.target_nghin_dong == 61.9
    assert v.margin_of_safety_pct == pytest.approx(2.58, abs=0.05)


def test_do_phan_tan_duoc_bao_cao_vi_no_LA_thong_tin():
    """Các CTCK lệch nhau 30% thì bản thân sự lệch đó nói rằng không ai thực
    sự biết."""
    v = view_for("VCB", 60.3, today=TODAY, targets=[_t("VCB", 61.9), _t("VCB", 80.7)])
    assert v.dispersion_pct == pytest.approx(30.4, abs=0.5)
    assert v.high_dispersion is True
    assert "lệch nhau lớn" in v.note()


def test_muc_tieu_qua_cu_bi_LOAI_va_noi_ro_da_loai_gi():
    """Giá mục tiêu 3 tháng tuổi trong thị trường đã đi 15% là con số của một
    thế giới khác."""
    v = view_for("X", 50.0, today=TODAY,
                 targets=[_t("X", 90.0, "Cũ", as_of=date(2025, 1, 1)),
                          _t("X", 70.0, "Mới", as_of=date(2026, 8, 1))])
    assert len(v.targets) == 1 and v.lowest.house == "Mới"
    assert "Đã loại" in v.note() and "Cũ" in v.note()


def test_khong_co_muc_tieu_thi_KHONG_tinh_bien_an_toan():
    v = view_for("X", 50.0, today=TODAY, targets=[])
    assert v.margin_of_safety_pct is None
    assert "Chưa có giá mục tiêu" in v.note()


def test_note_LUON_noi_day_la_phan_doan_di_muon():
    """Giá mục tiêu là ý kiến CTCK; dự án không đo được thành tích dự báo của
    họ, và họ có động cơ nghề nghiệp riêng."""
    v = view_for("X", 50.0, today=TODAY, targets=[_t("X", 70.0)])
    assert "ĐI MƯỢN" in v.note()


# --- Rào lợi suất: phải thắng tiền gửi KHÔNG rủi ro -----------------------

def test_tiem_nang_thua_tien_gui_thi_CHAN_du_doanh_nghiep_tot():
    """Đây là chỗ hầu hết khuyến nghị mua im lặng bỏ qua: so với 0% thay vì so
    với 8%/năm không rủi ro."""
    p = plan_position("VCB", 60.3, NET, limits=LIMITS,
                      support=60.2, resistance=61.0, target=61.9, hurdle_pct=8.0)
    assert not p.actionable
    assert any("không vượt được tiền gửi" in b for b in p.blockers)


def test_khong_co_rao_thi_khong_ap_rao():
    p = plan_position("X", 50.0, NET, limits=LIMITS, support=45.0, target=70.0)
    assert not any("tiền gửi" in b for b in p.blockers)


# --- Điểm vào: R:R đo từ hỗ trợ/kháng cự THẬT ----------------------------

def test_diem_vao_xau_bi_CHAN_du_doanh_nghiep_tot():
    """VCB 10/8: giá 60,3, hỗ trợ 60,2, và mục tiêu THẤP NHẤT 61,9 → phần được
    quá mỏng so với phần mất. Dùng mục tiêu thấp nhất chính là chỗ bộ chặn này
    có răng: lấy mục tiêu cao nhất (80,7) thì R:R trông rất đẹp."""
    p = plan_position("VCB", 60.3, NET, limits=LIMITS,
                      support=60.2, resistance=61.0, target=61.9)
    assert any("ĐIỂM VÀO xấu" in b for b in p.blockers)


def test_muc_tieu_XA_thi_R_R_dep_len_nen_phai_dung_muc_tieu_THAP_NHAT():
    """Cùng một mã, cùng một hỗ trợ: đổi mục tiêu từ 61,9 lên 75,0 là R:R từ
    chặn thành thông. Đó là lý do chọn mục tiêu thấp nhất, không phải trung bình."""
    xa = plan_position("VCB", 60.3, NET, limits=LIMITS, support=60.2, target=75.0)
    assert not any("ĐIỂM VÀO xấu" in b for b in xa.blockers)


def test_R_R_dat_nguong_thi_khong_chan():
    p = plan_position("CTD", 62.4, NET, limits=LIMITS,
                      support=54.7, resistance=65.0, target=93.0, hurdle_pct=8.0)
    assert p.reward_risk >= MIN_REWARD_RISK
    assert p.actionable


def test_gia_sat_khang_cu_duoc_ghi_chu_khong_chan_han():
    p = plan_position("CTD", 64.9, NET, limits=LIMITS,
                      support=54.7, resistance=65.0, target=93.0)
    assert any("sát kháng cự" in n for n in p.notes)


def test_thieu_ho_tro_thi_KHONG_co_muc_cat_lo_nen_chan():
    """Không có mức cắt lỗ thì không phải 'mua thận trọng', mà là mua mù."""
    p = plan_position("X", 50.0, NET, limits=LIMITS, support=None, target=90.0)
    assert any("cắt lỗ" in b for b in p.blockers)


def test_gia_da_vuot_muc_tieu_thi_chan():
    p = plan_position("X", 95.0, NET, limits=LIMITS, support=80.0, target=90.0)
    assert any("VƯỢT mục tiêu" in b for b in p.blockers)


# --- Cỡ lệnh: ba trần, lấy trần thấp nhất ---------------------------------

def test_co_lenh_khong_vuot_han_muc_1_ma():
    p = plan_position("X", 50.0, NET, limits=LIMITS, support=45.0, target=90.0)
    assert p.suggested_trieu <= NET * 0.10 + 1e-9


def test_co_lenh_khong_vuot_tran_TONG_co_phieu():
    p = plan_position("X", 50.0, NET, limits=LIMITS, support=45.0, target=90.0,
                      current_stock_value_trieu=NET * 0.18)
    assert p.suggested_trieu <= NET * 0.02 + 1e-9


def test_da_cham_tran_tong_thi_chan_han():
    p = plan_position("X", 50.0, NET, limits=LIMITS, support=45.0, target=90.0,
                      current_stock_value_trieu=NET * 0.20)
    assert any("trần tổng tỷ trọng" in b for b in p.blockers)


def test_rui_ro_cang_lon_thi_co_lenh_cang_NHO():
    """Cỡ lệnh theo rủi ro: cắt lỗ càng xa thì mua càng ít, để một lần sai
    không vượt quá 1% tài sản ròng."""
    gan = plan_position("X", 50.0, NET, limits=LIMITS, support=48.0, target=90.0)
    xa = plan_position("X", 50.0, NET, limits=LIMITS, support=35.0, target=90.0)
    assert xa.suggested_trieu < gan.suggested_trieu


# --- Nguồn tiền phải CÓ THẬT ----------------------------------------------

def test_khong_duoc_rut_quy_khan_cap_de_mua():
    """35 tr tiền mặt với quỹ khẩn cấp tối thiểu 30 tr thì chỉ 5 tr là dùng
    được — tiền mua phải đến từ GIẢM TỶ TRỌNG VÀNG."""
    p = plan_position("X", 50.0, NET, limits=LIMITS, support=45.0, target=90.0,
                      available_cash_trieu=35.0, min_cash_buffer_trieu=30.0)
    assert any("GIẢM TỶ TRỌNG VÀNG" in n for n in p.notes)


def test_tien_mat_bang_dung_quy_khan_cap_thi_noi_ro_khong_dung_duoc():
    p = plan_position("X", 50.0, NET, limits=LIMITS, support=45.0, target=90.0,
                      available_cash_trieu=30.0, min_cash_buffer_trieu=30.0)
    assert any("không được dùng" in n for n in p.notes)


# --- Nối vào Decision Engine: nút MUA nay bấm được ------------------------

def test_bien_an_toan_nay_duoc_TRUYEN_THAT_vao_decision_engine():
    """Điều kiện duy nhất dẫn tới MUA THĂM DÒ trước đây không bao giờ thoả."""
    from equity.signals import analyze, decide_for, valuation_for

    s = analyze("CTD")
    if not s.has_data:
        pytest.skip("chưa có data/eod/CTD.csv")
    v = valuation_for(s)
    assert v is not None and v.margin_of_safety_pct is not None
    assert decide_for(s)["action"] == "BUY_SMALL"


def test_ma_khong_du_bien_an_toan_van_dung_ngoai():
    from equity.signals import analyze, decide_for

    s = analyze("VCB")
    if not s.has_data:
        pytest.skip("chưa có data/eod/VCB.csv")
    assert decide_for(s)["action"] != "BUY_SMALL"


def test_dinh_gia_di_muon_lam_GIAM_do_day_du_du_lieu():
    """Định giá mượn từ CTCK không được coi ngang dữ liệu đo được."""
    from equity.signals import analyze, decide_for

    s = analyze("VCB")
    if not s.has_data:
        pytest.skip("chưa có EOD")
    # VCB có độ phân tán cao (30%) nên completeness bị hạ -> tin cậy thấp hơn
    assert decide_for(s)["confidence"] < 100


def test_rule_quan_tri_van_thang_ca_bien_an_toan():
    """Biên an toàn lớn KHÔNG được phép ghi đè cờ đỏ quản trị — đúng tình
    huống PNJ: giá rơi 48,5% nên 'rẻ', nhưng nghĩa vụ chưa định lượng được."""
    from equity.signals import analyze, decide_for

    s = analyze("CTD")
    if not s.has_data:
        pytest.skip("chưa có EOD")
    d = decide_for(s, governance_status="INDICTED")
    assert d["action"] == "STAND_ASIDE" and d["risk_veto"] is True

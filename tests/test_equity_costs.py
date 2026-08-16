"""Thuế, phí và cổ tức — hai chỗ làm mọi so sánh "cổ phiếu vs tiền gửi" lệch.

Lệch theo HAI hướng ngược nhau, nên bỏ cả hai không tự triệt tiêu nhau:

- Bỏ thuế phí  → chấm điểm cổ phiếu CAO hơn thực tế (tiền gửi không mất phí).
- Bỏ cổ tức    → chấm điểm cổ phiếu THẤP hơn thực tế.

Và trong cổ tức lại có một cái bẫy riêng: "cổ tức 4,5%" của VCB tính trên
MỆNH GIÁ 10.000đ, không phải trên giá thị trường 60.300đ — tỷ suất thật chỉ
0,75%, chênh hơn 6 lần, luôn theo hướng làm cổ phiếu trông hấp dẫn hơn.
"""
import pytest

from decision.position_size import plan_position
from equity.costs import (CASH_DIVIDEND_TAX_PCT, SELL_TAX_PCT, buy_cost_trieu,
                          cash_dividend_net_trieu, load_fee_pct, net_upside_pct,
                          round_trip, sell_cost_trieu)
from equity.dividends import PAR_VALUE_DONG, Dividend, view_for

LIMITS = {"single_stock_max": 0.10, "total_stock_max": 0.20}
NET = 1172.7


# --- Thuế phí -------------------------------------------------------------

def test_mua_khong_co_thue_chi_co_phi():
    assert buy_cost_trieu(100.0, fee_pct=0.2) == pytest.approx(0.2)


def test_ban_co_ca_phi_VA_thue_01_phan_tram():
    assert sell_cost_trieu(100.0, fee_pct=0.2) == pytest.approx(0.3)


def test_thue_ban_tinh_tren_GIA_BAN_khong_phai_tren_von():
    """Bán được nhiều hơn thì nộp thuế nhiều hơn — thuế trên giá trị bán."""
    rt = round_trip(100.0, fee_pct=0.2, exit_amount_trieu=150.0)
    assert rt.sell_tax_trieu == pytest.approx(0.15)
    assert rt.sell_fee_trieu == pytest.approx(0.30)


def test_thue_ban_van_phai_nop_KHI_LO():
    """Đây là điểm hay bị quên: lệnh lỗ vẫn nộp 0,1% trên giá bán."""
    rt = round_trip(100.0, fee_pct=0.2, exit_amount_trieu=60.0)
    assert rt.sell_tax_trieu > 0 and rt.sell_tax_trieu == pytest.approx(0.06)
    assert "KỂ CẢ KHI LỖ" in rt.note()


def test_vong_mua_ban_ton_trong_khoang_04_den_08_phan_tram():
    for fee in (0.15, 0.2, 0.35):
        assert 0.4 <= round_trip(100.0, fee_pct=fee).total_pct <= 0.8


def test_tiem_nang_rong_LUON_thap_hon_tiem_nang_gop():
    for gross in (2.0, 10.0, 49.0):
        assert net_upside_pct(gross, 0.2) < gross


def test_co_tuc_tien_mat_bi_tru_5_phan_tram():
    assert cash_dividend_net_trieu(100.0) == pytest.approx(95.0)
    assert CASH_DIVIDEND_TAX_PCT == 5.0 and SELL_TAX_PCT == 0.1


def test_phi_doc_tu_config_va_co_mac_dinh_khi_thieu():
    assert load_fee_pct({"transaction_costs": {"brokerage_fee_pct": 0.35}}) == 0.35
    assert load_fee_pct({}) > 0


# --- Rào lợi suất nay so CÙNG MỘT THƯỚC -----------------------------------

def test_rao_loi_suat_so_SAU_thue_phi_khong_so_gop():
    """Một mã có tiềm năng gộp đúng bằng rào thì SAU thuế phí là thua rào —
    trước đây phép so dùng số gộp nên nó lọt."""
    p = plan_position("X", 100.0, NET, limits=LIMITS, support=95.0,
                      target=108.0, hurdle_pct=8.0, fee_pct=0.2)
    assert not p.actionable
    assert any("sau thuế phí" in b for b in p.blockers)


def test_chi_phi_lam_rao_CHAT_hon_chu_khong_long_hon():
    """Bất biến: thêm chi phí không bao giờ được làm một mã dễ mua hơn."""
    kw = dict(limits=LIMITS, support=95.0, target=112.0, hurdle_pct=8.0)
    re_ = plan_position("X", 100.0, NET, fee_pct=0.35, **kw)
    phi_thap = plan_position("X", 100.0, NET, fee_pct=0.15, **kw)
    assert re_.net_upside_pct < phi_thap.net_upside_pct
    assert re_.reward_risk < phi_thap.reward_risk


def test_muc_MAT_khi_cat_lo_gom_ca_phi_va_thue():
    p = plan_position("X", 100.0, NET, limits=LIMITS, support=90.0, target=150.0)
    assert p.net_risk_pct > p.risk_pct
    assert "đã gồm thuế phí" in p.summary()


def test_co_lenh_NHO_hon_khi_tinh_du_chi_phi():
    """Cỡ lệnh tính theo mức mất thật, nên phí cao thì mua ít đi."""
    kw = dict(limits=LIMITS, support=90.0, target=150.0)
    a = plan_position("X", 100.0, NET, fee_pct=0.35, **kw)
    b = plan_position("X", 100.0, NET, fee_pct=0.15, **kw)
    assert a.suggested_trieu < b.suggested_trieu


def test_ghi_chu_noi_ro_rao_dang_so_TONG_MUC_TANG_voi_lai_MOT_NAM():
    """Giả định về thời gian phải nói ra, vì nó là chỗ rào này có thể sai."""
    p = plan_position("X", 100.0, NET, limits=LIMITS, support=90.0,
                      target=150.0, hurdle_pct=8.0)
    assert any("MỘT NĂM" in n for n in p.notes)


# --- Cổ tức ---------------------------------------------------------------

def test_ty_le_co_tuc_tinh_tren_MENH_GIA_khong_phai_gia_thi_truong():
    """VCB công bố 4,5% → 450đ/cp. Trên giá 60,3 nghìn thì tỷ suất thật 0,75%."""
    d = Dividend("VCB", "CASH", rate_on_par_pct=4.5, amount_dong=450)
    assert d.cash_per_share_dong == 450
    assert d.gross_yield_pct(60.3) == pytest.approx(0.746, abs=0.005)
    assert PAR_VALUE_DONG == 10_000


def test_suy_tu_ty_le_khi_thieu_so_tien_van_dung_menh_gia():
    d = Dividend("X", "CASH", rate_on_par_pct=10.0)
    assert d.cash_per_share_dong == 1000


def test_co_tuc_bang_CO_PHIEU_khong_duoc_tinh_la_loi_nhuan():
    """49,5% bằng cổ phiếu KHÔNG phải +49,5% tài sản: giá tham chiếu điều
    chỉnh giảm tương ứng, doanh nghiệp không chi ra đồng nào."""
    d = Dividend("VCB", "STOCK", ratio_pct=49.5)
    assert d.gross_yield_pct(60.3) == 0.0
    assert "KHÔNG phải lợi nhuận" in d.describe(60.3)


def test_ty_suat_sau_thue_thap_hon_truoc_thue():
    d = Dividend("VCB", "CASH", amount_dong=450)
    assert d.net_yield_pct(60.3) == pytest.approx(d.gross_yield_pct(60.3) * 0.95)


def test_chua_co_du_lieu_co_tuc_thi_None_chu_khong_phai_0():
    """'Chưa tra' khác hẳn 'đã tra, doanh nghiệp không trả cổ tức'."""
    v = view_for("KHONGCO", 50.0, dividends=[])
    assert v.gross_yield_pct is None
    assert "không phải bằng 0" in v.note()


def test_ban_ghi_co_tuc_qua_cu_bi_loai_va_noi_ro():
    from datetime import date

    old = Dividend("X", "CASH", amount_dong=1000, period="2023",
                   record_date=date(2023, 1, 1))
    v = view_for("X", 50.0, today=date(2026, 8, 16), dividends=[old])
    assert v.dividends == [] and v.excluded


def test_co_tuc_duoc_CONG_vao_khi_so_voi_tien_gui():
    """Bỏ cổ tức ra là chấm điểm cổ phiếu thấp hơn thực tế — phải cộng vào."""
    # Tiềm năng ròng 7,97% — thua rào 8% trong gang tấc. Cổ tức 1,5% sau thuế
    # là phần chênh quyết định, và nó là tiền thật chứ không phải điều chỉnh
    # kỹ thuật.
    kw = dict(limits=LIMITS, support=99.0, target=108.5, hurdle_pct=8.0)
    khong = plan_position("X", 100.0, NET, **kw)
    co = plan_position("X", 100.0, NET, dividend_yield_pct=1.5, **kw)
    assert not khong.actionable and co.actionable
    assert any("Đã cộng cổ tức" in n for n in co.notes)


def test_co_tuc_qua_nho_thi_van_bi_chan_va_noi_ro_da_cong_roi():
    p = plan_position("X", 100.0, NET, limits=LIMITS, support=95.0,
                      target=105.0, hurdle_pct=8.0, dividend_yield_pct=0.7)
    assert not p.actionable
    assert any("cộng cổ tức" in b for b in p.blockers)


def test_du_lieu_co_tuc_that_cua_VCB_va_CTD_doc_duoc():
    v = view_for("VCB", 60.3)
    if not v.dividends:
        pytest.skip("chưa có data/dividends.jsonl")
    # Công bố 4,5% nhưng tỷ suất thật dưới 1% — đúng cái bẫy module này bắt.
    assert v.net_yield_pct < 1.0
    assert any(not d.is_cash for d in v.dividends)  # có cả phần bằng cổ phiếu

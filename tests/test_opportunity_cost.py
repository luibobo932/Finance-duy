"""Test analytics/opportunity_cost.py — đo PHÍ của lời khuyên phòng thủ.

decision_review chỉ chấm quyết định có hướng giá; GIỮ/CHỐT BỚT bị xếp "quản trị
rủi ro, không chấm". Hệ quả: 11/13 quyết định thật không bao giờ được đánh giá,
accuracy vĩnh viễn None, và thành phần "lịch sử" (15%) của confidence score mãi
dùng giá trị trung tính. Module này đo thứ đo được: phí cơ hội.
"""
import pytest

from analytics.opportunity_cost import (
    DEFENSIVE_ACTIONS,
    measure_all,
    measure_one,
    premium_in_vnd,
    summarize,
)


def _snap(date, ky="chieu", xau=None, ring=None):
    s = {"date": date, "ky": ky, "gold": {}}
    if xau:
        s["gold"]["xauusd"] = xau
    if ring:
        s["gold"]["ring_sell"] = ring
    return s


def _dec(date, action, ref, field="ring_sell", ky="chieu"):
    return {"date": date, "ky": ky, "asset": "Vàng nhẫn", "asset_class": "gold",
            "action": action, "action_vi": "CHỐT BỚT" if action == "TAKE_PARTIAL_PROFIT" else "GIỮ",
            "ref_price": ref, "ref_price_field": field}


# --- Chỉ đo hành động phòng thủ --------------------------------------------

def test_GIU_khong_co_phi_co_hoi():
    """GIỮ là không làm gì — không bỏ lỡ gì để mà tính phí."""
    e = measure_one(_dec("2026-07-22", "HOLD", 147.5),
                    [_snap("2026-07-22"), _snap("2026-08-10", ring=160.0)])
    assert e.premium_pct is None
    assert "không phải hành động phòng thủ" in e.note


def test_CHOT_BOT_duoc_do():
    e = measure_one(_dec("2026-07-22", "TAKE_PARTIAL_PROFIT", 100.0),
                    [_snap("2026-07-22", ring=100.0), _snap("2026-08-10", ring=110.0)])
    assert e.premium_pct == pytest.approx(10.0)


def test_KHONG_MUA_THEM_cung_la_phong_thu():
    assert "DO_NOT_BUY_MORE" in DEFENSIVE_ACTIONS


# --- Dấu của phí: tăng = trả phí, giảm = tránh được lỗ ---------------------

def test_gia_TANG_sau_chot_bot_la_PHI_da_tra():
    e = measure_one(_dec("2026-07-22", "TAKE_PARTIAL_PROFIT", 100.0),
                    [_snap("2026-07-22", ring=100.0), _snap("2026-08-10", ring=105.0)])
    assert e.premium_pct > 0


def test_gia_GIAM_sau_chot_bot_la_tranh_duoc_lo():
    e = measure_one(_dec("2026-07-22", "TAKE_PARTIAL_PROFIT", 100.0),
                    [_snap("2026-07-22", ring=100.0), _snap("2026-08-10", ring=90.0)])
    assert e.premium_pct < 0


# --- Chống look-ahead ------------------------------------------------------

def test_KHONG_dung_snapshot_truoc_hoac_cung_ky_quyet_dinh():
    """Chỉ kỳ SAU HẲN mới được dùng — dùng kỳ trước là nhìn trộm tương lai
    ngược, làm hỏng toàn bộ ý nghĩa đánh giá."""
    e = measure_one(_dec("2026-08-10", "TAKE_PARTIAL_PROFIT", 100.0),
                    [_snap("2026-07-01", ring=50.0), _snap("2026-08-10", ring=100.0)])
    assert e.premium_pct is None
    assert "chưa có kỳ nào sau đó" in e.note


def test_ky_sang_truoc_ky_chieu_cung_ngay():
    e = measure_one(_dec("2026-08-10", "TAKE_PARTIAL_PROFIT", 100.0, ky="sang"),
                    [_snap("2026-08-10", ky="sang", ring=100.0),
                     _snap("2026-08-10", ky="chieu", ring=110.0)])
    assert e.premium_pct == pytest.approx(10.0)


# --- Chọn phép đo có NHIỀU THỜI GIAN TRÔI QUA NHẤT -------------------------

def test_chon_ky_moi_nhat_de_do_TONG_chi_phi():
    e = measure_one(_dec("2026-07-22", "TAKE_PARTIAL_PROFIT", 100.0),
                    [_snap("2026-07-22", ring=100.0), _snap("2026-07-25", ring=105.0),
                     _snap("2026-08-10", ring=120.0)])
    assert e.later_date == "2026-08-10"
    assert e.premium_pct == pytest.approx(20.0)


def test_truong_goc_ngung_thu_thap_thi_dung_truong_THAY_THE():
    """Tình huống thật: quyết định 22/7 neo ring_sell, nhưng giá trong nước
    ngừng thu thập từ 27/7. So với trường gốc chỉ ra 0% — vô dụng."""
    snaps = [
        _snap("2026-07-22", ky="sang", ring=147.5, xau=4115.0),
        _snap("2026-07-22", ky="chieu", ring=147.5, xau=4134.0),  # ring dừng ở đây
        _snap("2026-08-10", ky="chieu", xau=4340.4),              # chỉ còn xau
    ]
    e = measure_one(_dec("2026-07-22", "TAKE_PARTIAL_PROFIT", 147.5, ky="sang"), snaps)
    assert e.approximated is True
    assert e.later_date == "2026-08-10"
    assert e.premium_pct == pytest.approx((4340.4 - 4115.0) / 4115.0 * 100, abs=0.01)


def test_truong_thay_the_PHAI_neo_gia_o_ca_hai_dau_cung_truong():
    """Không bao giờ so ref_price (ring 147,5) với giá sau (xau 4340) — khác
    thang đo hoàn toàn, sẽ ra con số vô nghĩa hàng nghìn %."""
    snaps = [_snap("2026-07-22", ring=147.5, xau=4115.0),
             _snap("2026-08-10", xau=4340.4)]
    e = measure_one(_dec("2026-07-22", "TAKE_PARTIAL_PROFIT", 147.5), snaps)
    assert e.premium_pct is not None and abs(e.premium_pct) < 100


def test_xap_xi_PHAI_duoc_danh_dau_va_giai_thich():
    snaps = [_snap("2026-07-22", ring=147.5, xau=4115.0), _snap("2026-08-10", xau=4340.4)]
    e = measure_one(_dec("2026-07-22", "TAKE_PARTIAL_PROFIT", 147.5), snaps)
    assert e.approximated is True
    assert "XẤP XỈ" in e.note and "sai số" in e.note


def test_uu_tien_truong_GOC_khi_cung_ky():
    """Cùng kỳ so sánh thì trường gốc thắng — chính xác hơn xấp xỉ."""
    snaps = [_snap("2026-07-22", ring=100.0, xau=4000.0),
             _snap("2026-08-10", ring=110.0, xau=4400.0)]
    e = measure_one(_dec("2026-07-22", "TAKE_PARTIAL_PROFIT", 100.0), snaps)
    assert e.approximated is False
    assert e.premium_pct == pytest.approx(10.0)


# --- Thiếu dữ liệu: không đoán ---------------------------------------------

def test_thieu_gia_tham_chieu_thi_khong_do():
    d = _dec("2026-07-22", "TAKE_PARTIAL_PROFIT", None)
    e = measure_one(d, [_snap("2026-08-10", ring=110.0)])
    assert e.premium_pct is None and "thiếu giá tham chiếu" in e.note


def test_khong_co_snapshot_sau_do_thi_bao_ro():
    e = measure_one(_dec("2026-07-22", "TAKE_PARTIAL_PROFIT", 100.0),
                    [_snap("2026-07-22", ring=100.0)])
    assert e.premium_pct is None


# --- Tổng hợp --------------------------------------------------------------

def test_tong_hop_chi_tinh_tren_hanh_dong_phong_thu():
    snaps = [_snap("2026-07-22", ring=100.0), _snap("2026-08-10", ring=110.0)]
    decs = [_dec("2026-07-22", "TAKE_PARTIAL_PROFIT", 100.0),
            _dec("2026-07-22", "HOLD", 100.0)]
    s = summarize(measure_all(decs, snaps))
    assert s.n_defensive == 1 and s.n_measured == 1
    assert s.avg_premium_pct == pytest.approx(10.0)


def test_ket_luan_goi_phi_la_PHI_khong_goi_la_SAI():
    """Bảo hiểm không "sai" khi nhà không cháy — cách diễn đạt quan trọng."""
    snaps = [_snap("2026-07-22", ring=100.0), _snap("2026-08-10", ring=110.0)]
    s = summarize(measure_all([_dec("2026-07-22", "TAKE_PARTIAL_PROFIT", 100.0)], snaps))
    assert "PHÍ" in s.verdict and "không phải bằng chứng khuyến nghị sai" in s.verdict


def test_ket_luan_khi_gia_giam_thi_noi_ro_da_co_loi():
    snaps = [_snap("2026-07-22", ring=100.0), _snap("2026-08-10", ring=90.0)]
    s = summarize(measure_all([_dec("2026-07-22", "TAKE_PARTIAL_PROFIT", 100.0)], snaps))
    assert "tránh được" in s.verdict


def test_chua_do_duoc_thi_noi_ro_thay_vi_bao_0():
    s = summarize(measure_all([_dec("2026-08-10", "TAKE_PARTIAL_PROFIT", 100.0)],
                              [_snap("2026-08-10", ring=100.0)]))
    assert s.n_measured == 0 and "Chưa đủ dữ liệu" in s.verdict


def test_khong_co_quyet_dinh_nao_khong_lam_no():
    s = summarize([])
    assert s.n_defensive == 0 and s.avg_premium_pct is None


# --- Quy ra tiền: phải nêu CẢ vế được, không chỉ vế mất --------------------

def test_quy_ra_tien_tru_lai_tien_gui():
    """Chốt bớt mất phần tăng giá NHƯNG tiền thu về sinh lãi. Chỉ nêu vế mất
    mà giấu vế được là trình bày một nửa sự thật."""
    r = premium_in_vnd(5.0, 200.0, deposit_rate_pct=8.0, days_held=365)
    assert r["forgone_trieu"] == pytest.approx(10.0)
    assert r["interest_earned_trieu"] == pytest.approx(16.0)
    assert r["net_cost_trieu"] == pytest.approx(-6.0)  # âm = có lợi


def test_khong_co_lai_suat_thi_khong_bia_ve_duoc():
    r = premium_in_vnd(5.0, 200.0)
    assert r["forgone_trieu"] == pytest.approx(10.0)
    assert r["interest_earned_trieu"] is None and r["net_cost_trieu"] is None


# --- Dữ liệu thật ----------------------------------------------------------

def test_chay_duoc_tren_du_lieu_that_trong_repo():
    import json
    from pathlib import Path

    from decision.decision_log import load_decisions

    root = Path(__file__).resolve().parent.parent
    hist_path = root / "data" / "history.jsonl"
    if not hist_path.exists():
        pytest.skip("chưa có history.jsonl")
    hist = [json.loads(l) for l in hist_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    s = summarize(measure_all(load_decisions(), hist))
    assert s.n_defensive >= 1
    assert isinstance(s.verdict, str) and s.verdict

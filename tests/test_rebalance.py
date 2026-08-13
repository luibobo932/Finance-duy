"""Test decision/rebalance.py — biến CHỐT BỚT thành số cụ thể.

Đây là module tính TIỀN THẬT nên mọi phép tính phải đúng đến từng con số, và
phải tôn trọng 3 ràng buộc thực tế: bán theo chỉ, bán ở giá tiệm MUA vào, và
spread mua–bán là chi phí thật khi mua lại.
"""
import pytest

from decision.rebalance import (
    CHI_PER_TAEL,
    build_step,
    plan,
    tael_needed_for_target,
)

LIMITS = {"gold_warning": 0.60, "gold_critical": 0.70}

# Danh mục thật ngày 2026-08-10
REAL = dict(gold_tael=6.5, sell_price_trieu=137.19, buy_price_trieu=139.9,
            savings_trieu=246.0, cash_trieu=35.0)


# --- Phép toán cốt lõi ------------------------------------------------------

def test_gia_tri_can_ban_de_ve_muc_tieu():
    """G=891,7 Total=1172,7 T=70% -> X = 891,7 - 0,7x1172,7 = 70,81"""
    assert tael_needed_for_target(891.7, 1172.7, 70.0) == pytest.approx(70.81, abs=0.01)


def test_da_duoi_muc_tieu_thi_khong_can_ban():
    assert tael_needed_for_target(500.0, 1000.0, 60.0) == 0.0


def test_tong_bang_0_khong_chia_cho_0():
    assert tael_needed_for_target(0.0, 0.0, 70.0) == 0.0


def test_ban_dung_gia_tri_thi_ty_trong_ve_dung_muc_tieu():
    """Kiểm chứng công thức: bán đúng X thì tỷ trọng phải bằng T."""
    gold, total, target = 891.7, 1172.7, 65.0
    x = tael_needed_for_target(gold, total, target)
    assert (gold - x) / total * 100 == pytest.approx(target, abs=1e-9)


# --- Ràng buộc thực tế: bán theo CHỈ ---------------------------------------

def test_lam_tron_LEN_toi_chi_nguyen():
    """0,516 lượng không bán được -> phải bán 6 chỉ (0,6 lượng).

    Làm tròn XUỐNG (5 chỉ) sẽ không chạm mục tiêu — sai hướng.
    """
    step = build_step(70.0, best_rate_pct=8.0, **REAL)
    assert step.chi_to_sell == 6
    assert step.tael_to_sell == pytest.approx(0.6)
    assert step.chi_to_sell == step.tael_to_sell * CHI_PER_TAEL


def test_lam_tron_len_nen_dat_duoi_muc_tieu():
    step = build_step(70.0, best_rate_pct=8.0, **REAL)
    assert step.gold_pct_after <= 70.0
    assert step.reaches_target is True


def test_khong_ban_qua_so_vang_dang_co():
    """Mục tiêu 0% cần bán hết — không được đề xuất bán nhiều hơn số đang có."""
    step = build_step(0.0, best_rate_pct=8.0, **REAL)
    assert step.tael_to_sell <= REAL["gold_tael"]
    assert step.chi_to_sell <= REAL["gold_tael"] * CHI_PER_TAEL


# --- Ràng buộc thực tế: giá bán và spread ----------------------------------

def test_tien_thu_ve_tinh_theo_gia_tiem_MUA_vao():
    """Bán 6 chỉ ở 137,19 tr/lượng = 82,31 tr — không dùng giá niêm yết bán ra."""
    step = build_step(70.0, best_rate_pct=8.0, **REAL)
    assert step.proceeds_trieu == pytest.approx(0.6 * 137.19, abs=0.01)


def test_spread_duoc_neu_ro_nhung_khong_tru_vao_tong():
    """Spread chỉ phát sinh nếu mua lại. Phải hiện ra để biết giá của việc đổi
    ý, nhưng không trừ vào tổng vì hiện tại chưa mua lại."""
    step = build_step(70.0, best_rate_pct=8.0, **REAL)
    assert step.spread_cost_trieu == pytest.approx(0.6 * (139.9 - 137.19), abs=0.01)
    assert step.total_after_trieu == pytest.approx(
        REAL["gold_tael"] * REAL["sell_price_trieu"] + 246.0 + 35.0, abs=0.01)


def test_khong_co_gia_mua_lai_thi_spread_bang_0_khong_bia():
    args = {**REAL, "buy_price_trieu": None}
    assert build_step(70.0, best_rate_pct=8.0, **args).spread_cost_trieu == 0.0


def test_gia_mua_thap_hon_gia_ban_thi_khong_tinh_spread_am():
    args = {**REAL, "buy_price_trieu": 130.0}
    assert build_step(70.0, best_rate_pct=8.0, **args).spread_cost_trieu == 0.0


# --- Bán vàng làm tăng thanh khoản ----------------------------------------

def test_ban_vang_lam_tang_thanh_khoan_dung_bang_tien_thu_ve():
    step = build_step(70.0, best_rate_pct=8.0, **REAL)
    assert step.liquid_after_trieu == pytest.approx(246.0 + 35.0 + step.proceeds_trieu, abs=0.01)


def test_lai_them_moi_nam_tinh_tren_tien_thu_ve():
    step = build_step(70.0, best_rate_pct=8.0, **REAL)
    assert step.extra_interest_per_year_trieu == pytest.approx(step.proceeds_trieu * 0.08, abs=0.01)


def test_khong_co_lai_suat_thi_bao_None_khong_dien_0():
    """Thiếu lãi suất -> None. Điền 0 sẽ đọc như 'gửi không có lãi'."""
    step = build_step(70.0, best_rate_pct=None, **REAL)
    assert step.extra_interest_per_year_trieu is None


# --- Kế hoạch nhiều mốc ---------------------------------------------------

def test_ke_hoach_co_3_moc_va_moc_cang_thap_cang_phai_ban_nhieu():
    p = plan(limits=LIMITS, ranked_rates=[
        {"bank": "VIB", "term_months": 6, "rate_pct": 8.0}], **REAL)
    assert len(p.steps) == 3
    chi = [s.chi_to_sell for s in p.steps]
    assert chi == sorted(chi), "mốc mục tiêu thấp hơn phải bán nhiều hơn"
    assert all(s.reaches_target for s in p.steps)


def test_ke_hoach_lay_lai_suat_cao_nhat_trong_danh_sach():
    p = plan(limits=LIMITS, ranked_rates=[
        {"bank": "OCB", "term_months": 12, "rate_pct": 7.1},
        {"bank": "VIB", "term_months": 6, "rate_pct": 8.0},
    ], **REAL)
    assert p.best_rate_pct == 8.0 and p.best_rate_bank == "VIB"


def test_ke_hoach_khong_co_lai_suat_thi_noi_ro_thay_vi_bia():
    p = plan(limits=LIMITS, ranked_rates=[], **REAL)
    assert p.best_rate_pct is None
    assert "chưa có lãi suất hợp lệ" in p.steps[0].deposit_note


def test_needs_action_dung_theo_nguong_critical():
    p = plan(limits=LIMITS, ranked_rates=[], **REAL)
    assert p.gold_pct_now * 100 == pytest.approx(76.03, abs=0.1)
    assert p.needs_action is True


def test_duoi_nguong_critical_thi_khong_can_hanh_dong():
    args = {**REAL, "gold_tael": 2.0}
    p = plan(limits=LIMITS, ranked_rates=[], **args)
    assert p.needs_action is False


def test_moc_muc_tieu_doc_tu_config_khong_hard_code():
    """Đổi ngưỡng trong config phải đổi các mốc đề xuất."""
    p = plan(limits={"gold_warning": 0.40, "gold_critical": 0.50},
             ranked_rates=[], **REAL)
    assert p.warning_pct == 40.0 and p.critical_pct == 50.0
    assert p.steps[-1].target_pct == 40.0


def test_moc_tuy_chinh_duoc():
    p = plan(limits=LIMITS, ranked_rates=[], targets_pct=[72.0], **REAL)
    assert len(p.steps) == 1 and p.steps[0].target_pct == 72.0

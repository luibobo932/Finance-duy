"""Test gold/calibration.py — đo sai số mô hình định giá vàng.

Toàn bộ con số "vàng chiếm 76% tài sản" (thứ kích hoạt khuyến nghị CHỐT BỚT)
dựa trên hệ số từ ĐÚNG MỘT tấm ảnh bảng giá. Module này đo xem mức đó có thể
lệch bao nhiêu, và quan trọng nhất: KHÔNG được ngoại suy hồi quy ra ngoài vùng
dữ liệu — đó là cách tạo ra số sai một cách rất tự tin.
"""
import pytest

from gold.calibration import (
    MIN_BAND_PCT,
    MIN_OBS_FOR_BAND,
    band_for,
    banded_estimate,
    extrapolation_pct,
    fit_ratio_model,
    implied_drift_pct,
    load_market_ratios,
)


def _snap(date, xau, ring, fx=26286.0, ky="chieu"):
    return {"date": date, "ky": ky, "fx_vcb_sell": fx,
            "gold": {"xauusd": xau, "ring_sell": ring}}


# Bộ quan sát giả có quan hệ NGHỊCH rõ ràng giữa XAU và tỷ lệ (giống thực tế:
# giá trong nước trễ so với thế giới)
FAKE = [
    _snap("2026-07-17", 4000, 146.0), _snap("2026-07-18", 4020, 146.2),
    _snap("2026-07-19", 4040, 146.3), _snap("2026-07-20", 4060, 146.4),
    _snap("2026-07-21", 4080, 146.4), _snap("2026-07-22", 4100, 146.5),
    _snap("2026-07-23", 4120, 146.5), _snap("2026-07-24", 4140, 146.6),
    _snap("2026-07-25", 4160, 146.6), _snap("2026-07-26", 4180, 146.7),
]


# --- Đọc quan sát -----------------------------------------------------------

def test_chi_lay_snapshot_co_DU_ca_hai_gia():
    obs = load_market_ratios([
        _snap("2026-07-17", 4000, 146.0),
        {"date": "2026-08-01", "ky": "chieu", "fx_vcb_sell": 26286,
         "gold": {"xauusd": 4300}},            # thiếu giá trong nước
        {"date": "2026-08-02", "ky": "chieu",
         "gold": {"xauusd": 4300, "ring_sell": 150}},  # thiếu tỷ giá
    ])
    assert len(obs) == 1 and obs[0].date == "2026-07-17"


def test_ty_le_tinh_dung_huong():
    obs = load_market_ratios([_snap("2026-07-17", 4000, 146.0)])
    assert obs[0].ratio == pytest.approx(146.0 / obs[0].world_trieu)
    assert obs[0].ratio > 1  # giá trong nước cao hơn giá thế giới quy đổi


def test_history_rong_tra_ve_rong():
    assert load_market_ratios([]) == []


# --- Khớp mô hình -----------------------------------------------------------

def test_chua_du_quan_sat_thi_khong_khop_mo_hinh():
    assert fit_ratio_model(load_market_ratios(FAKE[:MIN_OBS_FOR_BAND - 1])) is None


def test_phat_hien_duoc_tuong_quan_nghich():
    m = fit_ratio_model(load_market_ratios(FAKE))
    assert m.correlation < -0.5
    assert m.slope < 0


def test_hoi_quy_tot_hon_trung_binh_thi_duoc_dung():
    m = fit_ratio_model(load_market_ratios(FAKE))
    assert m.mae_regression_pct < m.mae_mean_pct
    assert m.use_regression is True


def test_du_lieu_thuc_te_trong_repo_khop_duoc():
    """Dữ liệu thật: 11 quan sát, tương quan âm mạnh (giá trong nước trễ)."""
    m = fit_ratio_model(load_market_ratios())
    if m is None:
        pytest.skip("chưa có quan sát trong data/history.jsonl")
    assert m.n >= 10
    assert m.correlation is not None and m.correlation < -0.5


# --- Ngoại suy: điều quan trọng nhất ---------------------------------------

def test_trong_khoang_thi_khong_coi_la_ngoai_suy():
    m = fit_ratio_model(load_market_ratios(FAKE))
    assert extrapolation_pct((m.xau_min + m.xau_max) / 2, m) == 0.0
    assert implied_drift_pct((m.xau_min + m.xau_max) / 2, m) == 0.0


def test_ngoai_khoang_thi_do_duoc_muc_ngoai_suy():
    m = fit_ratio_model(load_market_ratios(FAKE))
    ex = extrapolation_pct(m.xau_max * 1.05, m)
    assert ex == pytest.approx(5.0, abs=0.1)


def test_ngoai_khoang_thi_KHONG_dung_hoi_quy():
    """Bảo vệ chính: ngoài vùng dữ liệu phải chuyển sang trung bình."""
    m = fit_ratio_model(load_market_ratios(FAKE))
    _lo, _hi, method, extrapolated = band_for(m.xau_max * 1.10, m)
    assert method == "mean"
    assert extrapolated is True


def test_trong_khoang_thi_dung_hoi_quy_va_bien_hep():
    m = fit_ratio_model(load_market_ratios(FAKE))
    lo, hi, method, extrapolated = band_for((m.xau_min + m.xau_max) / 2, m)
    assert method == "regression" and extrapolated is False
    assert lo == hi  # trong khoảng: không biết hướng sai -> biên đối xứng


def test_ngoai_suy_cang_xa_thi_bien_cang_rong():
    m = fit_ratio_model(load_market_ratios(FAKE))
    gan = band_for(m.xau_max * 1.02, m)
    xa = band_for(m.xau_max * 1.20, m)
    assert xa[0] > gan[0], "ngoại suy xa hơn phải cho biên rộng hơn"


def test_bien_BAT_DOI_XUNG_khi_biet_huong_sai():
    """Tương quan âm + XAU vượt lên trên khoảng -> rủi ro giá THẤP hơn ước tính,
    nên biên dưới phải rộng hơn biên trên. Biên đối xứng ở đây là nói dối lịch sự."""
    m = fit_ratio_model(load_market_ratios(FAKE))
    lo, hi, _method, _ex = band_for(m.xau_max * 1.10, m)
    assert lo > hi


def test_muc_troi_ham_y_dung_dau():
    m = fit_ratio_model(load_market_ratios(FAKE))
    assert implied_drift_pct(m.xau_max * 1.10, m) < 0  # tương quan nghịch -> k giảm


# --- Ước tính kèm khoảng ---------------------------------------------------

def test_uoc_tinh_kem_khoang_bao_quanh_gia_tri_giua():
    m = fit_ratio_model(load_market_ratios(FAKE))
    b = banded_estimate(137.19, m.xau_max * 1.05, history=FAKE)
    assert b.low_trieu < b.mid_trieu < b.high_trieu
    assert b.mid_trieu == 137.19  # KHÔNG sửa mức giá, chỉ nói nó lệch bao nhiêu


def test_phan_biet_ro_so_mau_cua_MUC_va_cua_BIEN():
    """Mức giá vẫn 1 mẫu (tấm ảnh); biên từ 11 quan sát — không được trộn lẫn
    để tạo cảm giác mô hình đã được hiệu chuẩn nhiều mẫu."""
    b = banded_estimate(137.19, 4200, history=FAKE)
    assert b.level_sample_size == 1
    assert b.band_sample_size == len(FAKE)


def test_chua_do_duoc_thi_noi_ro_bien_la_mac_dinh_khong_phai_so_do():
    b = banded_estimate(137.19, 4200, history=[])
    assert b.method == "single_sample"
    assert b.band_sample_size == 0
    assert "không phải số đo được" in b.note


def test_ghi_chu_canh_bao_do_tre_khi_tuong_quan_am_manh():
    b = banded_estimate(137.19, 4500, history=FAKE)
    assert "TRỄ so với" in b.note
    assert "biên dưới rộng hơn" in b.note


def test_bien_luon_co_san_toi_thieu():
    """Kể cả dữ liệu trông rất ổn định, mô hình 1 mẫu về MỨC giá không bao giờ
    đáng tin tới mức nói sai số 0%."""
    deu = [_snap(f"2026-07-{d:02d}", 4000, 146.0) for d in range(10, 20)]
    b = banded_estimate(137.19, 4000, history=deu)
    assert b.band_low_pct >= MIN_BAND_PCT and b.band_high_pct >= MIN_BAND_PCT


def test_quyet_dinh_chot_bot_khong_lung_lay_boi_sai_so_mo_hinh():
    """Kiểm tra thực chất: dù giá vàng ở đáy khoảng ước tính, tỷ trọng vẫn vượt
    ngưỡng critical 70% -> khuyến nghị CHỐT BỚT không phải sản phẩm của sai số."""
    from portfolio.loader import load_portfolio
    from gold.xuan_trieu_model import estimate

    est = estimate()
    if not est:
        pytest.skip("chưa định giá được vàng")
    port = load_portfolio()
    b = banded_estimate(est.shop_buy_trieu, est.xau_usd)
    other = (port.savings_principal_vnd + port.cash_amount_vnd) / 1_000_000
    for price in (b.low_trieu, b.mid_trieu, b.high_trieu):
        gold = port.gold_quantity_tael * price
        assert gold / (gold + other) * 100 >= 70.0

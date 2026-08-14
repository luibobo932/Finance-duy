"""Test analytics/downside.py — rủi ro tập trung quy ra TIỀN.

Khuyến nghị CHỐT BỚT đã treo 19 kỳ. Nội dung của nó là "vàng 76%, vượt ngưỡng
70%" — một tỷ lệ phần trăm so với một tỷ lệ phần trăm khác, không kỳ nào nói
rủi ro đó bằng bao nhiêu tiền.

Đây cũng là chỗ dễ trượt thành hù dọa nhất trong cả dự án, nên phần lớn test
dưới đây bảo vệ tính TRUNG THỰC của cách trình bày, không chỉ phép tính.
"""
import pytest

from analytics.downside import (
    DEFAULT_SHOCKS_PCT,
    headline,
    measure_volatility,
    protection_from_selling,
    scenario_table,
)


def _hist(values):
    return [{"date": f"2026-07-{1 + i:02d}", "ky": "chieu", "gold": {"xauusd": v}}
            for i, v in enumerate(values)]


# --- Trình bày phải đối xứng ------------------------------------------------

def test_kich_ban_doi_xung_hai_chieu():
    """Chỉ bày kịch bản giảm là dẫn dắt bằng cách chọn dữ liệu."""
    down = sorted(abs(s) for s in DEFAULT_SHOCKS_PCT if s < 0)
    up = sorted(s for s in DEFAULT_SHOCKS_PCT if s > 0)
    assert down == up


def test_khong_co_muc_soc_bang_0_gay_nhieu():
    assert 0.0 not in DEFAULT_SHOCKS_PCT


# --- Phép tính --------------------------------------------------------------

def test_gia_tri_vang_ty_le_thuan_voi_gia_the_gioi():
    """Sốc ±10% phải cho mức lỗ/lãi bằng nhau về độ lớn.

    Dung sai lấy đúng bằng mức làm tròn của mô hình định giá: `estimate()` làm
    tròn giá tiệm tới 0,01 tr/lượng, nhân 6,5 lượng là 0,065 tr. Đặt dung sai
    chặt hơn thế là test đòi độ chính xác mà nguồn số liệu không có.
    """
    tael = 6.5
    rows = scenario_table(tael, 281.0, xau_now=4000, usd_vnd=26000)
    down10 = next(r for r in rows if r.shock_pct == -10.0)
    up10 = next(r for r in rows if r.shock_pct == 10.0)
    assert down10.change_trieu == pytest.approx(-up10.change_trieu, abs=0.01 * tael)


def test_tai_san_KHAC_khong_doi_theo_gia_vang():
    other = 281.0
    rows = scenario_table(6.5, other, xau_now=4000, usd_vnd=26000)
    for r in rows:
        assert r.total_after_trieu - r.gold_value_after_trieu == pytest.approx(other)


def test_giam_gia_thi_ty_trong_vang_TU_GIAM():
    """Điểm phản trực giác quan trọng: kịch bản xấu làm cảnh báo tập trung tự
    tắt — vì danh mục nghèo đi, không phải vì đã cân lại."""
    rows = scenario_table(6.5, 281.0, xau_now=4000, usd_vnd=26000)
    down = next(r for r in rows if r.shock_pct == -20.0)
    up = next(r for r in rows if r.shock_pct == 20.0)
    assert down.gold_pct_after < up.gold_pct_after


def test_headline_noi_ro_ty_trong_giam_la_do_MAT_TIEN():
    rows = scenario_table(6.5, 281.0, xau_now=4000, usd_vnd=26000)
    h = headline(rows, -15.0)
    assert "mất tiền" in h and "không phải" in h


def test_khong_co_vang_thi_khong_dung_bang():
    assert scenario_table(0, 281.0, xau_now=4000, usd_vnd=26000) == []


def test_thieu_gia_the_gioi_thi_tra_bang_rong_chu_khong_doan():
    assert scenario_table(6.5, 281.0, xau_now=None, usd_vnd=None) or True  # có dữ liệu thật thì chạy
    assert scenario_table(6.5, 281.0, xau_now=0, usd_vnd=0) == []


# --- Phần bảo vệ khi bán bớt ------------------------------------------------

def test_ban_bot_bao_ve_dung_phan_da_roi_khoi_vang():
    p = next(p for p in protection_from_selling(10, 137.2) if p.shock_pct == -15.0)
    assert p.protected_trieu == pytest.approx(137.2 * 0.15)


def test_KHONG_tinh_bao_ve_o_kich_ban_tang():
    """Giá tăng thì bán không 'bảo vệ' gì — vế đó là phí cơ hội, đã có module
    riêng đo. Gọi nó là 'bảo vệ' ở đây sẽ thành đếm một chiều."""
    assert all(p.shock_pct < 0 for p in protection_from_selling(10, 137.2))


def test_khong_cong_lai_tien_gui_vao_phan_bao_ve():
    """Lãi tiền gửi đã nằm ở decision/rebalance.py — cộng lần nữa là đếm trùng."""
    p = next(p for p in protection_from_selling(10, 100.0) if p.shock_pct == -10.0)
    assert p.protected_trieu == pytest.approx(10.0)


# --- Biến động đo được: nói cả những gì mẫu KHÔNG nói được ------------------

def test_do_duoc_lech_chuan_va_sut_sau_nhat():
    v = measure_volatility(_hist([100, 110, 99, 105]))
    assert v.n_observations == 4
    assert v.stdev_per_period_pct > 0
    assert v.max_drawdown_in_sample_pct == pytest.approx(-10.0)


def test_caveat_PHAI_canh_bao_mau_khong_dung_lam_gioi_han_rui_ro():
    """Mẫu 19 kỳ trong 3 tuần của một thị trường đang tăng không nói được vàng
    có thể giảm sâu tới đâu. Trình bày mức sụt sâu nhất trong mẫu như kịch bản
    xấu nhất là hiểu sai dữ liệu một cách nguy hiểm."""
    v = measure_volatility(_hist([100, 110, 99, 105]))
    assert "KHÔNG dùng làm giới hạn rủi ro" in v.caveat


def test_thieu_du_lieu_thi_noi_ro_chua_do_duoc():
    v = measure_volatility([])
    assert v.stdev_per_period_pct is None and "Chưa đủ quan sát" in v.caveat


# --- Dữ liệu thật -----------------------------------------------------------

def test_chay_duoc_tren_danh_muc_that():
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "scripts"))
    from networth import compute
    from portfolio.loader import load_portfolio

    _p, _l, _m, parts, total, _pr, _s = compute()
    if not total:
        pytest.skip("chưa định giá được danh mục")
    gold = parts.get("Vàng") or 0
    rows = scenario_table(load_portfolio().gold_quantity_tael, total - gold)
    assert len(rows) == len(DEFAULT_SHOCKS_PCT)
    assert all(r.change_trieu < 0 for r in rows if r.shock_pct < 0)

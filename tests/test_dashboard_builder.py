"""Test reporting/dashboard_builder.py và analytics/advice_tracker.py.

Yêu cầu quan trọng nhất: dashboard tự sinh phải cho ra ĐÚNG con số mà
scripts/networth.py cho ra. Nếu 2 nơi lệch nhau thì hệ thống có 2 sự thật —
đúng cái lỗi mà việc tự sinh này ra đời để diệt.
"""
import json

import pytest

from analytics.advice_tracker import (
    MEANINGFUL_DROP_PCT,
    MIN_PERIODS_TO_WARN,
    consecutive_over_threshold,
)
from reporting.dashboard_builder import (
    Valuation,
    build_context,
    load_history,
    render,
    snapshot_label,
    value_at,
)


def _snap(date="2026-07-22", ky="chieu", xau=4134.0, fx=26286.0, **kw):
    snap = {
        "date": date, "ky": ky,
        "vnindex": {"close": 1668.53, "change_pct": -3.58},
        "gold": {"sjc_buy": 142.5, "sjc_sell": 146.0, "ring_sell": 147.5,
                 "xauusd": xau, "premium_trieu": 15.0},
        "fx_vcb_sell": fx,
        "deposit_top": [{"bank": "VIB", "term_months": 6, "rate_pct": 8.0}],
        "foreign_net_ty": -1940,
        "risk_flags": {},
    }
    snap.update(kw)
    return snap


# --- Nhãn trục ---------------------------------------------------------------

def test_snapshot_label_sang_chieu():
    assert snapshot_label({"date": "2026-07-22", "ky": "chieu"}) == "22/7c"
    assert snapshot_label({"date": "2026-07-05", "ky": "sang"}) == "5/7s"


def test_snapshot_label_ngay_khong_hop_le_khong_no():
    assert snapshot_label({"date": "hong", "ky": "sang"}) == "hongs"


# --- Định giá: PHẢI khớp networth.py ---------------------------------------

def test_dinh_gia_khop_networth_py():
    """Chống 2 nguồn sự thật: builder và networth.py phải ra cùng con số."""
    from networth import compute as compute_networth
    from portfolio.loader import load_portfolio

    hist = load_history()
    if not hist:
        pytest.skip("chưa có data/history.jsonl")
    _port, _lim, _meta, parts, total, _price, _src = compute_networth()
    v = value_at(hist[-1], load_portfolio())
    assert v.total_trieu == pytest.approx(total, abs=0.1)
    assert v.gold_trieu == pytest.approx(parts["Vàng"], abs=0.1)


def test_value_at_thieu_gia_vang_thi_bao_None_khong_dien_0():
    """Thiếu XAU/tỷ giá → total = None. Điền 0 sẽ vẽ đường lao xuống đáy giả."""
    from portfolio.loader import load_portfolio

    snap = _snap()
    snap["gold"]["xauusd"] = None
    v = value_at(snap, load_portfolio())
    assert v.gold_trieu is None and v.total_trieu is None and v.gold_pct is None
    assert v.savings_trieu > 0  # phần biết chắc vẫn giữ nguyên, không xoá sạch


def test_value_at_gia_vang_cao_hon_thi_tong_tai_san_lon_hon():
    from portfolio.loader import load_portfolio
    port = load_portfolio()
    thap = value_at(_snap(xau=4000.0), port)
    cao = value_at(_snap(xau=4200.0), port)
    assert cao.total_trieu > thap.total_trieu
    assert cao.gold_pct > thap.gold_pct  # vàng tăng giá thì tỷ trọng vàng cũng tăng


# --- Dựng ngữ cảnh & render ------------------------------------------------

def test_build_context_history_rong_thi_bao_loi_ro_rang():
    with pytest.raises(SystemExit, match="history.jsonl"):
        build_context([])


def test_render_khong_no_voi_mot_snapshot_duy_nhat():
    """Kỳ đầu tiên chưa có gì để so sánh — vẫn phải ra trang, không sập."""
    html_out = render(build_context([_snap()]))
    assert "Bản tin đầu tư" in html_out
    assert "chưa có kỳ trước để so sánh" in html_out


def test_render_co_du_cac_muc_chinh():
    html_out = render(build_context([_snap(date="2026-07-21", ky="sang"), _snap()]))
    for muc in ["Phân bổ tài sản", "Tổng tài sản theo thời gian",
                "Tỷ trọng vàng vs ngưỡng rủi ro", "Giá vàng trong nước",
                "Vàng thế giới", "Chênh lệch vàng", "Lãi suất tiết kiệm",
                "VN-Index theo kỳ", "Rủi ro cần theo dõi", "Watchlist"]:
        assert muc in html_out, f"thiếu mục: {muc}"


def test_render_khong_lot_the_html_thua_tu_du_lieu():
    """risk_flags là văn bản từ WebSearch — phải escape, không cho chèn thẻ."""
    snap = _snap()
    snap["risk_flags"] = {"war": "<script>alert(1)</script> căng thẳng"}
    out = render(build_context([snap]))
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out


def test_render_theme_toi_dinh_nghia_du_ca_hai_scope():
    """Người xem đổi theme thủ công và theme hệ điều hành đều phải đúng màu."""
    out = render(build_context([_snap()]))
    assert "prefers-color-scheme: dark" in out
    assert ':root[data-theme="dark"]' in out


def test_render_bien_dong_watchlist_am_thi_to_mau_canh_bao(tmp_path, monkeypatch):
    import reporting.dashboard_builder as db
    wl = tmp_path / "watchlist.json"
    wl.write_text(json.dumps({
        "base_date": "2026-07-18",
        "stocks": [{"ticker": "VCB", "group": "A", "base_price": 58.5,
                    "last_price": 55.173, "moat": "test"}],
    }), encoding="utf-8")
    monkeypatch.setattr(db, "WATCHLIST_PATH", wl)
    out = render(build_context([_snap()]))
    assert "VCB" in out and "-5,69%" in out
    assert "--st-critical" in out  # giảm ≥3% thì tô màu critical


# --- Theo dõi khuyến nghị treo ---------------------------------------------

def test_dem_ky_lien_tiep_vuot_nguong():
    assert consecutive_over_threshold([65.0, 71.0, 72.0, 75.0], 70.0) == 3
    assert consecutive_over_threshold([75.0, 75.0, 65.0], 70.0) == 0  # kỳ cuối dưới ngưỡng


def test_ky_thieu_du_lieu_lam_ngat_chuoi_khong_doan_bua():
    assert consecutive_over_threshold([75.0, None, 75.0], 70.0) == 1


def test_chuoi_rong_tra_ve_0():
    assert consecutive_over_threshold([], 70.0) == 0


def test_canh_bao_treo_xuat_hien_khi_ty_trong_khong_giam():
    from analytics.advice_tracker import summarize_pending
    vals = [Valuation(None, 246, 35, None, 0.746, None) for _ in range(MIN_PERIODS_TO_WARN)]
    vals[-1] = Valuation(None, 246, 35, None, 0.751, None)
    out = summarize_pending([_snap()] * len(vals), vals)
    assert out and "kỳ liên tiếp" in out["message"]
    assert out["periods"] == MIN_PERIODS_TO_WARN


def test_khong_canh_bao_khi_ty_trong_da_giam_that():
    """Đã chốt bớt thật (tỷ trọng giảm rõ) thì phải IM, không nhắc nữa."""
    from analytics.advice_tracker import summarize_pending
    start = 0.78
    vals = [Valuation(None, 246, 35, None, start - i * (MEANINGFUL_DROP_PCT / 100), None)
            for i in range(MIN_PERIODS_TO_WARN + 1)]
    assert summarize_pending([_snap()] * len(vals), vals) == {}


def test_khong_canh_bao_khi_moi_1_2_ky():
    from analytics.advice_tracker import summarize_pending
    vals = [Valuation(None, 246, 35, None, 0.75, None)] * (MIN_PERIODS_TO_WARN - 1)
    assert summarize_pending([_snap()] * len(vals), vals) == {}


def test_khong_canh_bao_khi_duoi_nguong():
    from analytics.advice_tracker import summarize_pending
    vals = [Valuation(None, 246, 35, None, 0.50, None)] * 5
    assert summarize_pending([_snap()] * 5, vals) == {}


def test_du_lieu_rong_khong_lam_no_tracker():
    from analytics.advice_tracker import summarize_pending
    assert summarize_pending([], []) == {}


# --- Suy giảm duyên dáng khi thiếu nguồn tự động (thêm 12/8) ----------------
# Từ 27/7 task tự động chỉ lấy được XAU/USD + tỷ giá + giá cổ phiếu; giá SJC
# trong nước, VN-Index, khối ngoại, lãi suất KHÔNG có nguồn tự động. Dashboard
# phải nói rõ chuỗi dừng ở đâu, không để nửa biểu đồ trống không giải thích.

def test_vi_tri_gia_tri_that_gan_nhat():
    from reporting.dashboard_builder import last_real_index
    assert last_real_index([1.0, 2.0, None, None]) == 1
    assert last_real_index([None, None]) is None
    assert last_real_index([]) is None
    assert last_real_index([None, 5.0]) == 1


def test_ghi_chu_chuoi_dung_neu_thieu_cac_ky_cuoi():
    from reporting.dashboard_builder import series_end_note
    note = series_end_note([1.0, 2.0, None, None], ["a", "b", "c", "d"], "giá vàng")
    assert "dừng ở kỳ" in note and "<b>b</b>" in note and "2 kỳ" in note


def test_khong_ghi_chu_khi_chuoi_du_toi_ky_cuoi():
    from reporting.dashboard_builder import series_end_note
    assert series_end_note([1.0, 2.0], ["a", "b"], "giá vàng") == ""


def test_ghi_chu_khi_chuoi_trong_hoan_toan():
    from reporting.dashboard_builder import series_end_note
    assert "Chưa có kỳ nào" in series_end_note([None, None], ["a", "b"], "giá vàng")


def test_lai_suat_dung_snapshot_gan_nhat_co_so_lieu_kem_NGAY():
    """Kỳ này thiếu lãi suất -> lấy kỳ gần nhất có, nhưng PHẢI ghi rõ ngày và
    số ngày đã cũ; im lặng dùng số cũ như số mới là bịa."""
    co = _snap(date="2026-07-22", ky="chieu")
    khong = _snap(date="2026-08-10", ky="chieu")
    khong["deposit_top"] = []
    out = render(build_context([co, khong]))
    assert "2026-07-22" in out
    assert "19 ngày không cập nhật" in out
    assert "VIB" in out  # vẫn hiện được số liệu dùng được


def test_khong_ky_nao_co_lai_suat_thi_noi_ro():
    snap = _snap()
    snap["deposit_top"] = []
    assert "Chưa có kỳ nào ghi nhận lãi suất" in render(build_context([snap]))


def test_snapshot_gan_nhat_co_truong():
    from reporting.dashboard_builder import latest_snapshot_with
    a, b = _snap(date="2026-07-22"), _snap(date="2026-08-10")
    b["deposit_top"] = []
    assert latest_snapshot_with([a, b], "deposit_top")["date"] == "2026-07-22"
    assert latest_snapshot_with([b], "deposit_top") is None


def test_lich_su_dai_thi_nhan_truc_x_thua_ra_nhung_ve_du_diem():
    """19 snapshot: nhãn phải thưa để không thành vệt đen, nhưng KHÔNG bớt điểm."""
    hist = [_snap(date=f"2026-08-{d:02d}", ky=k)
            for d in range(1, 11) for k in ("sang", "chieu")]
    out = render(build_context(hist))
    import re
    pts = re.search(r'aria-label="Tổng tài sản theo thời gian">(.*?)</svg>', out, re.S).group(1)
    so_diem = len(re.search(r'points="([^"]+)"', pts).group(1).split())
    assert so_diem == len(hist)  # vẽ đủ 20 điểm

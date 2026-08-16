"""Bối cảnh thị trường: đo VN-Index so với lịch sử + tín hiệu gom hàng.

Bất biến quan trọng nhất được kiểm ở đây: **thiếu dữ liệu không bao giờ được
biến thành tín hiệu mua**, và cũng không được biến thành "chưa đến lúc".
"""
from datetime import date, timedelta

from analytics.news_sentiment import NewsSentiment
from equity.market_regime import (
    STATUS_CHUA_DEN_LUC,
    STATUS_CHUA_DO_DUOC,
    STATUS_THEO_DOI_SAT,
    STATUS_VUNG_GOM,
    ZONE_DIEU_CHINH,
    ZONE_GIAM_SAU,
    ZONE_PHAN_PHOI,
    ZONE_VUNG_GOM,
    accumulation_signal,
    analyze,
    drawdown_from_peak,
    gain_pct,
    load_rules,
    making_new_low,
    percentile_rank,
    tranche_levels,
    track,
)

RULES = {
    "regime": {
        "deep_drawdown_pct": 30.0,
        "watch_drawdown_pct": 20.0,
        "correction_drawdown_pct": 10.0,
        "percentile_window_sessions": 750,
        "low_percentile_max": 30.0,
        "min_sessions_for_history": 250,
        "near_peak_pct": 7.0,
        "strong_run_lookback_sessions": 250,
        "strong_run_gain_pct": 30.0,
        "new_low_lookback_sessions": 10,
        "tranches": [
            {"drawdown_pct": 30.0, "allocation_pct": 30.0},
            {"drawdown_pct": 37.0, "allocation_pct": 35.0},
            {"drawdown_pct": 45.0, "allocation_pct": 35.0},
        ],
    },
    "news": {"window_days": 7, "min_headlines": 5, "negative_ratio_min": 0.6,
             "max_age_days": 3},
}


START = date(2020, 1, 1)


def rows(closes):
    """Chuỗi EOD giả lập, ngày TĂNG DẦN THẬT — chỉ dùng cho test.

    Ngày phải thật vì phép đo có kiểm tra độ cũ của phiên cuối: chuỗi có ngày
    bịa sẽ bị đánh dấu là không xác nhận được độ mới, và test sẽ đo nhầm thứ
    nó định đo.
    """
    return [{"date": (START + timedelta(days=i)).isoformat(),
             "open": c, "high": c, "low": c, "close": c, "volume": 1000}
            for i, c in enumerate(closes)]


def snap_of(closes, rules=None):
    """Phân tích chuỗi như thể HÔM NAY là phiên cuối của chuỗi đó."""
    r = rows(closes)
    return analyze(r, rules or RULES, today=r[-1]["date"])


def ramp(a, b, n):
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def base(lo=900.0, hi=1100.0, n=250):
    """Nền tích luỹ răng cưa — một nửa số phiên nằm dưới trung điểm.

    Chuỗi tăng đều đơn thuần KHÔNG mô phỏng được thị trường thật cho phép đo
    percentile: nó khiến mọi mức giá tỷ lệ thẳng với thời gian, nên đáy của
    một đợt sập luôn rơi vào đúng vị trí percentile bằng chính mức chiết khấu.
    Thị trường thật đi ngang lâu rồi tăng nhanh, nên phần lớn số phiên nằm ở
    vùng nền — và đó mới là thứ percentile so sánh.
    """
    return [lo if i % 2 else hi for i in range(n)]


def series_vung_gom():
    """Nền 900–1100 → phi lên 1900 → sập 47% về 1000, xoá sạch thành quả đợt tăng.

    Đúng hình dạng của 2022: đỉnh 1528 (01/2022) → 873,78 (11/2022), −43%.
    """
    return base() + ramp(1100, 1900, 250) + ramp(1900, 1000, 100)


def series_phan_phoi():
    """Sát đỉnh sau đợt tăng dài — bối cảnh chủ danh mục cho là đang diễn ra."""
    return base() + ramp(1100, 1900, 250) + ramp(1900, 1850, 20)


def series_dieu_chinh():
    return base() + ramp(1100, 1900, 250) + ramp(1900, 1615, 30)


def series_bong_bong_vo():
    """Sập 35% từ đỉnh bong bóng nhưng vẫn đắt hơn gần như mọi phiên trước đó."""
    return [100.0] * 250 + ramp(100, 1000, 100) + [650.0]


# --- Phép đo thuần túy -------------------------------------------------------


def test_drawdown_do_dung_dinh_va_do_dai_dot_giam():
    dd = drawdown_from_peak([100, 120, 150, 120, 90])
    assert dd["peak"] == 150
    assert dd["drawdown_pct"] == 40.0
    assert dd["sessions_since_peak"] == 2


def test_drawdown_lay_dinh_gan_nhat_khi_trung_gia():
    """Đỉnh trùng giá thì lấy lần GẦN NHẤT — đợt giảm phải tính từ đỉnh gần đây."""
    dd = drawdown_from_peak([150, 100, 150, 120])
    assert dd["sessions_since_peak"] == 1


def test_percentile_thap_khi_gia_o_day_cua_so():
    assert percentile_rank([100, 110, 120, 130, 90], window=750) == 0.0
    assert percentile_rank([90, 100, 110, 120, 130], window=750) == 100.0


def test_percentile_co_cua_so_theo_du_lieu_dang_co():
    """Cửa sổ 750 phiên nhưng chỉ có 5 phiên → tính trên 5 phiên, không lỗi."""
    assert percentile_rank([100, 200, 300], window=750) is not None
    assert percentile_rank([100], window=750) is None


def test_gain_pct_va_new_low():
    assert gain_pct([100, 110, 130], lookback=2) == 30.0
    assert gain_pct([100, 110], lookback=5) is None
    assert making_new_low([10, 9, 8, 7, 6], lookback=3) is True
    assert making_new_low([6, 7, 8, 9, 10], lookback=3) is False


# --- Nhãn vùng ---------------------------------------------------------------


def test_sap_sau_xoa_sach_thanh_qua_dot_tang_la_vung_gom():
    snap = snap_of(series_vung_gom())
    assert snap.zone == ZONE_VUNG_GOM
    assert snap.drawdown_pct >= 30.0
    assert snap.enough_history


def test_giam_15_phan_tram_chi_la_dieu_chinh():
    snap = snap_of(series_dieu_chinh())
    assert snap.zone == ZONE_DIEU_CHINH


def test_sat_dinh_sau_dot_tang_dai_la_vung_phan_phoi():
    """Bối cảnh chủ danh mục cho là đang diễn ra: tay to vừa phân phối xong."""
    snap = snap_of(series_phan_phoi())
    assert snap.zone == ZONE_PHAN_PHOI


def test_drawdown_sau_nhung_van_dat_hon_lich_su_thi_khong_phai_vung_gom():
    """Đỉnh bong bóng giảm 35% mà vẫn đắt hơn gần như mọi phiên trong cửa sổ →
    GIẢM SÂU, không phải VÙNG GOM. Đây là lý do percentile bắt buộc phải có
    mặt bên cạnh drawdown: một mình drawdown sẽ gọi đáy của bong bóng là rẻ."""
    snap = snap_of(series_bong_bong_vo())
    assert snap.drawdown_pct >= 30.0
    assert snap.percentile > RULES["regime"]["low_percentile_max"]
    assert snap.zone == ZONE_GIAM_SAU


def test_chuoi_ngan_khong_duoc_gan_nhan_vung():
    """43 phiên EOD không đủ để nói 'đáy so với lịch sử'."""
    snap = snap_of([100 - i for i in range(43)])
    assert snap.zone is None
    assert not snap.enough_history
    assert snap.notes


def test_khong_co_file_thi_khong_co_du_lieu():
    snap = analyze([], RULES)
    assert not snap.has_data
    assert snap.zone is None
    assert "chưa có dữ liệu EOD" in snap.evidence()


def test_file_eod_cu_thi_dieu_kien_gia_thanh_chua_do_duoc():
    """"VN-Index đang ở đáy sâu" đọc từ file quên cập nhật 3 tuần là câu về
    quá khứ nói ở thì hiện tại. Vùng vẫn được gán nhãn (thông tin), nhưng
    điều kiện mua thì KHÔNG được coi là đạt."""
    r = rows(series_vung_gom())
    muon = (date.fromisoformat(r[-1]["date"]) + timedelta(days=21)).isoformat()
    snap = analyze(r, RULES, today=muon)
    assert snap.is_stale
    assert snap.price_age_days == 21
    assert snap.zone == ZONE_VUNG_GOM
    sig = accumulation_signal(snap, news(), RULES)
    assert sig["status"] == STATUS_CHUA_DO_DUOC


def test_ngay_phien_cuoi_khong_doc_duoc_thi_coi_la_khong_xac_nhan_duoc():
    r = rows(series_vung_gom())
    r[-1]["date"] = "khong-phai-ngay"
    snap = analyze(r, RULES, today=r[-2]["date"])
    assert snap.is_stale
    assert snap.price_age_days is None


# --- Tín hiệu gom hàng -------------------------------------------------------


def news(negative=6, total=8, *, measurable=True):
    if not measurable:
        return NewsSentiment(window_days=7, total=1, negative=1,
                             newest_date="2026-08-16", age_days=0,
                             is_stale=False, enough_headlines=False)
    return NewsSentiment(window_days=7, total=total, negative=negative,
                         positive=total - negative, newest_date="2026-08-16",
                         age_days=0, is_stale=False, enough_headlines=True,
                         threshold_ratio=0.6)


def test_du_ca_hai_dieu_kien_thi_ra_tin_hieu_gom():
    snap = snap_of(series_vung_gom())
    sig = accumulation_signal(snap, news(), RULES)
    assert sig["status"] == STATUS_VUNG_GOM
    assert all(c.met for c in sig["conditions"])
    assert sig["tranches"]


def test_gia_re_nhung_tin_tuc_chua_tieu_cuc_thi_chi_theo_doi():
    snap = snap_of(series_vung_gom())
    sig = accumulation_signal(snap, news(negative=1, total=8), RULES)
    assert sig["status"] == STATUS_THEO_DOI_SAT


def test_tin_xau_tran_ngap_nhung_gia_con_cao_thi_khong_phai_co_hoi():
    """Tin xấu lúc giá sát đỉnh là tin xấu thật — không được thành tín hiệu mua."""
    snap = snap_of(series_phan_phoi())
    sig = accumulation_signal(snap, news(), RULES)
    assert sig["status"] == STATUS_THEO_DOI_SAT
    assert sig["status"] != STATUS_VUNG_GOM


def test_ca_hai_deu_khong_dat_thi_chua_den_luc():
    snap = snap_of(series_phan_phoi())
    sig = accumulation_signal(snap, news(negative=0, total=8), RULES)
    assert sig["status"] == STATUS_CHUA_DEN_LUC


def test_thieu_nhat_ky_tin_tuc_KHONG_thanh_tin_hieu_mua():
    """Bất biến: im lặng của nhật ký tin tức không được coi là điều kiện đạt,
    và cũng không được coi là 'chưa đến lúc' — hệ thống phải nói nó không biết."""
    snap = snap_of(series_vung_gom())
    sig = accumulation_signal(snap, news(measurable=False), RULES)
    assert sig["status"] == STATUS_CHUA_DO_DUOC
    assert sig["status"] != STATUS_VUNG_GOM
    assert any(c.met is None for c in sig["conditions"])


def test_thieu_chuoi_vnindex_KHONG_thanh_tin_hieu_mua():
    sig = accumulation_signal(analyze([], RULES), news(), RULES)
    assert sig["status"] == STATUS_CHUA_DO_DUOC


def test_chua_do_duoc_khac_han_chua_den_luc_trong_canh_bao():
    sig = accumulation_signal(analyze([], RULES), news(), RULES)
    assert any("KHÔNG có nghĩa là 'chưa đến lúc'" in w for w in sig["warnings"])


def test_tin_hieu_gom_kem_canh_bao_dao_dang_roi():
    """Chuỗi giảm đều tới phiên cuối → phiên cuối là đáy 10 phiên."""
    snap = snap_of(series_vung_gom())
    assert snap.making_new_low is True
    sig = accumulation_signal(snap, news(), RULES)
    assert any("chưa hết rơi" in w or "hết rơi" in w for w in sig["warnings"])


def test_bac_giai_ngan_quy_ra_diem_so_cu_the():
    snap = snap_of(series_vung_gom())
    levels = tranche_levels(snap, RULES)
    assert [t["drawdown_pct"] for t in levels] == [30.0, 37.0, 45.0]
    assert levels[0]["index_level"] == round(snap.peak * 0.7, 2)
    assert all(t["reached"] for t in levels)          # đã giảm 47% > cả 3 bậc
    assert sum(t["allocation_pct"] for t in levels) == 100.0

    # Mới điều chỉnh 15% thì chưa bậc nào tới — mốc phải nói được "chưa", nếu
    # không thì kế hoạch giải ngân chỉ là ba con số trang trí.
    nong = tranche_levels(snap_of(series_dieu_chinh()), RULES)
    assert not any(t["reached"] for t in nong)


# --- Trạng thái giữa các kỳ --------------------------------------------------


def test_ky_dau_la_tin_moi_ky_sau_la_boi_canh():
    s1, new1, n1 = track(STATUS_VUNG_GOM, ZONE_VUNG_GOM, today="2026-08-16", state={})
    assert new1 is True and n1 == 1
    s2, new2, n2 = track(STATUS_VUNG_GOM, ZONE_VUNG_GOM, today="2026-08-17", state=s1)
    assert new2 is False and n2 == 2
    assert s2["first_seen"] == "2026-08-16"


def test_chay_hai_lan_trong_ngay_khong_thanh_hai_ky():
    """Bản tin sáng + bản tin chiều cùng ngày là MỘT kỳ."""
    s1, _, n1 = track(STATUS_VUNG_GOM, ZONE_VUNG_GOM, today="2026-08-16", state={})
    s2, new2, n2 = track(STATUS_VUNG_GOM, ZONE_VUNG_GOM, today="2026-08-16", state=s1)
    assert n1 == n2 == 1
    assert new2 is False
    assert s2["first_seen"] == "2026-08-16"


def test_doi_trang_thai_thi_lai_thanh_tin_moi():
    s1, _, _ = track(STATUS_CHUA_DEN_LUC, ZONE_DIEU_CHINH, today="2026-08-16", state={})
    _, new, n = track(STATUS_VUNG_GOM, ZONE_VUNG_GOM, today="2026-08-17", state=s1)
    assert new is True and n == 1


# --- Cấu hình thật -----------------------------------------------------------


def test_config_that_nap_duoc_va_du_khoa():
    cfg = load_rules()
    assert cfg["regime"]["deep_drawdown_pct"] > cfg["regime"]["watch_drawdown_pct"]
    assert cfg["regime"]["watch_drawdown_pct"] > cfg["regime"]["correction_drawdown_pct"]
    assert sum(t["allocation_pct"] for t in cfg["regime"]["tranches"]) == 100.0
    assert 0 < cfg["news"]["negative_ratio_min"] <= 1

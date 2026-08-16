"""Đo tâm lý tin tức — điều kiện thứ hai của tín hiệu gom hàng.

Trọng tâm: các cách hệ thống có thể TỰ LỪA MÌNH (im lặng thành tin tốt, ba
tiêu đề thành "tràn ngập", nhật ký cũ thành hiện trạng) đều phải bị chặn.
"""
from analytics.news_sentiment import (
    NEGATIVE,
    NEUTRAL,
    POSITIVE,
    measure,
    suggest_sentiment,
)

RULES = {"news": {"window_days": 7, "min_headlines": 5,
                  "negative_ratio_min": 0.6, "max_age_days": 3}}
TODAY = "2026-08-16"


def n(date, sentiment, headline="tin", source="test", auto=False):
    rec = {"date": date, "headline": headline, "sentiment": sentiment, "source": source}
    if auto:
        rec["sentiment_source"] = "auto"
    return rec


def test_khong_co_tin_thi_chua_do_duoc_chu_khong_phai_khong_co_tin_xau():
    m = measure([], today=TODAY, rules=RULES)
    assert m.measurable is False
    assert m.overwhelming_negative is None       # KHÔNG phải False
    assert "chưa có tin nào" in m.reason


def test_vai_tin_xau_khong_phai_tran_ngap():
    entries = [n(TODAY, NEGATIVE) for _ in range(3)]
    m = measure(entries, today=TODAY, rules=RULES)
    assert m.measurable is False
    assert m.overwhelming_negative is None
    assert "chưa đủ để gọi là 'tràn ngập'" in m.reason


def test_nhat_ky_cu_thi_khong_duoc_coi_la_hien_trang():
    entries = [n("2026-08-01", NEGATIVE) for _ in range(8)]
    m = measure(entries, today=TODAY, rules=RULES)
    assert m.is_stale is True
    assert m.measurable is False
    assert m.overwhelming_negative is None


def test_du_tin_va_du_ty_le_thi_ket_luan_tran_ngap():
    entries = [n(TODAY, NEGATIVE) for _ in range(6)] + [n(TODAY, POSITIVE) for _ in range(2)]
    m = measure(entries, today=TODAY, rules=RULES)
    assert m.total == 8 and m.negative == 6
    assert m.negative_ratio == 0.75
    assert m.measurable is True
    assert m.overwhelming_negative is True


def test_duoi_nguong_ty_le_thi_khong_tran_ngap():
    entries = [n(TODAY, NEGATIVE) for _ in range(4)] + [n(TODAY, POSITIVE) for _ in range(4)]
    m = measure(entries, today=TODAY, rules=RULES)
    assert m.overwhelming_negative is False      # đo được, và KHÔNG đạt


def test_chi_dem_tin_trong_cua_so():
    entries = ([n("2026-06-01", NEGATIVE) for _ in range(20)]
               + [n(TODAY, POSITIVE) for _ in range(6)])
    m = measure(entries, today=TODAY, rules=RULES)
    assert m.total == 6
    assert m.negative == 0


def test_tin_tuong_lai_khong_duoc_tinh():
    """Chống look-ahead: tin ghi ngày mai không được vào phép đo hôm nay."""
    entries = [n("2026-08-20", NEGATIVE) for _ in range(8)]
    m = measure(entries, today=TODAY, rules=RULES)
    assert m.total == 0


def test_nhan_la_dem_duoc_va_bien_ban_ghi_nhan_tu_dong():
    entries = [n(TODAY, NEGATIVE, auto=True) for _ in range(5)] + [n(TODAY, NEGATIVE)]
    m = measure(entries, today=TODAY, rules=RULES)
    assert m.auto_labeled == 5
    assert "gán nhãn tự động" in m.evidence()


def test_nhan_sai_dinh_dang_coi_la_trung_tinh_khong_lam_sap():
    entries = [n(TODAY, "RẤT XẤU") for _ in range(5)]
    m = measure(entries, today=TODAY, rules=RULES)
    assert m.neutral == 5
    assert m.overwhelming_negative is False


def test_ngay_hong_thi_bo_qua_ban_ghi():
    entries = [n("khong-phai-ngay", NEGATIVE)] + [n(TODAY, NEGATIVE) for _ in range(5)]
    m = measure(entries, today=TODAY, rules=RULES)
    assert m.total == 5


# --- Gợi ý nhãn theo từ khoá -------------------------------------------------


def test_tu_khoa_tieu_cuc_va_tich_cuc():
    label, matched = suggest_sentiment("VN-Index bán tháo, mất mốc 1.200 điểm")
    assert label == NEGATIVE and matched
    label, matched = suggest_sentiment("Khối ngoại mua ròng, thị trường bứt phá")
    assert label == POSITIVE and matched


def test_hoa_thi_trung_tinh_khong_uu_tien_ben_nao():
    """Nếu hoà mà nghiêng về tiêu cực, chính điều kiện đang muốn kiểm chứng sẽ
    tự đạt — thiên kiến xác nhận được cài thẳng vào code."""
    label, _ = suggest_sentiment("Khối ngoại bán ròng nhưng thị trường phục hồi")
    assert label == NEUTRAL


def test_tieu_de_trung_tinh_thi_khong_gan_nhan_xau():
    label, matched = suggest_sentiment("Lịch chốt quyền nhận cổ tức tuần này")
    assert label == NEUTRAL
    assert matched == []

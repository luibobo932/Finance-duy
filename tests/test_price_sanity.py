"""Test analytics/price_sanity.py.

Case gốc phải bắt được: 4/6 bản tin 20–22/7 phải viết tay cảnh báo Simplize trả
giá CTD = 73.800đ trong khi HOSE EOD đã xác minh 59.100đ. Check này phải tự bắt.
"""
from analytics.price_sanity import (
    DAILY_BAND_PCT,
    IMPLAUSIBLE,
    NO_REFERENCE,
    PLAUSIBLE,
    check_price,
    max_plausible_move_pct,
    sessions_between,
)


# --- Case thật đã gây lỗi ---------------------------------------------------

def test_bat_duoc_gia_CTD_sai_cua_simplize():
    """73.800 vs 59.100 = +24,9% trong 1 phiên — vượt xa biên 7% của HOSE."""
    r = check_price("CTD", 73_800, 59_100, reference_date="2026-07-20",
                    target_date="2026-07-21")
    assert r.verdict == IMPLAUSIBLE
    assert not r.ok
    assert "BẤT KHẢ THI" in r.message
    assert r.actual_move_pct > 24


def test_gia_CTD_that_thi_hop_le():
    """63.500 -> 59.100 = -6,93%, sát trần giảm nhưng HỢP LỆ (đúng phiên sàn)."""
    r = check_price("CTD", 59_100, 63_500, reference_date="2026-07-17",
                    target_date="2026-07-20")
    assert r.verdict == PLAUSIBLE
    assert r.ok


def test_bat_duoc_bao_cao_ghi_CTD_27150():
    """Một báo cáo CTCK ghi CTD 27.150đ — lệch -57%, cũng bất khả thi."""
    r = check_price("CTD", 27_150, 63_500, reference_date="2026-07-16",
                    target_date="2026-07-17")
    assert r.verdict == IMPLAUSIBLE


def test_gia_VCB_giam_388_phan_tram_la_hop_le():
    r = check_price("VCB", 55_173, 57_400, reference_date="2026-07-21",
                    target_date="2026-07-22")
    assert r.verdict == PLAUSIBLE


# --- Biên độ theo sàn -------------------------------------------------------

def test_bien_do_dung_theo_san():
    assert DAILY_BAND_PCT["HOSE"] == 7.0
    assert DAILY_BAND_PCT["HNX"] == 10.0
    assert DAILY_BAND_PCT["UPCOM"] == 15.0


def test_bien_do_tinh_lai_kep_khong_nhan_tuyen_tinh():
    """2 phiên trần HOSE = 1,07²−1 = 14,49%, không phải 14%."""
    assert abs(max_plausible_move_pct(2, "HOSE") - 14.49) < 0.01


def test_ma_la_dung_bien_hep_nhat():
    """Mã không có trong bảng -> HOSE (7%), thận trọng hơn là bỏ sót."""
    r = check_price("XYZ", 100, 90, reference_date="2026-07-21", target_date="2026-07-22")
    assert r.verdict == IMPLAUSIBLE  # +11,1% > 7%


def test_san_bien_rong_hon_thi_cung_muc_lech_lai_hop_le():
    r = check_price("XYZ", 100, 90, reference_date="2026-07-21",
                    target_date="2026-07-22", exchange="UPCOM")
    assert r.verdict == PLAUSIBLE  # +11,1% < 15%


# --- Đếm phiên --------------------------------------------------------------

def test_dem_phien_bo_qua_cuoi_tuan():
    # thứ 6 17/7 -> thứ 2 20/7 = 1 phiên
    assert sessions_between("2026-07-17", "2026-07-20") == 1


def test_dem_phien_trong_tuan():
    assert sessions_between("2026-07-20", "2026-07-22") == 2


def test_cung_ngay_tinh_toi_thieu_1_phien():
    assert sessions_between("2026-07-22", "2026-07-22") == 1


def test_ngay_khong_doc_duoc_thi_ve_1_phien_khong_no():
    assert sessions_between("hong", "2026-07-22") == 1
    assert sessions_between(None, None) == 1


def test_nhieu_phien_thi_bien_noi_ra():
    """Sau 5 phiên, lệch 30% là hợp lệ (1,07⁵−1 = 40,3%)."""
    r = check_price("VCB", 130, 100, reference_date="2026-07-13", target_date="2026-07-20")
    assert r.verdict == PLAUSIBLE


# --- Thiếu tham chiếu: KHÔNG kết luận --------------------------------------

def test_khong_co_tham_chieu_thi_khong_ket_luan_dung_sai():
    r = check_price("CTD", 73_800, None)
    assert r.verdict == NO_REFERENCE
    assert r.ok is True  # không có căn cứ để bác bỏ
    assert "không kết luận được" in r.message


def test_tham_chieu_bang_0_coi_nhu_khong_co():
    assert check_price("CTD", 73_800, 0).verdict == NO_REFERENCE


# --- Hai lỗi do test cũ bắt được khi nối check vào trend.py (12/8) ----------

def test_tham_chieu_qua_cu_thi_KHONG_ket_luan_va_khong_tran_so():
    """Trước khi sửa: 1,07^18901 gây tràn số. Sau khi sửa: trả NO_REFERENCE.

    Thà nói "không đủ căn cứ" hơn là gật đầu vô nghĩa — sau 10 phiên biên tích
    lũy đã ~97% nên mọi giá đều "hợp lệ", kết luận mất ý nghĩa.
    """
    r = check_price("VCB", 58_500, 57_400, reference_date="2026-07-22",
                    target_date="2099-01-01")
    assert r.verdict == NO_REFERENCE
    assert "quá cũ" in r.message


def test_bien_do_khong_tran_voi_so_phien_rat_lon():
    assert max_plausible_move_pct(10**6, "HOSE") < 200  # bị chặn, không phải inf


def test_dung_o_ranh_gioi_10_phien_van_kiem_tra():
    r = check_price("VCB", 200_000, 57_400, reference_date="2026-07-08",
                    target_date="2026-07-22")  # đúng 10 phiên
    assert r.sessions_elapsed == 10
    assert r.verdict == IMPLAUSIBLE  # +248% vẫn vượt biên 96,7%

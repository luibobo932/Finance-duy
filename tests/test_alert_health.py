"""Test analytics/alert_health.py — chống "cảnh báo luôn bật".

Lỗi thật: data/alerts.json đặt ngưỡng theo giá 18/7 rồi không cập nhật; đo ngày
13/8 có 3/6 ngưỡng kích hoạt vĩnh viễn. Rõ nhất là gold-res "vượt 4.060$" khi
XAU đã 4.340$ — báo động ở mọi lần chạy suốt nhiều tuần, không mang thông tin
nào, và làm loãng những cảnh báo thật.
"""
import json

import pytest

from analytics.alert_health import (
    ATR_MULTIPLE,
    STALE_AFTER_FIRES,
    daily_volatility,
    evaluate,
    load_state,
    reanchor,
    save_state,
)

ALERTS = [
    {"id": "gold-res", "asset": "XAUUSD", "type": "above", "level": 4060,
     "note": "Vượt 4.060$ — mở đường lên 4.114$"},
    {"id": "vcb-sup", "asset": "VCB", "type": "below", "level": 58.0,
     "note": "Thủng hỗ trợ 58.0"},
]


# --- Đếm số lần kích hoạt liên tiếp ----------------------------------------

def test_lan_dau_cham_nguong_la_TIN():
    res, _state = evaluate(ALERTS, {"XAUUSD": 4340}, {})
    r = res[0]
    assert r.fired and r.is_fresh and not r.is_stale
    assert r.consecutive_fires == 1


def test_cham_lien_tiep_qua_nguong_thi_thanh_LOI_THOI():
    state = {}
    for _ in range(STALE_AFTER_FIRES + 1):
        res, state = evaluate(ALERTS, {"XAUUSD": 4340}, state)
    r = res[0]
    assert r.fired and r.is_stale and not r.is_fresh
    assert "NGƯỠNG LỖI THỜI" in r.headline


def test_thoat_nguong_thi_bo_dem_ve_0_va_lan_sau_lai_la_TIN():
    """Giá về dưới ngưỡng rồi vượt lại là diễn biến MỚI, phải báo lại."""
    state = {}
    for _ in range(STALE_AFTER_FIRES + 2):
        _res, state = evaluate(ALERTS, {"XAUUSD": 4340}, state)
    _res, state = evaluate(ALERTS, {"XAUUSD": 4000}, state)   # thoát ngưỡng
    assert state["gold-res"]["consecutive_fires"] == 0
    res, _state = evaluate(ALERTS, {"XAUUSD": 4340}, state)   # vượt lại
    assert res[0].is_fresh is True and res[0].is_stale is False


def test_thieu_gia_thi_BO_QUA_khong_reset_bo_dem():
    """Thiếu giá không phải bằng chứng rằng ngưỡng đã thoát."""
    state = {}
    _res, state = evaluate(ALERTS, {"XAUUSD": 4340}, state)
    assert state["gold-res"]["consecutive_fires"] == 1
    res, state = evaluate(ALERTS, {}, state)  # không có giá nào
    assert res == []
    assert state["gold-res"]["consecutive_fires"] == 1  # giữ nguyên


def test_khong_cham_nguong_thi_khong_bao():
    res, _ = evaluate(ALERTS, {"XAUUSD": 4000}, {})
    assert res[0].fired is False


def test_ghi_lai_ngay_cham_dau_tien_va_gan_nhat():
    _res, state = evaluate(ALERTS, {"XAUUSD": 4340}, {}, today="2026-08-01")
    _res, state = evaluate(ALERTS, {"XAUUSD": 4340}, state, today="2026-08-10")
    assert state["gold-res"]["first_fired"] == "2026-08-01"
    assert state["gold-res"]["last_fired"] == "2026-08-10"


def test_alert_khong_co_id_van_dem_duoc():
    res, state = evaluate([{"asset": "X", "type": "above", "level": 10}], {"X": 20}, {})
    assert res[0].consecutive_fires == 1 and len(state) == 1


# --- Lưu / đọc state -------------------------------------------------------

def test_luu_va_doc_lai_state(tmp_path):
    p = tmp_path / "alert_state.json"
    save_state({"a": {"consecutive_fires": 3}}, p)
    assert load_state(p)["a"]["consecutive_fires"] == 3


def test_state_hong_thi_coi_nhu_chua_co_khong_lam_sap(tmp_path):
    p = tmp_path / "alert_state.json"
    p.write_text("{ hỏng json", encoding="utf-8")
    assert load_state(p) == {}


def test_state_chua_ton_tai_tra_ve_rong(tmp_path):
    assert load_state(tmp_path / "chua-co.json") == {}


# --- Đo biến động ----------------------------------------------------------

def test_do_lech_chuan_thay_doi_hang_ngay():
    assert daily_volatility([100, 102, 101, 105, 103]) is not None


def test_qua_it_du_lieu_thi_khong_doan_bien_dong():
    assert daily_volatility([100]) is None
    assert daily_volatility([100, 102]) is None  # chỉ 1 hiệu số, chưa tính được stdev


# --- Đặt lại ngưỡng --------------------------------------------------------

def test_dat_lai_nguong_theo_bien_dong_that():
    updated, notes = reanchor(ALERTS, {"XAUUSD": 4340, "VCB": 60.0},
                              {"XAUUSD": 70.0, "VCB": 2.0})
    gold = next(a for a in updated if a["id"] == "gold-res")
    vcb = next(a for a in updated if a["id"] == "vcb-sup")
    assert gold["level"] == 4410.0   # above -> giá + band
    assert vcb["level"] == 58.0      # below -> giá − band
    assert len(notes) == 2


def test_sau_khi_dat_lai_thi_KHONG_con_kich_hoat():
    """Mục đích cuối cùng: 3/6 ngưỡng đang kêu vĩnh viễn phải im."""
    prices = {"XAUUSD": 4340, "VCB": 60.0}
    updated, _ = reanchor(ALERTS, prices, {"XAUUSD": 70.0, "VCB": 2.0})
    res, _ = evaluate(updated, prices, {})
    assert not any(r.fired for r in res)


def test_ghi_chu_duoc_viet_lai_de_KHONG_noi_nguoc_voi_nguong():
    """Lỗi thật đã gặp: ngưỡng thành 4.410$ mà ghi chú vẫn ghi "Vượt 4.060$"."""
    updated, _ = reanchor(ALERTS, {"XAUUSD": 4340}, {"XAUUSD": 70.0}, today="2026-08-10")
    gold = next(a for a in updated if a["id"] == "gold-res")
    assert "4.060" not in gold["note"]
    assert "4410" in gold["note"].replace(".", "").replace(",", "")
    assert "2026-08-10" in gold["note"]


def test_nhan_dinh_tay_goc_duoc_giu_o_note_manual():
    updated, _ = reanchor(ALERTS, {"XAUUSD": 4340}, {"XAUUSD": 70.0})
    gold = next(a for a in updated if a["id"] == "gold-res")
    assert gold["note_manual"] == "Vượt 4.060$ — mở đường lên 4.114$"


def test_dat_lai_nhieu_lan_khong_lam_mat_nhan_dinh_goc():
    a = list(ALERTS)
    for _ in range(3):
        a, _ = reanchor(a, {"XAUUSD": 4340}, {"XAUUSD": 70.0})
    gold = next(x for x in a if x["id"] == "gold-res")
    assert gold["note_manual"] == "Vượt 4.060$ — mở đường lên 4.114$"


def test_thieu_gia_thi_GIU_NGUYEN_nguong_khong_bia():
    updated, notes = reanchor(ALERTS, {}, {})
    assert [a["level"] for a in updated] == [4060, 58.0]
    assert all("GIỮ NGUYÊN" in n for n in notes)


def test_thieu_du_lieu_bien_dong_thi_GIU_NGUYEN():
    updated, notes = reanchor(ALERTS, {"XAUUSD": 4340}, {})  # có giá, không có band
    assert updated[0]["level"] == 4060
    assert "thiếu dữ liệu biến động" in notes[0]


def test_boi_so_bien_dong_dung_hang_so_cong_bo():
    updated, _ = reanchor(ALERTS, {"XAUUSD": 4000}, {"XAUUSD": 100.0})
    gold = next(a for a in updated if a["id"] == "gold-res")
    assert gold["level"] == 4000 + 100.0  # band đã nhân ATR_MULTIPLE ở tầng gọi
    assert str(ATR_MULTIPLE) in gold["note"]


# --- Dữ liệu thật trong repo ----------------------------------------------

def test_alerts_json_thuc_te_doc_duoc_va_dung_schema():
    from pathlib import Path

    doc = json.loads((Path(__file__).resolve().parent.parent / "data" / "alerts.json")
                     .read_text(encoding="utf-8"))
    for a in doc["alerts"]:
        assert a["type"] in ("below", "above")
        assert isinstance(a["level"], (int, float)) and a["level"] > 0
        assert a.get("id") and a.get("asset")


# --- Bộ đếm theo KỲ, không theo số lần quét (sửa 13/8) ---------------------

def test_quet_lai_cung_ky_KHONG_cong_them():
    """Chạy CLI 3 lần trong một buổi không được tự đẩy ngưỡng thành lỗi thời —
    bộ đếm đo diễn biến thị trường, không đo số lần mình gõ lệnh."""
    state = {}
    for _ in range(5):
        res, state = evaluate(ALERTS, {"XAUUSD": 4340}, state, period="2026-08-10-chieu")
    assert res[0].consecutive_fires == 1
    assert res[0].is_stale is False


def test_ky_khac_thi_moi_cong_them():
    state = {}
    for i in range(STALE_AFTER_FIRES + 1):
        res, state = evaluate(ALERTS, {"XAUUSD": 4340}, state, period=f"2026-08-{i:02d}-chieu")
    assert res[0].consecutive_fires == STALE_AFTER_FIRES + 1
    assert res[0].is_stale is True


def test_quet_lai_cung_ky_cho_KET_QUA_GIONG_NHAU():
    """Bất biến: cùng đầu vào + cùng kỳ phải cho cùng kết luận fresh/stale."""
    state = {}
    r1, state = evaluate(ALERTS, {"XAUUSD": 4340}, state, period="2026-08-10-chieu")
    r2, _ = evaluate(ALERTS, {"XAUUSD": 4340}, state, period="2026-08-10-chieu")
    assert (r1[0].is_fresh, r1[0].is_stale) == (r2[0].is_fresh, r2[0].is_stale)


def test_khong_truyen_period_van_hoat_dong_nhu_cu():
    """Tương thích ngược: caller cũ không truyền period thì đếm theo lần quét."""
    state = {}
    for _ in range(2):
        res, state = evaluate(ALERTS, {"XAUUSD": 4340}, state)
    assert res[0].consecutive_fires == 2

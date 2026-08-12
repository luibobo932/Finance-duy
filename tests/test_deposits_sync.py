"""Test deposits/sync.py — chấm dứt 2 nguồn sự thật về lãi suất.

Lỗi thật đã xảy ra: bản tin 22/7 dùng VIB 8,0%/OCB 7,1% trong khi
data/normalized/deposit_rates.jsonl vẫn đứng ở 19/7 với Bắc Á/OceanBank,
nên scripts/deposits_report.py trả lời khác bản tin cho CÙNG một câu hỏi.
"""
import json

from deposits.ranking import load_normalized, rank
from deposits.sync import UNKNOWN_CHANNEL_NOTE, snapshot_to_rates, sync_snapshot


def _snap(date="2026-07-22", deposits=None):
    return {
        "date": date, "ky": "chieu",
        "deposit_top": deposits if deposits is not None else [
            {"bank": "VIB", "term_months": 6, "rate_pct": 8.0},
            {"bank": "Cake by VPBank", "term_months": 12, "rate_pct": 7.4},
        ],
    }


def test_doi_snapshot_thanh_ban_ghi_chuan():
    rates = snapshot_to_rates(_snap())
    assert len(rates) == 2
    assert rates[0]["bank"] == "VIB"
    assert rates[0]["term_months"] == 6
    assert rates[0]["rate_online"] == 8.0
    assert rates[0]["updated_at"] == "2026-07-22"


def test_kenh_chua_biet_thi_GHI_RO_khong_gia_vo_da_xac_nhan():
    """Snapshot không nói online/tại quầy — phải nói thẳng là chưa xác định."""
    rates = snapshot_to_rates(_snap())
    assert UNKNOWN_CHANNEL_NOTE in rates[0]["conditions"]


def test_kenh_tai_quay_duoc_ghi_dung_cot():
    rates = snapshot_to_rates(_snap(deposits=[
        {"bank": "X", "term_months": 12, "rate_pct": 6.5, "channel": "counter"}]))
    assert rates[0]["rate_counter"] == 6.5 and rates[0]["rate_online"] is None
    assert UNKNOWN_CHANNEL_NOTE not in rates[0]["conditions"]  # đã biết kênh thì không cảnh báo


def test_khong_bia_muc_gui_toi_thieu():
    """Snapshot không có min_deposit → None, không được điền số mặc định."""
    assert snapshot_to_rates(_snap())[0]["min_deposit_vnd"] is None


def test_bo_qua_muc_thieu_du_lieu():
    rates = snapshot_to_rates(_snap(deposits=[
        {"bank": "", "term_months": 6, "rate_pct": 8.0},          # thiếu tên
        {"bank": "A", "term_months": None, "rate_pct": 8.0},      # thiếu kỳ hạn
        {"bank": "B", "term_months": 6, "rate_pct": None},        # thiếu lãi suất
        {"bank": "OK", "term_months": 6, "rate_pct": 7.0},
    ]))
    assert [r["bank"] for r in rates] == ["OK"]


def test_snapshot_khong_co_ngay_thi_khong_ghi():
    assert snapshot_to_rates({"deposit_top": [{"bank": "X", "term_months": 6, "rate_pct": 7.0}]}) == []


def test_snapshot_khong_co_lai_suat_thi_tra_ve_rong():
    assert snapshot_to_rates(_snap(deposits=[])) == []


def test_sync_ghi_duoc_va_khong_ghi_trung(tmp_path):
    """Chạy lại trend.py append phải an toàn — không nhân bản dữ liệu."""
    p = tmp_path / "deposit_rates.jsonl"
    assert sync_snapshot(_snap(), p) == 2
    assert sync_snapshot(_snap(), p) == 0  # lần 2: idempotent
    assert len(p.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_sync_ngay_moi_khong_de_len_ngay_cu(tmp_path):
    """Lịch sử lãi suất được giữ; chỉ ngày mới nhất được dùng để xếp hạng."""
    p = tmp_path / "deposit_rates.jsonl"
    sync_snapshot(_snap(date="2026-07-19", deposits=[
        {"bank": "OceanBank", "term_months": 12, "rate_pct": 7.0}]), p)
    sync_snapshot(_snap(date="2026-07-22", deposits=[
        {"bank": "VIB", "term_months": 6, "rate_pct": 8.0}]), p)
    assert len(p.read_text(encoding="utf-8").strip().splitlines()) == 2  # giữ cả 2 ngày
    ranked = rank(load_normalized(p))
    assert [r["bank"] for r in ranked] == ["VIB"]  # nhưng chỉ ngày mới nhất được xếp hạng


def test_lai_suat_sau_sync_khop_voi_snapshot_moi_nhat(tmp_path):
    """Test cốt lõi: kho chuẩn hoá phải nói ĐÚNG điều bản tin nói."""
    p = tmp_path / "deposit_rates.jsonl"
    snap = _snap(date="2026-07-22", deposits=[
        {"bank": "VIB", "term_months": 6, "rate_pct": 8.0},
        {"bank": "Cake by VPBank", "term_months": 12, "rate_pct": 7.4},
        {"bank": "OCB", "term_months": 12, "rate_pct": 7.1},
    ])
    sync_snapshot(snap, p)
    ranked = rank(load_normalized(p))
    tu_snapshot = {(d["bank"], d["term_months"], d["rate_pct"]) for d in snap["deposit_top"]}
    tu_kho = {(r["bank"], r["term_months"], r["rate_pct"]) for r in ranked}
    assert tu_kho == tu_snapshot


def test_muc_yeu_cau_so_du_lon_van_bi_loai_sau_sync(tmp_path):
    """Bộ lọc retail phải còn hiệu lực với dữ liệu đến từ snapshot."""
    p = tmp_path / "deposit_rates.jsonl"
    sync_snapshot(_snap(deposits=[
        {"bank": "HDBank", "term_months": 13, "rate_pct": 7.6,
         "conditions": "yêu cầu khách VIP"}]), p)
    assert rank(load_normalized(p)) == []

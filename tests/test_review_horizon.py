"""Thước đo độ chính xác không được tự bảo vệ mình.

Bằng chứng, đo trên `data/decisions.jsonl` + `data/history.jsonl` thật:

`gold.ring_sell` (giá vàng nhẫn trong nước) chỉ có tới 22/07 rồi ngừng hẳn vì
không có nguồn tự động. Bốn quyết định neo vào trường đó bị KẸT — kỳ so sánh
muộn nhất còn giá là 22/07 chiều, cách quyết định 22/07 sáng vài giờ.

Hệ quả không phải "thiếu dữ liệu" mà là **một khuyến nghị SAI bị ghi thành
đúng-không-sai**:

    22/07 sáng CHỐT BỚT (kỳ vọng giá giảm)
      đo bằng ring_sell tới 22/07 chiều  → +0,00%  → "đi ngang"
      đo bằng xauusd     tới 10/08       → +5,48%  → SAI HƯỚNG

Cả hai quyết định CHỐT BỚT của 22/07 đều rơi vào đó, nên `scored = 0` và
accuracy vĩnh viễn "chưa tính được" — trong khi thực tế đã có hai lần đoán sai.

`analytics/opportunity_cost.py` ĐÃ giải đúng vấn đề này và chú thích trong đó
nói thẳng ra. Sửa ở module đó, không sửa ở `decision_review` — mà module này
mới là nơi nạp accuracy vào điểm tin cậy. Hai nơi vì thế chấm cùng một quyết
định ra hai con số trái nhau: +0,00% và +5,48%.
"""
import json
from pathlib import Path

import pytest

from analytics.decision_review import (FALLBACK_FIELDS, Verdict, best_measurement,
                                       review_one, summarize)

ROOT = Path(__file__).resolve().parent.parent


def _snap(date, ky, **gold):
    return {"date": date, "ky": ky, "gold": gold}


def _decision(date, ky, action="TAKE_PARTIAL_PROFIT", ref=147.5, field="ring_sell"):
    return {"date": date, "ky": ky, "asset": "Vàng nhẫn", "asset_class": "gold",
            "action": action, "action_vi": "x", "ref_price_field": field, "ref_price": ref}


# --- Trường giá chết không được làm đóng băng phép chấm ---------------------

def test_truong_gia_ngung_thu_thap_thi_dung_truong_thay_the():
    snaps = [
        _snap("2026-07-22", "sang", ring_sell=147.5, xauusd=4115),
        _snap("2026-07-22", "chieu", ring_sell=147.5, xauusd=4134),
        _snap("2026-08-10", "chieu", xauusd=4340.4),          # ring_sell đã ngừng
    ]
    r = review_one(_decision("2026-07-22", "sang"), snaps)
    assert r["measured_field"] == "xauusd"
    assert r["approximated"] is True
    assert r["change_pct"] == pytest.approx(5.48, abs=0.01)
    assert r["verdict"] == Verdict.SAI_HUONG.value, "CHỐT BỚT rồi giá tăng 5,48% là SAI HƯỚNG"


def test_khong_co_truong_thay_the_thi_bi_dong_bang_o_0_phan_tram():
    """Dựng lại nguyên trạng hành vi cũ, để thấy nó che mất cái gì."""
    snaps = [
        _snap("2026-07-22", "sang", ring_sell=147.5),
        _snap("2026-07-22", "chieu", ring_sell=147.5),
        _snap("2026-08-10", "chieu", xauusd=4340.4),
    ]
    r = review_one(_decision("2026-07-22", "sang"), snaps)
    # Không có xauusd ở kỳ ra quyết định → không đọc được cả hai đầu cùng trường
    assert r["change_pct"] == 0.0 and r["verdict"] == Verdict.DI_NGANG.value


def test_KHONG_BAO_GIO_so_cheo_hai_don_vi_khac_nhau():
    """Ràng buộc bất di bất dịch: ref_price (ring_sell ~147) không bao giờ được
    so với giá sau (xauusd ~4340). Đó không phải xấp xỉ, đó là vô nghĩa."""
    snaps = [_snap("2026-08-10", "chieu", xauusd=4340.4)]   # không có kỳ ra quyết định
    r = review_one(_decision("2026-07-22", "sang"), snaps)
    assert r["verdict"] == Verdict.CHUA_DU_DU_LIEU.value
    assert r["change_pct"] is None


def test_truong_goc_con_song_thi_KHONG_xap_xi():
    snaps = [
        _snap("2026-07-20", "sang", ring_sell=145.0, xauusd=3990),
        _snap("2026-07-22", "chieu", ring_sell=138.0, xauusd=4134),
    ]
    r = review_one(_decision("2026-07-20", "sang", ref=145.0), snaps)
    assert r["measured_field"] == "ring_sell" and r["approximated"] is False
    assert r["verdict"] == Verdict.DUNG_HUONG.value


# --- Chân trời đánh giá phải hiện ra ----------------------------------------

def test_verdict_luon_kem_so_ngay_cua_cua_so_danh_gia():
    snaps = [_snap("2026-07-20", "sang", ring_sell=145.0),
             _snap("2026-08-10", "chieu", ring_sell=138.0)]
    r = review_one(_decision("2026-07-20", "sang", ref=145.0), snaps)
    assert r["horizon_days"] == 21


def test_cua_so_trong_ngay_la_0_ngay():
    snaps = [_snap("2026-08-10", "sang", ring_sell=145.0),
             _snap("2026-08-10", "chieu", ring_sell=145.0)]
    r = review_one(_decision("2026-08-10", "sang", ref=145.0), snaps)
    assert r["horizon_days"] == 0


# --- Hai module phải chấm cùng một con số -----------------------------------

def test_decision_review_va_opportunity_cost_KHONG_duoc_lech_nhau():
    """Lỗi gốc: +0,00% ở một module, +5,48% ở module kia, cùng một quyết định."""
    from analytics.opportunity_cost import measure_one

    snaps = [
        _snap("2026-07-22", "sang", ring_sell=147.5, xauusd=4115),
        _snap("2026-08-10", "chieu", xauusd=4340.4),
    ]
    d = _decision("2026-07-22", "sang")
    assert review_one(d, snaps)["change_pct"] == pytest.approx(measure_one(d, snaps).change_pct,
                                                              abs=0.01)


def test_chi_MOT_noi_dinh_nghia_truong_gia_thay_the():
    """Chống tái phát: `opportunity_cost` không được khai lại bảng của riêng nó."""
    src = (ROOT / "analytics" / "opportunity_cost.py").read_text(encoding="utf-8")
    assert "FALLBACK_FIELDS: dict" not in src, "đã khai lại bảng trường thay thế lần thứ hai"
    assert "gold" in FALLBACK_FIELDS


# --- Trên dữ liệu THẬT của dự án --------------------------------------------

def test_tren_du_lieu_that_hai_quyet_dinh_CHOT_BOT_22_07_la_SAI_HUONG():
    from decision.decision_log import load_decisions

    hist_path = ROOT / "data" / "history.jsonl"
    if not hist_path.exists():
        pytest.skip("chưa có data/history.jsonl")
    hist = [json.loads(l) for l in hist_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [review_one(d, hist) for d in load_decisions()
            if d["date"] == "2026-07-22" and d["action"] == "TAKE_PARTIAL_PROFIT"]
    if not rows:
        pytest.skip("không còn quyết định 22/07 trong nhật ký")
    for r in rows:
        assert r["verdict"] == Verdict.SAI_HUONG.value
        assert r["change_pct"] > 0


def test_accuracy_khong_con_vinh_vien_chua_tinh_duoc():
    from decision.decision_log import load_decisions

    hist_path = ROOT / "data" / "history.jsonl"
    if not hist_path.exists():
        pytest.skip("chưa có data/history.jsonl")
    hist = [json.loads(l) for l in hist_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    s = summarize([review_one(d, hist) for d in load_decisions()])
    assert s["scored"] > 0, "không quyết định nào được chấm — thước đo lại tự bảo vệ mình"
    assert s["accuracy_pct"] is not None


def test_best_measurement_tra_None_thay_vi_doan_bua():
    assert best_measurement(_decision("2026-07-22", "sang"), []) is None
    assert best_measurement({"date": "x", "ky": "sang"}, []) is None

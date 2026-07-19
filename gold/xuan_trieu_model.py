"""Mô hình ước tính giá vàng nhẫn tại tiệm Xuân Triệu từ giá vàng thế giới.

Công thức: quy đổi giá thế giới ra VND/lượng bằng gold.conversion, rồi nhân
hệ số tỷ lệ k (k_buy, k_sell) suy ra từ (các) điểm hiệu chuẩn thực tế —
ảnh bảng giá tiệm do chủ dự án chụp gửi. Hiện chỉ có 1 điểm hiệu chuẩn
(2026-07-18) nên `confidence` luôn là LOW cho tới khi có thêm ảnh mới.

KHÔNG bịa MAE khi chưa đủ mẫu — xem `mae()`.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from gold.conversion import theoretical_trieu_per_tael

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "data" / "gold_model.json"
HISTORY_CSV = ROOT / "data" / "normalized" / "xuan_trieu_gold_history.csv"
MARKET_HISTORY_JSONL = ROOT / "data" / "history.jsonl"

# Dưới ngưỡng này, confidence luôn LOW — chưa đủ mẫu để tin mô hình hiệu chuẩn
MIN_SAMPLES_FOR_MEDIUM_CONFIDENCE = 5
MIN_SAMPLES_FOR_HIGH_CONFIDENCE = 20


@dataclass
class GoldEstimate:
    xau_usd: float
    usd_vnd: float
    world_per_tael_trieu: float
    shop_buy_trieu: float
    shop_sell_trieu: float
    k_buy: float
    k_sell: float
    calibration_date: str
    shop_name: str
    sample_size: int
    confidence: str  # LOW | MEDIUM | HIGH


def _load_model() -> dict:
    return json.loads(MODEL_PATH.read_text(encoding="utf-8"))


def _latest_xau_fx_from_market_history() -> tuple[Optional[float], Optional[float]]:
    if not MARKET_HISTORY_JSONL.exists():
        return None, None
    lines = [json.loads(l) for l in MARKET_HISTORY_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
    xau = fx = None
    for s in reversed(lines):
        if xau is None:
            xau = (s.get("gold") or {}).get("xauusd")
        if fx is None:
            fx = s.get("fx_vcb_sell")
        if xau and fx:
            break
    return xau, fx


def calibration_sample_size() -> int:
    """Số điểm hiệu chuẩn thực tế đã ghi nhận (số dòng dữ liệu trong CSV lịch sử)."""
    if not HISTORY_CSV.exists():
        return 0
    with HISTORY_CSV.open(encoding="utf-8") as f:
        return max(0, sum(1 for _ in f) - 1)  # trừ header


def _confidence_for(n: int) -> str:
    if n >= MIN_SAMPLES_FOR_HIGH_CONFIDENCE:
        return "HIGH"
    if n >= MIN_SAMPLES_FOR_MEDIUM_CONFIDENCE:
        return "MEDIUM"
    return "LOW"


def estimate(xau_usd: Optional[float] = None, usd_vnd: Optional[float] = None) -> Optional[GoldEstimate]:
    model = _load_model()
    cal = model["calibration"]
    if xau_usd is None or usd_vnd is None:
        lx, lfx = _latest_xau_fx_from_market_history()
        xau_usd = xau_usd if xau_usd is not None else lx
        usd_vnd = usd_vnd if usd_vnd is not None else lfx
    if not xau_usd or not usd_vnd:
        return None

    world_cal = cal.get("world_per_luong_trieu") or theoretical_trieu_per_tael(cal["xauusd"], cal["fx_vcb_sell"])
    k_buy = cal["shop_buy_trieu"] / world_cal
    k_sell = cal["shop_sell_trieu"] / world_cal
    world_now = theoretical_trieu_per_tael(xau_usd, usd_vnd)
    n = max(1, calibration_sample_size())  # ít nhất 1 vì bản thân calibration là 1 điểm

    return GoldEstimate(
        xau_usd=xau_usd,
        usd_vnd=usd_vnd,
        world_per_tael_trieu=round(world_now, 2),
        shop_buy_trieu=round(world_now * k_buy, 2),
        shop_sell_trieu=round(world_now * k_sell, 2),
        k_buy=round(k_buy, 5),
        k_sell=round(k_sell, 5),
        calibration_date=cal["date"],
        shop_name=model["calibration"]["shop_name"],
        sample_size=n,
        confidence=_confidence_for(n),
    )


def record_calibration_point(
    date: str,
    xau_usd: float,
    usd_vnd: float,
    shop_buy_trieu: float,
    shop_sell_trieu: float,
    predicted_shop_buy_trieu: Optional[float] = None,
) -> None:
    """Ghi 1 điểm hiệu chuẩn thực tế (từ ảnh bảng giá mới) vào lịch sử.

    `predicted_shop_buy_trieu`: nếu có, là giá mô hình ĐÃ dự báo cho ngày này
    TRƯỚC khi biết giá thật — dùng để tính sai số dự báo (MAE) sau này. Để
    trống nếu đây là lần hiệu chuẩn mà trước đó chưa từng dự báo được (VD
    lần đầu tiên).
    """
    HISTORY_CSV.parent.mkdir(parents=True, exist_ok=True)
    is_new = not HISTORY_CSV.exists()
    world = theoretical_trieu_per_tael(xau_usd, usd_vnd)
    error = None
    if predicted_shop_buy_trieu is not None:
        error = round(abs(predicted_shop_buy_trieu - shop_buy_trieu), 3)
    with HISTORY_CSV.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(
                [
                    "date",
                    "xau_usd",
                    "usd_vnd",
                    "world_per_tael_trieu",
                    "shop_buy_trieu",
                    "shop_sell_trieu",
                    "premium_buy_trieu",
                    "abs_error_vs_prediction_trieu",
                ]
            )
        w.writerow(
            [
                date,
                xau_usd,
                usd_vnd,
                round(world, 2),
                shop_buy_trieu,
                shop_sell_trieu,
                round(shop_buy_trieu - world, 2),
                error if error is not None else "",
            ]
        )


def mae(max_points: Optional[int] = None) -> dict:
    """Sai số dự báo trung bình (MAE) dựa trên lịch sử hiệu chuẩn.

    Trả `mae=None, confidence="LOW"` khi chưa đủ ít nhất 2 điểm có so sánh
    dự báo — KHÔNG được bịa số MAE khi thiếu dữ liệu.
    """
    if not HISTORY_CSV.exists():
        return {"sample_size": 0, "mae_trieu": None, "confidence": "LOW",
                "reason": "chưa có lịch sử hiệu chuẩn nào"}
    rows = list(csv.DictReader(HISTORY_CSV.open(encoding="utf-8")))
    if max_points:
        rows = rows[-max_points:]
    valid = [r for r in rows if r.get("abs_error_vs_prediction_trieu")]
    if len(valid) < 2:
        return {
            "sample_size": len(rows),
            "mae_trieu": None,
            "confidence": "LOW",
            "reason": f"chưa đủ mẫu để tính MAE (cần >=2 điểm có so sánh dự báo, hiện có {len(valid)})",
        }
    errs = [abs(float(r["abs_error_vs_prediction_trieu"])) for r in valid]
    return {
        "sample_size": len(valid),
        "mae_trieu": round(sum(errs) / len(errs), 3),
        "confidence": _confidence_for(len(valid)),
    }

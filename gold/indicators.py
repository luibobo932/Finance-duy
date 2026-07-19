"""Chỉ báo kỹ thuật cho giá vàng — dùng chung analytics/ta_core.py với cổ phiếu.

Đọc lịch sử từ data/normalized/xuan_trieu_gold_history.csv. Hiện chỉ có 1
dòng lịch sử (Phase 4 mới tạo file) nên mọi chỉ báo sẽ trả None cho tới khi
tích lũy đủ — đây là hành vi ĐÚNG (dữ liệu thiếu thật), không phải lỗi.

QUAN TRỌNG: `trend_label()` ở đây chỉ trả xu hướng THỊ TRƯỜNG thuần túy
(TICH_CUC/TIEU_CUC/TRUNG_TINH). Hành động danh mục (GIỮ/CHỐT BỚT/...) KHÔNG
được quyết định ở module này — đó là việc của decision/policy_engine.py
(Phase 7), vì nó còn phụ thuộc tỷ trọng danh mục và hạn mức rủi ro, không
chỉ xu hướng giá.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from analytics.ta_core import atr, bollinger, macd, rsi, sma, volatility_annualized_pct

ROOT = Path(__file__).resolve().parent.parent
HISTORY_CSV = ROOT / "data" / "normalized" / "xuan_trieu_gold_history.csv"


def load_series(column: str = "shop_buy_trieu") -> list[tuple[str, float]]:
    if not HISTORY_CSV.exists():
        return []
    out = []
    with HISTORY_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                out.append((r["date"], float(r[column])))
            except (ValueError, KeyError, TypeError):
                continue
    return out


def analyze(column: str = "shop_buy_trieu") -> dict:
    series = load_series(column)
    closes = [p for _, p in series]
    n = len(closes)
    return {
        "column": column,
        "sessions": n,
        "last_value": closes[-1] if closes else None,
        "last_date": series[-1][0] if series else None,
        "rsi14": rsi(closes),
        "macd": macd(closes),
        "sma20": sma(closes, 20),
        "sma50": sma(closes, 50),
        "sma200": sma(closes, 200),
        "bollinger": bollinger(closes),
        "volatility_20d_annualized_pct": volatility_annualized_pct(closes, 20),
        "needed_for_full_history": max(0, 200 - n),
    }


def trend_label(a: dict) -> str:
    """Xu hướng kỹ thuật thuần túy — KHÔNG phải hành động danh mục.

    Trả TRUNG_TINH khi chưa đủ dữ liệu (rsi14 hoặc macd đều None) thay vì
    suy diễn từ dữ liệu thiếu.
    """
    r = a.get("rsi14")
    m = a.get("macd")
    if r is None or m is None:
        return "TRUNG_TINH"
    score = 0
    if r > 55:
        score += 1
    elif r < 45:
        score -= 1
    if m["hist"] > 0:
        score += 1
    elif m["hist"] < 0:
        score -= 1
    if score >= 1:
        return "TICH_CUC"
    if score <= -1:
        return "TIEU_CUC"
    return "TRUNG_TINH"

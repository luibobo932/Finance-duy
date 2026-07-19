"""Phát hiện giao dịch bất thường trên khớp lệnh — dấu hiệu tổ chức/nội bộ
gom hoặc xả hàng.

CHỈ được kết luận "cần theo dõi, chưa đủ căn cứ" — KHÔNG BAO GIỜ kết luận
"giao dịch nội gián"/"insider trading" một cách khẳng định, vì dữ liệu
khớp lệnh công khai không thể chứng minh động cơ giao dịch.
"""
from __future__ import annotations

from typing import Optional

BIG_ORDER_DEFAULT = 10_000  # cp
ROUND_LOTS_DEFAULT = (10_000, 20_000, 50_000, 100_000, 200_000, 500_000)
REPEAT_THRESHOLD = 3  # số lần lặp tối thiểu để coi là "chuỗi lệnh tròn số"


def detect(
    ticker: str,
    rows: list[tuple[str, float, float]],
    big_order: int = BIG_ORDER_DEFAULT,
    round_lots: tuple = ROUND_LOTS_DEFAULT,
) -> dict:
    """`rows`: list (thời_gian, giá, khối_lượng) — từng lệnh khớp hoặc nến phút.

    Trả dict đúng format chuẩn:
      {"ticker", "alert_level" (0-5), "anomaly_type", "evidence": [...], "conclusion"}
    """
    if not rows:
        return {
            "ticker": ticker, "alert_level": 0, "anomaly_type": "no_data",
            "evidence": [], "conclusion": "Không có dữ liệu để phân tích",
        }

    total_vol = sum(v for _, _, v in rows)
    big = [(t, p, v) for t, p, v in rows if v >= big_order]
    round_big = [(t, p, v) for t, p, v in big if any(v == lot or v % lot == 0 for lot in round_lots)]

    freq: dict[float, int] = {}
    for _, _, v in round_big:
        freq[v] = freq.get(v, 0) + 1
    repeated = sorted(((v, n) for v, n in freq.items() if n >= REPEAT_THRESHOLD), key=lambda x: -x[1])

    evidence: list[str] = []
    anomaly_types: list[str] = []
    alert_level = 0

    if repeated:
        anomaly_types.append("repeated_round_lot_orders")
        alert_level = max(alert_level, min(5, 2 + len(repeated)))
        for v, n in repeated:
            times = [t for t, _, vv in round_big if vv == v]
            evidence.append(f"{v:,.0f} cp lặp {n} lần ({times[0]} → {times[-1]})")

    big_share = (sum(v for _, _, v in big) / total_vol) if total_vol else 0
    if big_share >= 0.5:
        anomaly_types.append("unusual_volume")
        alert_level = max(alert_level, 2)
        evidence.append(f"Lệnh lớn (≥{big_order:,}cp) chiếm {big_share*100:.1f}% tổng khối lượng")

    if not anomaly_types:
        return {
            "ticker": ticker, "alert_level": 0, "anomaly_type": "none",
            "evidence": [f"Tổng {len(rows)} bản ghi, {total_vol:,.0f}cp — không thấy mẫu bất thường"],
            "conclusion": "Không phát hiện dấu hiệu bất thường đáng chú ý",
        }

    return {
        "ticker": ticker,
        "alert_level": alert_level,
        "anomaly_type": anomaly_types[0],
        "anomaly_types": anomaly_types,
        "evidence": evidence,
        "conclusion": "Cần theo dõi, chưa đủ căn cứ kết luận giao dịch nội bộ",
    }


def top_volume_records(rows: list[tuple[str, float, float]], n: int = 10,
                        round_lots: tuple = ROUND_LOTS_DEFAULT, big_order: int = BIG_ORDER_DEFAULT) -> list[dict]:
    """N bản ghi khối lượng lớn nhất, đánh dấu cái nào là lệnh tròn số."""
    top = sorted(rows, key=lambda x: -x[2])[:n]
    return [
        {
            "time": t, "price": p, "volume": v,
            "is_round_lot": any(v == lot or (v >= big_order and v % lot == 0) for lot in round_lots),
        }
        for t, p, v in top
    ]

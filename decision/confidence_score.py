"""Tính điểm tin cậy (0-100) cho 1 quyết định bằng công thức tường minh —
KHÔNG để AI tự "cho điểm" cảm tính.

Điểm tổng hợp có trọng số từ: độ đầy đủ dữ liệu, độ mới dữ liệu, mức đồng
thuận tín hiệu (kỹ thuật/cơ bản/dòng tiền có cùng hướng không), độ chính
xác lịch sử (từ evaluation/decision_review.py, Phase 9 — None nếu chưa có
lịch sử, dùng giá trị trung tính 50), mức xung đột nguồn, mức rủi ro danh
mục hiện tại.
"""
from __future__ import annotations

from typing import Optional

# Trọng số phải cộng lại = 1.0 — kiểm tra bằng test
WEIGHTS = {
    "completeness": 0.25,
    "freshness": 0.20,
    "agreement": 0.25,
    "historical": 0.15,
    "conflict": 0.10,
    "risk": 0.05,
}

NEUTRAL_HISTORICAL_SCORE = 50.0  # dùng khi chưa có lịch sử quyết định (Phase 9)


def compute_confidence(
    data_completeness_pct: float,
    data_freshness_score: float,
    signal_agreement_pct: float,
    historical_accuracy_pct: Optional[float] = None,
    source_conflict_penalty: float = 0.0,
    risk_level_penalty: float = 0.0,
) -> int:
    """Mọi input trong thang 0-100. Trả điểm nguyên 0-100."""
    hist = historical_accuracy_pct if historical_accuracy_pct is not None else NEUTRAL_HISTORICAL_SCORE
    raw = (
        _clamp(data_completeness_pct) * WEIGHTS["completeness"]
        + _clamp(data_freshness_score) * WEIGHTS["freshness"]
        + _clamp(signal_agreement_pct) * WEIGHTS["agreement"]
        + _clamp(hist) * WEIGHTS["historical"]
        + _clamp(100 - source_conflict_penalty) * WEIGHTS["conflict"]
        + _clamp(100 - risk_level_penalty) * WEIGHTS["risk"]
    )
    return round(_clamp(raw))


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def signal_agreement_from_labels(*labels: Optional[str]) -> float:
    """% đồng thuận giữa các nhãn xu hướng (VD kỹ thuật + cơ bản + dòng tiền).

    Bỏ qua nhãn None (thiếu tín hiệu đó). Trả 50 (trung tính) nếu không có
    nhãn nào — không bịa đồng thuận khi hoàn toàn thiếu dữ liệu.
    """
    present = [l for l in labels if l]
    if not present:
        return 50.0
    from collections import Counter

    counts = Counter(present)
    most_common_count = counts.most_common(1)[0][1]
    return round(most_common_count / len(present) * 100, 1)

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


# Cần ít nhất bằng này tín hiệu thì "đồng thuận" mới là một phép đo. Một mình
# thì luôn nhất trí với chính mình.
MIN_SIGNALS_FOR_AGREEMENT = 2


def signal_agreement_from_labels(*labels: Optional[str]) -> float:
    """% đồng thuận giữa các nhãn xu hướng (VD kỹ thuật + cơ bản + dòng tiền).

    Bỏ qua nhãn None (thiếu tín hiệu đó). Trả 50 (trung tính) nếu có DƯỚI
    `MIN_SIGNALS_FOR_AGREEMENT` nhãn.

    Vì sao ngưỡng 2 chứ không phải 1: với đúng một nhãn, công thức cũ tính
    1/1 = **100% đồng thuận** — nghe như ba nguồn độc lập cùng xác nhận, trong
    khi thực tế chỉ có một nguồn và không có gì kiểm chứng nó. Đây không phải
    giả định: hệ thống chỉ nối được `trend_label` cho vàng (`fundamental_label`
    và `flow_label` luôn None), nên thành phần đồng thuận — **25% trọng số** —
    được chấm tuyệt đối 100 ở cả 13 quyết định đã ghi, góp phần khoá điểm tin
    cậy ở đúng con số 92 suốt từ 20/7 đến 10/8.

    Đồng thuận là phép đo giữa NHIỀU nguồn. Thiếu nguồn thứ hai thì phép đo
    không tồn tại, và trung tính 50 là câu trả lời trung thực — giống hệt cách
    xử lý khi không có nhãn nào.
    """
    present = [l for l in labels if l]
    if len(present) < MIN_SIGNALS_FOR_AGREEMENT:
        return 50.0
    from collections import Counter

    counts = Counter(present)
    most_common_count = counts.most_common(1)[0][1]
    return round(most_common_count / len(present) * 100, 1)

"""Kiểm tra chất lượng dữ liệu: cũ, thiếu, bất thường, xung đột nguồn.

Không có hàm nào ở đây được phép "vá" dữ liệu thiếu bằng 0 — chỉ được
báo cáo trạng thái để tầng trên (Risk Officer, Phase 7) quyết định có
đủ điều kiện ra quyết định hay không.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from .schema import DataPoint, SourceStatus


def _parse_iso(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def compute_freshness_seconds(fetched_at_iso: str, now: Optional[datetime] = None) -> float:
    """Số giây đã trôi qua kể từ khi số liệu được lấy."""
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - _parse_iso(fetched_at_iso)).total_seconds())


def is_missing(dp: DataPoint) -> bool:
    return dp.value is None


def is_stale(dp: DataPoint, max_age_seconds: float, now: Optional[datetime] = None) -> bool:
    """Dữ liệu có bị coi là cũ so với ngưỡng cho phép không.

    Nếu không có `fetched_at`, coi như không xác định được độ mới -> STALE
    (an toàn hơn là giả định nó mới).
    """
    if dp.value is None:
        return False  # missing khác với stale — is_missing xử lý riêng
    if not dp.fetched_at:
        return True
    age = compute_freshness_seconds(dp.fetched_at, now)
    return age > max_age_seconds


def is_abnormal(dp: DataPoint, allow_zero: bool = False, allow_negative: bool = False) -> bool:
    """Giá trị âm hoặc bằng 0 bất thường (mặc định: giá/tỷ giá không được <=0).

    Đặt `allow_zero=True` cho các trường hợp lệ dĩ nhiên có thể bằng 0
    (VD: khối ngoại mua/bán ròng = 0, MACD histogram = 0).
    """
    if dp.value is None:
        return False
    if dp.value < 0 and not allow_negative:
        return True
    if dp.value == 0 and not allow_zero:
        return True
    return False


def compare_sources(dp_a: DataPoint, dp_b: DataPoint, tolerance_pct: float = 2.0) -> bool:
    """True nếu 2 nguồn cùng đo 1 đại lượng nhưng lệch nhau quá `tolerance_pct`%."""
    if dp_a.value is None or dp_b.value is None:
        return False
    base = max(abs(dp_a.value), abs(dp_b.value), 1e-9)
    diff_pct = abs(dp_a.value - dp_b.value) / base * 100
    return diff_pct > tolerance_pct


def evaluate_status(
    dp: DataPoint,
    max_age_seconds: float,
    allow_zero: bool = False,
    allow_negative: bool = False,
    conflicting_with: Optional[DataPoint] = None,
    tolerance_pct: float = 2.0,
) -> str:
    """Tính và gán `dp.status` (SourceStatus) dựa trên các kiểm tra trên.

    Thứ tự ưu tiên: FAILED (thiếu/bất thường) > CONFLICTING > STALE > DEGRADED > HEALTHY.
    """
    if is_missing(dp) or is_abnormal(dp, allow_zero=allow_zero, allow_negative=allow_negative):
        dp.status = SourceStatus.FAILED.value
        return dp.status
    if conflicting_with is not None and compare_sources(dp, conflicting_with, tolerance_pct):
        dp.status = SourceStatus.CONFLICTING.value
        return dp.status
    if dp.fetched_at:
        dp.freshness_seconds = compute_freshness_seconds(dp.fetched_at)
    if is_stale(dp, max_age_seconds):
        dp.status = SourceStatus.STALE.value
        return dp.status
    if dp.fallback_used or dp.confidence == "LOW":
        dp.status = SourceStatus.DEGRADED.value
        return dp.status
    dp.status = SourceStatus.HEALTHY.value
    return dp.status


def pick_with_fallback(
    candidates: Iterable[DataPoint],
    max_age_seconds: float,
    allow_zero: bool = False,
    allow_negative: bool = False,
) -> Optional[DataPoint]:
    """Chọn DataPoint đầu tiên còn HEALTHY/DEGRADED trong danh sách ưu tiên.

    `candidates` phải được truyền theo đúng thứ tự ưu tiên nguồn (nguồn tốt
    nhất trước). Nguồn nào bị bỏ qua (do FAILED/STALE/CONFLICTING) khiến
    DataPoint được chọn (nếu không phải cái đầu) có `fallback_used=True`.
    Trả về None nếu KHÔNG có candidate nào dùng được — tầng trên phải xử lý
    như "CHƯA ĐỦ DỮ LIỆU", không được tự chế số liệu.
    """
    cands = list(candidates)
    for i, dp in enumerate(cands):
        status = evaluate_status(dp, max_age_seconds, allow_zero=allow_zero, allow_negative=allow_negative)
        if status in (SourceStatus.HEALTHY.value, SourceStatus.DEGRADED.value):
            if i > 0:
                dp.fallback_used = True
                dp.status = SourceStatus.DEGRADED.value
            return dp
    return None


def requires_no_decision(
    datapoints: Iterable[DataPoint], critical_names: Optional[set[str]] = None
) -> tuple[bool, list[str]]:
    """Kiểm tra xem có nên trả về "CHƯA ĐỦ DỮ LIỆU ĐỂ RA QUYẾT ĐỊNH" không.

    `critical_names`: tên các DataPoint bắt buộc phải HEALTHY/DEGRADED; nếu
    None, mọi DataPoint truyền vào đều được coi là quan trọng.
    """
    reasons: list[str] = []
    for dp in datapoints:
        if critical_names is not None and dp.name not in critical_names:
            continue
        if dp.status in (SourceStatus.FAILED.value, SourceStatus.STALE.value, SourceStatus.CONFLICTING.value):
            reasons.append(f"{dp.name}: {dp.status}")
        elif dp.is_missing:
            reasons.append(f"{dp.name}: MISSING")
    return (len(reasons) > 0, reasons)

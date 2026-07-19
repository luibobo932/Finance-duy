"""Định giá cổ phiếu: P/E, P/B, biên an toàn, so lịch sử/ngành, 3 kịch bản.

Toàn bộ hàm là công thức thuần túy — không tự fetch dữ liệu, nhận input do
caller cung cấp (từ equity/fundamentals.py hoặc nhập tay có nguồn rõ ràng).
"""
from __future__ import annotations

from typing import Optional


def pe_ratio(price: float, eps: Optional[float]) -> Optional[float]:
    if not eps or eps <= 0:
        return None
    return round(price / eps, 2)


def pb_ratio(price: float, book_value_per_share: Optional[float]) -> Optional[float]:
    if not book_value_per_share or book_value_per_share <= 0:
        return None
    return round(price / book_value_per_share, 2)


def margin_of_safety_pct(intrinsic_value: Optional[float], price: float) -> Optional[float]:
    """(intrinsic - price) / intrinsic * 100 — dương nghĩa là giá đang RẺ hơn giá trị nội tại."""
    if not intrinsic_value or intrinsic_value <= 0:
        return None
    return round((intrinsic_value - price) / intrinsic_value * 100, 1)


def percentile_rank(current: float, historical: list[float]) -> Optional[float]:
    """Vị trí phần trăm của `current` trong chuỗi lịch sử — 0% = thấp nhất
    lịch sử (rẻ nhất), 100% = cao nhất lịch sử (đắt nhất). None nếu thiếu
    dữ liệu lịch sử.
    """
    if not historical:
        return None
    below = sum(1 for h in historical if h <= current)
    return round(below / len(historical) * 100, 1)


def scenario_fair_values(eps: Optional[float], pe_low: float, pe_base: float, pe_high: float) -> Optional[dict]:
    """3 kịch bản định giá (thấp/cơ sở/cao) dựa trên EPS hiện tại × dải P/E mục tiêu.

    Trả None nếu thiếu EPS — không tự bịa định giá khi thiếu số liệu cơ bản.
    """
    if not eps or eps <= 0:
        return None
    return {
        "low": round(eps * pe_low, 0),
        "base": round(eps * pe_base, 0),
        "high": round(eps * pe_high, 0),
    }


def valuation_read(pe: Optional[float], pe_history: Optional[list[float]] = None,
                    pb: Optional[float] = None, pb_history: Optional[list[float]] = None) -> list[str]:
    """Diễn giải P/E, P/B hiện tại so với lịch sử thành nhận định ngắn.

    Chỉ diễn giải khi CÓ đủ dữ liệu — không tự đưa nhận định khi thiếu.
    """
    notes = []
    if pe is not None:
        if pe_history:
            pct = percentile_rank(pe, pe_history)
            notes.append(f"P/E {pe} — ở mức {pct}% dải lịch sử ({'rẻ' if pct is not None and pct < 30 else 'đắt' if pct is not None and pct > 70 else 'trung bình'})")
        else:
            notes.append(f"P/E {pe} (chưa có lịch sử để so sánh)")
    if pb is not None:
        if pb_history:
            pct = percentile_rank(pb, pb_history)
            notes.append(f"P/B {pb} — ở mức {pct}% dải lịch sử ({'rẻ' if pct is not None and pct < 30 else 'đắt' if pct is not None and pct > 70 else 'trung bình'})")
        else:
            notes.append(f"P/B {pb} (chưa có lịch sử để so sánh)")
    return notes

"""Dữ liệu thị trường tổng quan: VN-Index, độ rộng, dòng vốn khối ngoại/tự
doanh/ETF. Nhận input do caller cung cấp — không tự fetch."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class MarketBreadth:
    advancers: int
    decliners: int
    unchanged: int = 0

    @property
    def ratio(self) -> Optional[float]:
        """advancers/decliners — None nếu cả 2 đều 0 (không có dữ liệu)."""
        if self.decliners == 0:
            return None if self.advancers == 0 else float("inf")
        return round(self.advancers / self.decliners, 2)

    @property
    def label(self) -> str:
        r = self.ratio
        if r is None:
            return "TRUNG_TINH"
        if r == float("inf") or r >= 2:
            return "TICH_CUC"
        if r <= 0.5:
            return "TIEU_CUC"
        return "TRUNG_TINH"


@dataclass
class CapitalFlow:
    """Dòng vốn 1 nhóm (khối ngoại/tự doanh/ETF), đơn vị tỷ đồng. Âm = bán ròng."""

    label: str
    net_value_ty: Optional[float]

    @property
    def direction(self) -> str:
        if self.net_value_ty is None:
            return "KHONG_RO"
        if self.net_value_ty > 0:
            return "MUA_RONG"
        if self.net_value_ty < 0:
            return "BAN_RONG"
        return "TRUNG_LAP"


def streak(values_oldest_to_newest: list[float]) -> dict:
    """Chuỗi mua/bán ròng liên tiếp gần nhất — dùng lại logic đã có trong
    scripts/trend.py nhưng tách thành hàm thuần túy để equity/market.py và
    trend.py có thể dùng chung nếu cần (Phase 8 sẽ wire).
    """
    if not values_oldest_to_newest:
        return {"streak": 0, "direction": "KHONG_RO", "total_ty": 0.0}
    sign = 1 if values_oldest_to_newest[-1] > 0 else -1 if values_oldest_to_newest[-1] < 0 else 0
    if sign == 0:
        return {"streak": 0, "direction": "TRUNG_LAP", "total_ty": 0.0}
    count, total = 0, 0.0
    for v in reversed(values_oldest_to_newest):
        if v * sign > 0:
            count += 1
            total += v
        else:
            break
    return {
        "streak": count,
        "direction": "MUA_RONG" if sign > 0 else "BAN_RONG",
        "total_ty": round(total, 1),
    }

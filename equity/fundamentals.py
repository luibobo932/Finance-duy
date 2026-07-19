"""Chỉ tiêu cơ bản doanh nghiệp: ROE, ROA, biên lợi nhuận, đòn bẩy, chất
lượng dòng tiền.

Chưa có API BCTC miễn phí đáng tin cho VCB/CTD — dữ liệu phải NHẬP TAY từ
báo cáo tài chính công bố, đánh dấu `source="BCTC_manual_entry"` (xem
docs/AUDIT_REPORT.md, docs/IMPLEMENTATION_PLAN.md Phase 6). File này chỉ
định nghĩa schema + công thức, KHÔNG chứa số liệu bịa cho VCB/CTD.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Fundamentals:
    ticker: str
    period: str  # VD "2026Q2"
    revenue_vnd: Optional[float] = None
    net_income_vnd: Optional[float] = None
    total_equity_vnd: Optional[float] = None
    total_assets_vnd: Optional[float] = None
    total_debt_vnd: Optional[float] = None
    operating_cash_flow_vnd: Optional[float] = None
    receivables_vnd: Optional[float] = None
    inventory_vnd: Optional[float] = None
    source: str = "BCTC_manual_entry"

    @property
    def roe_pct(self) -> Optional[float]:
        if not self.net_income_vnd or not self.total_equity_vnd:
            return None
        return round(self.net_income_vnd / self.total_equity_vnd * 100, 2)

    @property
    def roa_pct(self) -> Optional[float]:
        if not self.net_income_vnd or not self.total_assets_vnd:
            return None
        return round(self.net_income_vnd / self.total_assets_vnd * 100, 2)

    @property
    def net_margin_pct(self) -> Optional[float]:
        if not self.net_income_vnd or not self.revenue_vnd:
            return None
        return round(self.net_income_vnd / self.revenue_vnd * 100, 2)

    @property
    def debt_to_equity(self) -> Optional[float]:
        if self.total_debt_vnd is None or not self.total_equity_vnd:
            return None
        return round(self.total_debt_vnd / self.total_equity_vnd, 2)

    @property
    def cash_flow_to_income_ratio(self) -> Optional[float]:
        """Dòng tiền kinh doanh / lợi nhuận ròng — < 1 nhiều kỳ liên tiếp là
        cờ đỏ về CHẤT LƯỢNG lợi nhuận (lãi trên sổ sách nhưng không thu được tiền)."""
        if not self.net_income_vnd or self.operating_cash_flow_vnd is None:
            return None
        return round(self.operating_cash_flow_vnd / self.net_income_vnd, 2)


def quality_flags(f: Fundamentals) -> list[str]:
    """Cờ cảnh báo chất lượng lợi nhuận — chỉ nêu khi CÓ đủ dữ liệu để tính."""
    flags = []
    cf_ratio = f.cash_flow_to_income_ratio
    if cf_ratio is not None and cf_ratio < 0.7:
        flags.append(f"Dòng tiền KD/Lợi nhuận ròng = {cf_ratio} (<0.7) — cần soi khoản phải thu/tồn kho")
    de = f.debt_to_equity
    if de is not None and de > 2:
        flags.append(f"Nợ/Vốn chủ sở hữu = {de} (>2) — đòn bẩy cao")
    return flags

"""Schema chuẩn cho 1 mức lãi suất tiết kiệm ngân hàng."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DepositRate:
    bank: str
    term_months: int
    rate_online: Optional[float] = None  # %/năm
    rate_counter: Optional[float] = None  # %/năm
    min_deposit_vnd: Optional[float] = None
    conditions: str = ""
    interest_payment: str = "cuoi_ky"  # cuoi_ky | hang_thang
    early_withdrawal_note: str = ""
    updated_at: str = ""
    source: str = ""

    @property
    def best_rate_pct(self) -> Optional[float]:
        rates = [r for r in (self.rate_online, self.rate_counter) if r is not None]
        return max(rates) if rates else None

    @property
    def best_channel(self) -> Optional[str]:
        if self.rate_online is None and self.rate_counter is None:
            return None
        if self.rate_counter is None or (self.rate_online or -1) >= self.rate_counter:
            return "online"
        return "counter"

    @classmethod
    def from_dict(cls, d: dict) -> "DepositRate":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

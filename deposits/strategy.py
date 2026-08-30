"""Chiến lược chia kỳ hạn tiền gửi: quỹ dự phòng + chia theo kỳ hạn theo
lãi suất tốt nhất đã xếp hạng (deposits/ranking.py)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

DAYS_PER_MONTH = 30  # xấp xỉ đủ dùng cho lập kế hoạch, không dùng để tính lãi

# Trọng số mặc định chia vốn khả dụng theo kỳ hạn (tổng = 1.0)
DEFAULT_TERM_WEIGHTS: dict[int, float] = {6: 0.30, 12: 0.40, 13: 0.30}

# Lãi suất không kỳ hạn giả định khi rút trước hạn (theo quy định phổ biến)
UNQUALIFIED_WITHDRAWAL_RATE_PCT = 0.5


@dataclass
class DepositAllocation:
    label: str
    term_months: int
    amount_vnd: float
    rate_pct: float
    bank: str
    start_date: date

    @property
    def maturity_date(self) -> date:
        return self.start_date + timedelta(days=DAYS_PER_MONTH * self.term_months)

    @property
    def expected_interest_vnd(self) -> float:
        return self.amount_vnd * self.rate_pct / 100 * self.term_months / 12

    def early_withdrawal_loss_vnd(
        self, unqualified_rate_pct: float = UNQUALIFIED_WITHDRAWAL_RATE_PCT
    ) -> float:
        """Số tiền lãi bị MẤT nếu rút trước hạn (so với lãi đúng hạn)."""
        actual_if_withdrawn_early = self.amount_vnd * unqualified_rate_pct / 100 * self.term_months / 12
        return self.expected_interest_vnd - actual_if_withdrawn_early


def buffer_needed_from_savings(buffer_vnd: float, liquid_cash_vnd: float) -> float:
    """Còn phải chừa BAO NHIÊU từ khoản tiết kiệm cho quỹ khẩn cấp.

    Quỹ khẩn cấp là yêu cầu ở tầng DANH MỤC, không phải yêu cầu riêng của
    khoản tiết kiệm: tiền mặt đang nắm đã tính vào đó rồi. Bỏ qua điều này
    thì cùng một quỹ bị chừa HAI LẦN.

    Lỗi thật, đo ngày 30/08 trên chính config của dự án:

        risk_limits: minimum_cash_buffer_vnd = 30 tr
        tiền mặt 35 tr − 30 tr  → run_morning: "tiền khả dụng ngay chỉ 5 tr"   ✓ đúng
        tiết kiệm 246 tr − 30 tr → deposits_report chia kỳ hạn trên 216 tr     ✗ chừa lần hai

    Tổng chừa 60 tr trong khi hạn mức chỉ yêu cầu 30 tr. Hệ quả: **30 tr tiết
    kiệm nằm ngoài kế hoạch**, và ở mức tốt nhất đo được 8,00%/năm đó là
    **2,4 tr/năm tiền lãi bị bỏ lỡ** — trong đúng module sinh ra để tối đa hoá
    lãi tiền gửi.

    Trả về phần CÒN THIẾU sau khi trừ tiền mặt. Tiền mặt đã đủ quỹ → trả 0.
    """
    return max(0.0, float(buffer_vnd or 0) - float(liquid_cash_vnd or 0))


def split_strategy(
    total_vnd: float,
    emergency_buffer_vnd: float,
    ranked_rates: list[dict],
    term_weights: Optional[dict[int, float]] = None,
    start_date: Optional[date] = None,
) -> list[DepositAllocation]:
    """Chia `total_vnd` (sau khi trừ quỹ khẩn cấp) theo trọng số kỳ hạn,
    ưu tiên ngân hàng có lãi cao nhất mỗi kỳ hạn trong `ranked_rates`
    (đầu ra của `deposits.ranking.rank()` — đã loại các mức không hợp lệ).

    Bỏ qua kỳ hạn nào không tìm được ngân hàng phù hợp trong `ranked_rates`
    thay vì tự chế mức lãi suất giả định.
    """
    from .ranking import top_by_term

    term_weights = term_weights or DEFAULT_TERM_WEIGHTS
    start_date = start_date or date.today()
    investable = max(0.0, total_vnd - emergency_buffer_vnd)
    allocations: list[DepositAllocation] = []
    for term, weight in term_weights.items():
        amount = investable * weight
        if amount <= 0:
            continue
        best = top_by_term(ranked_rates, term)
        if best is None:
            continue
        allocations.append(
            DepositAllocation(
                label=f"Kỳ hạn {term} tháng",
                term_months=best["term_months"],
                amount_vnd=amount,
                rate_pct=best["rate_pct"],
                bank=best["bank"],
                start_date=start_date,
            )
        )
    return allocations


def total_expected_interest_vnd(allocations: list[DepositAllocation]) -> float:
    return sum(a.expected_interest_vnd for a in allocations)

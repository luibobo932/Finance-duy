"""Đo CHI PHÍ của lời khuyên phòng thủ — thứ decision review không chấm được.

Vì sao cần: `analytics/decision_review.py` chỉ chấm điểm những quyết định có
hướng giá (mua/bán theo dự báo). GIỮ và CHỐT BỚT bị xếp "quản trị rủi ro, không
chấm" — đúng về nguyên tắc, vì chúng KHÔNG phải dự báo giá. Nhưng hệ quả là
11/13 quyết định trong `data/decisions.jsonl` không bao giờ được đánh giá,
accuracy vĩnh viễn không tính được, và thành phần "lịch sử" (15% trọng số) của
confidence score mãi mãi dùng giá trị trung tính — hệ thống không học được gì
mà vẫn hiện "tin cậy 92/100".

Cách đo đúng cho hành động phòng thủ KHÔNG phải là "đúng hay sai hướng", mà là
**phí bảo hiểm**: chốt bớt để giảm rủi ro tập trung, và nếu giá sau đó tăng thì
phần tăng bị bỏ lỡ chính là phí đã trả cho việc giảm rủi ro đó. Bảo hiểm không
"sai" khi nhà không cháy — nhưng người mua vẫn có quyền biết mình đã trả bao
nhiêu.

Module này KHÔNG phán lời khuyên đúng hay sai. Nó trả lời câu người dùng thực
sự đang hỏi: "nghe theo CHỐT BỚT thì tới giờ tôi đã mất/được bao nhiêu?"

Chống look-ahead: chỉ dùng snapshot có kỳ SAU HẲN kỳ ra quyết định, qua đúng
hàm `later_snapshots` mà decision_review dùng — không có đường tắt nào khác.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from analytics.decision_review import APPROXIMATION_NOTE, best_measurement

# Hành động phòng thủ: giảm hoặc không tăng mức phơi nhiễm.
DEFENSIVE_ACTIONS = {"TAKE_PARTIAL_PROFIT", "DO_NOT_BUY_MORE"}
# GIỮ không phải hành động phòng thủ — nó là không làm gì, nên không có phí.
NEUTRAL_ACTIONS = {"HOLD", "WATCH", "STAND_ASIDE", "WAIT_FOR_CONFIRMATION"}

# FALLBACK_FIELDS và APPROXIMATION_NOTE nay sống ở analytics/decision_review.py
# và được import lại ở trên. Trước đây chúng khai ở ĐÂY, còn `review_one` bên
# kia thì không có cơ chế thay trường — nên hai module chấm cùng một quyết định
# ra +5,48% và +0,00%. Một định nghĩa, hai người dùng.


@dataclass
class OpportunityEntry:
    date: str
    ky: str
    asset: str
    action: str
    action_vi: str
    ref_price: Optional[float]
    later_price: Optional[float]
    later_date: Optional[str]
    change_pct: Optional[float]
    # Dương = giá tăng sau khi khuyên phòng thủ -> phí đã trả (bỏ lỡ tăng giá).
    # Âm  = giá giảm sau đó -> khuyến nghị đã tránh được khoản lỗ đó.
    premium_pct: Optional[float]
    note: str
    approximated: bool = False  # đo bằng trường giá thay thế, không phải trường gốc


@dataclass
class OpportunitySummary:
    n_defensive: int
    n_measured: int
    avg_premium_pct: Optional[float]
    worst_premium_pct: Optional[float]
    best_saving_pct: Optional[float]
    first_date: Optional[str]
    last_date: Optional[str]

    @property
    def verdict(self) -> str:
        """Câu kết luận trung thực, không phán đúng/sai."""
        if self.n_measured == 0:
            return ("Chưa đủ dữ liệu sau các khuyến nghị phòng thủ để đo chi phí — "
                    "cần thêm kỳ có giá.")
        if self.avg_premium_pct is None:
            return "Chưa tính được."
        if self.avg_premium_pct > 0:
            return (f"Trung bình mỗi khuyến nghị phòng thủ bỏ lỡ {self.avg_premium_pct:+.2f}% "
                    "tăng giá — đây là PHÍ đã trả để giảm rủi ro tập trung, không phải "
                    "bằng chứng khuyến nghị sai.")
        return (f"Trung bình mỗi khuyến nghị phòng thủ tránh được {abs(self.avg_premium_pct):.2f}% "
                "giảm giá — việc giảm tỷ trọng đã có lợi cả về giá.")


def measure_one(decision: dict, snapshots: Sequence[dict]) -> OpportunityEntry:
    """Đo phí cơ hội của MỘT quyết định, so với kỳ có giá gần nhất SAU đó."""
    base = OpportunityEntry(
        date=decision.get("date", ""), ky=decision.get("ky", ""),
        asset=decision.get("asset", ""), action=decision.get("action", ""),
        action_vi=decision.get("action_vi", ""), ref_price=decision.get("ref_price"),
        later_price=None, later_date=None, change_pct=None, premium_pct=None, note="",
    )
    if decision.get("action") not in DEFENSIVE_ACTIONS:
        base.note = "không phải hành động phòng thủ — không có phí cơ hội"
        return base
    ref = decision.get("ref_price")
    field = decision.get("ref_price_field")
    if not ref or not field:
        base.note = "thiếu giá tham chiếu tại thời điểm quyết định"
        return base

    m = best_measurement(decision, list(snapshots))
    if m is None:
        base.note = "chưa có kỳ nào sau đó có giá để so"
        return base
    approx, f, price, snap, change = (
        m["approximated"], m["field"], m["later_price"], m["snapshot"], m["change_pct"])
    base.later_price = price
    base.later_date = snap.get("date")
    base.change_pct = change
    # Chốt bớt rồi giá TĂNG = bỏ lỡ phần tăng đó = phí đã trả.
    base.premium_pct = change
    base.approximated = approx
    base.note = f"giá {f} đi {change:+.2f}% tới {snap.get('date')} ({snap.get('ky')})"
    if approx:
        base.note += f" — {APPROXIMATION_NOTE}"
    return base


def measure_all(decisions: Sequence[dict], snapshots: Sequence[dict]) -> list[OpportunityEntry]:
    return [measure_one(d, snapshots) for d in decisions]


def summarize(entries: Sequence[OpportunityEntry]) -> OpportunitySummary:
    defensive = [e for e in entries if e.action in DEFENSIVE_ACTIONS]
    measured = [e for e in defensive if e.premium_pct is not None]
    prems = [e.premium_pct for e in measured]
    dates = sorted(e.date for e in defensive if e.date)
    return OpportunitySummary(
        n_defensive=len(defensive),
        n_measured=len(measured),
        avg_premium_pct=(sum(prems) / len(prems)) if prems else None,
        worst_premium_pct=max(prems) if prems else None,
        best_saving_pct=min(prems) if prems else None,
        first_date=dates[0] if dates else None,
        last_date=dates[-1] if dates else None,
    )


def premium_in_vnd(
    premium_pct: float, amount_trieu: float, *, deposit_rate_pct: Optional[float] = None,
    days_held: Optional[int] = None,
) -> dict:
    """Quy phí cơ hội ra TIỀN cho một khoản đã chốt, và trừ lãi tiền gửi thu được.

    Chốt bớt không chỉ mất phần tăng giá — tiền thu về nằm trong ngân hàng và
    sinh lãi. Chỉ nêu vế mất mà giấu vế được là trình bày một nửa sự thật.
    """
    forgone = amount_trieu * premium_pct / 100
    interest = None
    if deposit_rate_pct is not None and days_held is not None:
        interest = amount_trieu * deposit_rate_pct / 100 * days_held / 365
    net = forgone - interest if interest is not None else None
    return {
        "amount_trieu": amount_trieu,
        "forgone_trieu": forgone,
        "interest_earned_trieu": interest,
        "net_cost_trieu": net,
    }

"""Mua BAO NHIÊU, ở GIÁ NÀO, và cắt lỗ ở đâu — vế còn thiếu của khuyến nghị mua.

`decision/rebalance.py` đã trả lời "bán bao nhiêu" cho vàng, và chính việc bổ
sung con số đó là thứ biến khuyến nghị CHỐT BỚT từ một hướng đi chung thành
việc làm được. Phía cổ phiếu chưa có gì tương đương: kể cả khi hệ thống nói
"MUA THĂM DÒ", nó không nói mua bao nhiêu tiền, vào vùng giá nào, và sai thì
thoát ở đâu. Một khuyến nghị mua thiếu ba thứ đó không thực hiện được.

Bốn ràng buộc, tất cả đều từ số thật chứ không từ cảm tính:

1. **Hạn mức danh mục** — `config/risk_limits.yaml`: 1 mã ≤ 10%, tổng cổ phiếu
   ≤ 20% tài sản ròng. Đây là trần cứng, không thương lượng.
2. **Rào lợi suất (hurdle)** — tiền gửi đang trả 8,0%/năm KHÔNG rủi ro. Một mã
   cổ phiếu chỉ đáng mua nếu kỳ vọng vượt được mức đó, chứ không phải vượt 0%.
   Đây là chỗ hầu hết khuyến nghị mua im lặng bỏ qua.
3. **Rủi ro/lợi nhuận đo từ hỗ trợ–kháng cự THẬT** (`equity/technical.py`),
   không phải từ một tỷ lệ đẹp gán sẵn. Giá nằm sát kháng cự thì R:R xấu dù
   doanh nghiệp tốt — đúng tình huống VCB ngày 10/8: giá 60,3 kẹt giữa hỗ trợ
   60,2 và kháng cự 61,0.
4. **Tiền phải có thật.** Chủ danh mục có 35 tr tiền mặt và quỹ khẩn cấp tối
   thiểu 30 tr — nên tiền mua PHẢI đến từ việc giảm tỷ trọng vàng, không phải
   từ việc rút cạn quỹ khẩn cấp. Module nói thẳng điều đó thay vì đưa ra một
   con số không có nguồn tiền.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Rủi ro tối đa cho MỘT lần vào lệnh, tính trên tài sản ròng. 1% là mức thận
# trọng phổ biến; với danh mục chưa từng có kỷ luật cắt lỗ thì thận trọng là
# lựa chọn đúng.
MAX_RISK_PER_TRADE_PCT = 1.0
# Tỷ lệ lợi nhuận/rủi ro tối thiểu để một lần vào lệnh đáng làm.
MIN_REWARD_RISK = 2.0


@dataclass
class PositionPlan:
    ticker: str
    price: float
    # Trần theo hạn mức danh mục
    max_by_single_limit_trieu: float
    max_by_total_limit_trieu: float
    # Vùng vào lệnh và mức thoát, đo từ hỗ trợ/kháng cự thật
    support: Optional[float]
    resistance: Optional[float]
    target: Optional[float]
    stop: Optional[float]
    # Rào lợi suất
    hurdle_pct: Optional[float]
    upside_to_target_pct: Optional[float]
    # Kết luận
    suggested_trieu: Optional[float]
    blockers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def risk_pct(self) -> Optional[float]:
        """% mất nếu giá về mức cắt lỗ."""
        if self.stop is None or not self.price:
            return None
        return (self.price - self.stop) / self.price * 100

    @property
    def reward_risk(self) -> Optional[float]:
        r, up = self.risk_pct, self.upside_to_target_pct
        if r is None or up is None or r <= 0:
            return None
        return up / r

    @property
    def actionable(self) -> bool:
        return not self.blockers and bool(self.suggested_trieu)

    def summary(self) -> str:
        if self.blockers:
            return "CHƯA MUA — " + "; ".join(self.blockers)
        rr = self.reward_risk
        bits = [f"Mua tối đa {self.suggested_trieu:,.0f} tr"]
        if self.stop is not None:
            bits.append(f"cắt lỗ dưới {self.stop:,.2f} (rủi ro {self.risk_pct:.1f}%)")
        if self.target is not None:
            bits.append(f"mục tiêu {self.target:,.2f} (+{self.upside_to_target_pct:.1f}%)")
        if rr is not None:
            bits.append(f"lợi nhuận/rủi ro {rr:.1f}:1")
        return " · ".join(bits)


def plan_position(
    ticker: str,
    price: float,
    net_worth_trieu: float,
    *,
    limits: dict,
    current_stock_value_trieu: float = 0.0,
    support: Optional[float] = None,
    resistance: Optional[float] = None,
    target: Optional[float] = None,
    hurdle_pct: Optional[float] = None,
    available_cash_trieu: Optional[float] = None,
    min_cash_buffer_trieu: Optional[float] = None,
) -> PositionPlan:
    """Kế hoạch vào lệnh cho 1 mã, hoặc lý do KHÔNG nên vào.

    Trả `blockers` rỗng chỉ khi mọi ràng buộc đều qua — thiếu dữ liệu cũng là
    một blocker, không phải lý do để bỏ qua ràng buộc đó.
    """
    single_max = float(limits.get("single_stock_max") or 0.10)
    total_max = float(limits.get("total_stock_max") or 0.20)
    max_single = net_worth_trieu * single_max
    room_total = max(0.0, net_worth_trieu * total_max - current_stock_value_trieu)

    blockers: list[str] = []
    notes: list[str] = []

    # --- Mức cắt lỗ: dưới hỗ trợ THẬT ---------------------------------------
    stop = None
    if support is not None and support < price:
        # Đặt ngay dưới hỗ trợ: hỗ trợ bị thủng thì luận điểm kỹ thuật sai,
        # không phải "chờ thêm chút nữa".
        stop = support * 0.98
    else:
        blockers.append("chưa xác định được hỗ trợ dưới giá hiện tại — không có mức cắt lỗ")

    upside = None
    if target is not None and price:
        upside = (target - price) / price * 100
        if upside <= 0:
            blockers.append(f"giá {price:,.2f} đã VƯỢT mục tiêu {target:,.2f} — không còn biên an toàn")
    else:
        blockers.append("chưa có giá mục tiêu — không đo được phần được")

    # --- Rào lợi suất: phải thắng tiền gửi không rủi ro ----------------------
    if hurdle_pct is not None and upside is not None and upside <= hurdle_pct:
        blockers.append(
            f"tiềm năng {upside:.1f}% không vượt được tiền gửi {hurdle_pct:.2f}%/năm KHÔNG rủi ro"
        )

    # --- Rủi ro/lợi nhuận ----------------------------------------------------
    risk_pct = (price - stop) / price * 100 if stop is not None else None
    if risk_pct is not None and upside is not None and risk_pct > 0:
        rr = upside / risk_pct
        if rr < MIN_REWARD_RISK:
            blockers.append(
                f"lợi nhuận/rủi ro {rr:.1f}:1 dưới mức tối thiểu {MIN_REWARD_RISK:.0f}:1 — "
                "doanh nghiệp có thể tốt nhưng ĐIỂM VÀO xấu"
            )
    if resistance is not None and price >= resistance * 0.99:
        notes.append(f"giá đang sát kháng cự {resistance:,.2f} — cân nhắc chờ vượt hoặc chờ lùi")

    # --- Cỡ lệnh theo rủi ro tối đa mỗi lần vào ------------------------------
    by_risk = None
    if risk_pct is not None and risk_pct > 0:
        by_risk = net_worth_trieu * MAX_RISK_PER_TRADE_PCT / 100 / (risk_pct / 100)

    caps = [c for c in (max_single, room_total, by_risk) if c is not None]
    suggested = min(caps) if caps else None
    if room_total <= 0:
        blockers.append("đã chạm trần tổng tỷ trọng cổ phiếu trong config/risk_limits.yaml")

    # --- Nguồn tiền: phải CÓ THẬT -------------------------------------------
    if available_cash_trieu is not None:
        usable = available_cash_trieu - (min_cash_buffer_trieu or 0.0)
        if usable <= 0:
            notes.append(
                f"tiền mặt {available_cash_trieu:,.0f} tr không được dùng — quỹ khẩn cấp tối thiểu "
                f"{min_cash_buffer_trieu or 0:,.0f} tr phải giữ nguyên. Tiền mua phải đến từ "
                "GIẢM TỶ TRỌNG VÀNG, không phải từ rút quỹ khẩn cấp."
            )
        elif suggested is not None and usable < suggested:
            notes.append(f"tiền khả dụng ngay chỉ {usable:,.0f} tr (sau khi chừa quỹ khẩn cấp) — "
                         "phần còn lại phải đến từ GIẢM TỶ TRỌNG VÀNG, không phải từ rút "
                         "quỹ khẩn cấp")

    return PositionPlan(
        ticker=ticker.upper(), price=price,
        max_by_single_limit_trieu=max_single, max_by_total_limit_trieu=room_total,
        support=support, resistance=resistance, target=target, stop=stop,
        hurdle_pct=hurdle_pct, upside_to_target_pct=upside,
        suggested_trieu=suggested if not blockers else None,
        blockers=blockers, notes=notes,
    )

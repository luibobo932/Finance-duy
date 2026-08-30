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
   Đây là chỗ hầu hết khuyến nghị mua im lặng bỏ qua. Và phép so phải **trừ
   thuế phí trước** (`equity/costs.py`): gửi tiết kiệm không mất phí giao dịch,
   còn một vòng mua–bán cổ phiếu tốn ~0,4–0,8% cộng thuế bán 0,1% phải nộp
   KỂ CẢ KHI LỖ. So tiềm năng GỘP với lãi tiền gửi là so lệch thước.
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

from equity.costs import (DEFAULT_BROKERAGE_FEE_PCT, SELL_TAX_PCT, load_fee_pct,
                          net_upside_pct, round_trip)

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
    # Thuế phí — phí giao dịch mỗi chiều đang áp dụng
    fee_pct: float = DEFAULT_BROKERAGE_FEE_PCT
    # Cổ tức tiền mặt SAU thuế 5%, tính trên giá mua. None = chưa có dữ liệu,
    # khác hẳn 0,0 = đã tra và doanh nghiệp không trả cổ tức tiền mặt.
    dividend_yield_pct: Optional[float] = None
    blockers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def risk_pct(self) -> Optional[float]:
        """% mất do GIÁ nếu về mức cắt lỗ — chưa gồm thuế phí."""
        if self.stop is None or not self.price:
            return None
        return (self.price - self.stop) / self.price * 100

    @property
    def net_upside_pct(self) -> Optional[float]:
        """Phần được CÒN LẠI sau thuế và phí — con số dùng để so tiền gửi."""
        if self.upside_to_target_pct is None:
            return None
        return net_upside_pct(self.upside_to_target_pct, self.fee_pct)

    @property
    def net_risk_pct(self) -> Optional[float]:
        """Phần mất THẬT khi bị cắt lỗ: giá giảm CỘNG phí mua, phí bán và thuế
        bán 0,1% — khoản thuế vẫn phải nộp dù lệnh đang lỗ."""
        r = self.risk_pct
        if r is None:
            return None
        exit_ratio = (100.0 - r) / 100.0
        return r + self.fee_pct + exit_ratio * (self.fee_pct + SELL_TAX_PCT)

    @property
    def cost_round_trip_pct(self) -> Optional[float]:
        """Chi phí trọn vòng mua–bán nếu lệnh chạy đúng tới mục tiêu."""
        if self.upside_to_target_pct is None:
            return None
        exit_ = 100.0 * (1 + self.upside_to_target_pct / 100)
        return round_trip(100.0, fee_pct=self.fee_pct,
                          exit_amount_trieu=exit_).total_pct

    @property
    def reward_risk(self) -> Optional[float]:
        """Đo trên số RÒNG cả hai vế — gộp vế được mà ròng vế mất là ăn gian
        theo hướng dễ dãi với chính mình."""
        r, up = self.net_risk_pct, self.net_upside_pct
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
            bits.append(f"cắt lỗ dưới {self.stop:,.2f} (mất {self.net_risk_pct:.1f}% "
                        "đã gồm thuế phí)")
        if self.target is not None:
            bits.append(f"mục tiêu {self.target:,.2f} (+{self.upside_to_target_pct:.1f}% "
                        f"gộp, +{self.net_upside_pct:.1f}% sau thuế phí)")
        if self.dividend_yield_pct:
            bits.append(f"cổ tức {self.dividend_yield_pct:.2f}%/năm sau thuế")
        if rr is not None:
            bits.append(f"lợi nhuận/rủi ro {rr:.1f}:1")
        return " · ".join(bits)


def plan_position(
    ticker: str,
    price: float,
    net_worth_trieu: float,
    *,
    limits: dict,
    current_stock_value_trieu: float = 0.0,   # TỔNG cổ phiếu đang nắm
    current_position_value_trieu: float = 0.0,  # riêng MÃ NÀY đang nắm
    support: Optional[float] = None,
    resistance: Optional[float] = None,
    target: Optional[float] = None,
    hurdle_pct: Optional[float] = None,
    available_cash_trieu: Optional[float] = None,
    min_cash_buffer_trieu: Optional[float] = None,
    fee_pct: Optional[float] = None,
    dividend_yield_pct: Optional[float] = None,   # SAU thuế 5%, trên giá mua
    price_stale_note: Optional[str] = None,
) -> PositionPlan:
    """Kế hoạch vào lệnh cho 1 mã, hoặc lý do KHÔNG nên vào.

    Trả `blockers` rỗng chỉ khi mọi ràng buộc đều qua — thiếu dữ liệu cũng là
    một blocker, không phải lý do để bỏ qua ràng buộc đó.

    `price_stale_note` là ràng buộc thứ NĂM, bổ sung sau khi đo được ngày 29/08:
    cả bốn ràng buộc trên đều nói về TƯƠNG QUAN giữa các con số (giá vs hỗ trợ,
    lợi nhuận vs rào tiền gửi, cỡ lệnh vs hạn mức) và tất cả vẫn tính ra kết quả
    đẹp khi mọi con số cùng cũ 19 ngày. Mức cắt lỗ là chỗ hỏng nặng nhất: 53.61
    được suy ra từ vùng hỗ trợ của gần ba tuần trước, chính xác tới hai chữ số
    thập phân về một thị trường mà hệ thống không còn nhìn thấy. Một kế hoạch
    vào lệnh dựng trên giá cũ không phải kế hoạch kém — nó không thực hiện được.
    """
    fee = load_fee_pct() if fee_pct is None else float(fee_pct)
    single_max = float(limits.get("single_stock_max") or 0.10)
    total_max = float(limits.get("total_stock_max") or 0.20)
    # Cả hai trần đều phải TRỪ phần đang nắm, nếu không "mua thêm" sẽ vượt
    # trần mà không báo gì. Lỗi thật đã đo: đang nắm 83 tr CTD, hệ thống vẫn
    # bảo "mua tối đa 89 tr" — cộng lại là 13,7% tài sản ròng, vượt trần 10%
    # cho một mã.
    max_single = max(0.0, net_worth_trieu * single_max - current_position_value_trieu)
    room_total = max(0.0, net_worth_trieu * total_max - current_stock_value_trieu)

    blockers: list[str] = []
    notes: list[str] = []

    # Đặt TRƯỚC mọi ràng buộc khác để nó là dòng đầu tiên người đọc thấy: các
    # blocker sau đều bàn về chất lượng của lệnh, cái này bàn về việc có được
    # phép bàn hay không.
    if price_stale_note:
        blockers.append(price_stale_note)

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
    # So SAU thuế phí, vì tiền gửi không mất phí giao dịch nào. Trước đây phép
    # so này dùng tiềm năng GỘP, tức là cộng cho cổ phiếu một khoản mà tiền gửi
    # không được cộng.
    net_up = net_upside_pct(upside, fee) if upside is not None else None
    # Cổ tức TIỀN MẶT sau thuế là phần lợi nhuận thật, phải cộng vào trước khi
    # so với tiền gửi — bỏ nó đi là chấm điểm cổ phiếu thấp hơn thực tế. Cổ tức
    # bằng CỔ PHIẾU đã được `equity/dividends.py` tính bằng 0 và không vào đây.
    total_ret = net_up
    if net_up is not None and dividend_yield_pct:
        total_ret = net_up + dividend_yield_pct
    if hurdle_pct is not None and total_ret is not None and total_ret <= hurdle_pct:
        extra = (f" cộng cổ tức {dividend_yield_pct:.2f}% sau thuế"
                 if dividend_yield_pct else "")
        blockers.append(
            f"tổng lợi nhuận {total_ret:.1f}% (tăng giá {upside:.1f}% gộp → {net_up:.1f}% "
            f"sau thuế phí{extra}) không vượt được tiền gửi {hurdle_pct:.2f}%/năm KHÔNG rủi ro"
        )
    if dividend_yield_pct:
        notes.append(f"Đã cộng cổ tức tiền mặt {dividend_yield_pct:.2f}%/năm sau thuế 5% "
                     "vào tổng lợi nhuận — cổ tức bằng cổ phiếu KHÔNG được cộng vì nó "
                     "không làm tài sản tăng")
    if hurdle_pct is not None and upside is not None:
        notes.append(
            "Rào lợi suất so tổng mức tăng tới giá mục tiêu với lãi tiền gửi MỘT NĂM — "
            "chỉ đúng nếu giá mục tiêu được kỳ vọng đạt trong khoảng 12 tháng; xa hơn "
            "thì rào này đang dễ dãi với cổ phiếu"
        )

    # --- Rủi ro/lợi nhuận ----------------------------------------------------
    risk_pct = (price - stop) / price * 100 if stop is not None else None
    net_risk = None
    if risk_pct is not None:
        net_risk = risk_pct + fee + (100.0 - risk_pct) / 100.0 * (fee + SELL_TAX_PCT)
    if net_risk is not None and net_up is not None and net_risk > 0:
        rr = net_up / net_risk
        if rr < MIN_REWARD_RISK:
            blockers.append(
                f"lợi nhuận/rủi ro {rr:.1f}:1 dưới mức tối thiểu {MIN_REWARD_RISK:.0f}:1 — "
                "doanh nghiệp có thể tốt nhưng ĐIỂM VÀO xấu"
            )
    if resistance is not None and price >= resistance * 0.99:
        notes.append(f"giá đang sát kháng cự {resistance:,.2f} — cân nhắc chờ vượt hoặc chờ lùi")

    # --- Cỡ lệnh theo rủi ro tối đa mỗi lần vào ------------------------------
    # Dùng mức mất RÒNG: một lệnh bị cắt lỗ còn kéo theo phí hai chiều và thuế
    # bán, nên tính cỡ lệnh trên phần mất do giá là ước lượng thiếu.
    by_risk = None
    if net_risk is not None and net_risk > 0:
        by_risk = net_worth_trieu * MAX_RISK_PER_TRADE_PCT / 100 / (net_risk / 100)

    caps = [c for c in (max_single, room_total, by_risk) if c is not None]
    suggested = min(caps) if caps else None
    if room_total <= 0:
        blockers.append("đã chạm trần tổng tỷ trọng cổ phiếu trong config/risk_limits.yaml")
    if max_single <= 0:
        blockers.append(f"đã chạm trần {single_max*100:.0f}% cho riêng mã này — "
                        "mua thêm sẽ vượt hạn mức tập trung 1 mã")

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

    # Chỉ nêu chi phí cho lệnh THẬT SỰ được đề xuất — in con số phí cho một
    # lệnh đang bị chặn là mời gọi đọc nhầm rằng lệnh đó đang được khuyên mua.
    if suggested and upside is not None and not blockers:
        notes.append(round_trip(suggested, fee_pct=fee,
                                exit_amount_trieu=suggested * (1 + upside / 100)).note())

    return PositionPlan(
        fee_pct=fee, dividend_yield_pct=dividend_yield_pct,
        ticker=ticker.upper(), price=price,
        max_by_single_limit_trieu=max_single, max_by_total_limit_trieu=room_total,
        support=support, resistance=resistance, target=target, stop=stop,
        hurdle_pct=hurdle_pct, upside_to_target_pct=upside,
        suggested_trieu=suggested if not blockers else None,
        blockers=blockers, notes=notes,
    )

"""Biến khuyến nghị "CHỐT BỚT" thành kế hoạch có số cụ thể.

Vì sao cần: 14 kỳ liên tiếp hệ thống nói CHỐT BỚT mà tỷ trọng vàng vẫn leo từ
74,6% lên 76,0%. Một phần lý do rất người: lời khuyên không kèm con số thì
không hành động được. "Chốt bớt" trả lời câu "làm gì" nhưng bỏ trống ba câu
quan trọng hơn: **bán bao nhiêu**, **tỷ trọng về đâu**, **tiền đi đâu và được
thêm bao nhiêu lãi**. Module này trả lời cả ba.

Ba chi tiết thực tế được tính đúng, không làm tròn cho tiện:

1. **Đơn vị bán được**: vàng nhẫn bán theo CHỈ (1 chỉ = 1/10 lượng), không bán
   được 0,516 lượng. Số lượng bán luôn quy về số chỉ nguyên và làm tròn LÊN —
   làm tròn xuống thì không chạm được mục tiêu.
2. **Giá bán là giá tiệm MUA VÀO** (`shop_buy_trieu`), không phải giá niêm yết
   bán ra. Đây là tiền thật nhận được khi mang vàng đi bán.
3. **Chi phí chênh lệch mua–bán**: nếu sau này mua lại, khoản lỗ do spread là
   thật và được nêu rõ, để quyết định giảm tỷ trọng là quyết định có biết giá.

KHÔNG mô hình thuế giao dịch vàng: cá nhân bán vàng vật chất ở Việt Nam không
có thuế giao dịch riêng — chi phí thực tế là spread. Không bịa thêm khoản phí.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

CHI_PER_TAEL = 10  # 1 lượng = 10 chỉ


@dataclass
class RebalanceStep:
    """Một phương án giảm tỷ trọng tới `target_pct`."""
    target_pct: float
    tael_to_sell: float
    chi_to_sell: int
    proceeds_trieu: float
    gold_after_trieu: float
    total_after_trieu: float
    gold_pct_after: float
    liquid_after_trieu: float
    spread_cost_trieu: float
    extra_interest_per_year_trieu: Optional[float]
    deposit_note: str
    reaches_target: bool


@dataclass
class RebalancePlan:
    gold_price_sell_trieu: float
    gold_price_buy_trieu: Optional[float]
    gold_tael: float
    gold_now_trieu: float
    savings_trieu: float
    cash_trieu: float
    total_now_trieu: float
    gold_pct_now: float
    warning_pct: float
    critical_pct: float
    best_rate_pct: Optional[float]
    best_rate_bank: Optional[str]
    best_rate_term: Optional[int]
    rate_as_of: Optional[str]
    steps: list[RebalanceStep] = field(default_factory=list)

    @property
    def needs_action(self) -> bool:
        return self.gold_pct_now * 100 >= self.critical_pct


def tael_needed_for_target(
    gold_trieu: float, total_trieu: float, target_pct: float
) -> float:
    """Giá trị vàng (triệu đồng) cần bán để tỷ trọng vàng về `target_pct`.

    Bán vàng chuyển giá trị từ ô "vàng" sang ô "tiền gửi" nên TỔNG không đổi:
        (G − X) / Total = T   →   X = G − T × Total
    Trả 0 nếu đã ở dưới mục tiêu (không có gì phải làm).
    """
    if total_trieu <= 0:
        return 0.0
    x = gold_trieu - (target_pct / 100) * total_trieu
    return max(0.0, x)


def _round_up_to_chi(tael: float) -> tuple[int, float]:
    """(số chỉ, số lượng) sau khi làm tròn LÊN tới chỉ nguyên gần nhất."""
    chi = math.ceil(round(tael * CHI_PER_TAEL, 6))
    return chi, chi / CHI_PER_TAEL


def build_step(
    target_pct: float,
    *,
    gold_tael: float,
    sell_price_trieu: float,
    buy_price_trieu: Optional[float],
    savings_trieu: float,
    cash_trieu: float,
    best_rate_pct: Optional[float],
    deposit_note: str = "",
) -> RebalanceStep:
    """Dựng 1 phương án cho mục tiêu `target_pct`, đã quy về số chỉ bán được."""
    gold_now = gold_tael * sell_price_trieu
    total = gold_now + savings_trieu + cash_trieu
    value_needed = tael_needed_for_target(gold_now, total, target_pct)
    tael_raw = value_needed / sell_price_trieu if sell_price_trieu > 0 else 0.0
    # Không bán quá số vàng đang có
    tael_raw = min(tael_raw, gold_tael)
    chi, tael = _round_up_to_chi(tael_raw)
    tael = min(tael, gold_tael)
    chi = min(chi, int(round(gold_tael * CHI_PER_TAEL)))

    proceeds = tael * sell_price_trieu
    gold_after = gold_now - proceeds
    total_after = total  # tổng không đổi: giá trị chuyển ô, chưa tính spread
    pct_after = (gold_after / total_after * 100) if total_after else 0.0
    liquid_after = savings_trieu + cash_trieu + proceeds

    # Spread chỉ phát sinh nếu SAU NÀY mua lại — nêu ra để biết giá của việc
    # đổi ý, không trừ vào tổng vì hiện tại chưa mua lại.
    spread = ((buy_price_trieu - sell_price_trieu) * tael
              if buy_price_trieu and buy_price_trieu > sell_price_trieu else 0.0)

    extra_interest = (proceeds * best_rate_pct / 100) if best_rate_pct else None

    return RebalanceStep(
        target_pct=target_pct,
        tael_to_sell=tael,
        chi_to_sell=chi,
        proceeds_trieu=proceeds,
        gold_after_trieu=gold_after,
        total_after_trieu=total_after,
        gold_pct_after=pct_after,
        liquid_after_trieu=liquid_after,
        spread_cost_trieu=spread,
        extra_interest_per_year_trieu=extra_interest,
        deposit_note=deposit_note,
        reaches_target=pct_after <= target_pct + 1e-9,
    )


def plan(
    *,
    gold_tael: float,
    sell_price_trieu: float,
    buy_price_trieu: Optional[float],
    savings_trieu: float,
    cash_trieu: float,
    limits: dict,
    ranked_rates: Optional[list[dict]] = None,
    rate_as_of: Optional[str] = None,
    targets_pct: Optional[list[float]] = None,
) -> RebalancePlan:
    """Kế hoạch giảm tỷ trọng vàng, kèm vài mốc mục tiêu để so sánh.

    Mặc định đưa 3 mốc thay vì áp 1 con số, vì lựa chọn "về mức nào" là quyết
    định khẩu vị của chủ danh mục chứ không phải kết luận kỹ thuật:
      - vừa dưới critical: ít phải bán nhất, nhưng sát mép — vàng tăng vài phần
        trăm là vượt ngưỡng lại
      - giữa warning và critical: có đệm chịu được biến động giá
      - về warning: hết cảnh báo tập trung theo cấu hình hiện tại
    """
    gold_now = gold_tael * sell_price_trieu
    total = gold_now + savings_trieu + cash_trieu
    warning = float(limits.get("gold_warning", 0.60)) * 100
    critical = float(limits.get("gold_critical", 0.70)) * 100

    best_rate = best_bank = best_term = None
    if ranked_rates:
        top = max(ranked_rates, key=lambda r: r.get("rate_pct") or 0)
        best_rate, best_bank = top.get("rate_pct"), top.get("bank")
        best_term = top.get("term_months")
    note = (f"{best_bank} {best_rate}%/năm kỳ hạn {best_term} tháng"
            if best_rate else "chưa có lãi suất hợp lệ trong dữ liệu")

    if targets_pct is None:
        mid = round((warning + critical) / 2, 1)
        targets_pct = [critical - 1.0, mid, warning]

    p = RebalancePlan(
        gold_price_sell_trieu=sell_price_trieu,
        gold_price_buy_trieu=buy_price_trieu,
        gold_tael=gold_tael,
        gold_now_trieu=gold_now,
        savings_trieu=savings_trieu,
        cash_trieu=cash_trieu,
        total_now_trieu=total,
        gold_pct_now=(gold_now / total) if total else 0.0,
        warning_pct=warning,
        critical_pct=critical,
        best_rate_pct=best_rate,
        best_rate_bank=best_bank,
        best_rate_term=best_term,
        rate_as_of=rate_as_of,
    )
    for t in targets_pct:
        p.steps.append(build_step(
            t, gold_tael=gold_tael, sell_price_trieu=sell_price_trieu,
            buy_price_trieu=buy_price_trieu, savings_trieu=savings_trieu,
            cash_trieu=cash_trieu, best_rate_pct=best_rate, deposit_note=note,
        ))
    return p

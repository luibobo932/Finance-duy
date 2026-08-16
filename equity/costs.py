"""Thuế và phí giao dịch cổ phiếu — và một so sánh KHÔNG CÔNG BẰNG đã dựng.

Lượt trước hệ thống thêm "rào lợi suất": một mã chỉ đáng mua nếu vượt được
tiền gửi 8,0%/năm không rủi ro. Đúng về nguyên tắc, nhưng phép so đó **thiên
vị cổ phiếu**: gửi tiết kiệm không mất phí giao dịch nào, còn mua–bán cổ phiếu
thì mất, ở cả hai chiều, và **thuế bán 0,1% phải nộp kể cả khi lỗ**.

Quy định hiện hành cho nhà đầu tư cá nhân tại Việt Nam:

    Thuế TNCN khi BÁN     0,1% trên GIÁ TRỊ BÁN — không phụ thuộc lãi hay lỗ
    Phí giao dịch         ~0,15–0,35% mỗi chiều, tuỳ công ty chứng khoán
    Thuế cổ tức tiền mặt  5%

Một vòng mua–bán vì thế tốn khoảng **0,4–0,8%** trước khi giá nhúc nhích. Con
số nhỏ, nhưng nó ăn thẳng vào biên an toàn và làm rào lợi suất chặt hơn tưởng.

KHÔNG mô hình thuế cho vàng: cá nhân bán vàng vật chất ở VN không có thuế
giao dịch riêng — chi phí thật là chênh lệch mua–bán, và `decision/rebalance.py`
đã tính đúng khoản đó. Bịa thêm một khoản thuế vàng là bịa số liệu.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Thuế TNCN khi bán chứng khoán — quy định hiện hành, KHÔNG phụ thuộc lãi/lỗ.
SELL_TAX_PCT = 0.1
# Thuế TNCN trên cổ tức TIỀN MẶT.
CASH_DIVIDEND_TAX_PCT = 5.0
# Phí giao dịch mặc định mỗi chiều. Khoảng thị trường 0,15–0,35%; lấy 0,2% là
# mức phổ biến. Chủ danh mục nên sửa theo biểu phí công ty chứng khoán đang
# dùng — xem `config/decision_rules.yaml: transaction_costs.brokerage_fee_pct`.
DEFAULT_BROKERAGE_FEE_PCT = 0.2

SOURCE_NOTE = ("Thuế bán 0,1% và thuế cổ tức tiền mặt 5% theo quy định hiện hành "
               "cho nhà đầu tư cá nhân; phí giao dịch tuỳ công ty chứng khoán")


@dataclass
class RoundTrip:
    """Chi phí trọn một vòng mua rồi bán."""

    amount_trieu: float
    buy_fee_trieu: float
    sell_fee_trieu: float
    sell_tax_trieu: float

    @property
    def total_trieu(self) -> float:
        return self.buy_fee_trieu + self.sell_fee_trieu + self.sell_tax_trieu

    @property
    def total_pct(self) -> float:
        return self.total_trieu / self.amount_trieu * 100 if self.amount_trieu else 0.0

    def note(self) -> str:
        return (f"Vòng mua–bán tốn {self.total_pct:.2f}% "
                f"({self.total_trieu:,.2f} tr trên {self.amount_trieu:,.0f} tr): "
                f"phí mua {self.buy_fee_trieu:,.2f} + phí bán {self.sell_fee_trieu:,.2f} + "
                f"thuế bán 0,1% {self.sell_tax_trieu:,.2f}. Thuế bán phải nộp KỂ CẢ KHI LỖ.")


def buy_cost_trieu(amount_trieu: float, fee_pct: float = DEFAULT_BROKERAGE_FEE_PCT) -> float:
    """Chi phí khi MUA — chỉ có phí, không có thuế."""
    return amount_trieu * fee_pct / 100


def sell_cost_trieu(amount_trieu: float, fee_pct: float = DEFAULT_BROKERAGE_FEE_PCT) -> float:
    """Chi phí khi BÁN — phí CỘNG thuế 0,1% trên giá trị bán."""
    return amount_trieu * (fee_pct + SELL_TAX_PCT) / 100


def round_trip(amount_trieu: float, *, fee_pct: float = DEFAULT_BROKERAGE_FEE_PCT,
               exit_amount_trieu: Optional[float] = None) -> RoundTrip:
    """Chi phí trọn vòng. `exit_amount_trieu` mặc định bằng vốn vào — dùng giá
    thoát thật khi biết, vì thuế bán tính trên GIÁ TRỊ BÁN chứ không trên vốn."""
    exit_amount = amount_trieu if exit_amount_trieu is None else exit_amount_trieu
    return RoundTrip(
        amount_trieu=amount_trieu,
        buy_fee_trieu=amount_trieu * fee_pct / 100,
        sell_fee_trieu=exit_amount * fee_pct / 100,
        sell_tax_trieu=exit_amount * SELL_TAX_PCT / 100,
    )


def net_upside_pct(gross_upside_pct: float,
                   fee_pct: float = DEFAULT_BROKERAGE_FEE_PCT) -> float:
    """Tiềm năng CÒN LẠI sau thuế và phí — con số dùng để so với tiền gửi.

    So tiềm năng GỘP của cổ phiếu với lãi tiền gửi là so lệch: tiền gửi không
    mất phí giao dịch nào. Phải trừ chi phí trước khi so thì phép so mới cùng
    một thước.
    """
    entry, exit_ = 100.0, 100.0 * (1 + gross_upside_pct / 100)
    rt = round_trip(entry, fee_pct=fee_pct, exit_amount_trieu=exit_)
    return (exit_ - entry - rt.total_trieu) / entry * 100


def cash_dividend_net_trieu(gross_trieu: float) -> float:
    """Cổ tức tiền mặt THỰC NHẬN sau thuế 5%."""
    return gross_trieu * (1 - CASH_DIVIDEND_TAX_PCT / 100)


def load_fee_pct(rules: Optional[dict] = None) -> float:
    """Phí giao dịch từ config; thiếu thì dùng mặc định thị trường."""
    if rules is None:
        try:
            from portfolio.loader import load_decision_rules

            rules = load_decision_rules()
        except Exception:  # noqa: BLE001
            rules = {}
    costs = (rules or {}).get("transaction_costs") or {}
    value = costs.get("brokerage_fee_pct")
    return float(value) if value is not None else DEFAULT_BROKERAGE_FEE_PCT

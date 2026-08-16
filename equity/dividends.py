"""Cổ tức — phần lợi nhuận hệ thống chưa từng biết tới, và hai cái bẫy trong nó.

Trước module này, mọi so sánh "cổ phiếu so với tiền gửi" đều tính THIẾU cho cổ
phiếu: chỉ đo phần giá tăng, bỏ hẳn cổ tức. Với VCB, riêng cổ tức tiền mặt đã
là một khoản thật, và bỏ nó đi là chấm điểm cổ phiếu thấp hơn thực tế.

Nhưng cộng cổ tức vào phải cộng cho đúng, vì hai chỗ rất dễ sai:

**Bẫy 1 — "tỷ lệ %" của cổ tức tính trên MỆNH GIÁ 10.000đ, không phải trên
giá thị trường.** VCB trả "cổ tức tiền mặt 4,5%" nghe như 4,5%/năm, ngang tiền
gửi. Thực tế là 450đ/cp; với giá 60.300đ thì tỷ suất thật chỉ **0,75%**. Sai số
gấp 6 lần, và luôn theo hướng làm cổ phiếu trông hấp dẫn hơn. Module này luôn
quy về tỷ suất trên GIÁ ĐANG MUA.

**Bẫy 2 — cổ tức bằng CỔ PHIẾU không phải là lợi nhuận.** "Cổ tức 49,5% bằng
cổ phiếu" không làm tài sản tăng 49,5%: doanh nghiệp không đưa thêm đồng nào
ra ngoài, giá tham chiếu bị điều chỉnh giảm tương ứng trong ngày giao dịch
không hưởng quyền. Cầm nhiều cổ phiếu hơn với giá mỗi cổ phiếu thấp hơn thì
giá trị nắm giữ không đổi. Nó chỉ là chia nhỏ mệnh giá kèm tăng vốn điều lệ.
Cổ phiếu THƯỞNG (CTD, tỷ lệ 20:1) bản chất pha loãng y hệt. Module này tính
tỷ suất cổ tức bằng cổ phiếu là **0** và nói rõ vì sao, thay vì im lặng bỏ qua.

Thuế: cổ tức TIỀN MẶT chịu thuế TNCN 5% (`equity/costs.py`). Cổ tức bằng cổ
phiếu bị đánh thuế khi BÁN chứ không phải khi nhận — hệ thống chưa mô hình
được phần đó, và ghi rõ là chưa, chứ không coi như bằng 0.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Sequence

from equity.costs import CASH_DIVIDEND_TAX_PCT, cash_dividend_net_trieu

ROOT = Path(__file__).resolve().parent.parent
DIVIDENDS_PATH = ROOT / "data" / "dividends.jsonl"

# Mệnh giá cổ phiếu niêm yết tại Việt Nam. "Cổ tức 4,5%" nghĩa là 4,5% CỦA
# CON SỐ NÀY, không phải của giá thị trường.
PAR_VALUE_DONG = 10_000

CASH = "CASH"
STOCK = "STOCK"

# Cổ tức cũ hơn mức này không còn nói gì về dòng tiền sắp tới. 400 ngày ≈ hơn
# một chu kỳ chi trả năm, đủ rộng để không loại nhầm doanh nghiệp trả chậm.
MAX_DIVIDEND_AGE_DAYS = 400

STOCK_DIVIDEND_NOTE = (
    "Cổ tức bằng cổ phiếu KHÔNG phải lợi nhuận: giá tham chiếu bị điều chỉnh "
    "giảm tương ứng trong ngày giao dịch không hưởng quyền, doanh nghiệp không "
    "chi ra đồng nào. Tính vào tỷ suất là tự cộng điểm cho mình"
)


@dataclass
class Dividend:
    ticker: str
    kind: str                                # CASH | STOCK
    period: str = ""
    amount_dong: Optional[float] = None      # tiền mặt: đồng/cổ phiếu
    rate_on_par_pct: Optional[float] = None  # tiền mặt: % trên MỆNH GIÁ
    ratio_pct: Optional[float] = None        # cổ phiếu: % số lượng phát hành thêm
    record_date: Optional[date] = None
    pay_date: Optional[date] = None
    source: str = ""

    @property
    def is_cash(self) -> bool:
        return self.kind.upper() == CASH

    @property
    def cash_per_share_dong(self) -> Optional[float]:
        """Số tiền thật mỗi cổ phiếu nhận được.

        Ưu tiên số tiền đã công bố; chỉ suy từ tỷ lệ khi thiếu, và suy trên
        MỆNH GIÁ chứ không trên giá thị trường.
        """
        if not self.is_cash:
            return None
        if self.amount_dong is not None:
            return float(self.amount_dong)
        if self.rate_on_par_pct is not None:
            return PAR_VALUE_DONG * self.rate_on_par_pct / 100
        return None

    def gross_yield_pct(self, price_nghin_dong: float) -> Optional[float]:
        """Tỷ suất cổ tức TRÊN GIÁ ĐANG MUA — con số duy nhất so được với lãi
        tiền gửi. Cổ tức bằng cổ phiếu trả 0,0 (xem STOCK_DIVIDEND_NOTE)."""
        if not self.is_cash:
            return 0.0
        cash = self.cash_per_share_dong
        if cash is None or not price_nghin_dong:
            return None
        return cash / (price_nghin_dong * 1_000) * 100

    def net_yield_pct(self, price_nghin_dong: float) -> Optional[float]:
        """Tỷ suất SAU thuế TNCN 5% trên cổ tức tiền mặt."""
        g = self.gross_yield_pct(price_nghin_dong)
        return None if g is None else g * (1 - CASH_DIVIDEND_TAX_PCT / 100)

    def age_days(self, today: Optional[date] = None) -> Optional[int]:
        ref = self.record_date or self.pay_date
        return None if ref is None else ((today or date.today()) - ref).days

    def describe(self, price_nghin_dong: Optional[float] = None) -> str:
        if not self.is_cash:
            r = f"{self.ratio_pct:.0f}%" if self.ratio_pct is not None else "chưa rõ tỷ lệ"
            return f"{self.ticker} cổ tức bằng CỔ PHIẾU {r} ({self.period}) — {STOCK_DIVIDEND_NOTE}."
        cash = self.cash_per_share_dong
        if cash is None:
            return f"{self.ticker} cổ tức tiền mặt {self.period} — chưa có số liệu."
        bits = [f"{self.ticker} cổ tức tiền mặt {cash:,.0f}đ/cp ({self.period})"]
        if self.rate_on_par_pct is not None:
            bits.append(f"công bố là {self.rate_on_par_pct:.1f}% nhưng đó là % trên MỆNH GIÁ "
                        f"{PAR_VALUE_DONG:,.0f}đ, không phải trên giá thị trường")
        if price_nghin_dong:
            g = self.gross_yield_pct(price_nghin_dong)
            n = self.net_yield_pct(price_nghin_dong)
            assert g is not None and n is not None
            bits.append(f"tỷ suất thật trên giá {price_nghin_dong:,.1f}: {g:.2f}% trước thuế, "
                        f"{n:.2f}% sau thuế 5%")
        if self.pay_date is not None:
            bits.append(f"thanh toán {self.pay_date:%d/%m/%Y}")
        return "; ".join(bits) + "."


@dataclass
class DividendView:
    ticker: str
    price: float
    dividends: list[Dividend]
    excluded: list[str]

    @property
    def cash(self) -> list[Dividend]:
        return [d for d in self.dividends if d.is_cash]

    @property
    def stock(self) -> list[Dividend]:
        return [d for d in self.dividends if not d.is_cash]

    @property
    def gross_yield_pct(self) -> Optional[float]:
        """Tổng tỷ suất cổ tức tiền mặt trên giá. None khi CHƯA CÓ dữ liệu —
        khác hẳn 0,0 nghĩa là 'đã tra và doanh nghiệp không trả cổ tức'."""
        vals = [d.gross_yield_pct(self.price) for d in self.cash]
        vals = [v for v in vals if v is not None]
        return sum(vals) if vals else None

    @property
    def net_yield_pct(self) -> Optional[float]:
        g = self.gross_yield_pct
        return None if g is None else g * (1 - CASH_DIVIDEND_TAX_PCT / 100)

    def note(self) -> str:
        if not self.dividends:
            return (f"Chưa có dữ liệu cổ tức cho {self.ticker} — tổng lợi nhuận đang bị "
                    "tính THIẾU, không phải bằng 0.")
        bits = []
        n = self.net_yield_pct
        if n is not None:
            bits.append(f"Cổ tức tiền mặt {n:.2f}%/năm sau thuế trên giá hiện tại "
                        f"(so với tiền gửi thì đây mới là con số cùng thước)")
        for d in self.stock:
            bits.append(d.describe(self.price).rstrip("."))
        if self.excluded:
            bits.append("Đã loại vì quá cũ: " + "; ".join(self.excluded))
        return ". ".join(bits) + "."


def load_dividends(path: Optional[Path] = None) -> list[Dividend]:
    p = path or DIVIDENDS_PATH
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        out.append(Dividend(
            ticker=str(d["ticker"]).upper(),
            kind=str(d.get("kind") or CASH).upper(),
            period=str(d.get("period") or ""),
            amount_dong=_num(d.get("amount_dong")),
            rate_on_par_pct=_num(d.get("rate_on_par_pct")),
            ratio_pct=_num(d.get("ratio_pct")),
            record_date=_parse(d.get("record_date")),
            pay_date=_parse(d.get("pay_date")),
            source=str(d.get("source") or ""),
        ))
    return out


def view_for(ticker: str, price: float, *, today: Optional[date] = None,
             dividends: Optional[Sequence[Dividend]] = None) -> DividendView:
    """Cổ tức của 1 mã, loại bản ghi quá cũ và nói rõ đã loại gì."""
    today = today or date.today()
    all_d = list(dividends) if dividends is not None else load_dividends()
    mine = [d for d in all_d if d.ticker == ticker.upper()]
    keep, excluded = [], []
    for d in mine:
        age = d.age_days(today)
        if age is not None and age > MAX_DIVIDEND_AGE_DAYS:
            excluded.append(f"{d.period} {d.kind} (cũ {age} ngày)")
            continue
        keep.append(d)
    return DividendView(ticker.upper(), price, keep, excluded)


def net_cash_received_trieu(view: DividendView, quantity: float) -> Optional[float]:
    """Tiền cổ tức THỰC NHẬN (triệu đồng) cho một lượng cổ phiếu đang nắm."""
    per_share = [d.cash_per_share_dong for d in view.cash]
    per_share = [v for v in per_share if v is not None]
    if not per_share:
        return None
    gross_trieu = sum(per_share) * quantity / 1_000_000
    return cash_dividend_net_trieu(gross_trieu)


def _num(value: object) -> Optional[float]:
    return None if value is None else float(value)  # type: ignore[arg-type]


def _parse(value: object) -> Optional[date]:
    if isinstance(value, str):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None

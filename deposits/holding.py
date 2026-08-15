"""Khoản tiền gửi ĐANG NẮM GIỮ — 21% tài sản mà hệ thống chưa biết gì về nó.

Vì sao cần: `config/portfolio.yaml` khai báo đúng một dòng cho khoản tiết kiệm

    savings:
      principal_vnd: 246000000

Không lãi suất, không ngân hàng, không kỳ hạn, không ngày gửi. Hệ quả không
phải chuyện nhỏ:

1. **Hệ thống tối ưu tiền SẮP có mà không nhìn tiền ĐANG có.**
   `decision/rebalance.py` tính "bán vàng thu 137tr, gửi 8,0%/năm → lãi thêm
   11,0 tr/năm". Nhưng 246tr đang nằm sẵn thì đang hưởng mức nào? Nếu nó ở
   5,5% trong khi mức tốt nhất đo được là 8,0%, riêng khoản chênh đó đã là
   **6,2 tr/năm** — lớn hơn phần lãi thêm của cả kế hoạch bán vàng về 69%,
   mà không kỳ bản tin nào từng nhắc tới.

2. **Định giá lịch sử coi tiết kiệm là tài sản KHÔNG sinh lãi.**
   `reporting/dashboard_builder.value_at()` lấy nguyên `principal_vnd` cho mọi
   kỳ, nên đường "tổng tài sản theo thời gian" gán toàn bộ biến động cho vàng.
   Sai về cấu trúc chứ không chỉ sai số lẻ.

3. **Không có ngày đáo hạn thì không cảnh báo được tái tục.** Ở Việt Nam sổ
   đến hạn không tất toán thường tự động quay vòng theo lãi suất NIÊM YẾT TẠI
   QUẦY của kỳ hạn đó — thường thấp hơn hẳn mức online đã ký ban đầu. Đây là
   khoản rò rỉ tiền phổ biến và im lặng.

Module này KHÔNG bịa số. Khi config còn để trống, nó trả về trạng thái "chưa
khai báo" kèm **bảng lượng hóa cái giá của việc không khai báo** — để việc xin
số liệu là một đề nghị có căn cứ, không phải một lời nhắc chung chung.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional, Sequence

# Kỳ hạn phổ biến khi chưa biết kỳ hạn thật — CHỈ dùng để lượng hóa khoảng
# thiếu thông tin, không bao giờ dùng như thể đó là kỳ hạn của chủ danh mục.
ASSUMED_RATES_FOR_GAP_PCT: tuple[float, ...] = (4.5, 5.5, 6.5, 7.5)

# Cảnh báo trước ngày đáo hạn bao lâu. 14 ngày đủ để ra ngân hàng hoặc thao
# tác online trước khi sổ tự quay vòng.
MATURITY_WARN_DAYS = 14

DAYS_PER_MONTH = 30  # xấp xỉ dùng cho lập kế hoạch, khớp deposits/strategy.py


@dataclass
class DepositHolding:
    """Khoản gửi thật của chủ danh mục. Mọi trường ngoài `principal_vnd` đều
    có thể None — thiếu thì báo thiếu, không đoán."""

    principal_vnd: float
    bank: Optional[str] = None
    rate_pct: Optional[float] = None
    term_months: Optional[int] = None
    start_date: Optional[date] = None
    channel: Optional[str] = None  # "online" | "counter"
    auto_renew: Optional[bool] = None

    @property
    def is_declared(self) -> bool:
        """Đủ thông tin để tính được gì đó chưa (lãi suất là tối thiểu)."""
        return self.rate_pct is not None

    @property
    def maturity_date(self) -> Optional[date]:
        if self.start_date is None or self.term_months is None:
            return None
        return self.start_date + timedelta(days=DAYS_PER_MONTH * self.term_months)

    def days_to_maturity(self, today: Optional[date] = None) -> Optional[int]:
        m = self.maturity_date
        return None if m is None else (m - (today or date.today())).days

    def accrued_interest_vnd(self, today: Optional[date] = None) -> Optional[float]:
        """Lãi đã tích lũy tới hôm nay (tuyến tính, chưa tính nhập gốc).

        Trả None khi thiếu lãi suất hoặc ngày gửi — số 0 ở đây sẽ bị đọc nhầm
        thành "chưa sinh lãi đồng nào", khác hẳn "chưa biết".
        """
        if self.rate_pct is None or self.start_date is None:
            return None
        days = max(0, ((today or date.today()) - self.start_date).days)
        return self.principal_vnd * self.rate_pct / 100 * days / 365

    def value_at(self, today: Optional[date] = None) -> float:
        """Giá trị khoản gửi hôm nay = gốc + lãi tích lũy (nếu tính được).

        Chưa khai báo thì trả đúng phần gốc — thấp hơn thực tế, và đó là hướng
        sai AN TOÀN: không bao giờ báo tài sản cao hơn số có thật.
        """
        return self.principal_vnd + (self.accrued_interest_vnd(today) or 0.0)


@dataclass
class RateGapRow:
    """Một dòng của bảng "không khai báo thì đang mất gì"."""

    assumed_rate_pct: float
    best_rate_pct: float
    gap_pct: float
    gap_per_year_vnd: float


@dataclass
class MaturityAlert:
    days_left: int
    maturity_date: date
    message: str
    level: str  # "warning" | "critical"


def from_portfolio(port, *, deposit_cfg: Optional[dict] = None) -> DepositHolding:
    """Dựng holding từ PortfolioConfig (+ khối `savings` thô nếu có thêm trường)."""
    cfg = deposit_cfg or {}
    return DepositHolding(
        principal_vnd=port.savings_principal_vnd,
        bank=cfg.get("bank"),
        rate_pct=cfg.get("rate_pct"),
        term_months=cfg.get("term_months"),
        start_date=_parse_date(cfg.get("start_date")),
        channel=cfg.get("channel"),
        auto_renew=cfg.get("auto_renew"),
    )


def rate_gap_table(
    principal_vnd: float, best_rate_pct: Optional[float],
    assumed_rates_pct: Sequence[float] = ASSUMED_RATES_FOR_GAP_PCT,
) -> list[RateGapRow]:
    """Chênh lệch lãi mỗi năm giữa "mức có thể đang hưởng" và mức tốt nhất đo được.

    Đây KHÔNG phải ước tính lãi suất của chủ danh mục — hệ thống không biết mức
    đó. Đây là bảng cho thấy khoảng chưa biết ấy đáng giá bao nhiêu tiền, để
    việc đề nghị khai báo có con số đi kèm.
    """
    if not best_rate_pct or not principal_vnd:
        return []
    rows = []
    for r in assumed_rates_pct:
        if r >= best_rate_pct:
            continue  # đã bằng hoặc tốt hơn mức tốt nhất thì không có khoảng trống
        gap = best_rate_pct - r
        rows.append(RateGapRow(assumed_rate_pct=r, best_rate_pct=best_rate_pct,
                               gap_pct=gap, gap_per_year_vnd=principal_vnd * gap / 100))
    return rows


def maturity_alert(
    holding: DepositHolding, today: Optional[date] = None,
    warn_days: int = MATURITY_WARN_DAYS,
) -> Optional[MaturityAlert]:
    """Cảnh báo trước khi sổ tự quay vòng — khoản rò rỉ tiền im lặng phổ biến.

    Sổ đến hạn không tất toán thường tự động tái tục theo lãi suất NIÊM YẾT
    TẠI QUẦY, thường thấp hơn hẳn mức online đã ký. Không có ngày đáo hạn thì
    không có gì cảnh báo được — đó chính là lý do cần khai báo.
    """
    days = holding.days_to_maturity(today)
    if days is None:
        return None
    m = holding.maturity_date
    assert m is not None
    if days < 0:
        return MaturityAlert(
            days_left=days, maturity_date=m, level="critical",
            message=(f"Sổ đã đáo hạn {abs(days)} ngày trước ({m:%d/%m/%Y}). Nếu để tự quay "
                     "vòng, lãi suất mới thường là mức NIÊM YẾT TẠI QUẦY của kỳ hạn đó — "
                     "kiểm tra lại và tái ký theo kênh online nếu chênh lệch đáng kể."),
        )
    if days > warn_days:
        return None
    return MaturityAlert(
        days_left=days, maturity_date=m, level="warning",
        message=(f"Còn {days} ngày tới hạn ({m:%d/%m/%Y}). Quyết định trước ngày đó: tất "
                 "toán, hay tái ký theo mức tốt nhất hiện có — để tự quay vòng thường "
                 "rơi vào lãi suất tại quầy, thấp hơn mức online."),
    )


def undeclared_note(principal_vnd: float, gap_rows: Sequence[RateGapRow]) -> str:
    """Câu đề nghị khai báo, KÈM con số — không phải lời nhắc chung chung."""
    trieu = principal_vnd / 1_000_000
    if not gap_rows:
        return (f"Chưa khai báo lãi suất/kỳ hạn cho khoản tiết kiệm {_vi(trieu, 0)} tr — "
                "hệ thống không tính được lãi tích lũy hay ngày đáo hạn.")
    worst = max(gap_rows, key=lambda r: r.gap_per_year_vnd)
    best = min(gap_rows, key=lambda r: r.gap_per_year_vnd)
    return (f"Chưa khai báo lãi suất/kỳ hạn cho khoản tiết kiệm {_vi(trieu, 0)} tr — "
            f"đây là {_vi(trieu, 0)} tr mà hệ thống không biết đang sinh lãi bao nhiêu. "
            f"Nếu đang ở {_vi(worst.assumed_rate_pct, 1)}%/năm thì so với mức tốt nhất đo "
            f"được {_vi(worst.best_rate_pct, 2)}%/năm, khoảng chênh là "
            f"{_vi(worst.gap_per_year_vnd / 1_000_000, 1)} tr/năm; nếu đã ở "
            f"{_vi(best.assumed_rate_pct, 1)}%/năm thì chênh {_vi(best.gap_per_year_vnd / 1_000_000, 1)} tr/năm. "
            "Khai báo ngân hàng, lãi suất, kỳ hạn và ngày gửi trong "
            "<code>config/portfolio.yaml</code> để hệ thống theo dõi đáo hạn và tính đúng "
            "tài sản.")


def _parse_date(value: object) -> Optional[date]:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _vi(value: float, decimals: int = 1) -> str:
    return f"{value:,.{decimals}f}".translate(str.maketrans({",": ".", ".": ","}))

"""Nối phần CỔ PHIẾU vào bản tin — trụ cột thứ ba, xây xong nhưng chưa cắm điện.

Bằng chứng, không phải cảm tính:

- `scripts/run_morning.py::section_tong_quan()` in nguyên văn *"Cổ phiếu
  watchlist: xem mục Chứng khoán bên dưới"* — trong khi **không có mục nào như
  vậy**. Bản tin trỏ tới một phần không tồn tại, ở mọi kỳ.
- `equity/technical.py::technical_snapshot()` đã có đủ RSI, MACD, MA, relative
  volume, z-score, hỗ trợ/kháng cự, breakout, trend state. Chạy được ngay trên
  **43 phiên EOD thật** của VCB/CTD trong `data/eod/`. Không caller nào gọi.
- `decision/policy_engine.py` có sẵn nhánh `asset_class == "equity"`, và
  `risk_officer` có rule quản trị doanh nghiệp + rule tập trung cổ phiếu.
  Chưa dòng code nào chạy Decision Engine cho một mã cổ phiếu.

Module này là phần nối, không phải phần tính — mọi công thức vẫn nằm ở
`equity/technical.py` và `analytics/ta_core.py`.

Một điểm ngữ nghĩa phải làm cho đúng: chủ danh mục **đã bán hết cổ phiếu**.
Với mã không nắm giữ, "GIỮ" là câu vô nghĩa — không thể giữ thứ mình không có.
Xem `decision/policy_engine.py::derive_initial_action`, nhánh equity nay phân
biệt có/không có vị thế.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from analytics.ta_core import trend_from_indicators
from equity.technical import technical_snapshot

ROOT = Path(__file__).resolve().parent.parent
EOD_DIR = ROOT / "data" / "eod"

# Khối lượng ≥ mức này lần bình quân là bất thường, đáng soi thỏa thuận/nội bộ.
# Khớp ngưỡng đã dùng ở `scripts/trend.py report` — một hệ thống, một ngưỡng.
VOLUME_SPIKE_RATIO = 1.5


@dataclass
class TickerSignal:
    ticker: str
    sessions: int
    last_date: Optional[str]
    close: Optional[float]
    trend_label: Optional[str]  # None = CHƯA ĐO ĐƯỢC, khác hẳn TRUNG_TINH
    tech: dict

    @property
    def has_data(self) -> bool:
        return self.close is not None

    @property
    def volume_flag(self) -> Optional[str]:
        """Cảnh báo khối lượng bất thường — cửa vào của phần soi giao dịch nội
        bộ trong `docs/phuong-phap-phan-tich.md`."""
        rv = self.tech.get("relative_volume")
        if rv is None:
            return None
        if rv >= VOLUME_SPIKE_RATIO:
            return (f"KLGD {rv:.2f}× bình quân — cần soi giao dịch thỏa thuận và "
                    "công bố giao dịch người nội bộ")
        return None

    def evidence(self) -> str:
        """Nhãn xu hướng đến từ đâu — nhãn không kèm căn cứ thì không phản biện được."""
        if not self.has_data:
            return f"chưa có dữ liệu EOD cho {self.ticker}"
        bits = []
        if self.tech.get("rsi14") is not None:
            bits.append(f"RSI(14)={self.tech['rsi14']:.1f}")
        m = self.tech.get("macd")
        if m and m.get("hist") is not None:
            bits.append(f"MACD hist={m['hist']:+.2f}")
        if self.tech.get("sma20") is not None and self.close is not None:
            vs = "trên" if self.close > self.tech["sma20"] else "dưới"
            bits.append(f"giá {vs} SMA20 ({self.tech['sma20']:.2f})")
        if not bits:
            return f"{self.sessions} phiên — chưa đủ cho RSI(14) (cần 15)"
        return f"đo trên {self.sessions} phiên EOD: " + ", ".join(bits)


def load_eod(ticker: str, path: Optional[Path] = None) -> list[dict]:
    p = path or (EOD_DIR / f"{ticker.upper()}.csv")
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def analyze(ticker: str, rows: Optional[list[dict]] = None) -> TickerSignal:
    """Tín hiệu kỹ thuật cho 1 mã từ `data/eod/<MÃ>.csv`.

    Thiếu file hoặc thiếu dữ liệu → trả về signal rỗng có `has_data=False`,
    KHÔNG dựng số 0 để bản tin có cái mà in.
    """
    rows = load_eod(ticker) if rows is None else rows
    if not rows:
        return TickerSignal(ticker.upper(), 0, None, None, None, {})
    try:
        highs = [float(r["high"]) for r in rows]
        lows = [float(r["low"]) for r in rows]
        closes = [float(r["close"]) for r in rows]
        volumes = [float(r["volume"]) for r in rows]
    except (KeyError, ValueError, TypeError):
        return TickerSignal(ticker.upper(), 0, None, None, None, {})

    tech = technical_snapshot(highs, lows, closes, volumes)
    return TickerSignal(
        ticker=ticker.upper(),
        sessions=len(closes),
        last_date=rows[-1].get("date"),
        close=closes[-1],
        trend_label=trend_from_indicators(tech.get("rsi14"), (tech.get("macd") or {}).get("hist")),
        tech=tech,
    )


def valuation_for(signal: TickerSignal):
    """Biên an toàn từ giá mục tiêu CTCK — None khi chưa có dữ liệu định giá."""
    if not signal.has_data or signal.close is None:
        return None
    from equity.target_prices import view_for

    view = view_for(signal.ticker, signal.close)
    return view if view.targets else None


def dividends_for(signal: TickerSignal):
    """Cổ tức của mã — None khi chưa có dữ liệu, KHÔNG trả về 'không cổ tức'.

    Bỏ cổ tức ra khỏi so sánh là chấm điểm cổ phiếu THẤP hơn thực tế; nhưng
    cộng nhầm cổ tức bằng cổ phiếu vào lại là tự cộng điểm. `equity/dividends.py`
    tách hai loại đó ra.
    """
    if not signal.has_data or signal.close is None:
        return None
    from equity.dividends import view_for

    view = view_for(signal.ticker, signal.close)
    return view if view.dividends else None


def decide_for(signal: TickerSignal, *, has_position: bool = False,
               governance_status: Optional[str] = None) -> Optional[dict]:
    """Chạy Decision Engine THẬT cho một mã — nhánh equity trước nay chưa từng chạy.

    Trả None khi chưa có dữ liệu: không có tín hiệu thì không ra quyết định,
    chứ không ra quyết định "trung tính" cho có.

    `margin_of_safety_pct` nay được TRUYỀN THẬT. Trước đây không caller
    production nào truyền trường này, nên điều kiện duy nhất dẫn tới MUA THĂM
    DÒ không bao giờ thoả — nhánh cổ phiếu về cấu trúc không thể khuyến nghị
    mua, mọi mã vĩnh viễn dừng ở ĐỨNG NGOÀI.
    """
    if not signal.has_data:
        return None
    from decision.policy_engine import DecisionInput, decide
    from decision.risk_officer import RiskContext
    from portfolio.loader import load_decision_rules, load_risk_limits

    view = valuation_for(signal)
    mos = view.margin_of_safety_pct if view else None

    # Định giá đi mượn từ CTCK KHÔNG được coi ngang dữ liệu đo được. Khi các
    # CTCK lệch nhau lớn, chính sự lệch đó là tín hiệu "không ai thực sự biết"
    # — hạ độ đầy đủ dữ liệu để điểm tin cậy phản ánh đúng điều đó.
    completeness = 100.0 if signal.sessions >= 15 else 50.0
    if view is None:
        completeness = min(completeness, 70.0)  # thiếu hẳn tầng định giá
    elif view.high_dispersion:
        completeness = min(completeness, 80.0)

    return decide(
        DecisionInput(
            asset=signal.ticker, asset_class="equity",
            trend_label=signal.trend_label,
            margin_of_safety_pct=mos,
            governance_status=governance_status,
            has_position=has_position,
            # Chất lượng dữ liệu của cổ phiếu đo riêng: chuỗi EOD là nguồn tự
            # động thật, khác hẳn tình trạng dữ liệu vàng.
            data_completeness_pct=completeness,
            data_freshness_score=100.0,
        ),
        RiskContext(governance_status=governance_status),
        load_risk_limits(), load_decision_rules(),
    )

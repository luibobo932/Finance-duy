"""Kịch bản giá vàng đổi — trả lời "không làm gì thì mất bao nhiêu TIỀN?"

Vì sao cần: hệ thống đã nói **CHỐT BỚT 19 kỳ liên tiếp** và chủ danh mục không
làm gì. Nhìn lại nội dung khuyến nghị thì dễ hiểu vì sao — nó nói "vàng 76%,
vượt ngưỡng 70%", tức là một tỷ lệ phần trăm so với một tỷ lệ phần trăm khác.
Không kỳ nào nói **rủi ro đó bằng bao nhiêu tiền**.

`decision/rebalance.py` đã trả lời "bán bao nhiêu". Module này trả lời vế còn
lại: "bán để tránh cái gì" — và trả lời bằng triệu đồng.

Ba nguyên tắc, vì đây là chỗ rất dễ trượt thành hù dọa:

1. **Kịch bản KHÔNG phải dự báo.** Đây là số học "nếu ... thì ...", không có
   xác suất nào gắn kèm. Nói "vàng có thể giảm 20%" khác hoàn toàn với "vàng
   sẽ giảm 20%", và module này chỉ làm vế đầu.
2. **Đối xứng.** Bảng chạy cả chiều tăng lẫn chiều giảm cùng biên độ. Chỉ bày
   kịch bản giảm là dẫn dắt bằng cách chọn dữ liệu — đúng cái lỗi mà
   `analytics/opportunity_cost.py` đã tránh ở phía ngược lại.
3. **Dùng CHÍNH mô hình định giá của production** (`gold.xuan_trieu_model.
   estimate`) cho mọi kịch bản, không dựng mô hình riêng. Hai mô hình định giá
   trong một hệ thống là hai nguồn sự thật.

Thiên lệch đã biết, nói thẳng: mô hình giả định tỷ lệ giá trong nước / thế giới
KHÔNG đổi. `gold/calibration.py` đo được tương quan Pearson(XAU, k) = −0,75 —
giá trong nước TRỄ so với thế giới. Nên khi thế giới giảm, giá trong nước
thường giảm CHẬM hơn, và các con số lỗ dưới đây có xu hướng **nặng hơn thực
tế đôi chút**, tức thiên về thận trọng.
"""
from __future__ import annotations

import json
import math
import statistics as st
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = ROOT / "data" / "history.jsonl"

# Biên độ kịch bản, ĐỐI XỨNG hai chiều. Không kèm xác suất — đây là "nếu...thì",
# không phải dự báo.
DEFAULT_SHOCKS_PCT: tuple[float, ...] = (-20.0, -15.0, -10.0, -5.0, 5.0, 10.0, 15.0, 20.0)

BIAS_NOTE = ("Giả định tỷ lệ giá trong nước/thế giới không đổi. Đo được tương quan "
             "XAU–tỷ lệ = −0,75 (giá trong nước trễ hơn thế giới) nên khi thế giới "
             "giảm, giá trong nước thường giảm chậm hơn — các mức lỗ dưới đây "
             "nghiêng về phía thận trọng")


@dataclass
class ScenarioRow:
    shock_pct: float
    xau_after: float
    gold_price_after_trieu: float  # giá tiệm MUA vào, tr/lượng — tiền thật nhận được
    gold_value_after_trieu: float
    total_after_trieu: float
    change_trieu: float  # âm = mất tiền
    gold_pct_after: float


@dataclass
class VolatilityFacts:
    """Những gì mẫu dữ liệu THẬT nói được — và những gì nó không nói được."""

    n_observations: int
    stdev_per_period_pct: Optional[float]
    max_drawdown_in_sample_pct: Optional[float]
    sample_min: Optional[float]
    sample_max: Optional[float]

    @property
    def caveat(self) -> str:
        """Giới hạn của mẫu, nêu trước khi ai đó dùng nó như một giới hạn rủi ro.

        19 quan sát trong 3 tuần của một thị trường đang tăng KHÔNG cho biết
        vàng có thể giảm sâu tới đâu. Trình bày mức sụt sâu nhất trong mẫu như
        thể đó là kịch bản xấu nhất là hiểu sai dữ liệu một cách nguy hiểm.
        """
        if self.n_observations < 2:
            return "Chưa đủ quan sát để đo biến động."
        base = (f"Đo trên {self.n_observations} kỳ quan sát "
                f"(XAU {_vi(self.sample_min, 0)}–{_vi(self.sample_max, 0)}$)")
        return (f"{base}: lệch chuẩn {_vi(self.stdev_per_period_pct, 2)}%/kỳ, sụt sâu nhất trong "
                f"mẫu {_vi(self.max_drawdown_in_sample_pct, 2)}%. ⚠️ Mẫu này quá ngắn và chỉ đi "
                "một chiều (tăng) nên KHÔNG dùng làm giới hạn rủi ro — nó không nói được "
                "vàng có thể giảm sâu tới đâu.")


@dataclass
class Protection:
    """Bán bớt hôm nay bảo vệ được bao nhiêu ở một mức sụt giảm."""

    chi_sold: int
    proceeds_trieu: float
    shock_pct: float
    protected_trieu: float  # số tiền KHÔNG bị cuốn theo vì đã rời khỏi vàng


def measure_volatility(history: Optional[Sequence[dict]] = None) -> VolatilityFacts:
    closes = _xau_closes(history)
    if len(closes) < 2:
        return VolatilityFacts(len(closes), None, None,
                               min(closes) if closes else None, max(closes) if closes else None)
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    peak, mdd = closes[0], 0.0
    for v in closes:
        peak = max(peak, v)
        mdd = min(mdd, (v - peak) / peak)
    return VolatilityFacts(
        n_observations=len(closes),
        stdev_per_period_pct=st.pstdev(rets) * 100,
        max_drawdown_in_sample_pct=mdd * 100,
        sample_min=min(closes), sample_max=max(closes),
    )


def scenario_table(
    gold_tael: float,
    other_assets_trieu: float,
    *,
    xau_now: Optional[float] = None,
    usd_vnd: Optional[float] = None,
    shocks_pct: Sequence[float] = DEFAULT_SHOCKS_PCT,
) -> list[ScenarioRow]:
    """Giá trị danh mục ở từng mức sốc giá vàng.

    `other_assets_trieu` (tiết kiệm + tiền mặt) KHÔNG đổi theo giá vàng — đó
    chính là lý do tỷ trọng vàng tự giảm trong kịch bản xấu, và cần nói rõ điều
    đó là do MẤT TIỀN chứ không phải do đã cân lại danh mục.
    """
    from gold.xuan_trieu_model import estimate

    base = estimate(xau_usd=xau_now, usd_vnd=usd_vnd)
    if not base or not gold_tael:
        return []
    rows: list[ScenarioRow] = []
    now_value = base.shop_buy_trieu * gold_tael
    for shock in shocks_pct:
        est = estimate(xau_usd=base.xau_usd * (1 + shock / 100), usd_vnd=base.usd_vnd)
        if not est:
            continue
        value = est.shop_buy_trieu * gold_tael
        total = value + other_assets_trieu
        rows.append(ScenarioRow(
            shock_pct=shock,
            xau_after=est.xau_usd,
            gold_price_after_trieu=est.shop_buy_trieu,
            gold_value_after_trieu=value,
            total_after_trieu=total,
            change_trieu=value - now_value,
            gold_pct_after=(value / total * 100) if total else 0.0,
        ))
    return rows


def protection_from_selling(
    chi_sold: int, proceeds_trieu: float, shocks_pct: Sequence[float] = DEFAULT_SHOCKS_PCT
) -> list[Protection]:
    """Nối kế hoạch bán với kịch bản giá: bán để tránh CÁI GÌ, bằng bao nhiêu tiền.

    Chỉ tính phần bảo vệ do rời khỏi vàng, KHÔNG cộng lãi tiền gửi vào đây —
    lãi đã nằm ở `decision/rebalance.py`, cộng lần nữa là đếm trùng một khoản.
    """
    out = []
    for shock in shocks_pct:
        if shock >= 0:
            continue  # bán không "bảo vệ" gì khi giá tăng — vế đó là phí cơ hội
        out.append(Protection(chi_sold=chi_sold, proceeds_trieu=proceeds_trieu,
                              shock_pct=shock,
                              protected_trieu=proceeds_trieu * abs(shock) / 100))
    return out


def headline(rows: Sequence[ScenarioRow], shock_pct: float = -15.0) -> str:
    """Một câu bằng TIỀN cho mục tổng quan — thứ 19 kỳ khuyến nghị còn thiếu."""
    row = next((r for r in rows if abs(r.shock_pct - shock_pct) < 1e-9), None)
    if row is None:
        return ""
    return (f"Nếu vàng giảm {abs(shock_pct):.0f}%, danh mục mất khoảng "
            f"{_vi(abs(row.change_trieu), 0)} tr và tỷ trọng vàng tự về "
            f"{_vi(row.gold_pct_after)}% — nhưng về bằng cách mất tiền, "
            "không phải bằng cách cân lại danh mục.")


def _vi(value: float, decimals: int = 1) -> str:
    """Định dạng số kiểu Việt (1.234,5) — trang này toàn tiếng Việt, trộn hai
    quy ước dấu trong cùng một thẻ đọc rất lộn xộn."""
    return f"{value:,.{decimals}f}".translate(str.maketrans({",": ".", ".": ","}))


def _xau_closes(history: Optional[Sequence[dict]] = None) -> list[float]:
    rows = list(history) if history is not None else _load_history()
    out = []
    for r in rows:
        gold = r.get("gold")
        v = gold.get("xauusd") if isinstance(gold, dict) else None
        if isinstance(v, (int, float)) and v > 0:
            out.append(float(v))
    return out


def _load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    return [json.loads(l) for l in HISTORY_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

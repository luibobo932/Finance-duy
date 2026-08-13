"""Đo SAI SỐ của mô hình định giá vàng từ dữ liệu thật, thay vì im lặng.

Vì sao cần: toàn bộ con số "vàng chiếm 76% tài sản" — thứ đang kích hoạt khuyến
nghị CHỐT BỚT — dựa trên hệ số quy đổi lấy từ ĐÚNG MỘT tấm ảnh bảng giá tiệm
ngày 18/7. Một con số trông rất chắc chắn mà không ai biết nó sai bao nhiêu.

Đo được gì từ dữ liệu đang có: 11 quan sát cặp (giá vàng thế giới quy đổi, giá
nhẫn trong nước) trong `data/history.jsonl`. Từ đó ra hai kết luận thật:

    k = nhẫn_trong_nước / thế_giới_quy_đổi
    n = 11 · mean 1,1368 · stdev 0,0081 · lệch tối đa 1,48%
    Pearson(XAU, k) = −0,753   → giá trong nước TRỄ so với thế giới:
                                  XAU tăng nhanh thì k co lại

Hồi quy k theo XAU giảm sai số từ 0,55% xuống 0,37% (tốt hơn 32%). NHƯNG chỉ
dùng được TRONG khoảng đã hiệu chuẩn (3.984–4.134$). XAU hiện tại 4.340$ nằm
ngoài khoảng đó: ngoại suy hồi quy ra ngoài vùng dữ liệu sẽ lệch k tới −3,3%
(≈29 triệu đồng trên danh mục này) — sai một cách rất tự tin. Nên:

    trong khoảng  → dùng hồi quy
    ngoài khoảng  → dùng trung bình phẳng + NỚI biên theo mức ngoại suy

Phân biệt rành mạch hai thứ, vì chúng có số mẫu khác nhau:
  - MỨC GIÁ (level) vẫn từ 1 mẫu duy nhất — tấm ảnh 18/7. Module này KHÔNG
    sửa được điều đó; chỉ ảnh bảng giá mới mới sửa được.
  - ĐỘ BIẾN ĐỘNG (band) từ 11 quan sát thị trường — đây là phần mới đo được.
"""
from __future__ import annotations

import json
import statistics as st
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from gold.conversion import theoretical_trieu_per_tael

ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = ROOT / "data" / "history.jsonl"

# Dưới số quan sát này thì chưa nói được gì về độ biến động
MIN_OBS_FOR_BAND = 3
# Cần bấy nhiêu quan sát mới tin hồi quy (mô hình 2 tham số cần dư bậc tự do)
MIN_OBS_FOR_REGRESSION = 8
# Ngoại suy quá mức này (so với biên khoảng hiệu chuẩn) thì cấm dùng hồi quy
MAX_EXTRAPOLATION_PCT = 1.0
# Biên tối thiểu, kể cả khi dữ liệu trông rất ổn định — mô hình 1 mẫu về MỨC
# giá thì không bao giờ đáng tin tới mức nói "sai số 0%"
MIN_BAND_PCT = 0.5


@dataclass
class MarketRatio:
    """Một quan sát tỷ lệ giá trong nước / giá thế giới quy đổi."""
    date: str
    ky: str
    xau_usd: float
    world_trieu: float
    domestic_trieu: float
    ratio: float


@dataclass
class RatioModel:
    n: int
    mean: float
    stdev: Optional[float]
    min_ratio: float
    max_ratio: float
    xau_min: float
    xau_max: float
    correlation: Optional[float]
    slope: Optional[float]
    intercept: Optional[float]
    mae_mean_pct: Optional[float]
    mae_regression_pct: Optional[float]

    @property
    def use_regression(self) -> bool:
        return (self.n >= MIN_OBS_FOR_REGRESSION
                and self.slope is not None
                and self.mae_regression_pct is not None
                and self.mae_mean_pct is not None
                and self.mae_regression_pct < self.mae_mean_pct)


@dataclass
class BandedEstimate:
    """Ước tính kèm khoảng — thay cho một con số giả chính xác."""
    mid_trieu: float
    low_trieu: float
    high_trieu: float
    band_low_pct: float   # biên dưới có thể RỘNG HƠN biên trên khi biết hướng sai
    band_high_pct: float
    method: str            # "regression" | "mean" | "single_sample"
    extrapolated: bool
    level_sample_size: int  # số mẫu quyết định MỨC giá (ảnh bảng giá tiệm)
    band_sample_size: int   # số quan sát quyết định BIÊN
    note: str


def load_market_ratios(history: Optional[Sequence[dict]] = None) -> list[MarketRatio]:
    """Các quan sát có ĐỦ cả giá thế giới và giá trong nước để tính tỷ lệ."""
    if history is None:
        if not HISTORY_PATH.exists():
            return []
        history = [json.loads(l) for l in
                   HISTORY_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    out: list[MarketRatio] = []
    for snap in history:
        gold = snap.get("gold") or {}
        xau, fx = gold.get("xauusd"), snap.get("fx_vcb_sell")
        domestic = gold.get("ring_sell")
        if not (xau and fx and domestic):
            continue
        world = theoretical_trieu_per_tael(xau, fx)
        if world <= 0:
            continue
        out.append(MarketRatio(
            date=snap.get("date", ""), ky=snap.get("ky", ""), xau_usd=float(xau),
            world_trieu=world, domestic_trieu=float(domestic), ratio=domestic / world,
        ))
    return out


def fit_ratio_model(obs: Sequence[MarketRatio]) -> Optional[RatioModel]:
    """Thống kê + hồi quy k theo XAU. None nếu chưa đủ quan sát."""
    if len(obs) < MIN_OBS_FOR_BAND:
        return None
    ks = [o.ratio for o in obs]
    xs = [o.xau_usd for o in obs]
    n = len(ks)
    mean_k = st.mean(ks)
    stdev = st.stdev(ks) if n >= 2 else None
    mae_mean = st.mean(abs(k - mean_k) for k in ks) / mean_k * 100

    corr = slope = intercept = mae_reg = None
    mean_x = st.mean(xs)
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x > 0 and n >= 2:
        cov = sum((x - mean_x) * (k - mean_k) for x, k in zip(xs, ks))
        var_k = sum((k - mean_k) ** 2 for k in ks)
        if var_k > 0:
            corr = cov / (var_x * var_k) ** 0.5
        slope = cov / var_x
        intercept = mean_k - slope * mean_x
        pred = [intercept + slope * x for x in xs]
        mae_reg = st.mean(abs(p - k) for p, k in zip(pred, ks)) / mean_k * 100

    return RatioModel(
        n=n, mean=mean_k, stdev=stdev, min_ratio=min(ks), max_ratio=max(ks),
        xau_min=min(xs), xau_max=max(xs), correlation=corr, slope=slope,
        intercept=intercept, mae_mean_pct=mae_mean, mae_regression_pct=mae_reg,
    )


def extrapolation_pct(xau: float, model: RatioModel) -> float:
    """Mức ngoại suy (%) so với biên gần nhất của khoảng đã hiệu chuẩn. 0 = trong khoảng."""
    if model.xau_min <= xau <= model.xau_max:
        return 0.0
    edge = model.xau_max if xau > model.xau_max else model.xau_min
    if edge <= 0:
        return 0.0
    return abs(xau - edge) / edge * 100


def implied_drift_pct(xau: float, model: RatioModel) -> float:
    """Mức k sẽ lệch (%) nếu quan hệ đã quan sát TIẾP TỤC ra ngoài khoảng.

    Dùng chính độ dốc hồi quy nhân với khoảng cách ngoại suy, thay vì cộng bừa
    "mức ngoại suy %" vào biên. Có dấu: âm = k thấp hơn trung bình.
    """
    if model.slope is None or model.mean == 0:
        return 0.0
    if model.xau_min <= xau <= model.xau_max:
        return 0.0
    edge = model.xau_max if xau > model.xau_max else model.xau_min
    return model.slope * (xau - edge) / model.mean * 100


def band_for(xau: float, model: Optional[RatioModel]) -> tuple[float, float, str, bool]:
    """(biên_dưới %, biên_trên %, phương pháp, có_ngoại_suy).

    Biên BẤT ĐỐI XỨNG khi biết hướng sai. Tương quan XAU–k âm mạnh nghĩa là giá
    trong nước trễ so với thế giới: khi XAU vừa tăng vượt khoảng đã hiệu chuẩn,
    ước tính có xu hướng CAO hơn giá tiệm thật. Biên đối xứng trong tình huống
    đó là nói dối theo kiểu lịch sự — nó ngụ ý sai lệch hai phía như nhau.
    """
    if model is None:
        return 2.5, 2.5, "single_sample", False  # chưa đo được gì: biên mặc định thận trọng
    ex = extrapolation_pct(xau, model)
    if model.use_regression and ex <= MAX_EXTRAPOLATION_PCT:
        base = max(MIN_BAND_PCT, model.mae_regression_pct or MIN_BAND_PCT)
        return base, base, "regression", False

    # Ngoài khoảng: KHÔNG ngoại suy hồi quy để lấy MỨC, nhưng dùng độ dốc đã
    # đo để biết sai lệch có thể lớn tới đâu và LỆCH VỀ PHÍA NÀO.
    spread = max(abs(model.max_ratio - model.mean),
                 abs(model.mean - model.min_ratio)) / model.mean * 100
    base = max(MIN_BAND_PCT, spread, model.mae_mean_pct or MIN_BAND_PCT)
    drift = implied_drift_pct(xau, model)
    low = base + max(0.0, -drift)   # drift âm -> rủi ro giá THẤP hơn ước tính
    high = base + max(0.0, drift)
    return low, high, "mean", ex > 0


def banded_estimate(
    mid_trieu: float,
    xau: float,
    *,
    level_sample_size: int = 1,
    history: Optional[Sequence[dict]] = None,
) -> BandedEstimate:
    """Bọc một ước tính điểm thành khoảng, kèm lời giải thích biên đến từ đâu.

    `mid_trieu` là ước tính điểm hiện có (từ gold/xuan_trieu_model). Hàm này
    KHÔNG sửa mức giá — chỉ nói mức đó có thể lệch bao nhiêu.
    """
    model = fit_ratio_model(load_market_ratios(history))
    band_low, band_high, method, extrapolated = band_for(xau, model)
    low = mid_trieu * (1 - band_low / 100)
    high = mid_trieu * (1 + band_high / 100)

    if model is None:
        note = ("Chưa đủ quan sát giá trong nước để đo sai số — biên là mức thận trọng "
                "mặc định, không phải số đo được.")
    elif method == "regression":
        note = (f"Biên từ sai số hồi quy trên {model.n} quan sát "
                f"(XAU {model.xau_min:.0f}–{model.xau_max:.0f}$).")
    else:
        ex = extrapolation_pct(xau, model)
        drift = implied_drift_pct(xau, model)
        note = (f"XAU {xau:.0f}$ NGOÀI khoảng đã hiệu chuẩn "
                f"({model.xau_min:.0f}–{model.xau_max:.0f}$, lệch {ex:.1f}%) nên KHÔNG ngoại suy "
                f"hồi quy để lấy mức giá; biên = mức lệch tối đa đã thấy trên {model.n} quan sát "
                f"cộng mức trôi {abs(drift):.1f}% mà độ dốc đã đo hàm ý.")
    if model and model.correlation is not None and model.correlation < -0.5:
        note += (f" Tương quan XAU–tỷ lệ = {model.correlation:+.2f}: giá trong nước TRỄ so với "
                 "thế giới, nên khi thế giới tăng nhanh, ước tính này thường CAO hơn giá tiệm "
                 "thật — vì vậy biên dưới rộng hơn biên trên.")

    return BandedEstimate(
        mid_trieu=mid_trieu, low_trieu=low, high_trieu=high,
        band_low_pct=band_low, band_high_pct=band_high,
        method=method, extrapolated=extrapolated,
        level_sample_size=level_sample_size,
        band_sample_size=model.n if model else 0, note=note,
    )

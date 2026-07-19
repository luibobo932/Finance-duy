"""Chỉ báo kỹ thuật mở rộng cho cổ phiếu: Relative Volume, Volume z-score,
hỗ trợ/kháng cự (pivot), breakout, trend state.

Dùng chung analytics/ta_core.py cho RSI/MACD/MA/Bollinger/ATR — không định
nghĩa lại ở đây.
"""
from __future__ import annotations

from typing import Optional

from analytics.ta_core import macd, rsi, sma


def relative_volume(current_vol: float, avg_vol: Optional[float]) -> Optional[float]:
    """Khối lượng hiện tại / bình quân — None nếu chưa có bình quân."""
    if not avg_vol:
        return None
    return round(current_vol / avg_vol, 2)


def volume_zscore(volumes: list[float]) -> Optional[float]:
    """Z-score của phiên gần nhất so với các phiên trước đó trong chuỗi.

    `volumes` phải có phiên gần nhất ở cuối danh sách. Cần >=2 phiên trước
    đó để tính độ lệch chuẩn có ý nghĩa.
    """
    if len(volumes) < 3:
        return None
    *history, current = volumes
    mean = sum(history) / len(history)
    var = sum((v - mean) ** 2 for v in history) / (len(history) - 1)
    sd = var ** 0.5
    if sd == 0:
        return None
    return round((current - mean) / sd, 2)


def find_pivots(highs: list[float], lows: list[float], window: int = 2) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Tìm đỉnh/đáy cục bộ (pivot) — điểm cao/thấp hơn `window` phiên liền kề mỗi bên.

    Trả (pivot_highs, pivot_lows), mỗi phần tử là (chỉ_số_trong_chuỗi, giá).
    """
    n = len(highs)
    pivot_highs, pivot_lows = [], []
    for i in range(window, n - window):
        left_h, right_h = highs[i - window:i], highs[i + 1:i + 1 + window]
        if highs[i] > max(left_h, default=float("-inf")) and highs[i] > max(right_h, default=float("-inf")):
            pivot_highs.append((i, highs[i]))
        left_l, right_l = lows[i - window:i], lows[i + 1:i + 1 + window]
        if lows[i] < min(left_l, default=float("inf")) and lows[i] < min(right_l, default=float("inf")):
            pivot_lows.append((i, lows[i]))
    return pivot_highs, pivot_lows


def support_resistance(highs: list[float], lows: list[float], last_close: float, window: int = 2) -> dict:
    """Hỗ trợ = pivot đáy gần nhất DƯỚI giá hiện tại; kháng cự = pivot đỉnh
    gần nhất TRÊN giá hiện tại. Trả None cho bên nào không tìm thấy — không
    tự bịa mức hỗ trợ/kháng cự khi thiếu dữ liệu.
    """
    pivot_highs, pivot_lows = find_pivots(highs, lows, window)
    resistances = sorted([p for _, p in pivot_highs if p > last_close])
    supports = sorted([p for _, p in pivot_lows if p < last_close], reverse=True)
    return {
        "resistance": resistances[0] if resistances else None,
        "support": supports[0] if supports else None,
        "all_resistances": resistances,
        "all_supports": supports,
    }


def detect_breakout(last_close: float, prev_close: float, resistance: Optional[float], support: Optional[float]) -> str:
    """BREAKOUT_UP nếu vừa vượt kháng cự, BREAKOUT_DOWN nếu vừa thủng hỗ trợ,
    NONE nếu không có breakout hoặc thiếu dữ liệu hỗ trợ/kháng cự."""
    if resistance is not None and prev_close <= resistance < last_close:
        return "BREAKOUT_UP"
    if support is not None and prev_close >= support > last_close:
        return "BREAKOUT_DOWN"
    return "NONE"


def trend_state(closes: list[float]) -> str:
    """UPTREND/DOWNTREND/SIDEWAYS dựa trên vị trí giá so với MA20/MA50.
    UNKNOWN nếu chưa đủ dữ liệu tính MA50.
    """
    s20, s50 = sma(closes, 20), sma(closes, 50)
    if s20 is None or s50 is None:
        return "UNKNOWN"
    price = closes[-1]
    if price > s20 > s50:
        return "UPTREND"
    if price < s20 < s50:
        return "DOWNTREND"
    return "SIDEWAYS"


def technical_snapshot(highs: list[float], lows: list[float], closes: list[float], volumes: list[float]) -> dict:
    """Gộp toàn bộ chỉ báo kỹ thuật mở rộng thành 1 dict — dùng cho bản tin."""
    avg_vol = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) >= 2 else None
    sr = support_resistance(highs, lows, closes[-1]) if closes else {"resistance": None, "support": None}
    return {
        "rsi14": rsi(closes),
        "macd": macd(closes),
        "sma20": sma(closes, 20),
        "sma50": sma(closes, 50),
        "relative_volume": relative_volume(volumes[-1], avg_vol) if volumes else None,
        "volume_zscore": volume_zscore(volumes),
        "support": sr["support"],
        "resistance": sr["resistance"],
        "breakout": (
            detect_breakout(closes[-1], closes[-2], sr["resistance"], sr["support"])
            if len(closes) >= 2 else "NONE"
        ),
        "trend_state": trend_state(closes),
    }

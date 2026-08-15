"""Công thức lõi phân tích kỹ thuật — dùng chung cho vàng (gold/) và cổ phiếu
(equity/, scripts/indicators.py).

Tách ra từ scripts/indicators.py ở Phase 4 để không có 2 bản cài đặt RSI/MACD
khác nhau trong repo. Hành vi giữ NGUYÊN 100% so với bản gốc — chỉ đổi vị trí.
"""
from __future__ import annotations

import math
from typing import Optional


def sma(vals: list[float], n: int) -> Optional[float]:
    return sum(vals[-n:]) / n if len(vals) >= n else None


def ema_series(vals: list[float], n: int) -> list[float]:
    if len(vals) < n:
        return []
    k = 2 / (n + 1)
    out = [sum(vals[:n]) / n]
    for v in vals[n:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(closes: list[float], n: int = 14) -> Optional[float]:
    if len(closes) < n + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    # Wilder smoothing
    ag = sum(gains[:n]) / n
    al = sum(losses[:n]) / n
    for i in range(n, len(gains)):
        ag = (ag * (n - 1) + gains[i]) / n
        al = (al * (n - 1) + losses[i]) / n
    if al == 0:
        return 100.0
    rs = ag / al
    return round(100 - 100 / (1 + rs), 1)


def macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[dict]:
    if len(closes) < slow + signal:
        return None
    ef = ema_series(closes, fast)
    es = ema_series(closes, slow)
    ef = ef[-len(es):]
    macd_line = [a - b for a, b in zip(ef, es)]
    sig = ema_series(macd_line, signal)
    if not sig:
        return None
    m, s = macd_line[-1], sig[-1]
    return {"macd": round(m, 2), "signal": round(s, 2), "hist": round(m - s, 2)}


def bollinger(closes: list[float], n: int = 20, k: float = 2) -> Optional[dict]:
    if len(closes) < n:
        return None
    window = closes[-n:]
    mid = sum(window) / n
    var = sum((x - mid) ** 2 for x in window) / n
    sd = var ** 0.5
    return {"mid": round(mid, 1), "upper": round(mid + k * sd, 1), "lower": round(mid - k * sd, 1)}


def atr(highs: list[float], lows: list[float], closes: list[float], n: int = 14) -> Optional[float]:
    """Average True Range (Wilder smoothing) — đo biên độ dao động thực."""
    if len(closes) < n + 1 or len(highs) != len(closes) or len(lows) != len(closes):
        return None
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    a = sum(trs[:n]) / n
    for i in range(n, len(trs)):
        a = (a * (n - 1) + trs[i]) / n
    return round(a, 2)


def volatility_annualized_pct(closes: list[float], n: int = 20) -> Optional[float]:
    """Độ biến động (annualized, %) từ log-return n phiên gần nhất."""
    if len(closes) < n + 1:
        return None
    window = closes[-(n + 1):]
    rets = [math.log(window[i] / window[i - 1]) for i in range(1, len(window)) if window[i - 1] > 0]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    sd = var ** 0.5
    return round(sd * (252 ** 0.5) * 100, 2)


# --- Nhãn xu hướng: MỘT định nghĩa cho cả vàng lẫn cổ phiếu ------------------
#
# Trước đây logic này chỉ nằm trong gold/indicators.py. Khi nối tiếp phần cổ
# phiếu, chép nó sang equity/ sẽ tạo nguồn sự thật thứ hai cho cùng một câu hỏi
# — đúng cái bẫy mà chính module này ra đời để tránh (2 bản cài đặt RSI).

RSI_BULL_ABOVE = 55.0
RSI_BEAR_BELOW = 45.0


def indicator_votes(rsi14: Optional[float], macd_hist: Optional[float]) -> dict[str, int]:
    """Phiếu của từng chỉ báo ĐANG CÓ: +1 tích cực, −1 tiêu cực, 0 trung tính.

    Chỉ báo thiếu thì KHÔNG bỏ phiếu — vắng mặt, không phải phiếu trắng.
    """
    votes: dict[str, int] = {}
    if rsi14 is not None:
        votes["rsi"] = 1 if rsi14 > RSI_BULL_ABOVE else (-1 if rsi14 < RSI_BEAR_BELOW else 0)
    if macd_hist is not None:
        votes["macd"] = 1 if macd_hist > 0 else (-1 if macd_hist < 0 else 0)
    return votes


def trend_from_indicators(rsi14: Optional[float], macd_hist: Optional[float]) -> Optional[str]:
    """TICH_CUC / TIEU_CUC / TRUNG_TINH, hoặc **None khi không đo được**.

    None nghĩa là "chưa đo được", TRUNG_TINH nghĩa là "đã đo, và đang đi ngang".
    Gộp hai thứ này làm hệ thống nói chắc về điều nó không biết — lỗi đã gặp
    thật: nhãn TRUNG_TINH sinh ra từ một file 1 dòng được bản tin in như một
    phát hiện suốt gần một tháng.
    """
    votes = indicator_votes(rsi14, macd_hist)
    if not votes:
        return None
    score = sum(votes.values())
    if score >= 1:
        return "TICH_CUC"
    if score <= -1:
        return "TIEU_CUC"
    return "TRUNG_TINH"

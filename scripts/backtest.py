#!/usr/bin/env python3
"""Backtest quy tắc giao dịch trên dữ liệu EOD — kiểm chứng chiến lược trước khi tin.

Quy tắc hiện có (Phase 9):
  ma   — MA cross: mua khi giá cắt lên MA n, bán khi cắt xuống (mặc định n=20)
  rsi  — mua khi RSI(period) < buy_th (quá bán), bán khi RSI > sell_th (quá mua)

Chống look-ahead: tín hiệu tại phiên i chỉ tính từ giá TỚI phiên i, khớp lệnh
ngay giá đóng cửa phiên i. Có tùy chọn phí giao dịch (--fee, %/chiều) để kết
quả gần thực tế hơn.

Cách dùng:
  python3 scripts/backtest.py CTD                      # MA20 cross, không phí
  python3 scripts/backtest.py CTD --rule rsi           # RSI 14, ngưỡng 30/70
  python3 scripts/backtest.py VCB --ma 50 --fee 0.15   # MA50, phí 0,15%/chiều
  python3 scripts/backtest.py --file path.csv --rule rsi --buy-th 25 --sell-th 75
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.ta_core import rsi as rsi_core  # noqa: E402

EOD_DIR = ROOT / "data" / "eod"

# Mỗi trade: (ngày mua, ngày bán, giá mua, giá bán, lợi nhuận % sau phí)
Trade = tuple[str, str, float, float, float]


def load_closes(path) -> list[tuple[str, float]]:
    out = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                out.append((r["date"].strip(), float(r["close"])))
            except (ValueError, KeyError):
                continue
    return out


def _net_return_pct(buy: float, sell: float, fee_pct: float) -> float:
    """Lợi nhuận % sau khi trừ phí giao dịch fee_pct mỗi chiều (mua + bán)."""
    return (sell - buy) / buy * 100 - 2 * fee_pct


def backtest_ma(series: list[tuple[str, float]], n: int = 20, fee_pct: float = 0.0) -> Optional[list[Trade]]:
    closes = [c for _, c in series]
    if len(closes) < n + 2:
        return None
    trades: list[Trade] = []
    pos: Optional[tuple[str, float]] = None
    for i in range(n, len(closes)):
        ma = sum(closes[i - n:i]) / n
        prev_ma = sum(closes[i - n - 1:i - 1]) / n
        price, prev = closes[i], closes[i - 1]
        cross_up = prev <= prev_ma and price > ma
        cross_dn = prev >= prev_ma and price < ma
        if pos is None and cross_up:
            pos = (series[i][0], price)
        elif pos is not None and cross_dn:
            trades.append((pos[0], series[i][0], pos[1], price,
                           _net_return_pct(pos[1], price, fee_pct)))
            pos = None
    return trades


def backtest_rsi(series: list[tuple[str, float]], period: int = 14,
                 buy_th: float = 30, sell_th: float = 70, fee_pct: float = 0.0) -> Optional[list[Trade]]:
    """Mua khi RSI < buy_th, bán khi RSI > sell_th. RSI tại phiên i tính từ
    closes[:i+1] (chỉ dữ liệu quá khứ tới phiên đó — không look-ahead)."""
    closes = [c for _, c in series]
    if len(closes) < period + 2:
        return None
    trades: list[Trade] = []
    pos: Optional[tuple[str, float]] = None
    for i in range(period, len(closes)):
        r = rsi_core(closes[:i + 1], period)
        if r is None:
            continue
        price = closes[i]
        if pos is None and r < buy_th:
            pos = (series[i][0], price)
        elif pos is not None and r > sell_th:
            trades.append((pos[0], series[i][0], pos[1], price,
                           _net_return_pct(pos[1], price, fee_pct)))
            pos = None
    return trades


def main() -> None:
    args = sys.argv[1:]
    n = 20
    rule = "ma"
    fee = 0.0
    buy_th, sell_th = 30.0, 70.0
    period = 14

    def _pop(flag: str, cast, default):
        nonlocal args
        if flag in args:
            i = args.index(flag)
            val = cast(args[i + 1])
            args = args[:i] + args[i + 2:]
            return val
        return default

    n = _pop("--ma", int, n)
    rule = _pop("--rule", str, rule).lower()
    fee = _pop("--fee", float, fee)
    buy_th = _pop("--buy-th", float, buy_th)
    sell_th = _pop("--sell-th", float, sell_th)
    period = _pop("--rsi-period", int, period)
    file_arg = _pop("--file", str, None)

    if file_arg:
        path = Path(file_arg)
    elif args and not args[0].startswith("--"):
        path = EOD_DIR / f"{args[0].upper()}.csv"
    else:
        sys.exit(__doc__)
    if not path.exists():
        sys.exit(f"Chưa có dữ liệu: {path}")
    series = load_closes(path)

    if rule == "rsi":
        trades = backtest_rsi(series, period, buy_th, sell_th, fee)
        label = f"RSI{period} <{buy_th:g} mua / >{sell_th:g} bán"
        min_needed = period + 2
    else:
        trades = backtest_ma(series, n, fee)
        label = f"MA{n} cross"
        min_needed = n + 2

    if trades is None:
        print(f"Không đủ dữ liệu (cần ≥{min_needed} phiên, hiện {len(series)}).")
        return
    if not trades:
        print(f"Đủ dữ liệu ({len(series)} phiên) nhưng quy tắc {label} không phát tín hiệu "
              f"mua-bán trọn vẹn nào trong giai đoạn này.")
        return
    print(f"=== BACKTEST {label} — {path.stem} ({len(series)} phiên"
          f"{f', phí {fee:g}%/chiều' if fee else ''}) ===")
    wins = sum(1 for *_, r in trades if r > 0)
    total_ret = sum(r for *_, r in trades)
    for d1, d2, p1, p2, r in trades:
        print(f"  {d1} mua {p1:.2f} → {d2} bán {p2:.2f}: {r:+.1f}%")
    print(f"\nSố lệnh: {len(trades)} | Thắng: {wins}/{len(trades)} ({wins/len(trades)*100:.0f}%) "
          f"| Tổng lợi nhuận cộng dồn: {total_ret:+.1f}%")
    if not fee:
        print("Lưu ý: chưa tính phí, trượt giá — thêm --fee 0.15 để gần thực tế hơn.")


if __name__ == "__main__":
    main()

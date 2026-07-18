#!/usr/bin/env python3
"""Backtest quy tắc giao dịch trên dữ liệu EOD — kiểm chứng chiến lược trước khi tin.

Chiến lược mẫu: MA cross (mua khi giá cắt lên MA20, bán khi cắt xuống) — dễ mở rộng.
Cần data/eod/<MÃ>.csv đủ dài (≥ ~40 phiên mới có ý nghĩa).

Cách dùng:
  python3 scripts/backtest.py CTD
  python3 scripts/backtest.py --file path.csv --ma 20
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EOD_DIR = ROOT / "data" / "eod"


def load_closes(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                out.append((r["date"].strip(), float(r["close"])))
            except (ValueError, KeyError):
                continue
    return out


def backtest_ma(series, n=20):
    closes = [c for _, c in series]
    if len(closes) < n + 2:
        return None
    trades = []
    pos = None
    for i in range(n, len(closes)):
        ma = sum(closes[i - n:i]) / n
        prev_ma = sum(closes[i - n - 1:i - 1]) / n
        price, prev = closes[i], closes[i - 1]
        cross_up = prev <= prev_ma and price > ma
        cross_dn = prev >= prev_ma and price < ma
        if pos is None and cross_up:
            pos = (series[i][0], price)
        elif pos is not None and cross_dn:
            ret = (price - pos[1]) / pos[1] * 100
            trades.append((pos[0], series[i][0], pos[1], price, ret))
            pos = None
    return trades


def main():
    args = sys.argv[1:]
    n = 20
    if "--ma" in args:
        n = int(args[args.index("--ma") + 1])
    if "--file" in args:
        path = args[args.index("--file") + 1]
    elif args and not args[0].startswith("--"):
        path = EOD_DIR / f"{args[0].upper()}.csv"
    else:
        sys.exit(__doc__)
    if not Path(path).exists():
        sys.exit(f"Chưa có dữ liệu: {path}")
    series = load_closes(path)
    trades = backtest_ma(series, n)
    if not trades:
        print(f"Không đủ dữ liệu hoặc không có lệnh nào (cần ≥{n+2} phiên, hiện {len(series)}).")
        return
    print(f"=== BACKTEST MA{n} cross — {Path(path).stem} ({len(series)} phiên) ===")
    wins = sum(1 for *_, r in trades if r > 0)
    total_ret = sum(r for *_, r in trades)
    for d1, d2, p1, p2, r in trades:
        print(f"  {d1} mua {p1:.2f} → {d2} bán {p2:.2f}: {r:+.1f}%")
    print(f"\nSố lệnh: {len(trades)} | Thắng: {wins}/{len(trades)} ({wins/len(trades)*100:.0f}%) "
          f"| Tổng lợi nhuận cộng dồn: {total_ret:+.1f}%")
    print("Lưu ý: đây là backtest thô (chưa tính phí, trượt giá) — dùng để so sánh tương đối các quy tắc.")


if __name__ == "__main__":
    main()

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
    """Lợi nhuận % sau thuế và phí — dùng CHUNG `equity/costs.py` với phần còn
    lại của hệ thống, không tự tính lấy một công thức riêng.

    Công thức cũ ở đây là `(sell-buy)/buy*100 - 2*fee_pct`, sai hai chỗ và cả
    hai đều lệch về phía LẠC QUAN:

    1. **Bỏ hẳn thuế bán 0,1%** — khoản bắt buộc, phải nộp KỂ CẢ KHI LỖ
       (`equity/costs.SELL_TAX_PCT`). Mọi lệnh trong mọi backtest đều được
       cộng không 0,1 điểm %.
    2. **Trừ phí như điểm phần trăm phẳng.** Phí mua tính trên tiền vào, phí
       bán tính trên tiền RA. Trừ `2*fee_pct` là coi cả hai như tính trên tiền
       vào — sai càng nhiều khi lãi càng lớn, tức sai đúng ở chỗ quan trọng.

    Đo trên chính dữ liệu CTD (phí 0,2%/chiều):

        mua 62,4 → bán 63,0   cũ +0,562%   đúng +0,459%   lệch 0,10
        mua 62,4 → bán 93,0   cũ +48,638%  đúng +48,391%  lệch 0,25
        mua 100  → bán 200    cũ +99,600%  đúng +99,200%  lệch 0,40

    Vì sao 0,1–0,4 điểm % không phải chuyện nhỏ: backtest tồn tại để trả lời
    "quy tắc này có đáng theo không", mà thước đo là lãi tiền gửi ~8%/năm KHÔNG
    rủi ro. Một sai số luôn cùng chiều, cộng dồn theo số lệnh, đúng ở phía làm
    quy tắc trông tốt hơn thực tế — đó là loại sai số dẫn tới quyết định sai.
    """
    from equity.costs import net_upside_pct

    return net_upside_pct((sell - buy) / buy * 100, fee_pct)


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


def _so_voi_tien_gui(trades: list, total_ret_pct: float) -> None:
    """Quy tắc này có thắng nổi tiền gửi KHÔNG rủi ro trong cùng khoảng thời
    gian không — câu hỏi mà con số "+5,5%" một mình không trả lời được.

    Cùng nguyên tắc "rào lợi suất" đã áp cho khuyến nghị mua ở
    `decision/position_size.py`: một chiến lược chỉ đáng theo nếu vượt được
    mức tiền gửi tốt nhất đo được. Ở đây so trên ĐÚNG số ngày vốn thực sự nằm
    trong thị trường, không qui năm — 3 lệnh trong 43 phiên qui ra %/năm là
    phóng đại một mẫu quá nhỏ thành một tuyên bố về tương lai.
    """
    from datetime import datetime

    try:
        from deposits.ranking import load_normalized, rank

        ranked = rank(load_normalized())
        rate = ranked[0]["rate_pct"] if ranked else None
    except Exception:  # noqa: BLE001 — thiếu bảng lãi suất không được chặn backtest
        rate = None
    if rate is None:
        print("Chưa có bảng lãi suất tiền gửi để đối chiếu — "
              "không kết luận được quy tắc này có đáng theo không.")
        return

    ngay = 0
    for d1, d2, *_ in trades:
        try:
            ngay += (datetime.strptime(d2, "%Y-%m-%d")
                     - datetime.strptime(d1, "%Y-%m-%d")).days
        except (ValueError, TypeError):
            continue
    if ngay <= 0:
        return
    tien_gui = rate * ngay / 365
    print(f"\nVốn nằm trong thị trường {ngay} ngày. Cùng {ngay} ngày đó, gửi tiết kiệm "
          f"ở mức tốt nhất đo được ({rate:.2f}%/năm) cho {tien_gui:+.2f}% KHÔNG rủi ro.")
    if total_ret_pct > tien_gui:
        print(f"→ Quy tắc vượt tiền gửi {total_ret_pct - tien_gui:+.2f} điểm % — "
              "nhưng có rủi ro, và mẫu này quá nhỏ để kết luận.")
    else:
        print(f"→ Quy tắc THUA tiền gửi {tien_gui - total_ret_pct:.2f} điểm %, "
              "trong khi vẫn phải chịu rủi ro giá.")
    if len(trades) < 30:
        print(f"⚠️ Chỉ {len(trades)} lệnh — quá ít để nói quy tắc tốt hay xấu. "
              "Đây là mô tả những gì ĐÃ xảy ra, không phải dự báo.")


def main() -> None:
    args = sys.argv[1:]
    n = 20
    rule = "ma"
    # Mặc định là phí THẬT trong config, không phải 0. Giao dịch miễn phí chưa
    # bao giờ là sự thật, và một backtest mặc định bỏ chi phí là một backtest
    # mặc định trả lời sai câu hỏi nó sinh ra để trả lời.
    from equity.costs import load_fee_pct

    fee = load_fee_pct()
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
    from equity.costs import SELL_TAX_PCT

    print(f"=== BACKTEST {label} — {path.stem} ({len(series)} phiên, "
          f"phí {fee:g}%/chiều + thuế bán {SELL_TAX_PCT:g}%) ===")
    wins = sum(1 for *_, r in trades if r > 0)
    total_ret = sum(r for *_, r in trades)
    for d1, d2, p1, p2, r in trades:
        print(f"  {d1} mua {p1:.2f} → {d2} bán {p2:.2f}: {r:+.1f}%")
    print(f"\nSố lệnh: {len(trades)} | Thắng: {wins}/{len(trades)} ({wins/len(trades)*100:.0f}%) "
          f"| Tổng lợi nhuận cộng dồn: {total_ret:+.1f}%")
    print("Lợi nhuận đã trừ phí hai chiều và thuế bán (equity/costs.py) — "
          "CHƯA trừ trượt giá.")
    _so_voi_tien_gui(trades, total_ret)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Theo dõi hiệu suất danh mục giả lập Buffett-list so với ngày lập.

Cách dùng:
  python3 scripts/watchlist.py report                       # bảng hiệu suất
  python3 scripts/watchlist.py update                       # tải giá thật từ entrade cho cả danh sách
  python3 scripts/watchlist.py set FPT 92.0 --base          # đặt giá tham chiếu (lần đầu, thủ công)
  python3 scripts/watchlist.py set FPT 95.0                  # cập nhật giá hiện tại (thủ công)

`update` cần network mở tới services.entrade.com.vn (chạy được trên laptop
local; bị chặn trong sandbox claude.ai). Quy tắc chống look-ahead: base_price
đang null chỉ được điền bằng giá đóng cửa phiên GẦN NHẤT TRƯỚC HOẶC BẰNG
base_date — không bao giờ bằng giá sau ngày lập danh sách; base đã có thì
không bao giờ ghi đè.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

WL = ROOT / "data" / "watchlist.json"


def load():
    return json.loads(WL.read_text(encoding="utf-8"))


def save(d):
    WL.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_set(args):
    d = load()
    tk = args[0].upper()
    price = float(args[1])
    is_base = "--base" in args
    for s in d["stocks"]:
        if s["ticker"] == tk:
            if is_base:
                s["base_price"] = price
            s["last_price"] = price
            save(d)
            print(f"Đã cập nhật {tk}: {'base+last' if is_base else 'last'} = {price}")
            return
    sys.exit(f"Không có mã {tk} trong watchlist")


def apply_prices(data: dict, closes_by_ticker: dict[str, list[tuple[str, float]]]) -> tuple[dict, list[str]]:
    """Áp giá đóng cửa thật vào watchlist. Trả (data đã sửa, ghi chú).

    - last_price: giá đóng cửa mới nhất có được.
    - base_price null: điền bằng phiên gần nhất ≤ base_date (chống look-ahead);
      không có phiên nào trước ngày lập → để null + ghi chú, không bịa.
    - base_price đã có: KHÔNG ghi đè (giá tham chiếu là bất biến).
    """
    notes: list[str] = []
    base_date = data.get("base_date", "")
    for s in data["stocks"]:
        closes = sorted(closes_by_ticker.get(s["ticker"], []))
        if not closes:
            notes.append(f"{s['ticker']}: không có dữ liệu giá — giữ nguyên")
            continue
        s["last_price"] = closes[-1][1]
        if s.get("base_price") is None:
            on_or_before = [c for d, c in closes if d <= base_date]
            if on_or_before:
                s["base_price"] = on_or_before[-1]
            else:
                notes.append(f"{s['ticker']}: chưa điền được base (không có phiên nào ≤ {base_date})")
    return data, notes


def cmd_update() -> None:
    from fetch_eod import FetchError, drop_incomplete_today, fetch_ohlc_raw, parse_ohlc_response
    from datetime import datetime, timedelta
    from fetch_eod import VN

    d = load()
    now = datetime.now(VN)
    frm = int((now - timedelta(days=40)).timestamp())
    to = int(now.timestamp())
    closes_by_ticker: dict[str, list[tuple[str, float]]] = {}
    for s in d["stocks"]:
        tk = s["ticker"]
        try:
            rows = drop_incomplete_today(parse_ohlc_response(fetch_ohlc_raw(tk, frm, to)), now)
        except FetchError as e:
            print(f"{tk}: lỗi tải — {e}", file=sys.stderr)
            continue
        closes_by_ticker[tk] = [(r["date"], r["close"]) for r in rows]
    d, notes = apply_prices(d, closes_by_ticker)
    save(d)
    print(f"Đã cập nhật giá thật cho {len(closes_by_ticker)}/{len(d['stocks'])} mã từ entrade.")
    for n in notes:
        print(f"  ⚠️ {n}")
    cmd_report()


def cmd_report():
    d = load()
    print(f"=== BUFFETT-LIST — hiệu suất từ {d['base_date']} ===")
    print(f"{'Mã':<6}{'Nhóm':<6}{'Base':>8}{'Hiện':>8}{'% thay đổi':>12}  Moat")
    tracked = []
    for s in sorted(d["stocks"], key=lambda x: (x["group"], x["ticker"])):
        bp, lp = s.get("base_price"), s.get("last_price")
        if bp and lp:
            pct = (lp - bp) / bp * 100
            tracked.append(pct)
            print(f"{s['ticker']:<6}{s['group']:<6}{bp:>8}{lp:>8}{pct:>+11.2f}%  {s['moat']}")
        else:
            print(f"{s['ticker']:<6}{s['group']:<6}{'—':>8}{'—':>8}{'chưa có giá':>12}  {s['moat']}")
    if tracked:
        print(f"\nTrung bình danh mục đang theo: {sum(tracked)/len(tracked):+.2f}%")
    print("Gợi ý: cập nhật giá bằng watchlist.py set <MÃ> <giá> để đo hiệu suất so VN-Index.")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "set":
        cmd_set(sys.argv[2:])
    elif sys.argv[1] == "report":
        cmd_report()
    elif sys.argv[1] == "update":
        cmd_update()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()

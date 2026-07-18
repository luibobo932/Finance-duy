#!/usr/bin/env python3
"""Theo dõi hiệu suất danh mục giả lập Buffett-list so với ngày lập.

Cách dùng:
  python3 scripts/watchlist.py report                       # bảng hiệu suất
  python3 scripts/watchlist.py set FPT 92.0 --base          # đặt giá tham chiếu (lần đầu)
  python3 scripts/watchlist.py set FPT 95.0                  # cập nhật giá hiện tại
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()

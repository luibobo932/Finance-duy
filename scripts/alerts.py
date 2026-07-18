#!/usr/bin/env python3
"""Kiểm tra ngưỡng cảnh báo giá — chạy giữa phiên hoặc trong mỗi bản tin.

Truyền giá hiện tại qua JSON; script so với data/alerts.json và in các cảnh báo bị kích hoạt.

Cách dùng:
  python3 scripts/alerts.py '{"VCB":57.8,"CTD":63.5,"XAUUSD":4017}'
  echo '{...}' | python3 scripts/alerts.py
  python3 scripts/alerts.py --list        # liệt kê các ngưỡng đang theo dõi
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALERTS = ROOT / "data" / "alerts.json"


def load():
    return json.loads(ALERTS.read_text(encoding="utf-8")).get("alerts", [])


def main():
    args = sys.argv[1:]
    if "--list" in args:
        for a in load():
            arrow = "▼ dưới" if a["type"] == "below" else "▲ trên"
            print(f"  [{a['asset']}] {arrow} {a['level']}: {a['note']}")
        return
    raw = args[0] if args else sys.stdin.read()
    try:
        prices = json.loads(raw)
    except (json.JSONDecodeError, IndexError):
        sys.exit(__doc__)
    hits = []
    for a in load():
        p = prices.get(a["asset"])
        if p is None:
            continue
        if (a["type"] == "below" and p < a["level"]) or (a["type"] == "above" and p > a["level"]):
            hits.append((a, p))
    if not hits:
        print("✅ Không có ngưỡng nào bị chạm.")
        return
    print(f"🚨 {len(hits)} CẢNH BÁO KÍCH HOẠT:")
    for a, p in hits:
        d = "thủng xuống" if a["type"] == "below" else "vượt lên"
        print(f"  • {a['asset']} = {p} đã {d} {a['level']} → {a['note']}")


if __name__ == "__main__":
    main()

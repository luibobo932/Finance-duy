#!/usr/bin/env python3
"""Kiểm tra ngưỡng cảnh báo giá — chạy giữa phiên hoặc trong mỗi bản tin.

Truyền giá hiện tại qua JSON; script so với data/alerts.json và in các cảnh báo
bị kích hoạt, PHÂN BIỆT tin mới với ngưỡng đã lỗi thời (xem
analytics/alert_health.py: đo 13/8 có 3/6 ngưỡng kích hoạt vĩnh viễn vì đặt theo
giá 18/7 rồi không cập nhật).

Cách dùng:
  python3 scripts/alerts.py '{"VCB":57.8,"CTD":63.5,"XAUUSD":4017}'
  echo '{...}' | python3 scripts/alerts.py
  python3 scripts/alerts.py --list                  # ngưỡng đang theo dõi + số lần đã chạm
  python3 scripts/alerts.py --reanchor '{...}'      # đặt lại ngưỡng theo biến động thật
  python3 scripts/alerts.py '{...}' --no-state      # quét mà không cập nhật bộ đếm
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.alert_health import (  # noqa: E402
    band_from_eod,
    daily_volatility,
    evaluate,
    load_state,
    reanchor,
    save_state,
)

ALERTS = ROOT / "data" / "alerts.json"
EOD_DIR = ROOT / "data" / "eod"
HIST = ROOT / "data" / "history.jsonl"


def load() -> list[dict]:
    return json.loads(ALERTS.read_text(encoding="utf-8")).get("alerts", [])


def save(alerts: list[dict]) -> None:
    doc = json.loads(ALERTS.read_text(encoding="utf-8"))
    doc["alerts"] = alerts
    ALERTS.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _today() -> str:
    """Ngày của snapshot mới nhất (ngày dữ liệu), không phải ngày hệ thống."""
    if HIST.exists():
        lines = [l for l in HIST.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            return json.loads(lines[-1]).get("date", "")
    from datetime import date

    return date.today().isoformat()


def _period() -> str:
    """Khoá kỳ (ngày + sáng/chiều) để bộ đếm tính theo KỲ, không theo số lần quét."""
    if HIST.exists():
        lines = [l for l in HIST.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            s = json.loads(lines[-1])
            return f"{s.get('date')}-{s.get('ky')}"
    return _today()


def _bands(prices: dict) -> dict[str, float]:
    """Khoảng đặt ngưỡng cho từng tài sản, đo từ dữ liệu thật của chính nó."""
    bands: dict[str, float] = {}
    for asset in prices:
        if asset == "XAUUSD":
            if HIST.exists():
                xs = []
                for line in HIST.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    v = (json.loads(line).get("gold") or {}).get("xauusd")
                    if v:
                        xs.append(float(v))
                vol = daily_volatility(xs)
                if vol:
                    bands[asset] = vol * 1.5
        else:
            band = band_from_eod(EOD_DIR / f"{asset}.csv")
            if band:
                bands[asset] = band
    return bands


def cmd_reanchor(raw: str) -> None:
    prices = json.loads(raw)
    bands = _bands(prices)
    updated, notes = reanchor(load(), prices, bands, today=_today())
    print("=== ĐẶT LẠI NGƯỠNG THEO BIẾN ĐỘNG THẬT (1,5× ATR/độ lệch chuẩn) ===")
    for n in notes:
        print(f"  {n}")
    save(updated)
    # Ngưỡng đã đổi thì bộ đếm cũ vô nghĩa — xoá để lần chạm tới lại là TIN.
    save_state({})
    print("\nĐã ghi data/alerts.json và reset bộ đếm (data/alert_state.json).")


def main() -> None:
    args = sys.argv[1:]
    if "--list" in args:
        state = load_state()
        for a in load():
            aid = a.get("id", "")
            n = int(state.get(aid, {}).get("consecutive_fires", 0) or 0)
            arrow = "▼ dưới" if a["type"] == "below" else "▲ trên"
            suffix = f"  [đã chạm liên tiếp {n} lần]" if n else ""
            print(f"  [{a['asset']}] {arrow} {a['level']}: {a['note']}{suffix}")
        return

    if "--reanchor" in args:
        rest = [x for x in args if x != "--reanchor"]
        cmd_reanchor(rest[0] if rest else sys.stdin.read())
        return

    positional = [x for x in args if not x.startswith("--")]
    raw = positional[0] if positional else sys.stdin.read()
    try:
        prices = json.loads(raw)
    except (json.JSONDecodeError, IndexError):
        sys.exit(__doc__)

    results, new_state = evaluate(load(), prices, load_state(),
                                 today=_today(), period=_period())
    if "--no-state" not in args:
        save_state(new_state)

    fired = [r for r in results if r.fired]
    fresh = [r for r in fired if not r.is_stale]
    stale = [r for r in fired if r.is_stale]

    if not fired:
        print("✅ Không có ngưỡng nào bị chạm.")
    if fresh:
        print(f"🚨 {len(fresh)} CẢNH BÁO KÍCH HOẠT:")
        for r in fresh:
            print(f"  • {r.headline}")
    if stale:
        print(f"\n🔧 {len(stale)} NGƯỠNG LỖI THỜI (kích hoạt liên tiếp, không còn là tin mới):")
        for r in stale:
            print(f"  • {r.headline}")
        print("  → Chạy: python3 scripts/alerts.py --reanchor '<json giá hiện tại>'")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Quản lý lịch sử số liệu bản tin đầu tư và phân tích xu hướng.

Cách dùng:
  python3 scripts/trend.py append '<json snapshot>'   # hoặc đọc từ stdin
  python3 scripts/trend.py report
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "history.jsonl"
PORT = ROOT / "data" / "portfolio.json"

REQUIRED = ["date", "ky", "vnindex", "gold"]


def load_history():
    if not HIST.exists():
        return []
    return [json.loads(line) for line in HIST.read_text(encoding="utf-8").splitlines() if line.strip()]


def fmt(x, nd=2):
    if x is None:
        return "n/a"
    s = f"{x:,.{nd}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def cmd_append(arg):
    raw = arg if arg else sys.stdin.read()
    snap = json.loads(raw)
    missing = [k for k in REQUIRED if k not in snap]
    if missing:
        sys.exit(f"LỖI: snapshot thiếu trường bắt buộc: {missing}")
    if snap["ky"] not in ("sang", "chieu"):
        sys.exit("LỖI: 'ky' phải là 'sang' hoặc 'chieu'")
    hist = load_history()
    if any(h["date"] == snap["date"] and h["ky"] == snap["ky"] for h in hist):
        sys.exit(f"LỖI: đã có snapshot {snap['date']} kỳ {snap['ky']} — không ghi trùng")
    HIST.parent.mkdir(parents=True, exist_ok=True)
    with HIST.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snap, ensure_ascii=False) + "\n")
    print(f"Đã ghi snapshot {snap['date']} ({snap['ky']}) — tổng {len(hist) + 1} bản ghi")


def delta_line(name, cur, prev, unit=""):
    if cur is None:
        return f"- {name}: chưa có số liệu kỳ này"
    if prev is None:
        return f"- {name}: {fmt(cur)}{unit} (chưa có kỳ trước để so)"
    d = cur - prev
    arrow = "▲" if d > 0 else ("▼" if d < 0 else "=")
    pct = f" ({d / prev * 100:+.2f}%)" if prev else ""
    return f"- {name}: {fmt(cur)}{unit} {arrow} {fmt(abs(d))}{unit} so với kỳ trước{pct}"


def get(snap, *path):
    cur = snap
    for p in path:
        if not isinstance(cur, dict) or p not in cur or cur[p] is None:
            return None
        cur = cur[p]
    return cur


def cmd_report():
    hist = load_history()
    if not hist:
        sys.exit("Chưa có lịch sử — chạy append trước.")
    cur = hist[-1]
    prev = hist[-2] if len(hist) > 1 else None
    print(f"=== XU HƯỚNG (kỳ hiện tại: {cur['date']} {cur['ky']}, {len(hist)} bản ghi) ===\n")

    print("## So với bản tin trước")
    for name, path, unit in [
        ("VN-Index", ("vnindex", "close"), ""),
        ("VCB", ("vcb", "close"), " đ"),
        ("CTD", ("ctd", "close"), " đ"),
        ("Vàng SJC bán ra", ("gold", "sjc_sell"), " tr"),
        ("Vàng thế giới", ("gold", "xauusd"), " $"),
        ("Chênh lệch vàng VN–TG", ("gold", "premium_trieu"), " tr"),
    ]:
        print(delta_line(name, get(cur, *path), get(prev, *path) if prev else None, unit))

    # Chuỗi khối ngoại: chỉ tính trên các kỳ "chieu" (số chốt phiên) để không đếm trùng
    flows = [(h["date"], h.get("foreign_net_ty")) for h in hist
             if h["ky"] == "chieu" and h.get("foreign_net_ty") is not None]
    if flows:
        sign = 1 if flows[-1][1] > 0 else -1
        streak = 0
        total = 0.0
        for _, v in reversed(flows):
            if v * sign > 0:
                streak += 1
                total += v
            else:
                break
        kind = "MUA ròng" if sign > 0 else "BÁN ròng"
        print(f"- Khối ngoại: {kind} {streak} phiên liên tiếp, lũy kế {fmt(abs(total), 0)} tỷ đồng")

    # Thay đổi lãi suất so với kỳ trước
    if prev:
        prev_rates = {(d["bank"], d["term_months"]): d["rate_pct"] for d in prev.get("deposit_top", [])}
        changes = []
        for d in cur.get("deposit_top", []):
            key = (d["bank"], d["term_months"])
            if key in prev_rates and prev_rates[key] != d["rate_pct"]:
                changes.append(f"{d['bank']} ({d['term_months']}T): {prev_rates[key]}% → {d['rate_pct']}%")
            elif key not in prev_rates:
                changes.append(f"{d['bank']} ({d['term_months']}T): mới vào top với {d['rate_pct']}%")
        print("- Lãi suất thay đổi: " + ("; ".join(changes) if changes else "không đổi so với kỳ trước"))

    # Lãi/lỗ danh mục
    print("\n## Lãi/lỗ danh mục")
    if PORT.exists():
        port = json.loads(PORT.read_text(encoding="utf-8"))
        total_pnl = 0.0
        have_any = False
        for ticker, pos in port.items():
            cost, qty = pos.get("avg_cost"), pos.get("quantity")
            price = get(cur, ticker.lower(), "close")
            if cost is None or qty is None:
                print(f"- {ticker}: chưa có giá vốn/số lượng trong data/portfolio.json")
                continue
            if price is None:
                print(f"- {ticker}: chưa có giá kỳ này để tính")
                continue
            pnl = (price - cost) * qty
            total_pnl += pnl
            have_any = True
            print(f"- {ticker}: giá {fmt(price, 0)} đ vs vốn {fmt(cost, 0)} đ × {fmt(qty, 0)} cp → "
                  f"{'LÃI' if pnl >= 0 else 'LỖ'} {fmt(abs(pnl), 0)} đ ({(price - cost) / cost * 100:+.2f}%)")
        if have_any:
            print(f"- TỔNG: {'LÃI' if total_pnl >= 0 else 'LỖ'} {fmt(abs(total_pnl), 0)} đ")
    else:
        print("- Chưa có data/portfolio.json")

    # Cờ rủi ro kỳ này
    flags = cur.get("risk_flags", {})
    if flags.get("arrest"):
        print(f"\n⚠️ CẢNH BÁO: {flags['arrest']}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("append", "report"):
        sys.exit(__doc__)
    if sys.argv[1] == "append":
        cmd_append(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        cmd_report()


if __name__ == "__main__":
    main()

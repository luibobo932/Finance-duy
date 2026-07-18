#!/usr/bin/env python3
"""Quản lý lịch sử số liệu bản tin đầu tư và phân tích xu hướng.

Cách dùng:
  python3 scripts/trend.py append '<json snapshot>'   # hoặc đọc từ stdin
  python3 scripts/trend.py report
"""
import json
import sys
from pathlib import Path

try:
    from .finance_data import DataValidationError, load_history as read_history, load_portfolio, safe_print, validate_snapshot
    from .decision_engine import source_fields, verified_risk_flags
except ImportError:  # Chạy trực tiếp: python scripts/trend.py
    from finance_data import DataValidationError, load_history as read_history, load_portfolio, safe_print, validate_snapshot
    from decision_engine import source_fields, verified_risk_flags

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "history.jsonl"
PORT = ROOT / "data" / "portfolio.local.json"

def load_history():
    return read_history(HIST)


def fmt(x, nd=2):
    if x is None:
        return "n/a"
    s = f"{x:,.{nd}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def cmd_append(arg):
    raw = arg if arg else sys.stdin.read()
    if not raw.strip():
        raise DataValidationError("không nhận được JSON snapshot")
    snap = validate_snapshot(json.loads(raw))
    hist = load_history()
    if any(h.get("date") == snap["date"] and h.get("ky") == snap["ky"] for h in hist):
        raise DataValidationError(
            f"đã có snapshot {snap['date']} kỳ {snap['ky']} — không ghi trùng"
        )
    HIST.parent.mkdir(parents=True, exist_ok=True)
    with HIST.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snap, ensure_ascii=False) + "\n")
    safe_print(f"Đã ghi snapshot {snap['date']} ({snap['ky']}) — tổng {len(hist) + 1} bản ghi")


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
    market_comparable = bool(
        prev
        and cur.get("market_date")
        and prev.get("market_date")
        and cur["market_date"] != prev["market_date"]
        and "market_date" in source_fields(cur)
        and "market_date" in source_fields(prev)
    )
    for name, path, unit, market_metric in [
        ("VN-Index", ("vnindex", "close"), "", True),
        ("VCB", ("vcb", "close"), " đ", True),
        ("CTD", ("ctd", "close"), " đ", True),
        ("Vàng SJC bán ra", ("gold", "sjc_sell"), " tr", False),
        ("Vàng thế giới", ("gold", "xauusd"), " $", False),
        ("Chênh lệch vàng VN–TG", ("gold", "premium_trieu"), " tr", False),
    ]:
        field = ".".join(path)
        history_verified = prev and field in source_fields(cur) and field in source_fields(prev)
        if market_metric and not market_comparable:
            print(f"- {name}: {fmt(get(cur, *path))}{unit} (không so kỳ trước: thiếu/không đổi market_date)")
        elif not history_verified:
            print(f"- {name}: {fmt(get(cur, *path))}{unit} (không so kỳ trước: thiếu nguồn theo field)")
        else:
            print(delta_line(name, get(cur, *path), get(prev, *path) if prev else None, unit))

    # Khối lượng đột biến: so KLGD kỳ này với bình quân các phiên chiều trước đó (tối đa 20)
    for ticker in ("vcb", "ctd"):
        vol = get(cur, ticker, "volume_million_shares")
        if cur.get("ky") != "chieu" or not cur.get("market_date") or f"{ticker}.volume_million_shares" not in source_fields(cur):
            print(f"- KLGD {ticker.upper()}: không tính ratio ở kỳ sáng hoặc khi thiếu market_date")
            continue
        by_market_date = {}
        for item in hist[:-1]:
            value = get(item, ticker, "volume_million_shares")
            if item.get("ky") == "chieu" and item.get("market_date") and value is not None and f"{ticker}.volume_million_shares" in source_fields(item) and "market_date" in source_fields(item):
                by_market_date[item["market_date"]] = value
        past = list(by_market_date.values())[-20:]
        if vol is None:
            continue
        if not past:
            print(f"- KLGD {ticker.upper()}: {fmt(vol)} triệu cp (chưa đủ lịch sử tính bình quân)")
            continue
        avg = sum(past) / len(past)
        ratio = vol / avg if avg else 0
        flag = " ⚠️ ĐỘT BIẾN — kiểm tra tin tức, thỏa thuận, giao dịch nội bộ" if ratio >= 1.5 else ""
        print(f"- KLGD {ticker.upper()}: {fmt(vol)} triệu cp = {ratio:.1f}× bình quân {len(past)} phiên{flag}")

    # Chuỗi khối ngoại: chỉ tính trên các kỳ "chieu" (số chốt phiên) để không đếm trùng
    flows = [(h["date"], h.get("foreign_net_ty")) for h in hist
             if h["ky"] == "chieu" and h.get("foreign_net_ty") is not None and "foreign_net_ty" in source_fields(h)]
    if flows:
        if flows[-1][1] == 0:
            print("- Khối ngoại: cân bằng trong phiên gần nhất")
            flows = []
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
    print("- Lãi suất thay đổi: xem decision_engine; trend không so các dòng raw chưa qua cổng sản phẩm")

    # Lãi/lỗ danh mục
    print("\n## Lãi/lỗ danh mục")
    if PORT.exists():
        port = load_portfolio(PORT)
        total_pnl = 0.0
        have_any = False
        for ticker, pos in port.items():
            cost, qty = pos.get("avg_cost"), pos.get("quantity")
            price = get(cur, ticker.lower(), "close")
            if f"{ticker.lower()}.close" not in source_fields(cur):
                print(f"- {ticker}: giá kỳ này chưa có nguồn đúng field để tính")
                continue
            if cost is None or qty is None:
                print(f"- {ticker}: chưa có giá vốn/số lượng trong data/portfolio.local.json")
                continue
            if price is None:
                print(f"- {ticker}: chưa có giá kỳ này để tính")
                continue
            if cost <= 0 or qty <= 0:
                print(f"- {ticker}: giá vốn và số lượng phải lớn hơn 0")
                continue
            pnl = (price - cost) * qty
            total_pnl += pnl
            have_any = True
            print(f"- {ticker}: giá {fmt(price, 0)} đ vs vốn {fmt(cost, 0)} đ × {fmt(qty, 0)} cp → "
                  f"{'LÃI' if pnl >= 0 else 'LỖ'} {fmt(abs(pnl), 0)} đ ({(price - cost) / cost * 100:+.2f}%)")
        if have_any:
            print(f"- TỔNG: {'LÃI' if total_pnl >= 0 else 'LỖ'} {fmt(abs(total_pnl), 0)} đ")
    else:
        print("- Chưa có data/portfolio.local.json")

    # Cờ rủi ro kỳ này
    flags = verified_risk_flags(cur)
    if flags.get("arrest"):
        print(f"\n⚠️ CẢNH BÁO: {flags['arrest']}")


def main():
    try:
        if len(sys.argv) < 2 or sys.argv[1] not in ("append", "report"):
            sys.exit(__doc__)
        if sys.argv[1] == "append":
            cmd_append(sys.argv[2] if len(sys.argv) > 2 else None)
        else:
            cmd_report()
    except (DataValidationError, json.JSONDecodeError, OSError) as exc:
        sys.exit(f"LỖI: {exc}")


if __name__ == "__main__":
    main()

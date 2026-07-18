#!/usr/bin/env python3
"""Engine chỉ báo phân tích kỹ thuật — tính RSI, MACD, MA, Bollinger từ chuỗi giá.

Đọc dữ liệu EOD từ data/eod/<MÃ>.csv (cột: date,open,high,low,close,volume — mới nhất ở cuối).
Codex hoặc người dùng bơm dữ liệu vào đó; script tự tính toàn bộ chỉ báo.

Cách dùng:
  python3 scripts/indicators.py CTD          # in bảng chỉ báo mã CTD
  python3 scripts/indicators.py VCB --json    # xuất JSON để nhúng vào bản tin
  python3 scripts/indicators.py --file path.csv
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EOD_DIR = ROOT / "data" / "eod"


def load_closes(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    "date": r["date"].strip(),
                    "high": float(r["high"]), "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r.get("volume") or 0),
                })
            except (ValueError, KeyError):
                continue
    return rows


def sma(vals, n):
    return sum(vals[-n:]) / n if len(vals) >= n else None


def ema_series(vals, n):
    if len(vals) < n:
        return []
    k = 2 / (n + 1)
    out = [sum(vals[:n]) / n]
    for v in vals[n:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(closes, n=14):
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


def macd(closes, fast=12, slow=26, signal=9):
    if len(closes) < slow + signal:
        return None
    ef = ema_series(closes, fast)
    es = ema_series(closes, slow)
    # căn chỉnh độ dài
    ef = ef[-len(es):]
    macd_line = [a - b for a, b in zip(ef, es)]
    sig = ema_series(macd_line, signal)
    if not sig:
        return None
    m, s = macd_line[-1], sig[-1]
    return {"macd": round(m, 2), "signal": round(s, 2), "hist": round(m - s, 2)}


def bollinger(closes, n=20, k=2):
    if len(closes) < n:
        return None
    window = closes[-n:]
    mid = sum(window) / n
    var = sum((x - mid) ** 2 for x in window) / n
    sd = var ** 0.5
    return {"mid": round(mid, 1), "upper": round(mid + k * sd, 1), "lower": round(mid - k * sd, 1)}


def analyze(path):
    rows = load_closes(path)
    closes = [r["close"] for r in rows]
    vols = [r["volume"] for r in rows if r["volume"]]
    name = Path(path).stem
    n = len(closes)
    out = {"symbol": name, "sessions": n, "last_close": closes[-1] if closes else None,
           "last_date": rows[-1]["date"] if rows else None,
           "rsi14": rsi(closes), "macd": macd(closes),
           "sma20": round(sma(closes, 20), 1) if sma(closes, 20) else None,
           "sma50": round(sma(closes, 50), 1) if sma(closes, 50) else None,
           "sma200": round(sma(closes, 200), 1) if sma(closes, 200) else None,
           "bollinger": bollinger(closes),
           "vol_vs_bq20": round(vols[-1] / (sum(vols[-21:-1]) / 20), 2) if len(vols) >= 21 else None,
           "needed_for_full": max(0, 200 - n)}
    return out


def signal_read(a):
    """Diễn giải chỉ báo thành nhận định."""
    notes = []
    r = a.get("rsi14")
    if r is not None:
        if r >= 70:
            notes.append(f"RSI {r}: quá mua — cẩn trọng nhịp chỉnh")
        elif r <= 30:
            notes.append(f"RSI {r}: quá bán — có thể hồi kỹ thuật")
        else:
            notes.append(f"RSI {r}: trung tính")
    m = a.get("macd")
    if m:
        notes.append(f"MACD hist {m['hist']:+}: {'động lượng tăng' if m['hist'] > 0 else 'động lượng giảm'}")
    c, s20, s50 = a.get("last_close"), a.get("sma20"), a.get("sma50")
    if c and s20:
        notes.append(f"Giá {'trên' if c > s20 else 'dưới'} MA20 ({s20})")
    if c and s50:
        notes.append(f"Giá {'trên' if c > s50 else 'dưới'} MA50 ({s50})")
    b = a.get("bollinger")
    if b and c:
        if c >= b["upper"]:
            notes.append("Chạm dải Bollinger trên — căng phía tăng")
        elif c <= b["lower"]:
            notes.append("Chạm dải Bollinger dưới — căng phía giảm")
    return notes


def main():
    args = sys.argv[1:]
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    if "--file" in args:
        path = args[args.index("--file") + 1]
    elif args:
        path = EOD_DIR / f"{args[0].upper()}.csv"
    else:
        sys.exit(__doc__)
    if not Path(path).exists():
        sys.exit(f"Chưa có dữ liệu EOD: {path}\nBơm CSV (date,open,high,low,close,volume) vào data/eod/ để bật chỉ báo.")
    a = analyze(path)
    if as_json:
        print(json.dumps(a, ensure_ascii=False))
        return
    print(f"=== CHỈ BÁO KỸ THUẬT: {a['symbol']} ({a['sessions']} phiên, tới {a['last_date']}) ===")
    print(f"Giá đóng cửa: {a['last_close']}")
    for k in ("rsi14", "sma20", "sma50", "sma200", "vol_vs_bq20"):
        print(f"  {k}: {a[k]}")
    print(f"  MACD: {a['macd']}")
    print(f"  Bollinger: {a['bollinger']}")
    if a["needed_for_full"]:
        print(f"  (cần thêm ~{a['needed_for_full']} phiên để đủ MA200)")
    print("Nhận định:")
    for note in signal_read(a):
        print(f"  • {note}")


if __name__ == "__main__":
    main()

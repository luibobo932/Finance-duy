#!/usr/bin/env python3
"""Phân tích khớp lệnh chi tiết để phát hiện dấu hiệu gom hàng nội bộ/tổ chức.

Heuristic chính (theo chủ danh mục): lệnh khối lượng LỚN + TRÒN SỐ xuất hiện
LIÊN TỤC là dấu hiệu robot gom hàng của tay to — nhỏ lẻ đặt lệnh số lẻ ngẫu nhiên.

Cách dùng:
  python3 scripts/tick.py fetch CTD 2026-07-17     # tải nến 1 phút từ API DNSE (cần network mở)
  python3 scripts/tick.py csv <file.csv>           # phân tích file khớp lệnh xuất từ app
                                                   # (FireAnt/SSI/Vietstock: cột time,price,volume)
"""
import csv as csvmod
import io
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

VN = timezone(timedelta(hours=7))
ROUND_LOTS = (10_000, 20_000, 50_000, 100_000, 200_000, 500_000)
BIG_ORDER = 10_000  # cp — ngưỡng coi là "lệnh lớn"


def analyze(rows, label):
    """rows: list of (time_str, price, volume) — từng lệnh khớp hoặc nến 1 phút."""
    if not rows:
        sys.exit("Không có dữ liệu để phân tích.")
    total_vol = sum(v for _, _, v in rows)
    big = [(t, p, v) for t, p, v in rows if v >= BIG_ORDER]
    round_big = [(t, p, v) for t, p, v in big if any(v == lot or v % lot == 0 for lot in ROUND_LOTS)]

    # Đếm tần suất từng cỡ lệnh tròn — lặp lại nhiều lần là dấu hiệu robot gom
    freq = {}
    for _, _, v in round_big:
        freq[v] = freq.get(v, 0) + 1
    repeated = sorted(((v, n) for v, n in freq.items() if n >= 3), key=lambda x: -x[1])

    print(f"=== PHÂN TÍCH KHỚP LỆNH: {label} ===")
    print(f"- Tổng: {len(rows)} bản ghi, khối lượng {total_vol:,.0f} cp")
    print(f"- Lệnh lớn (≥{BIG_ORDER:,} cp): {len(big)} lệnh, "
          f"chiếm {sum(v for _, _, v in big) / total_vol * 100:.1f}% tổng khối lượng")
    print(f"- Trong đó TRÒN SỐ: {len(round_big)} lệnh")
    if repeated:
        print("\n⚠️ NGHI VẤN GOM HÀNG CÓ CHỦ ĐÍCH — cỡ lệnh tròn số lặp ≥3 lần:")
        for v, n in repeated:
            times = [t for t, _, vv in round_big if vv == v]
            print(f"  • {v:,.0f} cp × {n} lần ({times[0]} → {times[-1]})")
        print("  → Đối chiếu giá: nếu giá KHÔNG giảm khi các lệnh này xuất hiện ở vùng hỗ trợ"
              " = tích lũy (Wyckoff); cân nhắc điểm vào theo vùng giá đó.")
    else:
        print("\n- Không thấy chuỗi lệnh tròn số lặp lại bất thường.")
    print("\nTop 10 bản ghi khối lượng lớn nhất:")
    for t, p, v in sorted(rows, key=lambda x: -x[2])[:10]:
        mark = " ◄ tròn số" if any(v == lot or (v >= BIG_ORDER and v % lot == 0) for lot in ROUND_LOTS) else ""
        print(f"  {t} | giá {p:,.0f} | {v:,.0f} cp{mark}")


def cmd_fetch(symbol, date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=VN)
    frm = int(d.timestamp())
    to = int((d + timedelta(days=1)).timestamp())
    url = (f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"
           f"?from={frm}&to={to}&symbol={symbol}&resolution=1")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception as e:
        sys.exit(f"Không tải được dữ liệu ({e}).\n"
                 "Môi trường có thể đang chặn API — mở network policy cho "
                 "services.entrade.com.vn, hoặc dùng chế độ csv với file xuất từ app chứng khoán.")
    rows = [(datetime.fromtimestamp(t, VN).strftime("%H:%M"), c, v)
            for t, c, v in zip(data.get("t", []), data.get("c", []), data.get("v", []))]
    analyze(rows, f"{symbol} {date_str} (nến 1 phút — gần đúng, không phải từng lệnh)")


def cmd_csv(path):
    text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    rows = []
    for r in csvmod.reader(io.StringIO(text)):
        if len(r) < 3:
            continue
        try:
            rows.append((r[0].strip(), float(r[1].replace(",", "")), float(r[2].replace(",", ""))))
        except ValueError:
            continue  # bỏ dòng tiêu đề
    analyze(rows, f"file {path} (khớp lệnh từng dòng)")


def main():
    if len(sys.argv) >= 4 and sys.argv[1] == "fetch":
        cmd_fetch(sys.argv[2].upper(), sys.argv[3])
    elif len(sys.argv) >= 3 and sys.argv[1] == "csv":
        cmd_csv(sys.argv[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()

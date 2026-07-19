#!/usr/bin/env python3
"""CLI mỏng cho analytics/anomaly_detector.py — phát hiện khớp lệnh bất
thường (lệnh lớn tròn số lặp lại) để cân nhắc điểm vào giá.

Logic đầy đủ nằm trong analytics/anomaly_detector.py — file này chỉ nạp dữ
liệu (từ API DNSE hoặc file khớp lệnh CSV) rồi in báo cáo.

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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.anomaly_detector import detect, top_volume_records  # noqa: E402

VN = timezone(timedelta(hours=7))


def report(ticker: str, rows: list, label: str) -> None:
    if not rows:
        sys.exit("Không có dữ liệu để phân tích.")
    result = detect(ticker, rows)
    print(f"=== PHÂN TÍCH KHỚP LỆNH: {label} ===")
    print(f"Alert level: {result['alert_level']}/5 | Loại: {result['anomaly_type']}")
    for e in result["evidence"]:
        print(f"  • {e}")
    print(f"Kết luận: {result['conclusion']}")
    print("\nTop 10 bản ghi khối lượng lớn nhất:")
    for r in top_volume_records(rows):
        mark = " ◄ tròn số" if r["is_round_lot"] else ""
        print(f"  {r['time']} | giá {r['price']:,.0f} | {r['volume']:,.0f} cp{mark}")
    if result["evidence"] and "repeated_round_lot_orders" in result.get("anomaly_types", []):
        print("\n→ Đối chiếu giá: nếu giá KHÔNG giảm khi các lệnh này xuất hiện ở vùng hỗ trợ"
              " = tích lũy (Wyckoff); cân nhắc điểm vào theo vùng giá đó.")
    print(json.dumps(result, ensure_ascii=False))


def cmd_fetch(symbol: str, date_str: str) -> None:
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
    report(symbol, rows, f"{symbol} {date_str} (nến 1 phút — gần đúng, không phải từng lệnh)")


def cmd_csv(path: str) -> None:
    text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    rows = []
    ticker = Path(path).stem.upper() if path != "-" else "STDIN"
    for r in csvmod.reader(io.StringIO(text)):
        if len(r) < 3:
            continue
        try:
            rows.append((r[0].strip(), float(r[1].replace(",", "")), float(r[2].replace(",", ""))))
        except ValueError:
            continue  # bỏ dòng tiêu đề
    report(ticker, rows, f"file {path} (khớp lệnh từng dòng)")


def main():
    if len(sys.argv) >= 4 and sys.argv[1] == "fetch":
        cmd_fetch(sys.argv[2].upper(), sys.argv[3])
    elif len(sys.argv) >= 3 and sys.argv[1] == "csv":
        cmd_csv(sys.argv[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()

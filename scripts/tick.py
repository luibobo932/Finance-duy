#!/usr/bin/env python3
"""Phát hiện cụm khối lượng tròn số bất thường trong dữ liệu tick thật.

Heuristic chỉ dùng để sàng lọc. Nó không chứng minh có tổ chức, người nội bộ hay
chiều mua/bán; muốn dùng trong quyết định phải đối chiếu side và nguồn độc lập.

Cách dùng:
  python3 scripts/tick.py fetch CTD 2026-07-17     # tải nến 1 phút từ API DNSE (cần network mở)
  python3 scripts/tick.py csv <file.csv>           # phân tích file khớp lệnh xuất từ app
                                                   # (FireAnt/SSI/Vietstock: cột time,price,volume)
"""
import csv as csvmod
import io
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

VN = timezone(timedelta(hours=7))
ROUND_LOTS = (10_000, 20_000, 50_000, 100_000, 200_000, 500_000)
BIG_ORDER = 10_000  # cp — ngưỡng coi là "lệnh lớn"


def parse_number(value):
    """Đọc cả 10,000 và 10.000 nhưng vẫn giữ số thập phân 73.8."""
    text = value.strip().replace(" ", "")
    if not text:
        raise ValueError("số rỗng")
    if re.fullmatch(r"[-+]?\d{1,3}([.,]\d{3})+", text):
        return float(text.replace(",", "").replace(".", ""))
    if "," in text and "." in text:
        # Dấu xuất hiện cuối cùng được xem là dấu thập phân.
        decimal = "," if text.rfind(",") > text.rfind(".") else "."
        thousands = "." if decimal == "," else ","
        text = text.replace(thousands, "").replace(decimal, ".")
    elif "," in text:
        text = text.replace(",", ".")
    return float(text)


def analyze(rows, label, data_kind="tick"):
    """rows: list of (time_str, price, volume) — từng lệnh khớp hoặc nến 1 phút."""
    if not rows:
        raise ValueError("không có dữ liệu hợp lệ để phân tích")
    if any(p < 0 or v <= 0 for _, p, v in rows):
        raise ValueError("giá phải >= 0 và khối lượng phải > 0")
    total_vol = sum(v for _, _, v in rows)
    if data_kind not in ("tick", "candle"):
        raise ValueError("data_kind phải là tick hoặc candle")
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
    if data_kind == "candle":
        average = total_vol / len(rows)
        spikes = [(t, p, v) for t, p, v in rows if v >= average * 2]
        print(f"- Nến 1 phút có volume ≥2× bình quân: {len(spikes)}")
        print("\n- Dữ liệu nến KHÔNG phải từng lệnh: không chạy heuristic lệnh tròn số/gom hàng.")
        print("\nTop 10 nến 1 phút có khối lượng lớn nhất:")
        for t, p, v in sorted(rows, key=lambda x: -x[2])[:10]:
            print(f"  {t} | giá đóng {p:,.0f} | {v:,.0f} cp")
        return
    print(f"- Trong đó TRÒN SỐ: {len(round_big)} lệnh")
    if repeated:
        print("\n⚠️ PHÁT HIỆN CỤM LỆNH TRÒN SỐ LẶP ≥3 LẦN:")
        for v, n in repeated:
            times = [t for t, _, vv in round_big if vv == v]
            print(f"  • {v:,.0f} cp × {n} lần ({times[0]} → {times[-1]})")
        print("  → Đây chỉ là tín hiệu bất thường. Cần đối chiếu chiều mua/bán, vùng giá,"
              " giao dịch thỏa thuận và tin công bố trước khi kết luận có gom hàng.")
    else:
        print("\n- Không thấy chuỗi lệnh tròn số lặp lại bất thường.")
    print("\nTop 10 bản ghi khối lượng lớn nhất:")
    for t, p, v in sorted(rows, key=lambda x: -x[2])[:10]:
        mark = " ◄ tròn số" if any(v == lot or (v >= BIG_ORDER and v % lot == 0) for lot in ROUND_LOTS) else ""
        print(f"  {t} | giá {p:,.0f} | {v:,.0f} cp{mark}")


def cmd_fetch(symbol, date_str):
    if not symbol.isalnum() or len(symbol) > 10:
        raise ValueError("mã chứng khoán không hợp lệ")
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=VN)
    frm = int(d.timestamp())
    to = int((d + timedelta(days=1)).timestamp())
    query = urlencode({"from": frm, "to": to, "symbol": symbol, "resolution": 1})
    url = f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception as e:
        raise RuntimeError(
            f"không tải được dữ liệu ({e}). Mở kết nối services.entrade.com.vn "
            "hoặc dùng chế độ csv với file xuất từ app chứng khoán"
        ) from None
    if not isinstance(data, dict):
        raise ValueError("API trả về dữ liệu không đúng định dạng")
    rows = [
        (datetime.fromtimestamp(t, VN).strftime("%H:%M"), float(c), float(v))
        for t, c, v in zip(data.get("t", []), data.get("c", []), data.get("v", []))
    ]
    analyze(rows, f"{symbol} {date_str} (nến 1 phút)", data_kind="candle")


def cmd_csv(path):
    if path == "-":
        text = sys.stdin.read()
    else:
        text = Path(path).read_text(encoding="utf-8-sig")
    try:
        dialect = csvmod.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csvmod.Error:
        dialect = csvmod.excel
    rows = []
    for r in csvmod.reader(io.StringIO(text), dialect=dialect):
        if len(r) < 3:
            continue
        try:
            rows.append((r[0].strip(), parse_number(r[1]), parse_number(r[2])))
        except ValueError:
            continue  # bỏ dòng tiêu đề
    analyze(rows, f"file {path} (khớp lệnh từng dòng)")


def main():
    try:
        if len(sys.argv) == 4 and sys.argv[1] == "fetch":
            cmd_fetch(sys.argv[2].upper(), sys.argv[3])
        elif len(sys.argv) == 3 and sys.argv[1] == "csv":
            cmd_csv(sys.argv[2])
        else:
            sys.exit(__doc__)
    except (OSError, ValueError, RuntimeError) as exc:
        sys.exit(f"LỖI: {exc}")


if __name__ == "__main__":
    main()

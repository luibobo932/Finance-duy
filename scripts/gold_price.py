#!/usr/bin/env python3
"""CLI mỏng cho gold/xuan_trieu_model.py — ước tính giá vàng nhẫn tại tiệm
của chủ dự án từ giá vàng THẾ GIỚI real-time.

Logic đầy đủ (công thức quy đổi, hiệu chuẩn, MAE) nằm trong gold/ — file này
chỉ là giao diện dòng lệnh, giữ để tương thích ngược với các routine đã gọi
`python3 scripts/gold_price.py`.

Cách dùng:
  python3 scripts/gold_price.py                 # dùng XAU + tỷ giá mới nhất trong history.jsonl
  python3 scripts/gold_price.py 4050 26500       # truyền tay XAU, tỷ giá
  python3 scripts/gold_price.py --json
"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gold.xuan_trieu_model import estimate  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv
    xau = float(args[0]) if len(args) >= 1 else None
    fx = float(args[1]) if len(args) >= 2 else None
    r = estimate(xau, fx)
    if not r:
        sys.exit("Thiếu XAU/USD hoặc tỷ giá (truyền tay hoặc ghi vào history.jsonl trước).")
    if as_json:
        # Giữ tên khóa CŨ để tương thích ngược với mọi nơi từng đọc JSON này,
        # đồng thời bổ sung field mới (sample_size, confidence).
        out = {
            "xauusd": r.xau_usd, "fx": r.usd_vnd,
            "world_per_luong": r.world_per_tael_trieu,
            "shop_buy": r.shop_buy_trieu, "shop_sell": r.shop_sell_trieu,
            "k_buy": r.k_buy, "k_sell": r.k_sell,
            "cal_date": r.calibration_date, "shop": r.shop_name,
            "sample_size": r.sample_size, "confidence": r.confidence,
        }
        print(json.dumps(out, ensure_ascii=False))
        return
    print(f"=== ƯỚC TÍNH GIÁ VÀNG NHẪN TIỆM (hiệu chuẩn {r.shop_name} {r.calibration_date}) ===")
    print(f"Vàng thế giới: {r.xau_usd} $/oz · tỷ giá {r.usd_vnd:,.0f} → {r.world_per_tael_trieu} tr/lượng")
    print(f"  Giá tiệm MUA (bạn bán được): ~{r.shop_buy_trieu} tr/lượng  [k={r.k_buy}]")
    print(f"  Giá tiệm BÁN (mua vào phải trả): ~{r.shop_sell_trieu} tr/lượng  [k={r.k_sell}]")
    print(f"  Độ tin cậy mô hình: {r.confidence} (dựa trên {r.sample_size} điểm hiệu chuẩn thực tế)")
    print("  (Ước tính theo mô hình — gửi ảnh bảng giá mới khi lệch nhiều để hiệu chuẩn lại.)")


if __name__ == "__main__":
    main()

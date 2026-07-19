#!/usr/bin/env python3
"""Ước tính giá vàng nhẫn tại tiệm của chủ danh mục từ giá vàng THẾ GIỚI real-time.

Công thức:
  world_per_luong (triệu đồng) = XAU/USD × tỷ_giá_USD × (37,5/31,1035) / 1e6
  giá_tiệm_mua  = world_per_luong × k_buy      (k_buy  = shop_buy_cal / world_cal)
  giá_tiệm_bán  = world_per_luong × k_sell     (k_sell = shop_sell_cal / world_cal)
Các hệ số k lấy từ điểm hiệu chuẩn trong data/gold_model.json (1 ảnh bảng giá tiệm).

Cách dùng:
  python3 scripts/gold_price.py                 # dùng XAU + tỷ giá mới nhất trong history.jsonl
  python3 scripts/gold_price.py 4050 26500       # truyền tay XAU, tỷ giá
  python3 scripts/gold_price.py --json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "data" / "gold_model.json"
HIST = ROOT / "data" / "history.jsonl"


def latest_xau_fx():
    if not HIST.exists():
        return None, None
    lines = [json.loads(l) for l in HIST.read_text(encoding="utf-8").splitlines() if l.strip()]
    xau = fx = None
    for s in reversed(lines):
        if xau is None:
            xau = (s.get("gold") or {}).get("xauusd")
        if fx is None:
            fx = s.get("fx_vcb_sell")
        if xau and fx:
            break
    return xau, fx


def world_per_luong(xau, fx, lpo):
    return xau * fx * lpo / 1_000_000


def estimate(xau=None, fx=None):
    m = json.loads(MODEL.read_text(encoding="utf-8"))
    lpo = m["luong_per_oz"]
    cal = m["calibration"]
    if xau is None or fx is None:
        lx, lfx = latest_xau_fx()
        xau = xau or lx
        fx = fx or lfx
    if not xau or not fx:
        return None
    world_cal = cal.get("world_per_luong_trieu") or world_per_luong(cal["xauusd"], cal["fx_vcb_sell"], lpo)
    k_buy = cal["shop_buy_trieu"] / world_cal
    k_sell = cal["shop_sell_trieu"] / world_cal
    world_now = world_per_luong(xau, fx, lpo)
    return {"xauusd": xau, "fx": fx,
            "world_per_luong": round(world_now, 2),
            "shop_buy": round(world_now * k_buy, 2),
            "shop_sell": round(world_now * k_sell, 2),
            "k_buy": round(k_buy, 5), "k_sell": round(k_sell, 5),
            "cal_date": cal["date"], "shop": cal["shop_name"]}


def main():
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv
    xau = float(args[0]) if len(args) >= 1 else None
    fx = float(args[1]) if len(args) >= 2 else None
    r = estimate(xau, fx)
    if not r:
        sys.exit("Thiếu XAU/USD hoặc tỷ giá (truyền tay hoặc ghi vào history.jsonl trước).")
    if as_json:
        print(json.dumps(r, ensure_ascii=False))
        return
    print(f"=== ƯỚC TÍNH GIÁ VÀNG NHẪN TIỆM (hiệu chuẩn {r['shop']} {r['cal_date']}) ===")
    print(f"Vàng thế giới: {r['xauusd']} $/oz · tỷ giá {r['fx']:,.0f} → {r['world_per_luong']} tr/lượng")
    print(f"  Giá tiệm MUA (bạn bán được): ~{r['shop_buy']} tr/lượng  [k={r['k_buy']}]")
    print(f"  Giá tiệm BÁN (mua vào phải trả): ~{r['shop_sell']} tr/lượng  [k={r['k_sell']}]")
    print("  (Ước tính theo mô hình — gửi ảnh bảng giá mới khi lệch nhiều để hiệu chuẩn lại.)")


if __name__ == "__main__":
    main()

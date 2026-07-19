#!/usr/bin/env python3
"""Tính tài sản ròng và phân bổ danh mục từ data/assets.json + giá vàng mới nhất.

Định giá vàng theo GIÁ MUA VÀO (số tiền thực nhận nếu bán) từ snapshot cuối trong history.jsonl.

Cách dùng:
  python3 scripts/networth.py            # bảng tài sản + phân bổ + cảnh báo tập trung
  python3 scripts/networth.py --json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "data" / "assets.json"
HIST = ROOT / "data" / "history.jsonl"


def latest_gold_buy():
    if not HIST.exists():
        return None
    lines = [json.loads(l) for l in HIST.read_text(encoding="utf-8").splitlines() if l.strip()]
    for s in reversed(lines):
        g = s.get("gold", {})
        key = "sjc_buy"  # giá mua vào SJC = tiền nhận khi bán
        if g.get(key):
            return g[key], s["date"]
    return None


def compute():
    a = json.loads(ASSETS.read_text(encoding="utf-8"))
    price = None
    pdate = None
    src = ""
    # 1) Ưu tiên ước tính ĐỘNG theo giá vàng thế giới real-time (data/gold_model.json)
    model = ROOT / "data" / "gold_model.json"
    if model.exists() and a.get("gold_type") == "nhan":
        try:
            from gold_price import estimate
        except ImportError:
            sys.path.insert(0, str(ROOT / "scripts"))
            from gold_price import estimate
        est = estimate()
        if est:
            price = est["shop_buy"]
            src = f"ước tính động theo XAU {est['xauusd']}$ (hiệu chuẩn {est['shop']} {est['cal_date']})"
            pdate = "real-time"
    # 2) Fallback: giá tiệm trả cố định trong assets.json
    if price is None and a.get("gold_buy_price_trieu"):
        price = a["gold_buy_price_trieu"]
        src = "giá tiệm cố định trong assets.json"
    # 3) Fallback cuối: SJC mua vào trừ chiết khấu nhẫn
    if price is None:
        gb = latest_gold_buy()
        sjc_buy, pdate = (gb if gb else (None, None))
        if sjc_buy is not None:
            price = sjc_buy - (a.get("gold_discount_vs_sjc_trieu", 0) if a.get("gold_type") == "nhan" else 0)
            src = f"SJC mua vào −{a.get('gold_discount_vs_sjc_trieu',0)}tr"
    a["_gold_src"] = src
    gold_val = (a["gold_luong"] * price) if price else None
    bank = a.get("bank_vnd_trieu", 0)
    cash = a.get("cash_vnd_trieu", 0)
    stock_val = sum((p.get("last_price", 0) or 0) * (p.get("quantity", 0) or 0) / 1000
                    for p in a.get("stocks", {}).values())
    parts = {"Vàng": gold_val, "Tiết kiệm ngân hàng": bank, "Tiền mặt": cash}
    if stock_val:
        parts["Cổ phiếu"] = stock_val
    total = sum(v for v in parts.values() if v)
    return a, parts, total, price, pdate


def main():
    a, parts, total, price, pdate = compute()
    if "--json" in sys.argv:
        print(json.dumps({"parts": parts, "total": total, "gold_price": price}, ensure_ascii=False))
        return
    print(f"=== TÀI SẢN RÒNG (cập nhật assets {a['updated']}) ===")
    if price:
        print(f"Vàng: {a['gold_luong']} cây {a['gold_type']} × {price:,.1f} tr/lượng ({a.get('_gold_src','')})")
    for name, val in parts.items():
        if val:
            print(f"  {name:<22}{val:>12,.1f} tr   {val/total*100:>5.1f}%")
    print(f"  {'TỔNG':<22}{total:>12,.1f} tr  (≈ {total/1000:.2f} tỷ)")
    # Cảnh báo tập trung
    gold_pct = (parts.get("Vàng") or 0) / total * 100 if total else 0
    print()
    if gold_pct >= 60:
        print(f"⚠️ TẬP TRUNG CAO: vàng chiếm {gold_pct:.0f}% tài sản — rủi ro lớn nếu vàng điều chỉnh.")
        print("   Nguyên tắc phân bổ: không nên để 1 loại tài sản >50-60%. Cân nhắc chốt bớt khi giá cao,")
        print("   đặc biệt khi chênh lệch VN–thế giới đang rộng (bán trong nước được lợi phần premium).")
    liquid = (parts.get("Tiết kiệm ngân hàng") or 0) + (parts.get("Tiền mặt") or 0)
    print(f"   Thanh khoản (tiết kiệm+mặt): {liquid:,.0f} tr = {liquid/total*100:.0f}% — quỹ dự phòng.")


if __name__ == "__main__":
    main()

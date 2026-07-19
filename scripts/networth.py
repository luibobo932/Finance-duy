#!/usr/bin/env python3
"""Tính tài sản ròng và phân bổ danh mục.

Số lượng tài sản (vàng/tiết kiệm/mặt/cổ phiếu) đọc từ config/portfolio.yaml
(nguồn sự thật duy nhất — sửa ở đó, không sửa số trong file .py này).
Ngưỡng cảnh báo tập trung đọc từ config/risk_limits.yaml.
Giá vàng lấy động từ giá thế giới real-time (data/gold_model.json), fallback
theo thứ tự mô tả trong compute().

Cách dùng:
  python3 scripts/networth.py            # bảng tài sản + phân bổ + cảnh báo tập trung
  python3 scripts/networth.py --json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from portfolio.loader import load_portfolio, load_risk_limits  # noqa: E402

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
    port = load_portfolio()
    limits = load_risk_limits()
    meta = json.loads(ASSETS.read_text(encoding="utf-8")) if ASSETS.exists() else {}

    price = None
    src = ""
    # 1) Ưu tiên ước tính ĐỘNG theo giá vàng thế giới real-time (data/gold_model.json)
    model = ROOT / "data" / "gold_model.json"
    if model.exists() and meta.get("gold_type") == "nhan":
        try:
            from gold_price import estimate
        except ImportError:
            sys.path.insert(0, str(ROOT / "scripts"))
            from gold_price import estimate
        est = estimate()
        if est:
            price = est["shop_buy"]
            src = f"ước tính động theo XAU {est['xauusd']}$ (hiệu chuẩn {est['shop']} {est['cal_date']})"
    # 2) Fallback: giá tiệm trả cố định trong data/assets.json
    if price is None and meta.get("gold_buy_price_trieu"):
        price = meta["gold_buy_price_trieu"]
        src = "giá tiệm cố định trong data/assets.json"
    # 3) Fallback cuối: SJC mua vào trừ chiết khấu nhẫn
    if price is None:
        gb = latest_gold_buy()
        sjc_buy = gb[0] if gb else None
        if sjc_buy is not None:
            discount = meta.get("gold_discount_vs_sjc_trieu", 0) if meta.get("gold_type") == "nhan" else 0
            price = sjc_buy - discount
            src = f"SJC mua vào −{discount}tr"

    gold_val = (port.gold_quantity_tael * price) if price else None
    bank = port.savings_principal_vnd / 1_000_000  # đổi sang triệu đồng
    cash = port.cash_amount_vnd / 1_000_000
    stock_val = port.stock_market_value_vnd / 1_000_000

    parts = {"Vàng": gold_val, "Tiết kiệm ngân hàng": bank, "Tiền mặt": cash}
    if stock_val:
        parts["Cổ phiếu"] = stock_val
    total = sum(v for v in parts.values() if v)
    return port, limits, meta, parts, total, price, src


def main():
    port, limits, meta, parts, total, price, src = compute()
    if "--json" in sys.argv:
        print(json.dumps({"parts": parts, "total": total, "gold_price": price}, ensure_ascii=False))
        return
    print(f"=== TÀI SẢN RÒNG (config/portfolio.yaml cập nhật {port.updated}) ===")
    if price:
        print(f"Vàng: {port.gold_quantity_tael} cây {meta.get('gold_type','?')} × {price:,.1f} tr/lượng ({src})")
    for name, val in parts.items():
        if val:
            print(f"  {name:<22}{val:>12,.1f} tr   {val/total*100:>5.1f}%")
    print(f"  {'TỔNG':<22}{total:>12,.1f} tr  (≈ {total/1000:.2f} tỷ)")

    gold_pct = (parts.get("Vàng") or 0) / total if total else 0
    warning = limits.get("gold_warning", 0.60)
    critical = limits.get("gold_critical", 0.70)
    print()
    if gold_pct >= critical:
        print(f"🔴 TẬP TRUNG NGHIÊM TRỌNG: vàng chiếm {gold_pct*100:.0f}% (>= ngưỡng critical {critical*100:.0f}%).")
        print("   Theo config/risk_limits.yaml: KHÔNG nên mua thêm vàng ở mức tập trung này.")
    elif gold_pct >= warning:
        print(f"⚠️ TẬP TRUNG CAO: vàng chiếm {gold_pct*100:.0f}% (>= ngưỡng warning {warning*100:.0f}%).")
        print("   Nguyên tắc phân bổ: không nên để 1 loại tài sản vượt ngưỡng warning. Cân nhắc chốt bớt khi giá cao.")

    min_buffer = limits.get("minimum_cash_buffer_vnd", 0) / 1_000_000
    liquid = (parts.get("Tiết kiệm ngân hàng") or 0) + (parts.get("Tiền mặt") or 0)
    print(f"   Thanh khoản (tiết kiệm+mặt): {liquid:,.0f} tr = {liquid/total*100:.0f}% tổng tài sản"
          f" (quỹ dự phòng tối thiểu theo cấu hình: {min_buffer:,.0f} tr).")
    if (parts.get("Tiền mặt") or 0) * 1_000_000 < limits.get("minimum_cash_buffer_vnd", 0):
        print(f"   ⚠️ Tiền mặt hiện dưới mức tối thiểu cấu hình ({min_buffer:,.0f} tr).")


if __name__ == "__main__":
    main()

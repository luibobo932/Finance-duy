#!/usr/bin/env python3
"""Kế hoạch giảm tỷ trọng vàng — bán bao nhiêu, về đâu, lãi thêm bao nhiêu.

Trả lời 3 câu mà khuyến nghị "CHỐT BỚT" bỏ trống suốt 14 kỳ: bán bao nhiêu
lượng, tỷ trọng về đâu, tiền đi đâu và được thêm bao nhiêu lãi.

Cách dùng:
  python3 scripts/rebalance_plan.py             # 3 mốc mục tiêu để so sánh
  python3 scripts/rebalance_plan.py --target 72 # 1 mốc cụ thể
  python3 scripts/rebalance_plan.py --json      # để nhúng vào bản tin/dashboard
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from decision.rebalance import plan  # noqa: E402
from deposits.ranking import load_normalized, rank  # noqa: E402
from gold.xuan_trieu_model import estimate as gold_estimate  # noqa: E402
from portfolio.loader import load_portfolio, load_risk_limits  # noqa: E402


def _vi(value: float, decimals: int = 1) -> str:
    return f"{value:,.{decimals}f}".translate(str.maketrans({",": ".", ".": ","}))


def build() -> tuple:
    port = load_portfolio()
    limits = load_risk_limits()
    est = gold_estimate()
    if not est:
        sys.exit("Chưa định giá được vàng (thiếu XAU/USD hoặc tỷ giá trong data/history.jsonl).")

    rates = load_normalized()
    ranked = rank(rates) if rates else []
    as_of = max((r.get("updated_at") or "" for r in
                 [{"updated_at": x.updated_at} for x in rates]), default=None) if rates else None

    targets = None
    if "--target" in sys.argv:
        idx = sys.argv.index("--target")
        targets = [float(sys.argv[idx + 1])]

    p = plan(
        gold_tael=port.gold_quantity_tael,
        sell_price_trieu=est.shop_buy_trieu,
        buy_price_trieu=est.shop_sell_trieu,
        savings_trieu=port.savings_principal_vnd / 1_000_000,
        cash_trieu=port.cash_amount_vnd / 1_000_000,
        limits=limits, ranked_rates=ranked, rate_as_of=as_of, targets_pct=targets,
    )
    return p, est


def main() -> None:
    p, est = build()
    if "--json" in sys.argv[1:]:
        print(json.dumps(asdict(p), ensure_ascii=False, default=str))
        return

    print("=== KẾ HOẠCH GIẢM TỶ TRỌNG VÀNG ===\n")
    print(f"Hiện tại: {_vi(p.gold_tael)} lượng × {_vi(p.gold_price_sell_trieu, 2)} tr "
          f"(giá tiệm MUA vào) = {_vi(p.gold_now_trieu)} tr")
    print(f"          tiết kiệm {_vi(p.savings_trieu, 0)} tr + mặt {_vi(p.cash_trieu, 0)} tr")
    print(f"          TỔNG {_vi(p.total_now_trieu)} tr · vàng chiếm "
          f"{_vi(p.gold_pct_now * 100)}% (ngưỡng warning {_vi(p.warning_pct, 0)}% / "
          f"critical {_vi(p.critical_pct, 0)}%)")
    if not p.needs_action:
        print("\n✅ Tỷ trọng vàng đang dưới ngưỡng critical — không cần giảm.")
        return
    print(f"\n🔴 Vượt ngưỡng critical → cần giảm. Vàng nhẫn bán theo CHỈ "
          f"(1 lượng = 10 chỉ), số bán làm tròn LÊN để chạm được mục tiêu.\n")

    hdr = (f"{'Mục tiêu':>9}{'Bán':>8}{'Thu về':>11}{'Vàng còn':>11}"
           f"{'% sau':>8}{'Thanh khoản':>13}{'Lãi thêm/năm':>14}")
    print(hdr)
    print("-" * len(hdr))
    for s in p.steps:
        lai = (_vi(s.extra_interest_per_year_trieu) + " tr"
               if s.extra_interest_per_year_trieu is not None else "chưa có LS")
        print(f"{_vi(s.target_pct, 0) + '%':>9}{str(s.chi_to_sell) + ' chỉ':>8}"
              f"{_vi(s.proceeds_trieu) + ' tr':>11}{_vi(s.gold_after_trieu) + ' tr':>11}"
              f"{_vi(s.gold_pct_after) + '%':>8}{_vi(s.liquid_after_trieu) + ' tr':>13}"
              f"{lai:>14}")

    print(f"\nTiền thu về gửi ở: {p.steps[0].deposit_note}")
    if p.rate_as_of:
        print(f"  (lãi suất theo snapshot {p.rate_as_of} — kiểm tra lại trước khi gửi)")
    print(f"\nChi phí nếu sau này MUA LẠI (chênh lệch mua–bán "
          f"{_vi((p.gold_price_buy_trieu or 0) - p.gold_price_sell_trieu, 2)} tr/lượng):")
    for s in p.steps:
        print(f"  mốc {_vi(s.target_pct, 0)}%: mất {_vi(s.spread_cost_trieu)} tr nếu mua lại đủ "
              f"{_vi(s.tael_to_sell)} lượng")
    print(f"\n⚠️ Giá vàng tiệm là ƯỚC TÍNH từ XAU {est.xau_usd}$ qua mô hình hiệu chuẩn "
          f"{est.sample_size} mẫu (độ tin cậy {est.confidence}) — hỏi giá tiệm thật "
          f"trước khi bán.")


if __name__ == "__main__":
    main()

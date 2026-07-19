#!/usr/bin/env python3
"""CLI demo Decision Engine — chạy quyết định thật cho vàng dựa trên tỷ
trọng danh mục thực tế (config/portfolio.yaml + giá vàng real-time).

Đây là nơi DUY NHẤT nên tạo ra kết luận GIỮ/CHỐT BỚT/...; scripts/run_morning.py
và run_evening.py (Phase 8) sẽ gọi decision/policy_engine.py trực tiếp thay
vì để bản tin tự viết kết luận.

Cách dùng:
  python3 scripts/decide.py gold [TICH_CUC|TIEU_CUC|TRUNG_TINH]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from decision.policy_engine import DecisionInput, decide  # noqa: E402
from decision.risk_officer import RiskContext  # noqa: E402
from portfolio.loader import load_decision_rules, load_risk_limits  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from networth import compute as compute_networth  # noqa: E402


def decide_gold(trend_label: str = "TRUNG_TINH") -> dict:
    port, limits_unused, meta, parts, total, price, src = compute_networth()
    gold_pct = (parts.get("Vàng") or 0) / total if total else None

    limits = load_risk_limits()
    rules = load_decision_rules()
    inp = DecisionInput(asset="XAUUSD (vàng nhẫn)", asset_class="gold", trend_label=trend_label)
    ctx = RiskContext(gold_allocation_pct=gold_pct)
    d = decide(inp, ctx, limits, rules)
    d["_context"] = {"gold_allocation_pct": round(gold_pct * 100, 1) if gold_pct else None,
                      "gold_price_trieu": price, "total_assets_trieu": round(total, 1)}
    return d


def main():
    trend = sys.argv[2] if len(sys.argv) > 2 else "TRUNG_TINH"
    target = sys.argv[1] if len(sys.argv) > 1 else "gold"
    if target != "gold":
        sys.exit("Hiện chỉ demo cho 'gold' (cần Phase 8 để nối đủ cổ phiếu/tiền gửi).")
    d = decide_gold(trend)
    print(json.dumps(d, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

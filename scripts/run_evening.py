#!/usr/bin/env python3
"""Orchestrator bản tin CHIỀU — như run_morning.py, cộng thêm mục bắt buộc
"THAY ĐỔI SO VỚI BẢN TIN TRƯỚC" (reporting/diff_report.py).

Cùng ràng buộc như run_morning.py: không tự fetch dữ liệu thị trường, giả
định `scripts/trend.py append` đã ghi snapshot HÔM NAY trước khi gọi.

Cách dùng:
  python3 scripts/trend.py append '<json>'
  python3 scripts/run_evening.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

HIST = ROOT / "data" / "history.jsonl"

# Import lại các hàm section dùng chung với bản tin sáng để không lặp code
from run_morning import section_alerts, section_tai_san, section_tien_gui, section_tong_quan, section_vang  # noqa: E402


def load_history() -> list[dict]:
    if not HIST.exists():
        return []
    return [json.loads(l) for l in HIST.read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    from decision.policy_engine import DecisionInput, decide
    from decision.risk_officer import RiskContext
    from deposits.ranking import load_normalized, rank
    from gold.indicators import analyze as gold_analyze
    from gold.indicators import trend_label as gold_trend_label
    from gold.xuan_trieu_model import estimate as gold_estimate
    from networth import compute as compute_networth
    from portfolio.loader import load_decision_rules, load_risk_limits
    from reporting.diff_report import compare_snapshots, format_diff_section

    port, _limits_unused, meta, parts, total, gold_price, gold_src = compute_networth()
    limits = load_risk_limits()
    rules = load_decision_rules()
    est = gold_estimate()
    gold_pct = (parts.get("Vàng") or 0) / total if total else None
    trend = gold_trend_label(gold_analyze())
    gold_decision = None
    if gold_pct is not None:
        gold_decision = decide(
            DecisionInput(asset="Vàng nhẫn", asset_class="gold", trend_label=trend),
            RiskContext(gold_allocation_pct=gold_pct), limits, rules,
        )

    deposit_rates = load_normalized()
    ranked_deposits = rank(deposit_rates) if deposit_rates else []

    print(f"# BẢN TIN ĐẦU TƯ CHIỀU — {port.updated}\n")
    print(section_tong_quan(gold_decision), "\n")
    print(section_tai_san({"parts": parts, "total": total}), "\n")
    print(section_vang(est, gold_decision), "\n")
    print(section_tien_gui(ranked_deposits), "\n")
    print(section_alerts(), "\n")

    # Mục bắt buộc: so với bản tin trước (kỳ liền trước trong history.jsonl,
    # thường là bản sáng cùng ngày)
    hist = load_history()
    if len(hist) >= 2:
        market_changes = compare_snapshots(hist[-2], hist[-1])
        # Không có lịch sử quyết định lưu lại theo kỳ ở bước này (Phase 9 sẽ
        # lưu vào journal) -> chỉ so market, không so quyết định (trung thực
        # về giới hạn hiện tại thay vì giả vờ so sánh được).
        print(format_diff_section(market_changes, []), "\n")
    else:
        print("## THAY ĐỔI SO VỚI BẢN TIN TRƯỚC\n\nChưa đủ 2 kỳ trong lịch sử để so sánh.\n")

    from reporting import render_dashboard

    render_dashboard.main()


if __name__ == "__main__":
    main()

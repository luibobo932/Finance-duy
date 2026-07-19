#!/usr/bin/env python3
"""Orchestrator bản tin SÁNG — ghép toàn bộ module thành 1 bản tin có cấu
trúc, gọi Decision Engine cho kết luận (không tự viết kết luận ở đây).

QUAN TRỌNG: script này KHÔNG tự fetch dữ liệu thị trường (VN-Index/VCB/CTD)
vì network bị chặn tới HOSE/entrade trong môi trường này (xem docs/AUDIT_
REPORT.md). Nó giả định phiên gọi (routine) đã dùng WebSearch thu thập số
liệu và ghi vào data/history.jsonl qua `scripts/trend.py append` TRƯỚC khi
gọi script này — đúng quy trình hiện tại đã hoạt động.

Cách dùng:
  python3 scripts/trend.py append '<json>'   # bước 1: ghi snapshot (như cũ)
  python3 scripts/run_morning.py             # bước 2: tổng hợp bản tin + dashboard
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

HIST = ROOT / "data" / "history.jsonl"


def load_history() -> list[dict]:
    if not HIST.exists():
        return []
    return [json.loads(l) for l in HIST.read_text(encoding="utf-8").splitlines() if l.strip()]


def section_tong_quan(gold_decision: dict | None) -> str:
    lines = ["## TỔNG QUAN HÀNH ĐỘNG", ""]
    if gold_decision:
        lines.append(f"Vàng: **{gold_decision['action_vi']}** (tin cậy {gold_decision['confidence']}/100)")
    else:
        lines.append("Vàng: chưa đủ dữ liệu để ra quyết định")
    lines.append("Tiền gửi: xem mục Tiền gửi bên dưới")
    lines.append("Cổ phiếu watchlist: xem mục Chứng khoán bên dưới")
    return "\n".join(lines)


def section_tai_san(networth_ctx: dict) -> str:
    lines = ["## TÀI SẢN RÒNG", ""]
    for name, val in networth_ctx["parts"].items():
        if val:
            pct = val / networth_ctx["total"] * 100 if networth_ctx["total"] else 0
            lines.append(f"- {name}: {val:,.1f} tr ({pct:.1f}%)")
    lines.append(f"- **TỔNG: {networth_ctx['total']:,.1f} tr**")
    return "\n".join(lines)


def section_vang(est, gold_decision: dict | None) -> str:
    lines = ["## VÀNG", ""]
    if est:
        lines.append(f"- XAU/USD: {est.xau_usd} $/oz · Tỷ giá: {est.usd_vnd:,.0f}")
        lines.append(f"- Quy đổi thế giới: {est.world_per_tael_trieu} tr/lượng")
        lines.append(f"- Giá tiệm ước tính: mua {est.shop_buy_trieu} tr / bán {est.shop_sell_trieu} tr "
                      f"(độ tin cậy {est.confidence}, {est.sample_size} mẫu hiệu chuẩn)")
    else:
        lines.append("- Chưa có đủ dữ liệu XAU/USD + tỷ giá để ước tính")
    if gold_decision:
        lines.append(f"- **Quyết định: {gold_decision['action_vi']}**")
        for r in gold_decision["reasons"]:
            lines.append(f"  - {r}")
        for w in gold_decision["risks"]:
            lines.append(f"  - ⚠️ {w}")
        for c in gold_decision["conditions_to_change"]:
            lines.append(f"  - Điều kiện đổi quyết định: {c}")
    return "\n".join(lines)


def section_tien_gui(ranked: list[dict]) -> str:
    lines = ["## TIỀN GỬI", ""]
    if not ranked:
        lines.append("- Chưa có dữ liệu lãi suất chuẩn hóa (data/normalized/deposit_rates.jsonl)")
        return "\n".join(lines)
    for r in ranked[:5]:
        lines.append(f"- {r['bank']} {r['term_months']}T: {r['rate_pct']:.2f}%/năm ({r['channel']})")
    return "\n".join(lines)


def section_alerts() -> str:
    from alerts import load as load_alerts  # scripts/alerts.py

    lines = ["## CẢNH BÁO NGƯỠNG GIÁ", ""]
    hist = load_history()
    if not hist:
        lines.append("- Chưa có dữ liệu")
        return "\n".join(lines)
    cur = hist[-1]
    # LƯU Ý ĐƠN VỊ: data/alerts.json ghi ngưỡng VCB/CTD theo "nghìn đồng"
    # (VD 58.0 = 58.000đ), trong khi data/history.jsonl lưu giá cổ phiếu
    # theo VND thô (58500). Phải quy đổi trước khi so — nếu không mọi giá
    # cổ phiếu thật (hàng chục nghìn) sẽ luôn bị coi là "vượt" mọi ngưỡng.
    vcb_raw = (cur.get("vcb") or {}).get("close")
    ctd_raw = (cur.get("ctd") or {}).get("close")
    prices = {
        "VCB": (vcb_raw / 1000) if vcb_raw is not None else None,
        "CTD": (ctd_raw / 1000) if ctd_raw is not None else None,
        "XAUUSD": (cur.get("gold") or {}).get("xauusd"),  # vàng: đơn vị USD thô, không quy đổi
    }
    prices = {k: v for k, v in prices.items() if v is not None}
    hits = []
    for a in load_alerts():
        p = prices.get(a["asset"])
        if p is None:
            continue
        if (a["type"] == "below" and p < a["level"]) or (a["type"] == "above" and p > a["level"]):
            hits.append(f"🚨 {a['asset']} = {p} đã {'thủng xuống' if a['type']=='below' else 'vượt lên'} {a['level']} → {a['note']}")
    lines.extend(hits if hits else ["- Không có ngưỡng nào bị chạm"])
    return "\n".join(lines)


def main():
    from decision.policy_engine import DecisionInput, decide
    from decision.risk_officer import RiskContext
    from deposits.ranking import load_normalized, rank
    from gold.indicators import analyze as gold_analyze
    from gold.indicators import trend_label as gold_trend_label
    from gold.xuan_trieu_model import estimate as gold_estimate
    from networth import compute as compute_networth
    from portfolio.loader import load_decision_rules, load_risk_limits

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

    print(f"# BẢN TIN ĐẦU TƯ SÁNG — {port.updated}\n")
    print(section_tong_quan(gold_decision), "\n")
    print(section_tai_san({"parts": parts, "total": total}), "\n")
    print(section_vang(est, gold_decision), "\n")
    print(section_tien_gui(ranked_deposits), "\n")
    print(section_alerts(), "\n")

    # Sinh lại dashboard tự động
    from reporting import render_dashboard

    render_dashboard.main()


if __name__ == "__main__":
    main()

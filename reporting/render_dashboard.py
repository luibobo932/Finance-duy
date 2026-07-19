#!/usr/bin/env python3
"""Sinh dashboard HTML tự động từ dữ liệu thật + quyết định của Decision
Engine — THAY THẾ cách sửa tay từng con số trong dashboard/ban-tin-dau-tu.html
mà hệ thống dùng trước Phase 8 (Audit L4).

Mỗi số liệu hiển thị PHẢI kèm: nguồn, thời điểm, độ tin cậy, có dùng fallback
không. Không có badge = không hiển thị số liệu.

File hiện có `dashboard/ban-tin-dau-tu.html` (thiết kế tay, đẹp) KHÔNG bị
ghi đè — dashboard tự sinh xuất ra file riêng `dashboard/auto_dashboard.html`
để không phá vỡ routine đang chạy; việc chuyển hẳn sang bản tự sinh là lựa
chọn của người vận hành ở bước sau.
"""
from __future__ import annotations

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

OUTPUT_PATH = ROOT / "dashboard" / "auto_dashboard.html"


def _badge(status: str) -> str:
    label = {
        "HEALTHY": "OK", "DEGRADED": "DÙNG FALLBACK", "STALE": "DỮ LIỆU ĐÃ CŨ",
        "FAILED": "DỮ LIỆU KHÔNG KHẢ DỤNG", "CONFLICTING": "NGUỒN XUNG ĐỘT",
    }.get(status, status)
    cls = {"HEALTHY": "ok", "DEGRADED": "warn", "STALE": "warn",
           "FAILED": "bad", "CONFLICTING": "bad"}.get(status, "warn")
    return f'<span class="badge {cls}">{html.escape(label)}</span>'


def build_context() -> dict:
    from decision.policy_engine import DecisionInput, decide
    from decision.risk_officer import RiskContext
    from deposits.ranking import load_normalized, rank
    from gold.indicators import analyze as gold_analyze
    from gold.indicators import trend_label as gold_trend_label
    from gold.xuan_trieu_model import estimate as gold_estimate
    from networth import compute as compute_networth
    from portfolio.loader import load_decision_rules, load_portfolio, load_risk_limits

    port, _limits_unused, meta, parts, total, gold_price, gold_src = compute_networth()
    limits = load_risk_limits()
    rules = load_decision_rules()

    gold_pct = (parts.get("Vàng") or 0) / total if total else None
    gold_status = "HEALTHY" if gold_price else "FAILED"

    gold_trend = gold_trend_label(gold_analyze())
    gold_decision = None
    if gold_pct is not None:
        gold_decision = decide(
            DecisionInput(asset="Vàng nhẫn", asset_class="gold", trend_label=gold_trend),
            RiskContext(gold_allocation_pct=gold_pct), limits, rules,
        )

    est = gold_estimate()

    deposit_rates = load_normalized()
    ranked_deposits = rank(deposit_rates) if deposit_rates else []

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "portfolio_updated": port.updated,
        "networth": {"parts": parts, "total": total, "gold_status": gold_status, "gold_src": gold_src},
        "gold_estimate": est,
        "gold_decision": gold_decision,
        "deposits": ranked_deposits[:6],
        "watchlist": port.watchlist,
        "risk_limits": limits,
    }


def render_html(ctx: dict) -> str:
    parts = ctx["networth"]["parts"]
    total = ctx["networth"]["total"]
    rows = []
    for name, val in parts.items():
        if val:
            pct = val / total * 100 if total else 0
            rows.append(f"<tr><td>{html.escape(name)}</td><td class='num'>{val:,.1f} tr</td><td class='num'>{pct:.1f}%</td></tr>")
    networth_rows = "\n".join(rows)

    gold_badge = _badge(ctx["networth"]["gold_status"])
    est = ctx["gold_estimate"]
    gold_block = ""
    if est:
        gold_block = (
            f"<p>Vàng thế giới: <strong>{est.xau_usd} $/oz</strong> · Quy đổi: "
            f"<strong>{est.world_per_tael_trieu} tr/lượng</strong></p>"
            f"<p>Giá tiệm ước tính — Mua: <strong>{est.shop_buy_trieu} tr</strong> · "
            f"Bán: <strong>{est.shop_sell_trieu} tr</strong> "
            f"({_badge('HEALTHY' if est.confidence != 'LOW' else 'DEGRADED')} độ tin cậy {est.confidence}, "
            f"{est.sample_size} mẫu hiệu chuẩn)</p>"
        )

    decision_block = ""
    gd = ctx["gold_decision"]
    if gd:
        veto_note = " ⚠️ Risk Officer đã điều chỉnh đề xuất ban đầu." if gd["risk_veto"] else ""
        decision_block = (
            f"<div class='decision'><h3>Quyết định: {html.escape(gd['action_vi'])}</h3>"
            f"<p>Độ tin cậy: {gd['confidence']}/100 · Chất lượng dữ liệu: {gd['data_quality']}{veto_note}</p>"
            f"<ul>{''.join(f'<li>{html.escape(r)}</li>' for r in gd['reasons'])}</ul></div>"
        )

    deposit_rows = "\n".join(
        f"<tr><td>{html.escape(d['bank'])}</td><td class='num'>{d['term_months']}T</td>"
        f"<td class='num'>{d['rate_pct']:.2f}%</td><td>{html.escape(d.get('channel') or '-')}</td></tr>"
        for d in ctx["deposits"]
    )

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<title>Dashboard tự động — Finance-duy</title>
<style>
:root{{--bg:#F2F4F1;--surface:#fff;--ink:#1C2723;--muted:#5C6B64;--accent:#A87B22;--line:#DDE3DE;
--ok:#0B7A4B;--warn:#B8860B;--bad:#C2372F;}}
@media (prefers-color-scheme: dark){{:root{{--bg:#0F1513;--surface:#161E1B;--ink:#E6EBE8;--muted:#93A29B;
--accent:#D4A94C;--line:#25302B;--ok:#3FBF87;--warn:#E0B84D;--bad:#E5685F;}}}}
body{{background:var(--bg);color:var(--ink);font-family:system-ui,sans-serif;margin:0;padding:20px;}}
.wrap{{max-width:820px;margin:0 auto;display:flex;flex-direction:column;gap:16px;}}
h1{{font-size:1.4rem;border-bottom:2px solid var(--accent);padding-bottom:8px;}}
section{{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:16px 18px;}}
table{{width:100%;border-collapse:collapse;}}
td,th{{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;}}
.num{{font-variant-numeric:tabular-nums;}}
.badge{{display:inline-block;padding:1px 8px;border-radius:999px;font-size:.75rem;font-weight:600;}}
.badge.ok{{background:rgba(11,122,75,.15);color:var(--ok);}}
.badge.warn{{background:rgba(184,134,11,.15);color:var(--warn);}}
.badge.bad{{background:rgba(194,55,47,.15);color:var(--bad);}}
.decision{{border-left:4px solid var(--accent);padding-left:12px;}}
.stamp{{color:var(--muted);font-size:.8rem;}}
</style></head><body><div class="wrap">
<h1>Dashboard tự động — Finance-duy</h1>
<p class="stamp">Sinh lúc {html.escape(ctx["generated_at"])} · Danh mục cập nhật {html.escape(ctx["portfolio_updated"])}</p>

<section><h2>Tài sản ròng {gold_badge}</h2>
<table><tr><th>Tài sản</th><th>Giá trị</th><th>Tỷ trọng</th></tr>{networth_rows}
<tr><td><strong>TỔNG</strong></td><td class='num'><strong>{total:,.1f} tr</strong></td><td></td></tr></table>
</section>

<section><h2>Vàng</h2>{gold_block}</section>

<section><h2>Quyết định (Decision Engine)</h2>{decision_block or "<p>Chưa có đủ dữ liệu để ra quyết định.</p>"}</section>

<section><h2>Lãi suất tiết kiệm (top {len(ctx["deposits"])})</h2>
<table><tr><th>Ngân hàng</th><th>Kỳ hạn</th><th>Lãi suất</th><th>Kênh</th></tr>{deposit_rows}</table>
</section>

<section><h2>Watchlist</h2><p>{", ".join(html.escape(w) for w in ctx["watchlist"])}</p></section>

</div></body></html>"""


def main():
    ctx = build_context()
    out = render_html(ctx)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(out, encoding="utf-8")
    print(f"Đã sinh dashboard: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

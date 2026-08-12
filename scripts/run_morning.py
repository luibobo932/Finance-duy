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


def bulletin_date(hist: list[dict], today: "date | None" = None) -> str:
    """Ngày hiển thị trên tiêu đề bản tin.

    KHÔNG dùng portfolio.updated (config/portfolio.yaml) — trường đó là ngày
    chủ dự án tự tay cập nhật SỐ LƯỢNG tài sản (vàng/tiết kiệm/tiền mặt),
    đứng yên hàng tuần/tháng, không phải ngày bản tin đang chạy. Bug thật đã
    xảy ra: bản tin chạy 26/7 vẫn in tiêu đề "2026-07-19" vì lấy nhầm trường
    này. Ưu tiên ngày của snapshot mới nhất trong history.jsonl (dữ liệu thật
    bản tin đang tường thuật); nếu chưa có snapshot nào thì dùng ngày hôm nay.
    """
    from datetime import date as _date

    today = today or _date.today()
    if hist and hist[-1].get("date"):
        return hist[-1]["date"]
    return today.isoformat()


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


def send_telegram_report(text: str) -> None:
    """Gửi bản tin qua Telegram nếu .env đã cấu hình đủ TOKEN + CHAT_ID.

    Đây là kênh phụ trợ — thất bại (chưa cấu hình, mất mạng...) chỉ log cảnh
    báo qua common/logsetup, KHÔNG được làm gián đoạn việc in bản tin ra
    stdout (kênh chính, luôn phải chạy được)."""
    from common import get_logger
    from common.env import get_env
    from notifications.formatting import to_telegram_html
    from notifications.telegram import TelegramError, send_message

    logger = get_logger("bulletin_telegram")
    token = get_env("TELEGRAM_BOT_TOKEN")
    chat_id = get_env("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.info("Bỏ qua gửi Telegram: chưa cấu hình TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID trong .env")
        return
    try:
        # Bản đẹp (HTML: icon + in đậm); nếu Telegram từ chối parse HTML vì
        # ký tự bất ngờ nào đó thì fallback text thô — bản tin phải luôn tới.
        try:
            result = send_message(token, chat_id, to_telegram_html(text), parse_mode="HTML")
        except TelegramError as e:
            logger.warning(f"Gửi bản HTML thất bại ({e}) — fallback text thô")
            result = send_message(token, chat_id, text)
        logger.info("Đã gửi bản tin qua Telegram",
                     extra={"extra_fields": {"message_id": result.get("message_id")}})
    except TelegramError as e:
        logger.warning(f"Gửi Telegram thất bại: {e}")


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


def run_gold_decision(ky: str):
    """Chạy Decision Engine cho vàng + ghi quyết định vào data/decisions.jsonl.

    Phase 9: (1) accuracy từ decision review (nếu đủ ≥5 mẫu đã chấm) được nạp
    vào trọng số lịch sử của confidence score — hệ thống tự "biết" nó đoán
    đúng bao nhiêu; (2) mỗi quyết định được lưu bất biến kèm giá tham chiếu
    tại thời điểm đó để review sau này (chống look-ahead: dup-guard theo
    date+ky+asset, không ghi đè lịch sử)."""
    from analytics.decision_review import historical_accuracy_for_confidence, review_all, summarize
    from decision.decision_log import append_decision, build_entry, load_decisions
    from decision.policy_engine import DecisionInput, decide
    from decision.risk_officer import RiskContext
    from gold.indicators import analyze as gold_analyze
    from gold.indicators import trend_label as gold_trend_label
    from networth import compute as compute_networth
    from portfolio.loader import load_decision_rules, load_risk_limits

    port, _limits_unused, meta, parts, total, gold_price, gold_src = compute_networth()
    limits = load_risk_limits()
    rules = load_decision_rules()
    gold_pct = (parts.get("Vàng") or 0) / total if total else None
    trend = gold_trend_label(gold_analyze())

    hist = load_history()
    past_decisions = load_decisions()
    hist_acc = None
    if past_decisions:
        hist_acc = historical_accuracy_for_confidence(summarize(review_all(past_decisions, hist)))

    gold_decision = None
    if gold_pct is not None:
        gold_decision = decide(
            DecisionInput(asset="Vàng nhẫn", asset_class="gold", trend_label=trend,
                          historical_accuracy_pct=hist_acc),
            RiskContext(gold_allocation_pct=gold_pct), limits, rules,
        )
        if hist:
            append_decision(build_entry(gold_decision, asset_class="gold", ky=ky, snapshot=hist[-1]))
    return port, parts, total, gold_decision


def main():
    from deposits.ranking import load_normalized, rank
    from gold.xuan_trieu_model import estimate as gold_estimate

    port, parts, total, gold_decision = run_gold_decision(ky="sang")
    est = gold_estimate()

    deposit_rates = load_normalized()
    ranked_deposits = rank(deposit_rates) if deposit_rates else []

    sections = [
        f"# BẢN TIN ĐẦU TƯ SÁNG — {bulletin_date(load_history())}",
        section_tong_quan(gold_decision),
        section_tai_san({"parts": parts, "total": total}),
        section_vang(est, gold_decision),
        section_tien_gui(ranked_deposits),
        section_alerts(),
    ]
    for s in sections:
        print(s, "\n")

    # Sinh lại dashboard tự động
    # Hai dashboard, hai vai trò khác nhau:
    # - auto_dashboard.html: bảng chẩn đoán, mỗi số kèm badge nguồn/độ tin cậy
    # - ban-tin-dau-tu.html: trang bản tin cho người đọc, sinh từ history.jsonl
    #   (trước đây phải sửa tay ~71 toạ độ SVG mỗi kỳ — giờ tự tính)
    from reporting import dashboard_builder, render_dashboard

    render_dashboard.main()
    dashboard_builder.main()

    send_telegram_report("\n\n".join(sections))


if __name__ == "__main__":
    main()

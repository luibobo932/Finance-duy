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
from datetime import date  # noqa: F401 — dùng trong chú thích kiểu
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


def section_ke_hoach_giam_ty_trong(ranked: list[dict]) -> str:
    """Mục "bán bao nhiêu là đủ" — chỉ xuất hiện khi tỷ trọng vượt critical.

    Khuyến nghị CHỐT BỚT treo 14 kỳ một phần vì nó không kèm con số. Mục này
    đưa số lượng bán được (theo chỉ), tiền thu về và lãi thêm mỗi năm, để
    khuyến nghị thành việc làm được ngay chứ không phải một hướng đi chung.
    """
    from decision.rebalance import plan as rebalance_plan
    from gold.xuan_trieu_model import estimate as gold_estimate
    from portfolio.loader import load_portfolio, load_risk_limits

    est = gold_estimate()
    if not est:
        return ""
    port = load_portfolio()
    p = rebalance_plan(
        gold_tael=port.gold_quantity_tael,
        sell_price_trieu=est.shop_buy_trieu,
        buy_price_trieu=est.shop_sell_trieu,
        savings_trieu=port.savings_principal_vnd / 1_000_000,
        cash_trieu=port.cash_amount_vnd / 1_000_000,
        limits=load_risk_limits(), ranked_rates=ranked,
    )
    if not p.needs_action or not p.steps:
        return ""
    lines = ["## KẾ HOẠCH GIẢM TỶ TRỌNG VÀNG — BÁN BAO NHIÊU LÀ ĐỦ", ""]
    lines.append(f"Vàng đang {p.gold_pct_now * 100:.1f}% (critical {p.critical_pct:.0f}%). "
                 f"Giá bán dùng giá tiệm MUA vào {p.gold_price_sell_trieu:.2f} tr/lượng. "
                 "Vàng nhẫn bán theo chỉ (1 lượng = 10 chỉ).")
    lines.append("")
    # Nối kế hoạch bán với kịch bản giá: khuyến nghị nói "bán bao nhiêu" và
    # "được thêm bao nhiêu lãi", nhưng chưa từng nói "bán để tránh CÁI GÌ".
    from analytics.downside import protection_from_selling

    for s in p.steps:
        lai = (f", lãi thêm ~{s.extra_interest_per_year_trieu:.1f} tr/năm"
               if s.extra_interest_per_year_trieu is not None else "")
        lines.append(f"- Về {s.target_pct:.0f}%: bán **{s.chi_to_sell} chỉ** "
                     f"({s.tael_to_sell:.1f} lượng) → thu {s.proceeds_trieu:.1f} tr, "
                     f"vàng còn {s.gold_pct_after:.1f}%{lai}")
        prot = next((x for x in protection_from_selling(s.chi_to_sell, s.proceeds_trieu)
                     if x.shock_pct == -15.0), None)
        if prot:
            lines.append(f"  - Nếu vàng giảm 15%, phần đã bán tránh được "
                         f"{prot.protected_trieu:.1f} tr sụt giá "
                         "(chưa tính lãi tiền gửi ở dòng trên — không đếm trùng)")
    if p.best_rate_pct:
        lines.append(f"- Gửi ở: {p.best_rate_bank} {p.best_rate_pct:.2f}%/năm "
                     f"kỳ hạn {p.best_rate_term} tháng (kiểm tra lại trước khi gửi)")
    lines.append(f"- Phí nếu sau này mua lại: chênh lệch mua–bán "
                 f"{(p.gold_price_buy_trieu or 0) - p.gold_price_sell_trieu:.2f} tr/lượng")
    return "\n".join(lines)


def section_kich_ban_gia_vang(parts: dict, total: float | None) -> str:
    """Rủi ro tập trung quy ra TIỀN — vế còn thiếu của khuyến nghị CHỐT BỚT.

    Khuyến nghị đã treo 19 kỳ với nội dung "vàng 76%, vượt ngưỡng 70%": một tỷ
    lệ phần trăm so với một tỷ lệ phần trăm khác. Mục này nói con số đó bằng
    bao nhiêu triệu đồng, và bày ĐỐI XỨNG cả chiều tăng lẫn chiều giảm.
    """
    from analytics.downside import headline, measure_volatility, scenario_table
    from portfolio.loader import load_portfolio

    gold = parts.get("Vàng") or 0
    if not total or not gold:
        return ""
    rows = scenario_table(load_portfolio().gold_quantity_tael, total - gold)
    if not rows:
        return ""
    lines = ["## KỊCH BẢN GIÁ VÀNG — RỦI RO QUY RA TIỀN", ""]
    lines.append("Đây là số học \"nếu…thì\", **không phải dự báo** và không kèm xác suất nào.")
    lines.append("")
    for r in rows:
        lines.append(f"- Vàng {r.shock_pct:+.0f}% (XAU {r.xau_after:,.0f}$): "
                     f"tổng tài sản {r.total_after_trieu:,.0f} tr "
                     f"({r.change_trieu:+,.0f} tr), vàng còn {r.gold_pct_after:.1f}%")
    lines.append("")
    lines.append(headline(rows))
    lines.append(measure_volatility().caveat)
    return "\n".join(lines)


def section_tien_gui(ranked: list[dict]) -> str:
    lines = ["## TIỀN GỬI", ""]
    lines.append(_khoan_dang_gui(ranked))
    lines.append("")
    if not ranked:
        lines.append("- Chưa có dữ liệu lãi suất chuẩn hóa (data/normalized/deposit_rates.jsonl)")
        return "\n".join(lines)
    lines.append("Mức tốt nhất đang đo được:")
    for r in ranked[:5]:
        lines.append(f"- {r['bank']} {r['term_months']}T: {r['rate_pct']:.2f}%/năm ({r['channel']})")
    return "\n".join(lines)


def _khoan_dang_gui(ranked: list[dict]) -> str:
    """Khoản tiết kiệm ĐANG NẮM — trước giờ bản tin chỉ liệt kê lãi suất thị
    trường mà chưa lần nào nói về chính khoản tiền của chủ danh mục."""
    from deposits.holding import (from_portfolio, maturity_alert, rate_gap_table,
                                  undeclared_note)
    from portfolio.loader import load_portfolio

    port = load_portfolio()
    h = from_portfolio(port, deposit_cfg=port.savings_raw)
    if not h.principal_vnd:
        return ""
    best = ranked[0]["rate_pct"] if ranked else None
    if not h.is_declared:
        note = undeclared_note(h.principal_vnd, rate_gap_table(h.principal_vnd, best))
        return "⚠️ " + note.replace("<code>", "`").replace("</code>", "`")

    out = [f"Khoản đang gửi: **{h.principal_vnd / 1e6:,.0f} tr** "
           f"@ {h.rate_pct:.2f}%/năm"
           + (f" · {h.bank}" if h.bank else "")
           + (f" · kỳ hạn {h.term_months} tháng" if h.term_months else "")]
    lai = h.accrued_interest_vnd()
    if lai is not None:
        out.append(f"- Lãi tích lũy tới nay: {lai / 1e6:,.1f} tr")
    if best and h.rate_pct < best:
        gap = (best - h.rate_pct) / 100 * h.principal_vnd / 1e6
        out.append(f"- ⚠️ Thấp hơn mức tốt nhất đang đo được ({best:.2f}%/năm) "
                   f"— chênh {gap:,.1f} tr/năm")
    alert = maturity_alert(h)
    if alert:
        out.append(f"- {'🔴' if alert.level == 'critical' else '⚠️'} {alert.message}")
    return "\n".join(out)


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


def section_suc_mua(parts: dict, total: float | None) -> str:
    """Sức mua, không phải số dư.

    Mọi con số hệ thống nói cho tới nay đều là DANH NGHĨA. Với CPI 7 tháng 2026
    là +4,39%, "tiền mặt 35 tr không đổi" thực ra là đang mất 1,47 tr sức mua
    mỗi năm — và chưa kỳ bản tin nào nói điều đó.
    """
    from planning.plan import load_plan
    from planning.real_return import (RealReturn, doubling_years, erosion_trieu,
                                      purchasing_power_trieu, real_pct)

    plan = load_plan()
    if not plan.inflation_pct or not total:
        return ""
    lines = ["## SỨC MUA (sau lạm phát)", ""]
    lines.append(f"Lạm phát tham chiếu **{plan.inflation_pct:.2f}%/năm** — {plan.inflation_source}.")
    lines.append("")

    cash = parts.get("Tiền mặt") or 0.0
    if cash:
        r = RealReturn("Tiền mặt", 0.0, plan.inflation_pct, cash)
        lines.append(f"- Tiền mặt {cash:,.0f} tr: danh nghĩa 0% → **thực {r.real_pct:+.2f}%/năm**, "
                     f"bào mòn **{erosion_trieu(cash, plan.inflation_pct):.2f} tr/năm**")
    best = _best_deposit_rate()
    if best:
        rr = real_pct(best, plan.inflation_pct)
        dbl = doubling_years(rr)
        lines.append(f"- Mức gửi tốt nhất đo được {best:.2f}%/năm → **thực {rr:+.2f}%/năm**"
                     + (f" (gấp đôi sức mua sau ~{dbl:.0f} năm)" if dbl else ""))
    pp = purchasing_power_trieu(total, plan.inflation_pct, 10)
    lines.append(f"- Nếu toàn bộ {total:,.0f} tr không sinh lời, sau 10 năm chỉ còn mua được "
                 f"lượng hàng hoá tương đương **{pp:,.0f} tr hôm nay** (mất {total - pp:,.0f} tr sức mua)")
    if not plan.has_goals:
        lines.append("")
        lines.append("⚠️ Chưa khai mục tiêu tài chính trong `config/plan.yaml`. Thiếu mục tiêu thì "
                     "mọi ngưỡng rủi ro đều là con số tuỳ tiện — \"vàng ≥70%\" là 70% so với cái gì?")
        return "\n".join(lines)

    # Có mục tiêu rồi thì mọi ngưỡng phía trên mới có chỗ neo.
    from planning.feasibility import best_lever, horizon_table

    goal = plan.goals[0]
    target = goal.target_vnd / 1_000_000
    rows = horizon_table(total, target, plan.inflation_pct, risk_free_pct=best)
    lines.append("")
    lines.append(f"**Mục tiêu: {goal.name}** — cần gấp {target / total:.2f} lần tài sản hiện có."
                 + ("" if goal.has_deadline else " Thời hạn **chưa chốt**, mà đó là biến quyết định tất cả:"))
    for h in rows:
        thm = (f"{h.required_monthly_trieu:.1f} tr/tháng" if h.required_monthly_trieu
               else "không cần gửi thêm")
        lines.append(f"  - {h.years} năm: cần {h.required_return_pct:.2f}%/năm nếu không gửi thêm, "
                     f"**hoặc** {thm} với lãi tiền gửi — {h.band_label}")
    lines.append(f"- {best_lever(rows)}")
    return "\n".join(lines)


def _best_deposit_rate() -> float | None:
    try:
        from deposits.ranking import load_normalized, rank

        ranked = rank(load_normalized())
        return ranked[0]["rate_pct"] if ranked else None
    except Exception:  # noqa: BLE001
        return None


def section_chung_khoan() -> str:
    """Mục CHỨNG KHOÁN — mục mà `section_tong_quan()` đã trỏ tới ở mọi kỳ bản
    tin trong khi nó KHÔNG TỒN TẠI.

    Toàn bộ lớp phân tích đã có sẵn (`equity/technical.py`, nhánh equity của
    Decision Engine, rule quản trị của Risk Officer) và chạy được ngay trên 43
    phiên EOD thật của VCB/CTD — chỉ chưa ai gọi.
    """
    from equity.signals import analyze as eq_analyze
    from equity.signals import (data_quality_for, decide_for, dividends_for, plan_for,
                                stale_price_note, valuation_for)
    from equity.target_prices import undated_warning
    from portfolio.loader import load_portfolio, load_risk_limits

    port = load_portfolio()
    limits = load_risk_limits()
    held = {p.ticker.upper(): p for p in port.stock_positions if p.quantity}
    tickers = [t.upper() for t in (port.watchlist or [])]
    if not tickers:
        return ""
    hurdle = _best_deposit_rate()
    net = _net_worth_trieu()
    hist = load_history()

    lines = ["## CHỨNG KHOÁN", ""]
    if not held:
        lines.append("Đang **không nắm giữ** cổ phiếu nào — đây là danh sách theo dõi, "
                     "nên khuyến nghị dừng ở ĐỨNG NGOÀI / CHỜ XÁC NHẬN / MUA THĂM DÒ "
                     "(không có \"GIỮ\" cho mã không có vị thế).")
        lines.append("")
    for t in tickers:
        s = eq_analyze(t)
        if not s.has_data:
            lines.append(f"- **{t}**: chưa có dữ liệu EOD (`data/eod/{t}.csv`)")
            continue
        d = decide_for(s, has_position=t in held)
        lines.append(f"- **{t}** {s.close:,.2f} (EOD {s.last_date}) → "
                     f"**{d['action_vi']}** (tin cậy {d['confidence']}/100)")
        # Một câu giải thích, dùng cho cả nhãn hành động lẫn kế hoạch vào lệnh
        # bên dưới, để hai thứ không thể nói khác nhau.
        stale_note = stale_price_note(s)
        if stale_note:
            lines.append(f"  - ⚠️ DỮ LIỆU CŨ: {data_quality_for(s).explain()}")
        lines.append(f"  - {s.evidence()}")
        sr = []
        if s.tech.get("support") is not None:
            sr.append(f"hỗ trợ {s.tech['support']:,.2f}")
        if s.tech.get("resistance") is not None:
            sr.append(f"kháng cự {s.tech['resistance']:,.2f}")
        if sr:
            lines.append(f"  - {' · '.join(sr)}")
        if s.tech.get("breakout") and s.tech["breakout"] != "NONE":
            lines.append(f"  - ⚠️ {s.tech['breakout']}")
        if s.volume_flag:
            lines.append(f"  - ⚠️ {s.volume_flag}")

        # Biên an toàn + kế hoạch vào lệnh. Một khuyến nghị mua thiếu "bao
        # nhiêu / giá nào / sai thì thoát ở đâu" thì không thực hiện được.
        view = valuation_for(s)
        if view:
            lines.append(f"  - {view.note()}")
            w = undated_warning(view)
            if w:
                lines.append(f"  - ⚠️ {w}")
        div = dividends_for(s)
        if div:
            lines.append(f"  - {div.note()}")
        # Mọi ràng buộc (trần 1 mã/tổng đã trừ phần đang nắm, rào lợi suất,
        # tiền phải có thật, giá không được cũ) nằm trong plan_for — dashboard
        # gọi đúng hàm này, nên hai nơi không thể ra hai con số khác nhau.
        plan = plan_for(s, port, limits, net_worth_trieu=net, hurdle_pct=hurdle)
        if plan:
            lines.append(f"  - **{plan.summary()}**")
            for n in plan.notes:
                lines.append(f"    - ⚠️ {n}")

        # Ghi quyết định cổ phiếu vào nhật ký. Trước đây decisions.jsonl chỉ có
        # vàng (13/13 bản ghi) nên toàn bộ máy chấm điểm không nhìn thấy phần
        # cổ phiếu — mà đây mới là loại quyết định CÓ HƯỚNG GIÁ, chấm đúng/sai
        # được, thứ mà HOLD/CHỐT BỚT của vàng không làm được.
        _log_equity_decision(d, t, hist)

    changes = _sync_stop_alerts(held, limits)
    if changes:
        lines.append("")
        lines.append("🔔 **Cảnh báo cắt lỗ đã đồng bộ:** " + "; ".join(changes))

    issues = _portfolio_consistency()
    if issues:
        lines.append("")
        lines.append("⚠️ **Danh mục chưa khớp nhật ký giao dịch:**")
        lines.extend(f"  - {i}" for i in issues)
    return "\n".join(lines)


def _log_equity_decision(decision: dict, ticker: str, hist: list[dict]) -> None:
    """Ghi bất biến vào data/decisions.jsonl, kèm giá tham chiếu của ĐÚNG mã."""
    try:
        from decision.decision_log import append_decision, build_entry

        if not hist:
            return
        snap = hist[-1]
        append_decision(build_entry(decision, asset_class="equity",
                                    ky=snap.get("ky", "sang"), snapshot=snap, ticker=ticker))
    except Exception:  # noqa: BLE001 — ghi nhật ký hỏng không được chặn bản tin
        pass


def _sync_stop_alerts(held: dict, limits: dict) -> list[str]:
    """Đăng ký mức cắt lỗ của vị thế ĐANG NẮM thành cảnh báo thật.

    Mức cắt lỗ chỉ tồn tại trong một dòng chữ đã trôi qua thì không phải mức
    thoát — đó là một lời hứa. `scripts/alerts.py` quét data/alerts.json mỗi
    kỳ, nên đưa mức cắt lỗ vào đó là cách duy nhất để nó được canh thật.
    """
    if not held:
        return []
    try:
        import json as _json

        from decision.stop_registry import sync_stops
        from equity.signals import analyze as eq_analyze
        from equity.signals import stale_price_note

        path = ROOT / "data" / "alerts.json"
        data = _json.loads(path.read_text(encoding="utf-8"))
        positions, freeze = [], []
        for ticker, pos in held.items():
            s = eq_analyze(ticker)
            # Chuỗi EOD cũ thì KHÔNG tính lại mức cắt lỗ — và cũng không gỡ mức
            # đang canh. Đây là nơi mức cắt lỗ được GHI XUỐNG ĐĨA, nên nó nguy
            # hiểm hơn hai nơi chỉ hiển thị: một con số suy từ vùng hỗ trợ của
            # 19 ngày trước nằm lại trong data/alerts.json và được quét mỗi kỳ
            # như thể là mức rủi ro đang sống.
            if s.has_data and stale_price_note(s):
                freeze.append(ticker)
                continue
            sup = s.tech.get("support") if s.has_data else None
            if sup and s.close and sup < s.close:
                positions.append({"ticker": ticker, "stop": round(sup * 0.98, 2),
                                  "entry": (pos.avg_cost_vnd or 0) / 1000 or None})
        alerts, changes = sync_stops(data.get("alerts", []), positions, freeze=freeze)
        if freeze:
            changes.append("giữ nguyên mức cắt lỗ " + ", ".join(freeze)
                           + " — chuỗi EOD quá cũ để tính lại (không gỡ, không đổi)")
        if changes:
            data["alerts"] = alerts
            path.write_text(_json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        return changes
    except Exception:  # noqa: BLE001 — đồng bộ cảnh báo hỏng không được chặn bản tin
        return []


def _portfolio_consistency() -> list[str]:
    """Vị thế khai báo có khớp nhật ký giao dịch không.

    Ra đời từ một phép thử: làm đúng theo khuyến nghị MUA rồi khai vị thế vào
    config, tài sản ròng nhảy từ 1.172,7 lên 1.255,7 tr — tự nhiên nhiều thêm
    83 triệu, vì config mô tả "đang nắm gì" chứ không mô tả "đã đổi gì lấy gì".
    """
    try:
        from portfolio.loader import load_portfolio
        from portfolio.transactions import load_transactions, reconcile, validate_history

        txs = load_transactions()
        return validate_history(txs) + reconcile(load_portfolio().stock_positions, txs)
    except Exception:  # noqa: BLE001
        return []


def _net_worth_trieu() -> float | None:
    try:
        from networth import compute

        return compute()[4]
    except Exception:  # noqa: BLE001
        return None


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

    # Dùng CHUNG analytics/alert_health với scripts/alerts.py. Trước đây mục này
    # có bản sao riêng của logic so ngưỡng, nên bản tin không thấy được ngưỡng đã
    # lỗi thời — nguồn sự thật thứ ba cho cùng một phép so sánh.
    from analytics.alert_health import evaluate, load_state, save_state

    period = f"{cur.get('date')}-{cur.get('ky')}"
    results, new_state = evaluate(load_alerts(), prices, load_state(),
                                  today=cur.get("date"), period=period)
    save_state(new_state)

    fresh = [r for r in results if r.fired and not r.is_stale]
    stale = [r for r in results if r.fired and r.is_stale]
    if fresh:
        lines.extend(f"🚨 {r.headline}" for r in fresh)
    if stale:
        lines.append(f"🔧 {len(stale)} ngưỡng LỖI THỜI (kích hoạt liên tiếp nhiều kỳ, "
                     "không còn là tin mới — đặt lại bằng `alerts.py --reanchor`):")
        lines.extend(f"  - {r.headline}" for r in stale)
    if not fresh and not stale:
        lines.append("- Không có ngưỡng nào bị chạm")
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
    from gold.indicators import trend_evidence as gold_trend_evidence
    from gold.indicators import trend_label as gold_trend_label
    from networth import compute as compute_networth
    from portfolio.loader import load_decision_rules, load_risk_limits

    port, _limits_unused, meta, parts, total, gold_price, gold_src = compute_networth()
    limits = load_risk_limits()
    rules = load_decision_rules()
    gold_pct = (parts.get("Vàng") or 0) / total if total else None
    hist = load_history()
    # Xu hướng đo trên chuỗi XAU/USD của CHÍNH history đã nạp — không đọc lại
    # đĩa lần nữa để hai chỗ không thể lệch nhau.
    gold_ta = gold_analyze(history=hist)
    trend = gold_trend_label(gold_ta)
    print(f"- Xu hướng vàng: {trend or 'chưa đo được'} — {gold_trend_evidence(gold_ta)}")

    past_decisions = load_decisions()
    hist_acc = None
    if past_decisions:
        hist_acc = historical_accuracy_for_confidence(summarize(review_all(past_decisions, hist)))

    gold_decision = None
    if gold_pct is not None:
        from analytics.data_quality import assess_gold

        dq = assess_gold(hist)
        gold_decision = decide(
            DecisionInput(asset="Vàng nhẫn", asset_class="gold", trend_label=trend,
                          historical_accuracy_pct=hist_acc,
                          data_completeness_pct=dq.completeness_pct,
                          data_freshness_score=dq.freshness_score),
            RiskContext(gold_allocation_pct=gold_pct, data_stale=dq.data_stale,
                        data_missing_critical=dq.data_missing_critical),
            limits, rules,
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
        section_suc_mua(parts, total),
        section_vang(est, gold_decision),
        section_kich_ban_gia_vang(parts, total),
        section_ke_hoach_giam_ty_trong(ranked_deposits),
        section_tien_gui(ranked_deposits),
        section_chung_khoan(),
        section_alerts(),
    ]
    for s in sections:
        if s:  # mục rỗng (VD kế hoạch giảm tỷ trọng khi chưa cần) thì bỏ qua
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

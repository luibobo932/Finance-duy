"""Sinh dashboard bản tin TỪ data/history.jsonl — không sửa tay số nào nữa.

Trước module này, `dashboard/ban-tin-dau-tu.html` được sửa TAY mỗi kỳ: ~71 toạ
độ SVG + mọi con số trong thẻ, bảng, chân trang. Hệ quả thực tế đã gặp:
- Biểu đồ chỉ hiện được 9 kỳ ("cửa sổ trượt") vì thêm điểm là phải tính lại tay
- Lịch sử cũ bị đẩy ra khỏi hình dù dữ liệu vẫn còn trong history.jsonl
- Không có cách nào kiểm tra hình vẽ có khớp số hay không

Ở đây mọi con số và toạ độ đều TÍNH từ `data/history.jsonl` + `config/*.yaml`,
nên hình luôn khớp dữ liệu và lịch sử hiện đầy đủ.

Định giá lịch sử: mỗi snapshot được định giá lại bằng CHÍNH mô hình mà
`scripts/networth.py` dùng (gold/xuan_trieu_model theo XAU + tỷ giá của snapshot
đó), nên đường "tổng tài sản" nhất quán với con số hiển thị ở thẻ đầu trang.
"""
from __future__ import annotations

import html
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.advice_tracker import summarize_pending  # noqa: E402
from decision.rebalance import plan as rebalance_plan  # noqa: E402
from gold.xuan_trieu_model import estimate as gold_estimate  # noqa: E402
from portfolio.loader import load_portfolio, load_risk_limits  # noqa: E402
from reporting.chart import (  # noqa: E402
    Bar,
    Box,
    Segment,
    Series,
    allocation_legend,
    bar_chart,
    diverging_bar_chart,
    legend,
    line_chart,
    stacked_bar,
    thin_labels,
)

HISTORY_PATH = ROOT / "data" / "history.jsonl"
WATCHLIST_PATH = ROOT / "data" / "watchlist.json"
OUTPUT_PATH = ROOT / "dashboard" / "ban-tin-dau-tu.html"

# Tuổi dữ liệu quá mốc này thì gắn nhãn "đã cũ" — bản tin 2 kỳ/ngày nên quá
# 1 ngày không có snapshot mới là dấu hiệu routine hỏng, phải nhìn thấy ngay.
STALE_AFTER = timedelta(days=1)

KY_VI = {"sang": "sáng", "chieu": "chiều"}

# Nhãn tiếng Việt cho các khoá `note_*` hay dùng trong snapshot. Khoá lạ sẽ
# rơi về chính tên khoá (đọc được, chỉ không đẹp) — thà thấy nhãn thô còn hơn
# gộp 2 ghi chú khác nhau vào cùng một tiêu đề.
NOTE_TOPIC_VI = {
    "gold": "vàng",
    "gold_surge": "vàng tăng mạnh",
    "market": "thị trường",
    "market_detail": "chi tiết thị trường",
    "market_outlook": "triển vọng thị trường",
    "selloff": "áp lực bán",
    "selloff_cause": "nguyên nhân bán tháo",
    "data_conflict": "xung đột dữ liệu",
    "ctd_data": "dữ liệu CTD",
    "ctd_price_conflict": "xung đột giá CTD",
}


@dataclass
class Valuation:
    """Định giá danh mục tại 1 snapshot."""
    gold_trieu: Optional[float]
    savings_trieu: float
    cash_trieu: float
    total_trieu: Optional[float]
    gold_pct: Optional[float]
    gold_price_trieu: Optional[float]


def load_history(path: Optional[Path] = None) -> list[dict]:
    path = path or HISTORY_PATH
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def snapshot_label(snap: dict) -> str:
    """Nhãn ngắn cho trục x: '22/7c' = chiều 22/7."""
    date = snap.get("date") or ""
    parts = date.split("-")
    short = f"{int(parts[2])}/{int(parts[1])}" if len(parts) == 3 else date
    return f"{short}{'c' if snap.get('ky') == 'chieu' else 's'}"


def value_at(snap: dict, port) -> Valuation:
    """Định giá danh mục theo giá vàng CỦA CHÍNH snapshot đó.

    Số lượng tài sản là hằng số trong config, nên đường giá trị theo thời gian
    phản ánh đúng biến động giá — không phải thay đổi do mua/bán.
    """
    savings = port.savings_principal_vnd / 1_000_000
    cash = port.cash_amount_vnd / 1_000_000
    xau = (snap.get("gold") or {}).get("xauusd")
    fx = snap.get("fx_vcb_sell")
    price = None
    if xau and fx:
        est = gold_estimate(xau_usd=xau, usd_vnd=fx)
        if est:
            price = est.shop_buy_trieu  # giá tiệm TRẢ khi bán — giá trị thanh lý thật
    if price is None:
        return Valuation(None, savings, cash, None, None, None)
    gold = port.gold_quantity_tael * price
    total = gold + savings + cash
    return Valuation(gold, savings, cash, total, gold / total if total else None, price)


def _freshness(latest: dict) -> tuple[str, str]:
    """(nhãn, mức) cho tuổi dữ liệu — mức thuộc {ok, warn, bad}."""
    date = latest.get("date")
    if not date:
        return "không rõ thời điểm dữ liệu", "bad"
    try:
        stamp = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return f"thời điểm không đọc được: {date}", "bad"
    age = datetime.now(timezone.utc) - stamp
    if age <= STALE_AFTER:
        return "dữ liệu mới", "ok"
    days = age.days
    return f"dữ liệu cũ {days} ngày — kiểm tra routine bản tin", "warn" if days <= 3 else "bad"


def build_context(history: Optional[list[dict]] = None) -> dict:
    history = history if history is not None else load_history()
    if not history:
        raise SystemExit("data/history.jsonl trống — chạy scripts/trend.py append trước.")

    port = load_portfolio()
    limits = load_risk_limits()
    latest = history[-1]
    vals = [value_at(s, port) for s in history]
    cur = vals[-1]
    labels = [snapshot_label(s) for s in history]

    watchlist = {}
    if WATCHLIST_PATH.exists():
        watchlist = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))

    # Ngưỡng trong config là PHÂN SỐ (0.70) — đổi sang % để dùng chung đơn vị
    # với tỷ trọng hiển thị trên biểu đồ.
    def _pct(key: str) -> Optional[float]:
        raw = (limits or {}).get(key)
        return float(raw) * 100 if raw is not None else None

    critical_pct = _pct("gold_critical")
    warning_pct = _pct("gold_warning")

    # Kế hoạch giảm tỷ trọng — chỉ dựng khi có đủ giá vàng; thiếu thì để None
    # và mục này biến mất khỏi trang thay vì hiện bảng rỗng.
    rebalance = None
    if cur.gold_price_trieu:
        est = gold_estimate()
        try:
            rebalance = rebalance_plan(
                gold_tael=port.gold_quantity_tael,
                sell_price_trieu=cur.gold_price_trieu,
                buy_price_trieu=est.shop_sell_trieu if est else None,
                savings_trieu=cur.savings_trieu,
                cash_trieu=cur.cash_trieu,
                limits=limits or {},
                ranked_rates=_ranked_deposit_rates(),
                rate_as_of=(latest_snapshot_with(history, "deposit_top") or {}).get("date"),
            )
        except Exception:  # noqa: BLE001 — thiếu kế hoạch không được làm sập cả trang
            rebalance = None

    gold_band = None
    if cur.gold_price_trieu:
        try:
            from gold.calibration import banded_estimate

            xau = (latest.get("gold") or {}).get("xauusd")
            if xau:
                gold_band = banded_estimate(cur.gold_price_trieu, float(xau), history=history)
        except Exception:  # noqa: BLE001 — thiếu biên không được làm sập trang
            gold_band = None

    return {
        "history": history,
        "labels": labels,
        "rebalance": rebalance,
        "gold_band": gold_band,
        "valuations": vals,
        "current": cur,
        "latest": latest,
        "portfolio": port,
        "limits": limits,
        "critical_pct": critical_pct,
        "warning_pct": warning_pct,
        "watchlist": watchlist,
        "freshness": _freshness(latest),
        "pending": summarize_pending(history, vals),
        "generated_at": datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=7))),
    }


# ---------------------------------------------------------------- render helpers

def _n(value: Optional[float], decimals: int = 1, suffix: str = "") -> str:
    """Số kiểu Việt hoặc '—' khi thiếu — KHÔNG bao giờ in 0 thay cho thiếu."""
    if value is None:
        return '<span class="na">chưa có dữ liệu</span>'
    text = f"{value:,.{decimals}f}".translate(str.maketrans({",": ".", ".": ","}))
    return f"{text}{suffix}"


def _tile(label: str, value: str, delta: str, flag: bool = False) -> str:
    cls = " flag" if flag else ""
    return (
        f'<div class="card tile"><div class="label">{html.escape(label)}</div>'
        f'<div class="value">{value}</div>'
        f'<div class="delta{cls}">{delta}</div></div>'
    )


def _status_card(level: str, tag: str, body: str) -> str:
    return (
        f'<div class="status-card {level}"><div class="tag">● {html.escape(tag)}</div>'
        f'<div class="body">{body}</div></div>'
    )


def _deposit_holding_section(ranked: list[dict]) -> str:
    """Khoản tiết kiệm ĐANG NẮM — 21% tài sản, và sẽ thành ~35% nếu thực hiện
    kế hoạch giảm tỷ trọng vàng.

    Trang này liệt kê lãi suất thị trường từ đầu nhưng chưa lần nào nói về
    chính khoản tiền của chủ danh mục: đang ở ngân hàng nào, lãi bao nhiêu,
    bao giờ đáo hạn. Hệ thống tối ưu tiền SẮP có mà không nhìn tiền ĐANG có.
    """
    try:
        from deposits.holding import (from_portfolio, maturity_alert, rate_gap_table,
                                      undeclared_note)

        port = load_portfolio()
        h = from_portfolio(port, deposit_cfg=port.savings_raw)
    except Exception:  # noqa: BLE001 — thiếu thẻ này không được làm hỏng trang
        return ""
    if not h.principal_vnd:
        return ""
    best = ranked[0]["rate_pct"] if ranked else None

    if not h.is_declared:
        gaps = rate_gap_table(h.principal_vnd, best)
        note = undeclared_note(h.principal_vnd, gaps)
        table = ""
        if gaps:
            # Bảng nằm ở SECTION rộng chứ không nhét vào thẻ rủi ro: thẻ rủi ro
            # rộng ~300px nên cột "chênh mỗi năm" — đúng con số duy nhất đáng
            # xem ở đây — sẽ bị đẩy ra ngoài khung.
            rows = "\n".join(
                f'<tr><td class="tk">{_n(g.assumed_rate_pct, 1)}%/năm</td>'
                f"<td>{_n(g.best_rate_pct, 2)}%/năm</td><td>{_n(g.gap_pct, 2)}%</td>"
                f'<td style="color:var(--st-warning-text);font-weight:600">'
                f"{_n(g.gap_per_year_vnd / 1_000_000, 1)} tr/năm</td></tr>"
                for g in gaps
            )
            table = f"""
    <div class="table-scroll">
      <table>
        <thead><tr><th>Nếu đang ở</th><th>Mức tốt nhất đo được</th><th>Chênh</th>
          <th>Trên {_n(h.principal_vnd / 1_000_000, 0)} tr</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <p class="card-note" style="margin:12px 0 0">Mỗi dòng là một <b>giả định</b> để đo khoảng
      chưa biết — không phải phán đoán về mức thật của bạn. Điền
      <code>bank / rate_pct / term_months / start_date</code> trong
      <code>config/portfolio.yaml</code> là mục này chuyển thành theo dõi thật.</p>"""
        return f"""
  <section class="card">
    <h2 class="card-title">Khoản tiết kiệm đang gửi — chưa khai báo</h2>
    <p class="card-note">{note}</p>{table}
  </section>
"""

    bits = [f"<b>{_n(h.principal_vnd / 1_000_000, 0)} tr</b> @ "
            f"<b>{_n(h.rate_pct, 2)}%/năm</b>"
            + (f" · {html.escape(h.bank)}" if h.bank else "")
            + (f" · kỳ hạn {h.term_months} tháng" if h.term_months else "") + "."]
    lai = h.accrued_interest_vnd()
    if lai is not None:
        bits.append(f"Lãi tích lũy tới nay: <b>{_n(lai / 1_000_000, 1)} tr</b>.")
    if best and h.rate_pct < best:
        gap = (best - h.rate_pct) / 100 * h.principal_vnd / 1_000_000
        bits.append(f"⚠️ Thấp hơn mức tốt nhất đang đo được ({_n(best, 2)}%/năm) — "
                    f"chênh <b>{_n(gap, 1)} tr/năm</b>.")
    alert = maturity_alert(h)
    if alert:
        bits.append(("🔴 " if alert.level == "critical" else "⚠️ ") + html.escape(alert.message))
    return f"""
  <section class="card">
    <h2 class="card-title">Khoản tiết kiệm đang gửi</h2>
    <p class="card-note">{"<br>".join(bits)}</p>
  </section>
"""


def _goal_section(ctx: dict) -> str:
    """Mục tiêu 10 tỷ — và **cần gì** để nó khả thi.

    Đây là mục đứng đầu trang từ nay: mọi ngưỡng rủi ro phía dưới ("vàng ≥70%")
    chỉ có nghĩa khi neo vào một mục tiêu. Trước khi có mục này, "70%" là con số
    tuỳ tiện, và khuyến nghị tuỳ tiện thì bị bỏ qua — đã xảy ra suốt 19 kỳ.
    """
    try:
        from planning.feasibility import GoalReality, best_lever, horizon_table
        from planning.plan import load_plan

        plan = load_plan()
        vals = ctx.get("valuations") or []
        latest = vals[-1] if vals else None
        if not plan.goals or latest is None or not latest.total_trieu:
            return ""
        goal = plan.goals[0]
        total = latest.total_trieu
        target = goal.target_vnd / 1_000_000
        ranked = _ranked_deposit_rates()
        safe = ranked[0]["rate_pct"] if ranked else None
        rows = horizon_table(total, target, plan.inflation_pct, risk_free_pct=safe)
    except Exception:  # noqa: BLE001 — thiếu mục này không được làm hỏng trang
        return ""

    band_class = {"risk_free": "good", "moderate": "good",
                  "aggressive": "warning", "unrealistic": "critical"}
    band_color = {"risk_free": "--good-text", "moderate": "--good-text",
                  "aggressive": "--st-warning-text", "unrealistic": "--st-critical"}
    trs = "\n".join(
        f'<tr><td class="tk">{r.years} năm</td>'
        f"<td>{_n(r.required_return_pct, 2)}%</td>"
        f'<td class="na">{_n(r.required_real_return_pct, 2)}%</td>'
        f"<td><b>{(_n(r.required_monthly_trieu, 1) + ' tr/tháng') if r.required_monthly_trieu else 'không cần'}</b></td>"
        f"<td>{_n(r.value_from_current_trieu, 0)} tr</td>"
        f'<td style="color:var({band_color.get(r.band, "--text-secondary")});font-weight:600">'
        f"{html.escape(r.band_label)}</td></tr>"
        for r in rows
    )
    reality = GoalReality(target, 20, plan.inflation_pct)
    lever = best_lever(rows)
    return f"""
  <section class="card">
    <h2 class="card-title">Mục tiêu: {html.escape(goal.name)}</h2>
    <p class="card-note">Hiện có <b>{_n(total, 0)} tr</b> → cần <b>{_n(target, 0)} tr</b>,
      tức gấp <b>{_n(target / total, 2)} lần</b>. Thời hạn <b>chưa chốt</b> — và đó là biến quyết
      định tất cả, nên bảng dưới đây là câu trả lời thay cho một con số lợi suất duy nhất.</p>
    <div class="table-scroll">
      <table>
        <thead><tr><th>Thời hạn</th><th>Lợi suất cần<br><span style="font-weight:400">nếu KHÔNG gửi thêm</span></th>
          <th>(thực)</th><th>Hoặc gửi thêm<br><span style="font-weight:400">chỉ với lãi tiền gửi</span></th>
          <th>Tài sản hiện có<br><span style="font-weight:400">tự lên tới</span></th><th>Phân loại</th></tr></thead>
        <tbody>{trs}</tbody>
      </table>
    </div>
    <div class="status-cards" style="margin-top:16px">
      {_status_card("good", "Đòn bẩy mạnh nhất", html.escape(lever))}
      {_status_card("warning", "Danh nghĩa hay sức mua?", html.escape(reality.note))}
    </div>
    <p class="card-note" style="margin:14px 0 0">Mốc phân loại thấp nhất neo vào
      <b>lãi suất tiền gửi tốt nhất đang đo được</b> (số thật). Hai mốc 12% và 20% là
      <b>nhận định</b> về mức bền vững, không phải số đo — nêu rõ để không bị đọc nhầm thành dự báo.</p>
  </section>
"""


def _purchasing_power_section(ctx: dict) -> str:
    """Sức mua — tầng mà cả hệ thống đang thiếu cho tới hôm nay.

    Mọi con số trên trang này (và trong mọi bản tin đã gửi) đều là DANH NGHĨA.
    Với CPI 7 tháng 2026 +4,39%, "tiền mặt 35 tr không đổi" thực ra là đang mất
    1,47 tr sức mua mỗi năm — và chưa kỳ nào nói điều đó.
    """
    try:
        from planning.plan import load_plan, sensitivity
        from planning.real_return import (doubling_years, erosion_trieu,
                                          purchasing_power_trieu, real_pct)

        plan = load_plan()
        vals = ctx.get("valuations") or []
        latest = vals[-1] if vals else None
        if not plan.inflation_pct or latest is None or not latest.total_trieu:
            return ""
        total = latest.total_trieu
        cash = latest.cash_trieu
        rows10 = sensitivity(total, plan.inflation_pct, 10)
        ranked = _ranked_deposit_rates()
        best = ranked[0]["rate_pct"] if ranked else None
    except Exception:  # noqa: BLE001 — thiếu mục này không được làm hỏng trang
        return ""

    pp10 = purchasing_power_trieu(total, plan.inflation_pct, 10)
    cash_real = real_pct(0.0, plan.inflation_pct)
    tiles = [
        _tile("Lạm phát tham chiếu", f"{_n(plan.inflation_pct, 2)}%/năm", "CPI bình quân 7 tháng 2026"),
        _tile("Tiền mặt — lợi suất THỰC", f"{_signed(cash_real, 2)}%",
              f"bào mòn {_n(erosion_trieu(cash, plan.inflation_pct), 2)} tr/năm", flag=True),
    ]
    if best:
        rr = real_pct(best, plan.inflation_pct)
        dbl = doubling_years(rr)
        tiles.append(_tile("Gửi tốt nhất — lợi suất THỰC", f"{_signed(rr, 2)}%",
                           f"danh nghĩa {_n(best, 2)}%"
                           + (f" · gấp đôi sau ~{dbl:.0f} năm" if dbl else "")))
    tiles.append(_tile("Không sinh lời, sau 10 năm", f"{_n(pp10, 0)} tr",
                       f"theo sức mua hôm nay — mất {_n(total - pp10, 0)} tr", flag=True))

    trs = "\n".join(
        f'<tr><td class="tk">{_n(rate, 1)}%</td><td>{_n(nom, 0)} tr</td>'
        f"<td><b>{_n(real, 0)} tr</b></td>"
        # Phần MẤT sức mua phải nổi bật hơn, không phải mờ đi — dùng đúng cặp
        # màu đã kiểm CVD ở biểu đồ kịch bản, để cả trang nói cùng một ngôn ngữ.
        f'<td style="color:var({"--s-orange" if real < total else "--s-blue"});'
        f'font-weight:600">{_signed(real - total, 0)} tr</td></tr>'
        for rate, nom, real in rows10
    )
    goal_note = ("" if plan.has_goals else
                 '<p class="card-note" style="margin:12px 0 0">⚠️ Chưa khai mục tiêu tài chính trong '
                 '<code>config/plan.yaml</code>. Thiếu mục tiêu thì mọi ngưỡng rủi ro đều là con số '
                 'tuỳ tiện — "vàng ≥70%" là 70% so với cái gì?</p>')
    return f"""
  <section class="card">
    <h2 class="card-title">Sức mua — không phải số dư</h2>
    <p class="card-note">Mọi con số phía trên là <b>danh nghĩa</b>. Sau lạm phát
      {_n(plan.inflation_pct, 2)}%/năm ({html.escape(plan.inflation_source)}), bức tranh khác đi.
      Lợi suất thực tính theo Fisher chính xác <code>(1+n)/(1+i)−1</code>, không phải phép trừ —
      phép trừ luôn lệch về phía lạc quan.</p>
    <div class="grid-tiles" style="margin-bottom:16px">{"".join(tiles)}</div>
    <p class="card-note">Toàn bộ <b>{_n(total, 0)} tr</b> sau 10 năm, ở từng mức lợi suất danh nghĩa.
      Đây là <b>bảng độ nhạy, không phải dự báo</b> — hệ thống không dự báo lợi suất.</p>
    <div class="table-scroll">
      <table>
        <thead><tr><th>Lợi suất/năm</th><th>Danh nghĩa</th><th>Sức mua hôm nay</th>
          <th>So với hiện tại</th></tr></thead>
        <tbody>{trs}</tbody>
      </table>
    </div>{goal_note}
  </section>
"""


def _equity_section(port) -> str:
    """Mục theo dõi kỹ thuật cho các mã trong `config/portfolio.yaml: watchlist`.

    Bảng watchlist Buffett-list bên dưới chỉ so giá gốc–giá hiện tại. Với 2 mã
    có chuỗi EOD thật (`data/eod/`) thì đo được nhiều hơn thế — và Decision
    Engine nhánh equity, vốn xây xong từ Phase 7, cũng chạy được ngay ở đây.
    """
    try:
        from equity.signals import analyze as eq_analyze
        from equity.signals import decide_for

        # `getattr` chứ không truy cập thẳng: mục này chỉ là phần thêm, không
        # được phép làm sập cả trang khi ngữ cảnh thiếu trường (test dùng port
        # giả đã bắt đúng trường hợp đó).
        from decision.position_size import plan_position
        from equity.signals import valuation_for

        held = {p.ticker.upper() for p in getattr(port, "stock_positions", []) if p.quantity}
        watch = [x.upper() for x in (getattr(port, "watchlist", None) or [])]
        limits = load_risk_limits() or {}
        ranked = _ranked_deposit_rates()
        hurdle = ranked[0]["rate_pct"] if ranked else None
        net = getattr(port, "_net_trieu", None)
    except Exception:  # noqa: BLE001 — thiếu mục này không được làm hỏng trang
        return ""
    rows = []
    for t in watch:
        s = eq_analyze(t)
        if not s.has_data:
            continue
        d = decide_for(s, has_position=t in held)
        view = valuation_for(s)
        plan = plan_position(
            t, s.close, net or 0.0, limits=limits,
            support=s.tech.get("support"), resistance=s.tech.get("resistance"),
            target=view.lowest.target_nghin_dong if view and view.lowest else None,
            hurdle_pct=hurdle,
        ) if net else None
        flags = []
        if s.tech.get("breakout") and s.tech["breakout"] != "NONE":
            flags.append(html.escape(s.tech["breakout"]))
        if s.volume_flag:
            flags.append("KLGD bất thường")
        mos = view.margin_of_safety_pct if view else None
        rows.append(
            f'<tr><td class="tk">{html.escape(t)}</td>'
            f"<td>{_n(s.close, 2)}</td>"
            f"<td>{_n(s.tech.get('rsi14'), 1) if s.tech.get('rsi14') is not None else '—'}</td>"
            f"<td>{_n(s.tech.get('support'), 2) if s.tech.get('support') is not None else '—'}</td>"
            f"<td>{(_n(mos, 1) + '%') if mos is not None else '—'}</td>"
            f"<td><b>{html.escape(d['action_vi'])}</b></td>"
            f'<td>{html.escape(plan.summary()) if plan else "—"}</td>'
            f'<td class="na">{" · ".join(flags) if flags else "—"}</td></tr>'
        )
    if not rows:
        return ""
    note = ("Đang <b>không nắm giữ</b> cổ phiếu nào — nên khuyến nghị dừng ở ĐỨNG NGOÀI / "
            "CHỜ XÁC NHẬN / MUA THĂM DÒ. Không có \"GIỮ\" cho mã không có vị thế: "
            "giữ thứ mình không sở hữu là lời khuyên không thực hiện được."
            if not held else
            "Khuyến nghị tính theo vị thế thật đang khai báo trong <code>config/portfolio.yaml</code>.")
    return f"""
  <section class="card">
    <h2 class="card-title">Theo dõi kỹ thuật — mã có dữ liệu EOD</h2>
    <p class="card-note">{note} Chỉ báo tính từ <code>data/eod/&lt;MÃ&gt;.csv</code> qua
      <code>equity/technical.py</code>; khuyến nghị do Decision Engine (nhánh equity) sinh ra,
      không viết tay. Giá nghìn đồng.</p>
    <div class="table-scroll">
      <table>
        <thead><tr><th>Mã</th><th>Giá</th><th>RSI(14)</th><th>Hỗ trợ</th>
          <th>Biên an toàn</th><th>Khuyến nghị</th><th>Kế hoạch vào lệnh</th><th>Cờ</th></tr></thead>
        <tbody>{"".join(rows)}</tbody>
      </table>
    </div>
  </section>
"""


def _signed(value: float, decimals: int = 0) -> str:
    """Số có dấu, định dạng Việt (1.234,5). Cột dương phải có dấu + để khớp
    nhãn trên biểu đồ — thiếu dấu ở một chỗ là bảng và hình nói khác nhau."""
    return f"{value:+,.{decimals}f}".translate(str.maketrans({",": ".", ".": ","}))


def _scenario_section(ctx: dict) -> str:
    """Rủi ro tập trung quy ra TIỀN — vế còn thiếu của khuyến nghị CHỐT BỚT.

    19 kỳ liền hệ thống nói "vàng 76%, vượt ngưỡng 70%": một tỷ lệ phần trăm so
    với một tỷ lệ phần trăm khác. Không kỳ nào nói rủi ro đó bằng bao nhiêu tiền.

    Bày ĐỐI XỨNG cả chiều tăng lẫn chiều giảm — chỉ bày kịch bản xấu là dẫn dắt
    bằng cách chọn dữ liệu.
    """
    try:
        from analytics.downside import (BIAS_NOTE, headline, measure_volatility,
                                         scenario_table)
        from portfolio.loader import load_portfolio

        vals = ctx.get("valuations") or []
        latest = vals[-1] if vals else None
        if latest is None or not latest.total_trieu or latest.gold_trieu is None:
            return ""
        rows = scenario_table(load_portfolio().gold_quantity_tael,
                              latest.total_trieu - latest.gold_trieu)
        if not rows:
            return ""
        vol = measure_volatility(ctx.get("history") or [])
    except Exception:  # noqa: BLE001 — thiếu mục này không được làm hỏng dashboard
        return ""

    bars = [Bar(label=f"{r.shock_pct:+.0f}%", value=r.change_trieu,
                sublabel=f"vàng {r.gold_pct_after:.0f}%") for r in rows]
    svg = diverging_bar_chart(bars, decimals=0, value_suffix=" tr",
                              aria_label="Thay đổi tổng tài sản theo kịch bản giá vàng")
    trs = "\n".join(
        f'<tr><td class="tk">{r.shock_pct:+.0f}%</td><td>{_n(r.xau_after, 0)} $</td>'
        f"<td>{_n(r.gold_price_after_trieu, 2)} tr</td><td>{_n(r.total_after_trieu, 0)} tr</td>"
        f'<td style="color:var({"--s-orange" if r.change_trieu < 0 else "--s-blue"});'
        f'font-weight:600">{_signed(r.change_trieu)} tr</td>'
        f"<td>{_n(r.gold_pct_after, 1)}%</td></tr>"
        for r in rows
    )
    return f"""
  <section class="card">
    <h2 class="card-title">Kịch bản giá vàng — rủi ro quy ra tiền</h2>
    <p class="card-note">Đây là số học "nếu…thì", <b>không phải dự báo</b> và không kèm xác suất nào.
      Bày đối xứng cả hai chiều vì chỉ bày kịch bản xấu là dẫn dắt bằng cách chọn dữ liệu.
      Cột = thay đổi tổng tài sản (triệu đồng) so với hiện tại; dấu +/− ghi thẳng trên cột nên
      nghĩa không phụ thuộc riêng vào màu.</p>
    <div class="table-scroll">{svg}</div>
    <div class="table-scroll">
      <table>
        <thead><tr><th>Kịch bản</th><th>XAU/USD</th><th>Giá tiệm</th><th>Tổng tài sản</th>
          <th>Thay đổi</th><th>% vàng sau</th></tr></thead>
        <tbody>{trs}</tbody>
      </table>
    </div>
    <p class="card-note" style="margin:12px 0 0">{html.escape(headline(rows))}<br>
      {html.escape(vol.caveat)}<br>
      {html.escape(BIAS_NOTE)}.</p>
  </section>
"""


def _data_quality_card(history: list[dict]) -> str:
    """Thẻ "tin số trên trang này tới mức nào" — đo, không tự nhận.

    Đặt ngay trong mục rủi ro chứ không giấu ở chân trang: mọi con số phía dưới
    (tỷ trọng vàng, khuyến nghị, điểm tin cậy) đều thừa hưởng chất lượng của
    những nguồn này. Trước đây điểm tin cậy 92/100 hiện trong bản tin mà không
    có chỗ nào cho người đọc kiểm lại nó dựa trên dữ liệu cũ tới đâu.
    """
    try:
        from analytics.data_quality import assess_gold

        a = assess_gold(history)
    except Exception:  # noqa: BLE001 — thiếu thẻ này không được làm hỏng dashboard
        return ""
    level = "good" if a.freshness_score >= 80 else ("warning" if a.freshness_score > 0 else "critical")
    parts = [
        f"Độ đầy đủ <b>{a.completeness_pct:.0f}/100</b> · độ mới <b>{a.freshness_score:.0f}/100</b>."
    ]
    if a.binding and a.freshness_score < 100:
        parts.append(f"Bị ghìm bởi {html.escape(a.binding)}.")
    # Mỗi nguồn nói MỘT lần. Nguồn ghìm điểm đã nêu ở câu trên, và nguồn đối
    # chiếu cũ đã có ghi chú đầy đủ hơn — liệt kê lại chỉ làm thẻ dài mà không
    # thêm thông tin, và thẻ dài thì người ta ngừng đọc.
    covered = (a.binding or "") + " ".join(a.notes)
    for item in a.stale:
        if item.split(":")[0] not in covered:
            parts.append(f"• {html.escape(item)}")
    for note in a.notes:
        parts.append(f"• {html.escape(note)}")
    parts.append("Điểm này đi thẳng vào <b>tin cậy</b> của khuyến nghị — dữ liệu cũ thì "
                 "điểm tin cậy phải giảm theo, không được giữ nguyên.")
    return _status_card(level, "Chất lượng dữ liệu nền", "<br>".join(parts))


def _ranked_deposit_rates() -> list[dict]:
    """Lãi suất đã xếp hạng, [] nếu chưa có — không để lỗi đọc file phá cả trang."""
    try:
        from deposits.ranking import load_normalized, rank

        rates = load_normalized()
        return rank(rates) if rates else []
    except Exception:  # noqa: BLE001
        return []


def last_real_index(values: list[Optional[float]]) -> Optional[int]:
    """Vị trí giá trị có thật gần nhất, None nếu chuỗi trống hoàn toàn."""
    for i in range(len(values) - 1, -1, -1):
        if values[i] is not None:
            return i
    return None


def series_end_note(values: list[Optional[float]], labels: list[str], what: str) -> str:
    """Câu ghi rõ chuỗi dừng ở kỳ nào và vì sao — thay vì để nửa biểu đồ trống
    mà người đọc không biết là hỏng hay là chưa có nguồn.

    Nảy sinh từ thực tế: từ 27/7 task tự động chỉ lấy được XAU/USD + tỷ giá +
    giá cổ phiếu; giá SJC/nhẫn trong nước, VN-Index, khối ngoại và lãi suất
    KHÔNG có nguồn tự động (xem README) nên các chuỗi đó dừng lại giữa đường.
    """
    idx = last_real_index(values)
    if idx is None:
        return f"Chưa có kỳ nào ghi nhận {what}."
    if idx == len(values) - 1:
        return ""
    thieu = len(values) - 1 - idx
    return (f"⚠️ Chuỗi {what} dừng ở kỳ <b>{html.escape(labels[idx])}</b> "
            f"({thieu} kỳ sau đó không có số liệu) — chưa có nguồn tự động, "
            "cần nhập tay qua <code>scripts/trend.py append</code>.")


def latest_snapshot_with(history: list[dict], key: str) -> Optional[dict]:
    """Snapshot mới nhất CÓ trường `key` — để hiển thị số liệu gần nhất còn
    dùng được kèm ngày, thay vì bỏ trống thẻ khi kỳ này thiếu."""
    for snap in reversed(history):
        if snap.get(key):
            return snap
    return None


def _delta_text(series: list[Optional[float]], decimals: int = 1, suffix: str = "") -> str:
    """'▲ 3,8 so với kỳ trước' — so sánh 2 giá trị có thật gần nhất."""
    real = [v for v in series if v is not None]
    if len(real) < 2:
        return "chưa có kỳ trước để so sánh"
    diff = real[-1] - real[-2]
    if abs(diff) < 10 ** -decimals / 2:
        return "đi ngang so với kỳ trước"
    arrow = "▲" if diff > 0 else "▼"
    return f"{arrow} {_n(abs(diff), decimals, suffix)} so với kỳ trước"


def render(ctx: dict) -> str:
    hist = ctx["history"]
    labels = ctx["labels"]
    vals = ctx["valuations"]
    cur = ctx["current"]
    latest = ctx["latest"]
    port = ctx["portfolio"]
    x_labels = thin_labels(labels)

    ky_vi = KY_VI.get(latest.get("ky", ""), latest.get("ky", ""))
    date_parts = (latest.get("date") or "").split("-")
    date_vi = f"{date_parts[2]}/{date_parts[1]}/{date_parts[0]}" if len(date_parts) == 3 else latest.get("date", "")

    fresh_label, fresh_level = ctx["freshness"]

    # --- Thẻ số liệu -------------------------------------------------------
    totals = [v.total_trieu for v in vals]
    golds = [v.gold_trieu for v in vals]
    gold_pcts = [v.gold_pct * 100 if v.gold_pct is not None else None for v in vals]
    critical = ctx["critical_pct"]
    over_critical = (
        cur.gold_pct is not None and critical is not None and cur.gold_pct * 100 >= critical
    )

    # Khoảng sai số của ước tính giá vàng, đo từ dữ liệu thật — để con số 76%
    # không trông chắc chắn hơn thực tế.
    band = ctx.get("gold_band")
    gold_delta = (f"{_n((cur.gold_pct or 0) * 100)}% tổng tài sản"
                  + (f" — vượt ngưỡng critical {_n(critical, 0)}%" if over_critical else ""))
    if band and cur.gold_trieu:
        lo = port.gold_quantity_tael * band.low_trieu
        hi = port.gold_quantity_tael * band.high_trieu
        other = (cur.total_trieu or 0) - cur.gold_trieu
        lo_pct = lo / (lo + other) * 100 if (lo + other) else 0
        hi_pct = hi / (hi + other) * 100 if (hi + other) else 0
        gold_delta += (f"<br><span style=\"font-weight:400;color:var(--text-muted)\">"
                       f"khoảng {_n(lo, 0)}–{_n(hi, 0)} tr → {_n(lo_pct)}–{_n(hi_pct)}%</span>")

    tiles = "".join([
        _tile("Tổng tài sản (ước tính)", _n(cur.total_trieu, 1, " tr"), _delta_text(totals, 1, " tr")),
        _tile(
            f"Vàng nhẫn — {_n(port.gold_quantity_tael, 1)} lượng",
            _n(cur.gold_trieu, 1, " tr"),
            gold_delta,
            flag=over_critical,
        ),
        _tile("Tiết kiệm", _n(cur.savings_trieu, 0, " tr"),
              f"{_n((cur.savings_trieu / cur.total_trieu * 100) if cur.total_trieu else None)}% tổng tài sản"),
        _tile("Tiền mặt", _n(cur.cash_trieu, 0, " tr"),
              f"{_n((cur.cash_trieu / cur.total_trieu * 100) if cur.total_trieu else None)}% tổng tài sản"),
    ])

    # --- Phân bổ tài sản ---------------------------------------------------
    segs = [
        Segment("Vàng nhẫn", cur.gold_trieu or 0, "--s-yellow"),
        Segment("Tiết kiệm", cur.savings_trieu, "--s-blue"),
        Segment("Tiền mặt", cur.cash_trieu, "--s-aqua"),
    ]
    alloc_note = (
        f"Risk Officer: vàng ≥ {_n(critical, 0)}% → KHÔNG mua thêm vàng (ngưỡng trong "
        "<code>config/risk_limits.yaml</code>)." if critical else
        "Ngưỡng tập trung chưa cấu hình trong <code>config/risk_limits.yaml</code>."
    )

    # --- Tổng tài sản + tỷ trọng vàng theo thời gian -----------------------
    total_series = [Series("Tổng tài sản", totals, "--s-violet", " tr")]
    pct_series = [Series("Tỷ trọng vàng", gold_pcts, "--s-yellow", "%")]
    # Ngưỡng rủi ro vẽ như 1 chuỗi phẳng để thấy khoảng cách tới ngưỡng — cùng
    # đơn vị %, nên hợp lệ trên chung 1 trục (không phải trục thứ hai).
    if critical is not None:
        pct_series.append(Series(f"Ngưỡng critical {_n(critical, 0)}%",
                                 [float(critical)] * len(gold_pcts), "--s-red", "%", end_label=False))

    # --- Giá vàng ----------------------------------------------------------
    gold_series = [
        Series("SJC bán", [(s.get("gold") or {}).get("sjc_sell") for s in hist], "--s-red", " tr"),
        Series("Nhẫn bán", [(s.get("gold") or {}).get("ring_sell") for s in hist], "--s-orange", " tr"),
        Series("SJC mua", [(s.get("gold") or {}).get("sjc_buy") for s in hist], "--s-blue", " tr"),
    ]
    xau_series = [Series("XAU/USD", [(s.get("gold") or {}).get("xauusd") for s in hist], "--s-magenta", " $")]
    premium_series = [Series("Chênh lệch VN–TG", [s.get("gold", {}).get("premium_trieu") for s in hist],
                             "--s-green", " tr")]

    # --- VN-Index + khối ngoại --------------------------------------------
    vnindex_series = [Series("VN-Index", [(s.get("vnindex") or {}).get("close") for s in hist], "--s-blue")]
    foreign = [s.get("foreign_net_ty") for s in hist]

    # --- Lãi suất ----------------------------------------------------------
    # Lãi suất đổi chậm và KHÔNG có nguồn tự động, nên dùng snapshot gần nhất
    # có số liệu thay vì bỏ trống thẻ — kèm ngày và cảnh báo nếu đã cũ.
    deposit_snap = latest_snapshot_with(hist, "deposit_top")
    deposits = (deposit_snap or {}).get("deposit_top") or []
    deposit_date = (deposit_snap or {}).get("date")
    deposit_stale_days = None
    if deposit_date and latest.get("date"):
        try:
            deposit_stale_days = (
                datetime.strptime(latest["date"], "%Y-%m-%d")
                - datetime.strptime(deposit_date, "%Y-%m-%d")
            ).days
        except ValueError:
            deposit_stale_days = None
    if not deposit_date:
        deposit_note = "Chưa kỳ nào ghi nhận lãi suất."
    elif deposit_stale_days:
        deposit_note = (
            f"%/năm theo snapshot <b>{html.escape(deposit_date)}</b> — "
            f"⚠️ đã {deposit_stale_days} ngày không cập nhật (lãi suất không có nguồn tự động; "
            "cập nhật qua <code>scripts/trend.py append</code>). Cột mọc từ gốc 0."
        )
    else:
        deposit_note = "%/năm, tiền gửi dưới 1 tỷ, theo snapshot kỳ này. Cột mọc từ gốc 0."
    deposit_bars = [
        Bar(d.get("bank", "?"), float(d.get("rate_pct") or 0), "--s-blue",
            f"kỳ hạn {d.get('term_months')} tháng")
        for d in deposits if d.get("rate_pct")
    ]
    savings_note = ""
    if deposit_bars and cur.savings_trieu:
        best = max(deposit_bars, key=lambda b: b.value)
        yearly = cur.savings_trieu * best.value / 100
        savings_note = (
            f"Lãi dự kiến cho {_n(cur.savings_trieu, 0)} tr ở mức cao nhất "
            f"({html.escape(best.label)} {_n(best.value, 2)}%/năm): "
            f"<b>{_n(yearly, 1)} tr/năm</b> ({_n(yearly / 12, 2)} tr/tháng)."
        )

    # --- Thẻ rủi ro từ risk_flags của snapshot ----------------------------
    flags = latest.get("risk_flags") or {}
    risk_cards: list[str] = []
    pending = ctx["pending"]
    if pending.get("message"):
        risk_cards.append(_status_card("critical", pending["tag"], pending["message"]))
    dq_card = _data_quality_card(ctx.get("history") or [])
    if dq_card:
        risk_cards.append(dq_card)
    for key, tag, level in [
        ("war", "Địa chính trị / chiến sự", "warning"),
        ("trump", "Động thái Trump / thuế quan", "warning"),
        ("fed", "Fed / lãi suất", "warning"),
        ("arrest", "Rủi ro pháp lý lãnh đạo doanh nghiệp", "good"),
    ]:
        text = flags.get(key)
        if text:
            risk_cards.append(_status_card(level, tag, html.escape(str(text))))
    # Ghi chú tự do trong snapshot: lấy nhãn từ CHÍNH tên khoá để 2 ghi chú
    # khác nhau không hiện cùng một tiêu đề (đã từng thấy 2 thẻ trùng nhãn).
    for key, value in sorted(flags.items()):
        if key.startswith("note_") and value:
            raw = key[len("note_"):]
            topic = NOTE_TOPIC_VI.get(raw, raw.replace("_", " ").strip() or "khác")
            risk_cards.append(_status_card("warning", f"Ghi chú: {topic}", html.escape(str(value))))
    if not risk_cards:
        risk_cards.append(_status_card("good", "Không có cờ rủi ro", "Snapshot mới nhất không ghi cờ rủi ro nào."))

    # --- Watchlist ---------------------------------------------------------
    rows = []
    for st in (ctx["watchlist"].get("stocks") or []):
        base, last = st.get("base_price"), st.get("last_price")
        if base and last:
            chg = (last - base) / base * 100
            cls = ("color:var(--st-critical);font-weight:600" if chg <= -3
                   else "color:var(--st-warning-text);font-weight:600" if chg < 0
                   else "color:var(--good-text);font-weight:600" if chg > 0 else "")
            chg_cell = f'<td style="{cls}">{_n(chg, 2, "%")}</td>' if chg else '<td class="chg-flat">0,00%</td>'
        else:
            chg_cell = '<td class="chg-flat">chưa có dữ liệu</td>'
        rows.append(
            f'<tr><td class="tk">{html.escape(st.get("ticker", "?"))}</td>'
            f'<td>{html.escape(st.get("group", ""))}</td>'
            f'<td>{_n(base, 2)}</td><td>{_n(last, 2)}</td>{chg_cell}'
            f'<td>{html.escape(st.get("moat", ""))}</td></tr>'
        )
    watchlist_rows = "\n".join(rows) or '<tr><td colspan="6" class="na">Chưa có mã nào trong watchlist.</td></tr>'
    base_date = ctx["watchlist"].get("base_date", "?")

    # --- Kế hoạch giảm tỷ trọng --------------------------------------------
    rb = ctx.get("rebalance")
    rebalance_section = ""
    if rb is not None and rb.needs_action and rb.steps:
        _rb_rows: list[str] = []
        for s in rb.steps:
            muc_tieu = _n(s.target_pct, 0) + "%"
            ban = f"<b>{s.chi_to_sell} chỉ</b> ({_n(s.tael_to_sell)} lượng)"
            thu_ve = _n(s.proceeds_trieu, 1) + " tr"
            pct_sau = _n(s.gold_pct_after, 1) + "%"
            thanh_khoan = _n(s.liquid_after_trieu, 0) + " tr"
            lai_them = ("+" + _n(s.extra_interest_per_year_trieu, 1) + " tr"
                        if s.extra_interest_per_year_trieu is not None else "—")
            phi = _n(s.spread_cost_trieu, 1) + " tr"
            _rb_rows.append(
                f'<tr><td class="tk">{muc_tieu}</td><td>{ban}</td><td>{thu_ve}</td>'
                f"<td>{pct_sau}</td><td>{thanh_khoan}</td>"
                f'<td style="color:var(--good-text);font-weight:600">{lai_them}</td>'
                f"<td>{phi}</td></tr>"
            )
        rows_rb = "\n".join(_rb_rows)
        rate_note = (f"Tiền thu về gửi ở <b>{html.escape(rb.best_rate_bank or '')} "
                     f"{_n(rb.best_rate_pct or 0, 2)}%/năm kỳ hạn {rb.best_rate_term} tháng</b>"
                     + (f" (lãi suất theo snapshot {html.escape(rb.rate_as_of)} — "
                        "kiểm tra lại trước khi gửi)" if rb.rate_as_of else "")
                     if rb.best_rate_pct else
                     "Chưa có lãi suất hợp lệ trong dữ liệu — cột lãi thêm để trống thay vì đoán.")
        rebalance_section = f"""
  <section class="card">
    <h2 class="card-title">Kế hoạch giảm tỷ trọng vàng — bán bao nhiêu là đủ</h2>
    <p class="card-note">Khuyến nghị <b>CHỐT BỚT</b> trả lời "làm gì" nhưng không nói "bao nhiêu" —
      đây là phần bù. Vàng nhẫn bán theo <b>chỉ</b> (1 lượng = 10 chỉ), số bán làm tròn LÊN để chạm
      được mục tiêu. Giá bán dùng <b>giá tiệm MUA vào</b> ({_n(rb.gold_price_sell_trieu, 2)} tr/lượng)
      — tiền thật nhận được, không phải giá niêm yết bán ra.<br>
      Chọn mốc nào là <b>khẩu vị của bạn</b>: mốc gần critical bán ít nhất nhưng sát mép (vàng tăng
      vài phần trăm là vượt ngưỡng lại); mốc {_n(rb.warning_pct, 0)}% thì hết cảnh báo tập trung.</p>
    <div class="table-scroll">
      <table>
        <thead><tr><th>Mục tiêu</th><th>Cần bán</th><th>Thu về</th><th>% vàng sau</th>
          <th>Thanh khoản sau</th><th>Lãi thêm/năm</th><th>Phí nếu mua lại</th></tr></thead>
        <tbody>{rows_rb}</tbody>
      </table>
    </div>
    <p class="card-note" style="margin:12px 0 0">{rate_note}<br>
      Cột cuối là chi phí chênh lệch mua–bán
      ({_n((rb.gold_price_buy_trieu or 0) - rb.gold_price_sell_trieu, 2)} tr/lượng) nếu sau này mua
      lại đúng số đã bán — nêu ra để quyết định là quyết định có biết giá, chưa trừ vào tổng.</p>
  </section>
"""

    scenario_section = _scenario_section(ctx)
    deposit_section = _deposit_holding_section(_ranked_deposit_rates())
    # Gắn tài sản ròng vào port để mục cổ phiếu tính được cỡ lệnh theo hạn mức.
    _vals = ctx.get("valuations") or []
    if _vals and _vals[-1].total_trieu:
        try:
            ctx["portfolio"]._net_trieu = _vals[-1].total_trieu
        except Exception:  # noqa: BLE001
            pass
    equity_section = _equity_section(ctx["portfolio"])
    power_section = _purchasing_power_section(ctx)
    goal_section = _goal_section(ctx)

    gen = ctx["generated_at"].strftime("%d/%m/%Y %H:%M")

    return f"""<title>Bản tin đầu tư — Duy</title>
{_CSS}
<div class="viz-root">
<div class="wrap">

  <header class="top">
    <h1>Bản tin đầu tư — Duy</h1>
    <div class="sub">Kỳ {html.escape(ky_vi)} {html.escape(date_vi)}
      <span class="badge {fresh_level}">{html.escape(fresh_label)}</span></div>
    <div class="sub gen">Trang này được <b>sinh tự động</b> từ <code>data/history.jsonl</code>
      ({len(hist)} snapshot) lúc {gen} (giờ VN) — không có số liệu nào nhập tay.</div>
  </header>

  <section class="grid-tiles">{tiles}</section>

  <section class="card">
    <h2 class="card-title">Phân bổ tài sản</h2>
    <p class="card-note">{alloc_note}</p>
    {stacked_bar(segs)}
    {allocation_legend(segs)}
  </section>
{goal_section}
{power_section}
{rebalance_section}
{scenario_section}
{deposit_section}
{equity_section}

  <section class="two-col">
    <div class="card">
      <h2 class="card-title">Tổng tài sản theo thời gian</h2>
      <p class="card-note">Triệu đồng. Định giá lại từng kỳ theo giá vàng của chính kỳ đó — số lượng
        tài sản không đổi, nên đường này là biến động GIÁ, không phải mua/bán.</p>
      {line_chart(total_series, x_labels, decimals=0, aria_label="Tổng tài sản theo thời gian")}
    </div>
    <div class="card">
      <h2 class="card-title">Tỷ trọng vàng vs ngưỡng rủi ro</h2>
      <p class="card-note">%. Đường đỏ là ngưỡng critical trong <code>config/risk_limits.yaml</code> —
        khoảng cách tới nó là mức độ lệch khỏi khẩu vị rủi ro đã đặt.</p>
      {line_chart(pct_series, x_labels, decimals=1, aria_label="Tỷ trọng vàng so với ngưỡng rủi ro")}
      {legend(pct_series)}
    </div>
  </section>

  <section class="two-col">
    <div class="card">
      <h2 class="card-title">Giá vàng trong nước — toàn bộ lịch sử</h2>
      <p class="card-note">Triệu đồng/lượng, giá niêm yết. Chỗ khuyết = kỳ đó không có số liệu
        (đường bị ngắt, không nội suy).<br>{
        series_end_note(list(gold_series[1].values), labels, "giá vàng trong nước")}</p>
      {line_chart(gold_series, x_labels, decimals=1, aria_label="Giá vàng trong nước theo kỳ")}
      {legend(gold_series)}
    </div>
    <div class="card">
      <h2 class="card-title">Vàng thế giới (XAU/USD)</h2>
      <p class="card-note">USD/oz. Tách riêng khỏi giá trong nước vì khác đơn vị —
        không bao giờ ghép 2 trục y vào một biểu đồ.</p>
      {line_chart(xau_series, x_labels, decimals=0, aria_label="Giá vàng thế giới XAU/USD")}
    </div>
  </section>

  <section class="two-col">
    <div class="card">
      <h2 class="card-title">Chênh lệch vàng VN – thế giới</h2>
      <p class="card-note">Triệu đồng/lượng. Chênh lệch nới rộng = mua trong nước đắt hơn so với
        giá trị quốc tế; thu hẹp = giá trong nước đang điều chỉnh về sát thế giới.<br>{
        series_end_note(list(premium_series[0].values), labels, "chênh lệch VN–TG")}</p>
      {line_chart(premium_series, x_labels, decimals=1, aria_label="Chênh lệch giá vàng VN và thế giới")}
    </div>
    <div class="card">
      <h2 class="card-title">Lãi suất tiết kiệm &lt; 1 tỷ</h2>
      <p class="card-note">{deposit_note}</p>
      {bar_chart(deposit_bars, decimals=2, value_suffix="%", aria_label="Lãi suất tiết kiệm top ngân hàng")
        or '<p class="na">Chưa có kỳ nào ghi nhận lãi suất.</p>'}
      <p class="card-note" style="margin:10px 0 0">{savings_note}</p>
    </div>
  </section>

  <section class="card">
    <h2 class="card-title">VN-Index theo kỳ</h2>
    <p class="card-note">Điểm. Khối ngoại kỳ này: <b>{
      ('mua ròng ' + _n(foreign[-1], 0, ' tỷ')) if (foreign[-1] or 0) > 0
      else ('bán ròng ' + _n(abs(foreign[-1]), 0, ' tỷ')) if foreign[-1]
      else 'chưa có dữ liệu'}</b>.<br>{
      series_end_note(list(vnindex_series[0].values), labels, "VN-Index")}</p>
    {line_chart(vnindex_series, x_labels, decimals=0, aria_label="VN-Index theo kỳ",
                box=Box(width=700, height=220))}
  </section>

  <section class="card">
    <h2 class="card-title">Rủi ro cần theo dõi</h2>
    <p class="card-note">Lấy nguyên văn cờ rủi ro từ snapshot — thuật ngữ pháp lý giữ đúng như nguồn,
      không quy kết khi nguồn chỉ nói đang xác minh.</p>
    <div class="status-cards">{"".join(risk_cards)}</div>
  </section>

  <section class="card">
    <h2 class="card-title">Watchlist cổ phiếu</h2>
    <p class="card-note">Đã bán hết cổ phiếu thực tế — đây là danh sách theo dõi (Buffett-list),
      gốc so sánh {html.escape(str(base_date))}. Giá nghìn đồng.</p>
    <div class="table-scroll">
      <table>
        <thead><tr><th>Mã</th><th>Nhóm</th><th>Giá gốc</th><th>Giá gần nhất</th>
          <th>Biến động</th><th>Lợi thế cạnh tranh</th></tr></thead>
        <tbody>{watchlist_rows}</tbody>
      </table>
    </div>
  </section>

  <footer class="foot">
    Nguồn: <code>data/history.jsonl</code> ({len(hist)} snapshot),
    <code>config/portfolio.yaml</code>, <code>config/risk_limits.yaml</code>,
    <code>data/watchlist.json</code>, <code>data/gold_model.json</code> —
    repo Finance-duy, nhánh <code>claude/investment-news-aggregator-w81l70</code>.<br>
    {(f"Giá vàng tiệm là ƯỚC TÍNH. {html.escape(ctx['gold_band'].note)} "
      f"Gửi ảnh bảng giá tiệm mới để siết MỨC giá (hiện chỉ "
      f"{ctx['gold_band'].level_sample_size} mẫu)."
      if ctx.get("gold_band") else
      "Giá vàng tiệm là ƯỚC TÍNH từ XAU/USD qua mô hình hiệu chuẩn 1 mẫu — "
      "gửi ảnh bảng giá mới để tăng độ chính xác.")}<br>
    Đây là công cụ hỗ trợ theo dõi cá nhân, không phải khuyến nghị đầu tư từ tổ chức được cấp phép.
  </footer>

</div>
</div>"""


_CSS = """<style>
  .viz-root {
    color-scheme: light;
    --page:#f9f9f7; --surface-1:#fcfcfb; --text-primary:#0b0b0b; --text-secondary:#52514e;
    --text-muted:#898781; --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,0.10);
    --good-text:#006300;
    --s-blue:#2a78d6; --s-green:#008300; --s-magenta:#e87ba4; --s-yellow:#eda100;
    --s-aqua:#1baf7a; --s-orange:#eb6834; --s-violet:#4a3aa7; --s-red:#e34948;
    --st-good:#0ca30c; --st-warning:#fab219; --st-critical:#d03b3b; --st-warning-text:#a06400;
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    background: var(--page); color: var(--text-primary);
  }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) .viz-root {
      color-scheme: dark;
      --page:#0d0d0d; --surface-1:#1a1a19; --text-primary:#ffffff; --text-secondary:#c3c2b7;
      --text-muted:#898781; --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
      --good-text:#0ca30c;
      --s-blue:#3987e5; --s-green:#008300; --s-magenta:#d55181; --s-yellow:#c98500;
      --s-aqua:#199e70; --s-orange:#d95926; --s-violet:#9085e9; --s-red:#e66767;
      --st-warning-text:#fab219;
    }
  }
  :root[data-theme="dark"] .viz-root {
    color-scheme: dark;
    --page:#0d0d0d; --surface-1:#1a1a19; --text-primary:#ffffff; --text-secondary:#c3c2b7;
    --text-muted:#898781; --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
    --good-text:#0ca30c;
    --s-blue:#3987e5; --s-green:#008300; --s-magenta:#d55181; --s-yellow:#c98500;
    --s-aqua:#199e70; --s-orange:#d95926; --s-violet:#9085e9; --s-red:#e66767;
    --st-warning-text:#fab219;
  }
  * { box-sizing: border-box; }
  body { margin: 0; }
  .viz-root { min-height: 100%; padding: 24px 16px 48px; }
  .wrap { max-width: 960px; margin: 0 auto; }
  header.top { margin-bottom: 24px; }
  header.top h1 { font-size: 1.5rem; margin: 0 0 6px; }
  header.top .sub { color: var(--text-secondary); font-size: 0.9rem; }
  header.top .gen { color: var(--text-muted); font-size: 0.78rem; margin-top: 4px; }
  .badge { display:inline-block; padding:1px 8px; border-radius:999px; font-size:.72rem;
           font-weight:600; margin-left:4px; }
  .badge.ok { background:rgba(12,163,12,.15); color:var(--good-text); }
  .badge.warn { background:rgba(250,178,25,.18); color:var(--st-warning-text); }
  .badge.bad { background:rgba(208,59,59,.15); color:var(--st-critical); }
  .card { background: var(--surface-1); border: 1px solid var(--border);
          border-radius: 12px; padding: 18px 20px; }
  .grid-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 12px; margin-bottom: 16px; }
  .tile .label { color: var(--text-secondary); font-size: 0.8rem; margin-bottom: 6px; }
  .tile .value { font-size: 1.6rem; font-weight: 600; }
  .tile .delta { font-size: 0.8rem; margin-top: 4px; color: var(--text-muted); }
  .tile .delta.flag { color: var(--st-warning-text); font-weight: 600; }
  section { margin-bottom: 16px; }
  h2.card-title { font-size: 1rem; margin: 0 0 4px; }
  .card-note { color: var(--text-muted); font-size: 0.78rem; margin: 0 0 14px; line-height:1.5; }
  .legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 0.8rem;
            color: var(--text-secondary); margin-top: 10px; }
  .legend .item { display: flex; align-items: center; gap: 6px; }
  .swatch { width: 10px; height: 10px; border-radius: 2px; flex: none; }
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  @media (max-width: 760px) { .two-col { grid-template-columns: 1fr; } }
  svg { display: block; max-width: 100%; overflow: visible; }
  svg text { fill: var(--text-secondary); font-size: 11px; }
  svg .muted { fill: var(--text-muted); }
  svg .axis-line { stroke: var(--axis); stroke-width: 1; }
  svg .grid-line { stroke: var(--grid); stroke-width: 1; }
  .status-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
  .status-card { border-left: 3px solid var(--st-warning); padding-left: 12px; }
  .status-card.critical { border-color: var(--st-critical); }
  .status-card.warning { border-color: var(--st-warning); }
  .status-card.good { border-color: var(--st-good); }
  .status-card .tag { display: inline-flex; align-items: center; gap: 6px; font-size: 0.72rem;
        font-weight: 700; text-transform: uppercase; letter-spacing: 0.02em; margin-bottom: 6px; }
  .status-card.critical .tag { color: var(--st-critical); }
  .status-card.warning .tag { color: var(--st-warning-text); }
  .status-card.good .tag { color: var(--good-text); }
  .status-card .body { font-size: 0.86rem; color: var(--text-primary); line-height: 1.5; }
  /* Bảng rộng phải TỰ cuộn ngang trong khung của nó — không được để thân
     trang cuộn ngang, cũng không bóp cột chữ thành sợi dọc trên điện thoại. */
  .table-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .table-scroll table { min-width: 560px; }
  /* Biểu đồ nhiều cột cũng vậy: ở 390px, SVG 620px co lại 55% làm chữ 11px
     còn ~6px — đúng thì có đúng nhưng không ai đọc được. Cuộn ngang giữ
     nguyên cỡ chữ, dùng lại đúng khuôn mẫu đã áp cho bảng. */
  .table-scroll > svg { min-width: 560px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  thead th { text-align: left; color: var(--text-muted); font-weight: 600; font-size: 0.75rem;
             text-transform: uppercase; letter-spacing: 0.02em; padding: 6px 10px;
             border-bottom: 1px solid var(--grid); }
  tbody td { padding: 8px 10px; border-bottom: 1px solid var(--grid);
             font-variant-numeric: tabular-nums; }
  tbody tr:last-child td { border-bottom: none; }
  .tk { font-weight: 600; font-variant-numeric: normal; }
  .chg-flat { color: var(--text-muted); }
  .na { color: var(--text-muted); font-style: italic; }
  footer.foot { margin-top: 24px; color: var(--text-muted); font-size: 0.78rem; line-height: 1.6; }
</style>"""


def main() -> None:
    ctx = build_context()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(render(ctx), encoding="utf-8")
    n = len(ctx["history"])
    print(f"Đã sinh {OUTPUT_PATH.relative_to(ROOT)} từ {n} snapshot "
          f"(kỳ mới nhất: {ctx['latest'].get('date')} {ctx['latest'].get('ky')}).")
    if ctx["pending"].get("message"):
        print(f"⚠️  {ctx['pending']['tag']}")


if __name__ == "__main__":
    main()

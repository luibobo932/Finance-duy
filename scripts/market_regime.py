#!/usr/bin/env python3
"""VN-Index đang ở vùng nào, và đã đến lúc gom hàng chưa.

Trả lời đúng một câu hỏi: **hai điều kiện gom hàng đã đủ chưa** —
(1) VN-Index ở đáy sâu so với lịch sử, (2) tin tức chứng khoán tiêu cực tràn
ngập. Xem `config/market_regime.yaml` để biết ngưỡng và vì sao chọn ngưỡng đó.

Cách dùng:
  python3 scripts/market_regime.py                 # báo cáo đầy đủ
  python3 scripts/market_regime.py --check         # ngắn gọn, exit 0 nếu ĐỦ ĐIỀU KIỆN
  python3 scripts/market_regime.py --json          # cho script khác đọc
  python3 scripts/market_regime.py --as-of 2022-11-15   # đo lại như thể hôm đó

Dữ liệu: `data/eod/VNINDEX.csv` (tải bằng `scripts/fetch_eod.py VNINDEX --index
--days 3000`, chạy trên máy không bị chặn services.entrade.com.vn) và
`data/market_news.jsonl` (`scripts/news_log.py add`).

Exit code của --check: 0 = đủ điều kiện gom, 1 = chưa/không đo được. Dùng để
nối vào cron/routine mà không phải parse chữ.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.news_sentiment import measure as measure_news  # noqa: E402
from equity.market_regime import (  # noqa: E402
    INDEX_SYMBOL,
    STATUS_VUNG_GOM,
    accumulation_signal,
    analyze,
    load_rules,
)

FETCH_HINT = (
    f"Chưa có `data/eod/{INDEX_SYMBOL}.csv`. Tải bằng:\n"
    f"    python3 scripts/fetch_eod.py {INDEX_SYMBOL} --index --days 3000\n"
    "(services.entrade.com.vn bị chặn trong sandbox Claude Code — chạy trên laptop.)"
)


def build(as_of: str | None = None) -> tuple[dict, object, object]:
    """Đo cả hai vế TẠI CÙNG MỘT MỐC THỜI GIAN.

    Mốc mặc định là NGÀY HỆ THỐNG, không phải ngày của snapshot bản tin mới
    nhất — đó là một lỗi thật đã gặp khi chạy thử: `data/history.jsonl` dừng ở
    06/08 trong khi tin tức được ghi ngày 16/08, nên toàn bộ tin mới bị phép
    đo coi là "tin của tương lai" và loại sạch, cho ra kết luận "chưa có tin
    nào" ngay sau khi vừa nhập ba tin. Độ cũ của dữ liệu giá nay được đo và
    báo riêng (`RegimeSnapshot.is_stale`) thay vì âm thầm bẻ cong mốc thời gian.
    """
    rules = load_rules()
    snap = analyze(rules=rules, today=as_of)
    news = measure_news(today=as_of, rules=rules)
    return accumulation_signal(snap, news, rules), snap, news


def report(signal: dict, snap, news) -> str:
    lines = [f"=== BỐI CẢNH THỊ TRƯỜNG — {signal['status_vi']} ==="]
    if not snap.has_data:
        lines.append("")
        lines.append(FETCH_HINT)
    else:
        lines.append(f"VN-Index {snap.close:,.2f} (EOD {snap.last_date}) — {snap.zone_vi}")
        lines.append(f"  {snap.evidence()}")
        for n in snap.notes:
            lines.append(f"  ⚠️ {n}")

    lines.append("")
    lines.append("Điều kiện gom hàng:")
    for c in signal["conditions"]:
        lines.append(f"  {c.mark} {c.name}: {c.evidence}")

    if signal["tranches"]:
        lines.append("")
        lines.append("Kế hoạch giải ngân từng bậc (tính từ đỉnh):")
        for t in signal["tranches"]:
            mark = "✅ đã tới" if t["reached"] else "chờ"
            lines.append(f"  - −{t['drawdown_pct']:.0f}% → VN-Index ≈ {t['index_level']:,.0f}: "
                         f"giải ngân {t['allocation_pct']:.0f}% phần tiền dành cho cổ phiếu [{mark}]")

    for w in signal["warnings"]:
        lines.append("")
        lines.append(f"⚠️ {w}")
    return "\n".join(lines)


def main() -> None:
    args = sys.argv[1:]
    as_of = args[args.index("--as-of") + 1] if "--as-of" in args else None
    signal, snap, news = build(as_of)

    if "--json" in args:
        print(json.dumps({
            "status": signal["status"],
            "zone": signal["zone"],
            "close": snap.close,
            "last_date": snap.last_date,
            "drawdown_pct": snap.drawdown_pct,
            "percentile": snap.percentile,
            "sessions": snap.sessions,
            "news": {"total": news.total, "negative": news.negative,
                     "ratio": news.negative_ratio, "measurable": news.measurable},
            "conditions": [{"name": c.name, "met": c.met, "evidence": c.evidence}
                           for c in signal["conditions"]],
            "warnings": signal["warnings"],
        }, ensure_ascii=False, indent=2))
    elif "--check" in args:
        print(signal["status_vi"] + " — " + "; ".join(
            f"{c.mark} {c.name}" for c in signal["conditions"]))
    else:
        print(report(signal, snap, news))

    sys.exit(0 if signal["status"] == STATUS_VUNG_GOM else 1)


if __name__ == "__main__":
    main()

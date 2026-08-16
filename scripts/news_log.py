#!/usr/bin/env python3
"""Ghi nhật ký tin tức chứng khoán — nguồn cho điều kiện "tin xấu tràn ngập".

Chưa có nguồn tin tự động (README: tin tức nằm trong nhóm phải nhập tay hoặc
lấy qua WebSearch trong phiên chat), nên cửa vào là script này. Mỗi tiêu đề
được lưu kèm NGUỒN và cách gán nhãn (auto theo từ khoá / manual), để về sau
còn kiểm lại tín hiệu đã dựa trên cái gì.

Cách dùng:
  python3 scripts/news_log.py add "VN-Index bán tháo, mất mốc 1.200 điểm" --source cafef
  python3 scripts/news_log.py add "Khối ngoại mua ròng trở lại" --sentiment POSITIVE --source vnexpress
  python3 scripts/news_log.py add "..." --date 2026-08-15 --source tinnhanhck
  python3 scripts/news_log.py list [--days 7]
  python3 scripts/news_log.py stats [--date 2026-08-16]

Nhãn: NEGATIVE / POSITIVE / NEUTRAL. Không truyền --sentiment thì script đoán
theo từ khoá và ĐÁNH DẤU là auto — nhãn đoán vẫn phải soát lại bằng mắt.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.news_sentiment import (  # noqa: E402
    NEWS_PATH,
    VALID_SENTIMENTS,
    append_news,
    load_news,
    measure,
    suggest_sentiment,
)

MARK = {"NEGATIVE": "🔴", "POSITIVE": "🟢", "NEUTRAL": "⚪"}


def _arg(args: list[str], flag: str, default: str | None = None) -> str | None:
    return args[args.index(flag) + 1] if flag in args and args.index(flag) + 1 < len(args) else default


def cmd_add(args: list[str]) -> None:
    positional = []
    skip = False
    for i, a in enumerate(args):
        if skip:
            skip = False
            continue
        if a.startswith("--"):
            skip = True
            continue
        positional.append(a)
    if not positional:
        sys.exit("Thiếu tiêu đề. VD: news_log.py add \"VN-Index lao dốc\" --source cafef")
    headline = " ".join(positional)

    sentiment = (_arg(args, "--sentiment") or "").upper()
    if sentiment:
        if sentiment not in VALID_SENTIMENTS:
            sys.exit(f"--sentiment phải thuộc {VALID_SENTIMENTS}")
        source_of_label, matched = "manual", []
    else:
        sentiment, matched = suggest_sentiment(headline)
        source_of_label = "auto"

    rec = {
        "date": _arg(args, "--date") or date.today().isoformat(),
        "headline": headline,
        "sentiment": sentiment,
        "sentiment_source": source_of_label,
        "source": _arg(args, "--source") or "khong_ro",
    }
    if matched:
        rec["matched_keywords"] = matched
    append_news(rec)
    hint = f" (khớp từ khoá: {', '.join(matched)})" if matched else ""
    print(f"{MARK[sentiment]} Đã ghi [{rec['date']}] {sentiment} ({source_of_label}){hint}")
    print(f"   {headline}")
    if source_of_label == "auto":
        print("   → Nhãn tự động theo từ khoá. Sai thì ghi đè bằng --sentiment.")


def cmd_list(args: list[str]) -> None:
    days = int(_arg(args, "--days", "7") or 7)
    entries = load_news()
    if not entries:
        print(f"Chưa có tin nào trong {NEWS_PATH.relative_to(ROOT)}.")
        return
    from datetime import date as _date
    from datetime import timedelta

    cutoff = _date.today() - timedelta(days=days)
    shown = 0
    for e in sorted(entries, key=lambda x: str(x.get("date"))):
        try:
            d = _date.fromisoformat(str(e.get("date"))[:10])
        except ValueError:
            continue
        if d < cutoff:
            continue
        shown += 1
        auto = " ·auto" if str(e.get("sentiment_source", "")).lower() == "auto" else ""
        print(f"  {MARK.get(e.get('sentiment'), '⚪')} [{e['date']}] "
              f"{e.get('headline', '')}  ({e.get('source', 'khong_ro')}{auto})")
    if not shown:
        print(f"Không có tin nào trong {days} ngày gần nhất.")


def cmd_stats(args: list[str]) -> None:
    m = measure(today=_arg(args, "--date"))
    print(f"=== TÂM LÝ TIN TỨC ({m.window_days} ngày gần nhất) ===")
    print(f"  Tổng: {m.total} tin — 🔴 {m.negative} · ⚪ {m.neutral} · 🟢 {m.positive}")
    if m.newest_date:
        print(f"  Tin mới nhất: {m.newest_date} ({m.age_days} ngày trước)")
    if m.sources:
        print(f"  Nguồn: {', '.join(m.sources)}")
    if m.measurable:
        verdict = "TIÊU CỰC TRÀN NGẬP" if m.overwhelming_negative else "chưa tới mức tràn ngập"
        print(f"  → {verdict} — {m.evidence()}")
    else:
        print(f"  → CHƯA ĐO ĐƯỢC: {m.reason}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    cmd, rest = args[0], args[1:]
    if cmd == "add":
        cmd_add(rest)
    elif cmd == "list":
        cmd_list(rest)
    elif cmd == "stats":
        cmd_stats(rest)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()

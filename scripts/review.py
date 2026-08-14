#!/usr/bin/env python3
"""Decision review (Phase 9) — hệ thống đã khuyên gì, và giá thực tế đi đâu?

Đọc data/decisions.jsonl (quyết định đã ghi bởi run_morning/run_evening) và
data/history.jsonl (snapshot thị trường), đối chiếu từng quyết định với diễn
biến giá SAU thời điểm đó (chống look-ahead — không bao giờ dùng dữ liệu cùng
kỳ hoặc trước đó để "chấm điểm").

Cách dùng:
  python3 scripts/review.py           # bảng review + tổng kết
  python3 scripts/review.py --json    # JSON để nhúng vào bản tin
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.decision_review import review_all, summarize  # noqa: E402
from decision.decision_log import load_decisions  # noqa: E402

HIST = ROOT / "data" / "history.jsonl"

VERDICT_VI = {
    "DUNG_HUONG": "✅ đúng hướng",
    "SAI_HUONG": "❌ sai hướng",
    "DI_NGANG": "➖ đi ngang (<0,5%)",
    "KHONG_CHAM_DIEM": "◻ quản trị rủi ro — không chấm",
    "CHUA_DU_DU_LIEU": "⏳ chưa đủ dữ liệu sau đó",
}


def load_history() -> list[dict]:
    if not HIST.exists():
        return []
    return [json.loads(l) for l in HIST.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> None:
    as_json = "--json" in sys.argv[1:]
    decisions = load_decisions()
    if not decisions:
        sys.exit("Chưa có quyết định nào trong data/decisions.jsonl — "
                 "chạy run_morning.py/run_evening.py trước để hệ thống ghi quyết định.")
    rows = review_all(decisions, load_history())
    s = summarize(rows)
    if as_json:
        print(json.dumps({"reviews": rows, "summary": s}, ensure_ascii=False))
        return
    print(f"=== DECISION REVIEW — {s['total']} quyết định đã ghi ===\n")
    for r in rows:
        line = f"  {r['date']} ({r['ky']}) {r['asset']}: {r['action_vi']}"
        if r["change_pct"] is not None and r["compared_with"]:
            line += (f" → giá {r['change_pct']:+.2f}% tới {r['compared_with']['date']}"
                     f" ({r['compared_with']['ky']})")
        print(f"{line} — {VERDICT_VI[r['verdict']]}")
    print(f"\nĐã chấm điểm: {s['scored']} (đúng {s['dung_huong']} / sai {s['sai_huong']})"
          f" · đi ngang {s['di_ngang']} · không chấm {s['khong_cham_diem']}"
          f" · chưa đủ dữ liệu {s['chua_du_du_lieu']}")
    if s["accuracy_pct"] is not None:
        print(f"Accuracy (chỉ trên quyết định có định hướng giá): {s['accuracy_pct']}%")
    else:
        print("Accuracy: chưa tính được — chưa có quyết định định hướng nào đủ dữ liệu chấm điểm.")
    if s["scored"] < 5:
        print("(Cần ≥5 quyết định đã chấm điểm thì accuracy mới được nạp vào confidence score.)")
    _print_opportunity_cost(decisions)


def _print_opportunity_cost(decisions: list[dict]) -> None:
    """Phí cơ hội của các khuyến nghị phòng thủ — phần decision review bỏ trống.

    GIỮ/CHỐT BỚT không phải dự báo giá nên không chấm đúng/sai được, nhưng
    "nghe theo thì tới giờ mất/được bao nhiêu" thì đo được, và đó mới là câu
    chủ danh mục thực sự hỏi.
    """
    from analytics.opportunity_cost import measure_all, summarize

    entries = measure_all(decisions, load_history())
    s = summarize(entries)
    if s.n_defensive == 0:
        return
    print(f"\n=== PHÍ CƠ HỘI CỦA KHUYẾN NGHỊ PHÒNG THỦ ({s.n_defensive} quyết định) ===\n")
    for e in entries:
        if e.premium_pct is None:
            continue
        if abs(e.premium_pct) < 0.005:
            dau = "giá chưa đổi"
        else:
            dau = "trả phí" if e.premium_pct > 0 else "tránh được lỗ"
        xx = " [xấp xỉ]" if e.approximated else ""
        print(f"  {e.date} ({e.ky}) {e.action_vi}{xx}: {e.premium_pct:+.2f}% — {dau}")
    if s.avg_premium_pct is not None:
        print(f"\n  Trung bình: {s.avg_premium_pct:+.2f}% · xấu nhất: {s.worst_premium_pct:+.2f}%")
    print(f"\n{s.verdict}")
    if any(e.approximated for e in entries):
        from analytics.opportunity_cost import APPROXIMATION_NOTE

        print(f"\n[xấp xỉ] {APPROXIMATION_NOTE}.")


if __name__ == "__main__":
    main()

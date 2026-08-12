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
from run_morning import (  # noqa: E402
    bulletin_date, run_gold_decision, section_alerts, section_tai_san, section_tien_gui,
    section_tong_quan, section_vang, send_telegram_report,
)


def load_history() -> list[dict]:
    if not HIST.exists():
        return []
    return [json.loads(l) for l in HIST.read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    from deposits.ranking import load_normalized, rank
    from gold.xuan_trieu_model import estimate as gold_estimate
    from reporting.diff_report import compare_snapshots, format_diff_section

    port, parts, total, gold_decision = run_gold_decision(ky="chieu")
    est = gold_estimate()
    hist = load_history()

    deposit_rates = load_normalized()
    ranked_deposits = rank(deposit_rates) if deposit_rates else []

    sections = [
        f"# BẢN TIN ĐẦU TƯ CHIỀU — {bulletin_date(hist)}",
        section_tong_quan(gold_decision),
        section_tai_san({"parts": parts, "total": total}),
        section_vang(est, gold_decision),
        section_tien_gui(ranked_deposits),
        section_alerts(),
    ]

    # Mục bắt buộc: so với bản tin trước (kỳ liền trước trong history.jsonl,
    # thường là bản sáng cùng ngày)
    if len(hist) >= 2:
        market_changes = compare_snapshots(hist[-2], hist[-1])
        # Không có lịch sử quyết định lưu lại theo kỳ ở bước này (Phase 9 sẽ
        # lưu vào journal) -> chỉ so market, không so quyết định (trung thực
        # về giới hạn hiện tại thay vì giả vờ so sánh được).
        sections.append(format_diff_section(market_changes, []))
    else:
        sections.append("## THAY ĐỔI SO VỚI BẢN TIN TRƯỚC\n\nChưa đủ 2 kỳ trong lịch sử để so sánh.")

    for s in sections:
        print(s, "\n")

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

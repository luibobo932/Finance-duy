#!/usr/bin/env python3
"""Xếp hạng lãi suất tiết kiệm (đã lọc bỏ mức không áp dụng cho retail) +
đề xuất chiến lược chia kỳ hạn cho khoản tiết kiệm hiện có trong
config/portfolio.yaml.

Cách dùng:
  python3 scripts/deposits_report.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deposits.ranking import load_normalized, rank  # noqa: E402
from deposits.strategy import split_strategy, total_expected_interest_vnd  # noqa: E402
from portfolio.loader import load_portfolio, load_risk_limits  # noqa: E402


def main():
    rates = load_normalized()
    if not rates:
        sys.exit("Chưa có data/normalized/deposit_rates.jsonl — chưa thể xếp hạng.")
    ranked = rank(rates)

    print("=== XẾP HẠNG LÃI SUẤT TIẾT KIỆM (đã loại mức không áp dụng cho khoản <1 tỷ) ===")
    print(f"{'Ngân hàng':<18}{'Kỳ hạn':>8}{'Lãi suất':>10}{'Kênh':>10}  Điều kiện")
    for r in ranked:
        print(f"{r['bank']:<18}{r['term_months']:>6}T{r['rate_pct']:>9.2f}%{(r['channel'] or '-'):>10}  {r['conditions']}")

    excluded_count = len(rates) - len({(r["bank"], r["term_months"]) for r in ranked})
    print(f"\n(Đã lọc bỏ {len(rates) - len(ranked)} mục không hợp lệ cho retail — VIP/số dư quá lớn/bảo hiểm/CCTG/thiếu dữ liệu)")

    port = load_portfolio()
    limits = load_risk_limits()
    buffer = limits.get("minimum_cash_buffer_vnd", 0)
    allocations = split_strategy(port.savings_principal_vnd, buffer, ranked)

    print(f"\n=== CHIẾN LƯỢC CHIA KỲ HẠN cho {port.savings_principal_vnd:,.0f}đ tiết kiệm hiện có ===")
    investable = max(0.0, port.savings_principal_vnd - buffer)
    if not allocations:
        print("Không đủ dữ liệu lãi suất theo các kỳ hạn mục tiêu để đề xuất chia.")
        return
    for a in allocations:
        print(
            f"  {a.label}: {a.amount_vnd:,.0f}đ @ {a.bank} {a.rate_pct}%/năm — "
            f"đáo hạn ~{a.maturity_date} — lãi dự kiến {a.expected_interest_vnd:,.0f}đ"
        )
        loss = a.early_withdrawal_loss_vnd()
        print(f"    Nếu rút trước hạn: mất khoảng {loss:,.0f}đ tiền lãi so với để đúng hạn")
    allocated = sum(a.amount_vnd for a in allocations)
    unallocated = investable - allocated
    if unallocated > 1:
        print(
            f"\n⚠️ CHƯA PHÂN BỔ: {unallocated:,.0f}đ — không tìm được ngân hàng hợp lệ (retail, <1 tỷ)"
            " cho (các) kỳ hạn còn lại trong dữ liệu hiện có. KHÔNG tự ý gán mức lãi suất giả định."
        )
    total_interest = total_expected_interest_vnd(allocations)
    print(f"\nTổng lãi dự kiến (phần đã phân bổ, giữ đúng hạn): {total_interest:,.0f}đ/năm")
    print(f"Quỹ khẩn cấp giữ lại (không đầu tư): {buffer:,.0f}đ")


if __name__ == "__main__":
    main()

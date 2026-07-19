"""Lọc lãi suất KHÔNG áp dụng cho retail (VIP/số dư siêu lớn/bảo hiểm/CCTG/
ưu đãi không rõ điều kiện) và xếp hạng phần còn lại theo lãi suất.

Nguyên tắc: loại trừ bằng danh sách từ khóa TƯỜNG MINH, không để AI tự đoán
xem 1 mức lãi suất có "hợp lý" hay không.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .schema import DepositRate

ROOT = Path(__file__).resolve().parent.parent
NORMALIZED = ROOT / "data" / "normalized" / "deposit_rates.jsonl"

# Từ khóa trong `conditions` khiến 1 mức lãi suất bị loại khỏi bảng xếp hạng
# retail — khớp không phân biệt hoa/thường, so trên chuỗi đã hạ chữ thường.
EXCLUSION_KEYWORDS = [
    "khách vip",
    "khách hàng ưu tiên",
    "priority banking",
    "bancassurance",
    "kèm bảo hiểm",
    "mua bảo hiểm",
    "chứng chỉ tiền gửi",
    "cctg",
]

DEFAULT_MAX_DEPOSIT_FOR_RETAIL_VND = 1_000_000_000  # khớp yêu cầu "khoản dưới 1 tỷ"


def is_excluded(dr: DepositRate, max_deposit_vnd: float = DEFAULT_MAX_DEPOSIT_FOR_RETAIL_VND) -> tuple[bool, Optional[str]]:
    """Trả (bị_loại, lý_do). lý_do=None nếu không bị loại."""
    text = (dr.conditions or "").lower()
    for kw in EXCLUSION_KEYWORDS:
        if kw in text:
            return True, f"điều kiện chứa '{kw}' — không áp dụng cho khách retail thông thường"
    if dr.min_deposit_vnd is not None and dr.min_deposit_vnd > max_deposit_vnd:
        return True, (
            f"yêu cầu tối thiểu {dr.min_deposit_vnd:,.0f}đ vượt quá {max_deposit_vnd:,.0f}đ"
        )
    if dr.best_rate_pct is None:
        return True, "thiếu dữ liệu lãi suất"
    return False, None


def load_normalized(path: Optional[Path] = None) -> list[DepositRate]:
    """Đọc data/normalized/deposit_rates.jsonl — mỗi dòng 1 DepositRate JSON.

    Chỉ trả các bản ghi thuộc ngày MỚI NHẤT có trong file (tránh trộn lẫn
    nhiều ngày khi xếp hạng "hiện tại").
    """
    path = path or NORMALIZED
    if not path.exists():
        return []
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not rows:
        return []
    latest_date = max(r.get("updated_at", "") for r in rows)
    return [DepositRate.from_dict(r) for r in rows if r.get("updated_at") == latest_date]


def rank(
    rates: list[DepositRate], max_deposit_vnd: float = DEFAULT_MAX_DEPOSIT_FOR_RETAIL_VND
) -> list[dict]:
    """Xếp hạng giảm dần theo lãi suất, sau khi loại các mục không hợp lệ."""
    out = []
    for dr in rates:
        excluded, reason = is_excluded(dr, max_deposit_vnd)
        if excluded:
            continue
        out.append(
            {
                "bank": dr.bank,
                "term_months": dr.term_months,
                "rate_pct": dr.best_rate_pct,
                "channel": dr.best_channel,
                "min_deposit_vnd": dr.min_deposit_vnd,
                "conditions": dr.conditions,
                "interest_payment": dr.interest_payment,
                "source": dr.source,
            }
        )
    out.sort(key=lambda x: -x["rate_pct"])
    return out


def top_by_term(ranked: list[dict], term_months: int) -> Optional[dict]:
    """Mức tốt nhất cho đúng kỳ hạn, hoặc kỳ hạn dài hơn gần nhất nếu không có."""
    exact = [r for r in ranked if r["term_months"] == term_months]
    if exact:
        return exact[0]
    longer = [r for r in ranked if r["term_months"] >= term_months]
    return longer[0] if longer else None

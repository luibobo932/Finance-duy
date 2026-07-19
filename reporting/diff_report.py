"""So sánh 2 bản tin (sáng vs chiều cùng ngày, hoặc bất kỳ 2 kỳ nào) — mục
"THAY ĐỔI SO VỚI BẢN TIN TRƯỚC" bắt buộc trong bản tin chiều. Nếu quyết
định (Decision Engine) thay đổi, PHẢI ghi rõ lý do — không được chỉ báo
"đã đổi" mà không giải thích.
"""
from __future__ import annotations

from typing import Optional

# Các trường mặc định so sánh giữa 2 snapshot trong data/history.jsonl
DEFAULT_MARKET_FIELDS: list[tuple[tuple, str, str]] = [
    (("vnindex", "close"), "VN-Index", ""),
    (("vcb", "close"), "VCB", "đ"),
    (("ctd", "close"), "CTD", "đ"),
    (("gold", "sjc_sell"), "Vàng SJC bán ra", "tr"),
    (("gold", "xauusd"), "Vàng thế giới", "$"),
    (("gold", "premium_trieu"), "Chênh lệch vàng VN-TG", "tr"),
    (("foreign_net_ty",), "Khối ngoại", "tỷ"),
]


def _get(d: dict, path: tuple) -> Optional[object]:
    cur = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur or cur[p] is None:
            return None
        cur = cur[p]
    return cur


def compare_snapshots(prev: dict, cur: dict, fields: Optional[list[tuple]] = None) -> list[dict]:
    """Trả danh sách các trường thị trường ĐÃ thay đổi giữa 2 snapshot.

    Chỉ liệt kê trường có thay đổi thật (khác None và khác giá trị cũ) —
    không liệt kê trường không đổi để bản tin gọn.
    """
    fields = fields or DEFAULT_MARKET_FIELDS
    changes = []
    for path, label, unit in fields:
        pv, cv = _get(prev, path), _get(cur, path)
        if pv is None and cv is None:
            continue
        if pv != cv:
            entry = {"label": label, "before": pv, "after": cv, "unit": unit}
            if isinstance(pv, (int, float)) and isinstance(cv, (int, float)) and pv:
                entry["delta_pct"] = round((cv - pv) / abs(pv) * 100, 2)
            changes.append(entry)
    return changes


def compare_decisions(prev_decision: Optional[dict], cur_decision: dict) -> dict:
    """So sánh 2 output của decision/policy_engine.decide() cho CÙNG 1 tài sản.

    Nếu hành động thay đổi, `reason` PHẢI được điền (từ `cur_decision["reasons"]`)
    — không được báo thay đổi mà không giải thích.
    """
    if prev_decision is None:
        return {"asset": cur_decision.get("asset"), "changed": False,
                "note": "Chưa có quyết định trước để so sánh"}
    changed = prev_decision.get("action") != cur_decision.get("action")
    result = {
        "asset": cur_decision.get("asset"),
        "changed": changed,
        "before": prev_decision.get("action_vi"),
        "after": cur_decision.get("action_vi"),
    }
    if changed:
        result["reason"] = "; ".join(cur_decision.get("reasons", [])) or "Không có lý do cụ thể được ghi nhận"
    return result


def format_diff_section(market_changes: list[dict], decision_changes: list[dict]) -> str:
    """Trả đoạn văn bản tiếng Việt cho mục 'THAY ĐỔI SO VỚI BẢN TIN TRƯỚC'."""
    lines = ["## THAY ĐỔI SO VỚI BẢN TIN TRƯỚC"]
    if not market_changes and not any(c["changed"] for c in decision_changes):
        lines.append("Không có thay đổi đáng kể so với bản tin trước.")
        return "\n".join(lines)
    if market_changes:
        lines.append("### Thị trường")
        for c in market_changes:
            arrow = "tăng" if isinstance(c["after"], (int, float)) and isinstance(c["before"], (int, float)) and c["after"] > c["before"] else "giảm"
            pct = f" ({c['delta_pct']:+.2f}%)" if "delta_pct" in c else ""
            lines.append(f"- {c['label']}: {c['before']}{c['unit']} → {c['after']}{c['unit']} ({arrow}{pct})")
    changed_decisions = [c for c in decision_changes if c["changed"]]
    if changed_decisions:
        lines.append("### Quyết định thay đổi")
        for c in changed_decisions:
            lines.append(f"- {c['asset']}: {c['before']} → {c['after']}. Lý do: {c.get('reason', '')}")
    return "\n".join(lines)

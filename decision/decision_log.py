"""Lưu quyết định của Decision Engine vào data/decisions.jsonl (Phase 9).

Mỗi lần run_morning/run_evening gọi decide(), kết quả được ghi lại kèm GIÁ
THAM CHIẾU tại đúng thời điểm quyết định (từ snapshot mà quyết định dựa vào).
Đây là nền của decision review: về sau đối chiếu "hệ thống đã nói gì" với
"giá thực tế đi đâu" — không thể tự sửa lịch sử, không look-ahead.

Quy tắc:
- Chặn ghi trùng (date, ky, asset) — mỗi kỳ mỗi tài sản chỉ 1 quyết định.
- ref_price lấy từ snapshot ĐÃ DÙNG để quyết định (không phải giá tương lai).
- Thiếu giá tham chiếu → ghi None trung thực, review sẽ báo "chưa đủ dữ liệu".
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
DECISIONS_PATH = ROOT / "data" / "decisions.jsonl"

# Trường giá tham chiếu theo asset_class, thử theo thứ tự — bản ghi quyết định
# lưu lại TÊN trường đã dùng để review chỉ so sánh cùng đơn vị.
REF_PRICE_FIELDS: dict[str, list[tuple[str, ...]]] = {
    "gold": [("gold", "ring_sell"), ("gold", "xauusd")],
    "equity": [("vcb", "close")],  # dùng khi decide() cho equity được nối vào orchestrator
}


def extract_ref_price(snapshot: dict, asset_class: str) -> Optional[tuple[str, float]]:
    """Lấy (tên_trường, giá) tham chiếu từ snapshot; None nếu không có."""
    for path in REF_PRICE_FIELDS.get(asset_class, []):
        node: object = snapshot
        for key in path:
            if not isinstance(node, dict) or key not in node:
                node = None
                break
            node = node[key]
        if isinstance(node, (int, float)) and node > 0:
            return path[-1], float(node)
    return None


def build_entry(decision: dict, asset_class: str, ky: str, snapshot: Optional[dict]) -> dict:
    """Chuẩn hóa 1 bản ghi quyết định từ output của policy_engine.decide()."""
    ref_field: Optional[str] = None
    ref_price: Optional[float] = None
    date: Optional[str] = None
    if snapshot:
        date = snapshot.get("date")
        ref = extract_ref_price(snapshot, asset_class)
        if ref:
            ref_field, ref_price = ref
    return {
        "date": date,
        "ky": ky,
        "asset": decision["asset"],
        "asset_class": asset_class,
        "action": decision["action"],
        "action_vi": decision["action_vi"],
        "confidence": decision["confidence"],
        "risk_veto": decision["risk_veto"],
        "data_quality": decision["data_quality"],
        "ref_price_field": ref_field,
        "ref_price": ref_price,
    }


def load_decisions(path: Optional[Path] = None) -> list[dict]:
    path = path or DECISIONS_PATH
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def append_decision(entry: dict, path: Optional[Path] = None) -> bool:
    """Ghi 1 quyết định; trả False (không ghi) nếu đã có bản ghi cùng
    (date, ky, asset) — lịch sử quyết định là bất biến, không ghi đè."""
    path = path or DECISIONS_PATH
    key = (entry.get("date"), entry.get("ky"), entry.get("asset"))
    for existing in load_decisions(path):
        if (existing.get("date"), existing.get("ky"), existing.get("asset")) == key:
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return True

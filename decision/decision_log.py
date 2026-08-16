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

# Phiên bản bộ rule đã tạo ra quyết định. Tăng số này MỖI KHI rule đổi hành vi,
# vì review đối chiếu quyết định cũ với giá sau đó — không có mốc này thì hai
# quyết định do hai bộ rule khác nhau sinh ra sẽ bị trộn vào cùng một thống kê
# accuracy mà không ai biết.
#   v1 (đến 2026-08-12): rule tập trung vàng CHỈ chạy khi đề xuất là mua thêm,
#      nên vàng ≥70% vẫn ra "GIỮ".
#   v2 (từ 2026-08-12): đề xuất GIỮ/ĐỨNG NGOÀI khi vàng ≥ critical được nâng
#      thành CHỐT BỚT; hành động đọc từ config/decision_rules.yaml.
RULE_VERSION = 2

# Trường giá tham chiếu theo asset_class, thử theo thứ tự — bản ghi quyết định
# lưu lại TÊN trường đã dùng để review chỉ so sánh cùng đơn vị.
REF_PRICE_FIELDS: dict[str, list[tuple[str, ...]]] = {
    "gold": [("gold", "ring_sell"), ("gold", "xauusd")],
    # equity KHÔNG dùng bảng này: giá tham chiếu phụ thuộc MÃ, không phụ thuộc
    # lớp tài sản. Bản cũ ghi cứng ("vcb","close"), nghĩa là một quyết định về
    # CTD sẽ được ghi kèm GIÁ CỦA VCB — sai lệch âm thầm làm hỏng vĩnh viễn
    # mọi phép chấm điểm sau này. Lỗi chưa từng nổ chỉ vì chưa có quyết định
    # cổ phiếu nào được ghi. Xem `_equity_ref_price`.
}


def extract_ref_price(snapshot: dict, asset_class: str,
                       ticker: Optional[str] = None) -> Optional[tuple[str, float]]:
    """Lấy (tên_trường, giá) tham chiếu từ snapshot; None nếu không có.

    Với cổ phiếu PHẢI truyền `ticker`: giá tham chiếu phụ thuộc mã, không phụ
    thuộc lớp tài sản. Thiếu ticker thì trả None thay vì lấy bừa một mã —
    ghi sai giá tham chiếu còn tệ hơn không ghi, vì nó làm hỏng mọi phép chấm
    điểm về sau mà không có gì báo lỗi.
    """
    if asset_class == "equity":
        return _equity_ref_price(snapshot, ticker)
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


def _equity_ref_price(snapshot: dict, ticker: Optional[str]) -> Optional[tuple[str, float]]:
    """Giá đóng cửa của ĐÚNG mã đó trong snapshot."""
    if not ticker:
        return None
    node = snapshot.get(ticker.lower())
    if isinstance(node, dict) and isinstance(node.get("close"), (int, float)) and node["close"] > 0:
        return f"{ticker.lower()}.close", float(node["close"])
    return None


def build_entry(decision: dict, asset_class: str, ky: str, snapshot: Optional[dict],
                ticker: Optional[str] = None) -> dict:
    """Chuẩn hóa 1 bản ghi quyết định từ output của policy_engine.decide()."""
    ref_field: Optional[str] = None
    ref_price: Optional[float] = None
    date: Optional[str] = None
    if snapshot:
        date = snapshot.get("date")
        ref = extract_ref_price(snapshot, asset_class, ticker)
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
        "rule_version": RULE_VERSION,
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

"""Decision review (Phase 9) — đối chiếu quyết định Decision Engine đã đưa
ra với diễn biến giá THỰC TẾ sau đó.

Chống look-ahead-bias là ràng buộc cứng của module này:
- Một quyết định tại kỳ (date, ky) chỉ được đánh giá bằng snapshot có kỳ
  LỚN HƠN HẲN (sáng < chiều trong cùng ngày). Không bao giờ dùng chính
  snapshot quyết định dựa vào, càng không dùng snapshot trước đó.
- Chỉ so sánh CÙNG trường giá đã ghi lúc quyết định (ref_price_field) —
  không so chéo ring_sell với xauusd.
- Chỉ chấm đúng/sai cho hành động CÓ ĐỊNH HƯỚNG GIÁ (BUY_SMALL kỳ vọng
  tăng, TAKE_PARTIAL_PROFIT kỳ vọng giảm). GIỮ/KHÔNG MUA THÊM/QUAN SÁT là
  hành động quản trị rủi ro — trung thực ghi "không chấm điểm" thay vì bịa
  ra tiêu chí thắng thua.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

# Ngưỡng coi là "đi ngang" — biến động dưới mức này không đủ để nói quyết
# định đúng hay sai hướng.
FLAT_THRESHOLD_PCT = 0.5

# Hành động có định hướng giá: +1 kỳ vọng tăng, -1 kỳ vọng giảm.
DIRECTIONAL_ACTIONS: dict[str, int] = {
    "BUY_SMALL": +1,
    "TAKE_PARTIAL_PROFIT": -1,
}

PERIOD_ORDER: dict[str, int] = {"sang": 0, "chieu": 1}


class Verdict(str, Enum):
    DUNG_HUONG = "DUNG_HUONG"
    SAI_HUONG = "SAI_HUONG"
    DI_NGANG = "DI_NGANG"
    KHONG_CHAM_DIEM = "KHONG_CHAM_DIEM"  # hành động quản trị rủi ro, không phải dự báo giá
    CHUA_DU_DU_LIEU = "CHUA_DU_DU_LIEU"


def period_key(date: str, ky: str) -> tuple[str, int]:
    """Khóa sắp xếp kỳ: ngày trước, trong ngày thì sáng (0) < chiều (1)."""
    return (date, PERIOD_ORDER.get(ky, 0))


def later_snapshots(decision: dict, snapshots: list[dict]) -> list[dict]:
    """Chỉ trả snapshot có kỳ SAU HẲN kỳ của quyết định, sắp theo thời gian.

    Đây là chốt chống look-ahead duy nhất — mọi hàm review phải đi qua đây.
    """
    d_key = period_key(decision["date"], decision["ky"])
    later = [s for s in snapshots
             if s.get("date") and period_key(s["date"], s.get("ky", "sang")) > d_key]
    return sorted(later, key=lambda s: period_key(s["date"], s.get("ky", "sang")))


def _price_from(snapshot: dict, asset_class: str, field: str) -> Optional[float]:
    if asset_class == "gold":
        node = snapshot.get("gold") or {}
    else:
        node = snapshot.get(field.split(".")[0]) or snapshot
    val = node.get(field) if isinstance(node, dict) else None
    if isinstance(val, (int, float)) and val > 0:
        return float(val)
    return None


def price_from_snapshot(snapshot: dict, asset_class: str, field: str) -> Optional[float]:
    """API công khai của `_price_from` — để module khác (VD analytics/
    opportunity_cost.py) đọc giá theo ĐÚNG cách review đọc, thay vì tự viết lại
    một bản hơi khác rồi hai nơi so giá lệch nhau."""
    return _price_from(snapshot, asset_class, field)


def review_one(decision: dict, snapshots: list[dict]) -> dict:
    """Đánh giá 1 quyết định. Trả dict: decision gốc + change_pct + verdict
    + compared_with (kỳ snapshot đã dùng để so)."""
    base = {
        "date": decision["date"], "ky": decision["ky"], "asset": decision["asset"],
        "action": decision["action"], "action_vi": decision.get("action_vi"),
        "confidence": decision.get("confidence"),
        "ref_price": decision.get("ref_price"),
        "change_pct": None, "compared_with": None,
    }
    ref_price = decision.get("ref_price")
    ref_field = decision.get("ref_price_field")
    if ref_price is None or ref_field is None:
        return {**base, "verdict": Verdict.CHUA_DU_DU_LIEU.value}

    candidates = later_snapshots(decision, snapshots)
    asset_class = decision.get("asset_class", "gold")
    # Lấy snapshot MỚI NHẤT có cùng trường giá (nhiều thời gian trôi qua nhất
    # = đánh giá công bằng nhất cho quyết định).
    compared: Optional[dict] = None
    later_price: Optional[float] = None
    for s in reversed(candidates):
        p = _price_from(s, asset_class, ref_field)
        if p is not None:
            compared, later_price = s, p
            break
    if compared is None or later_price is None:
        return {**base, "verdict": Verdict.CHUA_DU_DU_LIEU.value}

    change_pct = round((later_price - ref_price) / ref_price * 100, 2)
    base["change_pct"] = change_pct
    base["compared_with"] = {"date": compared["date"], "ky": compared.get("ky", "sang")}

    direction = DIRECTIONAL_ACTIONS.get(decision["action"])
    if direction is None:
        return {**base, "verdict": Verdict.KHONG_CHAM_DIEM.value}
    if abs(change_pct) < FLAT_THRESHOLD_PCT:
        return {**base, "verdict": Verdict.DI_NGANG.value}
    correct = (change_pct > 0) == (direction > 0)
    return {**base, "verdict": (Verdict.DUNG_HUONG if correct else Verdict.SAI_HUONG).value}


def review_all(decisions: list[dict], snapshots: list[dict]) -> list[dict]:
    return [review_one(d, snapshots) for d in decisions]


def summarize(rows: list[dict]) -> dict:
    """Tổng kết: đếm theo verdict + accuracy trên các quyết định ĐÃ chấm điểm.

    accuracy_pct = đúng / (đúng + sai) — đi ngang và không-chấm-điểm không
    tính vào mẫu (không phạt cũng không thưởng).
    """
    counts = {v.value: 0 for v in Verdict}
    for r in rows:
        counts[r["verdict"]] += 1
    dung, sai = counts[Verdict.DUNG_HUONG.value], counts[Verdict.SAI_HUONG.value]
    scored = dung + sai
    return {
        "total": len(rows),
        "dung_huong": dung,
        "sai_huong": sai,
        "di_ngang": counts[Verdict.DI_NGANG.value],
        "khong_cham_diem": counts[Verdict.KHONG_CHAM_DIEM.value],
        "chua_du_du_lieu": counts[Verdict.CHUA_DU_DU_LIEU.value],
        "scored": scored,
        "accuracy_pct": round(dung / scored * 100, 1) if scored else None,
    }


MIN_SCORED_FOR_CONFIDENCE = 5


def historical_accuracy_for_confidence(summary: dict) -> Optional[float]:
    """Accuracy để nạp vào compute_confidence (trọng số lịch sử 15%).

    Dưới 5 quyết định đã chấm điểm → None (mẫu quá nhỏ, nạp vào chỉ thêm
    nhiễu — compute_confidence xử lý None trung tính sẵn rồi)."""
    if (summary.get("scored") or 0) < MIN_SCORED_FOR_CONFIDENCE:
        return None
    acc = summary.get("accuracy_pct")
    return float(acc) if acc is not None else None

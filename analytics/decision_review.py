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

# Trường giá thay thế khi trường gốc NGỪNG được thu thập, theo thứ tự ưu tiên.
#
# Tình huống thật, đo trên `data/history.jsonl`: `gold.ring_sell` (giá vàng
# nhẫn trong nước) chỉ có tới 22/07 rồi ngừng hẳn vì không có nguồn tự động.
# Bốn quyết định neo vào trường đó vì thế bị KẸT: kỳ so sánh muộn nhất còn giá
# là 22/07 chiều, cách quyết định 22/07 sáng vài giờ.
#
# Hệ quả không phải "thiếu dữ liệu" mà là MỘT KHUYẾN NGHỊ SAI BỊ GHI THÀNH
# ĐÚNG-KHÔNG-SAI. Quyết định 22/07 sáng là CHỐT BỚT — kỳ vọng giá giảm. Đo
# bằng ring_sell: +0,00% → "đi ngang". Đo bằng xauusd trên cùng khoảng thời
# gian tới 10/08: **+5,48%** → lẽ ra là SAI HƯỚNG. Một thước đo độ chính xác
# mà chỗ duy nhất nó đáng lẽ ghi "sai" thì lại ghi "đi ngang" là thước đo
# đang tự bảo vệ mình.
#
# `analytics/opportunity_cost.py` ĐÃ giải đúng vấn đề này, và chú thích trong
# đó nói thẳng: "so hai kỳ cách nhau vài giờ ra +0,00% và không nói gì về chi
# phí của một hành động phòng thủ". Sửa ở module đó, không sửa ở module này —
# mà module NÀY mới là nơi nạp accuracy vào điểm tin cậy. Hai nơi vì thế chấm
# cùng một quyết định ra hai con số trái nhau: +0,00% và +5,48%.
#
# Ràng buộc bất di bất dịch khi thay trường: đọc giá ở CẢ HAI ĐẦU bằng CÙNG
# một trường. Không bao giờ so ref_price (ring_sell) với giá sau (xauusd) —
# khác hẳn thang đo, phép so đó vô nghĩa chứ không phải xấp xỉ.
FALLBACK_FIELDS: dict[str, list[str]] = {
    "gold": ["ring_sell", "sjc_sell", "sjc_buy", "xauusd"],
}

# Sai số khi thay trường: tỷ lệ giá trong nước / thế giới KHÔNG cố định — đo
# được 2,3% biên độ trong 6 ngày (xem gold/calibration.py). Nên % thay đổi của
# xauusd chỉ XẤP XỈ % thay đổi của giá trong nước, và phải nói rõ điều đó.
APPROXIMATION_NOTE = ("XẤP XỈ: trường giá gốc ngừng thu thập nên đo bằng trường khác; "
                      "tỷ lệ giá trong nước/thế giới trôi ~2,3% trong 6 ngày quan sát "
                      "(gold/calibration.py) nên con số này có sai số tương ứng")


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


def snapshot_at(decision: dict, snapshots: list[dict]) -> Optional[dict]:
    """Snapshot ĐÚNG kỳ ra quyết định — để lấy giá tham chiếu ở trường thay thế."""
    for s in snapshots:
        if s.get("date") == decision.get("date") and s.get("ky") == decision.get("ky"):
            return s
    return None


def best_measurement(decision: dict, snapshots: list[dict]) -> Optional[dict]:
    """Phép đo tốt nhất cho một quyết định: trường giá nào, so với kỳ nào.

    MỘT chỗ định nghĩa duy nhất, dùng chung cho `review_one` (chấm đúng/sai) và
    `analytics/opportunity_cost.py` (đo phí cơ hội). Trước đây hai module tự
    chọn kỳ so sánh theo hai cách khác nhau, nên chấm cùng một quyết định ra
    +0,00% và +5,48% — xem chú thích ở `FALLBACK_FIELDS`.

    Quy tắc, theo đúng thứ tự:
      1. Ưu tiên kỳ MUỘN NHẤT có giá — thời gian trôi qua càng nhiều thì phép
         đánh giá càng có nội dung.
      2. Cùng kỳ thì ưu tiên TRƯỜNG GỐC (không xấp xỉ) hơn trường thay thế.
      3. Trường thay thế phải đọc được giá ở CẢ HAI đầu; nếu không, bỏ qua.

    Trả None khi không có kỳ nào sau đó đo được — đó là "chưa đánh giá được",
    một trạng thái trung thực, khác hẳn một verdict.
    """
    ref = decision.get("ref_price")
    field = decision.get("ref_price_field")
    if not ref or not field:
        return None
    asset_class = decision.get("asset_class", "gold")
    later = later_snapshots(decision, list(snapshots))
    at_decision = snapshot_at(decision, snapshots)

    candidates = [field] + [f for f in FALLBACK_FIELDS.get(asset_class, []) if f != field]
    best: Optional[tuple] = None  # (khoá kỳ, là_xấp_xỉ, trường, ref, giá, snapshot)
    for i, f in enumerate(candidates):
        ref_for_f = ref if i == 0 else (
            _price_from(at_decision, asset_class, f) if at_decision else None)
        if not ref_for_f:
            continue
        for snap in reversed(later):
            price = _price_from(snap, asset_class, f)
            if not price:
                continue
            key = period_key(snap.get("date", ""), snap.get("ky", ""))
            cand = (key, i > 0, f, ref_for_f, price, snap)
            if best is None or key > best[0] or (key == best[0] and best[1] and i == 0):
                best = cand
            break  # đã lấy kỳ mới nhất của trường này
    if best is None:
        return None
    _key, approx, f, ref_for_f, price, snap = best
    return {
        "field": f, "ref_price": ref_for_f, "later_price": price, "snapshot": snap,
        "approximated": approx,
        "change_pct": round((price - ref_for_f) / ref_for_f * 100, 2),
        "horizon_days": _days_between(decision.get("date"), snap.get("date")),
    }


def _days_between(a: Optional[str], b: Optional[str]) -> Optional[int]:
    """Số ngày lịch giữa hai kỳ — để người đọc thấy verdict dựa trên cửa sổ nào.

    Một verdict trên cửa sổ 0 ngày (sáng so với chiều cùng ngày) và một verdict
    trên 14 ngày không cùng sức nặng; giấu con số này đi là để người đọc tự
    hiểu nhầm rằng chúng ngang nhau.
    """
    from datetime import datetime

    try:
        return (datetime.strptime(b[:10], "%Y-%m-%d")
                - datetime.strptime(a[:10], "%Y-%m-%d")).days
    except (ValueError, TypeError):
        return None


def review_one(decision: dict, snapshots: list[dict]) -> dict:
    """Đánh giá 1 quyết định. Trả dict: decision gốc + change_pct + verdict
    + compared_with (kỳ snapshot đã dùng để so)."""
    base = {
        "date": decision["date"], "ky": decision["ky"], "asset": decision["asset"],
        "action": decision["action"], "action_vi": decision.get("action_vi"),
        "confidence": decision.get("confidence"),
        "ref_price": decision.get("ref_price"),
        "change_pct": None, "compared_with": None,
        "approximated": False, "horizon_days": None, "measured_field": None,
    }
    # Chọn trường giá + kỳ so sánh qua best_measurement — CÙNG hàm mà
    # opportunity_cost dùng, để hai module không thể chấm một quyết định ra hai
    # con số trái nhau (đã từng: +0,00% và +5,48% cho cùng ngày 22/07).
    m = best_measurement(decision, snapshots)
    if m is None:
        return {**base, "verdict": Verdict.CHUA_DU_DU_LIEU.value}

    compared = m["snapshot"]
    change_pct = m["change_pct"]
    base["change_pct"] = change_pct
    base["compared_with"] = {"date": compared["date"], "ky": compared.get("ky", "sang")}
    base["approximated"] = m["approximated"]
    base["horizon_days"] = m["horizon_days"]
    base["measured_field"] = m["field"]

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

"""Theo dõi khuyến nghị TREO — cảnh báo lặp mà tỷ trọng không đổi.

Vì sao cần: trong 6 bản tin liên tiếp (20/7–22/7) hệ thống đều khuyên "CHỐT BỚT"
vàng, trong khi tỷ trọng vàng vẫn bò từ 74,6% lên 75,1%. Không có gì trong hệ
thống nhìn thấy điều đó: mỗi bản tin là một ảnh chụp độc lập, nên lời khuyên
lặp lại vô hạn mà không ai biết nó đã lặp bao nhiêu lần.

Module này biến "lời khuyên" thành "lời khuyên có trách nhiệm": nói rõ đã treo
bao nhiêu kỳ và tỷ trọng đã đi theo hướng nào kể từ đó.

Giới hạn phải nói thẳng: số lượng tài sản đọc từ `config/portfolio.yaml` là số
HIỆN TẠI, không có lịch sử số lượng. Nên tỷ trọng quá khứ được tính lại theo
số lượng hiện tại — câu kết luận vì thế là "tỷ trọng chưa giảm với số lượng
đang khai báo", KHÔNG phải "bạn chưa bán" (nếu đã bán và đã cập nhật config,
toàn bộ đường sẽ tự tính lại).
"""
from __future__ import annotations

from typing import Optional, Sequence

# Dưới số kỳ này thì chưa gọi là "treo" — 1-2 kỳ lặp lại là bình thường
MIN_PERIODS_TO_WARN = 3
# Tỷ trọng phải giảm ít nhất mức này mới coi là "đã có hành động giảm tỷ trọng"
MEANINGFUL_DROP_PCT = 1.0


def consecutive_over_threshold(gold_pcts: Sequence[Optional[float]], threshold: float) -> int:
    """Số kỳ LIÊN TIẾP gần nhất mà tỷ trọng ≥ ngưỡng (tính từ kỳ mới nhất lùi lại).

    Kỳ thiếu dữ liệu làm ngắt chuỗi — không đoán rằng kỳ đó cũng vượt ngưỡng.
    """
    count = 0
    for pct in reversed(list(gold_pcts)):
        if pct is None or pct < threshold:
            break
        count += 1
    return count


def summarize_pending(history: Sequence[dict], valuations: Sequence) -> dict:
    """Trả về {tag, message, periods, from_pct, to_pct} hoặc {} nếu không có gì treo.

    `valuations` là list Valuation của reporting.dashboard_builder (cần
    `.gold_pct`); truyền list rỗng thì hàm trả về {} thay vì nổ.
    """
    from portfolio.loader import load_risk_limits

    if not history or not valuations:
        return {}

    limits = load_risk_limits() or {}
    # config/risk_limits.yaml lưu ngưỡng dạng PHÂN SỐ (0.70), đổi sang % để so
    # với tỷ trọng hiển thị — cùng một nguồn sự thật, chỉ khác đơn vị trình bày.
    fraction = limits.get("gold_critical")
    if fraction is None:
        return {}
    threshold = float(fraction) * 100

    pcts = [(v.gold_pct * 100 if getattr(v, "gold_pct", None) is not None else None) for v in valuations]
    periods = consecutive_over_threshold(pcts, threshold)
    if periods < MIN_PERIODS_TO_WARN:
        return {}

    window = [p for p in pcts[-periods:] if p is not None]
    if not window:
        return {}
    from_pct, to_pct = window[0], window[-1]
    drop = from_pct - to_pct
    if drop >= MEANINGFUL_DROP_PCT:
        return {}  # tỷ trọng đang giảm thật — khuyến nghị đã được thực hiện, không cảnh báo

    if to_pct > from_pct:
        direction = f"vẫn TĂNG từ {_vi(from_pct)}% lên {_vi(to_pct)}%"
    else:
        direction = f"gần như không đổi ({_vi(from_pct)}% → {_vi(to_pct)}%)"

    advised = _count_repeated_advice("gold")
    advice_note = (
        f" Hệ thống đã ghi {advised} quyết định cho vàng trong "
        "<code>data/decisions.jsonl</code>."
        if advised else
        " Lưu ý: <code>data/decisions.jsonl</code> chưa ghi quyết định nào cho vàng — "
        "bản tin đang được soạn ngoài orchestrator nên Decision Engine không thấy khuyến nghị thật."
    )

    return {
        "tag": f"Khuyến nghị treo {periods} kỳ — tỷ trọng vàng chưa giảm",
        "periods": periods,
        "from_pct": from_pct,
        "to_pct": to_pct,
        "message": (
            f"Tỷ trọng vàng đã vượt ngưỡng critical {_vi(threshold, 0)}% "
            f"<b>{periods} kỳ liên tiếp</b> và {direction} "
            f"(tính theo số lượng đang khai báo trong <code>config/portfolio.yaml</code>).{advice_note} "
            "Hai lựa chọn dứt khoát: <b>(1)</b> thực hiện chốt bớt để đưa tỷ trọng về khẩu vị đã đặt, "
            "hoặc <b>(2)</b> nếu đã cân nhắc và chấp nhận mức tập trung này, hãy nâng ngưỡng trong "
            "<code>config/risk_limits.yaml</code> để hệ thống ngừng nhắc — "
            "giữ nguyên cả hai sẽ khiến cảnh báo mất tác dụng vì lặp mãi."
        ),
    }


def _count_repeated_advice(asset_class: str) -> int:
    """Số quyết định đã ghi cho một lớp tài sản (0 nếu chưa có log)."""
    try:
        from decision.decision_log import load_decisions
    except ImportError:
        return 0
    return sum(1 for d in load_decisions() if d.get("asset_class") == asset_class)


def _vi(value: float, decimals: int = 1) -> str:
    return f"{value:,.{decimals}f}".translate(str.maketrans({",": ".", ".": ","}))

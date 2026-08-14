"""Sinh SVG biểu đồ TỪ DỮ LIỆU — thay cho việc gõ tay toạ độ pixel.

Vì sao module này tồn tại: trước đây `dashboard/ban-tin-dau-tu.html` chứa ~71
cặp toạ độ `x,y` viết tay. Mỗi kỳ bản tin phải sửa lại từng số, và một con số
sai sẽ vẽ ra đường sai mà KHÔNG có gì báo lỗi — dữ liệu đúng nhưng hình vẽ dối.
Ở đây toạ độ được TÍNH từ giá trị thật, nên hình luôn khớp số.

Nguyên tắc thiết kế (theo skill dataviz):
- Đường 2px, điểm cuối r=4 có vòng 2px màu nền (đọc được khi chồng nhau)
- Lưới hairline lùi về sau, KHÔNG bao giờ 2 trục y trong 1 biểu đồ
- Nhãn trực tiếp chỉ ở điểm CUỐI, không rải số lên mọi điểm
- `None` = thiếu dữ liệu → NGẮT đường, không nội suy (không bịa số)
- Màu truyền vào bằng tên CSS var, không hard-code hex → theme sáng/tối tự đổi
"""
from __future__ import annotations

import html
import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

# Kích thước mark cố định (px) — xem references/marks-and-anatomy.md
LINE_WIDTH = 2
MARKER_RADIUS = 4
SURFACE_RING = 2
BAR_MAX_THICKNESS = 24
BAR_CORNER_RADIUS = 4
SEGMENT_GAP = 2  # khoảng trắng ngăn 2 mảng liền nhau trong thanh xếp lớp


@dataclass
class Series:
    """Một chuỗi số liệu. `values` cùng độ dài với x_labels; None = thiếu."""
    label: str
    values: Sequence[Optional[float]]
    color: str  # tên CSS var, VD "--s-red"
    value_suffix: str = ""
    end_label: bool = True  # có ghi nhãn giá trị ở điểm cuối không


@dataclass
class Bar:
    label: str
    value: float
    color: str = "--s-blue"
    sublabel: str = ""


@dataclass
class Segment:
    label: str
    value: float
    color: str


@dataclass
class Box:
    """Khung vẽ: vùng dữ liệu nằm trong lề (margin) để chừa chỗ cho nhãn trục."""
    width: int = 700
    height: int = 240
    left: int = 44
    right: int = 56
    top: int = 16
    bottom: int = 46

    @property
    def plot_left(self) -> int:
        return self.left

    @property
    def plot_right(self) -> int:
        return self.width - self.right

    @property
    def plot_top(self) -> int:
        return self.top

    @property
    def plot_bottom(self) -> int:
        return self.height - self.bottom


def nice_step(span: float, target_ticks: int = 4) -> float:
    """Bước chia trục "tròn" theo bậc 1–2–5×10^n.

    Trục có bước 0,37 đọc rất khó; hàm này luôn cho bước dạng
    1/2/5/10/20/50... để nhãn trục là số tròn.
    """
    if span <= 0 or not math.isfinite(span):
        return 1.0
    raw = span / max(1, target_ticks)
    magnitude = 10 ** math.floor(math.log10(raw))
    for mult in (1, 2, 5, 10):
        if raw <= mult * magnitude:
            return mult * magnitude
    return 10 * magnitude


def axis_domain(values: Sequence[Optional[float]], target_ticks: int = 4) -> tuple[float, float, float]:
    """(đáy, đỉnh, bước) đã làm tròn theo bước tròn, bao trọn dữ liệu.

    Trả về miền có biên nới ra bội số của bước để đường không dính sát mép.
    """
    real = [v for v in values if v is not None]
    if not real:
        return 0.0, 1.0, 1.0
    lo, hi = min(real), max(real)
    if lo == hi:  # chuỗi phẳng — tạo miền quanh giá trị đó để vẫn vẽ được
        step = nice_step(abs(lo) or 1.0, target_ticks)
        return lo - step, lo + step, step
    step = nice_step(hi - lo, target_ticks)
    bottom = math.floor(lo / step) * step
    top = math.ceil(hi / step) * step
    if top == bottom:
        top = bottom + step
    return bottom, top, step


def _fmt(value: float, decimals: int = 1) -> str:
    """Số kiểu Việt Nam: nghìn cách bằng '.', thập phân bằng ','."""
    if value == int(value) and decimals == 0:
        text = f"{int(value):,}"
    else:
        text = f"{value:,.{decimals}f}"
    return text.translate(str.maketrans({",": ".", ".": ","}))


def _x_positions(box: Box, count: int) -> list[float]:
    if count <= 0:
        return []
    if count == 1:
        return [(box.plot_left + box.plot_right) / 2]
    span = box.plot_right - box.plot_left
    return [box.plot_left + span * i / (count - 1) for i in range(count)]


def _y_for(value: float, bottom: float, top: float, box: Box) -> float:
    if top == bottom:
        return box.plot_bottom
    ratio = (value - bottom) / (top - bottom)
    return box.plot_bottom - ratio * (box.plot_bottom - box.plot_top)


def _segments(points: list[Optional[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    """Cắt chuỗi điểm thành các đoạn liên tục, bỏ qua chỗ thiếu dữ liệu."""
    out: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    for p in points:
        if p is None:
            if len(current) > 0:
                out.append(current)
                current = []
        else:
            current.append(p)
    if current:
        out.append(current)
    return out


def line_chart(
    series: Sequence[Series],
    x_labels: Sequence[str],
    *,
    box: Optional[Box] = None,
    decimals: int = 1,
    aria_label: str = "",
    highlight_last_label: bool = True,
) -> str:
    """Biểu đồ đường nhiều chuỗi, dùng chung 1 trục y (không bao giờ 2 trục).

    Nhãn giá trị chỉ đặt ở điểm cuối mỗi chuỗi và tự tách nhau theo chiều dọc
    nếu trùng chỗ, để không đè lên nhau khi các đường hội tụ.
    """
    box = box or Box()
    all_values = [v for s in series for v in s.values]
    bottom, top, step = axis_domain(all_values)
    xs = _x_positions(box, len(x_labels))

    parts: list[str] = []
    label = aria_label or ", ".join(s.label for s in series)
    parts.append(
        f'<svg viewBox="0 0 {box.width} {box.height}" width="100%" height="{box.height}" '
        f'role="img" aria-label="{html.escape(label)}">'
    )

    # Lưới + nhãn trục y: hairline, lùi về sau, số tròn
    tick = bottom
    while tick <= top + step / 2:
        y = _y_for(tick, bottom, top, box)
        is_base = abs(tick - bottom) < step / 1000
        cls = "axis-line" if is_base else "grid-line"
        parts.append(f'<line class="{cls}" x1="{box.plot_left}" y1="{y:.1f}" x2="{box.plot_right}" y2="{y:.1f}"/>')
        parts.append(
            f'<text class="muted" x="{box.plot_left - 6}" y="{y + 4:.1f}" text-anchor="end">{_fmt(tick, decimals)}</text>'
        )
        tick += step

    # Nhãn trục x — kỳ mới nhất in đậm để mắt bắt được "hiện tại" ngay.
    # Nhãn rỗng bị bỏ qua: cách để vẽ HẾT điểm nhưng chỉ ghi thưa nhãn.
    label_y = box.plot_bottom + 18
    for i, (x, text) in enumerate(zip(xs, x_labels)):
        if not text:
            continue
        last = highlight_last_label and i == len(x_labels) - 1
        cls = "" if last else ' class="muted"'
        weight = ' style="font-weight:600"' if last else ""
        parts.append(f'<text{cls}{weight} x="{x:.1f}" y="{label_y}" text-anchor="middle">{html.escape(text)}</text>')

    # Đường + điểm cuối
    end_labels: list[tuple[float, float, str, str]] = []  # (x, y, text, color)
    for s in series:
        points: list[Optional[tuple[float, float]]] = []
        for x, v in zip(xs, s.values):
            points.append(None if v is None else (x, _y_for(v, bottom, top, box)))
        for seg in _segments(points):
            if len(seg) == 1:  # điểm đơn lẻ giữa 2 khoảng thiếu — vẫn phải thấy
                cx, cy = seg[0]
                parts.append(
                    f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{MARKER_RADIUS}" fill="var({s.color})" '
                    f'stroke="var(--surface-1)" stroke-width="{SURFACE_RING}"/>'
                )
                continue
            pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in seg)
            parts.append(
                f'<polyline points="{pts}" fill="none" stroke="var({s.color})" '
                f'stroke-width="{LINE_WIDTH}" stroke-linejoin="round" stroke-linecap="round"/>'
            )
        real = [p for p in points if p is not None]
        if real:
            cx, cy = real[-1]
            last_value = [v for v in s.values if v is not None][-1]
            tip = f"{s.label}: {_fmt(last_value, decimals)}{s.value_suffix}"
            parts.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{MARKER_RADIUS}" fill="var({s.color})" '
                f'stroke="var(--surface-1)" stroke-width="{SURFACE_RING}">'
                f"<title>{html.escape(tip)}</title></circle>"
            )
            if s.end_label:
                end_labels.append((cx, cy, _fmt(last_value, decimals), s.color))

    # Tách nhãn cuối chồng nhau: đẩy xuống tối thiểu 13px, giữ nguyên thứ tự cao-thấp
    end_labels.sort(key=lambda t: t[1])
    min_gap = 13.0
    adjusted: list[tuple[float, float, str, str]] = []
    for x, y, text, color in end_labels:
        if adjusted and y - adjusted[-1][1] < min_gap:
            y = adjusted[-1][1] + min_gap
        adjusted.append((x, y, text, color))
    for x, y, text, _color in adjusted:
        parts.append(f'<text class="muted" x="{x + 8:.1f}" y="{y + 4:.1f}">{text}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def legend(series: Sequence[Series]) -> str:
    """Chú giải — LUÔN có khi ≥2 chuỗi (không để người đọc chỉ dựa vào màu)."""
    if len(series) < 2:
        return ""  # 1 chuỗi: tiêu đề đã nói rõ đang vẽ gì, hộp chú giải chỉ chiếm chỗ
    items = "".join(
        f'<span class="item"><span class="swatch" style="background:var({s.color})"></span>'
        f"{html.escape(s.label)}</span>"
        for s in series
    )
    return f'<div class="legend">{items}</div>'


def bar_chart(
    bars: Sequence[Bar],
    *,
    box: Optional[Box] = None,
    decimals: int = 1,
    value_suffix: str = "",
    aria_label: str = "",
    baseline_at_zero: bool = True,
) -> str:
    """Cột dọc, nhãn giá trị trên đầu cột, tên ở dưới.

    `baseline_at_zero=True` (mặc định) vì cột cắt gốc 0 sẽ phóng đại chênh lệch
    — đây là lỗi biểu đồ kinh điển, không đánh đổi để "trông rõ hơn".
    """
    box = box or Box(width=380, height=240, left=30, right=20, bottom=52)
    if not bars:
        return ""
    values = [b.value for b in bars]
    bottom = 0.0 if baseline_at_zero else axis_domain(values)[0]
    top = axis_domain(values + [bottom])[1]
    step = nice_step(top - bottom)

    parts: list[str] = [
        f'<svg viewBox="0 0 {box.width} {box.height}" width="100%" height="{box.height}" '
        f'role="img" aria-label="{html.escape(aria_label or "biểu đồ cột")}">'
    ]
    tick = bottom
    while tick <= top + step / 2:
        y = _y_for(tick, bottom, top, box)
        cls = "axis-line" if abs(tick - bottom) < step / 1000 else "grid-line"
        parts.append(f'<line class="{cls}" x1="{box.plot_left}" y1="{y:.1f}" x2="{box.plot_right}" y2="{y:.1f}"/>')
        tick += step

    slot = (box.plot_right - box.plot_left) / len(bars)
    thickness = min(BAR_MAX_THICKNESS * 2.2, slot * 0.55)  # chừa air, không lấp kín slot
    baseline_y = _y_for(bottom, bottom, top, box)
    for i, bar in enumerate(bars):
        center = box.plot_left + slot * (i + 0.5)
        y = _y_for(bar.value, bottom, top, box)
        height = max(0.0, baseline_y - y)
        parts.append(
            f'<rect x="{center - thickness / 2:.1f}" y="{y:.1f}" width="{thickness:.1f}" '
            f'height="{height:.1f}" rx="{BAR_CORNER_RADIUS}" fill="var({bar.color})">'
            f"<title>{html.escape(bar.label)}: {_fmt(bar.value, decimals)}{value_suffix}</title></rect>"
        )
        parts.append(
            f'<text x="{center:.1f}" y="{y - 6:.1f}" text-anchor="middle" style="font-weight:600">'
            f"{_fmt(bar.value, decimals)}{value_suffix}</text>"
        )
        parts.append(
            f'<text class="muted" x="{center:.1f}" y="{box.plot_bottom + 16}" text-anchor="middle">'
            f"{html.escape(bar.label)}</text>"
        )
        if bar.sublabel:
            parts.append(
                f'<text class="muted" x="{center:.1f}" y="{box.plot_bottom + 30}" text-anchor="middle">'
                f"{html.escape(bar.sublabel)}</text>"
            )
    parts.append("</svg>")
    return "\n".join(parts)


def diverging_bar_chart(
    bars: Sequence[Bar],
    *,
    box: Optional[Box] = None,
    decimals: int = 0,
    value_suffix: str = "",
    aria_label: str = "",
    negative_color: str = "--s-orange",
    positive_color: str = "--s-blue",
) -> str:
    """Cột mọc HAI CHIỀU từ đường 0 — dùng cho dữ liệu có DẤU (lãi/lỗ).

    `bar_chart` thường không dùng được ở đây: nó kẹp chiều cao ở 0 nên mọi cột
    âm biến mất. Đây là dạng *diverging*: hai cực + điểm giữa trung tính, và
    chính vị trí so với đường 0 mới là thứ mang nghĩa.

    Màu KHÔNG dùng cặp đỏ–xanh lá quen thuộc: chạy
    `dataviz/scripts/validate_palette.js` trên cặp đó cho ΔE deutan = 5,9 —
    dưới cả ngưỡng sàn 6, tức người mù màu đỏ–lục không tách được hai cực.
    Cặp cam–xanh dương đạt ΔE 24,7 (light) và 26,8 (dark). Dấu +/− vẫn được
    ghi thẳng trên từng cột nên nghĩa không bao giờ phụ thuộc riêng vào màu.
    """
    box = box or Box(width=620, height=260, left=44, right=20, bottom=52)
    if not bars:
        return ""
    values = [b.value for b in bars]
    span = max(abs(min(values)), abs(max(values))) or 1.0
    step = nice_step(span * 2)
    top = math.ceil(span / step) * step
    bottom = -top  # đối xứng quanh 0: lệch trục sẽ phóng đại một phía

    parts: list[str] = [
        f'<svg viewBox="0 0 {box.width} {box.height}" width="100%" height="{box.height}" '
        f'role="img" aria-label="{html.escape(aria_label or "biểu đồ cột hai chiều")}">'
    ]
    tick = bottom
    while tick <= top + step / 2:
        y = _y_for(tick, bottom, top, box)
        is_zero = abs(tick) < step / 1000
        parts.append(f'<line class="{"axis-line" if is_zero else "grid-line"}" '
                      f'x1="{box.plot_left}" y1="{y:.1f}" x2="{box.plot_right}" y2="{y:.1f}"/>')
        parts.append(f'<text class="muted" x="{box.plot_left - 6}" y="{y + 4:.1f}" '
                      f'text-anchor="end">{_fmt(tick, decimals)}</text>')
        tick += step

    zero_y = _y_for(0.0, bottom, top, box)
    slot = (box.plot_right - box.plot_left) / len(bars)
    thickness = min(BAR_MAX_THICKNESS * 1.6, slot * 0.6)
    for i, bar in enumerate(bars):
        center = box.plot_left + slot * (i + 0.5)
        y = _y_for(bar.value, bottom, top, box)
        color = negative_color if bar.value < 0 else positive_color
        # Chừa SEGMENT_GAP quanh đường 0 để cột không dính vào trục
        if bar.value < 0:
            rect_y, height = zero_y + SEGMENT_GAP, max(0.0, y - zero_y - SEGMENT_GAP)
        else:
            rect_y, height = y, max(0.0, zero_y - y - SEGMENT_GAP)
        parts.append(
            f'<rect x="{center - thickness / 2:.1f}" y="{rect_y:.1f}" width="{thickness:.1f}" '
            f'height="{height:.1f}" rx="{BAR_CORNER_RADIUS}" fill="var({color})">'
            f"<title>{html.escape(bar.label)}: {bar.value:+,.{decimals}f}{value_suffix}</title></rect>"
        )
        # Nhãn giá trị luôn nằm PHÍA NGOÀI cột (dưới với cột âm, trên với cột
        # dương) nên không bao giờ đè lên đường 0 hay lên chính cột.
        label_y = (rect_y + height + 14) if bar.value < 0 else (rect_y - 6)
        parts.append(
            f'<text x="{center:.1f}" y="{label_y:.1f}" text-anchor="middle" '
            f'style="font-weight:600">{bar.value:+,.{decimals}f}{value_suffix}</text>'
        )
        parts.append(
            f'<text class="muted" x="{center:.1f}" y="{box.plot_bottom + 16}" text-anchor="middle">'
            f"{html.escape(bar.label)}</text>"
        )
        if bar.sublabel:
            parts.append(
                f'<text class="muted" x="{center:.1f}" y="{box.plot_bottom + 30}" text-anchor="middle">'
                f"{html.escape(bar.sublabel)}</text>"
            )
    parts.append("</svg>")
    return "\n".join(parts)


def stacked_bar(segments: Sequence[Segment], *, width: int = 620, height: int = 56) -> str:
    """Thanh ngang 100% — dùng cho phân bổ tài sản.

    Các mảng cách nhau đúng 2px màu nền (surface gap): mắt tự tách được mà
    không cần vẽ viền quanh mảng (viền là mực không phải dữ liệu).
    """
    total = sum(s.value for s in segments if s.value > 0)
    if total <= 0:
        return ""
    bar_y, bar_h = 16, 24
    usable = width - SEGMENT_GAP * max(0, len(segments) - 1)
    parts: list[str] = []
    desc = ", ".join(f"{s.label} {s.value / total * 100:.1f}%" for s in segments)
    parts.append(
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="Phân bổ: {html.escape(desc)}">'
    )
    x = 0.0
    for i, seg in enumerate(segments):
        w = usable * seg.value / total
        parts.append(
            f'<rect x="{x:.1f}" y="{bar_y}" width="{max(w, 2):.1f}" height="{bar_h}" '
            f'rx="{BAR_CORNER_RADIUS}" fill="var({seg.color})">'
            f"<title>{html.escape(seg.label)}: {_fmt(seg.value / total * 100)}%</title></rect>"
        )
        x += w + (SEGMENT_GAP if i < len(segments) - 1 else 0)
    parts.append("</svg>")
    return "\n".join(parts)


def allocation_legend(segments: Sequence[Segment]) -> str:
    total = sum(s.value for s in segments if s.value > 0)
    if total <= 0:
        return ""
    items = "".join(
        f'<span class="item"><span class="swatch" style="background:var({s.color})"></span>'
        f"{html.escape(s.label)} — {_fmt(s.value / total * 100)}%</span>"
        for s in segments
    )
    return f'<div class="legend">{items}</div>'


def thin_labels(labels: Sequence[str], max_shown: int = 9) -> list[str]:
    """Giữ thưa nhãn trục x khi lịch sử dài — VẪN vẽ hết điểm dữ liệu.

    Lịch sử tích lũy 2 snapshot/ngày nên sau vài tuần nhãn sẽ chồng nhau thành
    một vệt đen. Giải pháp là bớt NHÃN chứ không bớt DỮ LIỆU: nhãn cuối luôn
    được giữ (đó là "hiện tại", thứ người đọc tìm trước nhất).
    """
    n = len(labels)
    if n <= max_shown:
        return list(labels)
    stride = math.ceil(n / max_shown)
    out = []
    for i, text in enumerate(labels):
        keep_last = i == n - 1
        # Đếm ngược từ cuối để nhãn cuối luôn nằm trên mốc chia
        out.append(text if keep_last or (n - 1 - i) % stride == 0 else "")
    return out

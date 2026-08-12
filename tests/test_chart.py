"""Test reporting/chart.py — toạ độ SVG phải TÍNH ĐÚNG từ dữ liệu.

Đây là lớp thay thế cho ~71 toạ độ viết tay trước đây. Nếu module này sai,
biểu đồ sẽ vẽ dối trong khi số liệu vẫn đúng — nên phải test cả hình học.
"""
import re

from reporting.chart import (
    Bar,
    Box,
    Segment,
    Series,
    _fmt,
    axis_domain,
    bar_chart,
    legend,
    line_chart,
    nice_step,
    stacked_bar,
)


# --- Trục: bước chia phải "tròn", miền phải bao trọn dữ liệu ---

def test_nice_step_theo_bac_1_2_5():
    assert nice_step(10) == 2.5 or nice_step(10) in (2, 2.5, 5)
    # bước luôn thuộc dạng {1,2,5}×10^n
    for span in (0.4, 3, 17, 96, 1234, 45678):
        step = nice_step(span)
        mantissa = step / (10 ** __import__("math").floor(__import__("math").log10(step)))
        assert round(mantissa, 6) in (1.0, 2.0, 5.0, 10.0), f"span={span} -> step={step}"


def test_nice_step_span_khong_hop_le_khong_lam_sap():
    assert nice_step(0) == 1.0
    assert nice_step(-5) == 1.0
    assert nice_step(float("nan")) == 1.0


def test_axis_domain_bao_tron_du_lieu():
    bottom, top, step = axis_domain([142.0, 147.5, 145.4])
    assert bottom <= 142.0
    assert top >= 147.5
    assert step > 0


def test_axis_domain_chuoi_phang_van_ve_duoc():
    bottom, top, step = axis_domain([58.5, 58.5, 58.5])
    assert bottom < 58.5 < top  # có miền quanh giá trị, không chia cho 0


def test_axis_domain_toan_bo_thieu_du_lieu():
    assert axis_domain([None, None]) == (0.0, 1.0, 1.0)


# --- Số kiểu Việt Nam ---

def test_fmt_dinh_dang_viet_nam():
    assert _fmt(1234.5) == "1.234,5"
    assert _fmt(147.5) == "147,5"
    assert _fmt(1668, 0) == "1.668"


# --- Biểu đồ đường ---

def test_line_chart_thieu_du_lieu_thi_NGAT_duong_khong_noi_suy():
    """None ở giữa phải cắt thành 2 polyline — nội suy qua chỗ thiếu là bịa số."""
    s = Series(label="X", values=[1.0, 2.0, None, 4.0, 5.0], color="--s-blue")
    svg = line_chart([s], ["a", "b", "c", "d", "e"])
    assert svg.count("<polyline") == 2


def test_line_chart_lien_tuc_thi_mot_duong():
    s = Series(label="X", values=[1.0, 2.0, 3.0], color="--s-blue")
    assert line_chart([s], ["a", "b", "c"]).count("<polyline") == 1


def test_line_chart_diem_don_le_van_hien_thi():
    """Giá trị bị kẹp giữa 2 khoảng thiếu vẫn phải thấy được (vẽ điểm)."""
    s = Series(label="X", values=[None, 5.0, None], color="--s-blue")
    svg = line_chart([s], ["a", "b", "c"])
    assert "<polyline" not in svg
    assert "<circle" in svg


def test_line_chart_gia_tri_cao_hon_nam_tren_trong_svg():
    """Trục y SVG hướng xuống: giá trị lớn phải có y NHỎ hơn."""
    s = Series(label="X", values=[10.0, 20.0], color="--s-blue")
    svg = line_chart([s], ["a", "b"])
    pts = re.search(r'points="([^"]+)"', svg).group(1).split()
    y_dau = float(pts[0].split(",")[1])
    y_cuoi = float(pts[1].split(",")[1])
    assert y_cuoi < y_dau


def test_line_chart_nam_trong_khung_ve():
    box = Box(width=700, height=240)
    s = Series(label="X", values=[100.0, 250.0, 175.0], color="--s-blue")
    svg = line_chart([s], ["a", "b", "c"], box=box)
    for x, y in re.findall(r"(\d+\.?\d*),(\d+\.?\d*)", re.search(r'points="([^"]+)"', svg).group(1)):
        assert box.plot_left <= float(x) <= box.plot_right
        assert box.plot_top <= float(y) <= box.plot_bottom


def test_line_chart_nhan_cuoi_trung_cho_thi_tach_nhau():
    """2 chuỗi gần bằng nhau: nhãn phải cách nhau ≥13px, không đè chữ lên chữ."""
    a = Series(label="A", values=[10.0, 20.0], color="--s-red")
    b = Series(label="B", values=[10.0, 20.2], color="--s-orange")
    svg = line_chart([a, b], ["x", "y"])
    # Nhãn giá trị cuối là thẻ text DUY NHẤT không có text-anchor (nhãn trục
    # x/y đều có) — bám vào đó để không bắt lẫn nhãn trục.
    ys = sorted(float(m) for m in re.findall(r'<text class="muted" x="[\d.]+" y="([\d.]+)">', svg))
    assert len(ys) == 2, f"phải có đúng 2 nhãn cuối, thấy {len(ys)}"
    assert ys[1] - ys[0] >= 12.9, f"2 nhãn cuối chỉ cách {ys[1] - ys[0]:.1f}px — sẽ đè nhau"


def test_line_chart_moi_chuoi_dung_mau_rieng():
    a = Series(label="A", values=[1.0], color="--s-red")
    b = Series(label="B", values=[2.0], color="--s-blue")
    svg = line_chart([a, b], ["x"])
    assert "var(--s-red)" in svg and "var(--s-blue)" in svg


def test_line_chart_diem_cuoi_co_vong_mau_nen():
    """Vòng 2px màu nền giúp điểm đọc được khi chồng lên đường khác."""
    s = Series(label="X", values=[1.0, 2.0], color="--s-blue")
    svg = line_chart([s], ["a", "b"])
    assert 'stroke="var(--surface-1)"' in svg and 'stroke-width="2"' in svg


# --- Chú giải: bắt buộc khi ≥2 chuỗi, bỏ khi 1 chuỗi ---

def test_legend_bat_buoc_khi_nhieu_chuoi():
    out = legend([Series("A", [1.0], "--s-red"), Series("B", [2.0], "--s-blue")])
    assert "A" in out and "B" in out


def test_legend_bo_qua_khi_mot_chuoi():
    assert legend([Series("A", [1.0], "--s-red")]) == ""


# --- Biểu đồ cột ---

def test_bar_chart_cot_cat_goc_0_khong_phong_dai():
    """Cột phải mọc từ 0; nếu cắt trục, chênh lệch nhỏ sẽ bị phóng đại sai."""
    svg = bar_chart([Bar("A", 8.0), Bar("B", 7.4), Bar("C", 7.1)])
    heights = [float(h) for h in re.findall(r'<rect [^>]*height="(\d+\.?\d*)"', svg)]
    # tỷ lệ chiều cao phải xấp xỉ tỷ lệ giá trị vì gốc là 0
    assert abs(heights[1] / heights[0] - 7.4 / 8.0) < 0.02


def test_bar_chart_rong_khong_lap_kin_slot():
    svg = bar_chart([Bar("A", 1.0), Bar("B", 2.0)], box=Box(width=380, height=240, left=30, right=20))
    widths = [float(w) for w in re.findall(r'<rect [^>]*width="(\d+\.?\d*)"', svg)]
    slot = (380 - 30 - 20) / 2
    assert all(w < slot for w in widths)


def test_bar_chart_rong_tra_ve_chuoi_rong():
    assert bar_chart([]) == ""


# --- Thanh xếp lớp (phân bổ tài sản) ---

def test_stacked_bar_ty_le_dung_va_co_khoang_trang():
    segs = [Segment("Vàng", 75.0, "--s-yellow"), Segment("Tiết kiệm", 21.9, "--s-blue"),
            Segment("Mặt", 3.1, "--s-aqua")]
    svg = stacked_bar(segs, width=620)
    widths = [float(w) for w in re.findall(r'width="(\d+\.?\d*)" height="24"', svg)]
    assert abs(widths[0] / sum(widths) - 0.75) < 0.01
    # tổng chiều rộng + 2 khoảng trắng 2px = chiều rộng khung
    assert abs(sum(widths) + 4 - 620) < 1.5


def test_stacked_bar_tong_bang_khong_tra_ve_rong():
    assert stacked_bar([Segment("A", 0, "--s-blue")]) == ""


def test_stacked_bar_mang_rat_nho_van_nhin_thay():
    segs = [Segment("To", 999.0, "--s-yellow"), Segment("Ti", 0.05, "--s-aqua")]
    svg = stacked_bar(segs, width=620)
    widths = [float(w) for w in re.findall(r'width="(\d+\.?\d*)" height="24"', svg)]
    assert min(widths) >= 2  # có sàn 2px, không biến mất khỏi hình

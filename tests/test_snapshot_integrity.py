"""Snapshot rỗng thì tệ hơn không có snapshot — và giá cũ không được đóng dấu
ngày hôm nay.

Bằng chứng, tự tạo ra trong lúc rà soát ngày 29/08: chạy
`python3 scripts/fetch_market_snapshot.py` khi mạng bị chặn. Script thoát mã 0
như thành công, và ghi vào `data/history.jsonl`:

    {"date": "2026-08-29", "ky": "chieu", "vnindex": {}, "gold": {},
     "vcb": {"close": 60300, "change_pct": 1.01, "volume": 2.714},
     "ctd": {"close": 62400, "change_pct": 0.48, "volume": 0.248}}

Hai chuyện sai cùng lúc, và chúng khuếch đại nhau:

1. **Không có giá vàng.** Vàng là ~76% tài sản. Hậu quả đo được ngay:
   `reporting/dashboard_builder.value_at()` trả `total_trieu=None` cho kỳ mới
   nhất — đường tài sản ròng thủng đúng ở đầu bên phải; và Decision Engine ghi
   tiếp 4 quyết định dựa trên kỳ rỗng đó.
2. **Giá VCB/CTD là nến ngày 10/08 mang nhãn ngày 29/08.** Đây là rửa dữ liệu
   cũ thành dữ liệu mới. `analytics/price_sanity.py` không bắt được, vì nó so
   với snapshot LIỀN TRƯỚC và giá chép nguyên thì lệch 0% — qua mọi kiểm tra
   một cách hoàn hảo.

`validate_snapshot()` của trend.py bắt giá SAI (âm, bằng 0, bất khả thi). Nó
không bắt giá THIẾU, vì thiếu không phải một giá trị bất thường. Đó là khoảng
trống mà bộ test này lấp.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from analytics.data_quality import EOD_MAX_AGE_DAYS  # noqa: E402
from fetch_market_snapshot import build_snapshot, refuse_reasons  # noqa: E402

DU = {"close": 60300, "change_pct": 1.01, "volume": 2.7, "as_of": "2026-08-29"}
CU = {"close": 60300, "change_pct": 1.01, "volume": 2.7, "as_of": "2026-08-10"}


# --- Từ chối ghi khi thiếu thứ không thể thiếu ------------------------------

def test_khong_co_gia_vang_thi_TU_CHOI_ghi():
    snap = build_snapshot("2026-08-29", "chieu", None, None, None, None)
    ly_do = refuse_reasons(snap)
    assert ly_do, "snapshot không có giá vàng vẫn được cho ghi"
    assert any("vàng" in r.lower() for r in ly_do)


def test_khong_co_ty_gia_thi_TU_CHOI_ghi():
    """Có XAU/USD mà không có tỷ giá thì vẫn không quy ra VND được."""
    snap = build_snapshot("2026-08-29", "chieu", 4340.4, None, None, None)
    assert any("tỷ giá" in r.lower() for r in refuse_reasons(snap))


def test_du_gia_vang_va_ty_gia_thi_ghi_duoc():
    snap = build_snapshot("2026-08-29", "chieu", 4340.4, 26350.0, DU, DU)
    assert refuse_reasons(snap) == []


def test_snapshot_rong_khong_dinh_gia_duoc_danh_muc():
    """Nối thẳng nguyên nhân với hậu quả: chính xác cái đã thủng đường tài sản."""
    from portfolio.loader import load_portfolio
    from reporting.dashboard_builder import value_at

    rong = build_snapshot("2026-08-29", "chieu", None, None, None, None)
    assert value_at(rong, load_portfolio()).total_trieu is None
    assert refuse_reasons(rong), "kỳ không định giá được lẽ ra phải bị từ chối ghi"

    day_du = build_snapshot("2026-08-29", "chieu", 4340.4, 26350.0, DU, DU)
    assert value_at(day_du, load_portfolio()).total_trieu is not None


# --- Không đóng dấu ngày hôm nay lên nến cũ --------------------------------

def test_nen_EOD_cu_KHONG_duoc_ghi_vao_snapshot():
    snap = build_snapshot("2026-08-29", "chieu", 4340.4, 26350.0, CU, CU)
    assert "vcb" not in snap and "ctd" not in snap


def test_nen_EOD_moi_van_duoc_ghi():
    snap = build_snapshot("2026-08-29", "chieu", 4340.4, 26350.0, DU, DU)
    assert snap["vcb"]["close"] == 60300


def test_cuoi_tuan_khong_bi_loai_oan():
    """Đóng cửa thứ Sáu đọc sáng thứ Hai vẫn là phiên gần nhất — ngưỡng dùng
    chung EOD_MAX_AGE_DAYS phải nuốt được một cuối tuần bình thường."""
    thu_sau = dict(DU, as_of="2026-08-07")
    snap = build_snapshot("2026-08-10", "chieu", 4340.4, 26350.0, thu_sau, None)
    assert (3 <= EOD_MAX_AGE_DAYS) and "vcb" in snap


def test_nen_khong_ro_ngay_thi_khong_tu_ket_luan():
    """Không biết ngày nến thì không kết luận cũ/mới ở đây — để tầng validate
    khác lo, chứ không im lặng vứt dữ liệu đi."""
    khong_ngay = {"close": 60300, "change_pct": 1.01, "volume": 2.7}
    snap = build_snapshot("2026-08-29", "chieu", 4340.4, 26350.0, khong_ngay, None)
    assert "vcb" in snap


def test_gia_chep_nguyen_qua_duoc_price_sanity_nen_khong_the_trong_cho_no():
    """Vì sao phải chặn ở đây chứ không dựa vào price_sanity: giá chép nguyên
    lệch 0% so với kỳ trước nên nó qua kiểm tra biên độ sàn một cách hoàn hảo."""
    from analytics.price_sanity import PLAUSIBLE, check_price

    kq = check_price("VCB", 60.3, 60.3, reference_date="2026-08-10",
                     target_date="2026-08-29")
    assert kq.verdict != "IMPLAUSIBLE"
    assert kq.verdict in (PLAUSIBLE, "NO_REFERENCE")

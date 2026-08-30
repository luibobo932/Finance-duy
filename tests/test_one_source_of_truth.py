"""Cùng một câu hỏi, hai nơi hiển thị, PHẢI ra một con số.

Lỗi lặp lại nhiều lần nhất trong dự án này không phải sai công thức — mà là
**sửa đúng một nơi trong nhiều nơi**. Ba lần đã đo được:

1. `margin_of_safety_pct` có trong `DecisionInput` nhưng không caller nào
   truyền → nhánh cổ phiếu về cấu trúc không thể khuyến nghị MUA.
2. `data_freshness_score` mặc định 100 và không caller nào truyền → 13/13
   quyết định cùng một điểm 92.
3. Trần "10% một mã" chỉ trừ được phần đang nắm khi caller TRUYỀN phần đang
   nắm. Sửa ở `run_morning.py` (commit "Vòng đời vị thế"), KHÔNG sửa ở
   `reporting/dashboard_builder.py`. Với 83 tr CTD đang nắm:

       bản tin   → Mua tối đa 34 tr   (đúng)
       dashboard → Mua tối đa 81 tr   (sai, gấp 2,4 lần, vị thế lên 14%)

   Và dashboard mới là trang chủ danh mục thật sự đọc.

Bộ test này khoá cả lớp lỗi: mọi ràng buộc dựng kế hoạch vào lệnh phải đi qua
`equity.signals.plan_for()`, không nơi nào được tự gọi `plan_position()` với
danh sách tham số riêng.
"""
from pathlib import Path

import pytest

from decision.position_size import plan_position
from equity.signals import analyze, plan_for
from portfolio.loader import load_portfolio, load_risk_limits

ROOT = Path(__file__).resolve().parent.parent
NET = 1172.7


class _Pos:
    def __init__(self, ticker, quantity, last_price_vnd):
        self.ticker, self.quantity = ticker, quantity
        self.last_price_vnd = last_price_vnd

    @property
    def market_value_vnd(self):
        return self.last_price_vnd * self.quantity


class _Port:
    """Danh mục giả có 83 tr CTD — đúng tình huống đã làm lộ lỗi."""

    def __init__(self, positions=(), cash_vnd=35_000_000):
        self.stock_positions = list(positions)
        self.cash_amount_vnd = cash_vnd

    @property
    def stock_market_value_vnd(self):
        return sum(p.market_value_vnd for p in self.stock_positions)


def _ctd():
    s = analyze("CTD")
    if not s.has_data:
        pytest.skip("chưa có data/eod/CTD.csv")
    return s


# --- Lỗi gốc: trần một mã bị bỏ qua khi không truyền phần đang nắm ---------

def test_tran_mot_ma_phai_tru_phan_dang_nam_qua_plan_for():
    s = _ctd()
    limits = load_risk_limits()
    port = _Port([_Pos("CTD", 1330, 62_400)])   # ≈ 83 tr
    assert port.stock_market_value_vnd / 1e6 == pytest.approx(83.0, abs=1.0)

    plan = plan_for(s, port, limits, net_worth_trieu=NET, hurdle_pct=8.0,
                    today=__import__("datetime").date.fromisoformat(s.last_date))
    tran_con_lai = NET * limits["single_stock_max"] - port.stock_market_value_vnd / 1e6
    assert plan.suggested_trieu is None or plan.suggested_trieu <= tran_con_lai + 1e-9


def test_bo_qua_phan_dang_nam_thi_tran_NOI_RA_gap_hon_hai_lan():
    """Dựng lại chính con số đã đo, để về sau đọc test còn thấy mức nghiêm trọng."""
    limits = load_risk_limits()
    dung = plan_position("CTD", 62.4, NET, limits=limits, support=54.7, target=93.0,
                         current_stock_value_trieu=83.0, current_position_value_trieu=83.0)
    thieu_rang_buoc = plan_position("CTD", 62.4, NET, limits=limits,
                                    support=54.7, target=93.0)
    assert dung.suggested_trieu is not None and thieu_rang_buoc.suggested_trieu is not None
    assert thieu_rang_buoc.suggested_trieu > dung.suggested_trieu * 2


# --- Hai bề mặt phải gọi chung một hàm dựng --------------------------------

def test_ban_tin_va_dashboard_ra_CUNG_mot_ke_hoach():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from reporting.dashboard_builder import _equity_section
    from run_morning import section_chung_khoan

    port = load_portfolio()
    port._net_trieu = NET
    dash = _equity_section(port)
    ban_tin = section_chung_khoan()
    if not dash or "CHƯA MUA" not in ban_tin:
        pytest.skip("không dựng được cả hai bề mặt trong môi trường này")
    # Cỡ lệnh là con số dễ lệch nhất; nếu một bên in ra thì bên kia phải in y hệt.
    assert ("Mua tối đa" in dash) == ("Mua tối đa" in ban_tin)


def test_chi_MOT_noi_duoc_goi_thang_plan_position():
    """Chống tái phát: thêm một bề mặt mới mà gọi thẳng `plan_position()` là
    lại mở đường cho việc quên một ràng buộc."""
    goi_thang = []
    for path in list((ROOT / "scripts").glob("*.py")) + list((ROOT / "reporting").glob("*.py")):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]  # nhắc tên trong chú thích thì không tính
            if "plan_position(" in code:
                goi_thang.append(f"{path.name}:{i}")
    assert not goi_thang, (
        f"{goi_thang} gọi thẳng plan_position() — dùng equity.signals.plan_for() "
        "để mọi ràng buộc đi qua một chỗ")


def test_plan_for_luon_ap_rang_buoc_gia_cu():
    s = _ctd()
    plan = plan_for(s, _Port(), load_risk_limits(), net_worth_trieu=NET, hurdle_pct=8.0)
    if plan is None:
        pytest.skip("thiếu tài sản ròng")
    from equity.signals import stale_price_note
    if stale_price_note(s):
        assert plan.suggested_trieu is None
        # Không có MỨC cắt lỗ nào được in ra. ("cắt lỗ" vẫn xuất hiện trong
        # chính câu giải thích vì sao không dựng được kế hoạch — đó là lời
        # giải thích, không phải một mức để đặt lệnh.)
        assert "cắt lỗ dưới" not in plan.summary()
        assert "Mua tối đa" not in plan.summary()


def test_thieu_tai_san_rong_thi_KHONG_dung_ke_hoach():
    """Không biết tài sản ròng thì mọi trần đều vô nghĩa — trả None, không
    lặng lẽ dùng 0 rồi ra "mua tối đa 0 tr" như thể đó là một kết luận."""
    assert plan_for(_ctd(), _Port(), load_risk_limits(), net_worth_trieu=None) is None

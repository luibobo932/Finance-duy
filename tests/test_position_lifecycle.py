"""Test vòng đời vị thế: khuyến nghị MUA → giao dịch → mức thoát được canh.

Hệ thống vừa nói được "MUA CTD tối đa 83 tr". Làm đúng theo lời khuyên đó rồi
đo lại thì tài sản ròng nhảy từ 1.172,7 lên 1.255,7 tr — **tự nhiên nhiều thêm
83 triệu**, vì `config/portfolio.yaml` mô tả *đang nắm gì* chứ không mô tả *đã
đổi gì lấy gì*. Và mức cắt lỗ 53,61 chỉ tồn tại trong một dòng chữ đã trôi qua.
"""
from datetime import date

import pytest

from decision.decision_log import extract_ref_price
from decision.stop_registry import build_stop_alert, stop_alert_id, sync_stops
from portfolio.transactions import (
    BUY,
    SELL,
    Transaction,
    holdings_from,
    reconcile,
    validate,
    validate_history,
)


def _tx(asset="CTD", side=BUY, qty=1330, price=62.4, amount=83.0, funded="ban_vang", d=None):
    return Transaction(date=d or date(2026, 8, 15), asset=asset, side=side,
                       quantity=qty, price=price, amount_trieu=amount, funded_from=funded)


class _Pos:
    def __init__(self, ticker, quantity):
        self.ticker, self.quantity = ticker, quantity


# --- Giao dịch MUA phải khai NGUỒN TIỀN -----------------------------------

def test_mua_khong_khai_nguon_tien_bi_TU_CHOI():
    """Một giao dịch mua không có nguồn tiền là giao dịch chưa xảy ra — đó
    chính là cách tài sản ròng bị thổi phồng 83 triệu."""
    errs = validate(_tx(funded=None))
    assert any("funded_from" in e for e in errs)


def test_nguon_tien_khong_hop_le_bi_tu_choi():
    assert validate(_tx(funded="tren_troi_roi_xuong"))


def test_BAN_khong_bat_buoc_khai_nguon():
    """Bán thì tiền ĐI RA khỏi tài sản đó; vào đâu là chuyện của giao dịch sau."""
    assert validate(_tx(side=SELL, funded=None)) == []


def test_so_luong_hoac_gia_am_bi_tu_choi():
    assert validate(_tx(qty=0))
    assert validate(_tx(price=-1))


# --- Giá vốn suy ra TỪ giao dịch, không phải từ trí nhớ -------------------

def test_gia_von_binh_quan_gia_quyen():
    h = holdings_from([_tx(qty=1000, amount=60.0), _tx(qty=1000, amount=70.0)])["CTD"]
    assert h.quantity == 2000
    assert h.cost_basis_trieu == pytest.approx(130.0)
    assert h.avg_cost == pytest.approx(65.0)


def test_ban_lam_giam_gia_von_theo_TY_LE_khong_theo_gia_ban():
    """Dùng giá bán sẽ khiến giá vốn phần còn lại nhảy theo thị trường, trong
    khi giá vốn là chi phí đã bỏ ra, không phải thị giá."""
    txs = [_tx(qty=1000, amount=60.0), _tx(side=SELL, qty=500, price=200.0, amount=100.0)]
    h = holdings_from(txs)["CTD"]
    assert h.quantity == 500
    assert h.cost_basis_trieu == pytest.approx(30.0)  # nửa giá vốn, không dính giá bán
    assert h.avg_cost == pytest.approx(60.0)


def test_ban_het_thi_khong_con_vi_the():
    assert holdings_from([_tx(qty=1000, amount=60.0),
                          _tx(side=SELL, qty=1000, amount=70.0)]) == {}


def test_ban_nhieu_hon_dang_nam_bi_bat():
    errs = validate_history([_tx(qty=100, amount=6.0), _tx(side=SELL, qty=500, amount=30.0)])
    assert errs and "không nhất quán" in errs[0]


# --- Đối chiếu khai báo vs giao dịch --------------------------------------

def test_khai_vi_the_ma_KHONG_co_giao_dich_thi_bao_thoi_phong():
    """Đây là ca đã xảy ra thật khi thử làm theo khuyến nghị MUA."""
    issues = reconcile([_Pos("CTD", 1330)], [])
    assert issues and "thổi phồng" in issues[0]


def test_lech_so_luong_duoc_bao_kem_muc_lech():
    issues = reconcile([_Pos("CTD", 2000)], [_tx(qty=1330)])
    assert issues and "+670" in issues[0]


def test_khop_thi_khong_bao_gi():
    assert reconcile([_Pos("CTD", 1330)], [_tx(qty=1330)]) == []


def test_co_giao_dich_ma_config_khong_khai_cung_bi_bao():
    issues = reconcile([], [_tx(qty=1330)])
    assert issues and "không khai vị thế" in issues[0]


def test_reconcile_KHONG_tu_sua_config():
    """Sửa danh mục phải là hành động có ý thức của chủ danh mục."""
    pos = _Pos("CTD", 1330)
    reconcile([pos], [])
    assert pos.quantity == 1330  # không bị đụng tới


# --- Giá tham chiếu phải theo ĐÚNG MÃ -------------------------------------

def test_gia_tham_chieu_equity_theo_dung_ma():
    """Bản cũ ghi cứng ('vcb','close'): một quyết định về CTD sẽ được ghi kèm
    GIÁ CỦA VCB — sai lệch âm thầm làm hỏng vĩnh viễn mọi phép chấm điểm."""
    snap = {"vcb": {"close": 60300}, "ctd": {"close": 62400}}
    assert extract_ref_price(snap, "equity", "CTD") == ("ctd.close", 62400.0)
    assert extract_ref_price(snap, "equity", "VCB") == ("vcb.close", 60300.0)


def test_thieu_ticker_thi_tra_None_khong_lay_bua_mot_ma():
    """Ghi sai giá tham chiếu còn tệ hơn không ghi — nó làm hỏng mọi phép chấm
    điểm về sau mà không có gì báo lỗi."""
    assert extract_ref_price({"vcb": {"close": 60300}}, "equity") is None


def test_ma_khong_co_trong_snapshot_thi_tra_None():
    assert extract_ref_price({"vcb": {"close": 60300}}, "equity", "HPG") is None


# --- Mức cắt lỗ phải được CANH --------------------------------------------

def test_cat_lo_thanh_canh_bao_THAT():
    a = build_stop_alert("CTD", 53.61, entry=62.4, target=93.0)
    assert a["type"] == "below" and a["level"] == 53.61
    assert a["auto"] is True and a["asset"] == "CTD"
    assert "CẮT LỖ" in a["note"] and "14.1%" in a["note"]


def test_them_canh_bao_cho_vi_the_moi():
    alerts, changes = sync_stops([], [{"ticker": "CTD", "stop": 53.61, "entry": 62.4}])
    assert len(alerts) == 1 and alerts[0]["id"] == stop_alert_id("CTD")
    assert any("thêm cảnh báo cắt lỗ CTD" in c for c in changes)


def test_KHONG_dung_toi_nguong_dat_tay():
    manual = {"id": "vcb-sup", "asset": "VCB", "type": "below", "level": 58.17,
              "note_manual": "nhận định tay"}
    alerts, _ = sync_stops([manual], [{"ticker": "CTD", "stop": 53.61}])
    assert manual in alerts


def test_vi_the_dong_thi_GO_canh_bao():
    """Ngưỡng của một vị thế không còn tồn tại sẽ kêu mãi mà không mang thông
    tin nào — đúng bệnh alert fatigue đã sửa ở analytics/alert_health.py."""
    old = build_stop_alert("CTD", 53.61)
    alerts, changes = sync_stops([old], [])
    assert alerts == []
    assert any("gỡ cảnh báo cắt lỗ CTD" in c for c in changes)


def test_doi_muc_cat_lo_thi_cap_nhat_va_NOI_RO():
    alerts, changes = sync_stops([build_stop_alert("CTD", 53.61)],
                                 [{"ticker": "CTD", "stop": 55.0}])
    assert alerts[0]["level"] == 55.0
    assert any("cập nhật cắt lỗ CTD" in c for c in changes)


def test_khong_co_stop_thi_khong_dang_ky():
    alerts, _ = sync_stops([], [{"ticker": "CTD"}])
    assert alerts == []


def test_chay_lai_KHONG_sinh_trung():
    pos = [{"ticker": "CTD", "stop": 53.61}]
    a1, _ = sync_stops([], pos)
    a2, changes = sync_stops(a1, pos)
    assert len(a2) == 1 and changes == []

"""Dữ liệu EOD cũ phải CHẶN được khuyến nghị cổ phiếu — đúng như nó đang chặn vàng.

Bằng chứng khởi nguồn, đo ngày 29/08/2026 trên chính repo này, cùng một lần chạy:

    scripts/health_check.py  → ❌ EOD CTD: mới nhất 2026-08-10 — đã 19 ngày,
                                 gấp >3× ngưỡng 4 ngày. Automation đã ngừng chạy.
    scripts/run_morning.py   → CTD 62.40 (EOD 2026-08-10) → MUA THĂM DÒ
                                 (tin cậy 80/100) · Mua tối đa 81 tr ·
                                 cắt lỗ dưới 53.61 · mục tiêu 93.00

Nửa hệ thống gọi dữ liệu là hỏng, nửa kia dựng trên nó một lệnh mua kèm mức cắt
lỗ. Trong khi ĐÚNG kỳ đó, vàng — đọc từ snapshot cũ y hệt — bị Risk Officer
chặn thành CHƯA ĐỦ DỮ LIỆU (30/100). Cơ chế chặn không thiếu, nhánh cổ phiếu chỉ
không đi qua nó: `decide_for` ghi cứng `data_freshness_score=100.0` và dựng
`RiskContext` không có `data_stale`, nên rule `stale_critical_data` về cấu trúc
không thể chạm tới cổ phiếu.

Đây là cùng một lớp lỗi đã sửa hai lần trước — `margin_of_safety_pct` không
được truyền nên nhánh cổ phiếu không thể khuyến nghị MUA, và
`data_completeness_pct` mặc định 100 nên 13/13 quyết định vàng cùng điểm 92.
Trường có tồn tại, kiểu đúng, nhưng KHÔNG CALLER NÀO TRUYỀN. Test dưới đây khoá
đường đó lại cho nhánh cổ phiếu.
"""
from datetime import date, timedelta

import pytest

from analytics.data_quality import EOD_MAX_AGE_DAYS, STALE_ESCALATE_FACTOR, assess_equity
from decision.position_size import plan_position
from equity.signals import analyze, data_quality_for, decide_for

LIMITS = {"single_stock_max": 0.10, "total_stock_max": 0.20}
NET = 1172.7


def _rows(closes, start="2026-06-01"):
    d0 = date.fromisoformat(start)
    return [{"date": (d0 + timedelta(days=i)).isoformat(), "open": str(c),
             "high": str(c * 1.01), "low": str(c * 0.99), "close": str(c),
             "volume": "1000"}
            for i, c in enumerate(closes)]


def _signal(n=30):
    return analyze("X", rows=_rows([50 + i * 0.5 for i in range(n)]))


def _last(signal):
    return date.fromisoformat(signal.last_date)


# --- Đo độ mới của chuỗi EOD -----------------------------------------------

def test_nen_trong_ngay_la_tuoi_100():
    s = _signal()
    assert data_quality_for(s, _last(s)).freshness_score == 100.0


def test_dong_cua_thu_sau_doc_sang_thu_hai_van_TUOI():
    """Ngưỡng phải nuốt được một cuối tuần bình thường, nếu không hệ thống tự
    chặn chính nó mỗi sáng thứ Hai — cảnh báo luôn bật thì thành cảnh báo vô
    nghĩa, đúng cái bẫy đã sửa ở analytics/alert_health.py."""
    thu_sau = date(2026, 8, 7)
    thu_hai = date(2026, 8, 10)
    assert (thu_hai - thu_sau).days == 3 <= EOD_MAX_AGE_DAYS
    a = assess_equity("X", thu_sau, thu_hai)
    assert a.freshness_score == 100.0 and a.data_stale is False


def test_qua_nguong_thi_diem_giam_dan_chu_khong_sap_ngay():
    """Cũ hơn ngưỡng một chút KHÁC hẳn cũ ba tuần — điểm phải phản ánh mức độ,
    dùng chung thang tuyến tính với vàng."""
    base = date(2026, 8, 10)
    giua = assess_equity("X", base, base + timedelta(days=EOD_MAX_AGE_DAYS + 2))
    assert 0 < giua.freshness_score < 100
    assert giua.data_stale is False  # chưa về 0 thì chưa phải lý do chặn hẳn


def test_qua_gap_ba_lan_nguong_thi_ve_0_va_la_STALE():
    base = date(2026, 8, 10)
    het = assess_equity("X", base, base + timedelta(days=EOD_MAX_AGE_DAYS * STALE_ESCALATE_FACTOR))
    assert het.freshness_score == 0.0 and het.data_stale is True


def test_khong_co_file_EOD_la_THIEU_chu_khong_phai_moi():
    """Thiếu hẳn ≠ cũ, và tuyệt đối không được đọc thành 'tươi'."""
    a = assess_equity("KHONGTONTAI")
    assert a.data_missing_critical is True
    assert a.freshness_score == 0.0


def test_do_moi_do_tren_CHUOI_DA_NAP_chu_khong_doc_lai_dia():
    """Nhãn hành động và nhãn chất lượng phải nói về CÙNG một bộ dữ liệu.

    Dựng đúng tình huống hai chỗ có thể lệch nhau: mã CTD có file thật trên đĩa
    (ngày 2026-08-10), nhưng tín hiệu được nạp từ chuỗi khác. Nếu phép đo lén
    đọc lại đĩa thì nó sẽ chấm điểm cho một chuỗi mà quyết định không hề dùng.
    """
    tren_dia = assess_equity("CTD")
    s = analyze("CTD", rows=_rows([50 + i * 0.5 for i in range(30)], start="2026-06-01"))
    assert s.last_date != "2026-08-10"

    a = data_quality_for(s, _last(s))
    assert a.freshness_score == 100.0, "đã đọc lại đĩa thay vì dùng chuỗi đã nạp"
    assert a.freshness_score != tren_dia.freshness_score or tren_dia.freshness_score == 100.0


# --- Chặn quyết định: đúng cơ chế đang chặn vàng ----------------------------

def test_du_lieu_cu_bien_khuyen_nghi_MUA_thanh_CHUA_DU_DU_LIEU():
    """Lỗi gốc, dựng lại nguyên trạng: cùng một tín hiệu, chỉ khác ngày đọc."""
    s = analyze("CTD")
    if not s.has_data:
        pytest.skip("chưa có data/eod/CTD.csv")
    trong_ngay = decide_for(s, today=_last(s))
    assert trong_ngay["action"] == "BUY_SMALL"

    cu = decide_for(s, today=_last(s) + timedelta(days=EOD_MAX_AGE_DAYS * STALE_ESCALATE_FACTOR))
    assert cu["action"] == "NO_DECISION"
    assert cu["risk_veto"] is True
    assert "stale_critical_data" in " ".join(cu["reasons"])


def test_du_lieu_cu_keo_diem_tin_cay_xuong_va_ha_hang_chat_luong():
    s = _signal()
    tuoi = decide_for(s, today=_last(s))
    cu = decide_for(s, today=_last(s) + timedelta(days=60))
    assert cu["confidence"] < tuoi["confidence"]
    assert cu["data_quality"] == "POOR"


def test_do_moi_KHONG_con_la_hang_so_100():
    """Chốt lại đúng lớp lỗi đã lặp ba lần: trường có tồn tại nhưng không
    caller nào truyền, nên mặc định biến thành số cứng."""
    s = _signal()
    diem = {decide_for(s, today=_last(s) + timedelta(days=n))["confidence"]
            for n in (0, 30)}
    assert len(diem) > 1, "độ mới không ảnh hưởng gì tới điểm — lại là hằng số"


def test_co_phieu_va_vang_bi_chan_bang_CUNG_MOT_rule():
    """Hai trụ cột không được có hai tiêu chuẩn 'quá cũ' khác nhau."""
    from decision.risk_officer import VETO_RULES

    s = _signal()
    cu = decide_for(s, today=_last(s) + timedelta(days=60))
    assert "stale_critical_data" in VETO_RULES
    assert "stale_critical_data" in " ".join(cu["reasons"])


# --- Chặn kế hoạch vào lệnh: chỗ nguy hiểm nhất -----------------------------

def test_gia_cu_thi_KHONG_con_muc_cat_lo_nao_duoc_in_ra():
    """Mức cắt lỗ mới là chỗ hỏng nặng nhất, không phải nhãn hành động: 53.61
    chính xác tới hai chữ số thập phân, suy từ vùng hỗ trợ của 19 ngày trước,
    về một thị trường hệ thống không còn nhìn thấy."""
    p = plan_position("CTD", 62.4, NET, limits=LIMITS, support=54.7, target=93.0,
                      price_stale_note="giá tham chiếu đã cũ 19 ngày")
    assert p.suggested_trieu is None
    assert p.summary().startswith("CHƯA MUA")
    assert "53.61" not in p.summary()
    assert "cắt lỗ" not in p.summary()


def test_ly_do_chan_dung_dau_tien_truoc_moi_ly_do_khac():
    """Các blocker khác bàn về CHẤT LƯỢNG của lệnh; cái này bàn về việc có
    được phép bàn hay không — nên nó phải là câu đầu tiên."""
    p = plan_position("VCB", 60.3, NET, limits=LIMITS, support=60.2, target=61.9,
                      hurdle_pct=8.0, price_stale_note="giá tham chiếu đã cũ")
    assert p.blockers[0] == "giá tham chiếu đã cũ"


def test_khong_co_canh_bao_cu_thi_ke_hoach_giu_nguyen_nhu_truoc():
    """Sửa lỗi này không được làm hỏng đường chạy bình thường."""
    p = plan_position("CTD", 62.4, NET, limits=LIMITS, support=54.7, target=93.0)
    assert p.suggested_trieu is not None and "cắt lỗ dưới 53.61" in p.summary()


# --- Bản tin không được tự mâu thuẫn ---------------------------------------

def test_ban_tin_khong_vua_noi_CHUA_DU_DU_LIEU_vua_bao_mua_bao_nhieu():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from run_morning import section_chung_khoan

    muc = section_chung_khoan()
    for dong in muc.splitlines():
        if "CHƯA ĐỦ DỮ LIỆU" in dong:
            break
    else:
        pytest.skip("dữ liệu EOD đang còn mới — không dựng lại được tình huống")
    assert "Mua tối đa" not in muc, "vẫn in cỡ lệnh cho một mã không đủ dữ liệu"
    assert "DỮ LIỆU CŨ" in muc


def test_health_check_va_decision_engine_dung_CHUNG_mot_nguong():
    """Hai nơi cùng nói 'EOD quá cũ' thì phải cùng một con số, nếu không hệ
    thống lại tự mâu thuẫn theo kiểu khác."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from health_check import FRESHNESS_TARGETS

    nguong_eod = {t[2] for t in FRESHNESS_TARGETS if t[0].startswith("EOD ")}
    assert nguong_eod == {EOD_MAX_AGE_DAYS}


def test_dashboard_khong_in_co_lenh_canh_nhan_CHUA_DU_DU_LIEU():
    """Trang HTML là thứ chủ danh mục THẬT SỰ đọc — nó từng in "CHƯA ĐỦ DỮ
    LIỆU ĐỂ RA QUYẾT ĐỊNH" ở cột Khuyến nghị và "Mua tối đa 81 tr · cắt lỗ
    dưới 53.61" ở cột ngay bên cạnh, trên cùng một hàng."""
    from portfolio.loader import load_portfolio
    from reporting.dashboard_builder import _equity_section

    port = load_portfolio()
    port._net_trieu = NET
    muc = _equity_section(port)
    if "CHƯA ĐỦ DỮ LIỆU" not in muc:
        pytest.skip("dữ liệu EOD đang còn mới — không dựng lại được tình huống")
    assert "Mua tối đa" not in muc
    assert "DỮ LIỆU CŨ" in muc


def test_ban_tin_va_dashboard_dung_CHUNG_mot_cau_giai_thich():
    """Hai nơi hiển thị, một định nghĩa — để không nơi nào quên mất."""
    s = analyze("CTD")
    if not s.has_data:
        pytest.skip("chưa có data/eod/CTD.csv")
    from equity.signals import stale_price_note

    cu = stale_price_note(s, _last(s) + timedelta(days=60))
    assert cu and "fetch_eod.py" in cu
    assert stale_price_note(s, _last(s)) is None

"""Test equity/signals.py — trụ cột cổ phiếu: xây xong nhưng chưa cắm điện.

Bằng chứng: `section_tong_quan()` in "Cổ phiếu watchlist: xem mục Chứng khoán
bên dưới" ở MỌI kỳ bản tin, trong khi không có mục nào như vậy.
`equity/technical.py` đã có đủ chỉ báo và chạy được ngay trên 43 phiên EOD thật
của VCB/CTD; nhánh equity của Decision Engine cũng đã có sẵn. Không caller nào
gọi tới cả hai.
"""
from datetime import date

import pytest

from decision.action_mapper import Action
from decision.policy_engine import DecisionInput, derive_initial_action
from equity.signals import VOLUME_SPIKE_RATIO, analyze, decide_for


def _rows(closes, volumes=None):
    volumes = volumes or [1000.0] * len(closes)
    return [{"date": f"2026-06-{1 + i:02d}", "open": str(c), "high": str(c * 1.01),
             "low": str(c * 0.99), "close": str(c), "volume": str(volumes[i])}
            for i, c in enumerate(closes)]


def _phien_cuoi(signal):
    """Ngày của nến EOD cuối cùng trong chuỗi — dùng làm "hôm nay" cho các test
    KHÔNG nói về độ mới dữ liệu.

    Không có nó thì mọi test dưới đây là bom hẹn giờ: rule chặn dữ liệu cũ
    (`stale_critical_data`) chạy TRƯỚC mọi rule khác và trả NO_DECISION, nên
    một test về rule quản trị doanh nghiệp sẽ đổi kết quả chỉ vì hôm nay là
    ngày nào — nó xanh khi vừa viết và đỏ ba tuần sau, mà chẳng có dòng code
    nào thay đổi. Test độ mới nằm riêng ở tests/test_equity_freshness.py.
    """
    return date.fromisoformat(signal.last_date)


# --- Đọc dữ liệu: thiếu thì báo thiếu --------------------------------------

def test_khong_co_file_EOD_thi_bao_khong_co_du_lieu():
    s = analyze("KHONGTONTAI")
    assert s.has_data is False and s.close is None


def test_du_lieu_hong_khong_lam_no():
    s = analyze("X", rows=[{"date": "2026-06-01", "close": "không phải số"}])
    assert s.has_data is False


def test_khong_du_phien_thi_trend_la_None_chu_khong_phai_TRUNG_TINH():
    """Chưa đo được KHÁC đi ngang — cùng nguyên tắc đã áp cho vàng."""
    s = analyze("X", rows=_rows([50.0, 51.0, 52.0]))
    assert s.has_data is True and s.trend_label is None


def test_du_phien_thi_do_duoc_xu_huong():
    s = analyze("X", rows=_rows([50 + i * 0.5 for i in range(30)]))
    assert s.trend_label == "TICH_CUC"


def test_giam_lien_tuc_ra_TIEU_CUC():
    s = analyze("X", rows=_rows([80 - i * 0.5 for i in range(30)]))
    assert s.trend_label == "TIEU_CUC"


# --- Cảnh báo khối lượng ----------------------------------------------------

def test_KLGD_dot_bien_duoc_canh_bao_kem_huong_dan_soi_noi_bo():
    vols = [1000.0] * 29 + [1000.0 * VOLUME_SPIKE_RATIO * 2]
    s = analyze("X", rows=_rows([50 + i * 0.1 for i in range(30)], vols))
    assert s.volume_flag is not None
    assert "nội bộ" in s.volume_flag


def test_KLGD_binh_thuong_thi_khong_canh_bao():
    s = analyze("X", rows=_rows([50 + i * 0.1 for i in range(30)]))
    assert s.volume_flag is None


# --- "GIỮ" là vô nghĩa với mã KHÔNG nắm giữ --------------------------------

def test_khong_co_vi_the_thi_KHONG_duoc_khuyen_GIU():
    """Chủ danh mục đã bán hết cổ phiếu — VCB/CTD chỉ là danh sách theo dõi.
    "GIỮ" một mã không có vị thế là lời khuyên không thực hiện được."""
    inp = DecisionInput(asset="VCB", asset_class="equity", trend_label="TICH_CUC",
                        has_position=False)
    assert derive_initial_action(inp) == Action.WATCH.value


def test_co_vi_the_thi_GIU_moi_co_nghia():
    inp = DecisionInput(asset="VCB", asset_class="equity", trend_label="TICH_CUC",
                        has_position=True)
    assert derive_initial_action(inp) == Action.HOLD.value


def test_mac_dinh_la_KHONG_co_vi_the():
    """Danh mục này đã bán hết cổ phiếu nên watchlist là trạng thái phổ biến
    hơn — mặc định phải khớp thực tế, không phải khớp giả định lạc quan."""
    assert DecisionInput(asset="X", asset_class="equity").has_position is False


def test_xu_huong_tieu_cuc_van_la_CHO_XAC_NHAN_du_co_vi_the_hay_khong():
    for held in (True, False):
        inp = DecisionInput(asset="X", asset_class="equity", trend_label="TIEU_CUC",
                            has_position=held)
        assert derive_initial_action(inp) == Action.WAIT_FOR_CONFIRMATION.value


# --- Decision Engine chạy thật cho cổ phiếu --------------------------------

def test_chua_co_du_lieu_thi_KHONG_ra_quyet_dinh():
    """Không có tín hiệu thì không ra quyết định, chứ không ra một quyết định
    'trung tính' cho có."""
    assert decide_for(analyze("KHONGTONTAI")) is None


def test_ra_duoc_quyet_dinh_day_du_truong():
    s = analyze("X", rows=_rows([50 + i * 0.5 for i in range(30)]))
    d = decide_for(s, today=_phien_cuoi(s))
    for key in ("action", "action_vi", "confidence", "reasons", "data_quality", "risk_veto"):
        assert key in d


def test_rule_quan_tri_van_chan_duoc_qua_duong_nay():
    """Rule quản trị doanh nghiệp của Risk Officer trước nay chưa từng chạy vì
    nhánh equity không được gọi. Nối vào rồi thì nó phải có tác dụng thật."""
    s = analyze("X", rows=_rows([50 + i * 0.5 for i in range(30)]))
    d = decide_for(s, governance_status="INDICTED", today=_phien_cuoi(s))
    assert d["action"] == Action.STAND_ASIDE.value
    assert d["risk_veto"] is True


def test_dang_xac_minh_KHONG_bi_chan_han():
    """Đúng yêu cầu gốc: 'đang xác minh'/'mời làm việc' chỉ cảnh báo, không
    quy kết — thuật ngữ pháp lý phải giữ đúng mức."""
    s = analyze("X", rows=_rows([50 + i * 0.5 for i in range(30)]))
    d = decide_for(s, governance_status="UNDER_VERIFICATION", today=_phien_cuoi(s))
    assert d["action"] != Action.STAND_ASIDE.value


# --- Nhãn phải kèm căn cứ ---------------------------------------------------

def test_evidence_neu_ro_chi_bao_va_so_phien():
    s = analyze("X", rows=_rows([50 + i * 0.5 for i in range(30)]))
    e = s.evidence()
    assert "RSI(14)" in e and "30 phiên" in e


def test_evidence_khi_thieu_du_lieu_noi_ro_thieu_gi():
    s = analyze("X", rows=_rows([50.0, 51.0, 52.0]))
    assert "chưa đủ cho RSI(14)" in s.evidence()


# --- Một định nghĩa xu hướng cho CẢ vàng lẫn cổ phiếu ----------------------

def test_vang_va_co_phieu_dung_CHUNG_mot_dinh_nghia_xu_huong():
    """Chép logic nhãn xu hướng sang equity/ sẽ tạo nguồn sự thật thứ hai cho
    cùng một câu hỏi — đúng cái bẫy mà analytics/ta_core.py ra đời để tránh."""
    from analytics.ta_core import trend_from_indicators
    from gold.indicators import trend_label as gold_trend

    for rsi_v, hist in ((70.0, 1.0), (30.0, -1.0), (50.0, 0.0), (None, None)):
        expected = trend_from_indicators(rsi_v, hist)
        assert gold_trend({"rsi14": rsi_v, "macd": {"hist": hist}}) == expected


# --- Dữ liệu thật trong repo ------------------------------------------------

def test_chay_duoc_tren_EOD_that_cua_VCB_va_CTD():
    for t in ("VCB", "CTD"):
        s = analyze(t)
        if not s.has_data:
            pytest.skip(f"chưa có data/eod/{t}.csv")
        assert s.sessions >= 15
        assert s.trend_label is not None
        assert decide_for(s, today=_phien_cuoi(s)) is not None


def test_ban_tin_khong_con_tro_toi_muc_KHONG_TON_TAI():
    """Lỗi khởi nguồn: TỔNG QUAN hứa 'xem mục Chứng khoán bên dưới' mà không
    có mục nào như vậy."""
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "scripts"))
    from run_morning import section_chung_khoan, section_tong_quan

    assert "Chứng khoán bên dưới" in section_tong_quan(None)
    assert "## CHỨNG KHOÁN" in section_chung_khoan()

"""Test analytics/data_quality.py + hai lỗ hổng khiến điểm tin cậy là hằng số.

Bằng chứng khởi nguồn: cả 13 quyết định trong data/decisions.jsonl (20/7→10/8)
đều ghi confidence=92, data_quality=GOOD — không kỳ nào khác kỳ nào, kể cả kỳ
mà giá nhẫn trong nước đã ngừng thu thập 23 ngày và file hiệu chuẩn vàng (nguồn
duy nhất của mọi chỉ báo) chỉ có 1 dòng ngày 18/7.
"""
from datetime import date

import pytest

from analytics.data_quality import (
    STALE_ESCALATE_FACTOR,
    Assessment,
    Source,
    assess,
    assess_gold,
    gold_sources,
)
from decision.confidence_score import signal_agreement_from_labels
from decision.policy_engine import DecisionInput, decide
from decision.risk_officer import RiskContext
from portfolio.loader import load_decision_rules, load_risk_limits

TODAY = date(2026, 8, 14)
LIMITS = load_risk_limits()
RULES = load_decision_rules()


def _src(name="X", as_of=date(2026, 8, 14), max_age=2, critical=True):
    return Source(name, as_of, max_age, critical=critical)


# --- Thang điểm độ mới ------------------------------------------------------

def test_trong_nguong_thi_diem_tuyet_doi():
    assert _src(as_of=date(2026, 8, 13), max_age=2).freshness(TODAY) == 100.0


def test_qua_moc_leo_thang_thi_ve_0():
    """Cùng mốc mà health check leo thang WARN → FAIL: không có hai định nghĩa
    'quá cũ' trong một hệ thống."""
    old = date(2026, 8, 14 - 2 * STALE_ESCALATE_FACTOR)
    assert _src(as_of=old, max_age=2).freshness(TODAY) == 0.0


def test_giua_hai_moc_thi_giam_tuyen_tinh():
    # ngưỡng 2, mốc 0 điểm ở 6 ngày; 4 ngày = đúng giữa
    assert _src(as_of=date(2026, 8, 10), max_age=2).freshness(TODAY) == 50.0


def test_thieu_han_KHAC_voi_cu():
    """Thiếu không phải 'cũ vô hạn' — nó tính vào completeness, không phải
    freshness. Trừ hai lần vào một sự việc là phạt chồng."""
    assert _src(as_of=None).freshness(TODAY) is None


# --- Tổng hợp ---------------------------------------------------------------

def test_lay_MIN_khong_lay_trung_binh():
    """Trung bình cho phép một nguồn tươi che một nguồn mục."""
    a = assess([_src("tuoi", date(2026, 8, 14)), _src("muc", date(2026, 7, 1))], TODAY)
    assert a.freshness_score == 0.0
    assert "muc" in a.binding


def test_nguon_doi_chieu_KHONG_keo_diem_nhung_van_duoc_ghi_nhan():
    a = assess([_src("chinh", date(2026, 8, 14)),
                _src("doi_chieu", date(2026, 7, 1), critical=False)], TODAY)
    assert a.freshness_score == 100.0
    assert any("doi_chieu" in s for s in a.stale)
    assert any("kiểm chứng chéo" in n for n in a.notes)


def test_thieu_nguon_lam_giam_completeness():
    a = assess([_src("co"), _src("thieu", as_of=None)], TODAY)
    assert a.completeness_pct == pytest.approx(50.0)
    assert a.missing == ["thieu"] and a.data_missing_critical is True


def test_khong_khai_bao_nguon_nao_thi_0_diem_chu_khong_phai_100():
    """Không có gì để kiểm tra là lý do KHÔNG tin, không phải tin tuyệt đối —
    đây chính là cái bẫy mặc-định-100 đang phải sửa."""
    a = assess([], TODAY)
    assert a.freshness_score == 0.0 and a.completeness_pct == 0.0


def test_moi_nguon_trong_yeu_deu_thieu_thi_freshness_0():
    a = assess([_src("a", as_of=None), _src("b", date(2026, 8, 14), critical=False)], TODAY)
    assert a.freshness_score == 0.0


def test_data_stale_chi_bat_khi_da_ve_0_diem():
    """Cũ hơn ngưỡng một chút chưa phải 'đừng tin quyết định này' — nếu không,
    mọi thứ trễ 1 ngày sẽ bị hạ xuống POOR và cảnh báo lại mất tác dụng."""
    hoi_cu = assess([_src(as_of=date(2026, 8, 11), max_age=2)], TODAY)
    assert hoi_cu.freshness_score > 0 and hoi_cu.data_stale is False
    qua_cu = assess([_src(as_of=date(2026, 7, 1), max_age=2)], TODAY)
    assert qua_cu.data_stale is True


def test_explain_neu_ro_nguon_nao_ghim_diem():
    a = assess([_src("XAU/USD", date(2026, 8, 10), max_age=2)], TODAY)
    assert "XAU/USD" in a.explain() and "độ mới" in a.explain()


# --- Bộ nguồn vàng thật -----------------------------------------------------

def test_gold_sources_gom_dung_nhung_gi_quyet_dinh_dua_vao():
    names = [s.name for s in gold_sources([])]
    assert any("XAU/USD" in n for n in names)
    assert any("hiệu chuẩn" in n for n in names)


def test_gia_nhan_trong_nuoc_la_nguon_DOI_CHIEU_khong_phai_dinh_gia():
    """networth.py định giá vàng từ XAU/USD + hệ số quy đổi, không đọc thẳng
    ring_sell. Xếp nó là trọng yếu sẽ kéo điểm về 0 vì một nguồn mà quyết định
    không thực sự phụ thuộc — sai bản chất."""
    ring = [s for s in gold_sources([]) if "nhẫn" in s.name][0]
    assert ring.critical is False


def test_file_hieu_chuan_it_mau_phai_duoc_canh_bao():
    """MỨC giá tiệm neo vào 1 ảnh bảng giá — mà toàn bộ con số 'vàng 76%' dựa
    trên đó. Tuổi file không nói ra điều này, số mẫu mới nói."""
    cal = [s for s in gold_sources([]) if "hiệu chuẩn" in s.name][0]
    if cal.as_of is not None:
        assert "mẫu" in cal.note and "ảnh bảng giá" in cal.note


def test_chay_duoc_tren_du_lieu_that():
    a = assess_gold()
    assert isinstance(a, Assessment)
    assert 0 <= a.freshness_score <= 100 and 0 <= a.completeness_pct <= 100


# --- Đồng thuận: một mình không phải là nhất trí ---------------------------

def test_mot_tin_hieu_KHONG_duoc_cham_100_dong_thuan():
    """Công thức cũ tính 1/1 = 100%, nghe như ba nguồn cùng xác nhận. Hệ thống
    chỉ nối được trend_label cho vàng nên 25% trọng số bị chấm tuyệt đối ở cả
    13 quyết định đã ghi."""
    assert signal_agreement_from_labels("TICH_CUC", None, None) == 50.0


def test_hai_tin_hieu_dong_y_van_la_100():
    assert signal_agreement_from_labels("TICH_CUC", None, "TICH_CUC") == 100.0


def test_khong_co_tin_hieu_nao_van_trung_tinh():
    assert signal_agreement_from_labels(None, None) == 50.0


# --- Nối vào Decision Engine ------------------------------------------------

def test_chua_do_chat_luong_thi_KHONG_duoc_bao_GOOD():
    """Mặc định cũ (100.0) khiến 'chưa kiểm tra' bị đọc thành 'đã kiểm tra và
    hoàn hảo' — nguồn gốc của điểm 92 bất biến."""
    d = decide(DecisionInput(asset="Vàng nhẫn", asset_class="gold", trend_label="TRUNG_TINH"),
               RiskContext(gold_allocation_pct=0.76), LIMITS, RULES)
    assert d["data_quality"] != "GOOD"
    assert any("CHƯA ĐO" in r for r in d["reasons"])


def test_do_that_thi_diem_THAP_HON_mac_dinh_cu():
    ctx = RiskContext(gold_allocation_pct=0.76)
    cu = decide(DecisionInput(asset="V", asset_class="gold", trend_label="TRUNG_TINH",
                              data_completeness_pct=100, data_freshness_score=100),
                ctx, LIMITS, RULES)
    moi = decide(DecisionInput(asset="V", asset_class="gold", trend_label="TRUNG_TINH",
                               data_completeness_pct=100, data_freshness_score=50),
                 ctx, LIMITS, RULES)
    assert moi["confidence"] < cu["confidence"]
    assert moi["data_quality"] == "FAIR"


def test_ly_do_phai_neu_ro_diem_du_lieu_khong_chi_neu_con_so():
    d = decide(DecisionInput(asset="V", asset_class="gold", trend_label="TRUNG_TINH",
                             data_completeness_pct=100, data_freshness_score=50),
               RiskContext(gold_allocation_pct=0.76), LIMITS, RULES)
    assert any("độ mới" in r for r in d["reasons"])
    assert any("1 nhóm tín hiệu" in r for r in d["reasons"])


def test_quyet_dinh_thuc_te_hom_nay_khong_con_la_92():
    """Kiểm trên dữ liệu THẬT trong repo: với chất lượng dữ liệu đo được, điểm
    tin cậy phải khác con số 92 đã đóng băng suốt 13 kỳ."""
    dq = assess_gold()
    d = decide(DecisionInput(asset="Vàng nhẫn", asset_class="gold", trend_label="TRUNG_TINH",
                             data_completeness_pct=dq.completeness_pct,
                             data_freshness_score=dq.freshness_score),
               RiskContext(gold_allocation_pct=0.76, data_stale=dq.data_stale,
                           data_missing_critical=dq.data_missing_critical),
               LIMITS, RULES)
    assert d["confidence"] != 92

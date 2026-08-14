"""Test gold/indicators.py — nhãn xu hướng phải đến từ dữ liệu, và phải phân
biệt "chưa đo được" với "đo rồi, đi ngang".

Bằng chứng khởi nguồn: module đọc mặc định `xuan_trieu_gold_history.csv`, file
có ĐÚNG 1 dòng ngày 18/7, nên mọi chỉ báo trả None suốt gần một tháng — trong
khi `data/history.jsonl` có 19 quan sát XAU/USD thật nằm không ai dùng.
"""
import pytest

from gold.indicators import analyze, load_xau_series, trend_evidence, trend_label


def _hist(values, start_day=1):
    return [{"date": f"2026-07-{start_day + i:02d}", "ky": "chieu", "gold": {"xauusd": v}}
            for i, v in enumerate(values)]


# --- Đọc đúng nguồn ---------------------------------------------------------

def test_doc_chuoi_xau_tu_history_jsonl():
    s = load_xau_series(_hist([4000, 4010, 4020]))
    assert [v for _, v in s] == [4000, 4010, 4020]


def test_bo_qua_ky_thieu_gia_khong_dien_so():
    hist = _hist([4000, 4010])
    hist.append({"date": "2026-07-05", "ky": "chieu", "gold": {}})
    hist.append({"date": "2026-07-06", "ky": "chieu"})
    assert len(load_xau_series(hist)) == 2


def test_gia_am_hoac_0_bi_loai():
    hist = _hist([4000]) + [{"date": "2026-07-09", "ky": "chieu", "gold": {"xauusd": 0}}]
    assert len(load_xau_series(hist)) == 1


def test_analyze_mac_dinh_dung_chuoi_the_gioi():
    a = analyze(history=_hist([4000] * 20))
    assert a["column"] == "xauusd" and a["source"] == "data/history.jsonl"
    assert a["sessions"] == 20


def test_van_do_duoc_chuoi_gia_tiem_khi_chi_dinh():
    """Không phá đường cũ — chuỗi giá tiệm vẫn dùng được để đối chiếu."""
    a = analyze("shop_buy_trieu")
    assert a["source"] == "xuan_trieu_gold_history.csv"


# --- "Chưa đo được" KHÁC "đi ngang" ----------------------------------------

def test_khong_du_du_lieu_tra_None_chu_khong_phai_TRUNG_TINH():
    """TRUNG_TINH là một kết luận; thiếu dữ liệu là CHƯA có kết luận. Gộp hai
    thứ khiến bản tin in 'Xu hướng: TRUNG_TINH' như một phát hiện, và bộ đếm
    đồng thuận tính nó là 1 tín hiệu có mặt."""
    assert trend_label(analyze(history=_hist([4000, 4010]))) is None


def test_khong_co_du_lieu_nao_cung_tra_None():
    assert trend_label(analyze(history=[])) is None


def test_di_ngang_that_su_van_tra_TRUNG_TINH():
    """RSI quanh 50 = ĐÃ ĐO và trung tính — phải khác None.

    Đây là điểm mấu chốt của cả module: TRUNG_TINH và None từ nay là hai câu
    trả lời khác nhau, và chỉ câu đầu mới là một nhận định.
    """
    values, v = [], 4000.0
    for i in range(19):  # dao động đều quanh một mức
        v += 6 if i % 2 == 0 else -6
        values.append(v)
    a = analyze(history=_hist(values))
    assert a["rsi14"] is not None
    assert trend_label(a) == "TRUNG_TINH"


# --- Không đòi đủ bộ chỉ báo mới chấm --------------------------------------

def test_chi_co_RSI_van_cham_duoc():
    """MACD cần 26 điểm. Đòi đủ bộ nghĩa là với 19 điểm hiện có, RSI 78,3 —
    vùng quá mua rõ rệt — bị vứt đi và báo 'trung tính'."""
    a = analyze(history=_hist([4000 + i * 25 for i in range(19)]))
    assert a["rsi14"] is not None and a["macd"] is None
    assert trend_label(a) == "TICH_CUC"


def test_giam_lien_tuc_ra_TIEU_CUC():
    a = analyze(history=_hist([4500 - i * 25 for i in range(19)]))
    assert trend_label(a) == "TIEU_CUC"


# --- Nhãn phải kèm căn cứ ---------------------------------------------------

def test_evidence_neu_ro_chi_bao_va_so_ky():
    a = analyze(history=_hist([4000 + i * 25 for i in range(19)]))
    e = trend_evidence(a)
    assert "RSI(14)" in e and "19 kỳ" in e


def test_evidence_khi_thieu_du_lieu_noi_ro_thieu_bao_nhieu():
    e = trend_evidence(analyze(history=_hist([4000, 4010])))
    assert "chưa đo được" in e and "cần 15" in e


# --- Dữ liệu thật trong repo ------------------------------------------------

def test_du_lieu_that_gio_do_duoc_xu_huong():
    """Trước khi sửa, nhãn luôn là TRUNG_TINH vì đọc file 1 dòng."""
    a = analyze()
    assert a["sessions"] >= 15
    assert a["rsi14"] is not None
    assert trend_label(a) is not None

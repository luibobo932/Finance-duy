"""Đối chiếu kỷ luật giao dịch — bộ đếm cũ vừa bỏ sót vừa buộc tội oan.

`docs/AUDIT_REPORT.md` mục L7 xếp logic cũ là "dễ vỡ nếu đổi cách viết action".
Đo lại trên chính 9 nhãn mà `decision/action_mapper.py` đang sinh ra thì nó
không dễ vỡ — nó đã vỡ sẵn từ lúc bảng nhãn tiếng Việt ra đời.
"""
import pytest

from decision.action_mapper import VIETNAMESE_LABEL, Action
from decision.discipline import (AGAINST, ALIGNED, NO_BASIS, UNKNOWN, classify,
                                 explain, normalize_action)


def _cu(side, rec):
    """Nguyên văn logic string-matching cũ trong scripts/journal.py."""
    r = (rec or "").upper()
    return ((side == "BUY" and "CHƯA MUA" in r) or
            (side == "SELL" and "MUA" in r and "CHƯA" not in r))


# --- Hai lỗi cụ thể của logic cũ -------------------------------------------

def test_ban_sau_KHONG_MUA_THEM_khong_con_bi_buoc_toi_oan():
    """"KHÔNG MUA THÊM" chứa chuỗi con "MUA" nên logic cũ đếm lệnh BÁN là đi
    ngược — trong khi bán chính là làm đúng điều được khuyên."""
    assert _cu("SELL", "KHÔNG MUA THÊM") is True      # sai của logic cũ
    assert classify("SELL", "KHÔNG MUA THÊM") == ALIGNED


def test_mua_khi_he_thong_bao_DUNG_NGOAI_phai_bi_bat():
    """Nhánh BUY cũ dò chuỗi "CHƯA MUA" — chuỗi này không nằm trong bất kỳ nhãn
    quyết định nào, nên mọi lệnh mua sai đều lọt. Mà mua sai mới mất tiền."""
    assert _cu("BUY", "ĐỨNG NGOÀI") is False          # sót của logic cũ
    assert classify("BUY", "ĐỨNG NGOÀI") == AGAINST


def test_logic_cu_khong_bat_duoc_BAT_KY_lenh_mua_sai_nao():
    """Chốt lại mức độ: trên cả 9 nhãn, cột BUY của logic cũ luôn False."""
    assert not any(_cu("BUY", vi) for vi in VIETNAMESE_LABEL.values())
    # Logic mới bắt được đúng những nhãn không cho phép mua.
    bat_duoc = [vi for a, vi in VIETNAMESE_LABEL.items()
                if classify("BUY", vi) == AGAINST]
    assert len(bat_duoc) >= 6


# --- Bảng đối chiếu đầy đủ --------------------------------------------------

@pytest.mark.parametrize("action,side,mong_doi", [
    (Action.BUY_SMALL.value, "BUY", ALIGNED),
    (Action.BUY_SMALL.value, "SELL", AGAINST),
    (Action.HOLD.value, "BUY", AGAINST),
    (Action.HOLD.value, "SELL", AGAINST),
    (Action.TAKE_PARTIAL_PROFIT.value, "SELL", ALIGNED),
    (Action.TAKE_PARTIAL_PROFIT.value, "BUY", AGAINST),
    (Action.DO_NOT_BUY_MORE.value, "BUY", AGAINST),
    (Action.DO_NOT_BUY_MORE.value, "SELL", ALIGNED),
    (Action.WATCH.value, "BUY", AGAINST),
    (Action.STAND_ASIDE.value, "BUY", AGAINST),
    (Action.WAIT_FOR_CONFIRMATION.value, "BUY", AGAINST),
    (Action.DEPOSIT.value, "BUY", AGAINST),
])
def test_bang_doi_chieu(action, side, mong_doi):
    assert classify(side, action) == mong_doi


def test_moi_nhan_tieng_viet_deu_anh_xa_duoc():
    """Nhãn nào bản tin in ra được thì nhật ký phải đối chiếu được — nếu không,
    ghi đúng nguyên văn khuyến nghị vẫn ra UNKNOWN."""
    for vi in VIETNAMESE_LABEL.values():
        assert normalize_action(vi) is not None, vi
        assert classify("BUY", vi) != UNKNOWN


def test_moi_action_enum_deu_anh_xa_duoc():
    for a in Action:
        assert normalize_action(a.value) == a.value


# --- Ba trạng thái, không phải hai ------------------------------------------

def test_CHUA_DU_DU_LIEU_khong_phai_di_nguoc_ma_la_khong_co_can_cu():
    """"Hệ thống không biết" không phải một khuyến nghị để mà đi ngược. Trộn nó
    vào cột đi ngược sẽ làm loãng đúng thứ cần nhìn."""
    for side in ("BUY", "SELL"):
        assert classify(side, "CHƯA ĐỦ DỮ LIỆU ĐỂ RA QUYẾT ĐỊNH") == NO_BASIS
        assert classify(side, Action.NO_DECISION.value) == NO_BASIS


def test_rec_khong_doc_duoc_phai_BAO_chu_khong_duoc_coi_la_thuan():
    """Im lặng cho qua một dòng không đọc được là cách bộ đếm tự khoe thành tích."""
    assert classify("BUY", "mua theo cảm giác") == UNKNOWN
    assert classify("BUY", "") == UNKNOWN
    assert classify("BUY", None) == UNKNOWN


def test_khong_phan_biet_hoa_thuong_va_khoang_trang_thua():
    assert classify("buy", "  mua thăm dò  ") == ALIGNED
    assert classify("BUY", "buy_small") == ALIGNED


def test_explain_luon_neu_ly_do_doc_duoc():
    e = explain("BUY", "ĐỨNG NGOÀI")
    assert "BUY" in e and "ĐỨNG NGOÀI" in e

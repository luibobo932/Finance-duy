"""Bạn có làm ngược lại điều hệ thống khuyên không — đối chiếu bằng ENUM, không
bằng cách dò chữ tiếng Việt.

Lỗi đang sửa (đã ghi trong `docs/AUDIT_REPORT.md` mục L7 là "dễ vỡ", nhưng đo
lại thì nó không dễ vỡ — nó đang SAI SẴN). Nguyên văn logic cũ trong
`scripts/journal.py`:

    (side == "BUY"  and "CHƯA MUA" in rec.upper()) or
    (side == "SELL" and "MUA" in rec.upper() and "CHƯA" not in rec.upper())

Chạy nó trên đúng 9 nhãn mà `decision/action_mapper.py` sinh ra:

    KHÔNG MUA THÊM   + SELL  → bị gắn cờ "đi ngược khuyến nghị"   ← NGƯỢC HẲN
    ĐỨNG NGOÀI       + BUY   → không bị gắn cờ
    CHỜ XÁC NHẬN     + BUY   → không bị gắn cờ
    CHƯA ĐỦ DỮ LIỆU  + BUY   → không bị gắn cờ
    GIỮ              + SELL  → không bị gắn cờ

Hai kết luận, cả hai đều tệ:

1. **Cột BUY không bắt được gì cả.** Nhánh BUY dò chuỗi `"CHƯA MUA"` — chuỗi
   này chỉ xuất hiện trong `PositionPlan.summary()`, KHÔNG nằm trong bất kỳ
   nhãn quyết định nào. Nghĩa là mua khi hệ thống nói ĐỨNG NGOÀI / CHỜ XÁC
   NHẬN / CHƯA ĐỦ DỮ LIỆU đều lọt sạch. Mà mua sai mới là phía mất tiền.
2. **Có một trường hợp bị buộc tội oan.** "KHÔNG MUA THÊM" chứa chuỗi con
   "MUA", nên bán sau khuyến nghị KHÔNG MUA THÊM bị đếm là đi ngược — trong
   khi đó chính là làm đúng.

Một bộ đếm kỷ luật vừa bỏ sót phía nguy hiểm vừa báo động sai phía an toàn thì
tệ hơn không có: nó tạo cảm giác đang được canh.

Ba trạng thái, không phải hai. `CHƯA ĐỦ DỮ LIỆU` không phải một khuyến nghị để
mà đi ngược — nó là lời thú nhận hệ thống không biết. Giao dịch lúc đó không
phải vô kỷ luật, nhưng cũng không có gì chống lưng, và trộn nó vào cột "đi
ngược" sẽ làm loãng đúng thứ cần nhìn.
"""
from __future__ import annotations

from typing import Optional

from .action_mapper import VIETNAMESE_LABEL, Action

AGAINST = "AGAINST"      # đi ngược khuyến nghị
ALIGNED = "ALIGNED"      # thuận theo khuyến nghị
NO_BASIS = "NO_BASIS"    # hệ thống chưa ra được khuyến nghị nào để mà đối chiếu
UNKNOWN = "UNKNOWN"      # không đọc được `rec` — phải báo, không được coi là ALIGNED

# Hành động nào CHO PHÉP mua, hành động nào CHO PHÉP bán. Bảng tường minh thay
# cho suy diễn từ chữ: mọi ô đều đọc được và cãi được.
BUY_OK = {Action.BUY_SMALL.value}
SELL_OK = {
    Action.TAKE_PARTIAL_PROFIT.value,   # khuyên chốt bớt
    Action.DO_NOT_BUY_MORE.value,       # khuyên đừng mua thêm — bán không mâu thuẫn
    Action.DEPOSIT.value,               # khuyên chuyển sang tiền gửi
    Action.WATCH.value,                 # đứng ngoài — thoát vị thế là thuận
    Action.STAND_ASIDE.value,           # bị chặn hẳn — thoát là thuận
    Action.WAIT_FOR_CONFIRMATION.value,  # chờ xác nhận — không mua, bán thì tuỳ
}

# Nhãn tiếng Việt -> action. Xây NGƯỢC từ VIETNAMESE_LABEL để không thể lệch
# khỏi bảng gốc. "ĐỨNG NGOÀI" ứng với cả WATCH lẫn STAND_ASIDE; chọn WATCH vì
# hai cái xử lý giống hệt nhau ở đây (cùng cấm mua, cùng cho bán).
_VI_TO_ACTION: dict[str, str] = {}
for _action, _label in VIETNAMESE_LABEL.items():
    _VI_TO_ACTION.setdefault(_label.upper(), _action)


def normalize_action(rec: Optional[str]) -> Optional[str]:
    """`rec` ghi trong nhật ký -> action chuẩn. None khi không nhận ra.

    Nhận cả ba cách viết vì nhật ký được ghi tay qua nhiều đời: tên enum
    (`BUY_SMALL`), nhãn tiếng Việt (`MUA THĂM DÒ`), và biến thể hoa/thường.
    KHÔNG đoán mò từ chuỗi con — đó chính là cách logic cũ hỏng.
    """
    if not rec or not isinstance(rec, str):
        return None
    key = rec.strip().upper()
    if key in {a.value for a in Action}:
        return key
    return _VI_TO_ACTION.get(key)


def classify(side: str, rec: Optional[str]) -> str:
    """Một lệnh BUY/SELL đứng ở đâu so với khuyến nghị lúc đó."""
    action = normalize_action(rec)
    if action is None:
        return UNKNOWN
    if action == Action.NO_DECISION.value:
        return NO_BASIS
    side = (side or "").upper()
    if side == "BUY":
        return ALIGNED if action in BUY_OK else AGAINST
    if side == "SELL":
        return ALIGNED if action in SELL_OK else AGAINST
    return UNKNOWN


def explain(side: str, rec: Optional[str]) -> str:
    """Câu giải thích cho dòng bị gắn cờ — cờ không kèm lý do thì không sửa
    được hành vi, mà sửa hành vi mới là mục đích của cuốn nhật ký."""
    action = normalize_action(rec)
    label = VIETNAMESE_LABEL.get(action or "", rec or "không rõ")
    verdict = classify(side, rec)
    if verdict == AGAINST:
        return (f"{side} trong khi hệ thống khuyến nghị {label}"
                if side.upper() == "BUY"
                else f"{side} trong khi hệ thống khuyến nghị {label}")
    if verdict == NO_BASIS:
        return f"{side} khi hệ thống báo {label} — giao dịch không có căn cứ từ hệ thống"
    if verdict == UNKNOWN:
        return f"{side} với khuyến nghị ghi là \"{rec}\" — không ánh xạ được về hành động chuẩn"
    return f"{side} thuận theo khuyến nghị {label}"

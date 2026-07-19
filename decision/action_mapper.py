"""9 hành động chuẩn nội bộ (tiếng Anh, dùng trong code) + ánh xạ sang 7 nhãn
tiếng Việt bắt buộc theo yêu cầu chủ dự án. Ánh xạ tường minh, không suy diễn.
"""
from __future__ import annotations

from enum import Enum


class Action(str, Enum):
    HOLD = "HOLD"
    TAKE_PARTIAL_PROFIT = "TAKE_PARTIAL_PROFIT"
    DO_NOT_BUY_MORE = "DO_NOT_BUY_MORE"
    DEPOSIT = "DEPOSIT"
    BUY_SMALL = "BUY_SMALL"
    WATCH = "WATCH"
    WAIT_FOR_CONFIRMATION = "WAIT_FOR_CONFIRMATION"
    STAND_ASIDE = "STAND_ASIDE"
    NO_DECISION = "NO_DECISION"


# Chuỗi bắt buộc khi dữ liệu không đủ để ra quyết định (đúng nguyên văn yêu
# cầu ở phần Data Contract).
INSUFFICIENT_DATA_MESSAGE = "CHƯA ĐỦ DỮ LIỆU ĐỂ RA QUYẾT ĐỊNH"

# Ánh xạ 9 action nội bộ -> 7 nhãn tiếng Việt của chủ dự án. WATCH và
# STAND_ASIDE cùng map ĐỨNG NGOÀI (khác nhau ở ngữ cảnh nội bộ: WATCH = có
# theo dõi tín hiệu, STAND_ASIDE = bị risk officer chặn hẳn) — cả hai đều
# là "không hành động" khi hiển thị cho người dùng.
VIETNAMESE_LABEL: dict[str, str] = {
    Action.HOLD.value: "GIỮ",
    Action.TAKE_PARTIAL_PROFIT.value: "CHỐT BỚT",
    Action.DO_NOT_BUY_MORE.value: "KHÔNG MUA THÊM",
    Action.DEPOSIT.value: "GỬI TIẾT KIỆM",
    Action.BUY_SMALL.value: "MUA THĂM DÒ",
    Action.WATCH.value: "ĐỨNG NGOÀI",
    Action.WAIT_FOR_CONFIRMATION.value: "CHỜ XÁC NHẬN",
    Action.STAND_ASIDE.value: "ĐỨNG NGOÀI",
    Action.NO_DECISION.value: INSUFFICIENT_DATA_MESSAGE,
}


def to_vietnamese(action: str) -> str:
    return VIETNAMESE_LABEL.get(action, action)


def is_valid_action(action: str) -> bool:
    return action in VIETNAMESE_LABEL

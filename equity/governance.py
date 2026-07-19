"""Trạng thái pháp lý/quản trị doanh nghiệp — enum chuẩn + phân loại theo
từ khóa tường minh từ nguồn tin.

Nguyên tắc AN TOÀN (yêu cầu gốc của chủ dự án): KHÔNG được gán INDICTED
("bị khởi tố"/"bị bắt") nếu nguồn tin chỉ nói "đang xác minh" hoặc "bị mời
làm việc". Việc phân loại dựa trên khớp từ khóa tường minh, không suy diễn
ngữ nghĩa — nếu không khớp từ khóa nào, trả NONE thay vì đoán.
"""
from __future__ import annotations

from enum import Enum


class GovernanceStatus(str, Enum):
    NONE = "NONE"
    RUMOR = "RUMOR"
    UNDER_VERIFICATION = "UNDER_VERIFICATION"
    SUMMONED_FOR_QUESTIONING = "SUMMONED_FOR_QUESTIONING"
    INVESTIGATION_OPENED = "INVESTIGATION_OPENED"
    INDICTED = "INDICTED"
    CONVICTED = "CONVICTED"


# Trạng thái CHẶN đề xuất mua (theo config/decision_rules.yaml, Phase 7 dùng)
BLOCKING_STATES = {GovernanceStatus.INDICTED.value, GovernanceStatus.CONVICTED.value,
                    GovernanceStatus.INVESTIGATION_OPENED.value}
# Trạng thái chỉ CẢNH BÁO/theo dõi, chưa đủ căn cứ chặn
WATCH_STATES = {GovernanceStatus.RUMOR.value, GovernanceStatus.UNDER_VERIFICATION.value,
                 GovernanceStatus.SUMMONED_FOR_QUESTIONING.value}

# Thứ tự PHẢI theo đúng mức độ nghiêm trọng GIẢM DẦN — khi 1 đoạn tin khớp
# nhiều mức (VD "trước có tin đồn, nay đã bị khởi tố"), hệ thống chọn mức
# nghiêm trọng nhất, không chọn mức xuất hiện trước trong câu.
_KEYWORD_RULES: list[tuple[str, list[str]]] = [
    (GovernanceStatus.CONVICTED.value,
     ["tuyên án", "kết án", "bị tòa tuyên", "phạt tù", "án tù", "y án"]),
    (GovernanceStatus.INDICTED.value,
     # CHÚ Ý: "khởi tố bị can" (đích danh 1 người) khác "khởi tố vụ án" (mới mở vụ
     # án, chưa chỉ đích danh) — không dùng "khởi tố" trần trụi ở mức INDICTED để
     # tránh nhầm 2 khái niệm pháp lý khác nhau này.
     ["khởi tố bị can", "bắt tạm giam", "bắt giam", "truy tố"]),
    (GovernanceStatus.INVESTIGATION_OPENED.value,
     ["mở cuộc điều tra", "khởi tố vụ án", "khám xét", "vào cuộc điều tra", "khởi tố"]),
    (GovernanceStatus.SUMMONED_FOR_QUESTIONING.value,
     ["mời làm việc", "triệu tập", "làm việc với cơ quan công an", "làm việc với cơ quan điều tra"]),
    (GovernanceStatus.UNDER_VERIFICATION.value,
     ["đang xác minh", "xác minh thông tin", "chưa xác nhận", "đang làm rõ", "chưa có kết luận"]),
    (GovernanceStatus.RUMOR.value,
     ["tin đồn", "mạng xã hội lan truyền", "chưa có xác nhận chính thức", "tin chưa kiểm chứng"]),
]

_ORDER = [rule[0] for rule in _KEYWORD_RULES]


def classify_governance_news(text: str) -> str:
    """Phân loại 1 đoạn tin tức thành GovernanceStatus theo từ khóa tường minh.

    Không khớp từ khóa nào -> NONE (không tự suy diễn mức độ nghiêm trọng).
    Khớp nhiều mức -> chọn mức NGHIÊM TRỌNG NHẤT trong số các mức khớp.
    """
    t = (text or "").lower()
    matched = [status for status, keywords in _KEYWORD_RULES if any(kw in t for kw in keywords)]
    if not matched:
        return GovernanceStatus.NONE.value
    matched.sort(key=lambda s: _ORDER.index(s))
    return matched[0]


def is_blocking(status: str) -> bool:
    return status in BLOCKING_STATES


def is_watch_only(status: str) -> bool:
    return status in WATCH_STATES

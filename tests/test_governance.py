"""Test cho equity/governance.py — KHÔNG được gán INDICTED khi nguồn chỉ
nói 'đang xác minh'/'mời làm việc' (yêu cầu gốc của chủ dự án, Phase 6)."""
from equity.governance import GovernanceStatus, classify_governance_news, is_blocking, is_watch_only


def test_summoned_for_questioning_not_indicted():
    status = classify_governance_news("Chủ tịch X đang bị mời làm việc để xác minh thông tin liên quan")
    assert status != GovernanceStatus.INDICTED.value
    assert status == GovernanceStatus.SUMMONED_FOR_QUESTIONING.value
    assert is_blocking(status) is False


def test_under_verification_not_indicted():
    status = classify_governance_news("Cơ quan chức năng đang xác minh thông tin, chưa có kết luận")
    assert status != GovernanceStatus.INDICTED.value
    assert is_watch_only(status) is True


def test_indicted_when_clearly_stated():
    status = classify_governance_news("Lãnh đạo Y đã bị khởi tố, bắt tạm giam để điều tra")
    assert status == GovernanceStatus.INDICTED.value
    assert is_blocking(status) is True


def test_convicted_when_court_ruling():
    status = classify_governance_news("Tòa tuyên án 5 năm tù đối với ông A")
    assert status == GovernanceStatus.CONVICTED.value
    assert is_blocking(status) is True


def test_rumor_stays_rumor_without_confirmation():
    status = classify_governance_news("Có tin đồn trên mạng xã hội, chưa có xác nhận chính thức")
    assert status == GovernanceStatus.RUMOR.value
    assert is_blocking(status) is False


def test_escalation_picks_most_severe_match():
    status = classify_governance_news("Trước đó có tin đồn, nhưng nay xác nhận đã bị khởi tố bị can")
    assert status == GovernanceStatus.INDICTED.value


def test_unrelated_news_returns_none():
    status = classify_governance_news("Kết quả kinh doanh quý 2 của công ty tăng trưởng tốt")
    assert status == GovernanceStatus.NONE.value
    assert is_blocking(status) is False
    assert is_watch_only(status) is False


def test_empty_text_returns_none():
    assert classify_governance_news("") == GovernanceStatus.NONE.value
    assert classify_governance_news(None) == GovernanceStatus.NONE.value


def test_investigation_opened_is_blocking():
    status = classify_governance_news("Cơ quan điều tra đã khởi tố vụ án liên quan đến công ty")
    assert status == GovernanceStatus.INVESTIGATION_OPENED.value
    assert is_blocking(status) is True


def test_case_level_prosecution_not_conflated_with_person_level_indictment():
    # "khởi tố vụ án" (mở vụ án, CHƯA chỉ đích danh ai) phải KHÁC "khởi tố bị can"
    # (khởi tố đích danh 1 người) — không được để mức độ nghiêm trọng bị nhầm lẫn.
    case_level = classify_governance_news("Khởi tố vụ án hình sự xảy ra tại công ty ABC")
    person_level = classify_governance_news("Khởi tố bị can, bắt tạm giam ông Nguyễn Văn A")
    assert case_level == GovernanceStatus.INVESTIGATION_OPENED.value
    assert person_level == GovernanceStatus.INDICTED.value
    assert case_level != person_level

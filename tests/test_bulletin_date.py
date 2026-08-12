"""Test cho run_morning.bulletin_date() — sửa bug tiêu đề bản tin dùng nhầm
config/portfolio.yaml `updated` (ngày chủ dự án tự cập nhật số lượng tài sản,
không đổi hằng ngày) thay vì NGÀY THẬT của bản tin đang chạy."""
from datetime import date

from run_morning import bulletin_date


def test_uses_latest_snapshot_date_when_history_present():
    hist = [{"date": "2026-07-20"}, {"date": "2026-07-22"}]
    assert bulletin_date(hist, today=date(2026, 7, 26)) == "2026-07-22"


def test_falls_back_to_today_when_history_empty():
    assert bulletin_date([], today=date(2026, 7, 26)) == "2026-07-26"


def test_falls_back_to_today_when_snapshot_missing_date_field():
    hist = [{"vnindex": {"close": 1700}}]
    assert bulletin_date(hist, today=date(2026, 7, 26)) == "2026-07-26"

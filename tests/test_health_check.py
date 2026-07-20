"""Test cho scripts/health_check.py (Phase 10) — freshness dữ liệu + an ninh.

Toàn bộ hàm nhận `now`/đường dẫn tiêm từ ngoài — test không phụ thuộc đồng hồ
thật hay trạng thái repo thật.
"""
from datetime import date
from pathlib import Path

from health_check import (
    check_data_freshness,
    check_env_hygiene,
    find_secret_leaks,
    latest_date_in_csv,
    latest_date_in_jsonl,
    overall_status,
)


def test_latest_date_in_jsonl(tmp_path):
    p = tmp_path / "history.jsonl"
    p.write_text('{"date": "2026-07-18"}\n{"date": "2026-07-20"}\n', encoding="utf-8")
    assert latest_date_in_jsonl(p) == "2026-07-20"


def test_latest_date_in_jsonl_missing_file_returns_none(tmp_path):
    assert latest_date_in_jsonl(tmp_path / "nope.jsonl") is None


def test_latest_date_in_csv(tmp_path):
    p = tmp_path / "VCB.csv"
    p.write_text("date,close\n2026-07-16,1\n2026-07-17,2\n", encoding="utf-8")
    assert latest_date_in_csv(p) == "2026-07-17"


def test_freshness_ok_when_recent(tmp_path):
    p = tmp_path / "history.jsonl"
    p.write_text('{"date": "2026-07-20"}\n', encoding="utf-8")
    r = check_data_freshness("history", p, max_age_days=1, today=date(2026, 7, 20), kind="jsonl")
    assert r["status"] == "OK"


def test_freshness_warn_when_stale(tmp_path):
    p = tmp_path / "history.jsonl"
    p.write_text('{"date": "2026-07-10"}\n', encoding="utf-8")
    r = check_data_freshness("history", p, max_age_days=2, today=date(2026, 7, 20), kind="jsonl")
    assert r["status"] == "WARN"
    assert "10 ngày" in r["detail"]


def test_freshness_fail_when_missing(tmp_path):
    r = check_data_freshness("history", tmp_path / "nope.jsonl", max_age_days=2,
                             today=date(2026, 7, 20), kind="jsonl")
    assert r["status"] == "FAIL"


def test_env_hygiene_fails_when_env_tracked():
    r = check_env_hygiene(tracked_files=[".env", "README.md"], gitignore_text=".env\n")
    assert r["status"] == "FAIL"


def test_env_hygiene_fails_when_env_not_in_gitignore():
    r = check_env_hygiene(tracked_files=["README.md"], gitignore_text="__pycache__/\n")
    assert r["status"] == "FAIL"


def test_env_hygiene_ok():
    r = check_env_hygiene(tracked_files=["README.md"], gitignore_text=".env\nlogs/*.jsonl\n")
    assert r["status"] == "OK"


def test_find_secret_leaks_detects_telegram_token():
    # Token GIẢ đúng định dạng BotFather — tuyệt đối không dùng token thật ở đây
    files = {"docs/x.md": "token la 1234567890:FAKEtoken_abcdefghijklmnopqrstuvwx day"}
    leaks = find_secret_leaks(files)
    assert leaks == ["docs/x.md"]


def test_find_secret_leaks_ignores_normal_text():
    files = {"README.md": "python3 notifications/telegram.py whoami — token trong .env"}
    assert find_secret_leaks(files) == []


def test_overall_status_worst_wins():
    assert overall_status([{"status": "OK"}, {"status": "WARN"}]) == "WARN"
    assert overall_status([{"status": "WARN"}, {"status": "FAIL"}]) == "FAIL"
    assert overall_status([{"status": "OK"}]) == "OK"

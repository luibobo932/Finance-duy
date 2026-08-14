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
    """Trễ vừa phải (trong ngưỡng leo thang) vẫn chỉ là WARN."""
    p = tmp_path / "history.jsonl"
    p.write_text('{"date": "2026-07-16"}\n', encoding="utf-8")
    r = check_data_freshness("history", p, max_age_days=2, today=date(2026, 7, 20), kind="jsonl")
    assert r["status"] == "WARN"
    assert "4 ngày" in r["detail"]


# --- Leo thang WARN -> FAIL (thêm 13/8) ------------------------------------
# Trước bản này, WARN không bao giờ leo thang dù kéo dài bao lâu, nên automation
# kẹt 7 ngày (20–26/7) vẫn "thành công" mọi lần chạy và không ai biết.

def test_tre_qua_lau_thi_LEO_THANG_thanh_FAIL(tmp_path):
    from health_check import STALE_ESCALATE_FACTOR

    p = tmp_path / "history.jsonl"
    p.write_text('{"date": "2026-07-10"}\n', encoding="utf-8")   # trễ 10 ngày
    r = check_data_freshness("history", p, max_age_days=2, today=date(2026, 7, 20), kind="jsonl")
    assert r["status"] == "FAIL", f"10 ngày > {2 * STALE_ESCALATE_FACTOR} ngày phải là FAIL"
    assert "automation" in r["detail"].lower()


def test_WARN_noi_ro_moc_se_thanh_FAIL(tmp_path):
    """Cảnh báo phải nói khi nào nó trở thành lỗi — để biết còn bao lâu."""
    p = tmp_path / "history.jsonl"
    p.write_text('{"date": "2026-07-16"}\n', encoding="utf-8")
    r = check_data_freshness("history", p, max_age_days=2, today=date(2026, 7, 20), kind="jsonl")
    assert "thành FAIL nếu quá 6 ngày" in r["detail"]


def test_nguon_NHAP_TAY_khong_leo_thang_thanh_FAIL(tmp_path):
    """Leo thang nghĩa là "automation hỏng". Nguồn không có automation mà FAIL
    mỗi ngày sẽ tái tạo đúng bẫy "cảnh báo luôn bật", làm chìm lỗi thật."""
    p = tmp_path / "deposit_rates.jsonl"
    p.write_text('{"updated_at": "2026-07-01"}\n', encoding="utf-8")  # trễ 50 ngày
    r = check_data_freshness("Lãi suất", p, max_age_days=7, today=date(2026, 8, 20),
                             kind="jsonl_updated_at", automated=False)
    assert r["status"] == "WARN"
    assert "NHẬP TAY" in r["detail"]


def test_nguon_tu_dong_cung_muc_tre_do_thi_FAIL(tmp_path):
    """Cùng độ trễ, khác kết luận — vì ý nghĩa của độ trễ khác nhau."""
    p = tmp_path / "history.jsonl"
    p.write_text('{"date": "2026-07-01"}\n', encoding="utf-8")
    r = check_data_freshness("Snapshot", p, max_age_days=7, today=date(2026, 8, 20),
                             kind="jsonl", automated=True)
    assert r["status"] == "FAIL"


def test_moi_muc_tieu_deu_khai_bao_ro_co_automation_hay_khong():
    from health_check import FRESHNESS_TARGETS

    for target in FRESHNESS_TARGETS:
        assert len(target) == 5, f"thiếu cờ automated: {target[0]}"
        assert isinstance(target[4], bool)


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
    # Token GIẢ đúng định dạng BotFather, GHÉP CHUỖI lúc chạy — để chính file
    # test này không khớp pattern khi health_check quét file nguồn được track
    fake_token = "1234567890" + ":" + "FAKEtoken_abcdefghijklmnopqrstuvwx"
    files = {"docs/x.md": f"token la {fake_token} day"}
    leaks = find_secret_leaks(files)
    assert leaks == ["docs/x.md"]


def test_find_secret_leaks_ignores_normal_text():
    files = {"README.md": "python3 notifications/telegram.py whoami — token trong .env"}
    assert find_secret_leaks(files) == []


def test_overall_status_worst_wins():
    assert overall_status([{"status": "OK"}, {"status": "WARN"}]) == "WARN"
    assert overall_status([{"status": "WARN"}, {"status": "FAIL"}]) == "FAIL"
    assert overall_status([{"status": "OK"}]) == "OK"


# --- Chống spam cảnh báo health check (thêm 13/8) --------------------------
# Gửi Telegram mỗi lần chạy khi vẫn FAIL sẽ tái tạo bẫy "cảnh báo luôn bật":
# người đọc quen tay bỏ qua, rồi lỗi thật cũng bị bỏ qua theo.

def test_khong_gui_khi_khong_FAIL():
    from health_check import should_alert

    for st in ("OK", "WARN"):
        send, _ = should_alert(st, {}, date(2026, 8, 14))
        assert send is False


def test_gui_ngay_khi_VUA_chuyen_sang_FAIL():
    from health_check import should_alert

    send, ly_do = should_alert("FAIL", {"last_status": "OK"}, date(2026, 8, 14))
    assert send is True and "vừa chuyển" in ly_do


def test_KHONG_gui_lai_ngay_hom_sau_neu_van_FAIL():
    from health_check import should_alert

    state = {"last_status": "FAIL", "last_alert_date": "2026-08-13"}
    send, ly_do = should_alert("FAIL", state, date(2026, 8, 14))
    assert send is False and "chưa tới hạn" in ly_do


def test_nhac_lai_sau_du_so_ngay():
    from health_check import REALERT_AFTER_DAYS, should_alert

    state = {"last_status": "FAIL", "last_alert_date": "2026-08-01"}
    send, ly_do = should_alert("FAIL", state, date(2026, 8, 1 + REALERT_AFTER_DAYS))
    assert send is True and "vẫn FAIL" in ly_do


def test_FAIL_lai_sau_khi_da_hoi_phuc_thi_gui_lai():
    """FAIL -> OK -> FAIL là sự cố MỚI, phải báo lại dù mới nhắc gần đây."""
    from health_check import should_alert

    state = {"last_status": "OK", "last_alert_date": "2026-08-13"}
    send, _ = should_alert("FAIL", state, date(2026, 8, 14))
    assert send is True


def test_moc_gui_truoc_hong_thi_van_gui_khong_im_lang():
    from health_check import should_alert

    state = {"last_status": "FAIL", "last_alert_date": "hỏng"}
    send, ly_do = should_alert("FAIL", state, date(2026, 8, 14))
    assert send is True and "không đọc được" in ly_do

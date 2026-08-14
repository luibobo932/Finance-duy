#!/usr/bin/env python3
"""Health check (Phase 10) — kiểm tra sức khỏe dữ liệu + vệ sinh an ninh.

Kiểm tra:
  1. Freshness dữ liệu: history.jsonl, data/eod/*.csv, lãi suất chuẩn hóa,
     lịch sử hiệu chuẩn vàng — cũ quá ngưỡng thì WARN, thiếu hẳn thì FAIL.
  2. An ninh: .env không bị git track, .env có trong .gitignore, không có
     token Telegram lọt vào file được track.

Exit code: 0 nếu OK/WARN, 1 nếu có FAIL — dùng được trong automation.

Cách dùng:
  python3 scripts/health_check.py
  python3 scripts/health_check.py --json
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Token bot Telegram: "<số 8-12 chữ số>:<35 ký tự base64-ish>" — đủ đặc thù để
# không bắt nhầm văn bản thường.
TELEGRAM_TOKEN_RE = re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b")

# Trễ quá ngưỡng bao nhiêu LẦN thì WARN leo thang thành FAIL. Chọn 3 vì ngưỡng
# đã nới cho cuối tuần/nghỉ lễ: trễ gấp 3 lần mức đó thì không còn giải thích
# được bằng lịch nghỉ, mà là automation hỏng.
STALE_ESCALATE_FACTOR = 3

# (tên, đường dẫn, tuổi tối đa ngày, loại, CÓ nguồn tự động?)
#
# Cờ cuối cùng quan trọng: leo thang lên FAIL có nghĩa "automation đang hỏng".
# Với nguồn KHÔNG có automation (lãi suất phải nhập tay, hiệu chuẩn vàng cần ảnh
# bảng giá), dữ liệu cũ không mang nghĩa đó — nó chỉ có nghĩa con người chưa cập
# nhật. Cho những nguồn đó FAIL mỗi ngày sẽ tái tạo đúng cái bẫy "cảnh báo luôn
# bật" vừa sửa ở analytics/alert_health.py, và làm automation hỏng thật bị chìm.
FRESHNESS_TARGETS: list[tuple[str, str, int, str, bool]] = [
    ("Snapshot thị trường (history.jsonl)", "data/history.jsonl", 2, "jsonl", True),
    ("EOD VCB", "data/eod/VCB.csv", 4, "csv", True),
    ("EOD CTD", "data/eod/CTD.csv", 4, "csv", True),
    ("Lãi suất chuẩn hóa", "data/normalized/deposit_rates.jsonl", 7, "jsonl_updated_at", False),
    ("Hiệu chuẩn giá vàng tiệm", "data/normalized/xuan_trieu_gold_history.csv", 30, "csv", False),
]


def latest_date_in_jsonl(path: Path, field: str = "date") -> Optional[str]:
    if not path.exists():
        return None
    latest: Optional[str] = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line).get(field)
        except json.JSONDecodeError:
            continue
        if isinstance(d, str) and (latest is None or d > latest):
            latest = d
    return latest


def latest_date_in_csv(path: Path, column: str = "date") -> Optional[str]:
    if not path.exists():
        return None
    latest: Optional[str] = None
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d = (row.get(column) or "").strip()
            if d and (latest is None or d > latest):
                latest = d
    return latest


def check_data_freshness(name: str, path: Path, max_age_days: int, today: date, kind: str,
                          automated: bool = True) -> dict:
    if kind == "csv":
        latest = latest_date_in_csv(path)
    elif kind == "jsonl_updated_at":
        latest = latest_date_in_jsonl(path, field="updated_at")
    else:
        latest = latest_date_in_jsonl(path)
    if latest is None:
        return {"name": name, "status": "FAIL", "detail": f"Không có dữ liệu ({path.name})"}
    try:
        age = (today - datetime.strptime(latest, "%Y-%m-%d").date()).days
    except ValueError:
        return {"name": name, "status": "FAIL", "detail": f"Ngày không hợp lệ: {latest!r}"}
    if automated and age > max_age_days * STALE_ESCALATE_FACTOR:
        # Trễ kéo dài KHÔNG còn là cảnh báo — nó là hỏng. Trước đây WARN không
        # bao giờ leo thang nên automation kẹt 7 ngày (20–26/7) vẫn "thành công"
        # ở mọi lần chạy và không ai biết. Một cảnh báo lặp mãi ở mức nhẹ chính
        # là cách sự cố dài ngày lọt lưới.
        return {"name": name, "status": "FAIL",
                "detail": (f"Dữ liệu mới nhất {latest} — đã {age} ngày, "
                           f"gấp >{STALE_ESCALATE_FACTOR}× ngưỡng {max_age_days} ngày. "
                           "Nhiều khả năng automation đã ngừng chạy hoặc đang kẹt.")}
    if age > max_age_days:
        if automated:
            them = f", thành FAIL nếu quá {max_age_days * STALE_ESCALATE_FACTOR} ngày"
        else:
            them = " — nguồn NHẬP TAY, không có automation nên không leo thang thành FAIL"
        return {"name": name, "status": "WARN",
                "detail": f"Dữ liệu mới nhất {latest} — đã {age} ngày (ngưỡng {max_age_days}{them})"}
    return {"name": name, "status": "OK", "detail": f"Mới nhất {latest} ({age} ngày tuổi)"}


def check_env_hygiene(tracked_files: list[str], gitignore_text: str) -> dict:
    name = "Vệ sinh .env"
    if ".env" in tracked_files:
        return {"name": name, "status": "FAIL",
                "detail": ".env ĐANG BỊ GIT TRACK — chứa token thật, phải gỡ ngay (git rm --cached .env)"}
    ignored = any(line.strip() == ".env" for line in gitignore_text.splitlines())
    if not ignored:
        return {"name": name, "status": "FAIL", "detail": ".env chưa có trong .gitignore"}
    return {"name": name, "status": "OK", "detail": ".env không bị track, đã có trong .gitignore"}


def find_secret_leaks(files: dict[str, str]) -> list[str]:
    """Quét nội dung các file được track, trả danh sách file chứa token."""
    return [path for path, text in files.items() if TELEGRAM_TOKEN_RE.search(text)]


def overall_status(results: list[dict]) -> str:
    statuses = {r["status"] for r in results}
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    return "OK"


def _git_tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    return out.stdout.splitlines() if out.returncode == 0 else []


def run_all_checks(today: Optional[date] = None) -> list[dict]:
    today = today or date.today()
    results = [check_data_freshness(name, ROOT / rel, max_age, today, kind, automated)
               for name, rel, max_age, kind, automated in FRESHNESS_TARGETS]

    tracked = _git_tracked_files()
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8") if (ROOT / ".gitignore").exists() else ""
    results.append(check_env_hygiene(tracked, gitignore))

    # Quét token lọt vào file text được track (bỏ file nhị phân/không đọc được)
    texts: dict[str, str] = {}
    for rel in tracked:
        p = ROOT / rel
        try:
            texts[rel] = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
    leaks = find_secret_leaks(texts)
    results.append({
        "name": "Quét secret trong file được track",
        "status": "FAIL" if leaks else "OK",
        "detail": f"Token lộ trong: {', '.join(leaks)}" if leaks else f"Đã quét {len(texts)} file, sạch",
    })
    return results


ICON = {"OK": "✅", "WARN": "⚠️", "FAIL": "❌"}

HEALTH_STATE = ROOT / "data" / "health_state.json"
# Vẫn FAIL kéo dài thì nhắc lại sau bấy nhiêu ngày — KHÔNG nhắc mỗi lần chạy.
# Gửi hàng ngày sẽ tái tạo đúng bẫy "cảnh báo luôn bật": người đọc quen tay bỏ
# qua, rồi lỗi thật cũng bị bỏ qua theo.
REALERT_AFTER_DAYS = 3


def should_alert(status: str, state: dict, today: date) -> tuple[bool, str]:
    """(có gửi không, lý do). Gửi khi VỪA chuyển sang FAIL, hoặc đã nhắc lâu rồi."""
    if status != "FAIL":
        return False, "không FAIL"
    last_status = state.get("last_status")
    last_alert = state.get("last_alert_date")
    if last_status != "FAIL":
        return True, "vừa chuyển sang FAIL"
    if not last_alert:
        return True, "chưa từng gửi cảnh báo cho lần FAIL này"
    try:
        days = (today - datetime.strptime(last_alert, "%Y-%m-%d").date()).days
    except ValueError:
        return True, "mốc gửi trước không đọc được"
    if days >= REALERT_AFTER_DAYS:
        return True, f"vẫn FAIL sau {days} ngày kể từ lần nhắc trước"
    return False, f"đã nhắc {days} ngày trước, chưa tới hạn nhắc lại"


def _load_health_state() -> dict:
    if not HEALTH_STATE.exists():
        return {}
    try:
        return json.loads(HEALTH_STATE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_health_state(state: dict) -> None:
    HEALTH_STATE.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")


def _send_alert(results: list[dict], status: str) -> None:
    """Gửi cảnh báo sức khoẻ qua Telegram. Thất bại chỉ log, không làm sập."""
    from common import get_logger

    logger = get_logger("health_check")
    bad = [r for r in results if r["status"] == "FAIL"]
    lines = ["🚑 <b>HEALTH CHECK: FAIL</b>", ""]
    lines += [f"❌ {r['name']}: {r['detail']}" for r in bad]
    lines.append("")
    lines.append("Bản tin tự động có thể đang KHÔNG chạy. Kiểm tra "
                 "logs/daily_task.log trên máy chạy task.")
    try:
        from common.env import get_env
        from notifications.telegram import send_message

        token, chat_id = get_env("TELEGRAM_BOT_TOKEN"), get_env("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            logger.info("Bỏ qua gửi cảnh báo health check: chưa cấu hình Telegram")
            return
        send_message(token, chat_id, "\n".join(lines), parse_mode="HTML")
        logger.info("Đã gửi cảnh báo health check qua Telegram")
    except Exception as exc:  # noqa: BLE001 — kênh phụ trợ, không được làm sập
        logger.warning(f"Không gửi được cảnh báo health check: {exc}")


def main() -> None:
    as_json = "--json" in sys.argv[1:]
    results = run_all_checks()
    status = overall_status(results)

    if "--alert" in sys.argv[1:]:
        today = date.today()
        state = _load_health_state()
        send, reason = should_alert(status, state, today)
        if send:
            _send_alert(results, status)
            state["last_alert_date"] = today.isoformat()
        state["last_status"] = status
        state["last_check_date"] = today.isoformat()
        _save_health_state(state)
        if not as_json:
            print(f"[alert] {'ĐÃ GỬI' if send else 'bỏ qua'} — {reason}")
    if as_json:
        print(json.dumps({"status": status, "checks": results}, ensure_ascii=False))
    else:
        print("=== HEALTH CHECK ===\n")
        for r in results:
            print(f"{ICON[r['status']]} {r['name']}: {r['detail']}")
        print(f"\nTổng thể: {ICON[status]} {status}")
    if status == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()

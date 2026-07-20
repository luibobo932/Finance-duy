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

# (tên, đường dẫn, tuổi tối đa ngày, loại) — ngưỡng nới cho cuối tuần/nghỉ lễ.
FRESHNESS_TARGETS: list[tuple[str, str, int, str]] = [
    ("Snapshot thị trường (history.jsonl)", "data/history.jsonl", 2, "jsonl"),
    ("EOD VCB", "data/eod/VCB.csv", 4, "csv"),
    ("EOD CTD", "data/eod/CTD.csv", 4, "csv"),
    ("Lãi suất chuẩn hóa", "data/normalized/deposit_rates.jsonl", 7, "jsonl_updated_at"),
    ("Hiệu chuẩn giá vàng tiệm", "data/normalized/xuan_trieu_gold_history.csv", 30, "csv"),
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


def check_data_freshness(name: str, path: Path, max_age_days: int, today: date, kind: str) -> dict:
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
    if age > max_age_days:
        return {"name": name, "status": "WARN",
                "detail": f"Dữ liệu mới nhất {latest} — đã {age} ngày (ngưỡng {max_age_days})"}
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
    results = [check_data_freshness(name, ROOT / rel, max_age, today, kind)
               for name, rel, max_age, kind in FRESHNESS_TARGETS]

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


def main() -> None:
    as_json = "--json" in sys.argv[1:]
    results = run_all_checks()
    status = overall_status(results)
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

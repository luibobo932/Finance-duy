#!/usr/bin/env python3
"""Luồng an toàn: tạo ứng viên, rà soát rồi mới đưa snapshot vào lịch sử."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from .finance_data import DataValidationError, load_history, safe_print, validate_snapshot
except ImportError:
    from finance_data import DataValidationError, load_history, safe_print, validate_snapshot

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CANDIDATES = ROOT / "data" / "candidates"
DEFAULT_HISTORY = ROOT / "data" / "history.jsonl"


def snapshot_digest(snapshot):
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataValidationError(f"{Path(path).name}: JSON lỗi ({exc.msg})") from None


def write_json_atomic(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def create_candidate(snapshot, output_dir=DEFAULT_CANDIDATES, now=None):
    snapshot = validate_snapshot(snapshot)
    created_at = (now or datetime.now(timezone.utc)).isoformat()
    candidate = {
        "pipeline_version": 1,
        "status": "pending_review",
        "created_at": created_at,
        "snapshot_sha256": snapshot_digest(snapshot),
        "snapshot": snapshot,
    }
    filename = f"{snapshot['date']}-{snapshot['ky']}.candidate.json"
    path = Path(output_dir) / filename
    if path.exists():
        raise DataValidationError(f"đã có ứng viên {filename}; không ghi đè")
    write_json_atomic(path, candidate)
    return path


def review_candidate(path, reviewer, note="", now=None):
    candidate = read_json(path)
    if candidate.get("pipeline_version") != 1 or candidate.get("status") != "pending_review":
        raise DataValidationError("ứng viên không ở trạng thái pending_review")
    snapshot = validate_snapshot(candidate.get("snapshot"), location="candidate.snapshot")
    if candidate.get("snapshot_sha256") != snapshot_digest(snapshot):
        raise DataValidationError("checksum ứng viên không khớp; dữ liệu có thể đã bị sửa")
    if not reviewer.strip():
        raise DataValidationError("reviewer không được để trống")
    candidate["status"] = "reviewed"
    candidate["review"] = {
        "reviewer": reviewer.strip(),
        "reviewed_at": (now or datetime.now(timezone.utc)).isoformat(),
        "note": note.strip(),
    }
    write_json_atomic(path, candidate)
    return candidate


def promote_candidate(path, history_path=DEFAULT_HISTORY):
    candidate = read_json(path)
    if candidate.get("status") != "reviewed" or not isinstance(candidate.get("review"), dict):
        raise DataValidationError("ứng viên chưa được rà soát; không thể promote")
    snapshot = validate_snapshot(candidate.get("snapshot"), location="candidate.snapshot")
    if candidate.get("snapshot_sha256") != snapshot_digest(snapshot):
        raise DataValidationError("checksum ứng viên không khớp; từ chối promote")
    history = load_history(history_path)
    key = (snapshot["date"], snapshot["ky"])
    if any((item["date"], item["ky"]) == key for item in history):
        raise DataValidationError(f"lịch sử đã có snapshot {key[0]} kỳ {key[1]}")
    if history:
        last = history[-1]
        order = {"sang": 0, "chieu": 1}
        if (snapshot["date"], order[snapshot["ky"]]) <= (last["date"], order[last["ky"]]):
            raise DataValidationError("snapshot promote phải mới hơn bản ghi cuối lịch sử")
    history_path = Path(history_path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
    candidate["status"] = "promoted"
    candidate["promoted_at"] = datetime.now(timezone.utc).isoformat()
    write_json_atomic(path, candidate)
    return snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    stage = sub.add_parser("stage", help="Tạo ứng viên từ file snapshot JSON")
    stage.add_argument("snapshot", type=Path)
    stage.add_argument("--output-dir", type=Path, default=DEFAULT_CANDIDATES)
    review = sub.add_parser("review", help="Rà soát và ký nhận ứng viên")
    review.add_argument("candidate", type=Path)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--note", default="")
    promote = sub.add_parser("promote", help="Đưa ứng viên đã duyệt vào lịch sử")
    promote.add_argument("candidate", type=Path)
    promote.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    args = parser.parse_args(argv)
    try:
        if args.command == "stage":
            path = create_candidate(read_json(args.snapshot), args.output_dir)
            safe_print(f"Đã tạo ứng viên: {path}")
        elif args.command == "review":
            review_candidate(args.candidate, args.reviewer, args.note)
            safe_print(f"Đã rà soát: {args.candidate}")
        else:
            snapshot = promote_candidate(args.candidate, args.history)
            safe_print(f"Đã promote snapshot {snapshot['date']} kỳ {snapshot['ky']}")
    except (DataValidationError, OSError) as exc:
        safe_print(f"LỖI: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

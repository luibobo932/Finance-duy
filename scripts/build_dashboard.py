#!/usr/bin/env python3
"""Tạo gói dữ liệu tĩnh để dashboard đọc trên GitHub Pages."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .finance_data import DataValidationError, load_history
    from .decision_engine import build_decision_report, load_profile, source_fields
    from .scorecard import build_scorecard, load_journal
except ImportError:  # Chạy trực tiếp: python scripts/build_dashboard.py
    from finance_data import DataValidationError, load_history
    from decision_engine import build_decision_report, load_profile, source_fields
    from scorecard import build_scorecard, load_journal

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HISTORY = ROOT / "data" / "history.jsonl"
DEFAULT_PORTFOLIO = ROOT / "data" / "portfolio.local.json"
DEFAULT_OUTPUT = ROOT / "dashboard" / "data.json"
DEFAULT_PROFILE = ROOT / "config" / "decision_profile.json"
DEFAULT_JOURNAL = ROOT / "data" / "decision_journal.jsonl"


def build_payload(history_path=DEFAULT_HISTORY, portfolio_path=DEFAULT_PORTFOLIO, profile_path=DEFAULT_PROFILE):
    history = load_history(history_path)
    if not history:
        raise DataValidationError("history.jsonl chưa có bản ghi")
    # Giữ tham số để tương thích lệnh cũ nhưng tuyệt đối không đọc dữ liệu danh mục private.
    profile = load_profile(profile_path)
    return {
        "schema_version": 2,
        "latest": history[-1],
        "previous": history[-2] if len(history) > 1 else None,
        "history": history,
        "history_provenance": [
            {"date": item["date"], "ky": item["ky"], "verified_fields": sorted(source_fields(item))}
            for item in history
        ],
        # Tuyệt đối không nhúng giá vốn/số lượng cá nhân vào dashboard công khai.
        "decision": build_decision_report(history, {}, profile),
        "scorecard": build_scorecard(load_journal(DEFAULT_JOURNAL), history),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--portfolio", type=Path, default=DEFAULT_PORTFOLIO, help="Đã ngừng dùng; dashboard công khai không đọc danh mục")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    args = parser.parse_args(argv)

    try:
        payload = build_payload(args.history, args.portfolio, args.profile)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (DataValidationError, OSError) as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1

    print(f"Đã tạo {args.output} từ {len(payload['history'])} bản ghi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

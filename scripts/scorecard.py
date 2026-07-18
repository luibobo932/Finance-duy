#!/usr/bin/env python3
"""Ghi nhật ký và kiểm chứng các quyết định sau 5 phiên quan sát.

Cách dùng:
  python scripts/scorecard.py record
  python scripts/scorecard.py review
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from .decision_engine import build_decision_report, load_profile, source_fields
    from .finance_data import DataValidationError, load_history
except ImportError:
    from decision_engine import build_decision_report, load_profile, source_fields
    from finance_data import DataValidationError, load_history

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "history.jsonl"
JOURNAL = ROOT / "data" / "decision_journal.jsonl"
PROFILE = ROOT / "config" / "decision_profile.json"
VN = timezone(timedelta(hours=7))
ENGINE_VERSION = "2.0.0"


def load_journal(path=JOURNAL):
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise DataValidationError(f"{path.name} dòng {line_number}: JSON lỗi ({exc.msg})") from None
    return rows


def make_entry(report):
    assets = {}
    for item in [report["gold"], report["savings"], *report["stocks"]]:
        baseline = item.get("metrics", {})
        assets[item["id"]] = {
            "score": item["score"],
            "confidence": item["confidence"],
            "status": item["decision_status"],
            "signal": item["signal"],
            "baseline": baseline,
        }
    identifier = f"{report['as_of']['date']}-{report['as_of']['ky']}-{ENGINE_VERSION}"
    return {
        "id": identifier,
        "recorded_at": datetime.now(VN).isoformat(timespec="seconds"),
        "engine_version": ENGINE_VERSION,
        "as_of": report["as_of"],
        "data_quality_score": report["data_quality"]["score"],
        "evaluation_assumptions": {
            "stock_round_trip_cost_pct": report["profile"].get("stock_round_trip_cost_pct", 0.35),
        },
        "assets": assets,
    }


def append_entry(entry, path=JOURNAL):
    path = Path(path)
    rows = load_journal(path)
    if any(row.get("id") == entry["id"] for row in rows):
        raise DataValidationError(f"đã có nhật ký {entry['id']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return len(rows) + 1


def _future_value(history, after_date, path, horizon, date_path):
    if not after_date:
        return None, None
    try:
        after_time = datetime.fromisoformat(after_date)
        if after_time.tzinfo is None:
            after_time = after_time.replace(tzinfo=timezone.utc)
        after_time = after_time.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None, None
    seen = {}
    for snapshot in history:
        data_field = ".".join(path)
        date_field = date_path if isinstance(date_path, str) else ".".join(date_path)
        covered = source_fields(snapshot)
        if data_field not in covered or date_field not in covered:
            continue
        effective_date = snapshot
        for key in ((date_path,) if isinstance(date_path, str) else date_path):
            effective_date = effective_date.get(key) if isinstance(effective_date, dict) else None
        value = snapshot
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        try:
            effective_time = datetime.fromisoformat(effective_date)
            if effective_time.tzinfo is None:
                effective_time = effective_time.replace(tzinfo=timezone.utc)
            effective_time = effective_time.astimezone(timezone.utc)
        except (TypeError, ValueError):
            continue
        if effective_time > after_time and isinstance(value, (int, float)):
            seen[effective_date] = (effective_time, value)
    rows = [(effective_date, value) for effective_date, (_, value) in sorted(seen.items(), key=lambda item: item[1][0])]
    return rows[horizon - 1] if len(rows) >= horizon else (None, None)


def evaluate_entry(entry, history, horizon=5):
    outcomes = []
    market_date = entry.get("as_of", {}).get("market_date")
    gold_observed_at = entry.get("as_of", {}).get("gold_observed_at")
    gold_asset = entry.get("assets", {}).get("gold", {})
    use_domestic_gold = isinstance(gold_asset.get("baseline", {}).get("sjc_sell"), (int, float))
    mappings = {
        "gold": (("gold", "sjc_buy") if use_domestic_gold else ("gold", "xauusd"), ("gold", "observed_at"), gold_observed_at, "sjc_sell" if use_domestic_gold else "xauusd"),
        "vcb": (("vcb", "close"), "market_date", market_date, "price"),
        "ctd": (("ctd", "close"), "market_date", market_date, "price"),
    }
    savings_asset = entry.get("assets", {}).get("savings", {})
    savings_rate = savings_asset.get("baseline", {}).get("top_rate_pct") if savings_asset.get("status") == "READY" else None
    stock_cost = entry.get("evaluation_assumptions", {}).get("stock_round_trip_cost_pct", 0.35)
    for asset_id, (path, date_field, after_date, baseline_key) in mappings.items():
        asset = entry.get("assets", {}).get(asset_id)
        if not asset or asset.get("status") != "READY":
            continue
        if not isinstance(savings_rate, (int, float)):
            outcomes.append({"asset_id": asset_id, "status": "PENDING", "reason": "Thiếu lãi suất tiết kiệm đã xác minh làm mức chuẩn"})
            continue
        baseline = asset.get("baseline", {}).get(baseline_key)
        future_date, future = _future_value(history, after_date, path, horizon, date_field)
        if not isinstance(baseline, (int, float)) or not isinstance(future, (int, float)) or baseline == 0:
            outcomes.append({"asset_id": asset_id, "status": "PENDING"})
            continue
        raw_return_pct = (future - baseline) / baseline * 100
        net_return_pct = raw_return_pct - stock_cost if asset_id in ("vcb", "ctd") else raw_return_pct
        try:
            elapsed_days = max(1, (datetime.fromisoformat(future_date).date() - datetime.fromisoformat(after_date).date()).days)
        except (TypeError, ValueError):
            elapsed_days = horizon
        hurdle_pct = savings_rate * elapsed_days / 365 if isinstance(savings_rate, (int, float)) else None
        excess_pct = net_return_pct - hurdle_pct if hurdle_pct is not None else None
        score = asset["score"]
        comparison = excess_pct if excess_pct is not None else net_return_pct
        direction_correct = (score >= 55 and comparison > 0) or (score < 40 and comparison <= 0)
        outcomes.append({
            "asset_id": asset_id,
            "status": "ASSESSED",
            "horizon": horizon,
            "future_date": future_date,
            "gross_return_pct": round(raw_return_pct, 4),
            "net_return_pct": round(net_return_pct, 4),
            "savings_hurdle_pct": round(hurdle_pct, 4) if hurdle_pct is not None else None,
            "excess_vs_savings_pct": round(excess_pct, 4) if excess_pct is not None else None,
            "direction_correct": direction_correct if score >= 55 or score < 40 else None,
        })
    return outcomes


def build_scorecard(journal, history, horizon=5, minimum_assessed=20):
    outcomes = []
    for entry in journal:
        outcomes.extend(evaluate_entry(entry, history, horizon))
    assessed = [item for item in outcomes if item["status"] == "ASSESSED"]
    directional = [item for item in assessed if item["direction_correct"] is not None]
    correct = sum(bool(item["direction_correct"]) for item in directional)
    status = "READY" if len(assessed) >= minimum_assessed else "INSUFFICIENT_HISTORY"
    return {
        "status": status,
        "journal_entries": len(journal),
        "assessed": len(assessed),
        "pending": sum(item["status"] == "PENDING" for item in outcomes),
        "minimum_assessed": minimum_assessed,
        "directional_accuracy_pct": round(correct / len(directional) * 100, 2) if status == "READY" and directional else None,
        "horizon_periods": horizon,
        "outcomes": outcomes[-30:],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("record", "review"))
    args = parser.parse_args(argv)
    try:
        history = load_history(HISTORY)
        if args.command == "record":
            report = build_decision_report(history, {}, load_profile(PROFILE))
            entry = make_entry(report)
            count = append_entry(entry)
            print(f"Đã ghi nhật ký {entry['id']} — tổng {count} bản")
        else:
            scorecard = build_scorecard(load_journal(), history)
            print(json.dumps(scorecard, ensure_ascii=False, indent=2))
    except (DataValidationError, OSError) as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

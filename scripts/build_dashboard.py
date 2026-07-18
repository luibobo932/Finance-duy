#!/usr/bin/env python3
"""Tạo gói dữ liệu tĩnh để dashboard đọc trên GitHub Pages."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from math import isfinite
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    from .finance_data import DataValidationError, load_history
    from .decision_engine import build_decision_report, load_profile, load_source_registry, source_fields
    from .scorecard import build_scorecard, load_journal
except ImportError:  # Chạy trực tiếp: python scripts/build_dashboard.py
    from finance_data import DataValidationError, load_history
    from decision_engine import build_decision_report, load_profile, load_source_registry, source_fields
    from scorecard import build_scorecard, load_journal

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HISTORY = ROOT / "data" / "history.jsonl"
DEFAULT_PORTFOLIO = ROOT / "data" / "portfolio.local.json"
DEFAULT_OUTPUT = ROOT / "dashboard" / "data.json"
DEFAULT_PROFILE = ROOT / "config" / "decision_profile.json"
DEFAULT_JOURNAL = ROOT / "data" / "decision_journal.jsonl"
DEFAULT_MARKET_HISTORY = ROOT / "data" / "market_history.json"
MARKET_SYMBOLS = ("VCB", "CTD")
MARKET_SOURCE_URLS = {
    "cafef_history": "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx",
    "entrade_minute": "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock",
}


def _market_date(value, label):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise DataValidationError(f"market_history.{label}: ngày ISO không hợp lệ") from None


def _market_number(value, label, *, minimum=None, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise DataValidationError(f"market_history.{label}: phải là số hữu hạn")
    if integer and not isinstance(value, int):
        raise DataValidationError(f"market_history.{label}: phải là số nguyên")
    if minimum is not None and value < minimum:
        raise DataValidationError(f"market_history.{label}: phải >= {minimum}")
    return value


def _validate_market_sources(payload, market_day):
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise DataValidationError("market_history.sources: phải là danh sách")
    by_id = {item.get("id"): item for item in sources if isinstance(item, dict)}
    if len(sources) != len(MARKET_SOURCE_URLS) or set(by_id) != set(MARKET_SOURCE_URLS):
        raise DataValidationError("market_history.sources: phải có đúng hai nguồn phụ trợ đã đăng ký")
    try:
        batch_time = datetime.fromisoformat(payload.get("retrieved_at"))
    except (TypeError, ValueError):
        raise DataValidationError("market_history.retrieved_at: thời gian ISO không hợp lệ") from None
    for source_id, expected_url in MARKET_SOURCE_URLS.items():
        source = by_id.get(source_id)
        if (
            not source or source.get("url") != expected_url or not source.get("name") or not source.get("role")
            or source.get("source_tier") != "secondary" or source.get("decision_eligible") is not False
            or not isinstance(source.get("fields"), list) or not source.get("fields")
            or not isinstance(source.get("request_urls"), list) or len(source.get("request_urls")) != len(MARKET_SYMBOLS)
            or any(not isinstance(url, str) or not url.startswith(expected_url + "?") for url in source.get("request_urls", []))
            or not source.get("license_note")
        ):
            raise DataValidationError(f"market_history.sources: nguồn {source_id} sai registry")
        try:
            source_time = datetime.fromisoformat(source.get("retrieved_at"))
        except (TypeError, ValueError):
            raise DataValidationError(f"market_history.sources: nguồn {source_id} thiếu retrieved_at hợp lệ") from None
        if source_time.tzinfo is None:
            raise DataValidationError(f"market_history.sources: nguồn {source_id} thiếu múi giờ")
        source_age = batch_time - source_time
        if source_age < -timedelta(minutes=5) or source_age > timedelta(hours=2):
            raise DataValidationError(f"market_history.sources: thời gian nguồn {source_id} lệch batch")
        request_symbols = set()
        for request_url in source["request_urls"]:
            query = parse_qs(urlparse(request_url).query, keep_blank_values=True)
            if source_id == "cafef_history":
                symbol = (query.get("Symbol") or [""])[0].upper()
                if (query.get("PageIndex") or [""])[0] != "1" or (query.get("PageSize") or [""])[0] != "40":
                    raise DataValidationError("market_history.sources: query CafeF sai PageIndex/PageSize")
            else:
                symbol = (query.get("symbol") or [""])[0].upper()
                if (query.get("resolution") or [""])[0] != "1":
                    raise DataValidationError("market_history.sources: query EnTrade sai resolution")
                try:
                    start = int((query.get("from") or [""])[0])
                    end = int((query.get("to") or [""])[0])
                    request_day = datetime.fromtimestamp(start, source_time.tzinfo).date()
                except (TypeError, ValueError, OSError, OverflowError):
                    raise DataValidationError("market_history.sources: query EnTrade sai mốc thời gian") from None
                if request_day != market_day or end - start != 86400:
                    raise DataValidationError("market_history.sources: query EnTrade không khớp market_date")
            request_symbols.add(symbol)
        if request_symbols != set(MARKET_SYMBOLS):
            raise DataValidationError(f"market_history.sources: query {source_id} không đủ VCB/CTD")


def _validate_daily_rows(payload, market_day):
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise DataValidationError("market_history.daily: phải là object")
    for symbol in MARKET_SYMBOLS:
        rows = daily.get(symbol)
        if not isinstance(rows, list) or len(rows) < 2:
            raise DataValidationError(f"market_history.daily.{symbol}: cần ít nhất 2 phiên")
        row_dates = []
        for index, row in enumerate(rows):
            label = f"daily.{symbol}[{index}]"
            if not isinstance(row, dict):
                raise DataValidationError(f"market_history.{label}: phải là object")
            row_day = _market_date(row.get("date"), f"{label}.date")
            row_dates.append(row_day)
            opened = _market_number(row.get("open_vnd"), f"{label}.open_vnd", minimum=1, integer=True)
            high = _market_number(row.get("high_vnd"), f"{label}.high_vnd", minimum=1, integer=True)
            low = _market_number(row.get("low_vnd"), f"{label}.low_vnd", minimum=1, integer=True)
            closed = _market_number(row.get("close_vnd"), f"{label}.close_vnd", minimum=1, integer=True)
            _market_number(row.get("matched_volume"), f"{label}.matched_volume", minimum=0, integer=True)
            if low > min(opened, closed) or high < max(opened, closed):
                raise DataValidationError(f"market_history.{label}: vi phạm quan hệ OHLC")
            change_pct = row.get("change_pct")
            if change_pct is not None:
                _market_number(change_pct, f"{label}.change_pct")
        if row_dates != sorted(row_dates) or len(row_dates) != len(set(row_dates)):
            raise DataValidationError(f"market_history.daily.{symbol}: ngày phải tăng dần và không trùng")
        if row_dates[-1] != market_day:
            raise DataValidationError(f"market_history.daily.{symbol}: dòng cuối không khớp market_date")
        if rows[-1].get("change_pct") is None:
            raise DataValidationError(f"market_history.daily.{symbol}: phiên mới nhất thiếu change_pct")


def _validate_intraday(payload, market_day):
    daily = payload["daily"]
    intraday = payload.get("intraday")
    if not isinstance(intraday, dict):
        raise DataValidationError("market_history.intraday: phải là object")
    reconciled = []
    for symbol in MARKET_SYMBOLS:
        summary = intraday.get(symbol)
        if summary is None:
            continue
        if not isinstance(summary, dict):
            raise DataValidationError(f"market_history.intraday.{symbol}: phải là object")
        if _market_date(summary.get("market_date"), f"intraday.{symbol}.market_date") != market_day:
            raise DataValidationError(f"market_history.intraday.{symbol}: sai market_date")
        total = _market_number(summary.get("total_volume"), f"intraday.{symbol}.total_volume", minimum=0, integer=True)
        daily_volume = _market_number(summary.get("daily_volume"), f"intraday.{symbol}.daily_volume", minimum=0, integer=True)
        expected = daily[symbol][-1]["matched_volume"]
        computed_reconciled = total == daily_volume == expected
        if summary.get("reconciled_with_daily") is not computed_reconciled:
            raise DataValidationError(f"market_history.intraday.{symbol}: cờ đối soát không khớp số liệu")
        for field in ("bar_count", "morning_volume", "afternoon_volume", "atc_volume", "uptick_volume", "downtick_volume", "flat_volume"):
            minimum = 1 if field == "bar_count" else 0
            _market_number(summary.get(field), f"intraday.{symbol}.{field}", minimum=minimum, integer=True)
        direction_total = sum(summary[field] for field in ("uptick_volume", "downtick_volume", "flat_volume"))
        if direction_total != total:
            raise DataValidationError(f"market_history.intraday.{symbol}: tổng tick rule không khớp tổng phiên")
        if summary["morning_volume"] + summary["afternoon_volume"] != total or summary["atc_volume"] > total:
            raise DataValidationError(f"market_history.intraday.{symbol}: phân bổ thời gian không khớp tổng phiên")
        if computed_reconciled:
            reconciled.append(symbol)
    return reconciled


def _attach_hose_crosscheck(market_history, latest):
    """Đối chiếu nguồn phụ với snapshot HOSE đã duyệt, không cấp quyền mở khóa."""
    if not market_history:
        return
    verified_fields = source_fields(latest)
    same_market_date = latest.get("market_date") == market_history.get("market_date")
    rows = []
    for symbol in MARKET_SYMBOLS:
        key = symbol.lower()
        required = {f"{key}.prior_close", f"{key}.close", f"{key}.change_pct", f"{key}.volume_million_shares"}
        source_ready = same_market_date and required.issubset(verified_fields)
        auxiliary = market_history["daily"][symbol][-1]
        auxiliary_prior = market_history["daily"][symbol][-2]["close_vnd"]
        official = latest.get(key, {})
        prior_close_match = source_ready and auxiliary_prior == official.get("prior_close")
        close_match = source_ready and auxiliary["close_vnd"] == official.get("close")
        official_change = official.get("change_pct")
        auxiliary_change = auxiliary.get("change_pct")
        change_pct_match = (
            source_ready and isinstance(official_change, (int, float)) and isinstance(auxiliary_change, (int, float))
            and abs(auxiliary_change - official_change) <= 0.01
        )
        official_volume = official.get("volume_million_shares")
        volume_match = source_ready and isinstance(official_volume, (int, float)) and auxiliary["matched_volume"] == round(official_volume * 1_000_000)
        rows.append({
            "symbol": symbol,
            "available": source_ready,
            "prior_close_match": bool(prior_close_match),
            "close_match": bool(close_match),
            "change_pct_match": bool(change_pct_match),
            "volume_match": bool(volume_match),
            "matched": bool(prior_close_match and close_match and change_pct_match and volume_match),
        })
    market_history["quality"]["official_hose_crosscheck"] = {
        "available": all(item["available"] for item in rows),
        "matched": all(item["matched"] for item in rows),
        "symbols": rows,
        "note": "Đối chiếu giá tham chiếu, giá đóng cửa, % thay đổi và tổng khối lượng; chuỗi CafeF/DNSE vẫn là nguồn phụ trợ.",
    }


def load_market_history(path=DEFAULT_MARKET_HISTORY):
    path = Path(path)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataValidationError(f"{path.name}: JSON lỗi ({exc.msg})") from None
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise DataValidationError(f"{path.name}: schema không hợp lệ")
    if payload.get("classification") != "AUXILIARY_REFERENCE_ONLY" or payload.get("decision_unlock") is not False:
        raise DataValidationError(f"{path.name}: nguồn phụ trợ không được phép mở khóa quyết định")
    market_day = _market_date(payload.get("market_date"), "market_date")
    try:
        retrieved_at = datetime.fromisoformat(payload.get("retrieved_at"))
    except (TypeError, ValueError):
        raise DataValidationError("market_history.retrieved_at: thời gian ISO không hợp lệ") from None
    if retrieved_at.tzinfo is None:
        raise DataValidationError("market_history.retrieved_at: bắt buộc có múi giờ")
    if market_day > retrieved_at.date():
        raise DataValidationError("market_history.market_date: không được sau ngày thu thập")
    if retrieved_at > datetime.now(retrieved_at.tzinfo) + timedelta(minutes=5):
        raise DataValidationError("market_history.retrieved_at: không được nằm trong tương lai")
    _validate_market_sources(payload, market_day)
    _validate_daily_rows(payload, market_day)
    reconciled = _validate_intraday(payload, market_day)
    warnings = payload.get("warnings")
    if not isinstance(warnings, list) or any(not isinstance(item, str) for item in warnings):
        raise DataValidationError("market_history.warnings: phải là danh sách chuỗi")
    payload["quality"] = {
        "status": "RECONCILED" if len(reconciled) == len(MARKET_SYMBOLS) else "PARTIAL",
        "reconciled_symbols": reconciled,
        "required_symbols": list(MARKET_SYMBOLS),
        "validated_at_build": True,
    }
    return payload


def build_payload(history_path=DEFAULT_HISTORY, portfolio_path=DEFAULT_PORTFOLIO, profile_path=DEFAULT_PROFILE, market_history_path=DEFAULT_MARKET_HISTORY):
    history = load_history(history_path)
    if not history:
        raise DataValidationError("history.jsonl chưa có bản ghi")
    # Giữ tham số để tương thích lệnh cũ nhưng tuyệt đối không đọc dữ liệu danh mục private.
    profile = load_profile(profile_path)
    market_history = load_market_history(market_history_path)
    _attach_hose_crosscheck(market_history, history[-1])
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
        "market_history": market_history,
        "source_registry": load_source_registry(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--portfolio", type=Path, default=DEFAULT_PORTFOLIO, help="Đã ngừng dùng; dashboard công khai không đọc danh mục")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--market-history", type=Path, default=DEFAULT_MARKET_HISTORY)
    args = parser.parse_args(argv)

    try:
        payload = build_payload(args.history, args.portfolio, args.profile, args.market_history)
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

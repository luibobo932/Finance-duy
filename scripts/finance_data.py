#!/usr/bin/env python3
"""Đọc và kiểm tra dữ liệu dùng chung của Finance-duy."""

from __future__ import annotations

import json
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


class DataValidationError(ValueError):
    """Dữ liệu không đúng schema tối thiểu của dự án."""


def safe_print(message, *, file=None):
    """In thông báo mà không làm hỏng lệnh trên Windows dùng bảng mã cũ."""
    stream = file or sys.stdout
    text = str(message)
    encoding = getattr(stream, "encoding", None)
    if encoding:
        text = text.encode(encoding, errors="replace").decode(encoding)
    print(text, file=stream)


def _is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _optional_number(value, field, *, minimum=None):
    if value is None:
        return
    if not _is_number(value):
        raise DataValidationError(f"'{field}' phải là số hoặc null")
    if minimum is not None and value < minimum:
        raise DataValidationError(f"'{field}' phải >= {minimum}")


def validate_snapshot(snapshot, *, location="snapshot"):
    if not isinstance(snapshot, dict):
        raise DataValidationError(f"{location} phải là object JSON")

    for field in ("schema_version", "date", "ky", "vnindex", "gold"):
        if field not in snapshot:
            raise DataValidationError(f"{location} thiếu trường bắt buộc '{field}'")
    if snapshot["schema_version"] != 2:
        raise DataValidationError(f"{location}.schema_version phải bằng 2")

    try:
        date.fromisoformat(snapshot["date"])
    except (TypeError, ValueError):
        raise DataValidationError(
            f"{location}.date phải có dạng YYYY-MM-DD"
        ) from None

    if snapshot["ky"] not in ("sang", "chieu"):
        raise DataValidationError(f"{location}.ky phải là 'sang' hoặc 'chieu'")

    vnindex = snapshot["vnindex"]
    if not isinstance(vnindex, dict):
        raise DataValidationError(f"{location}.vnindex phải là object")
    _optional_number(vnindex.get("close"), f"{location}.vnindex.close", minimum=0)
    if vnindex.get("close") is None:
        raise DataValidationError(f"{location}.vnindex.close là bắt buộc")
    if vnindex["close"] <= 0:
        raise DataValidationError(f"{location}.vnindex.close phải > 0")
    _optional_number(vnindex.get("change_pct"), f"{location}.vnindex.change_pct")

    gold = snapshot["gold"]
    if not isinstance(gold, dict):
        raise DataValidationError(f"{location}.gold phải là object")
    for field in ("sjc_buy", "sjc_sell", "ring_sell", "xauusd", "premium_trieu"):
        _optional_number(gold.get(field), f"{location}.gold.{field}", minimum=0)
    if gold.get("sjc_sell") is None or gold.get("xauusd") is None:
        raise DataValidationError(f"{location}.gold cần sjc_sell và xauusd")
    for field in ("sjc_buy", "sjc_sell", "ring_sell", "xauusd"):
        if gold.get(field) is not None and gold[field] <= 0:
            raise DataValidationError(f"{location}.gold.{field} phải > 0")
    if gold.get("observed_at") is not None:
        try:
            observed_at = datetime.fromisoformat(gold["observed_at"])
        except (TypeError, ValueError):
            raise DataValidationError(f"{location}.gold.observed_at phải là ISO-8601") from None
        if observed_at.utcoffset() is None:
            raise DataValidationError(f"{location}.gold.observed_at phải có múi giờ")

    for ticker in ("vcb", "ctd"):
        value = snapshot.get(ticker)
        if value is None:
            continue
        if not isinstance(value, dict):
            raise DataValidationError(f"{location}.{ticker} phải là object")
        _optional_number(value.get("close"), f"{location}.{ticker}.close", minimum=0)
        _optional_number(value.get("prior_close"), f"{location}.{ticker}.prior_close", minimum=0)
        for price_field in ("close", "prior_close"):
            if value.get(price_field) is not None and value[price_field] <= 0:
                raise DataValidationError(f"{location}.{ticker}.{price_field} phải > 0")
        _optional_number(value.get("change_pct"), f"{location}.{ticker}.change_pct")
        if "volume" in value:
            raise DataValidationError(f"{location}.{ticker}.volume mơ hồ; dùng volume_million_shares")
        _optional_number(value.get("volume_million_shares"), f"{location}.{ticker}.volume_million_shares", minimum=0)

    _optional_number(snapshot.get("foreign_net_ty"), f"{location}.foreign_net_ty")
    _optional_number(snapshot.get("fx_vcb_sell"), f"{location}.fx_vcb_sell", minimum=0)
    if snapshot.get("fx_vcb_sell") is not None and snapshot["fx_vcb_sell"] <= 0:
        raise DataValidationError(f"{location}.fx_vcb_sell phải > 0")

    rates = snapshot.get("deposit_top", [])
    if not isinstance(rates, list):
        raise DataValidationError(f"{location}.deposit_top phải là mảng")
    for index, item in enumerate(rates):
        prefix = f"{location}.deposit_top[{index}]"
        if not isinstance(item, dict):
            raise DataValidationError(f"{prefix} phải là object")
        if not isinstance(item.get("bank"), str) or not item["bank"].strip():
            raise DataValidationError(f"{prefix}.bank không hợp lệ")
        if item.get("term_months") is None or item.get("rate_pct") is None:
            raise DataValidationError(f"{prefix} cần term_months và rate_pct")
        _optional_number(item.get("term_months"), f"{prefix}.term_months", minimum=1)
        _optional_number(item.get("rate_pct"), f"{prefix}.rate_pct", minimum=0)
        for amount_field in ("minimum_amount_vnd", "maximum_amount_vnd"):
            _optional_number(item.get(amount_field), f"{prefix}.{amount_field}", minimum=0)
        effective_date = item.get("effective_date")
        if effective_date is not None:
            try:
                date.fromisoformat(effective_date)
            except (TypeError, ValueError):
                raise DataValidationError(f"{prefix}.effective_date phải có dạng YYYY-MM-DD") from None

    flags = snapshot.get("risk_flags", {})
    if not isinstance(flags, dict):
        raise DataValidationError(f"{location}.risk_flags phải là object")

    collected_at = snapshot.get("collected_at")
    if collected_at is not None:
        try:
            parsed_collected_at = datetime.fromisoformat(collected_at)
        except (TypeError, ValueError):
            raise DataValidationError(
                f"{location}.collected_at phải là ISO-8601 có múi giờ"
            ) from None
        if parsed_collected_at.utcoffset() is None:
            raise DataValidationError(f"{location}.collected_at phải có múi giờ")

    market_date = snapshot.get("market_date")
    if market_date is not None:
        try:
            date.fromisoformat(market_date)
        except (TypeError, ValueError):
            raise DataValidationError(
                f"{location}.market_date phải có dạng YYYY-MM-DD"
            ) from None

    sources = snapshot.get("sources", [])
    if not isinstance(sources, list):
        raise DataValidationError(f"{location}.sources phải là mảng")
    for index, source in enumerate(sources):
        prefix = f"{location}.sources[{index}]"
        if not isinstance(source, dict):
            raise DataValidationError(f"{prefix} phải là object")
        if not isinstance(source.get("id"), str) or not source["id"].strip():
            raise DataValidationError(f"{prefix}.id không hợp lệ")
        if not isinstance(source.get("name"), str) or not source["name"].strip():
            raise DataValidationError(f"{prefix}.name không hợp lệ")
        url = source.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise DataValidationError(f"{prefix}.url phải bắt đầu bằng https://")
        fields = source.get("fields", [])
        if not isinstance(fields, list) or any(not isinstance(field, str) for field in fields):
            raise DataValidationError(f"{prefix}.fields phải là mảng chuỗi")
        retrieved_at = source.get("retrieved_at")
        if retrieved_at is None:
            raise DataValidationError(f"{prefix}.retrieved_at là bắt buộc")
        try:
            parsed_retrieved_at = datetime.fromisoformat(retrieved_at)
        except (TypeError, ValueError):
            raise DataValidationError(f"{prefix}.retrieved_at phải là ISO-8601") from None
        if parsed_retrieved_at.utcoffset() is None:
            raise DataValidationError(f"{prefix}.retrieved_at phải có múi giờ")

    if collected_at is not None:
        snapshot_date = date.fromisoformat(snapshot["date"])
        if parsed_collected_at.date() != snapshot_date:
            raise DataValidationError(f"{location}.collected_at phải cùng ngày với snapshot.date")
        if market_date is not None and date.fromisoformat(market_date) > parsed_collected_at.date():
            raise DataValidationError(f"{location}.market_date không được sau collected_at")
        if gold.get("observed_at") is not None and datetime.fromisoformat(gold["observed_at"]) > parsed_collected_at + timedelta(minutes=5):
            raise DataValidationError(f"{location}.gold.observed_at không được sau collected_at")
        for index, source in enumerate(sources):
            retrieved_at = datetime.fromisoformat(source["retrieved_at"])
            if retrieved_at > parsed_collected_at + timedelta(minutes=5):
                raise DataValidationError(f"{location}.sources[{index}].retrieved_at không được sau collected_at")

    return snapshot


def load_history(path):
    path = Path(path)
    if not path.exists():
        return []

    history = []
    last_key = None
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            snapshot = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DataValidationError(
                f"{path.name} dòng {line_number}: JSON lỗi ({exc.msg})"
            ) from None
        snapshot = validate_snapshot(snapshot, location=f"dòng {line_number}")
        key = (snapshot["date"], 0 if snapshot["ky"] == "sang" else 1)
        if last_key is not None and key <= last_key:
            raise DataValidationError(
                f"{path.name} dòng {line_number}: kỳ dữ liệu bị trùng hoặc không đúng thứ tự thời gian"
            )
        last_key = key
        history.append(snapshot)
    return history


def load_portfolio(path):
    path = Path(path)
    if not path.exists():
        return {}
    try:
        portfolio = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataValidationError(f"{path.name}: JSON lỗi ({exc.msg})") from None
    if not isinstance(portfolio, dict):
        raise DataValidationError("portfolio.json phải là object")

    for ticker, position in portfolio.items():
        if not isinstance(position, dict):
            raise DataValidationError(f"portfolio.{ticker} phải là object")
        _optional_number(position.get("avg_cost"), f"portfolio.{ticker}.avg_cost", minimum=0)
        _optional_number(position.get("quantity"), f"portfolio.{ticker}.quantity", minimum=0)
        if position.get("avg_cost") is not None and position["avg_cost"] <= 0:
            raise DataValidationError(f"portfolio.{ticker}.avg_cost phải > 0")
        if position.get("quantity") is not None and position["quantity"] <= 0:
            raise DataValidationError(f"portfolio.{ticker}.quantity phải > 0")
    return portfolio

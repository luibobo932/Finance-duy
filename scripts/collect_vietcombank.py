#!/usr/bin/env python3
"""Thu thập tỷ giá và lãi suất từ API chính thức của Vietcombank.

Chỉ ghi vào data/raw/ (đã bị Git bỏ qua). Dữ liệu phải được rà soát trước khi
đưa vào snapshot chính.

Cách dùng:
  python scripts/collect_vietcombank.py all
  python scripts/collect_vietcombank.py fx --date 2026-07-18
  python scripts/collect_vietcombank.py rates
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "vietcombank"
FX_URL = "https://www.vietcombank.com.vn/api/exchangerates"
RATES_URL = "https://www.vietcombank.com.vn/vi-VN/api/interestrates?accountType=Personal"


def fetch_json(url, timeout=30):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Finance-duy/1.0 (+personal decision support)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"không tải được {url}: {exc}") from None


def tenor_months(value):
    match = re.fullmatch(r"(\d+)-months", value or "")
    return int(match.group(1)) if match else None


def normalize_fx(payload, requested_date):
    if not isinstance(payload, dict) or not isinstance(payload.get("Data"), list) or not payload["Data"]:
        raise ValueError("payload tỷ giá Vietcombank rỗng hoặc sai schema")
    observed_at = payload.get("UpdatedDate")
    try:
        parsed_observed = datetime.fromisoformat(observed_at)
    except (TypeError, ValueError):
        raise ValueError("payload tỷ giá thiếu UpdatedDate ISO-8601") from None
    if parsed_observed.utcoffset() is None:
        raise ValueError("UpdatedDate tỷ giá phải có múi giờ")
    rows = []
    for item in payload.get("Data", []):
        currency = item.get("currencyCode")
        if not isinstance(currency, str) or not currency.strip():
            raise ValueError("payload tỷ giá có currencyCode không hợp lệ")
        try:
            values = {
                "cash_buy_vnd": float(item["cash"]) if item.get("cash") else None,
                "transfer_buy_vnd": float(item["transfer"]) if item.get("transfer") else None,
                "sell_vnd": float(item["sell"]) if item.get("sell") else None,
            }
        except (TypeError, ValueError):
            raise ValueError(f"payload tỷ giá {currency} có giá không hợp lệ") from None
        if any(value is not None and value <= 0 for value in values.values()):
            raise ValueError(f"payload tỷ giá {currency} có giá không dương")
        rows.append({
            "currency": currency,
            **values,
        })
    usd = next((item for item in rows if item["currency"] == "USD"), None)
    if not usd or usd["sell_vnd"] is None:
        raise ValueError("payload tỷ giá thiếu giá bán USD")
    return {
        "schema_version": 1,
        "kind": "fx",
        "requested_date": requested_date,
        "observed_at": observed_at,
        "source_url": f"{FX_URL}?{urllib.parse.urlencode({'date': requested_date})}",
        "publisher": "Vietcombank",
        "unit": "VND per currency unit",
        "data": rows,
    }


def normalize_rates(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("Data"), list) or not payload["Data"]:
        raise ValueError("payload lãi suất Vietcombank rỗng hoặc sai schema")
    observed_at = payload.get("UpdatedDate")
    try:
        parsed_observed = datetime.fromisoformat(observed_at)
    except (TypeError, ValueError):
        raise ValueError("payload lãi suất thiếu UpdatedDate ISO-8601") from None
    if parsed_observed.utcoffset() is None:
        raise ValueError("UpdatedDate lãi suất phải có múi giờ")
    rows = []
    for item in payload.get("Data", []):
        months = tenor_months(item.get("tenor"))
        if item.get("currencyCode") != "VND" or months is None:
            continue
        try:
            raw_rate = float(item.get("rates"))
        except (TypeError, ValueError):
            raise ValueError("payload lãi suất có rates không hợp lệ") from None
        if not 0 < raw_rate <= 0.20:
            raise ValueError(f"lãi suất API ngoài biên kỳ vọng: {raw_rate}")
        rows.append({
            "bank": "Vietcombank",
            "customer_type": "personal",
            "channel": item.get("tenorType"),
            "term_months": months,
            "rate_pct": round(raw_rate * 100, 4),
            "minimum_amount_vnd": None,
            "maximum_amount_vnd": None,
            "conditions": "Cần xác minh điều kiện sản phẩm tại thời điểm gửi",
            "effective_date": parsed_observed.date().isoformat(),
            "payout_method": None,
            "source_id": "vietcombank_deposit",
            "source_url": RATES_URL,
            "retrieved_at": observed_at,
        })
    if not rows:
        raise ValueError("payload không có lãi suất VND theo tháng")
    return {
        "schema_version": 1,
        "kind": "deposit_rates",
        "observed_at": observed_at,
        "source_url": RATES_URL,
        "publisher": "Vietcombank",
        "unit": "percent per year",
        "data": rows,
    }


def save_raw(kind, raw, normalized):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RAW_DIR / f"{stamp}_{kind}.json"
    path.write_text(
        json.dumps({"raw": raw, "normalized": normalized}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def collect_fx(requested_date):
    url = f"{FX_URL}?{urllib.parse.urlencode({'date': requested_date})}"
    raw = fetch_json(url)
    normalized = normalize_fx(raw, requested_date)
    return save_raw("fx", raw, normalized), normalized


def collect_rates():
    raw = fetch_json(RATES_URL)
    normalized = normalize_rates(raw)
    return save_raw("rates", raw, normalized), normalized


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("fx", "rates", "all"))
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args(argv)
    try:
        results = []
        if args.kind in ("fx", "all"):
            results.append(collect_fx(args.date))
        if args.kind in ("rates", "all"):
            results.append(collect_rates())
        for path, normalized in results:
            print(f"Đã lưu bản thô: {path}")
            print(json.dumps(normalized, ensure_ascii=False, indent=2))
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

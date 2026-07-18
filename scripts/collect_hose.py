#!/usr/bin/env python3
"""Thu thập dữ liệu cuối ngày HOSE cho watchlist.

Endpoint là JSON nội bộ trên tên miền HOSE, không có SLA. Chỉ lưu raw vào
data/raw/ và phải rà soát quyền phân phối lại trước khi công khai.

Cách dùng:
  python scripts/collect_hose.py 2026-07-17 VCB CTD
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "hose"
API_URL = "https://api.hsx.vn/mk/api/v1/market/quote-report"
PUBLIC_URL = "https://www.hsx.vn/vi/du-lieu-giao-dich/thong-ke/du-lieu-cuoi-ngay"
API_TYPE = "HJ2HNS3SKICV4FNE"


def parse_number(value):
    if value is None or value == "":
        return None
    parsed = float(str(value).replace(",", ""))
    if not math.isfinite(parsed):
        raise ValueError("HOSE trả số không hữu hạn")
    return parsed


def price_vnd(value, field, symbol):
    parsed = parse_number(value)
    if parsed is None:
        raise ValueError(f"HOSE thiếu {field} của {symbol}")
    if parsed <= 0:
        raise ValueError(f"HOSE trả {field} không dương của {symbol}")
    return parsed * 1000


def fetch_eod(trading_date, timeout=30):
    query = urllib.parse.urlencode({"tradingBy": "VNINDEX", "date": trading_date})
    request = urllib.request.Request(
        f"{API_URL}?{query}",
        data=b"{}",
        method="POST",
        headers={
            "type": API_TYPE,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Finance-duy/1.0 (+personal decision support)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"không tải được HOSE: {exc}") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list) or not payload["data"]:
        raise ValueError("HOSE trả payload rỗng hoặc sai schema")
    return payload


def normalize(payload, trading_date, symbols):
    try:
        date.fromisoformat(trading_date)
    except (TypeError, ValueError):
        raise ValueError("ngày HOSE phải có dạng YYYY-MM-DD") from None
    wanted = {symbol.upper() for symbol in symbols}
    rows = []
    for item in payload.get("data", []):
        if not isinstance(item, dict):
            raise ValueError("HOSE trả dòng dữ liệu không phải object")
        symbol = item.get("securitySymbol")
        if symbol not in wanted:
            continue
        main_lots = parse_number(item.get("mainVolume"))
        change_pct = parse_number(item.get("changePriceRatio"))
        if main_lots is None or main_lots < 0:
            raise ValueError(f"HOSE thiếu khối lượng hợp lệ của {symbol}")
        if change_pct is None or abs(change_pct) > 100:
            raise ValueError(f"HOSE thiếu biến động hợp lệ của {symbol}")
        rows.append({
            "symbol": symbol,
            "market_date": trading_date,
            "prior_close_vnd": price_vnd(item.get("priorClosePrice"), "priorClosePrice", symbol),
            "open_vnd": price_vnd(item.get("openPrice"), "openPrice", symbol),
            "high_vnd": price_vnd(item.get("highPrice"), "highPrice", symbol),
            "low_vnd": price_vnd(item.get("lowPrice"), "lowPrice", symbol),
            "close_vnd": price_vnd(item.get("closePrice"), "closePrice", symbol),
            "change_pct": change_pct,
            "volume_shares": main_lots * 100 if main_lots is not None else None,
            "volume_million_shares": main_lots / 10_000 if main_lots is not None else None,
            "value_million_vnd": parse_number(item.get("mainValue")),
        })
    missing = wanted - {item["symbol"] for item in rows}
    if missing:
        raise ValueError("HOSE không có mã: " + ", ".join(sorted(missing)))
    return {
        "schema_version": 1,
        "kind": "hose_eod",
        "market_date": trading_date,
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_url": PUBLIC_URL,
        "api_url": API_URL,
        "unit_note": "Giá gốc nghìn đồng; mainVolume gốc lô 100 cổ phiếu; mainValue triệu đồng",
        "data": sorted(rows, key=lambda item: item["symbol"]),
    }


def save_raw(payload, normalized):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RAW_DIR / f"{stamp}_{normalized['market_date']}_eod.json"
    path.write_text(json.dumps({"raw": payload, "normalized": normalized}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("date")
    parser.add_argument("symbols", nargs="+", default=["VCB", "CTD"])
    args = parser.parse_args(argv)
    try:
        payload = fetch_eod(args.date)
        normalized = normalize(payload, args.date, args.symbols)
        path = save_raw(payload, normalized)
        print(f"Đã lưu bản thô: {path}")
        print(json.dumps(normalized, ensure_ascii=False, indent=2))
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

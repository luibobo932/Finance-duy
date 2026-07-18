#!/usr/bin/env python3
"""Thu thập lịch sử VCB/CTD và cấu trúc nến phút cho dashboard.

Dữ liệu CafeF được dùng để bổ sung chuỗi giá ngày; tổng khối lượng phiên gần
nhất được đối chiếu với nến một phút DNSE/EnTrade. Đây không phải dữ liệu từng
lệnh khớp và không được dùng để kết luận gom/xả.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from math import isfinite
from pathlib import Path
from urllib.parse import urlencode

try:
    from .finance_data import DataValidationError, safe_print
    from .tick import candle_metrics
except ImportError:
    from finance_data import DataValidationError, safe_print
    from tick import candle_metrics

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "data" / "market_history.json"
VN = timezone(timedelta(hours=7))
CAFEF_ENDPOINT = "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx"
ENTRADE_ENDPOINT = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"
SYMBOLS = ("VCB", "CTD")


def fetch_json(url, *, referer=None, opener=urllib.request.urlopen):
    headers = {"Accept": "application/json", "User-Agent": "Finance-duy/1.0 Mozilla/5.0"}
    if referer:
        headers["Referer"] = referer
    request = urllib.request.Request(url, headers=headers)
    last_error = None
    for attempt in range(3):
        try:
            with opener(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(.6 * (attempt + 1))
    raise RuntimeError(f"không tải được {url} sau 3 lần thử: {last_error}") from None


def normalize_daily_payload(symbol, payload):
    if not isinstance(payload, dict) or payload.get("Success") is not True:
        raise DataValidationError(f"CafeF {symbol}: phản hồi không thành công")
    rows = payload.get("Data", {}).get("Data")
    if not isinstance(rows, list) or not rows:
        raise DataValidationError(f"CafeF {symbol}: không có lịch sử giá")
    normalized = []
    for index, item in enumerate(rows):
        try:
            day = datetime.strptime(item["Ngay"], "%d/%m/%Y").date().isoformat()
            close_thousand = float(item["GiaDongCua"])
            open_thousand = float(item["GiaMoCua"])
            high_thousand = float(item["GiaCaoNhat"])
            low_thousand = float(item["GiaThapNhat"])
            volume = int(item["KhoiLuongKhopLenh"])
            put_through_volume = int(item.get("KLThoaThuan") or 0)
            raw_matched_value = item.get("GiaTriKhopLenh")
            matched_value = float(raw_matched_value) if raw_matched_value not in (None, "") else None
        except (KeyError, TypeError, ValueError):
            raise DataValidationError(f"CafeF {symbol}: dòng {index + 1} sai schema") from None
        prices = (close_thousand, open_thousand, high_thousand, low_thousand)
        if not all(isfinite(value) for value in prices) or min(prices) <= 0 or volume < 0:
            raise DataValidationError(f"CafeF {symbol}: dòng {index + 1} có giá/khối lượng không hợp lệ")
        if put_through_volume < 0 or (matched_value is not None and (not isfinite(matched_value) or matched_value < 0)):
            raise DataValidationError(f"CafeF {symbol}: dòng {index + 1} có giá trị/thỏa thuận không hợp lệ")
        if low_thousand > min(open_thousand, close_thousand) or high_thousand < max(open_thousand, close_thousand):
            raise DataValidationError(f"CafeF {symbol}: dòng {index + 1} vi phạm quan hệ OHLC")
        change_pct = None
        change_text = str(item.get("ThayDoi") or "")
        if "(" in change_text and "%" in change_text:
            try:
                change_pct = float(change_text.split("(", 1)[1].split("%", 1)[0].replace(",", "."))
            except ValueError:
                change_pct = None
        if change_pct is not None and not isfinite(change_pct):
            raise DataValidationError(f"CafeF {symbol}: dòng {index + 1} có % thay đổi không hữu hạn")
        normalized.append({
            "date": day,
            "open_vnd": round(open_thousand * 1000),
            "high_vnd": round(high_thousand * 1000),
            "low_vnd": round(low_thousand * 1000),
            "close_vnd": round(close_thousand * 1000),
            "change_pct": change_pct,
            "matched_volume": volume,
            "matched_value_billion_vnd": matched_value,
            "put_through_volume": put_through_volume,
        })
    normalized.sort(key=lambda row: row["date"])
    return normalized


def fetch_daily(symbol, *, limit=40, fetcher=fetch_json):
    symbol = symbol.upper()
    if symbol not in SYMBOLS:
        raise DataValidationError(f"chỉ hỗ trợ {', '.join(SYMBOLS)}")
    query = urlencode({"Symbol": symbol, "StartDate": "", "EndDate": "", "PageIndex": 1, "PageSize": limit})
    url = f"{CAFEF_ENDPOINT}?{query}"
    payload = None
    for attempt in range(3):
        payload = fetcher(url, referer=f"https://cafef.vn/du-lieu/{symbol}-201.chn")
        if isinstance(payload, dict) and payload.get("Success") is True:
            break
        if attempt < 2:
            time.sleep(.6 * (attempt + 1))
    return normalize_daily_payload(symbol, payload)


def normalize_intraday_payload(symbol, market_date, payload):
    if not isinstance(payload, dict):
        raise DataValidationError(f"EnTrade {symbol}: phản hồi không phải object")
    keys = ("t", "o", "h", "l", "c", "v")
    arrays = [payload.get(key) for key in keys]
    if not all(isinstance(values, list) for values in arrays) or len({len(values) for values in arrays}) != 1:
        raise DataValidationError(f"EnTrade {symbol}: các mảng nến không đồng nhất")
    if not arrays[0]:
        raise DataValidationError(f"EnTrade {symbol}: không có nến cho {market_date}")
    bars = []
    candle_rows = []
    seen_timestamps = set()
    last_timestamp = None
    for timestamp, opened, high, low, closed, volume in zip(*arrays):
        try:
            timestamp = int(timestamp)
            opened = float(opened)
            high = float(high)
            low = float(low)
            closed = float(closed)
            volume = int(volume)
            observed = datetime.fromtimestamp(timestamp, VN)
        except (TypeError, ValueError, OSError, OverflowError):
            raise DataValidationError(f"EnTrade {symbol}: nến có giá trị sai kiểu") from None
        if observed.date().isoformat() != market_date:
            continue
        if timestamp in seen_timestamps:
            raise DataValidationError(f"EnTrade {symbol}: trùng timestamp {timestamp}")
        seen_timestamps.add(timestamp)
        if last_timestamp is not None and timestamp <= last_timestamp:
            raise DataValidationError(f"EnTrade {symbol}: timestamp không tăng dần")
        last_timestamp = timestamp
        prices = (opened, high, low, closed)
        if not all(isfinite(value) for value in prices) or min(prices) <= 0 or low > min(opened, closed) or high < max(opened, closed):
            raise DataValidationError(f"EnTrade {symbol}: nến {observed:%H:%M} vi phạm quan hệ OHLC")
        clock = observed.strftime("%H:%M")
        if not ("09:00" <= clock <= "11:30" or "13:00" <= clock <= "14:45"):
            raise DataValidationError(f"EnTrade {symbol}: nến {clock} ngoài giờ giao dịch HOSE")
        bar = {
            "time": clock,
            "open_thousand_vnd": opened,
            "high_thousand_vnd": high,
            "low_thousand_vnd": low,
            "close_thousand_vnd": closed,
            "volume": volume,
        }
        if bar["volume"] <= 0:
            continue
        bars.append(bar)
        candle_rows.append((bar["time"], bar["close_thousand_vnd"], bar["volume"]))
    if not bars:
        raise DataValidationError(f"EnTrade {symbol}: không có nến hợp lệ cho {market_date}")
    metrics = candle_metrics(candle_rows)
    average = metrics["total"] / len(bars)
    return {
        "market_date": market_date,
        "bar_count": len(bars),
        "total_volume": metrics["total"],
        "morning_volume": metrics["morning"],
        "afternoon_volume": metrics["afternoon"],
        "atc_volume": metrics["atc"],
        "uptick_volume": metrics["up"],
        "downtick_volume": metrics["down"],
        "flat_volume": metrics["flat"],
        "price_profile": [
            {"price_thousand_vnd": price, "volume": volume}
            for price, volume in metrics["profile"][:8]
        ],
        "large_bars": sorted(
            [bar for bar in bars if bar["volume"] >= average * 2],
            key=lambda bar: (-bar["volume"], bar["time"]),
        )[:10],
        "method_note": "Nến 1 phút; tick rule chỉ so giá đóng nến, không phải mua/bán chủ động chính thức.",
    }


def fetch_intraday(symbol, market_date, *, fetcher=fetch_json):
    start = datetime.fromisoformat(market_date).replace(tzinfo=VN)
    query = urlencode({
        "from": int(start.timestamp()),
        "to": int((start + timedelta(days=1)).timestamp()),
        "symbol": symbol.upper(),
        "resolution": 1,
    })
    payload = fetcher(f"{ENTRADE_ENDPOINT}?{query}")
    return normalize_intraday_payload(symbol.upper(), market_date, payload)


def build_market_history(*, daily_fetcher=fetch_daily, intraday_fetcher=fetch_intraday, now=None):
    daily = {symbol: daily_fetcher(symbol) for symbol in SYMBOLS}
    if any(not rows for rows in daily.values()):
        raise DataValidationError("CafeF: thiếu chuỗi giá cho VCB hoặc CTD")
    latest_dates = {symbol: rows[-1]["date"] for symbol, rows in daily.items()}
    common_dates = set.intersection(*(set(row["date"] for row in rows) for rows in daily.values()))
    if not common_dates:
        raise DataValidationError("CafeF: VCB và CTD không có ngày giao dịch chung")
    market_date = max(common_dates)
    intraday = {}
    warnings = []
    if len(set(latest_dates.values())) > 1:
        warnings.append(
            "Ngày mới nhất giữa các mã lệch nhau; dùng phiên chung "
            f"{market_date} (" + ", ".join(f"{symbol}={day}" for symbol, day in latest_dates.items()) + ")"
        )
    for symbol in SYMBOLS:
        daily[symbol] = [row for row in daily[symbol] if row["date"] <= market_date][-40:]
        if not daily[symbol] or daily[symbol][-1]["date"] != market_date:
            raise DataValidationError(f"CafeF {symbol}: không có dòng cho phiên chung {market_date}")
        try:
            summary = intraday_fetcher(symbol, market_date)
            if not isinstance(summary, dict) or summary.get("market_date") != market_date:
                raise DataValidationError(f"EnTrade {symbol}: summary sai phiên {market_date}")
            expected = daily[symbol][-1]["matched_volume"]
            summary["reconciled_with_daily"] = summary["total_volume"] == expected
            summary["daily_volume"] = expected
            if not summary["reconciled_with_daily"]:
                warnings.append(f"{symbol}: tổng nến phút {summary['total_volume']:,} khác CafeF {expected:,}")
            intraday[symbol] = summary
        except (DataValidationError, RuntimeError) as exc:
            warnings.append(str(exc))
    observed = now or datetime.now(VN)
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=VN)
    reconciled_symbols = sorted(
        symbol for symbol, summary in intraday.items() if summary.get("reconciled_with_daily") is True
    )
    daily_request_urls = [
        f"{CAFEF_ENDPOINT}?{urlencode({'Symbol': symbol, 'StartDate': '', 'EndDate': '', 'PageIndex': 1, 'PageSize': 40})}"
        for symbol in SYMBOLS
    ]
    intraday_start = datetime.fromisoformat(market_date).replace(tzinfo=VN)
    intraday_request_urls = [
        f"{ENTRADE_ENDPOINT}?{urlencode({'from': int(intraday_start.timestamp()), 'to': int((intraday_start + timedelta(days=1)).timestamp()), 'symbol': symbol, 'resolution': 1})}"
        for symbol in SYMBOLS
    ]
    return {
        "schema_version": 1,
        "classification": "AUXILIARY_REFERENCE_ONLY",
        "decision_unlock": False,
        "market_date": market_date,
        "retrieved_at": observed.isoformat(),
        "daily": daily,
        "intraday": intraday,
        "warnings": warnings,
        "quality": {
            "status": "RECONCILED" if len(reconciled_symbols) == len(SYMBOLS) else "PARTIAL",
            "reconciled_symbols": reconciled_symbols,
            "required_symbols": list(SYMBOLS),
            "coverage": {
                "daily": f"{sum(bool(daily.get(symbol)) for symbol in SYMBOLS)}/{len(SYMBOLS)}",
                "intraday": f"{len(intraday)}/{len(SYMBOLS)}",
            },
        },
        "sources": [
            {
                "id": "cafef_history", "name": "CafeF", "url": CAFEF_ENDPOINT,
                "role": "Lịch sử giá/khối lượng ngày", "source_tier": "secondary",
                "decision_eligible": False, "retrieved_at": observed.isoformat(),
                "fields": ["daily.VCB", "daily.CTD"],
                "request_urls": daily_request_urls,
                "request_note": "PageSize tối đa 40; symbol VCB và CTD; phản hồi không được lưu thô công khai.",
                "license_note": "Chỉ dùng tham khảo cá nhân; rà soát điều khoản trước khi phân phối lại.",
            },
            {
                "id": "entrade_minute", "name": "DNSE/EnTrade", "url": ENTRADE_ENDPOINT,
                "role": "Nến một phút phiên gần nhất", "source_tier": "secondary",
                "decision_eligible": False, "retrieved_at": observed.isoformat(),
                "fields": ["intraday.VCB", "intraday.CTD"],
                "request_urls": intraday_request_urls,
                "request_note": f"resolution=1; market_date={market_date}; phản hồi không được lưu thô công khai.",
                "license_note": "Nến phút chỉ để tham khảo cá nhân; không diễn giải thành từng giao dịch.",
            },
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        payload = build_market_history()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (DataValidationError, RuntimeError, OSError) as exc:
        safe_print(f"LỖI: {exc}", file=sys.stderr)
        return 1
    safe_print(f"Đã cập nhật {args.output} tới phiên {payload['market_date']}")
    for warning in payload["warnings"]:
        safe_print(f"CẢNH BÁO: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

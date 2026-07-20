#!/usr/bin/env python3
"""Tải dữ liệu EOD (giá đóng cửa mỗi phiên) thật từ services.entrade.com.vn
và ghi/gộp vào data/eod/<MÃ>.csv — định dạng scripts/indicators.py đọc được.

Chỉ chạy được khi network policy của môi trường cho phép
services.entrade.com.vn (bị chặn trong claude.ai sandbox, đã xác nhận mở
được trên laptop local — xem docs/ROADMAP.md mục 1).

Cách dùng:
  python3 scripts/fetch_eod.py VCB CTD              # 40 ngày gần nhất (mặc định)
  python3 scripts/fetch_eod.py VCB --days 90
"""
from __future__ import annotations

import csv
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EOD_DIR = ROOT / "data" / "eod"
VN = timezone(timedelta(hours=7))
API_URL = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"

NETWORK_HINT = (
    "Không tải được dữ liệu từ services.entrade.com.vn. Trong môi trường Claude Code "
    "sandbox, domain này thường bị chặn theo network policy — thử lại trên môi trường "
    "không bị chặn (VD laptop local), hoặc bơm CSV thủ công vào data/eod/."
)


class FetchError(RuntimeError):
    pass


def fetch_ohlc_raw(symbol: str, frm: int, to: int) -> dict:
    """Gọi API entrade, trả JSON thô {t,o,h,l,c,v,...}."""
    url = f"{API_URL}?from={frm}&to={to}&symbol={symbol}&resolution=1D"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError) as e:
        raise FetchError(f"{NETWORK_HINT}\nChi tiết lỗi: {e}") from e


def parse_ohlc_response(data: dict) -> list[dict]:
    """Chuyển JSON thô của entrade thành list bản ghi date/open/high/low/close/volume.

    Giá trả về từ entrade đã ở đơn vị nghìn đồng — khớp thẳng với quy ước
    của data/eod/<MÃ>.csv, không cần quy đổi.
    """
    times = data.get("t") or []
    opens = data.get("o") or []
    highs = data.get("h") or []
    lows = data.get("l") or []
    closes = data.get("c") or []
    vols = data.get("v") or []
    rows = []
    for t, o, h, low, c, v in zip(times, opens, highs, lows, closes, vols):
        if t is None or c is None:
            continue
        rows.append({
            "date": datetime.fromtimestamp(t, VN).strftime("%Y-%m-%d"),
            "open": float(o), "high": float(h), "low": float(low),
            "close": float(c), "volume": int(v or 0),
        })
    return rows


MARKET_CLOSE_HOUR = 15  # HOSE đóng cửa 14:45, chốt 15:00 giờ VN


def drop_incomplete_today(rows: list[dict], now: datetime) -> list[dict]:
    """Bỏ bar của NGÀY HÔM NAY nếu phiên chưa đóng cửa (trước 15h giờ VN).

    API entrade trả cả nến ngày đang giao dịch dở — nếu ghi vào data/eod,
    RSI/MACD/MA sẽ tính trên nến chưa hoàn chỉnh rồi cho tín hiệu sai lệch.
    Dữ liệu thiếu trung thực hơn dữ liệu nửa vời (data contract)."""
    today = now.astimezone(VN).strftime("%Y-%m-%d")
    if now.astimezone(VN).hour >= MARKET_CLOSE_HOUR:
        return rows
    return [r for r in rows if r["date"] != today]


def load_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    "date": r["date"].strip(),
                    "open": float(r["open"]), "high": float(r["high"]),
                    "low": float(r["low"]), "close": float(r["close"]),
                    "volume": int(float(r.get("volume") or 0)),
                })
            except (ValueError, KeyError):
                continue
    return rows


def merge_rows(existing: list[dict], new: list[dict]) -> list[dict]:
    """Gộp bản ghi mới vào lịch sử cũ, mới ghi đè cũ cùng ngày, sắp theo ngày tăng dần."""
    by_date = {r["date"]: r for r in existing}
    for r in new:
        by_date[r["date"]] = r
    return [by_date[d] for d in sorted(by_date)]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "open", "high", "low", "close", "volume"])
        for r in rows:
            writer.writerow([
                r["date"], f"{r['open']:.3f}", f"{r['high']:.3f}",
                f"{r['low']:.3f}", f"{r['close']:.3f}", r["volume"],
            ])


def fetch_and_update(symbol: str, days: int, now: Optional[datetime] = None) -> int:
    """Tải + gộp dữ liệu EOD cho 1 mã, trả về tổng số phiên sau khi gộp."""
    now = now or datetime.now(VN)
    frm = int((now - timedelta(days=days)).timestamp())
    to = int(now.timestamp())
    raw = fetch_ohlc_raw(symbol, frm, to)
    new_rows = drop_incomplete_today(parse_ohlc_response(raw), now)
    path = EOD_DIR / f"{symbol.upper()}.csv"
    merged = merge_rows(load_existing(path), new_rows)
    write_csv(path, merged)
    return len(merged)


def main() -> None:
    args = sys.argv[1:]
    days = 40
    if "--days" in args:
        i = args.index("--days")
        days = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    symbols = [a.upper() for a in args if not a.startswith("--")]
    if not symbols:
        sys.exit(__doc__)
    for symbol in symbols:
        try:
            n = fetch_and_update(symbol, days)
        except FetchError as e:
            print(f"{symbol}: {e}", file=sys.stderr)
            continue
        print(f"{symbol}: đã ghi {n} phiên vào data/eod/{symbol}.csv")


if __name__ == "__main__":
    main()

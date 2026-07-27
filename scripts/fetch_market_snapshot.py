#!/usr/bin/env python3
"""Tải phần dữ liệu thị trường TỰ ĐỘNG lấy được bằng API công khai (không
cần WebSearch/AI), ghi vào data/history.jsonl qua cùng cơ chế validate của
scripts/trend.py.

Bối cảnh (2026-07-27): trước đây phần này do 1 routine claude.ai (dùng
WebSearch) đảm nhiệm 2 lần/ngày. Chủ dự án quyết định ngừng routine đó, chỉ
giữ automation local. Script này lấp khoảng trống cho phần vàng — QUAN
TRỌNG NHẤT vì vàng chiếm 74,6% tài sản, Risk Officer cần giá tham chiếu
tương đối mới để quyết định vàng có ý nghĩa.

Tự động lấy được (API công khai, không cần key):
  - XAU/USD thật từ api.gold-api.com
  - Tỷ giá USD/VND bán ra thật từ portal.vietcombank.com.vn (XML tỷ giá)
  - Giá đóng cửa VCB/CTD thật từ data/eod/ (đã có nhờ fetch_eod.py)

CHƯA tự động lấy được (cần WebSearch hoặc nhập tay — trung thực để trống,
KHÔNG bịa số): VN-Index, khối ngoại mua/bán ròng, giá SJC/vàng nhẫn tại
tiệm trong nước, lãi suất tiết kiệm, tin tức pháp lý/quản trị. Xem
docs/ROADMAP.md.

Cách dùng:
  python3 scripts/fetch_market_snapshot.py chieu    # hoặc "sang"
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

GOLD_API_URL = "https://api.gold-api.com/price/XAU"
VCB_FX_URL = "https://portal.vietcombank.com.vn/Usercontrols/TVPortal.TyGia/pXML.aspx?b=10"
EOD_DIR = ROOT / "data" / "eod"


def _http_get(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_xau_usd() -> Optional[float]:
    try:
        data = json.loads(_http_get(GOLD_API_URL))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    price = data.get("price")
    return round(float(price), 1) if isinstance(price, (int, float)) and price > 0 else None


def parse_vcb_usd_sell(xml_text: str) -> Optional[float]:
    """Lấy tỷ giá BÁN RA của USD từ XML tỷ giá VCB. None nếu không tìm thấy
    hoặc XML không hợp lệ — không suy đoán, không bịa."""
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return None
    for node in root.findall(".//Exrate"):
        if node.get("CurrencyCode") == "USD":
            sell = node.get("Sell", "")
            cleaned = re.sub(r"[^\d.]", "", sell)
            return float(cleaned) if cleaned else None
    return None


def fetch_fx_vcb_sell() -> Optional[float]:
    try:
        xml_text = _http_get(VCB_FX_URL)
    except (urllib.error.URLError, TimeoutError):
        return None
    return parse_vcb_usd_sell(xml_text)


def latest_eod_close_pct(symbol: str) -> Optional[dict]:
    """Đọc phiên gần nhất + phiên trước từ data/eod/<symbol>.csv (đã có sẵn
    nhờ fetch_eod.py) để tính close/change_pct/volume thật."""
    from fetch_eod import load_existing

    rows = load_existing(EOD_DIR / f"{symbol.upper()}.csv")
    if len(rows) < 1:
        return None
    last = rows[-1]
    change_pct = None
    if len(rows) >= 2 and rows[-2]["close"]:
        change_pct = round((last["close"] - rows[-2]["close"]) / rows[-2]["close"] * 100, 2)
    # Đơn vị VND thô để khớp quy ước history.jsonl (data/eod dùng nghìn đồng)
    return {"close": round(last["close"] * 1000), "change_pct": change_pct,
            "volume": round(last["volume"] / 1_000_000, 3)}


def build_snapshot(date: str, ky: str, xau_usd: Optional[float], fx_vcb_sell: Optional[float],
                   vcb: Optional[dict], ctd: Optional[dict]) -> dict:
    """Ghép snapshot chỉ từ dữ liệu THẬT đã lấy được. Trường nào không có
    dữ liệu thì KHÔNG đưa vào (trừ 'vnindex'/'gold' — trend.py REQUIRED phải
    có mặt 2 key này, nhưng để rỗng {} là trung thực, không phải bịa số)."""
    snap: dict = {"date": date, "ky": ky, "vnindex": {}}
    gold: dict = {}
    if xau_usd is not None:
        gold["xauusd"] = xau_usd
    snap["gold"] = gold
    if fx_vcb_sell is not None:
        snap["fx_vcb_sell"] = fx_vcb_sell
    if vcb is not None:
        snap["vcb"] = vcb
    if ctd is not None:
        snap["ctd"] = ctd
    return snap


def main() -> None:
    ky = sys.argv[1] if len(sys.argv) > 1 else "chieu"
    if ky not in ("sang", "chieu"):
        sys.exit("Tham số phải là 'sang' hoặc 'chieu'")

    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone(timedelta(hours=7)))
    date_str = now.strftime("%Y-%m-%d")

    xau_usd = fetch_xau_usd()
    fx_vcb_sell = fetch_fx_vcb_sell()
    vcb = latest_eod_close_pct("VCB")
    ctd = latest_eod_close_pct("CTD")

    snap = build_snapshot(date_str, ky, xau_usd, fx_vcb_sell, vcb, ctd)

    from trend import HIST, load_history, validate_snapshot  # noqa: E402

    hist = load_history()
    if any(h["date"] == snap["date"] and h["ky"] == snap["ky"] for h in hist):
        print(f"Đã có snapshot {snap['date']} kỳ {snap['ky']} — bỏ qua (không ghi trùng).")
        return
    errors = validate_snapshot(snap)
    if errors:
        sys.exit("LỖI: dữ liệu bất thường, từ chối ghi:\n" + "\n".join(f"  - {e}" for e in errors))
    HIST.parent.mkdir(parents=True, exist_ok=True)
    with HIST.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snap, ensure_ascii=False) + "\n")

    missing = [k for k, v in [("XAU/USD", xau_usd), ("tỷ giá VCB", fx_vcb_sell),
                              ("VCB EOD", vcb), ("CTD EOD", ctd)] if v is None]
    print(f"Đã ghi snapshot {date_str} ({ky}) vào data/history.jsonl.")
    if missing:
        print(f"Chưa lấy được: {', '.join(missing)} (không bịa, để trống).")
    print("LƯU Ý: VN-Index, khối ngoại, giá SJC/vàng nhẫn tại tiệm, lãi suất tiết kiệm "
          "vẫn CHƯA có nguồn tự động — cần WebSearch hoặc nhập tay.")


if __name__ == "__main__":
    main()

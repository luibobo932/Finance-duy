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
    nhờ fetch_eod.py) để tính close/change_pct/volume thật.

    Kèm `as_of` = ngày của CHÍNH nến đó. Không có trường này thì giá bị đóng
    dấu ngày của snapshot, và một nến cũ 19 ngày sẽ được ghi vào lịch sử như
    thể là giá hôm nay — xem `build_snapshot` để biết vì sao điều đó nguy hiểm.
    """
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
            "volume": round(last["volume"] / 1_000_000, 3),
            "as_of": last.get("date")}


def _eod_too_old(field: Optional[dict], snapshot_date: str) -> bool:
    """Nến EOD cũ hơn ngưỡng so với ngày snapshot thì KHÔNG được ghi vào.

    Ngưỡng dùng chung `analytics.data_quality.EOD_MAX_AGE_DAYS` — cùng con số
    mà health check và Decision Engine dùng, không đặt ngưỡng thứ ba.
    """
    if not field or not field.get("as_of"):
        return False  # không biết ngày nến thì không kết luận được, để validate khác lo
    from datetime import datetime

    from analytics.data_quality import EOD_MAX_AGE_DAYS

    try:
        bar = datetime.strptime(field["as_of"][:10], "%Y-%m-%d").date()
        day = datetime.strptime(snapshot_date[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return False
    return (day - bar).days > EOD_MAX_AGE_DAYS


def build_snapshot(date: str, ky: str, xau_usd: Optional[float], fx_vcb_sell: Optional[float],
                   vcb: Optional[dict], ctd: Optional[dict]) -> dict:
    """Ghép snapshot chỉ từ dữ liệu THẬT đã lấy được. Trường nào không có
    dữ liệu thì KHÔNG đưa vào (trừ 'vnindex'/'gold' — trend.py REQUIRED phải
    có mặt 2 key này, nhưng để rỗng {} là trung thực, không phải bịa số).

    Một nến EOD CŨ bị bỏ ra, không phải được ghi kèm ghi chú. Lý do đo được
    ngày 29/08: chạy script này khi mạng bị chặn cho ra snapshot
    `{"date": "2026-08-29", ..., "vcb": {"close": 60300, "change_pct": 1.01}}`
    — giá đóng cửa ngày 10/08 mang nhãn ngày 29/08. Không ai đọc lịch sử sau
    này phân biệt được nữa, và `analytics/price_sanity.py` cũng không bắt
    được: nó so giá với snapshot LIỀN TRƯỚC, mà chép nguyên giá cũ sang thì
    lệch 0% — qua mọi kiểm tra một cách hoàn hảo. Đây là rửa dữ liệu cũ thành
    dữ liệu mới, đúng thứ mà lượt sửa trước vừa chặn ở nhánh khuyến nghị.
    """
    snap: dict = {"date": date, "ky": ky, "vnindex": {}}
    gold: dict = {}
    if xau_usd is not None:
        gold["xauusd"] = xau_usd
    snap["gold"] = gold
    if fx_vcb_sell is not None:
        snap["fx_vcb_sell"] = fx_vcb_sell
    if vcb is not None and not _eod_too_old(vcb, date):
        snap["vcb"] = vcb
    if ctd is not None and not _eod_too_old(ctd, date):
        snap["ctd"] = ctd
    return snap


def refuse_reasons(snap: dict) -> list[str]:
    """Vì sao snapshot này KHÔNG đáng ghi vào lịch sử. Rỗng = ghi được.

    `validate_snapshot()` của trend.py bắt giá SAI (âm, bằng 0, bất khả thi).
    Nó không bắt giá THIẾU, vì thiếu không phải một giá trị bất thường — và
    đó là lỗ hổng đã lọt: khi mọi nguồn mạng đều hỏng, script vẫn ghi
    `{"date": "2026-08-29", "gold": {}}` và trả về mã thoát 0 như thành công.

    Hậu quả đo được ngay: `reporting/dashboard_builder.value_at()` trả
    `total_trieu=None` cho kỳ mới nhất — đường tài sản ròng thủng đúng ở đầu
    bên phải; Decision Engine ghi tiếp 4 quyết định dựa trên kỳ rỗng đó.

    Vàng là 76% tài sản. Một snapshot không có giá vàng không phải "snapshot
    thiếu vài trường" — nó không phải snapshot. Thà không ghi gì còn hơn ghi
    một kỳ rỗng rồi để cả hệ thống coi đó là hiện trạng mới nhất.
    """
    reasons = []
    if not (snap.get("gold") or {}).get("xauusd"):
        reasons.append("không lấy được giá vàng thế giới (XAU/USD) — vàng chiếm ~76% tài sản, "
                       "snapshot không có giá vàng thì không định giá được danh mục")
    if not snap.get("fx_vcb_sell"):
        reasons.append("không lấy được tỷ giá USD/VND — không quy đổi được giá vàng ra VND")
    return reasons


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
    refused = refuse_reasons(snap)
    if refused:
        sys.exit("TỪ CHỐI GHI: snapshot rỗng thì tệ hơn là không có snapshot.\n"
                 + "\n".join(f"  - {r}" for r in refused)
                 + "\n\nKhông ghi gì vào data/history.jsonl. Kiểm tra mạng tới "
                   "api.gold-api.com và portal.vietcombank.com.vn rồi chạy lại.")
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

"""Đồng bộ lãi suất từ snapshot bản tin vào kho chuẩn hoá.

Lỗi gốc mà module này sửa: `data/history.jsonl` (bản tin ghi mỗi kỳ) và
`data/normalized/deposit_rates.jsonl` (module `deposits/` đọc) là HAI nguồn sự
thật rời nhau. Thực tế đã lệch: ngày 22/7 bản tin dùng VIB 8,0% / OCB 7,1%
trong khi kho chuẩn hoá vẫn đứng ở 19/7 với Bắc Á/OceanBank — nghĩa là
`scripts/deposits_report.py` và bản tin nói hai chuyện khác nhau về cùng một
câu hỏi "gửi ở đâu lãi cao nhất".

Cách sửa: mỗi lần `scripts/trend.py append` ghi snapshot, lãi suất trong đó
được đổ luôn vào kho chuẩn hoá. `load_normalized()` chỉ lấy bản ghi thuộc ngày
mới nhất nên bản ghi mới tự nhiên thay bản cũ, không cần xoá lịch sử.

Trung thực về kênh gửi: snapshot chỉ có `rate_pct`, KHÔNG nói online hay tại
quầy. Ta không đoán — ghi vào `rate_online` (kênh phổ biến của các mức lãi cao
nhất) nhưng ghi rõ trong `conditions` rằng kênh chưa xác định, để người đọc
biết cần kiểm tra lại chứ không tưởng là đã xác nhận.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
NORMALIZED = ROOT / "data" / "normalized" / "deposit_rates.jsonl"

UNKNOWN_CHANNEL_NOTE = "kênh gửi chưa xác định từ snapshot bản tin — cần kiểm tra online/tại quầy"
SOURCE_LABEL = "snapshot bản tin (scripts/trend.py append) — tổng hợp WebSearch, chưa phải API ngân hàng"


def _existing_keys(path: Path) -> set[tuple[str, int, str]]:
    """(bank, term_months, updated_at) đã có — dùng để không ghi trùng."""
    if not path.exists():
        return set()
    keys = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        keys.add((row.get("bank", ""), int(row.get("term_months") or 0), row.get("updated_at", "")))
    return keys


def snapshot_to_rates(snapshot: dict) -> list[dict]:
    """Đổi `deposit_top` của snapshot thành các bản ghi DepositRate dạng dict.

    Bỏ qua mục thiếu tên ngân hàng / kỳ hạn / lãi suất — thiếu dữ liệu thì
    không ghi, không điền mặc định.
    """
    date = snapshot.get("date")
    if not date:
        return []
    out: list[dict] = []
    for item in snapshot.get("deposit_top") or []:
        bank = (item.get("bank") or "").strip()
        term = item.get("term_months")
        rate = item.get("rate_pct")
        if not bank or term is None or rate is None:
            continue
        channel = (item.get("channel") or "").strip().lower()
        record = {
            "bank": bank,
            "term_months": int(term),
            "rate_online": None,
            "rate_counter": None,
            "min_deposit_vnd": None,  # snapshot không ghi mức tối thiểu → để None, không bịa
            "conditions": item.get("conditions") or ("" if channel else UNKNOWN_CHANNEL_NOTE),
            "interest_payment": "cuoi_ky",
            "updated_at": date,
            "source": SOURCE_LABEL,
        }
        if channel == "counter":
            record["rate_counter"] = float(rate)
        else:
            record["rate_online"] = float(rate)
        out.append(record)
    return out


def sync_snapshot(snapshot: dict, path: Optional[Path] = None) -> int:
    """Ghi lãi suất của snapshot vào kho chuẩn hoá. Trả về số bản ghi đã thêm.

    Idempotent: gọi lại với cùng snapshot sẽ không thêm bản trùng
    (bank + kỳ hạn + ngày), nên chạy lại `trend.py append` an toàn.
    """
    path = path or NORMALIZED
    rates = snapshot_to_rates(snapshot)
    if not rates:
        return 0
    seen = _existing_keys(path)
    fresh = [r for r in rates if (r["bank"], r["term_months"], r["updated_at"]) not in seen]
    if not fresh:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in fresh:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(fresh)

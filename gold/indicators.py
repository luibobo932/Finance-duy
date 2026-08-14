"""Chỉ báo kỹ thuật cho giá vàng — dùng chung analytics/ta_core.py với cổ phiếu.

QUAN TRỌNG: `trend_label()` ở đây chỉ trả xu hướng THỊ TRƯỜNG thuần túy
(TICH_CUC/TIEU_CUC/TRUNG_TINH), hoặc **None khi không đo được**. Hành động
danh mục (GIỮ/CHỐT BỚT/...) KHÔNG được quyết định ở module này — đó là việc
của decision/policy_engine.py (Phase 7), vì nó còn phụ thuộc tỷ trọng danh
mục và hạn mức rủi ro, không chỉ xu hướng giá.

Hai lỗi đã sửa ở đây (14/08/2026), cùng một gốc: module tự tin hơn dữ liệu.

1. **Đọc nhầm nguồn.** Mặc định đọc `xuan_trieu_gold_history.csv` — file có
   ĐÚNG 1 dòng ngày 18/7, nên mọi chỉ báo trả None suốt gần một tháng. Trong
   khi đó `data/history.jsonl` có **19 quan sát XAU/USD thật** nằm không ai
   dùng. Đo trên chuỗi đó ra ngay RSI(14) = 78,3 — vùng quá mua rõ rệt, một
   tín hiệu mà hệ thống chưa từng nhìn thấy lần nào.

2. **"Không đo được" bị trả về thành "đi ngang".** Cả khi thiếu dữ liệu lẫn
   khi thị trường thật sự trung tính, hàm đều trả `TRUNG_TINH`. Hai chuyện
   khác hẳn nhau: một đằng là kết luận, một đằng là chưa có kết luận. Vì bị
   gộp, bản tin in "Xu hướng kỹ thuật: TRUNG_TINH" như một phát hiện, và
   `signal_agreement_from_labels` đếm nó là 1 tín hiệu có mặt. Nay thiếu dữ
   liệu trả **None**.

   Kèm theo: cũ đòi CÓ ĐỦ cả RSI lẫn MACD mới chấm. MACD cần ≥26 điểm nên với
   19 điểm hiện có, RSI 78,3 vẫn bị vứt đi và báo TRUNG_TINH. Nay chấm trên
   những chỉ báo ĐANG CÓ, và nói rõ đã dùng cái nào.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

from analytics.ta_core import atr, bollinger, macd, rsi, sma, volatility_annualized_pct

ROOT = Path(__file__).resolve().parent.parent
HISTORY_CSV = ROOT / "data" / "normalized" / "xuan_trieu_gold_history.csv"
HISTORY_JSONL = ROOT / "data" / "history.jsonl"

# Chuỗi mặc định để đo xu hướng: giá vàng THẾ GIỚI từ snapshot bản tin. Đây là
# chuỗi thật, dày nhất đang có (19 điểm) và là biến dẫn dắt giá trong nước.
#
# KHÔNG suy ra giá tiệm từ chuỗi này để lấp vào file hiệu chuẩn: `ring_sell`
# (giá niêm yết) và `shop_buy_trieu` (giá tiệm MUA vào) là hai đại lượng khác
# nhau; quy đổi qua lại sẽ là bịa số liệu hiệu chuẩn.
DEFAULT_SOURCE = "xauusd"


def load_series(column: str = "shop_buy_trieu") -> list[tuple[str, float]]:
    """Chuỗi giá tiệm từ file hiệu chuẩn (ảnh bảng giá) — vẫn giữ để đối chiếu."""
    if not HISTORY_CSV.exists():
        return []
    out = []
    with HISTORY_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                out.append((r["date"], float(r[column])))
            except (ValueError, KeyError, TypeError):
                continue
    return out


def load_xau_series(history: Optional[list[dict]] = None) -> list[tuple[str, float]]:
    """Chuỗi XAU/USD từ data/history.jsonl, theo thứ tự kỳ.

    Mỗi kỳ bản tin (sáng/chiều) là một điểm — KHÔNG phải mỗi phiên. Chỉ báo
    vì thế đọc theo "kỳ quan sát", không phải "phiên giao dịch"; khoảng cách
    giữa các điểm cũng không đều (có ngày nghỉ). Nói rõ ở đây thay vì để người
    đọc ngầm hiểu RSI(14) là 14 phiên.
    """
    rows = list(history) if history is not None else _load_history()
    out = []
    for r in rows:
        gold = r.get("gold")
        value = gold.get(DEFAULT_SOURCE) if isinstance(gold, dict) else None
        if isinstance(value, (int, float)) and value > 0:
            out.append((str(r.get("date", "")), float(value)))
    return out


def _load_history() -> list[dict]:
    if not HISTORY_JSONL.exists():
        return []
    return [json.loads(l) for l in HISTORY_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]


def analyze(column: Optional[str] = None, history: Optional[list[dict]] = None) -> dict:
    """Chỉ báo trên chuỗi XAU/USD (mặc định) hoặc trên một cột của file hiệu chuẩn.

    `column=None` → dùng chuỗi thế giới. Truyền tên cột để đo chuỗi giá tiệm
    như trước (vẫn dùng được, chỉ là dữ liệu còn quá mỏng).
    """
    if column is None:
        series, source, unit = load_xau_series(history), DEFAULT_SOURCE, "USD/oz"
    else:
        series, source, unit = load_series(column), column, "triệu/lượng"
    closes = [p for _, p in series]
    n = len(closes)
    return {
        "column": source,
        "source": "data/history.jsonl" if column is None else "xuan_trieu_gold_history.csv",
        "unit": unit,
        "sessions": n,
        "last_value": closes[-1] if closes else None,
        "last_date": series[-1][0] if series else None,
        "rsi14": rsi(closes),
        "macd": macd(closes),
        "sma20": sma(closes, 20),
        "sma50": sma(closes, 50),
        "sma200": sma(closes, 200),
        "bollinger": bollinger(closes),
        "volatility_20d_annualized_pct": volatility_annualized_pct(closes, 20),
        "needed_for_full_history": max(0, 200 - n),
    }


def trend_label(a: dict) -> Optional[str]:
    """Xu hướng kỹ thuật thuần túy — KHÔNG phải hành động danh mục.

    Trả **None** khi không có chỉ báo nào đo được. None nghĩa là "chưa đo
    được", khác hẳn TRUNG_TINH nghĩa là "đã đo, và đang đi ngang" — gộp hai
    thứ này làm hệ thống nói chắc về điều nó không biết.

    Chấm trên những chỉ báo ĐANG CÓ thay vì đòi đủ bộ: RSI cần 15 điểm, MACD
    cần 26. Với 19 điểm hiện có, đòi đủ bộ nghĩa là vứt bỏ RSI 78,3 (quá mua
    rõ rệt) và báo "trung tính".
    """
    votes = _votes(a)
    if not votes:
        return None
    score = sum(votes.values())
    if score >= 1:
        return "TICH_CUC"
    if score <= -1:
        return "TIEU_CUC"
    return "TRUNG_TINH"


def trend_evidence(a: dict) -> str:
    """Câu giải thích nhãn xu hướng đến từ chỉ báo nào — nhãn không kèm căn cứ
    thì người đọc không có cách nào phản biện nó."""
    votes = _votes(a)
    if not votes:
        return (f"chưa đo được xu hướng: {a.get('sessions', 0)} kỳ quan sát, "
                "chưa đủ cho RSI(14) (cần 15) hay MACD (cần 26)")
    bits = []
    if "rsi" in votes:
        bits.append(f"RSI(14)={a['rsi14']:.1f}")
    if "macd" in votes:
        bits.append(f"MACD hist={a['macd']['hist']:+.2f}")
    return (f"đo trên {a.get('sessions', 0)} kỳ {a.get('column', '')} "
            f"({a.get('source', '')}): " + ", ".join(bits))


def _votes(a: dict) -> dict[str, int]:
    """Phiếu của từng chỉ báo ĐANG CÓ: +1 tích cực, −1 tiêu cực, 0 trung tính.

    Chỉ báo trả None thì KHÔNG bỏ phiếu — vắng mặt, không phải phiếu trắng.
    """
    votes: dict[str, int] = {}
    r = a.get("rsi14")
    if r is not None:
        votes["rsi"] = 1 if r > 55 else (-1 if r < 45 else 0)
    m = a.get("macd")
    if m is not None and m.get("hist") is not None:
        votes["macd"] = 1 if m["hist"] > 0 else (-1 if m["hist"] < 0 else 0)
    return votes

"""Đo ĐỘ ĐẦY ĐỦ và ĐỘ MỚI của dữ liệu mà một quyết định thực sự dựa vào.

Vì sao cần — bằng chứng chứ không phải lo xa: cả **13/13 quyết định** trong
`data/decisions.jsonl` (20/7 → 10/8) đều ghi đúng một con số `confidence: 92`
và `data_quality: GOOD`. Không kỳ nào khác kỳ nào, kể cả những kỳ mà:

- `gold.ring_sell` (giá vàng nhẫn trong nước) ngừng thu thập từ **22/7**;
- `data/normalized/xuan_trieu_gold_history.csv` — nguồn DUY NHẤT của
  `gold/indicators.py` — chỉ có **1 dòng, ngày 18/7**, nên mọi chỉ báo trả
  `None` và `trend_label()` trả `TRUNG_TINH` vì không có gì để tính;
- `data/history.jsonl` cũ 4 ngày.

Lý do 92 là hằng số: `DecisionInput.data_completeness_pct` và
`data_freshness_score` mặc định **100.0** và **không caller nào truyền giá trị
khác** — 45% trọng số điểm tin cậy là số cứng. Nhánh hạ cấp chất lượng
(`data_quality = "FAIR"` khi hai chỉ số này < 80) vì thế không bao giờ chạy
được. Điểm tin cậy đang là phép cộng, không phải bằng chứng.

Module này đo hai chỉ số đó từ dữ liệu thật trên đĩa.

Ba quyết định thiết kế, nêu rõ để về sau đọc lại còn cãi được:

1. **Ngưỡng tuổi dùng lại đúng ngưỡng của health check**, không đặt ngưỡng mới.
   Tươi trong ngưỡng = 100; giảm TUYẾN TÍNH về 0 ở mốc `STALE_ESCALATE_FACTOR`
   lần ngưỡng — cùng mốc mà health check leo thang WARN → FAIL. Một hệ thống
   không nên có hai định nghĩa "quá cũ".
2. **Freshness lấy MIN trên các nguồn TRỌNG YẾU, không lấy trung bình.** Trung
   bình cho phép một nguồn tươi che một nguồn mục. Nguồn không trọng yếu (đối
   chiếu, tham khảo) có cũ thì ghi chú rõ nhưng không kéo điểm — điểm phải phản
   ánh đúng thứ quyết định phụ thuộc vào.
3. **Thiếu hẳn ≠ cũ.** Thiếu tính vào `completeness`, cũ tính vào `freshness`.
   Trừ một lần vào đúng một chỗ, không phạt chồng.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent

# Trễ quá ngưỡng bao nhiêu LẦN thì coi như hết giá trị (điểm 0). Dùng chung với
# scripts/health_check.py — nó import hằng số này để hai nơi không trôi khỏi nhau.
STALE_ESCALATE_FACTOR = 3

# Tuổi tối đa của một nến EOD trước khi coi là cũ. 4 ngày lịch chứ không phải 1:
# giá đóng cửa thứ Sáu đọc vào sáng thứ Hai đã 3 ngày tuổi mà vẫn là phiên gần
# nhất — ngưỡng phải nuốt được một cuối tuần bình thường.
#
# Hằng số này là ĐỊNH NGHĨA DUY NHẤT của "EOD quá cũ": `scripts/health_check.py`
# import nó thay vì viết lại số 4, đúng nguyên tắc đã nêu ở đầu module — một hệ
# thống không nên có hai định nghĩa "quá cũ". Giới hạn phải nói thẳng: không có
# lịch nghỉ lễ, nên một kỳ nghỉ Tết dài sẽ làm dữ liệu trông cũ hơn thực tế. Sai
# theo hướng thận trọng (khuyên ít đi), không theo hướng nguy hiểm.
EOD_MAX_AGE_DAYS = 4


@dataclass
class Source:
    """Một nguồn dữ liệu mà quyết định dựa vào."""

    name: str
    as_of: Optional[date]  # None = KHÔNG có dữ liệu nào (thiếu hẳn, khác với cũ)
    max_age_days: int
    critical: bool = True  # False = nguồn đối chiếu, cũ thì ghi chú chứ không kéo điểm
    note: str = ""

    def age_days(self, today: date) -> Optional[int]:
        return None if self.as_of is None else (today - self.as_of).days

    def freshness(self, today: date) -> Optional[float]:
        """100 khi còn trong ngưỡng, giảm tuyến tính về 0 ở mốc leo thang.

        Trả None khi thiếu hẳn — thiếu không phải "cũ vô hạn", nó là chuyện
        khác và được tính ở completeness.
        """
        age = self.age_days(today)
        if age is None:
            return None
        if age <= self.max_age_days:
            return 100.0
        limit = self.max_age_days * STALE_ESCALATE_FACTOR
        if age >= limit:
            return 0.0
        return round((limit - age) / (limit - self.max_age_days) * 100, 1)


@dataclass
class Assessment:
    completeness_pct: float
    freshness_score: float
    missing: list[str] = field(default_factory=list)
    missing_critical: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)
    binding: Optional[str] = None  # nguồn ép freshness xuống thấp nhất
    notes: list[str] = field(default_factory=list)

    @property
    def data_stale(self) -> bool:
        """Đủ cũ để KHÔNG nên tin quyết định — một nguồn trọng yếu đã về 0 điểm."""
        return self.freshness_score <= 0.0

    @property
    def data_missing_critical(self) -> bool:
        return bool(self.missing_critical)

    def explain(self) -> str:
        """Một câu nói vì sao điểm như vậy — con số không kèm lý do thì lại
        thành một con số 92 nữa."""
        bits = [f"đầy đủ {self.completeness_pct:.0f}/100", f"độ mới {self.freshness_score:.0f}/100"]
        if self.binding and self.freshness_score < 100:
            bits.append(f"bị ghìm bởi {self.binding}")
        if self.missing:
            bits.append("thiếu: " + ", ".join(self.missing))
        return "Chất lượng dữ liệu: " + " · ".join(bits)


def assess(sources: Sequence[Source], today: Optional[date] = None) -> Assessment:
    """Chấm điểm một bộ nguồn. Bộ rỗng trả 0 điểm chứ không trả 100.

    Không có nguồn nào để kiểm tra là lý do để KHÔNG tin, không phải lý do để
    tin tuyệt đối — mặc định 100 khi rỗng chính là cái bẫy đang phải sửa.
    """
    today = today or date.today()
    if not sources:
        return Assessment(0.0, 0.0, notes=["không khai báo nguồn nào để kiểm tra"])

    present = [s for s in sources if s.as_of is not None]
    missing = [s.name for s in sources if s.as_of is None]
    missing_critical = [s.name for s in sources if s.as_of is None and s.critical]
    completeness = len(present) / len(sources) * 100

    scored = [(s, s.freshness(today)) for s in present if s.critical]
    if scored:
        binding_src, freshness = min(scored, key=lambda p: p[1])
        binding = f"{binding_src.name} (cũ {binding_src.age_days(today)} ngày, ngưỡng {binding_src.max_age_days})"
    else:
        # Không còn nguồn trọng yếu nào có dữ liệu — không có cơ sở nào để chấm
        # độ mới, và đó là tin xấu chứ không phải tin trung tính.
        freshness, binding = 0.0, None

    stale, notes = [], []
    for s in present:
        age = s.age_days(today)
        if age is not None and age > s.max_age_days:
            label = f"{s.name}: cũ {age} ngày (ngưỡng {s.max_age_days})"
            stale.append(label)
            if not s.critical:
                notes.append(f"{label} — nguồn đối chiếu, không kéo điểm nhưng mất khả năng kiểm chứng chéo")
        if s.note:
            notes.append(f"{s.name}: {s.note}")

    return Assessment(
        completeness_pct=round(completeness, 1), freshness_score=float(freshness),
        missing=missing, missing_critical=missing_critical, stale=stale,
        binding=binding, notes=notes,
    )


# --- Bộ nguồn thật cho quyết định VÀNG --------------------------------------

def gold_sources(history: Optional[Sequence[dict]] = None) -> list[Source]:
    """Đúng những nguồn mà một quyết định vàng đang dựa vào, không thêm bớt.

    Trọng yếu:
      - XAU/USD từ snapshot: đầu vào định giá vàng của `scripts/networth.py`,
        đồng thời là chuỗi mà `gold/indicators.py` đo xu hướng
      - lịch sử hiệu chuẩn giá tiệm: neo MỨC giá tiệm (hệ số quy đổi từ giá
        thế giới sang giá nhẫn thực tế) — sai ở đây thì sai toàn bộ tỷ trọng
    Đối chiếu (không kéo điểm):
      - giá nhẫn trong nước từ snapshot: dùng để kiểm chứng mô hình quy đổi,
        không phải đầu vào định giá chính
    """
    hist = list(history) if history is not None else _load_history()
    return [
        Source("XAU/USD (history.jsonl)", _latest_gold_field(hist, "xauusd"), 2, critical=True),
        Source("Lịch sử giá tiệm (hiệu chuẩn)", _latest_calibration_date(), 30, critical=True,
               note=_calibration_note()),
        Source("Giá nhẫn trong nước (history.jsonl)", _latest_gold_field(hist, "ring_sell"), 7,
               critical=False),
    ]


def assess_gold(history: Optional[Sequence[dict]] = None, today: Optional[date] = None) -> Assessment:
    return assess(gold_sources(history), today)


def _load_history() -> list[dict]:
    path = ROOT / "data" / "history.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _latest_gold_field(history: Sequence[dict], field_name: str) -> Optional[date]:
    dates = [
        _parse(row.get("date"))
        for row in history
        if isinstance(row.get("gold"), dict) and row["gold"].get(field_name)
    ]
    real = [d for d in dates if d]
    return max(real) if real else None


def _latest_calibration_date() -> Optional[date]:
    path = ROOT / "data" / "normalized" / "xuan_trieu_gold_history.csv"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        dates = [_parse(r.get("date")) for r in csv.DictReader(f)]
    real = [d for d in dates if d]
    return max(real) if real else None


def _calibration_note() -> str:
    """Số MẪU của file hiệu chuẩn, vì tuổi không nói hết vấn đề.

    Đây là nguồn neo MỨC giá tiệm. Với 1 mẫu, con số "vàng chiếm 76% tài sản"
    — thứ kích hoạt toàn bộ khuyến nghị CHỐT BỚT — dựa trên đúng một tấm ảnh
    bảng giá. `gold/calibration.py` đo được BIÊN từ 11 quan sát, nhưng MỨC thì
    chỉ ảnh bảng giá mới siết được.
    """
    path = ROOT / "data" / "normalized" / "xuan_trieu_gold_history.csv"
    if not path.exists():
        return ""
    with path.open(encoding="utf-8") as f:
        n = sum(1 for _ in csv.DictReader(f))
    if n >= 5:
        return ""
    return (f"chỉ {n} mẫu — MỨC giá tiệm neo vào đúng {n} ảnh bảng giá; "
            "gửi ảnh mới để siết (biên đã đo được từ 11 quan sát, riêng mức thì chưa)")


def _parse(value: object) -> Optional[date]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


# --- Bộ nguồn thật cho quyết định CỔ PHIẾU ----------------------------------
#
# Vì sao cần, bằng chứng đo được ngày 29/08/2026 trên chính repo này:
#
#   scripts/health_check.py  → "❌ EOD VCB: mới nhất 2026-08-10 — đã 19 ngày,
#                               gấp >3× ngưỡng 4 ngày. Automation đã ngừng chạy."
#   scripts/run_morning.py   → "CTD 62.40 (EOD 2026-08-10) → MUA THĂM DÒ
#                               (tin cậy 80/100) · Mua tối đa 81 tr ·
#                               cắt lỗ dưới 53.61 · mục tiêu 93.00"
#
# Cùng một file, cùng một lần chạy: một nửa hệ thống gọi dữ liệu là HỎNG, nửa
# kia dựng trên nó một lệnh mua kèm mức cắt lỗ. Trong khi ĐÚNG kỳ đó, vàng —
# đọc từ snapshot cũ y hệt — bị Risk Officer chặn thành CHƯA ĐỦ DỮ LIỆU
# (30/100). Cơ chế chặn có sẵn và chạy đúng; nhánh cổ phiếu chỉ đơn giản không
# đi qua nó: `equity/signals.py::decide_for` ghi cứng
# `data_freshness_score=100.0` và dựng `RiskContext` không có `data_stale`.
#
# Mức cắt lỗ mới là chỗ nguy hiểm nhất, không phải nhãn hành động: 53.61 được
# tính từ vùng hỗ trợ của 19 ngày trước. Sau ngần ấy phiên không quan sát, giá
# có thể đã ở bất kỳ đâu — đó là một con số chính xác đến hai chữ số thập phân
# nói về một thị trường mà hệ thống không còn nhìn thấy.

def equity_sources(ticker: str, last_eod: Optional[date] = None) -> list[Source]:
    """Nguồn mà một quyết định cổ phiếu đang dựa vào — chuỗi EOD của chính mã đó.

    `last_eod` truyền từ tín hiệu đã nạp (`TickerSignal.last_date`) chứ không
    đọc lại đĩa, để hai chỗ không thể lệch nhau — cùng nguyên tắc mà
    `run_gold_decision()` đang áp cho chuỗi vàng. Chỉ khi caller không có sẵn
    tín hiệu thì mới rơi về đọc file.

    Chỉ khai báo chuỗi EOD, không nhét thêm nguồn cho đủ bộ: giá, RSI/MACD,
    hỗ trợ/kháng cự và mức cắt lỗ đều rút ra từ đúng chuỗi này. Giá mục tiêu
    CTCK có vấn đề riêng của nó (độ phân tán, không rõ ngày phát hành) và đã
    được `equity/target_prices.py` xử lý ở chỗ khác — không phạt chồng.
    """
    t = ticker.upper()
    as_of = last_eod if last_eod is not None else _latest_eod_date(t)
    return [Source(f"EOD {t} (data/eod/{t}.csv)", as_of, EOD_MAX_AGE_DAYS, critical=True)]


def assess_equity(ticker: str, last_eod: Optional[date] = None,
                  today: Optional[date] = None) -> Assessment:
    return assess(equity_sources(ticker, last_eod), today)


def _latest_eod_date(ticker: str) -> Optional[date]:
    path = ROOT / "data" / "eod" / f"{ticker.upper()}.csv"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        dates = [_parse(r.get("date")) for r in csv.DictReader(f)]
    real = [d for d in dates if d]
    return max(real) if real else None

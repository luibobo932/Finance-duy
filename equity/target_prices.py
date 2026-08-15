"""Biên an toàn từ giá mục tiêu CTCK — thứ khiến nhánh MUA THĂM DÒ chạy được.

Lỗi cấu trúc trước module này: `derive_initial_action` cho equity chỉ ra
`BUY_SMALL` khi `margin_of_safety_pct > 20`, mà **không caller production nào
truyền trường đó** (grep toàn repo trả về rỗng). Nghĩa là nhánh cổ phiếu
**về mặt cấu trúc không thể khuyến nghị mua**, bất kể dữ liệu tốt tới đâu —
mọi mã vĩnh viễn dừng ở ĐỨNG NGOÀI. Một hệ thống theo dõi cổ phiếu mà không
bao giờ nói được "mua" thì chỉ là một cái đồng hồ báo giá.

**Đây là phán đoán ĐI MƯỢN, không phải giá trị đo được.** Giá mục tiêu là ý
kiến của công ty chứng khoán; dự án này không đo được thành tích dự báo của
họ, và họ có động cơ nghề nghiệp riêng. Nên ba ràng buộc cứng:

1. **Dùng mục tiêu THẤP NHẤT**, không dùng trung bình và tuyệt đối không dùng
   cao nhất. Với VCB, dải mục tiêu là 61,9–80,7 — biên an toàn tính theo mức
   thấp nhất là 2,6%, theo mức cao nhất là 25,3%. Cùng một mã, hai kết luận
   trái ngược. Chọn mức thấp nhất là chọn kết luận khó chịu hơn khi không có
   cơ sở để tin bên nào.
2. **Độ phân tán được báo cáo.** Các CTCK lệch nhau 30% thì bản thân sự lệch
   đó là thông tin: không ai thực sự biết.
3. **Mục tiêu quá cũ bị loại.** Giá mục tiêu 3 tháng tuổi trong một thị trường
   đã đi 15% là con số của một thế giới khác.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent
VALUATIONS_PATH = ROOT / "data" / "valuations.jsonl"

# Mục tiêu cũ hơn mức này bị loại khỏi tính toán. 180 ngày ≈ 2 quý: qua 2 kỳ
# BCTC thì luận điểm định giá cũ gần như chắc chắn đã phải viết lại.
MAX_TARGET_AGE_DAYS = 180
# Mục tiêu KHÔNG rõ ngày: vẫn dùng nhưng đánh dấu, vì không kiểm được độ cũ.
UNDATED_NOTE = "không rõ ngày phát hành — không kiểm được độ cũ"

# Các CTCK lệch nhau quá mức này thì bản thân sự lệch là tín hiệu "không ai
# thực sự biết", và biên an toàn tính ra kém tin cậy hẳn.
HIGH_DISPERSION_PCT = 25.0


@dataclass
class Target:
    ticker: str
    target_nghin_dong: float
    house: str
    rating: Optional[str] = None
    as_of: Optional[date] = None
    source: str = ""

    def age_days(self, today: Optional[date] = None) -> Optional[int]:
        return None if self.as_of is None else ((today or date.today()) - self.as_of).days


@dataclass
class ValuationView:
    ticker: str
    price: float
    targets: list[Target]
    excluded: list[str]

    @property
    def usable(self) -> list[Target]:
        return self.targets

    @property
    def lowest(self) -> Optional[Target]:
        """Mục tiêu THẤP NHẤT — cơ sở duy nhất để tính biên an toàn."""
        return min(self.targets, key=lambda t: t.target_nghin_dong) if self.targets else None

    @property
    def highest(self) -> Optional[Target]:
        return max(self.targets, key=lambda t: t.target_nghin_dong) if self.targets else None

    @property
    def margin_of_safety_pct(self) -> Optional[float]:
        """(mục tiêu thấp nhất − giá) / mục tiêu thấp nhất, theo %."""
        low = self.lowest
        if low is None or not low.target_nghin_dong or not self.price:
            return None
        return (low.target_nghin_dong - self.price) / low.target_nghin_dong * 100

    @property
    def dispersion_pct(self) -> Optional[float]:
        """Mức lệch giữa mục tiêu cao nhất và thấp nhất, tính trên mức thấp nhất."""
        lo, hi = self.lowest, self.highest
        if lo is None or hi is None or not lo.target_nghin_dong:
            return None
        return (hi.target_nghin_dong - lo.target_nghin_dong) / lo.target_nghin_dong * 100

    @property
    def high_dispersion(self) -> bool:
        d = self.dispersion_pct
        return d is not None and d >= HIGH_DISPERSION_PCT

    def note(self) -> str:
        """Câu giải thích biên an toàn đến từ đâu — và nó đáng tin tới mức nào."""
        if not self.targets:
            return "Chưa có giá mục tiêu nào dùng được — không tính được biên an toàn."
        low = self.lowest
        assert low is not None
        bits = [f"Biên an toàn {self.margin_of_safety_pct:.1f}% tính theo mục tiêu THẤP NHẤT "
                f"{low.target_nghin_dong:,.1f} ({low.house})"]
        if len(self.targets) > 1:
            hi = self.highest
            assert hi is not None
            bits.append(f"Dải mục tiêu {low.target_nghin_dong:,.1f}–{hi.target_nghin_dong:,.1f} "
                        f"từ {len(self.targets)} CTCK (lệch {self.dispersion_pct:.0f}%)")
        if self.high_dispersion:
            bits.append("⚠️ Các CTCK lệch nhau lớn — bản thân điều đó là tín hiệu "
                        "không ai thực sự biết, biên an toàn kém tin cậy")
        if self.excluded:
            bits.append("Đã loại: " + "; ".join(self.excluded))
        bits.append("Đây là phán đoán ĐI MƯỢN từ CTCK, không phải giá trị đo được — "
                    "dự án không đo được thành tích dự báo của họ")
        return ". ".join(bits) + "."


def load_targets(path: Optional[Path] = None) -> list[Target]:
    p = path or VALUATIONS_PATH
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        out.append(Target(
            ticker=str(d["ticker"]).upper(),
            target_nghin_dong=float(d["target_nghin_dong"]),
            house=str(d.get("house") or "?"),
            rating=d.get("rating"),
            as_of=_parse(d.get("as_of")),
            source=str(d.get("source") or ""),
        ))
    return out


def view_for(
    ticker: str, price: float, *, today: Optional[date] = None,
    targets: Optional[Sequence[Target]] = None,
) -> ValuationView:
    """Gom giá mục tiêu của 1 mã, loại mục tiêu quá cũ, và nêu rõ đã loại gì."""
    today = today or date.today()
    all_t = list(targets) if targets is not None else load_targets()
    mine = [t for t in all_t if t.ticker == ticker.upper()]
    keep, excluded = [], []
    for t in mine:
        age = t.age_days(today)
        if age is not None and age > MAX_TARGET_AGE_DAYS:
            excluded.append(f"{t.house} {t.target_nghin_dong:,.1f} (cũ {age} ngày)")
            continue
        keep.append(t)
    return ValuationView(ticker.upper(), price, keep, excluded)


def undated_warning(view: ValuationView) -> str:
    """Cảnh báo riêng cho mục tiêu không rõ ngày — không loại, nhưng phải nói."""
    undated = [t.house for t in view.targets if t.as_of is None]
    if not undated:
        return ""
    return f"{len(undated)}/{len(view.targets)} mục tiêu {UNDATED_NOTE} ({', '.join(undated)})"


def _parse(value: object) -> Optional[date]:
    if isinstance(value, str):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None

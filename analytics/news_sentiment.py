"""Đo mức độ tiêu cực của tin tức chứng khoán — điều kiện thứ hai của tín hiệu gom hàng.

Đây là phần dễ tự lừa mình nhất trong cả hệ thống, nên ba nguyên tắc được cài
cứng vào code chứ không để cho người dùng nhớ:

1. **Im lặng ≠ tin tốt, mà cũng ≠ tin xấu.** Không có nhật ký tin tức thì
   `measurable=False`, và `equity/market_regime.accumulation_signal` biến điều
   đó thành CHƯA ĐO ĐƯỢC — không phải "điều kiện chưa đạt".
2. **Vài tin không phải "tràn ngập".** Dưới `min_headlines` tin trong cửa sổ
   thì không kết luận. Ba tiêu đề xấu tìm được sau khi đã tin rằng thị trường
   xấu là thiên kiến xác nhận, không phải phép đo.
3. **Nhãn tự động phải tự khai là tự động.** `suggest_sentiment()` chỉ đoán
   theo từ khoá; mỗi bản ghi lưu `sentiment_source` = auto/manual để sau này
   còn kiểm lại được tín hiệu đã dựa trên cái gì.

Nguồn dữ liệu: `data/market_news.jsonl`, mỗi dòng một tiêu đề. Chưa có nguồn
tự động (xem README: tin tức là một trong các mảng phải nhập tay hoặc lấy qua
WebSearch trong phiên chat) — `scripts/news_log.py` là cửa ghi vào.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
NEWS_PATH = ROOT / "data" / "market_news.jsonl"

NEGATIVE = "NEGATIVE"
POSITIVE = "POSITIVE"
NEUTRAL = "NEUTRAL"
VALID_SENTIMENTS = (NEGATIVE, POSITIVE, NEUTRAL)

# Từ khoá tiếng Việt thường gặp trên báo chứng khoán. Danh sách này là GỢI Ý
# cho người nhập, không phải mô hình ngôn ngữ — nó sẽ bỏ sót và bắt nhầm.
NEGATIVE_KEYWORDS = [
    "bán tháo", "lao dốc", "giảm sàn", "sàn hàng loạt", "rơi tự do", "bốc hơi",
    "mất mốc", "thủng đáy", "đỏ lửa", "tháo chạy", "khủng hoảng", "suy thoái",
    "call margin", "margin call", "giải chấp", "rút vốn", "bán ròng",
    "thao túng", "khởi tố", "bắt tạm giam", "điều tra", "vỡ nợ", "trái phiếu",
    "hủy niêm yết", "thua lỗ", "cắt lỗ", "hoảng loạn", "tiêu cực", "ảm đạm",
    "thanh khoản cạn", "mất thanh khoản", "tin đồn", "đình chỉ",
]
POSITIVE_KEYWORDS = [
    "bứt phá", "tăng trần", "kỷ lục", "đỉnh lịch sử", "hưng phấn", "khởi sắc",
    "dòng tiền đổ", "mua ròng", "nâng hạng", "vượt đỉnh", "bùng nổ", "lãi kỷ lục",
    "khối ngoại mua", "phục hồi", "tích cực", "lập đỉnh",
]


def suggest_sentiment(headline: str) -> tuple[str, list[str]]:
    """Đoán nhãn theo từ khoá. Trả (nhãn, từ khoá đã khớp) để người nhập soát lại.

    Hoà (khớp cả hai bên bằng nhau) → NEUTRAL: không ưu tiên bên nào, vì ưu
    tiên tiêu cực sẽ khiến chính điều kiện mình muốn kiểm chứng tự đạt.
    """
    text = (headline or "").lower()
    neg = [k for k in NEGATIVE_KEYWORDS if k in text]
    pos = [k for k in POSITIVE_KEYWORDS if k in text]
    if len(neg) > len(pos):
        return NEGATIVE, neg
    if len(pos) > len(neg):
        return POSITIVE, pos
    return NEUTRAL, neg + pos


def load_news(path: Optional[Path] = None) -> list[dict]:
    """Đọc data/market_news.jsonl. Dòng hỏng thì bỏ qua, không làm sập bản tin."""
    p = path or NEWS_PATH
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and rec.get("date"):
            out.append(rec)
    return out


def append_news(rec: dict, path: Optional[Path] = None) -> None:
    p = path or NEWS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


@dataclass
class NewsSentiment:
    window_days: int
    total: int = 0
    negative: int = 0
    positive: int = 0
    neutral: int = 0
    newest_date: Optional[str] = None
    age_days: Optional[int] = None
    is_stale: bool = False
    enough_headlines: bool = False
    auto_labeled: int = 0
    sources: list[str] = field(default_factory=list)
    threshold_ratio: float = 0.6

    @property
    def negative_ratio(self) -> Optional[float]:
        if not self.total:
            return None
        return round(self.negative / self.total, 2)

    @property
    def measurable(self) -> bool:
        """Đủ điều kiện để NÓI BẤT CỨ ĐIỀU GÌ về tâm lý tin tức."""
        return self.enough_headlines and not self.is_stale

    @property
    def overwhelming_negative(self) -> Optional[bool]:
        if not self.measurable:
            return None
        return (self.negative_ratio or 0) >= self.threshold_ratio

    @property
    def reason(self) -> str:
        """Vì sao chưa đo được — câu này đi thẳng vào bản tin nên phải hành động được."""
        if self.total == 0:
            return (f"chưa có tin nào trong {self.window_days} ngày gần nhất "
                    "(`data/market_news.jsonl`) — ghi bằng `scripts/news_log.py add`")
        if not self.enough_headlines:
            return (f"mới có {self.total} tin trong {self.window_days} ngày, "
                    "chưa đủ để gọi là 'tràn ngập'")
        if self.is_stale:
            return (f"tin mới nhất là {self.newest_date} ({self.age_days} ngày trước) "
                    "— nhật ký tin tức đã cũ, im lặng không phải là 'không có tin xấu'")
        return "đo được"

    def evidence(self) -> str:
        ratio = self.negative_ratio
        s = (f"{self.negative}/{self.total} tin tiêu cực trong {self.window_days} ngày "
             f"({(ratio or 0) * 100:.0f}%, cần ≥ {self.threshold_ratio * 100:.0f}%)")
        if self.auto_labeled:
            s += f" — {self.auto_labeled} tin gán nhãn tự động theo từ khoá"
        return s


def measure(entries: Optional[list[dict]] = None, *, today: Optional[str] = None,
            rules: Optional[dict[str, Any]] = None) -> NewsSentiment:
    """Đếm tin theo nhãn trong cửa sổ `window_days` tính lùi từ `today`.

    `today` mặc định là NGÀY HỆ THỐNG, nhưng caller trong bản tin nên truyền
    ngày của snapshot mới nhất để phép đo bám ngày dữ liệu — cùng quy ước với
    `scripts/alerts.py::_today()`.
    """
    if rules is None:
        from equity.market_regime import load_rules

        rules = load_rules()
    cfg = (rules or {}).get("news", {}) or {}
    window_days = int(cfg.get("window_days", 7))
    min_headlines = int(cfg.get("min_headlines", 5))
    max_age_days = int(cfg.get("max_age_days", 3))
    ratio_min = float(cfg.get("negative_ratio_min", 0.6))

    entries = load_news() if entries is None else entries
    ref = date.fromisoformat(today) if today else date.today()
    cutoff = ref - timedelta(days=window_days)

    in_window, dates = [], []
    for e in entries:
        try:
            d = date.fromisoformat(str(e.get("date"))[:10])
        except ValueError:
            continue
        dates.append(d)
        if cutoff <= d <= ref:
            in_window.append(e)

    counts = {NEGATIVE: 0, POSITIVE: 0, NEUTRAL: 0}
    auto = 0
    sources: list[str] = []
    for e in in_window:
        label = str(e.get("sentiment", "")).upper()
        if label not in VALID_SENTIMENTS:
            label = NEUTRAL
        counts[label] += 1
        if str(e.get("sentiment_source", "")).lower() == "auto":
            auto += 1
        src = e.get("source")
        if src and src not in sources:
            sources.append(str(src))

    newest = max(dates) if dates else None
    age = (ref - newest).days if newest else None
    total = len(in_window)
    return NewsSentiment(
        window_days=window_days,
        total=total,
        negative=counts[NEGATIVE],
        positive=counts[POSITIVE],
        neutral=counts[NEUTRAL],
        newest_date=newest.isoformat() if newest else None,
        age_days=age,
        is_stale=(age is None or age > max_age_days),
        enough_headlines=total >= min_headlines,
        auto_labeled=auto,
        sources=sources,
        threshold_ratio=ratio_min,
    )

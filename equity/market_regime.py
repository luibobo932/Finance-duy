"""VN-Index đang ở đâu so với LỊCH SỬ của chính nó — vùng phân phối hay vùng gom.

Vì sao module này tồn tại: toàn bộ phần cổ phiếu của hệ thống cho tới nay nhìn
TỪNG MÃ (`equity/signals.py` → RSI/MACD/hỗ trợ/kháng cự của VCB, CTD), không có
gì nhìn THỊ TRƯỜNG. Mà quyết định lớn nhất của một danh mục đang cầm 100% tiền
mặt + vàng không phải "mua mã nào" — nó là "đã đến lúc mua chưa". Câu đó chỉ
trả lời được ở tầng chỉ số.

Hai thước đo, phải dùng CÙNG NHAU:

1. **Drawdown từ đỉnh** — không bị lệch bởi tăng trưởng dài hạn, nhưng một
   mình thì không đủ: đỉnh bong bóng giảm 30% vẫn có thể đắt hơn mọi phiên của
   ba năm trước đó.
2. **Percentile trong cửa sổ ~3 năm** — trả lời "rẻ so với chính nó gần đây".
   Một mình cũng không đủ, vì thị trường đi ngang nhiều năm sẽ liên tục cho
   percentile thấp mà chẳng có đợt bán tháo nào.

Cả hai đo trên `data/eod/VNINDEX.csv`. Chuỗi ngắn hơn `min_sessions_for_history`
thì module trả về **CHƯA ĐO ĐƯỢC**, không phải một nhãn vùng nghe cho có —
`data/history.jsonl` chỉ có 19 snapshot (3 tuần) và dùng nó để kết luận "đáy
lịch sử" sẽ là đúng cái lỗi mà `analytics/ta_core.trend_from_indicators` đã
được viết ra để chặn: nói chắc về điều hệ thống không biết.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

from analytics.ta_core import rsi, sma

ROOT = Path(__file__).resolve().parent.parent
EOD_DIR = ROOT / "data" / "eod"
STATE_PATH = ROOT / "data" / "market_regime_state.json"

INDEX_SYMBOL = "VNINDEX"

# Nhãn vùng — xếp theo mức chiết khấu, KHÔNG phải theo mức độ hấp dẫn.
ZONE_PHAN_PHOI = "PHAN_PHOI"       # sát đỉnh sau một đợt tăng dài
ZONE_BINH_THUONG = "BINH_THUONG"
ZONE_DIEU_CHINH = "DIEU_CHINH"     # ≥ correction_drawdown_pct
ZONE_GIAM_SAU = "GIAM_SAU"         # ≥ watch_drawdown_pct
ZONE_VUNG_GOM = "VUNG_GOM"         # ≥ deep_drawdown_pct

ZONE_VI = {
    ZONE_PHAN_PHOI: "VÙNG PHÂN PHỐI (sát đỉnh sau đợt tăng dài)",
    ZONE_BINH_THUONG: "BÌNH THƯỜNG",
    ZONE_DIEU_CHINH: "ĐIỀU CHỈNH",
    ZONE_GIAM_SAU: "GIẢM SÂU — theo dõi sát",
    ZONE_VUNG_GOM: "VÙNG GOM HÀNG (chiết khấu sâu so với lịch sử)",
}

# Trạng thái tín hiệu gom hàng.
STATUS_CHUA_DO_DUOC = "CHUA_DO_DUOC"
STATUS_CHUA_DEN_LUC = "CHUA_DEN_LUC"
STATUS_THEO_DOI_SAT = "THEO_DOI_SAT"
STATUS_VUNG_GOM = "VUNG_GOM"

STATUS_VI = {
    STATUS_CHUA_DO_DUOC: "CHƯA ĐO ĐƯỢC",
    STATUS_CHUA_DEN_LUC: "CHƯA ĐẾN LÚC",
    STATUS_THEO_DOI_SAT: "THEO DÕI SÁT",
    STATUS_VUNG_GOM: "🟢 ĐỦ ĐIỀU KIỆN GOM HÀNG",
}


# --- Nạp cấu hình + dữ liệu --------------------------------------------------


def load_rules(path: Optional[Path] = None) -> dict[str, Any]:
    """Ngưỡng từ config/market_regime.yaml. Không viết chết số nào trong .py."""
    import yaml

    p = path or (ROOT / "config" / "market_regime.yaml")
    if not p.exists():
        raise FileNotFoundError(f"Thiếu file cấu hình: {p}")
    with p.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_index_eod(symbol: str = INDEX_SYMBOL, path: Optional[Path] = None) -> list[dict]:
    """Đọc data/eod/<CHỈ_SỐ>.csv. Thiếu file → [] (không dựng dữ liệu giả)."""
    p = path or (EOD_DIR / f"{symbol.upper()}.csv")
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --- Phép đo thuần túy -------------------------------------------------------


def drawdown_from_peak(closes: list[float]) -> Optional[dict]:
    """Đỉnh cao nhất của chuỗi và mức giảm hiện tại so với đỉnh đó.

    `sessions_since_peak` là chiều DÀI của đợt giảm — đáy sâu mà mới rơi 5
    phiên khác hẳn đáy sâu đã bào mòn 8 tháng, dù % giảm bằng nhau.
    """
    if not closes:
        return None
    peak = max(closes)
    peak_idx = len(closes) - 1 - closes[::-1].index(peak)  # đỉnh GẦN NHẤT nếu trùng giá
    if peak <= 0:
        return None
    return {
        "peak": peak,
        "peak_index": peak_idx,
        "drawdown_pct": round((peak - closes[-1]) / peak * 100, 2),
        "sessions_since_peak": len(closes) - 1 - peak_idx,
    }


def percentile_rank(closes: list[float], window: int) -> Optional[float]:
    """% số phiên trong `window` phiên gần nhất có giá đóng cửa THẤP HƠN hiện tại.

    0 = thấp nhất cửa sổ, 100 = cao nhất. Cửa sổ tự co lại theo dữ liệu đang
    có; caller phải công bố số phiên thật đã dùng, đừng để người đọc tưởng là
    3 năm khi mới có 8 tháng.
    """
    if len(closes) < 2:
        return None
    w = closes[-window:] if window > 0 else closes
    if len(w) < 2:
        return None
    lower = sum(1 for c in w[:-1] if c < w[-1])
    return round(lower / (len(w) - 1) * 100, 1)


def gain_pct(closes: list[float], lookback: int) -> Optional[float]:
    """% thay đổi so với `lookback` phiên trước — đo "đợt tăng dài" của vùng phân phối."""
    if len(closes) <= lookback or lookback <= 0:
        return None
    base = closes[-1 - lookback]
    if base <= 0:
        return None
    return round((closes[-1] - base) / base * 100, 2)


def making_new_low(closes: list[float], lookback: int) -> Optional[bool]:
    """Phiên gần nhất có phải đáy của `lookback` phiên gần đây không.

    True = dao vẫn đang rơi. Đây là lý do tín hiệu gom hàng đi kèm kế hoạch
    giải ngân từng bậc chứ không phải một lệnh mua duy nhất.
    """
    if len(closes) < lookback + 1 or lookback <= 0:
        return None
    return closes[-1] <= min(closes[-(lookback + 1):])


# --- Ảnh chụp bối cảnh -------------------------------------------------------


@dataclass
class RegimeSnapshot:
    sessions: int
    last_date: Optional[str] = None
    close: Optional[float] = None
    peak: Optional[float] = None
    peak_date: Optional[str] = None
    drawdown_pct: Optional[float] = None
    sessions_since_peak: Optional[int] = None
    percentile: Optional[float] = None
    percentile_sessions: Optional[int] = None
    ma200: Optional[float] = None
    vs_ma200_pct: Optional[float] = None
    rsi14: Optional[float] = None
    gain_run_pct: Optional[float] = None
    making_new_low: Optional[bool] = None
    zone: Optional[str] = None          # None = CHƯA ĐO ĐƯỢC, khác hẳn BINH_THUONG
    enough_history: bool = False
    price_age_days: Optional[int] = None
    is_stale: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return self.close is not None

    @property
    def zone_vi(self) -> str:
        return ZONE_VI.get(self.zone or "", "CHƯA ĐO ĐƯỢC")

    def evidence(self) -> str:
        """Nhãn vùng đến từ đâu — nhãn không kèm căn cứ thì không phản biện được."""
        if not self.has_data:
            return (f"chưa có dữ liệu EOD cho {INDEX_SYMBOL} "
                    f"(`data/eod/{INDEX_SYMBOL}.csv`)")
        bits = [f"đo trên {self.sessions} phiên"]
        if self.drawdown_pct is not None and self.peak is not None:
            bits.append(f"giảm {self.drawdown_pct:.1f}% từ đỉnh {self.peak:,.2f}"
                        + (f" ({self.peak_date})" if self.peak_date else ""))
        if self.percentile is not None:
            bits.append(f"thấp hơn {100 - self.percentile:.0f}% số phiên trong "
                        f"{self.percentile_sessions} phiên gần nhất")
        if self.vs_ma200_pct is not None:
            vs = "trên" if self.vs_ma200_pct >= 0 else "dưới"
            bits.append(f"{vs} MA200 {abs(self.vs_ma200_pct):.1f}%")
        if self.rsi14 is not None:
            bits.append(f"RSI(14)={self.rsi14:.1f}")
        return ", ".join(bits)


def _age_days(last_date: Optional[str], today: Optional[str]) -> Optional[int]:
    """Số ngày từ phiên cuối tới `today`. None khi không đọc được ngày."""
    if not last_date:
        return None
    try:
        d = date.fromisoformat(str(last_date)[:10])
    except ValueError:
        return None
    ref = date.fromisoformat(today) if today else date.today()
    return (ref - d).days


def analyze(rows: Optional[list[dict]] = None, rules: Optional[dict] = None,
            today: Optional[str] = None) -> RegimeSnapshot:
    """Ảnh chụp bối cảnh VN-Index từ chuỗi EOD.

    Thiếu file, thiếu cột, hay chuỗi quá ngắn đều dẫn tới `zone=None`. Nhãn
    vùng chỉ xuất hiện khi có đủ phiên để nói câu "so với lịch sử" mà không
    nói quá.

    `today` mặc định là ngày hệ thống — dùng để đo độ CŨ của phiên cuối. File
    EOD quên cập nhật ba tuần vẫn cho ra đủ mọi con số đẹp đẽ; chỉ có mốc thời
    gian mới phân biệt được "đang ở đáy" với "đã từng ở đáy".
    """
    rules = rules or load_rules()
    cfg = rules.get("regime", {}) or {}
    rows = load_index_eod() if rows is None else rows
    if not rows:
        return RegimeSnapshot(sessions=0)
    try:
        closes = [float(r["close"]) for r in rows]
        dates = [str(r.get("date") or "") for r in rows]
    except (KeyError, ValueError, TypeError):
        return RegimeSnapshot(sessions=0, notes=["file EOD sai định dạng cột close"])
    if not closes:
        return RegimeSnapshot(sessions=0)

    min_sessions = int(cfg.get("min_sessions_for_history", 250))
    dd = drawdown_from_peak(closes) or {}
    window = int(cfg.get("percentile_window_sessions", 750))
    pct = percentile_rank(closes, window)
    ma200 = sma(closes, 200)
    peak_idx = dd.get("peak_index")

    snap = RegimeSnapshot(
        sessions=len(closes),
        last_date=dates[-1] or None,
        close=closes[-1],
        peak=dd.get("peak"),
        peak_date=(dates[peak_idx] or None) if peak_idx is not None else None,
        drawdown_pct=dd.get("drawdown_pct"),
        sessions_since_peak=dd.get("sessions_since_peak"),
        percentile=pct,
        percentile_sessions=min(len(closes), window) if pct is not None else None,
        ma200=ma200,
        vs_ma200_pct=(round((closes[-1] - ma200) / ma200 * 100, 2)
                      if ma200 else None),
        rsi14=rsi(closes),
        gain_run_pct=gain_pct(closes, int(cfg.get("strong_run_lookback_sessions", 250))),
        making_new_low=making_new_low(closes, int(cfg.get("new_low_lookback_sessions", 10))),
        enough_history=len(closes) >= min_sessions,
    )

    max_age = int(cfg.get("max_price_age_days", 5))
    snap.price_age_days = _age_days(snap.last_date, today)
    if snap.price_age_days is None:
        snap.is_stale = True
        snap.notes.append("không đọc được ngày của phiên cuối trong file EOD — "
                          "không xác nhận được dữ liệu còn mới")
    elif snap.price_age_days > max_age:
        snap.is_stale = True
        snap.notes.append(
            f"phiên cuối {snap.last_date} đã {snap.price_age_days} ngày trước "
            f"(quá {max_age} ngày) — cập nhật bằng "
            f"`scripts/fetch_eod.py {INDEX_SYMBOL} --index`")

    if not snap.enough_history:
        snap.notes.append(
            f"mới có {len(closes)} phiên, cần ≥ {min_sessions} phiên mới kết luận "
            "được 'so với lịch sử' — chưa gán nhãn vùng")
        return snap
    snap.zone = classify_zone(snap, cfg)
    return snap


def classify_zone(snap: RegimeSnapshot, cfg: dict) -> Optional[str]:
    """Nhãn vùng từ drawdown + percentile. None khi thiếu drawdown.

    VÙNG GOM đòi CẢ HAI: chiết khấu sâu từ đỉnh VÀ nằm trong nhóm phiên rẻ
    nhất của cửa sổ. Thiếu percentile (chuỗi quá ngắn) thì cao nhất chỉ tới
    GIẢM SÂU — không có chuyện thăng hạng nhờ thiếu dữ liệu.
    """
    dd = snap.drawdown_pct
    if dd is None:
        return None
    deep = float(cfg.get("deep_drawdown_pct", 30.0))
    watch = float(cfg.get("watch_drawdown_pct", 20.0))
    correction = float(cfg.get("correction_drawdown_pct", 10.0))
    low_pct_max = float(cfg.get("low_percentile_max", 20.0))

    if dd >= deep:
        if snap.percentile is not None and snap.percentile <= low_pct_max:
            return ZONE_VUNG_GOM
        return ZONE_GIAM_SAU
    if dd >= watch:
        return ZONE_GIAM_SAU
    if dd >= correction:
        return ZONE_DIEU_CHINH
    near_peak = float(cfg.get("near_peak_pct", 7.0))
    run_min = float(cfg.get("strong_run_gain_pct", 30.0))
    if (dd <= near_peak and snap.gain_run_pct is not None
            and snap.gain_run_pct >= run_min):
        return ZONE_PHAN_PHOI
    return ZONE_BINH_THUONG


# --- Kế hoạch giải ngân theo bậc ---------------------------------------------


def tranche_levels(snap: RegimeSnapshot, rules: Optional[dict] = None) -> list[dict]:
    """Quy các bậc % giảm trong config thành MỨC ĐIỂM SỐ cụ thể của VN-Index.

    Một tín hiệu "đã đến lúc mua" mà không nói mua ở đâu, mua bao nhiêu phần
    thì không thực hiện được — cùng lý do `decision/position_size.py` tồn tại
    cho từng mã.
    """
    rules = rules or load_rules()
    cfg = (rules.get("regime", {}) or {})
    if snap.peak is None:
        return []
    out = []
    for t in cfg.get("tranches", []) or []:
        dd = float(t.get("drawdown_pct", 0))
        out.append({
            "drawdown_pct": dd,
            "allocation_pct": float(t.get("allocation_pct", 0)),
            "index_level": round(snap.peak * (1 - dd / 100), 2),
            "reached": snap.drawdown_pct is not None and snap.drawdown_pct >= dd,
        })
    return out


# --- Tín hiệu gom hàng: ghép bối cảnh giá với tâm lý tin tức ------------------


@dataclass
class Condition:
    name: str
    met: Optional[bool]      # None = CHƯA ĐO ĐƯỢC — không phải False
    evidence: str

    @property
    def mark(self) -> str:
        return {True: "✅", False: "❌", None: "❔"}[self.met]


def accumulation_signal(snap: RegimeSnapshot, news, rules: Optional[dict] = None) -> dict:
    """Hai điều kiện chủ danh mục đặt ra, đo bằng số:

    1. VN-Index ở vùng đáy sâu so với lịch sử (drawdown + percentile).
    2. Tin tức về chứng khoán đang tiêu cực áp đảo (`analytics/news_sentiment`).

    Quy tắc quan trọng nhất ở đây là quy tắc IM LẶNG: chỉ cần một điều kiện
    CHƯA ĐO ĐƯỢC là trạng thái thành CHƯA ĐO ĐƯỢC, không bao giờ thành tín
    hiệu mua. Thiếu nhật ký tin tức không phải "không có tin xấu", và chuỗi
    EOD 43 phiên không phải "chưa chạm đáy lịch sử".
    """
    rules = rules or load_rules()
    cfg = rules.get("regime", {}) or {}
    deep = float(cfg.get("deep_drawdown_pct", 30.0))
    low_pct_max = float(cfg.get("low_percentile_max", 20.0))

    # Điều kiện 1 -------------------------------------------------------------
    if not snap.has_data:
        c1 = Condition("VN-Index ở đáy sâu so với lịch sử", None,
                       f"chưa có `data/eod/{INDEX_SYMBOL}.csv`")
    elif not snap.enough_history or snap.drawdown_pct is None or snap.is_stale:
        c1 = Condition("VN-Index ở đáy sâu so với lịch sử", None,
                       "; ".join(snap.notes) or "chuỗi lịch sử chưa đủ dài")
    else:
        met = snap.zone == ZONE_VUNG_GOM
        detail = f"giảm {snap.drawdown_pct:.1f}% từ đỉnh (cần ≥ {deep:.0f}%)"
        if snap.percentile is not None:
            detail += (f", percentile {snap.percentile:.0f} trong "
                       f"{snap.percentile_sessions} phiên (cần ≤ {low_pct_max:.0f})")
        else:
            detail += ", chưa tính được percentile"
        c1 = Condition("VN-Index ở đáy sâu so với lịch sử", met, detail)

    # Điều kiện 2 -------------------------------------------------------------
    if news is None or not news.measurable:
        c2 = Condition("Tin tức tiêu cực tràn ngập", None,
                       news.reason if news is not None else "chưa có nhật ký tin tức")
    else:
        c2 = Condition("Tin tức tiêu cực tràn ngập", news.overwhelming_negative,
                       news.evidence())

    conditions = [c1, c2]
    if any(c.met is None for c in conditions):
        status = STATUS_CHUA_DO_DUOC
    elif all(c.met for c in conditions):
        status = STATUS_VUNG_GOM
    elif any(c.met for c in conditions):
        status = STATUS_THEO_DOI_SAT
    else:
        status = STATUS_CHUA_DEN_LUC

    warnings: list[str] = []
    if status == STATUS_VUNG_GOM:
        if snap.making_new_low:
            warnings.append(
                "Giá đóng cửa vẫn là đáy của "
                f"{int(cfg.get('new_low_lookback_sessions', 10))} phiên gần nhất — "
                "đáy sâu + tin xấu KHÔNG có nghĩa là đã hết rơi. Giải ngân từng bậc, "
                "không mua một lần.")
        warnings.append(
            "Điều kiện 'tin xấu tràn ngập' là tín hiệu NGƯỢC chỉ khi giá đã chiết "
            "khấu sâu. Tin xấu lúc giá còn cao là tin xấu thật, không phải cơ hội.")
    if status == STATUS_CHUA_DO_DUOC:
        warnings.append(
            "Trạng thái này KHÔNG có nghĩa là 'chưa đến lúc' — nghĩa là hệ thống "
            "không đủ dữ liệu để nói. Xem phần thiếu gì ở trên.")

    return {
        "status": status,
        "status_vi": STATUS_VI[status],
        "zone": snap.zone,
        "zone_vi": snap.zone_vi,
        "conditions": conditions,
        "warnings": warnings,
        "tranches": tranche_levels(snap, rules) if status in (
            STATUS_VUNG_GOM, STATUS_THEO_DOI_SAT) else [],
    }


# --- Trạng thái giữa các kỳ: tin MỚI hay điều kiện đã kéo dài -----------------


def load_state(path: Optional[Path] = None) -> dict:
    p = path or STATE_PATH
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_state(state: dict, path: Optional[Path] = None) -> None:
    p = path or STATE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def track(status: str, zone: Optional[str], today: Optional[str] = None,
          state: Optional[dict] = None) -> tuple[dict, bool, int]:
    """Trả (state mới, is_new, số kỳ liên tiếp) cho trạng thái hiện tại.

    Cùng bài học với `analytics/alert_health.py`: một cảnh báo lặp lại ở mọi kỳ
    thì không còn là tin. Vùng gom hàng có thể kéo dài hàng tháng — kỳ đầu là
    TIN, kỳ thứ 20 là BỐI CẢNH, và bản tin phải nói khác nhau ở hai chỗ đó.

    Bộ đếm tính theo NGÀY, không theo số lần chạy: bản tin sáng và bản tin
    chiều cùng ngày, hay một lần chạy thử, không được thổi "đã 2 kỳ" lên từ
    một ngày duy nhất. Bối cảnh thị trường đổi theo phiên, không theo lần gọi
    hàm.
    """
    state = dict(state if state is not None else load_state())
    today = today or date.today().isoformat()
    same = state.get("status") == status and state.get("zone") == zone
    if same and state.get("last_seen") == today:
        return dict(state), False, int(state.get("periods", 1))
    if same:
        periods = int(state.get("periods", 1)) + 1
        first_seen = state.get("first_seen", today)
    else:
        periods, first_seen = 1, today
    new_state = {"status": status, "zone": zone, "first_seen": first_seen,
                 "periods": periods, "last_seen": today}
    return new_state, not same, periods

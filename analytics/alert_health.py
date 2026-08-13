"""Giữ cho cảnh báo ngưỡng còn nói được điều gì — chống "cảnh báo luôn bật".

Vì sao cần: `data/alerts.json` đặt ngưỡng theo giá ngày 18/7 rồi không bao giờ
cập nhật. Đo ngày 13/8: **3 trong 6 ngưỡng kích hoạt vĩnh viễn**. Rõ nhất là
`gold-res` "vượt 4.060$" — XAU đã 4.340$, nên nó báo động ở MỌI lần chạy suốt
nhiều tuần và không còn mang thông tin nào. Cảnh báo luôn bật là cảnh báo không
ai đọc, và tệ hơn: nó làm loãng những cảnh báo thật.

Cùng họ lỗi với vụ "khuyến nghị CHỐT BỚT lặp 14 kỳ": trạng thái cần làm mới mà
không có gì làm mới nó.

Hai cơ chế:

1. **Đếm số lần kích hoạt liên tiếp** (`data/alert_state.json`). Lần đầu chạm
   ngưỡng là TIN; chạm liên tiếp quá `STALE_AFTER_FIRES` lần thì thành trạng
   thái nền — báo "ngưỡng lỗi thời, cần đặt lại" thay vì báo như tin mới.
2. **Đặt lại ngưỡng theo biến động thật** thay vì số tròn tay: hỗ trợ/kháng cự
   cách giá hiện tại 1,5×ATR (cổ phiếu, từ `data/eod/`) hoặc 1,5×độ lệch chuẩn
   ngày (vàng, từ `history.jsonl`). Ngưỡng tôn trọng biến động của chính tài sản
   thì mới không kêu vì nhiễu.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "data" / "alert_state.json"

# Kích hoạt liên tiếp quá số lần này thì ngưỡng coi như lỗi thời
STALE_AFTER_FIRES = 3
# Khoảng cách đặt ngưỡng mới, theo bội số biến động thật của tài sản
ATR_MULTIPLE = 1.5


@dataclass
class AlertResult:
    alert_id: str
    asset: str
    type: str          # below | above
    level: float
    price: float
    note: str
    fired: bool
    consecutive_fires: int
    is_fresh: bool     # vừa chạm lần đầu (hoặc chạm lại sau khi đã thoát) = TIN
    is_stale: bool     # chạm liên tiếp quá nhiều = ngưỡng lỗi thời

    @property
    def headline(self) -> str:
        d = "thủng xuống" if self.type == "below" else "vượt lên"
        if self.is_stale:
            return (f"{self.asset} = {self.price:g} vẫn {d} {self.level:g} "
                    f"(liên tiếp {self.consecutive_fires} lần — NGƯỠNG LỖI THỜI, "
                    f"đặt lại bằng: alerts.py --reanchor)")
        return f"{self.asset} = {self.price:g} đã {d} {self.level:g} → {self.note}"


def load_state(path: Optional[Path] = None) -> dict:
    path = path or STATE_PATH
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}  # state hỏng thì coi như chưa có — không được làm sập việc quét


def save_state(state: dict, path: Optional[Path] = None) -> None:
    path = path or STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _fired(alert: dict, price: float) -> bool:
    if alert["type"] == "below":
        return price < alert["level"]
    return price > alert["level"]


def evaluate(
    alerts: Sequence[dict],
    prices: dict,
    state: Optional[dict] = None,
    *,
    today: Optional[str] = None,
    period: Optional[str] = None,
) -> tuple[list[AlertResult], dict]:
    """(kết quả, state mới). Không tự ghi đĩa — caller quyết định có lưu không.

    Không có giá cho tài sản nào thì BỎ QUA tài sản đó, KHÔNG reset bộ đếm: thiếu
    giá không phải bằng chứng rằng ngưỡng đã thoát.

    `period` (VD "2026-08-10-chieu") khiến bộ đếm tính theo KỲ chứ không theo số
    lần quét: quét lại cùng một kỳ không cộng thêm. Nếu không, chạy CLI 3 lần
    trong một buổi sẽ tự đẩy ngưỡng thành "lỗi thời" dù mới chạm 1 kỳ — bộ đếm
    phải đo diễn biến thị trường, không đo số lần mình gõ lệnh.
    """
    state = dict(state or {})
    out: list[AlertResult] = []
    for a in alerts:
        aid = a.get("id") or f"{a.get('asset')}-{a.get('type')}-{a.get('level')}"
        price = prices.get(a.get("asset"))
        if price is None:
            continue
        prev = state.get(aid, {})
        prev_count = int(prev.get("consecutive_fires", 0) or 0)
        hit = _fired(a, float(price))
        same_period = period is not None and prev.get("last_period") == period
        if not hit:
            count = 0
        elif same_period:
            count = max(1, prev_count)  # đã tính kỳ này rồi, không cộng nữa
        else:
            count = prev_count + 1
        entry = {"consecutive_fires": count}
        if hit:
            entry["first_fired"] = prev.get("first_fired") or today
            entry["last_fired"] = today
            if period:
                entry["last_period"] = period
        state[aid] = entry
        out.append(AlertResult(
            alert_id=aid, asset=a["asset"], type=a["type"], level=float(a["level"]),
            price=float(price), note=a.get("note", ""), fired=hit,
            consecutive_fires=count,
            # Theo `count` chứ không theo `prev_count`: quét lại cùng một kỳ phải
            # cho CÙNG kết quả, không đổi từ "tin mới" sang "cũ" chỉ vì gõ lệnh lần hai.
            is_fresh=hit and count == 1,
            is_stale=hit and count > STALE_AFTER_FIRES,
        ))
    return out, state


# ---------------------------------------------------------------- đặt lại ngưỡng

def daily_volatility(values: Sequence[float]) -> Optional[float]:
    """Độ lệch chuẩn của thay đổi tuyệt đối giữa các quan sát liền nhau."""
    import statistics as st

    diffs = [abs(b - a) for a, b in zip(values, values[1:])]
    if len(diffs) < 2:
        return None
    return st.stdev(diffs)


def band_from_eod(csv_path: Path) -> Optional[float]:
    """Khoảng đặt ngưỡng = 1,5×ATR(14) từ file EOD. None nếu thiếu dữ liệu."""
    from analytics.ta_core import atr

    if not csv_path.exists():
        return None
    highs, lows, closes = [], [], []
    for line in csv_path.read_text(encoding="utf-8").splitlines():
        parts = line.split(",")
        if len(parts) < 5:
            continue
        try:
            highs.append(float(parts[2]))
            lows.append(float(parts[3]))
            closes.append(float(parts[4]))
        except ValueError:
            continue  # dòng header hoặc dòng lỗi
    value = atr(highs, lows, closes) if len(closes) >= 15 else None
    return value * ATR_MULTIPLE if value else None


def reanchor(
    alerts: Sequence[dict],
    prices: dict,
    bands: dict[str, float],
    *,
    today: Optional[str] = None,
) -> tuple[list[dict], list[str]]:
    """(danh sách alert đã đặt lại, ghi chú thay đổi).

    Ngưỡng `below` về `giá − band`, `above` về `giá + band`. Tài sản thiếu giá
    hoặc thiếu band thì GIỮ NGUYÊN ngưỡng cũ và nói rõ vì sao — thà để ngưỡng cũ
    còn hơn đặt ngưỡng bằng số bịa.

    Ghi chú cũng được viết lại. Nếu không, `note` viết tay theo mức cũ sẽ nói
    ngược với mức mới (đã thấy thật: ngưỡng thành 4.410$ mà ghi chú vẫn ghi
    "Vượt 4.060$"). Ghi chú tay gốc được giữ ở `note_manual` để không mất phần
    nhận định của con người — chỉ chuyển nó xuống vai phụ.
    """
    updated: list[dict] = []
    notes: list[str] = []
    for a in alerts:
        new = dict(a)
        asset = a.get("asset")
        price, band = prices.get(asset), bands.get(asset)
        if price is None or not band:
            thieu = "giá hiện tại" if price is None else "dữ liệu biến động"
            notes.append(f"{a.get('id', asset)}: GIỮ NGUYÊN {a['level']:g} — thiếu {thieu}")
            updated.append(new)
            continue
        level = round(price - band, 2) if a["type"] == "below" else round(price + band, 2)
        if level == a["level"]:
            notes.append(f"{a.get('id', asset)}: không đổi ({level:g})")
        else:
            notes.append(f"{a.get('id', asset)}: {a['level']:g} → {level:g} "
                         f"(giá {price:g} ∓ {band:.2f} = {ATR_MULTIPLE}×biến động)")
        huong = "thủng xuống" if a["type"] == "below" else "vượt lên"
        manual = a.get("note_manual") or a.get("note") or ""
        new["level"] = level
        new["note"] = (f"{huong} {level:g} — ngưỡng tự đặt"
                       + (f" {today}" if today else "")
                       + f", cách giá {price:g} một khoảng {ATR_MULTIPLE}×biến động thật "
                         f"({band:.2f})")
        if manual:
            new["note_manual"] = manual
        updated.append(new)
    return updated, notes

"""Mức CẮT LỖ của vị thế phải được CANH, không chỉ được in ra một lần.

`decision/position_size.py` tính ra "cắt lỗ dưới 53,61" và bản tin in nó. Rồi
thôi. Không gì trong hệ thống theo dõi mức đó: `data/alerts.json` là các ngưỡng
đặt tay, và mức cắt lỗ của một vị thế thật không nằm trong đó.

Một vị thế có mức thoát chỉ tồn tại trong một dòng chữ đã trôi qua thì không
phải vị thế được quản lý — đó là vị thế có kèm một lời hứa. Cùng họ với những
lỗi khác trong dự án này: trạng thái cần được canh mà không có gì canh nó.

Module đăng ký mức cắt lỗ thành một cảnh báo THẬT trong `data/alerts.json`, để
`scripts/alerts.py` quét nó mỗi kỳ như mọi ngưỡng khác. Ba ràng buộc:

1. **Chỉ đăng ký cho vị thế ĐANG NẮM.** Mức cắt lỗ của một mã chỉ theo dõi
   thì vô nghĩa — chưa mua thì không có gì để cắt.
2. **Không đè ngưỡng đặt tay.** Cảnh báo tự sinh mang `id` riêng và cờ
   `auto: true`; nhận định tay ở `note_manual` không bị đụng tới.
3. **Vị thế đóng thì gỡ cảnh báo.** Ngưỡng của một vị thế không còn tồn tại sẽ
   kêu mãi mà không mang thông tin nào — đúng cái bệnh alert fatigue đã sửa ở
   `analytics/alert_health.py`.
"""
from __future__ import annotations

from typing import Optional, Sequence

# Tiền tố id để phân biệt cảnh báo tự sinh với ngưỡng đặt tay.
AUTO_PREFIX = "stop-"


def stop_alert_id(ticker: str) -> str:
    return f"{AUTO_PREFIX}{ticker.lower()}"


def build_stop_alert(ticker: str, stop_level: float, *, entry: Optional[float] = None,
                     target: Optional[float] = None) -> dict:
    """Một cảnh báo `below` cho mức cắt lỗ, kèm lý do đọc được."""
    bits = [f"CẮT LỖ vị thế {ticker.upper()}: thủng {stop_level:,.2f}"]
    if entry:
        loss = (entry - stop_level) / entry * 100
        bits.append(f"giá vào {entry:,.2f} → mất {loss:.1f}%")
    if target:
        bits.append(f"mục tiêu {target:,.2f}")
    bits.append("luận điểm kỹ thuật sai khi thủng mức này — thoát, không chờ thêm")
    return {
        "id": stop_alert_id(ticker),
        "asset": ticker.upper(),
        "type": "below",
        "level": round(stop_level, 2),
        "note": " · ".join(bits),
        "auto": True,
    }


def sync_stops(alerts: list[dict], positions: Sequence[dict]) -> tuple[list[dict], list[str]]:
    """Đồng bộ cảnh báo cắt lỗ với vị thế đang nắm.

    `positions` = [{"ticker", "stop", "entry"?, "target"?}]. Trả (alerts mới,
    danh sách việc đã làm) — luôn nói rõ đã thêm/sửa/gỡ gì, vì thay đổi âm
    thầm trong danh sách cảnh báo là thứ không ai kiểm được.
    """
    wanted = {p["ticker"].upper(): p for p in positions if p.get("stop")}
    changes: list[str] = []
    out: list[dict] = []

    seen: set[str] = set()
    for a in alerts:
        if not a.get("auto") or not str(a.get("id", "")).startswith(AUTO_PREFIX):
            out.append(a)  # ngưỡng đặt tay: giữ nguyên tuyệt đối
            continue
        ticker = str(a.get("asset", "")).upper()
        p = wanted.get(ticker)
        if p is None:
            # Vị thế đã đóng — gỡ, không để ngưỡng mồ côi kêu mãi.
            changes.append(f"gỡ cảnh báo cắt lỗ {ticker} (không còn vị thế)")
            continue
        seen.add(ticker)
        fresh = build_stop_alert(ticker, p["stop"], entry=p.get("entry"), target=p.get("target"))
        if abs(float(a.get("level", 0)) - fresh["level"]) > 1e-9:
            changes.append(f"cập nhật cắt lỗ {ticker}: {a.get('level')} → {fresh['level']}")
        out.append(fresh)

    for ticker, p in wanted.items():
        if ticker in seen:
            continue
        out.append(build_stop_alert(ticker, p["stop"], entry=p.get("entry"), target=p.get("target")))
        changes.append(f"thêm cảnh báo cắt lỗ {ticker} tại {p['stop']:,.2f}")
    return out, changes

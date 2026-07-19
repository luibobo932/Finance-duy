"""Quy đổi giá vàng thế giới (USD/oz troy) sang VND/lượng.

Hằng số dùng đúng độ chính xác chuẩn quốc tế — Phase 1 audit phát hiện
`data/gold_model.json` cũ dùng xấp xỉ `1.205656` thay vì giá trị chính xác
`37.5 / 31.1034768 = 1.2056529963...`. Sai số tuyệt đối nhỏ (~0.0003tr/lượng)
nhưng phải sửa cho đúng vì đây là hằng số vật lý cố định, không có lý do gì
để xấp xỉ.
"""
from __future__ import annotations

GRAMS_PER_TROY_OUNCE = 31.1034768
GRAMS_PER_VIETNAMESE_TAEL = 37.5

# Hệ số quy đổi lượng <-> ounce troy (dùng chính xác, không làm tròn trước)
TAEL_PER_TROY_OUNCE = GRAMS_PER_VIETNAMESE_TAEL / GRAMS_PER_TROY_OUNCE


def theoretical_vnd_per_tael(xau_usd: float, usd_vnd: float) -> float:
    """Giá vàng thế giới quy đổi lý thuyết, đơn vị VND/lượng (chưa trừ/cộng premium).

    theoretical_vnd_per_tael = xau_usd * (37.5 / 31.1034768) * usd_vnd
    """
    return xau_usd * GRAMS_PER_VIETNAMESE_TAEL / GRAMS_PER_TROY_OUNCE * usd_vnd


def theoretical_trieu_per_tael(xau_usd: float, usd_vnd: float) -> float:
    """Như trên nhưng đơn vị triệu đồng/lượng — tiện cho hiển thị bản tin."""
    return theoretical_vnd_per_tael(xau_usd, usd_vnd) / 1_000_000

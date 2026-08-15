"""Lợi suất THỰC — tầng mà toàn bộ hệ thống đang thiếu.

Vì sao đây không phải chi tiết học thuật: mọi con số hệ thống đã nói với chủ
danh mục cho tới nay đều là **danh nghĩa**. "Tiền gửi 8,0%/năm", "lãi thêm 11
tr/năm", "danh mục 1.173 tr". Không kỳ nào trừ lạm phát. Với **CPI bình quân 7
tháng 2026 là +4,39%** (Tổng cục Thống kê), khoảng cách giữa hai cách nói là
khoảng cách giữa hai kết luận trái ngược:

    35 tr tiền mặt      danh nghĩa   0,00%  →  THỰC  −4,21%/năm  (mất 1,47 tr/năm)
    tiết kiệm ở 4,5%    danh nghĩa  +4,50%  →  THỰC  +0,11%/năm  (đứng yên)
    tiết kiệm ở 8,0%    danh nghĩa  +8,00%  →  THỰC  +3,46%/năm

Nói "gửi 4,5%/năm" nghe như đang sinh lời. Nói "thực +0,11%/năm" mới là sự
thật: sức mua gần như không nhúc nhích. Đây là cùng một họ lỗi mà cả dự án
đang sửa — một con số đúng về kỹ thuật nhưng dẫn tới kết luận sai.

**Fisher CHÍNH XÁC, không phải phép trừ.** Lợi suất thực không phải
`danh_nghĩa − lạm_phát` mà là `(1+n)/(1+i) − 1`. Ở mức 8,00% và 4,39%, phép
trừ cho 3,61% còn công thức đúng cho 3,46% — chênh 0,15 điểm %. Trên 246 tr
suốt 10 năm, sai số đó là hơn 4 triệu đồng, và nó luôn lệch về phía LẠC QUAN.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass
class RealReturn:
    label: str
    nominal_pct: float
    inflation_pct: float
    amount_trieu: Optional[float] = None

    @property
    def real_pct(self) -> float:
        """Fisher chính xác: (1+n)/(1+i) − 1. KHÔNG dùng phép trừ."""
        return ((1 + self.nominal_pct / 100) / (1 + self.inflation_pct / 100) - 1) * 100

    @property
    def real_change_trieu(self) -> Optional[float]:
        """Sức mua thay đổi mỗi năm, quy ra tiền. Âm = đang bào mòn."""
        if self.amount_trieu is None:
            return None
        return self.amount_trieu * self.real_pct / 100

    @property
    def verdict(self) -> str:
        r = self.real_pct
        if r < -1:
            return "đang MẤT sức mua"
        if r < 0.5:
            return "gần như đứng yên"
        if r < 2:
            return "giữ được sức mua, tăng chậm"
        return "tăng thật"


def real_pct(nominal_pct: float, inflation_pct: float) -> float:
    """Lợi suất thực theo Fisher chính xác."""
    return ((1 + nominal_pct / 100) / (1 + inflation_pct / 100) - 1) * 100


def nominal_needed_for(target_real_pct: float, inflation_pct: float) -> float:
    """Cần lãi suất danh nghĩa bao nhiêu để đạt mức thực mong muốn.

    Câu hỏi ngược, và là câu hữu ích hơn khi đi chọn kỳ hạn gửi: "muốn sức mua
    tăng thật 2%/năm thì phải tìm mức mấy phần trăm?"
    """
    return ((1 + target_real_pct / 100) * (1 + inflation_pct / 100) - 1) * 100


def erosion_trieu(amount_trieu: float, inflation_pct: float, years: float = 1.0) -> float:
    """Sức mua BỊ BÀO MÒN của một khoản không sinh lãi, sau `years` năm.

    Dùng cho tiền mặt: 35 tr để yên một năm với lạm phát 4,39% chỉ còn mua được
    lượng hàng hoá tương đương 33,5 tr hôm nay.
    """
    return amount_trieu * (1 - (1 / (1 + inflation_pct / 100) ** years))


def purchasing_power_trieu(amount_trieu: float, inflation_pct: float, years: float) -> float:
    """Giá trị của `amount_trieu` sau `years` năm, tính theo sức mua HÔM NAY."""
    return amount_trieu / (1 + inflation_pct / 100) ** years


def portfolio_real_return(
    holdings: Sequence[tuple[str, float, Optional[float]]], inflation_pct: float
) -> dict:
    """Lợi suất thực bình quân gia quyền của cả danh mục.

    `holdings` = [(tên, giá_trị_triệu, lợi_suất_danh_nghĩa_%_hoặc_None)].
    Phần **chưa khai báo lợi suất KHÔNG được coi là 0%** — đó là hai chuyện
    khác nhau, và gán 0 cho cái chưa biết sẽ kéo tụt kết quả một cách bịa đặt.
    Thay vào đó chúng được tách riêng và báo rõ tỷ trọng chưa đo được.
    """
    total = sum(v for _, v, _ in holdings)
    if not total:
        return {"known_weight_pct": 0.0, "real_pct": None, "unknown": [], "rows": [], "total_trieu": 0.0}
    known = [(n, v, r) for n, v, r in holdings if r is not None]
    # Giữ CẢ GIÁ TRỊ của phần chưa đo được: biết "Vàng chưa khai báo" mà không
    # biết nó là 892 tr thì không thấy được vấn đề lớn tới đâu.
    unknown = [(n, v) for n, v, r in holdings if r is None]
    known_value = sum(v for _, v, _ in known)
    rows = [RealReturn(n, r, inflation_pct, v) for n, v, r in known]
    weighted = (sum(rr.real_pct * (rr.amount_trieu or 0) for rr in rows) / known_value
                if known_value else None)
    return {
        "known_weight_pct": known_value / total * 100,
        "real_pct": weighted,
        "unknown": unknown,
        "rows": rows,
        "total_trieu": total,
    }


def doubling_years(real_pct_value: float) -> Optional[float]:
    """Bao nhiêu năm để sức mua tăng gấp đôi, ở mức lợi suất thực này.

    Trả None khi lợi suất thực ≤ 0 — không có "số năm để gấp đôi" cho một
    khoản đang teo lại, và trả một con số khổng lồ ở đó là gây hiểu nhầm.
    """
    if real_pct_value <= 0:
        return None
    from math import log

    return log(2) / log(1 + real_pct_value / 100)

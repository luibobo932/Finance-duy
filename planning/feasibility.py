"""Mục tiêu 10 tỷ có khả thi không — và **cần gì** để khả thi.

Chủ danh mục đặt mục tiêu: nâng tổng tài sản lên **10 tỷ**. Hiện có 1.173 tr,
tức cần gấp **8,53 lần**. Câu hỏi đúng không phải "mua mã nào" mà là: với ba
biến — **thời hạn**, **tiền gửi thêm mỗi tháng**, **lợi suất** — cố định hai
cái thì cái thứ ba phải bằng bao nhiêu.

Đây là điều module này làm, và kết quả trên số thật đảo ngược trực giác thông
thường về đầu tư:

    KHÔNG gửi thêm đồng nào, chỉ dựa vào lợi suất:
        10 năm → cần 23,90%/năm    ← không danh mục cá nhân nào giữ được mức
        20 năm → cần 11,31%/năm       này bền vững; đó là đánh cược, không
        30 năm →  7,41%/năm           phải đầu tư

    CHỈ gửi tiết kiệm 8,0%/năm (không rủi ro), gửi thêm mỗi tháng:
        10 năm → 40,8 tr/tháng
        20 năm →  7,7 tr/tháng     ← khả thi với thu nhập bình thường
        30 năm → không cần gửi thêm đồng nào

Kết luận có sức nặng hơn mọi khuyến nghị cổ phiếu: **đòn bẩy mạnh nhất là THỜI
HẠN và TỶ LỆ TÍCH LUỸ, không phải chọn mã.** Kéo dài từ 10 năm lên 20 năm làm
mức tiết kiệm cần thiết giảm 5,3 lần — không cách chọn cổ phiếu nào tạo ra được
độ chênh đó.

**Danh nghĩa hay sức mua?** "10 tỷ" hầu như luôn được hiểu là con số danh
nghĩa — nhìn thấy 10 tỷ trong tài khoản. Nhưng sau 20 năm lạm phát 4,39%, 10 tỷ
đó chỉ mua được lượng hàng hoá của **~4,2 tỷ hôm nay**. Module này luôn trả CẢ
HAI, vì đó là hai mục tiêu khác nhau chứ không phải hai cách nói.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

# Các mốc thời hạn đem ra so sánh khi chưa chốt thời hạn.
DEFAULT_HORIZONS_YEARS: tuple[int, ...] = (5, 10, 15, 20, 25, 30)

# Phân loại mức lợi suất đòi hỏi. Mốc đầu là SỐ ĐO THẬT (lãi suất tiền gửi tốt
# nhất đang quan sát được); các mốc sau là NHẬN ĐỊNH, nêu rõ để không ai đọc
# nhầm thành số đo.
BAND_LABELS = {
    "risk_free": "đạt được bằng TIỀN GỬI, không cần chấp nhận rủi ro",
    "moderate": "cần danh mục có cổ phiếu — khả thi nhưng phải chịu biến động",
    "aggressive": "đòi hỏi rất cao; rất ít danh mục cá nhân giữ được mức này nhiều năm liền",
    "unrealistic": "KHÔNG phải mục tiêu đầu tư — cần đổi thời hạn hoặc tăng tích luỹ",
}
# Nhãn NGẮN cho bảng, nhãn dài cho phần chú giải bên dưới. Lý do rất cụ thể:
# bảng đầy đủ nhãn dài rộng ~118 ký tự, trong khối <pre> của Telegram nó phải
# cuộn ngang trên điện thoại — mà bảng này là phần đáng đọc nhất của báo cáo.
BAND_SHORT = {
    "risk_free": "✅ tiền gửi là đủ",
    "moderate": "✅ khả thi",
    "aggressive": "⚠️ đòi hỏi rất cao",
    "unrealistic": "❌ không khả thi",
}
MODERATE_CEILING_PCT = 12.0
AGGRESSIVE_CEILING_PCT = 20.0
BAND_NOTE = ("Mốc dưới cùng là lãi suất tiền gửi tốt nhất ĐANG ĐO ĐƯỢC (số thật). "
             "Hai mốc 12% và 20% là NHẬN ĐỊNH về mức bền vững, không phải số đo — "
             "nêu rõ để không bị đọc nhầm thành dự báo.")


@dataclass
class HorizonRow:
    years: int
    required_return_pct: Optional[float]      # nếu KHÔNG gửi thêm
    required_real_return_pct: Optional[float]
    required_monthly_trieu: Optional[float]   # nếu CHỈ dùng lợi suất an toàn
    value_from_current_trieu: float           # tài sản hiện có tự lên bao nhiêu
    band: str

    @property
    def band_label(self) -> str:
        return BAND_LABELS.get(self.band, self.band)

    @property
    def band_short(self) -> str:
        return BAND_SHORT.get(self.band, self.band)


def required_return_pct(current_trieu: float, target_trieu: float, years: int) -> Optional[float]:
    """Lợi suất danh nghĩa cần, nếu KHÔNG gửi thêm đồng nào."""
    if current_trieu <= 0 or years <= 0:
        return None
    return ((target_trieu / current_trieu) ** (1 / years) - 1) * 100


def required_monthly_trieu(
    current_trieu: float, target_trieu: float, years: int, annual_return_pct: float
) -> Optional[float]:
    """Cần gửi thêm bao nhiêu mỗi tháng, ở một mức lợi suất cho trước.

    Trả 0.0 khi tài sản hiện có đã tự đủ — khác hẳn None (không tính được).
    """
    if years <= 0:
        return None
    fv_current = current_trieu * (1 + annual_return_pct / 100) ** years
    need = target_trieu - fv_current
    if need <= 0:
        return 0.0
    r, n = annual_return_pct / 100 / 12, years * 12
    if r == 0:
        return need / n
    return need * r / ((1 + r) ** n - 1)


def required_years(
    current_trieu: float, target_trieu: float, annual_return_pct: float,
    monthly_trieu: float = 0.0, max_years: int = 60,
) -> Optional[int]:
    """Bao nhiêu năm thì tới đích, với lợi suất và mức tích luỹ cho trước.

    Trả None khi KHÔNG BAO GIỜ tới trong `max_years` — trả một con số khổng lồ
    ở đây sẽ bị đọc thành "rồi cũng tới", trong khi sự thật là kế hoạch không
    hoạt động.
    """
    if current_trieu >= target_trieu:
        return 0
    value = current_trieu
    for y in range(1, max_years + 1):
        value = value * (1 + annual_return_pct / 100) + monthly_trieu * 12
        if value >= target_trieu:
            return y
    return None


def classify(required_pct: Optional[float], risk_free_pct: Optional[float]) -> str:
    """Xếp mức lợi suất đòi hỏi vào một dải, neo mốc đầu vào SỐ ĐO THẬT."""
    if required_pct is None:
        return "unrealistic"
    if risk_free_pct is not None and required_pct <= risk_free_pct:
        return "risk_free"
    if required_pct <= MODERATE_CEILING_PCT:
        return "moderate"
    if required_pct <= AGGRESSIVE_CEILING_PCT:
        return "aggressive"
    return "unrealistic"


def horizon_table(
    current_trieu: float, target_trieu: float, inflation_pct: float,
    *, risk_free_pct: Optional[float] = None,
    horizons: Sequence[int] = DEFAULT_HORIZONS_YEARS,
) -> list[HorizonRow]:
    """Bảng "cần gì ở từng thời hạn" — đầu ra chính khi chưa chốt thời hạn.

    Chưa chốt thời hạn thì đây KHÔNG phải thiếu sót cần chờ: chính bảng này là
    thứ giúp chọn thời hạn, vì nó cho thấy mỗi năm cộng thêm đáng giá bao nhiêu.
    """
    from planning.real_return import real_pct

    safe = risk_free_pct if risk_free_pct is not None else 0.0
    rows = []
    for y in horizons:
        req = required_return_pct(current_trieu, target_trieu, y)
        rows.append(HorizonRow(
            years=y,
            required_return_pct=req,
            required_real_return_pct=real_pct(req, inflation_pct) if req is not None else None,
            required_monthly_trieu=required_monthly_trieu(current_trieu, target_trieu, y, safe),
            value_from_current_trieu=current_trieu * (1 + safe / 100) ** y,
            band=classify(req, risk_free_pct),
        ))
    return rows


@dataclass
class GoalReality:
    """Mục tiêu quy về hai thang — vì đó là hai mục tiêu khác nhau."""

    target_nominal_trieu: float
    years: int
    inflation_pct: float

    @property
    def purchasing_power_today_trieu(self) -> float:
        """10 tỷ sau N năm mua được lượng hàng hoá bằng bao nhiêu tiền hôm nay."""
        return self.target_nominal_trieu / (1 + self.inflation_pct / 100) ** self.years

    @property
    def nominal_needed_for_same_power_trieu(self) -> float:
        """Muốn 10 tỷ THEO SỨC MUA HÔM NAY thì con số danh nghĩa phải là bao nhiêu."""
        return self.target_nominal_trieu * (1 + self.inflation_pct / 100) ** self.years

    @property
    def note(self) -> str:
        return (f"Đạt {self.target_nominal_trieu / 1000:,.1f} tỷ danh nghĩa sau {self.years} năm "
                f"chỉ mua được lượng hàng hoá tương đương "
                f"{self.purchasing_power_today_trieu / 1000:,.1f} tỷ hôm nay. Muốn 10 tỷ THEO SỨC "
                f"MUA HÔM NAY thì con số danh nghĩa phải là "
                f"{self.nominal_needed_for_same_power_trieu / 1000:,.1f} tỷ.")


def best_lever(rows: Sequence[HorizonRow]) -> str:
    """Câu kết luận: đòn bẩy nào mạnh nhất, đo bằng chính bảng trên.

    Không phải nhận định chung chung — nó đo tỷ lệ giảm của mức tiết kiệm cần
    thiết khi kéo dài thời hạn, và so với thứ mà việc chọn cổ phiếu có thể đem
    lại.
    """
    usable = [r for r in rows if r.required_monthly_trieu not in (None, 0.0)]
    if len(usable) < 2:
        return ""
    # So một mốc với mốc GẤP ĐÔI nó — phép so người đọc tự kiểm được trong đầu,
    # khác với "đầu bảng vs cuối bảng" ra số to hơn nhưng khó đối chiếu.
    # Trong các cặp gấp đôi có thể lập, chọn cặp có tỷ lệ LỚN NHẤT: chọn bằng
    # dữ liệu, không phải bằng ý thích của người viết code.
    by_year = {r.years: r for r in usable}
    pairs = [(by_year[y], by_year[y * 2]) for y in by_year if y * 2 in by_year]
    if not pairs:
        return ""
    short, long = max(
        pairs, key=lambda p: p[0].required_monthly_trieu / p[1].required_monthly_trieu)  # type: ignore[operator]
    ratio = short.required_monthly_trieu / long.required_monthly_trieu  # type: ignore[operator]
    return (f"Gấp đôi thời hạn — từ {short.years} lên {long.years} năm — làm mức tiết kiệm cần "
            f"thiết giảm {ratio:.1f} lần ({short.required_monthly_trieu:.1f} → "
            f"{long.required_monthly_trieu:.1f} tr/tháng). Không cách chọn cổ phiếu nào tạo ra "
            "được độ chênh đó — đòn bẩy mạnh nhất là THỜI HẠN và TỶ LỆ TÍCH LUỸ.")

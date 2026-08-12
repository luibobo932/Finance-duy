"""Kiểm tra giá cổ phiếu có KHẢ THI về mặt vi cấu trúc thị trường hay không.

Vì sao cần: 4 trong 6 bản tin (20–22/7) phải viết tay một đoạn cảnh báo rằng
Simplize trả giá CTD = 73.800đ trong khi giá đã xác minh qua HOSE EOD là
59.100đ. Mỗi lần đều là phát hiện thủ công, dựa vào việc người soạn NHỚ rằng
nguồn đó không đáng tin. Không nhớ là dùng số sai.

Cách tiếp cận: KHÔNG dùng danh sách đen nguồn (chỉ bắt được nguồn đã biết), mà
dùng biên độ giá — một ràng buộc cứng của sàn:

    HOSE ±7%/phiên · HNX ±10% · UPCoM ±15%

Giá lệch khỏi tham chiếu quá biên độ cho phép trong số phiên đã trôi qua là
BẤT KHẢ THI, không phải "đáng nghi": sàn không cho phép khớp ở mức đó. Nhờ vậy
check này bắt được MỌI nguồn sai, kể cả nguồn chưa từng gặp.

Giới hạn phải nói thẳng: không có lịch nghỉ lễ, nên số phiên được đếm bằng số
ngày trong tuần (thứ 2–6). Nghỉ lễ dài làm phép đếm này CAO hơn thực tế, tức là
check nới lỏng hơn thực tế — sai theo hướng an toàn (không báo động giả).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

# Biên độ dao động giá tối đa 1 phiên theo sàn (%)
DAILY_BAND_PCT: dict[str, float] = {
    "HOSE": 7.0,
    "HNX": 10.0,
    "UPCOM": 15.0,
}
DEFAULT_EXCHANGE = "HOSE"

# Sàn của các mã đang theo dõi. Mã lạ dùng HOSE (biên hẹp nhất) — đoán chặt hơn
# thì cảnh báo sai theo hướng thận trọng, không bỏ sót giá phi lý.
TICKER_EXCHANGE: dict[str, str] = {
    t: "HOSE" for t in
    ("VCB", "CTD", "FPT", "VNM", "GAS", "ACB", "HPG", "MWG", "PNJ", "REE", "BSR")
}

PLAUSIBLE = "PLAUSIBLE"
IMPLAUSIBLE = "IMPLAUSIBLE"
NO_REFERENCE = "NO_REFERENCE"

# Quá số phiên này thì giá tham chiếu KHÔNG còn nói được gì về tính khả thi:
# biên tích lũy đã quá rộng (10 phiên HOSE = 1,07¹⁰−1 ≈ 96,7%) nên mọi giá đều
# "hợp lệ", và luỹ thừa với số phiên rất lớn còn gây tràn số. Trường hợp đó
# phải trả NO_REFERENCE — thà nói "không đủ căn cứ" hơn là gật đầu vô nghĩa.
MAX_SESSIONS_FOR_CHECK = 10


@dataclass
class PriceCheck:
    ticker: str
    candidate: float
    reference: Optional[float]
    reference_date: Optional[str]
    sessions_elapsed: Optional[int]
    max_move_pct: Optional[float]
    actual_move_pct: Optional[float]
    verdict: str
    message: str

    @property
    def ok(self) -> bool:
        return self.verdict != IMPLAUSIBLE


def sessions_between(start: str, end: str) -> int:
    """Số phiên (ngày trong tuần) từ `start` tới `end`, tối thiểu 1.

    Không có lịch nghỉ lễ — xem docstring module về hướng sai số.
    """
    try:
        a = datetime.strptime(start, "%Y-%m-%d").date()
        b = datetime.strptime(end, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 1
    if b <= a:
        return 1
    count = 0
    cur = a
    while cur < b:
        cur += timedelta(days=1)
        if cur.weekday() < 5:  # 0=thứ 2 ... 4=thứ 6
            count += 1
    return max(1, count)


def max_plausible_move_pct(sessions: int, exchange: str = DEFAULT_EXCHANGE) -> float:
    """Mức lệch tối đa có thể xảy ra sau `sessions` phiên, tính lãi kép biên độ.

    Dùng lãi kép chứ không nhân tuyến tính: 2 phiên trần HOSE là
    1,07² − 1 = 14,49%, không phải 14%.
    """
    band = DAILY_BAND_PCT.get(exchange.upper(), DAILY_BAND_PCT[DEFAULT_EXCHANGE])
    capped = min(max(1, sessions), MAX_SESSIONS_FOR_CHECK)  # chặn tràn số
    return ((1 + band / 100) ** capped - 1) * 100


def check_price(
    ticker: str,
    candidate: float,
    reference: Optional[float],
    *,
    reference_date: Optional[str] = None,
    target_date: Optional[str] = None,
    exchange: Optional[str] = None,
) -> PriceCheck:
    """So giá ứng viên với giá tham chiếu đã xác minh theo biên độ sàn.

    `candidate` và `reference` phải CÙNG đơn vị (cả hai là đồng, hoặc cả hai là
    nghìn đồng) — hàm không tự đoán đơn vị.
    """
    ex = (exchange or TICKER_EXCHANGE.get(ticker.upper(), DEFAULT_EXCHANGE)).upper()
    if reference is None or reference <= 0:
        return PriceCheck(
            ticker=ticker, candidate=candidate, reference=None, reference_date=reference_date,
            sessions_elapsed=None, max_move_pct=None, actual_move_pct=None,
            verdict=NO_REFERENCE,
            message=(f"{ticker}: chưa có giá tham chiếu đã xác minh để đối chiếu — "
                     "không kết luận được giá này đúng hay sai."),
        )

    sessions = (sessions_between(reference_date, target_date)
                if reference_date and target_date else 1)
    if sessions > MAX_SESSIONS_FOR_CHECK:
        return PriceCheck(
            ticker=ticker, candidate=candidate, reference=reference, reference_date=reference_date,
            sessions_elapsed=sessions, max_move_pct=None, actual_move_pct=None,
            verdict=NO_REFERENCE,
            message=(f"{ticker}: giá tham chiếu cách {sessions} phiên "
                     f"(> {MAX_SESSIONS_FOR_CHECK}) nên quá cũ để kết luận tính khả thi — "
                     "cần một giá đã xác minh gần hơn."),
        )
    limit = max_plausible_move_pct(sessions, ex)
    move = (candidate - reference) / reference * 100

    if abs(move) > limit:
        return PriceCheck(
            ticker=ticker, candidate=candidate, reference=reference, reference_date=reference_date,
            sessions_elapsed=sessions, max_move_pct=limit, actual_move_pct=move,
            verdict=IMPLAUSIBLE,
            message=(
                f"{ticker}: giá {candidate:,.2f} lệch {move:+.1f}% so với giá đã xác minh "
                f"{reference:,.2f}"
                + (f" ngày {reference_date}" if reference_date else "")
                + f", vượt biên độ tối đa {limit:.1f}% của {ex} sau {sessions} phiên. "
                "Giá này BẤT KHẢ THI — sàn không cho khớp ở mức đó. Kiểm tra lại nguồn "
                "(có thể sai đơn vị, sai mã, hoặc dữ liệu cũ/hỏng); KHÔNG dùng để ra quyết định."
            ),
        )
    return PriceCheck(
        ticker=ticker, candidate=candidate, reference=reference, reference_date=reference_date,
        sessions_elapsed=sessions, max_move_pct=limit, actual_move_pct=move,
        verdict=PLAUSIBLE,
        message=(f"{ticker}: giá {candidate:,.2f} lệch {move:+.1f}% so với tham chiếu "
                 f"{reference:,.2f} — trong biên độ {limit:.1f}% ({ex}, {sessions} phiên)."),
    )

"""Nạp `config/plan.yaml` + chiếu danh mục về tương lai theo SỨC MUA HÔM NAY.

Đây là tầng trả lời câu mà 19 kỳ khuyến nghị chưa trả lời: **"70% so với cái
gì?"** Không có mục tiêu thì mọi ngưỡng đều cảm giác tuỳ tiện, và một khuyến
nghị cảm giác tuỳ tiện thì bị bỏ qua — đúng như đã xảy ra.

Ba ràng buộc, cùng tinh thần với cả dự án:

1. **Hệ thống KHÔNG dự báo lợi suất.** Lợi suất kỳ vọng là giả định của chủ
   danh mục, khai trong config. Thiếu thì chạy **bảng độ nhạy** chứ không đoán.
   Cái duy nhất lấy từ số liệu thật là lạm phát (CPI đã công bố) và lãi suất
   tiền gửi (đang đo được).
2. **Mọi chiếu tương lai đều quy về sức mua HÔM NAY.** "3 tỷ năm 2041" là câu
   vô nghĩa nếu không nói 3 tỷ đó mua được gì — mà sau 15 năm lạm phát 4,39%,
   nó chỉ còn mua được lượng hàng của ~1,57 tỷ hôm nay.
3. **Chưa khai báo ≠ bằng 0.** Phần danh mục chưa có giả định lợi suất được
   tách riêng và báo rõ tỷ trọng, không bị gán 0 rồi kéo tụt kết quả.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

import yaml

ROOT = Path(__file__).resolve().parent.parent
PLAN_PATH = ROOT / "config" / "plan.yaml"

# Khoảng độ nhạy dùng khi chủ danh mục chưa khai lợi suất kỳ vọng. Đây KHÔNG
# phải dự báo — nó là cách nói "kết quả phụ thuộc mạnh vào giả định này, và
# đây là mức độ phụ thuộc".
SENSITIVITY_NOMINAL_PCT: tuple[float, ...] = (0.0, 3.0, 5.0, 7.0, 9.0, 12.0)


@dataclass
class Goal:
    name: str
    target_today_vnd: float
    target_year: int
    priority: int = 1

    def years_from(self, current_year: int) -> int:
        return max(0, self.target_year - current_year)


@dataclass
class Plan:
    inflation_pct: float
    inflation_source: str
    inflation_as_of: str
    expected_returns: dict[str, Optional[float]] = field(default_factory=dict)
    monthly_surplus_vnd: Optional[float] = None
    monthly_expense_vnd: Optional[float] = None
    goals: list[Goal] = field(default_factory=list)

    @property
    def has_goals(self) -> bool:
        return bool(self.goals)

    def expected_for(self, asset_class: str) -> Optional[float]:
        return self.expected_returns.get(asset_class)


def load_plan(path: Optional[Path] = None) -> Plan:
    raw: dict[str, Any] = {}
    p = path or PLAN_PATH
    if p.exists():
        with p.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    infl = raw.get("inflation") or {}
    cf = raw.get("cash_flow") or {}
    goals = []
    for g in raw.get("goals") or []:
        if not g or g.get("target_today_vnd") is None or g.get("target_year") is None:
            continue
        goals.append(Goal(
            name=str(g.get("name") or "Mục tiêu"),
            target_today_vnd=float(g["target_today_vnd"]),
            target_year=int(g["target_year"]),
            priority=int(g.get("priority", 1)),
        ))
    return Plan(
        inflation_pct=float(infl.get("annual_pct") or 0.0),
        inflation_source=str(infl.get("source") or ""),
        inflation_as_of=str(infl.get("as_of") or ""),
        expected_returns=dict(raw.get("expected_returns_nominal_pct") or {}),
        monthly_surplus_vnd=cf.get("monthly_surplus_vnd"),
        monthly_expense_vnd=cf.get("monthly_expense_vnd"),
        goals=sorted(goals, key=lambda x: (x.priority, x.target_year)),
    )


# --- Chiếu danh mục về tương lai -------------------------------------------

@dataclass
class ProjectionRow:
    year_offset: int
    nominal_trieu: float
    real_trieu: float  # quy về sức mua HÔM NAY


def project(
    start_trieu: float, nominal_pct: float, inflation_pct: float, years: int,
    *, monthly_add_trieu: float = 0.0,
) -> list[ProjectionRow]:
    """Chiếu giá trị danh mục theo năm, kèm cột quy về sức mua hôm nay.

    Luôn trả CẢ HAI cột. Chỉ đưa cột danh nghĩa là cách trình bày làm người đọc
    thấy tài sản tăng trong khi sức mua có thể đang giảm.
    """
    rows, value = [], start_trieu
    for y in range(years + 1):
        if y:
            value = value * (1 + nominal_pct / 100) + monthly_add_trieu * 12
        rows.append(ProjectionRow(
            year_offset=y,
            nominal_trieu=value,
            real_trieu=value / (1 + inflation_pct / 100) ** y,
        ))
    return rows


def sensitivity(
    start_trieu: float, inflation_pct: float, years: int,
    *, monthly_add_trieu: float = 0.0,
    rates_pct: Sequence[float] = SENSITIVITY_NOMINAL_PCT,
) -> list[tuple[float, float, float]]:
    """[(lợi_suất_danh_nghĩa, giá_trị_danh_nghĩa, giá_trị_theo_sức_mua_hôm_nay)].

    Dùng khi chủ danh mục CHƯA khai lợi suất kỳ vọng: thay vì chọn hộ một con
    số rồi trình bày nó như sự thật, bày cả dải để thấy kết luận nhạy tới đâu.
    """
    out = []
    for r in rates_pct:
        last = project(start_trieu, r, inflation_pct, years,
                       monthly_add_trieu=monthly_add_trieu)[-1]
        out.append((r, last.nominal_trieu, last.real_trieu))
    return out


# --- Đối chiếu với mục tiêu -------------------------------------------------

@dataclass
class GoalCheck:
    goal: Goal
    years: int
    target_today_trieu: float
    target_nominal_trieu: float  # số tiền DANH NGHĨA cần có tại năm đó
    current_trieu: float
    required_nominal_pct: Optional[float]
    required_real_pct: Optional[float]
    shortfall_today_trieu: float

    @property
    def reachable_note(self) -> str:
        if self.required_nominal_pct is None:
            return "Chưa tính được — thiếu dữ liệu."
        if self.required_nominal_pct <= 0:
            return "Đã đủ bằng tài sản hiện có, không cần lợi suất dương."
        return (f"Cần {self.required_nominal_pct:.2f}%/năm danh nghĩa "
                f"({self.required_real_pct:+.2f}%/năm thực) trên toàn bộ tài sản hiện có.")


def check_goal(goal: Goal, current_trieu: float, plan: Plan, current_year: int) -> GoalCheck:
    """Mục tiêu đòi lợi suất bao nhiêu — tính theo cả hai thang.

    Mục tiêu khai theo SỨC MUA HÔM NAY nên phải quy lên danh nghĩa trước khi so
    với tài sản tương lai. Bỏ bước này là so hai đơn vị khác nhau — lỗi âm thầm
    và luôn lệch về phía lạc quan.
    """
    from planning.real_return import real_pct

    years = goal.years_from(current_year)
    target_today = goal.target_today_vnd / 1_000_000
    target_nominal = target_today * (1 + plan.inflation_pct / 100) ** years

    required_nom: Optional[float] = None
    if current_trieu > 0 and years > 0:
        required_nom = ((target_nominal / current_trieu) ** (1 / years) - 1) * 100
    elif current_trieu > 0 and years == 0:
        required_nom = 0.0 if current_trieu >= target_nominal else float("inf")

    required_real = (real_pct(required_nom, plan.inflation_pct)
                     if required_nom is not None and required_nom != float("inf") else None)
    return GoalCheck(
        goal=goal, years=years,
        target_today_trieu=target_today,
        target_nominal_trieu=target_nominal,
        current_trieu=current_trieu,
        required_nominal_pct=required_nom,
        required_real_pct=required_real,
        shortfall_today_trieu=max(0.0, target_today - current_trieu),
    )


def emergency_fund_months(cash_trieu: float, monthly_expense_vnd: Optional[float]) -> Optional[float]:
    """Quỹ khẩn cấp đủ mấy THÁNG chi tiêu.

    `config/risk_limits.yaml` đang đặt quỹ khẩn cấp tối thiểu 30 tr — một con số
    tuyệt đối, không neo vào chi tiêu thật. 30 tr là 6 tháng với người tiêu 5
    tr/tháng và là 1 tháng với người tiêu 30 tr/tháng; cùng một ngưỡng nhưng hai
    mức an toàn hoàn toàn khác nhau. Trả None khi chưa khai chi tiêu — đó là
    thông tin duy nhất làm ngưỡng kia có nghĩa.
    """
    if not monthly_expense_vnd:
        return None
    return cash_trieu / (monthly_expense_vnd / 1_000_000)

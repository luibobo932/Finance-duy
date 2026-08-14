"""Risk Officer — có quyền BÁC BỎ hoặc GHI ĐÈ hành động do policy_engine đề
xuất. Đây là nơi DUY NHẤT áp các hạn mức rủi ro cứng (config/risk_limits.yaml,
config/decision_rules.yaml) — không nơi nào khác được tự ý cho phép mua
thêm khi đã vượt ngưỡng.

Nguyên tắc: `approved = (final_action == original_action)`. Bất cứ khi nào
Risk Officer đổi hành động so với đề xuất ban đầu, coi là chưa được duyệt
nguyên trạng, dù có "chặn cứng" (veto) hay chỉ "hạ cấp" (downgrade).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .action_mapper import Action, to_vietnamese

# Danh sách rule tên chuẩn theo yêu cầu gốc — dùng làm tài liệu tham chiếu,
# veto_reasons có thể chứa thêm biến thể chi tiết hơn (VD
# "gold_concentration_warning" bên cạnh "gold_concentration_critical").
VETO_RULES = [
    "stale_critical_data",
    "conflicting_critical_sources",
    "gold_concentration_critical",
    "governance_red_flag",
    "insufficient_liquidity",
    "missing_financial_data",
    "abnormal_price_data",
]

# Mức độ SIẾT phơi nhiễm của từng hành động, dùng để giữ một bất biến:
# **tỷ trọng càng vượt ngưỡng, lời khuyên không bao giờ được nhẹ đi**.
#
# Vì sao cần: đo được ngày 14/8, cùng một danh mục vàng —
#     vàng 65% (warning)  + tín hiệu TICH_CUC → CHỐT BỚT
#     vàng 76% (critical) + tín hiệu TICH_CUC → KHÔNG MUA THÊM  ← NHẸ HƠN
#     vàng 76% (critical) + tín hiệu TRUNG_TINH → CHỐT BỚT
# Rủi ro tệ hơn mà lời khuyên dịu đi, và kết quả còn lật theo việc tín hiệu
# thị trường tình cờ là gì. Đó không phải một lựa chọn khẩu vị, đó là lỗi.
EXPOSURE_SEVERITY: dict[str, int] = {
    Action.BUY_SMALL.value: 0,
    Action.DEPOSIT.value: 1,
    Action.HOLD.value: 1,
    Action.WAIT_FOR_CONFIRMATION.value: 2,
    Action.WATCH.value: 2,
    Action.DO_NOT_BUY_MORE.value: 3,
    Action.STAND_ASIDE.value: 4,
    Action.TAKE_PARTIAL_PROFIT.value: 5,
    Action.NO_DECISION.value: 6,
}


def severity(action: str) -> int:
    """Hành động lạ trả -1 để `stricter()` không vô tình coi nó là nghiêm nhất."""
    return EXPOSURE_SEVERITY.get(action, -1)


def stricter(a: str, b: str) -> str:
    """Hành động siết phơi nhiễm mạnh hơn trong hai hành động."""
    return a if severity(a) >= severity(b) else b


@dataclass
class ProposedAction:
    asset: str
    asset_class: str  # "gold" | "equity" | "deposit"
    action: str  # giá trị Action


@dataclass
class RiskContext:
    gold_allocation_pct: Optional[float] = None  # 0-1
    cash_buffer_ok: Optional[bool] = None
    single_stock_pct: Optional[float] = None  # 0-1, tỷ trọng mã đang xét
    total_stock_pct: Optional[float] = None  # 0-1, tổng tỷ trọng cổ phiếu
    governance_status: Optional[str] = None
    data_stale: bool = False
    data_conflicting: bool = False
    data_missing_critical: bool = False
    data_abnormal_price: bool = False


@dataclass
class RiskReview:
    approved: bool
    original_action: str
    final_action: str
    veto_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conditions_to_reconsider: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "original_action": self.original_action,
            "final_action": self.final_action,
            "veto_reasons": self.veto_reasons,
            "warnings": self.warnings,
            "conditions_to_reconsider": self.conditions_to_reconsider,
        }


def _check_data_quality(ctx: RiskContext, rules: dict, veto_reasons: list[str]) -> bool:
    """Trả True nếu có veto dữ liệu — khi đó KHÔNG xét các rule khác nữa,
    hành động cuối luôn là NO_DECISION."""
    dq = rules.get("data_quality", {})
    if dq.get("veto_on_stale_critical_data", True) and ctx.data_stale:
        veto_reasons.append("stale_critical_data")
    if dq.get("veto_on_conflicting_critical_sources", True) and ctx.data_conflicting:
        veto_reasons.append("conflicting_critical_sources")
    if dq.get("veto_on_missing_critical_financial_data", True) and ctx.data_missing_critical:
        veto_reasons.append("missing_financial_data")
    if dq.get("veto_on_abnormal_price_data", True) and ctx.data_abnormal_price:
        veto_reasons.append("abnormal_price_data")
    return len(veto_reasons) > 0


def _apply_gold_rule(proposal: ProposedAction, ctx: RiskContext, limits: dict, rules: dict,
                      veto_reasons: list[str], warnings: list[str], conditions: list[str]) -> str:
    """Rule tập trung vàng — hành động lấy từ `config/decision_rules.yaml`.

    Hai nhánh, vì hai đề xuất khác nhau đặt ra hai câu hỏi khác nhau:

    1) Đề xuất MUA THÊM → câu hỏi "có được mua thêm không?" → trả lời dứt khoát
       KHÔNG MUA THÊM ở mức critical (đúng yêu cầu gốc của chủ dự án), hạ xuống
       CHỐT BỚT ở mức warning.
    2) Đề xuất GIỮ / ĐỨNG NGOÀI mà tỷ trọng ĐÃ vượt critical → câu hỏi "giữ
       nguyên có ổn không?". Trước đây nhánh này bị bỏ trống: rule chỉ chạy khi
       đề xuất là BUY_SMALL, nên vàng 75,1% vẫn ra "GIỮ, tin cậy 92" — ngưỡng
       critical hoá ra chỉ chặn mua chứ không nói được gì khi danh mục đã lệch
       quá xa. Nay nhánh này nâng lên CHỐT BỚT.

    Tắt nhánh (2) bằng `escalate_hold_above_critical: false` nếu chủ danh mục
    thực sự muốn hệ thống chỉ chặn mua và im lặng ở mọi mức tập trung.
    """
    if proposal.asset_class != "gold":
        return proposal.action
    gold_pct = ctx.gold_allocation_pct
    if gold_pct is None:
        return proposal.action

    critical = limits.get("gold_critical", 0.70)
    warning = limits.get("gold_warning", 0.60)
    # Ngưỡng lấy từ risk_limits.yaml, HÀNH ĐỘNG lấy từ decision_rules.yaml —
    # trước đây 3 khoá dưới đây có trong config nhưng không dòng code nào đọc,
    # nên config trông như nguồn sự thật mà thực chất chỉ để trang trí.
    gold_rules = (rules or {}).get("gold") or {}

    if proposal.action == Action.BUY_SMALL.value:
        if gold_pct >= critical:
            veto_reasons.append("gold_concentration_critical")
            conditions.append(f"Chỉ xem xét mua thêm vàng khi tỷ trọng giảm dưới {critical*100:.0f}%")
            blocked = gold_rules.get("above_critical_action", Action.DO_NOT_BUY_MORE.value)
            # Yêu cầu gốc của chủ danh mục — "vàng ≥70% thì không cho phép đề
            # xuất mua thêm" — được giữ nguyên: đề xuất mua ĐÃ bị veto, và câu
            # đó nêu thẳng ở đây nên không mất đi dù hành động cuối mạnh hơn.
            warnings.append(
                f"Vàng đang {gold_pct*100:.0f}% (≥ critical {critical*100:.0f}%) — KHÔNG MUA THÊM vàng"
            )
            # ... nhưng ở mức critical, lời khuyên không được nhẹ hơn mức
            # warning. Lấy hành động siết mạnh hơn giữa hai nấc, thay vì để
            # nấc nặng hơn lại trả kết quả dịu hơn.
            escalated = stricter(blocked, gold_rules.get(
                "above_warning_action", Action.TAKE_PARTIAL_PROFIT.value))
            if escalated != blocked:
                warnings.append(
                    "Ở mức critical, khuyến nghị không được nhẹ hơn ở mức warning — "
                    f"nâng từ {to_vietnamese(blocked)} lên {to_vietnamese(escalated)}"
                )
            return escalated
        if gold_pct >= warning:
            veto_reasons.append("gold_concentration_warning")
            warnings.append(
                f"Vàng đang {gold_pct*100:.0f}% (≥ ngưỡng warning {warning*100:.0f}%) — ưu tiên chốt bớt thay vì mua thêm"
            )
            return gold_rules.get("above_warning_action", Action.TAKE_PARTIAL_PROFIT.value)
        return proposal.action

    # Nhánh (2): đề xuất thụ động trong khi tỷ trọng đã vượt ngưỡng critical
    passive = (Action.HOLD.value, Action.WATCH.value)
    if proposal.action in passive and gold_pct >= critical:
        if not gold_rules.get("escalate_hold_above_critical", True):
            warnings.append(
                f"Vàng đang {gold_pct*100:.0f}% (≥ critical {critical*100:.0f}%) nhưng cấu hình đang tắt "
                "việc tự nâng đề xuất giữ thành chốt bớt (escalate_hold_above_critical: false)"
            )
            return proposal.action
        veto_reasons.append("gold_concentration_critical")
        warnings.append(
            f"Vàng đang {gold_pct*100:.0f}% (≥ critical {critical*100:.0f}%) — giữ nguyên tỷ trọng này "
            "không còn là lựa chọn trung tính, cần giảm tỷ trọng"
        )
        conditions.append(f"Trở lại GIỮ khi tỷ trọng vàng giảm dưới {critical*100:.0f}%")
        return gold_rules.get("concentrated_hold_action", Action.TAKE_PARTIAL_PROFIT.value)
    return proposal.action


def _apply_governance_rule(proposal: ProposedAction, ctx: RiskContext, rules: dict,
                            veto_reasons: list[str], warnings: list[str]) -> str:
    if proposal.asset_class != "equity" or not ctx.governance_status:
        return proposal.action
    eq_rules = rules.get("equity", {})
    block_states = set(eq_rules.get("governance_block_states", []))
    watch_states = set(eq_rules.get("governance_watch_states", []))
    if ctx.governance_status in block_states and proposal.action in (
        Action.BUY_SMALL.value, Action.HOLD.value, Action.WATCH.value,
    ):
        veto_reasons.append("governance_red_flag")
        return Action.STAND_ASIDE.value
    if ctx.governance_status in watch_states:
        warnings.append(f"Trạng thái quản trị đang theo dõi: {ctx.governance_status} — chưa đủ căn cứ chặn hẳn")
    return proposal.action


def _apply_liquidity_rule(proposal: ProposedAction, ctx: RiskContext,
                           veto_reasons: list[str], warnings: list[str]) -> str:
    if ctx.cash_buffer_ok is False and proposal.action in (Action.BUY_SMALL.value, Action.DEPOSIT.value):
        veto_reasons.append("insufficient_liquidity")
        warnings.append("Tiền mặt dưới quỹ khẩn cấp tối thiểu — ưu tiên giữ thanh khoản")
        return Action.WATCH.value
    return proposal.action


def _apply_stock_concentration_rule(proposal: ProposedAction, ctx: RiskContext, limits: dict,
                                     veto_reasons: list[str], warnings: list[str]) -> str:
    if proposal.asset_class != "equity" or proposal.action != Action.BUY_SMALL.value:
        return proposal.action
    single_max = limits.get("single_stock_max")
    total_max = limits.get("total_stock_max")
    if single_max is not None and ctx.single_stock_pct is not None and ctx.single_stock_pct >= single_max:
        veto_reasons.append("single_stock_concentration")
        warnings.append(f"Tỷ trọng {proposal.asset} đã ≥ {single_max*100:.0f}% giới hạn 1 mã")
        return Action.DO_NOT_BUY_MORE.value
    if total_max is not None and ctx.total_stock_pct is not None and ctx.total_stock_pct >= total_max:
        veto_reasons.append("total_stock_concentration")
        warnings.append(f"Tổng tỷ trọng cổ phiếu đã ≥ {total_max*100:.0f}% giới hạn")
        return Action.DO_NOT_BUY_MORE.value
    return proposal.action


def review(proposal: ProposedAction, ctx: RiskContext, limits: dict, rules: dict) -> RiskReview:
    """Điểm vào duy nhất — luôn gọi hàm này trước khi hiển thị bất kỳ hành
    động nào cho người dùng."""
    veto_reasons: list[str] = []
    warnings: list[str] = []
    conditions: list[str] = []

    if _check_data_quality(ctx, rules, veto_reasons):
        return RiskReview(
            approved=False,
            original_action=proposal.action,
            final_action=Action.NO_DECISION.value,
            veto_reasons=veto_reasons,
            warnings=warnings,
            conditions_to_reconsider=["Chờ dữ liệu đủ tin cậy (không stale/không xung đột nguồn) trước khi ra quyết định"],
        )

    action = proposal.action
    action = _apply_gold_rule(proposal, ctx, limits, rules, veto_reasons, warnings, conditions)
    proposal_after_gold = ProposedAction(proposal.asset, proposal.asset_class, action)
    action = _apply_governance_rule(proposal_after_gold, ctx, rules, veto_reasons, warnings)
    proposal_after_gov = ProposedAction(proposal.asset, proposal.asset_class, action)
    action = _apply_stock_concentration_rule(proposal_after_gov, ctx, limits, veto_reasons, warnings)
    proposal_after_stock = ProposedAction(proposal.asset, proposal.asset_class, action)
    action = _apply_liquidity_rule(proposal_after_stock, ctx, veto_reasons, warnings)

    approved = action == proposal.action
    return RiskReview(
        approved=approved,
        original_action=proposal.action,
        final_action=action,
        veto_reasons=veto_reasons,
        warnings=warnings,
        conditions_to_reconsider=conditions,
    )

"""Decision Engine — kết hợp tín hiệu thị trường (xu hướng kỹ thuật, định
giá, quản trị) thành 1 đề xuất hành động ban đầu, sau đó BẮT BUỘC đưa qua
decision/risk_officer.py trước khi trả kết quả cuối cùng.

Đây là nơi DUY NHẤT trong hệ thống tạo ra kết luận GIỮ/CHỐT BỚT/... — bản
tin (Phase 8) chỉ được HIỂN THỊ kết quả từ đây, không được tự viết kết luận
khác.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .action_mapper import Action, to_vietnamese
from .confidence_score import compute_confidence, signal_agreement_from_labels
from .risk_officer import ProposedAction, RiskContext, review


@dataclass
class DecisionInput:
    asset: str
    asset_class: str  # "gold" | "equity" | "deposit"
    trend_label: Optional[str] = None  # TICH_CUC/TIEU_CUC/TRUNG_TINH
    fundamental_label: Optional[str] = None  # cùng thang TICH_CUC/TIEU_CUC/TRUNG_TINH, từ valuation
    flow_label: Optional[str] = None  # dòng tiền/khối ngoại, cùng thang
    margin_of_safety_pct: Optional[float] = None
    governance_status: Optional[str] = None
    data_completeness_pct: float = 100.0
    data_freshness_score: float = 100.0
    source_conflict_penalty: float = 0.0
    risk_level_penalty: float = 0.0
    historical_accuracy_pct: Optional[float] = None


def derive_initial_action(inp: DecisionInput) -> str:
    """Đề xuất hành động BAN ĐẦU chỉ từ tín hiệu THỊ TRƯỜNG (chưa xét tỷ
    trọng danh mục/rủi ro — đó là việc của risk_officer ở bước sau).
    """
    if inp.asset_class == "deposit":
        return Action.DEPOSIT.value

    if inp.asset_class == "gold":
        if inp.trend_label == "TICH_CUC":
            return Action.BUY_SMALL.value
        if inp.trend_label == "TIEU_CUC":
            return Action.TAKE_PARTIAL_PROFIT.value
        if inp.trend_label == "TRUNG_TINH":
            return Action.HOLD.value
        return Action.WATCH.value  # chưa có tín hiệu xu hướng

    if inp.asset_class == "equity":
        if inp.trend_label == "TIEU_CUC" or inp.fundamental_label == "TIEU_CUC":
            return Action.WAIT_FOR_CONFIRMATION.value
        if (
            inp.margin_of_safety_pct is not None
            and inp.margin_of_safety_pct > 20
            and inp.trend_label != "TIEU_CUC"
        ):
            return Action.BUY_SMALL.value
        if inp.trend_label == "TICH_CUC" or inp.fundamental_label == "TICH_CUC":
            return Action.HOLD.value
        return Action.WATCH.value

    return Action.WATCH.value


def decide(inp: DecisionInput, ctx: RiskContext, limits: dict, rules: dict) -> dict:
    """Điểm vào chính của Decision Engine — trả dict đúng format chuẩn:
    {asset, action, confidence, reasons, risks, conditions_to_change,
     data_quality, risk_veto} (+ action_vi bổ sung, không phá schema gốc).
    """
    initial_action = derive_initial_action(inp)
    proposal = ProposedAction(asset=inp.asset, asset_class=inp.asset_class, action=initial_action)
    rr = review(proposal, ctx, limits, rules)

    agreement = signal_agreement_from_labels(inp.trend_label, inp.fundamental_label, inp.flow_label)
    conflict_penalty = inp.source_conflict_penalty + (30 if rr.veto_reasons and "conflicting_critical_sources" in rr.veto_reasons else 0)
    confidence = compute_confidence(
        data_completeness_pct=inp.data_completeness_pct,
        data_freshness_score=inp.data_freshness_score,
        signal_agreement_pct=agreement,
        historical_accuracy_pct=inp.historical_accuracy_pct,
        source_conflict_penalty=conflict_penalty,
        risk_level_penalty=inp.risk_level_penalty,
    )

    reasons = []
    if inp.trend_label:
        reasons.append(f"Xu hướng kỹ thuật: {inp.trend_label}")
    if inp.fundamental_label:
        reasons.append(f"Định giá/cơ bản: {inp.fundamental_label}")
    if inp.flow_label:
        reasons.append(f"Dòng tiền: {inp.flow_label}")
    if rr.veto_reasons:
        reasons.append("Risk Officer điều chỉnh: " + ", ".join(rr.veto_reasons))

    data_quality = "GOOD"
    if ctx.data_stale or ctx.data_conflicting or ctx.data_missing_critical or ctx.data_abnormal_price:
        data_quality = "POOR"
    elif inp.data_completeness_pct < 80 or inp.data_freshness_score < 80:
        data_quality = "FAIR"

    # Confidence PHẢI nhất quán với data_quality — không được báo "POOR" mà
    # vẫn cho điểm tin cậy cao chỉ vì các tín hiệu khác (đồng thuận xu hướng...)
    # trùng hợp cao. Đây là ràng buộc an toàn, không phải trọng số bổ sung.
    if data_quality == "POOR":
        confidence = min(confidence, 30)
    elif data_quality == "FAIR":
        confidence = min(confidence, 70)

    return {
        "asset": inp.asset,
        "action": rr.final_action,
        "action_vi": to_vietnamese(rr.final_action),
        "confidence": confidence,
        "reasons": reasons,
        "risks": list(rr.warnings),
        "conditions_to_change": list(rr.conditions_to_reconsider),
        "data_quality": data_quality,
        "risk_veto": not rr.approved,
    }

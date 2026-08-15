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
    # Có đang NẮM GIỮ tài sản này không. Mặc định False vì watchlist là trạng
    # thái phổ biến hơn ở danh mục này (đã bán hết cổ phiếu 19/7).
    has_position: bool = False
    # None = CHƯA ĐO, không phải "hoàn hảo". Trước đây hai trường này mặc định
    # 100.0 và không caller nào truyền giá trị khác, nên 45% trọng số điểm tin
    # cậy là số cứng và nhánh hạ cấp `data_quality = "FAIR"` không bao giờ chạy
    # được — kết quả là cả 13 quyết định đã ghi đều đúng một điểm 92/GOOD.
    # Chưa đo thì dùng trung tính 50 (xem UNMEASURED_QUALITY_SCORE): quên đo
    # phải LÀM GIẢM điểm chứ không được thưởng điểm tuyệt đối.
    data_completeness_pct: Optional[float] = None
    data_freshness_score: Optional[float] = None
    source_conflict_penalty: float = 0.0
    risk_level_penalty: float = 0.0
    historical_accuracy_pct: Optional[float] = None


# Điểm dùng khi chất lượng dữ liệu chưa được đo. Trung tính, KHÔNG phải 100 —
# "chưa kiểm tra" không bao giờ được đọc thành "đã kiểm tra và hoàn hảo".
UNMEASURED_QUALITY_SCORE = 50.0


def _measured_or_neutral(value: Optional[float]) -> float:
    return UNMEASURED_QUALITY_SCORE if value is None else float(value)


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
            # KHÔNG thể "GIỮ" thứ mình không nắm giữ. Chủ danh mục đã bán hết
            # cổ phiếu (config/portfolio.yaml: positions rỗng) nên VCB/CTD chỉ
            # là danh sách theo dõi. Trả "GIỮ" cho một mã không có vị thế là
            # lời khuyên không thực hiện được — lỗi chỉ lộ ra khi nhánh equity
            # được đem ra dùng thật, và nó vừa được đem ra dùng thật.
            return Action.HOLD.value if inp.has_position else Action.WATCH.value
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
    completeness = _measured_or_neutral(inp.data_completeness_pct)
    freshness = _measured_or_neutral(inp.data_freshness_score)
    conflict_penalty = inp.source_conflict_penalty + (30 if rr.veto_reasons and "conflicting_critical_sources" in rr.veto_reasons else 0)
    confidence = compute_confidence(
        data_completeness_pct=completeness,
        data_freshness_score=freshness,
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
    if inp.data_completeness_pct is None or inp.data_freshness_score is None:
        reasons.append(
            f"Chất lượng dữ liệu CHƯA ĐO — dùng trung tính {UNMEASURED_QUALITY_SCORE:.0f}/100 "
            "(gọi analytics.data_quality.assess_gold() để đo thật)"
        )
    else:
        reasons.append(f"Dữ liệu: đầy đủ {completeness:.0f}/100 · độ mới {freshness:.0f}/100")
    if len([l for l in (inp.trend_label, inp.fundamental_label, inp.flow_label) if l]) < 2:
        reasons.append("Chỉ có 1 nhóm tín hiệu — chưa đo được đồng thuận, dùng trung tính 50")

    data_quality = "GOOD"
    if ctx.data_stale or ctx.data_conflicting or ctx.data_missing_critical or ctx.data_abnormal_price:
        data_quality = "POOR"
    elif completeness < 80 or freshness < 80:
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

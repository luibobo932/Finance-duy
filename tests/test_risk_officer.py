"""Test cho decision/risk_officer.py — phần quan trọng nhất của toàn hệ
thống (Phase 7). Kịch bản chính lấy TRỰC TIẾP từ tài sản thật của chủ dự án
(vàng 74,7%) và ví dụ gốc chủ dự án đưa ra."""
from decision.action_mapper import Action
from decision.risk_officer import ProposedAction, RiskContext, review
from portfolio.loader import load_decision_rules, load_risk_limits

LIMITS = load_risk_limits()
RULES = load_decision_rules()


def test_gold_critical_blocks_buy_with_real_portfolio_allocation():
    # Đúng tài sản thật của chủ dự án: vàng 74.7% > ngưỡng critical 70%
    proposal = ProposedAction(asset="XAUUSD", asset_class="gold", action=Action.BUY_SMALL.value)
    ctx = RiskContext(gold_allocation_pct=0.747)
    rr = review(proposal, ctx, LIMITS, RULES)
    assert rr.approved is False
    assert rr.final_action == Action.DO_NOT_BUY_MORE.value
    assert "gold_concentration_critical" in rr.veto_reasons


def test_gold_warning_downgrades_to_take_partial_profit():
    proposal = ProposedAction(asset="XAUUSD", asset_class="gold", action=Action.BUY_SMALL.value)
    ctx = RiskContext(gold_allocation_pct=0.65)  # >=60% warning, <70% critical
    rr = review(proposal, ctx, LIMITS, RULES)
    assert rr.approved is False
    assert rr.final_action == Action.TAKE_PARTIAL_PROFIT.value
    assert "gold_concentration_warning" in rr.veto_reasons


def test_gold_below_warning_allows_buy():
    proposal = ProposedAction(asset="XAUUSD", asset_class="gold", action=Action.BUY_SMALL.value)
    ctx = RiskContext(gold_allocation_pct=0.40)
    rr = review(proposal, ctx, LIMITS, RULES)
    assert rr.approved is True
    assert rr.final_action == Action.BUY_SMALL.value
    assert rr.veto_reasons == []


def test_gold_take_partial_profit_never_vetoed_regardless_of_allocation():
    # Chốt bớt luôn được phép, không cần chặn dù tỷ trọng cao
    proposal = ProposedAction(asset="XAUUSD", asset_class="gold", action=Action.TAKE_PARTIAL_PROFIT.value)
    ctx = RiskContext(gold_allocation_pct=0.90)
    rr = review(proposal, ctx, LIMITS, RULES)
    assert rr.approved is True


def test_stale_data_forces_no_decision_regardless_of_other_factors():
    proposal = ProposedAction(asset="CTD", asset_class="equity", action=Action.BUY_SMALL.value)
    ctx = RiskContext(data_stale=True, gold_allocation_pct=0.10)  # các yếu tố khác đều "an toàn"
    rr = review(proposal, ctx, LIMITS, RULES)
    assert rr.approved is False
    assert rr.final_action == Action.NO_DECISION.value
    assert "stale_critical_data" in rr.veto_reasons


def test_conflicting_sources_forces_no_decision():
    proposal = ProposedAction(asset="XAUUSD", asset_class="gold", action=Action.HOLD.value)
    ctx = RiskContext(data_conflicting=True)
    rr = review(proposal, ctx, LIMITS, RULES)
    assert rr.final_action == Action.NO_DECISION.value
    assert "conflicting_critical_sources" in rr.veto_reasons


def test_missing_critical_data_forces_no_decision():
    ctx = RiskContext(data_missing_critical=True)
    rr = review(ProposedAction("VCB", "equity", Action.WATCH.value), ctx, LIMITS, RULES)
    assert rr.final_action == Action.NO_DECISION.value


def test_abnormal_price_forces_no_decision():
    ctx = RiskContext(data_abnormal_price=True)
    rr = review(ProposedAction("VCB", "equity", Action.BUY_SMALL.value), ctx, LIMITS, RULES)
    assert rr.final_action == Action.NO_DECISION.value


def test_governance_indicted_blocks_buy_proposal():
    proposal = ProposedAction(asset="CTD", asset_class="equity", action=Action.BUY_SMALL.value)
    ctx = RiskContext(governance_status="INDICTED")
    rr = review(proposal, ctx, LIMITS, RULES)
    assert rr.approved is False
    assert rr.final_action == Action.STAND_ASIDE.value
    assert "governance_red_flag" in rr.veto_reasons


def test_governance_investigation_opened_blocks_buy_proposal():
    proposal = ProposedAction(asset="CTD", asset_class="equity", action=Action.HOLD.value)
    ctx = RiskContext(governance_status="INVESTIGATION_OPENED")
    rr = review(proposal, ctx, LIMITS, RULES)
    assert rr.final_action == Action.STAND_ASIDE.value


def test_governance_watch_state_does_not_block():
    # Đúng yêu cầu gốc: 'đang xác minh'/'mời làm việc' KHÔNG được chặn hẳn
    proposal = ProposedAction(asset="CTD", asset_class="equity", action=Action.BUY_SMALL.value)
    ctx = RiskContext(governance_status="UNDER_VERIFICATION")
    rr = review(proposal, ctx, LIMITS, RULES)
    assert rr.approved is True
    assert rr.final_action == Action.BUY_SMALL.value
    assert len(rr.warnings) > 0  # vẫn cảnh báo, nhưng không chặn


def test_governance_none_status_no_effect():
    proposal = ProposedAction(asset="CTD", asset_class="equity", action=Action.BUY_SMALL.value)
    ctx = RiskContext(governance_status="NONE")
    rr = review(proposal, ctx, LIMITS, RULES)
    assert rr.approved is True


def test_insufficient_liquidity_blocks_buy_and_deposit():
    ctx = RiskContext(cash_buffer_ok=False)
    rr_buy = review(ProposedAction("CTD", "equity", Action.BUY_SMALL.value), ctx, LIMITS, RULES)
    assert rr_buy.final_action == Action.WATCH.value
    assert "insufficient_liquidity" in rr_buy.veto_reasons

    rr_deposit = review(ProposedAction("savings", "deposit", Action.DEPOSIT.value), ctx, LIMITS, RULES)
    assert "insufficient_liquidity" in rr_deposit.veto_reasons


def test_liquidity_ok_does_not_block():
    ctx = RiskContext(cash_buffer_ok=True)
    rr = review(ProposedAction("savings", "deposit", Action.DEPOSIT.value), ctx, LIMITS, RULES)
    assert rr.approved is True


def test_single_stock_concentration_blocks_buy():
    ctx = RiskContext(single_stock_pct=0.15)  # >= single_stock_max 0.10
    rr = review(ProposedAction("VCB", "equity", Action.BUY_SMALL.value), ctx, LIMITS, RULES)
    assert rr.approved is False
    assert rr.final_action == Action.DO_NOT_BUY_MORE.value
    assert "single_stock_concentration" in rr.veto_reasons


def test_total_stock_concentration_blocks_buy():
    ctx = RiskContext(total_stock_pct=0.25)  # >= total_stock_max 0.20
    rr = review(ProposedAction("VCB", "equity", Action.BUY_SMALL.value), ctx, LIMITS, RULES)
    assert rr.approved is False
    assert "total_stock_concentration" in rr.veto_reasons


def test_stock_concentration_within_limits_allows_buy():
    ctx = RiskContext(single_stock_pct=0.05, total_stock_pct=0.10)
    rr = review(ProposedAction("VCB", "equity", Action.BUY_SMALL.value), ctx, LIMITS, RULES)
    assert rr.approved is True


def test_empty_context_no_veto_for_neutral_action():
    ctx = RiskContext()
    rr = review(ProposedAction("VCB", "equity", Action.WATCH.value), ctx, LIMITS, RULES)
    assert rr.approved is True
    assert rr.veto_reasons == []


def test_veto_rules_list_matches_spec_names():
    from decision.risk_officer import VETO_RULES

    expected = {
        "stale_critical_data", "conflicting_critical_sources", "gold_concentration_critical",
        "governance_red_flag", "insufficient_liquidity", "missing_financial_data", "abnormal_price_data",
    }
    assert expected.issubset(set(VETO_RULES))

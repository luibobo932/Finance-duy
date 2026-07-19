"""Test cho decision/{confidence_score,policy_engine,action_mapper}.py (Phase 7)."""
from decision.action_mapper import Action, INSUFFICIENT_DATA_MESSAGE, is_valid_action, to_vietnamese
from decision.confidence_score import WEIGHTS, compute_confidence, signal_agreement_from_labels
from decision.policy_engine import DecisionInput, decide, derive_initial_action
from decision.risk_officer import RiskContext
from portfolio.loader import load_decision_rules, load_risk_limits

LIMITS = load_risk_limits()
RULES = load_decision_rules()


# ---- action_mapper.py ----


def test_all_actions_have_vietnamese_label():
    for a in Action:
        assert to_vietnamese(a.value) != a.value or a.value == "UNKNOWN_ACTION"


def test_seven_required_vietnamese_labels_present():
    required = {"GIỮ", "CHỐT BỚT", "KHÔNG MUA THÊM", "GỬI TIẾT KIỆM", "MUA THĂM DÒ", "ĐỨNG NGOÀI", "CHỜ XÁC NHẬN"}
    from decision.action_mapper import VIETNAMESE_LABEL

    assert required.issubset(set(VIETNAMESE_LABEL.values()))


def test_no_decision_maps_to_insufficient_data_message():
    assert to_vietnamese(Action.NO_DECISION.value) == INSUFFICIENT_DATA_MESSAGE


def test_is_valid_action():
    assert is_valid_action("HOLD") is True
    assert is_valid_action("BUY_EVERYTHING") is False


# ---- confidence_score.py ----


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_compute_confidence_perfect_inputs_near_100():
    c = compute_confidence(100, 100, 100, historical_accuracy_pct=100)
    assert c == 100


def test_compute_confidence_worst_case_inputs_is_zero():
    c = compute_confidence(0, 0, 0, historical_accuracy_pct=0,
                            source_conflict_penalty=100, risk_level_penalty=100)
    assert c == 0


def test_compute_confidence_neutral_without_history():
    c1 = compute_confidence(80, 80, 80)
    c2 = compute_confidence(80, 80, 80, historical_accuracy_pct=50)
    assert c1 == c2  # None phải tương đương giá trị trung tính 50


def test_compute_confidence_penalized_by_conflict():
    base = compute_confidence(90, 90, 90)
    penalized = compute_confidence(90, 90, 90, source_conflict_penalty=50)
    assert penalized < base


def test_signal_agreement_full_consensus():
    assert signal_agreement_from_labels("TICH_CUC", "TICH_CUC", "TICH_CUC") == 100.0


def test_signal_agreement_split():
    assert signal_agreement_from_labels("TICH_CUC", "TIEU_CUC", "TICH_CUC") == round(2 / 3 * 100, 1)


def test_signal_agreement_none_labels_neutral():
    assert signal_agreement_from_labels(None, None) == 50.0


def test_signal_agreement_ignores_none_among_present():
    assert signal_agreement_from_labels("TICH_CUC", None, "TICH_CUC") == 100.0


# ---- policy_engine.py ----


def test_derive_initial_action_gold_positive_trend():
    inp = DecisionInput(asset="XAUUSD", asset_class="gold", trend_label="TICH_CUC")
    assert derive_initial_action(inp) == Action.BUY_SMALL.value


def test_derive_initial_action_gold_negative_trend():
    inp = DecisionInput(asset="XAUUSD", asset_class="gold", trend_label="TIEU_CUC")
    assert derive_initial_action(inp) == Action.TAKE_PARTIAL_PROFIT.value


def test_derive_initial_action_deposit_always_deposit():
    inp = DecisionInput(asset="savings", asset_class="deposit")
    assert derive_initial_action(inp) == Action.DEPOSIT.value


def test_derive_initial_action_equity_margin_of_safety_triggers_buy():
    inp = DecisionInput(asset="REE", asset_class="equity", trend_label="TRUNG_TINH", margin_of_safety_pct=30)
    assert derive_initial_action(inp) == Action.BUY_SMALL.value


def test_derive_initial_action_equity_negative_trend_waits():
    inp = DecisionInput(asset="CTD", asset_class="equity", trend_label="TIEU_CUC")
    assert derive_initial_action(inp) == Action.WAIT_FOR_CONFIRMATION.value


def test_decide_end_to_end_blocks_gold_at_real_portfolio_allocation():
    inp = DecisionInput(asset="XAUUSD", asset_class="gold", trend_label="TICH_CUC")
    ctx = RiskContext(gold_allocation_pct=0.747)  # tài sản thật của chủ dự án
    d = decide(inp, ctx, LIMITS, RULES)
    assert d["action"] == Action.DO_NOT_BUY_MORE.value
    assert d["action_vi"] == "KHÔNG MUA THÊM"
    assert d["risk_veto"] is True
    assert d["data_quality"] == "GOOD"


def test_decide_output_has_all_required_keys():
    inp = DecisionInput(asset="VCB", asset_class="equity")
    ctx = RiskContext()
    d = decide(inp, ctx, LIMITS, RULES)
    for key in ("asset", "action", "confidence", "reasons", "risks", "conditions_to_change", "data_quality", "risk_veto"):
        assert key in d


def test_decide_confidence_consistent_with_poor_data_quality():
    inp = DecisionInput(asset="CTD", asset_class="equity", trend_label="TIEU_CUC")
    ctx = RiskContext(data_stale=True)
    d = decide(inp, ctx, LIMITS, RULES)
    assert d["data_quality"] == "POOR"
    assert d["confidence"] <= 30  # không được báo tin cậy cao khi dữ liệu tồi


def test_decide_stale_data_returns_insufficient_data_message():
    inp = DecisionInput(asset="VCB", asset_class="equity")
    ctx = RiskContext(data_stale=True)
    d = decide(inp, ctx, LIMITS, RULES)
    assert d["action_vi"] == INSUFFICIENT_DATA_MESSAGE


def test_decide_confidence_always_within_0_100():
    inp = DecisionInput(asset="X", asset_class="equity", data_completeness_pct=150, data_freshness_score=-10)
    d = decide(inp, RiskContext(), LIMITS, RULES)
    assert 0 <= d["confidence"] <= 100

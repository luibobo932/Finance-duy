"""Test cho decision/risk_officer.py — phần quan trọng nhất của toàn hệ
thống (Phase 7). Kịch bản chính lấy TRỰC TIẾP từ tài sản thật của chủ dự án
(vàng 74,7%) và ví dụ gốc chủ dự án đưa ra."""
from decision.action_mapper import Action
from decision.risk_officer import ProposedAction, RiskContext, review, severity
from portfolio.loader import load_decision_rules, load_risk_limits

LIMITS = load_risk_limits()
RULES = load_decision_rules()


def test_gold_critical_blocks_buy_with_real_portfolio_allocation():
    """Yêu cầu gốc của chủ dự án: vàng ≥70% thì KHÔNG cho phép đề xuất mua thêm.

    Kiểm bằng thứ thực sự thể hiện điều đó — đề xuất mua bị veto và câu "KHÔNG
    MUA THÊM" được nói ra — chứ không neo vào đúng một mã hành động, vì hành
    động cuối được phép NGHIÊM HƠN (xem test bất biến đơn điệu bên dưới).
    """
    proposal = ProposedAction(asset="XAUUSD", asset_class="gold", action=Action.BUY_SMALL.value)
    ctx = RiskContext(gold_allocation_pct=0.747)
    rr = review(proposal, ctx, LIMITS, RULES)
    assert rr.approved is False
    assert "gold_concentration_critical" in rr.veto_reasons
    assert any("KHÔNG MUA THÊM" in w for w in rr.warnings)
    assert severity(rr.final_action) >= severity(Action.DO_NOT_BUY_MORE.value)


def test_critical_KHONG_duoc_nhe_hon_warning():
    """Bất biến: tỷ trọng càng vượt ngưỡng, khuyến nghị không bao giờ nhẹ đi.

    Đo được ngày 14/8 trước khi sửa: vàng 65% ra CHỐT BỚT còn vàng 76% chỉ ra
    KHÔNG MUA THÊM — rủi ro tệ hơn mà lời khuyên dịu đi.
    """
    buy = ProposedAction(asset="XAUUSD", asset_class="gold", action=Action.BUY_SMALL.value)
    o_warning = review(buy, RiskContext(gold_allocation_pct=0.65), LIMITS, RULES)
    o_critical = review(buy, RiskContext(gold_allocation_pct=0.76), LIMITS, RULES)
    assert severity(o_critical.final_action) >= severity(o_warning.final_action)


def test_bat_bien_dung_o_MOI_muc_ty_trong():
    buy = ProposedAction(asset="XAUUSD", asset_class="gold", action=Action.BUY_SMALL.value)
    levels = [0.30, 0.55, 0.61, 0.65, 0.69, 0.70, 0.76, 0.90]
    sevs = [severity(review(buy, RiskContext(gold_allocation_pct=p), LIMITS, RULES).final_action)
            for p in levels]
    assert sevs == sorted(sevs), f"khuyến nghị dịu đi khi tỷ trọng tăng: {list(zip(levels, sevs))}"


def test_tin_hieu_thi_truong_KHONG_duoc_lam_nhe_khuyen_nghi_o_critical():
    """Cùng một tỷ trọng critical, tín hiệu tăng giá không được ra lời khuyên
    nhẹ hơn tín hiệu đi ngang — vàng tăng chính là thứ làm tập trung tệ thêm."""
    ctx = RiskContext(gold_allocation_pct=0.76)
    from_buy = review(ProposedAction("XAUUSD", "gold", Action.BUY_SMALL.value), ctx, LIMITS, RULES)
    from_hold = review(ProposedAction("XAUUSD", "gold", Action.HOLD.value), ctx, LIMITS, RULES)
    assert severity(from_buy.final_action) >= severity(from_hold.final_action)


def test_cau_hinh_mau_thuan_duoc_nang_len_VA_noi_ro():
    """Cấu hình đặt nấc critical nhẹ hơn nấc warning thì phải được nâng lên,
    và việc nâng phải hiện ra chứ không âm thầm."""
    rules = {**RULES, "gold": {**RULES.get("gold", {}),
                               "above_critical_action": Action.DO_NOT_BUY_MORE.value,
                               "above_warning_action": Action.TAKE_PARTIAL_PROFIT.value}}
    rr = review(ProposedAction("XAUUSD", "gold", Action.BUY_SMALL.value),
                RiskContext(gold_allocation_pct=0.76), LIMITS, rules)
    assert rr.final_action == Action.TAKE_PARTIAL_PROFIT.value
    assert any("không được nhẹ hơn" in w for w in rr.warnings)


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


# --- Nhánh "giữ nguyên khi đã quá tập trung" (lỗi gốc phát hiện 12/8) -------
# Trước bản sửa này, rule tập trung vàng chỉ chạy khi đề xuất là BUY_SMALL,
# nên vàng 75,1% vẫn cho ra "GIỮ, tin cậy 92" suốt 6 bản tin liên tiếp trong
# khi bản tin viết tay lại khuyên CHỐT BỚT — máy và người nói ngược nhau.

def test_gold_critical_nang_GIU_thanh_CHOT_BOT():
    proposal = ProposedAction(asset="XAUUSD", asset_class="gold", action=Action.HOLD.value)
    ctx = RiskContext(gold_allocation_pct=0.751)  # đúng tỷ trọng thật ngày 22/7
    rr = review(proposal, ctx, LIMITS, RULES)
    assert rr.final_action == Action.TAKE_PARTIAL_PROFIT.value
    assert rr.approved is False
    assert "gold_concentration_critical" in rr.veto_reasons
    assert any("giữ nguyên tỷ trọng này" in w for w in rr.warnings)


def test_gold_critical_nang_ca_DUNG_NGOAI():
    proposal = ProposedAction(asset="XAUUSD", asset_class="gold", action=Action.WATCH.value)
    rr = review(proposal, RiskContext(gold_allocation_pct=0.80), LIMITS, RULES)
    assert rr.final_action == Action.TAKE_PARTIAL_PROFIT.value


def test_gold_duoi_critical_thi_GIU_van_la_GIU():
    """Chỉ vượt warning (65%) mà đề xuất là giữ thì KHÔNG nâng cấp — nhánh
    này chỉ kích hoạt từ mức critical, tránh nhắc chốt bớt quá sớm."""
    proposal = ProposedAction(asset="XAUUSD", asset_class="gold", action=Action.HOLD.value)
    rr = review(proposal, RiskContext(gold_allocation_pct=0.65), LIMITS, RULES)
    assert rr.final_action == Action.HOLD.value
    assert rr.approved is True


def test_co_the_TAT_nhanh_nang_cap_bang_config():
    """Chủ danh mục chấp nhận mức tập trung -> tắt được, nhưng vẫn phải thấy
    cảnh báo để việc tắt là lựa chọn hiển thị chứ không phải im lặng."""
    rules = {**RULES, "gold": {**RULES.get("gold", {}), "escalate_hold_above_critical": False}}
    proposal = ProposedAction(asset="XAUUSD", asset_class="gold", action=Action.HOLD.value)
    rr = review(proposal, RiskContext(gold_allocation_pct=0.751), LIMITS, rules)
    assert rr.final_action == Action.HOLD.value
    assert rr.approved is True
    assert any("escalate_hold_above_critical" in w for w in rr.warnings)


def test_hanh_dong_doc_tu_config_khong_hard_code():
    """3 khoá trong decision_rules.yaml trước đây KHÔNG được code nào đọc.
    Đổi giá trị trong config phải đổi được kết quả thật."""
    rules = {**RULES, "gold": {**RULES.get("gold", {}),
                               "above_critical_action": Action.STAND_ASIDE.value,
                               "above_warning_action": Action.WATCH.value}}
    proposal = ProposedAction(asset="XAUUSD", asset_class="gold", action=Action.BUY_SMALL.value)
    rr = review(proposal, RiskContext(gold_allocation_pct=0.90), LIMITS, rules)
    assert rr.final_action == Action.STAND_ASIDE.value


def test_thieu_ty_trong_vang_thi_khong_doan():
    """Không biết tỷ trọng -> không được tự suy ra là đang quá tập trung."""
    proposal = ProposedAction(asset="XAUUSD", asset_class="gold", action=Action.HOLD.value)
    rr = review(proposal, RiskContext(gold_allocation_pct=None), LIMITS, RULES)
    assert rr.final_action == Action.HOLD.value
    assert rr.approved is True

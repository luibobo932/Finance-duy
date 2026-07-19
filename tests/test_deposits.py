"""Test cho deposits/ — loại lãi suất không hợp lệ, xếp hạng, chia kỳ hạn (Phase 5)."""
from datetime import date

from deposits.ranking import DEFAULT_MAX_DEPOSIT_FOR_RETAIL_VND, is_excluded, load_normalized, rank, top_by_term
from deposits.schema import DepositRate
from deposits.strategy import DepositAllocation, split_strategy, total_expected_interest_vnd


def test_best_rate_pct_picks_higher_of_online_counter():
    dr = DepositRate(bank="X", term_months=12, rate_online=7.4, rate_counter=7.1)
    assert dr.best_rate_pct == 7.4
    assert dr.best_channel == "online"


def test_best_rate_pct_none_when_no_rates():
    dr = DepositRate(bank="X", term_months=12)
    assert dr.best_rate_pct is None
    assert dr.best_channel is None


def test_is_excluded_for_huge_minimum_deposit():
    dr = DepositRate(bank="HDBank", term_months=13, rate_counter=7.6, min_deposit_vnd=500_000_000_000)
    excluded, reason = is_excluded(dr)
    assert excluded is True
    assert "500" in reason or "tối thiểu" in reason


def test_is_excluded_for_vip_keyword():
    dr = DepositRate(bank="X", term_months=12, rate_online=9.0, conditions="Chỉ áp dụng cho khách VIP")
    excluded, reason = is_excluded(dr)
    assert excluded is True


def test_is_excluded_for_bancassurance():
    dr = DepositRate(bank="X", term_months=12, rate_online=9.0, conditions="Kèm bảo hiểm nhân thọ")
    assert is_excluded(dr)[0] is True


def test_not_excluded_for_normal_retail_rate():
    dr = DepositRate(bank="Cake by VPBank", term_months=12, rate_online=7.4, min_deposit_vnd=1_000_000)
    excluded, reason = is_excluded(dr)
    assert excluded is False
    assert reason is None


def test_is_excluded_missing_rate_data():
    dr = DepositRate(bank="X", term_months=12)
    assert is_excluded(dr)[0] is True


def test_rank_sorts_descending_and_filters():
    rates = [
        DepositRate(bank="A", term_months=12, rate_online=7.0, min_deposit_vnd=1_000_000),
        DepositRate(bank="B", term_months=12, rate_online=7.5, min_deposit_vnd=1_000_000),
        DepositRate(bank="Excluded", term_months=12, rate_online=9.0, min_deposit_vnd=500_000_000_000),
    ]
    ranked = rank(rates)
    assert [r["bank"] for r in ranked] == ["B", "A"]


def test_top_by_term_exact_match():
    ranked = [
        {"bank": "A", "term_months": 12, "rate_pct": 7.0},
        {"bank": "B", "term_months": 6, "rate_pct": 6.8},
    ]
    assert top_by_term(ranked, 12)["bank"] == "A"


def test_top_by_term_falls_back_to_longer_term():
    ranked = [{"bank": "A", "term_months": 18, "rate_pct": 7.8}]
    assert top_by_term(ranked, 13)["bank"] == "A"


def test_top_by_term_none_when_no_candidate():
    ranked = [{"bank": "A", "term_months": 6, "rate_pct": 6.8}]
    assert top_by_term(ranked, 13) is None


def test_load_normalized_returns_only_latest_date_and_excludes_hdbank_after_rank():
    rates = load_normalized()
    assert len(rates) > 0
    ranked = rank(rates)
    assert "HDBank" not in [r["bank"] for r in ranked]
    assert "Cake by VPBank" in [r["bank"] for r in ranked]


def test_deposit_allocation_expected_interest():
    a = DepositAllocation(
        label="Kỳ hạn 12 tháng", term_months=12, amount_vnd=100_000_000, rate_pct=7.4,
        bank="Cake by VPBank", start_date=date(2026, 7, 19),
    )
    assert a.expected_interest_vnd == 7_400_000


def test_deposit_allocation_early_withdrawal_loss_positive():
    a = DepositAllocation(
        label="Kỳ hạn 12 tháng", term_months=12, amount_vnd=100_000_000, rate_pct=7.4,
        bank="Cake by VPBank", start_date=date(2026, 7, 19),
    )
    loss = a.early_withdrawal_loss_vnd(unqualified_rate_pct=0.5)
    assert loss > 0
    assert loss == 7_400_000 - 500_000


def test_split_strategy_respects_buffer_and_weights():
    ranked = [
        {"bank": "A", "term_months": 6, "rate_pct": 6.85},
        {"bank": "B", "term_months": 12, "rate_pct": 7.4},
    ]
    allocations = split_strategy(
        total_vnd=246_000_000, emergency_buffer_vnd=30_000_000, ranked_rates=ranked
    )
    total_allocated = sum(a.amount_vnd for a in allocations)
    investable = 246_000_000 - 30_000_000
    assert total_allocated <= investable + 1  # dung sai làm tròn
    # kỳ hạn 13 tháng không có ứng viên -> không tự bịa, bị bỏ qua
    assert all(a.term_months in (6, 12) for a in allocations)


def test_split_strategy_zero_when_buffer_exceeds_total():
    allocations = split_strategy(
        total_vnd=10_000_000, emergency_buffer_vnd=30_000_000,
        ranked_rates=[{"bank": "A", "term_months": 6, "rate_pct": 6.85}],
    )
    assert allocations == []


def test_total_expected_interest_sums_allocations():
    a1 = DepositAllocation("A", 6, 50_000_000, 6.85, "X", date(2026, 7, 19))
    a2 = DepositAllocation("B", 12, 50_000_000, 7.4, "Y", date(2026, 7, 19))
    assert total_expected_interest_vnd([a1, a2]) == a1.expected_interest_vnd + a2.expected_interest_vnd

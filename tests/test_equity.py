"""Test cho equity/{market,fundamentals,valuation,technical}.py (Phase 6)."""
import pytest

from equity.fundamentals import Fundamentals, quality_flags
from equity.market import CapitalFlow, MarketBreadth, streak
from equity.technical import (
    detect_breakout,
    find_pivots,
    relative_volume,
    support_resistance,
    trend_state,
    volume_zscore,
)
from equity.valuation import margin_of_safety_pct, pb_ratio, pe_ratio, percentile_rank, scenario_fair_values


# ---- market.py ----


def test_market_breadth_ratio_and_label():
    b = MarketBreadth(advancers=200, decliners=80)
    assert b.ratio == 2.5
    assert b.label == "TICH_CUC"


def test_market_breadth_negative_label():
    b = MarketBreadth(advancers=50, decliners=200)
    assert b.label == "TIEU_CUC"


def test_market_breadth_no_data():
    b = MarketBreadth(advancers=0, decliners=0)
    assert b.ratio is None
    assert b.label == "TRUNG_TINH"


def test_capital_flow_direction():
    assert CapitalFlow("Khối ngoại", -690).direction == "BAN_RONG"
    assert CapitalFlow("Khối ngoại", 690).direction == "MUA_RONG"
    assert CapitalFlow("Khối ngoại", None).direction == "KHONG_RO"


def test_streak_detects_consecutive_selling():
    result = streak([100, -50, -690, -400])
    assert result["direction"] == "BAN_RONG"
    assert result["streak"] == 3
    assert result["total_ty"] == -1140


def test_streak_empty_returns_zero():
    assert streak([])["streak"] == 0


# ---- fundamentals.py ----


def test_fundamentals_roe_roa_margin():
    f = Fundamentals(
        ticker="VCB", period="2026Q2",
        revenue_vnd=10_000, net_income_vnd=2_000,
        total_equity_vnd=20_000, total_assets_vnd=200_000,
    )
    assert f.roe_pct == 10.0
    assert f.roa_pct == 1.0
    assert f.net_margin_pct == 20.0


def test_fundamentals_none_when_missing_inputs():
    f = Fundamentals(ticker="VCB", period="2026Q2")
    assert f.roe_pct is None
    assert f.roa_pct is None
    assert f.debt_to_equity is None


def test_quality_flags_detects_low_cash_conversion():
    f = Fundamentals(
        ticker="X", period="2026Q2", net_income_vnd=1000, operating_cash_flow_vnd=300,
        total_debt_vnd=5000, total_equity_vnd=2000,
    )
    flags = quality_flags(f)
    assert any("Dòng tiền" in fl for fl in flags)
    assert any("Nợ/Vốn" in fl for fl in flags)


def test_quality_flags_empty_when_healthy():
    f = Fundamentals(
        ticker="X", period="2026Q2", net_income_vnd=1000, operating_cash_flow_vnd=1200,
        total_debt_vnd=1000, total_equity_vnd=2000,
    )
    assert quality_flags(f) == []


# ---- valuation.py ----


def test_pe_ratio_basic():
    assert pe_ratio(price=58.5, eps=5.0) == 11.7


def test_pe_ratio_none_for_negative_eps():
    assert pe_ratio(price=58.5, eps=-1.0) is None


def test_pb_ratio_basic():
    assert pb_ratio(price=63.5, book_value_per_share=40.0) == pytest.approx(1.59)


def test_margin_of_safety_positive_when_cheap():
    assert margin_of_safety_pct(intrinsic_value=100, price=70) == 30.0


def test_margin_of_safety_negative_when_expensive():
    assert margin_of_safety_pct(intrinsic_value=100, price=130) == -30.0


def test_percentile_rank_middle():
    assert percentile_rank(5, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]) == 50.0


def test_percentile_rank_none_without_history():
    assert percentile_rank(5, []) is None


def test_scenario_fair_values():
    v = scenario_fair_values(eps=5.0, pe_low=8, pe_base=12, pe_high=16)
    assert v == {"low": 40.0, "base": 60.0, "high": 80.0}


def test_scenario_fair_values_none_without_eps():
    assert scenario_fair_values(eps=None, pe_low=8, pe_base=12, pe_high=16) is None


# ---- technical.py ----


def test_relative_volume():
    assert relative_volume(150_000, 100_000) == 1.5
    assert relative_volume(100_000, None) is None


def test_volume_zscore_flags_spike():
    z = volume_zscore([100, 110, 90, 105, 95, 300])
    assert z is not None
    assert z > 2  # phiên cuối đột biến rõ so với lịch sử


def test_volume_zscore_insufficient_data():
    assert volume_zscore([100, 110]) is None


def test_find_pivots_detects_high_and_low():
    highs = [10, 11, 15, 11, 10]
    lows = [9, 10, 13, 10, 9]
    ph, pl = find_pivots(highs, lows, window=1)
    assert (2, 15) in ph


def test_support_resistance_none_when_no_pivots_found():
    sr = support_resistance([10, 10, 10], [9, 9, 9], last_close=9.5, window=1)
    assert sr["support"] is None
    assert sr["resistance"] is None


def test_detect_breakout_up():
    assert detect_breakout(last_close=65, prev_close=64, resistance=64.5, support=60) == "BREAKOUT_UP"


def test_detect_breakout_down():
    assert detect_breakout(last_close=59, prev_close=61, resistance=65, support=60) == "BREAKOUT_DOWN"


def test_detect_breakout_none():
    assert detect_breakout(last_close=62, prev_close=61, resistance=65, support=60) == "NONE"


def test_trend_state_unknown_with_insufficient_data():
    assert trend_state([1, 2, 3]) == "UNKNOWN"

"""Test cho datacontract/ — schema, validators, sources (Phase 2)."""
from datetime import datetime, timedelta, timezone

from datacontract.schema import Confidence, DataPoint, SourceStatus, now_iso
from datacontract.sources import BLOCKED_SOURCES, priority_for
from datacontract.validators import (
    compare_sources,
    evaluate_status,
    is_abnormal,
    is_missing,
    is_stale,
    pick_with_fallback,
    requires_no_decision,
)


def test_datapoint_missing_is_not_zero():
    dp = DataPoint(name="xau", value=None, unit="usd", source="s")
    assert dp.is_missing is True
    assert dp.value != 0  # None phải khác 0 tuyệt đối


def test_is_missing():
    assert is_missing(DataPoint(name="x", value=None, unit="u", source="s")) is True
    assert is_missing(DataPoint(name="x", value=10, unit="u", source="s")) is False


def test_is_abnormal_negative_and_zero_rejected_by_default():
    assert is_abnormal(DataPoint(name="price", value=-5, unit="u", source="s")) is True
    assert is_abnormal(DataPoint(name="price", value=0, unit="u", source="s")) is True
    assert is_abnormal(DataPoint(name="price", value=100, unit="u", source="s")) is False


def test_is_abnormal_allows_zero_when_flagged():
    dp = DataPoint(name="foreign_net", value=0, unit="ty", source="s")
    assert is_abnormal(dp, allow_zero=True) is False


def test_is_abnormal_missing_value_is_not_abnormal():
    # thiếu dữ liệu là is_missing, không phải is_abnormal — hai khái niệm khác nhau
    dp = DataPoint(name="x", value=None, unit="u", source="s")
    assert is_abnormal(dp) is False


def test_is_stale_fresh_vs_old():
    fresh = DataPoint(name="x", value=1, unit="u", source="s", fetched_at=now_iso())
    assert is_stale(fresh, max_age_seconds=3600) is False

    old_ts = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    stale = DataPoint(name="x", value=1, unit="u", source="s", fetched_at=old_ts)
    assert is_stale(stale, max_age_seconds=3600) is True


def test_is_stale_missing_fetched_at_is_conservative():
    dp = DataPoint(name="x", value=1, unit="u", source="s", fetched_at="")
    assert is_stale(dp, max_age_seconds=3600) is True


def test_compare_sources_within_tolerance_not_conflicting():
    a = DataPoint(name="xau", value=4017, unit="usd", source="a")
    b = DataPoint(name="xau", value=4020, unit="usd", source="b")
    assert compare_sources(a, b, tolerance_pct=2.0) is False


def test_compare_sources_large_gap_is_conflicting():
    a = DataPoint(name="xau", value=4017, unit="usd", source="a")
    c = DataPoint(name="xau", value=5000, unit="usd", source="c")
    assert compare_sources(a, c, tolerance_pct=2.0) is True


def test_evaluate_status_missing_is_failed():
    dp = DataPoint(name="x", value=None, unit="u", source="s")
    assert evaluate_status(dp, max_age_seconds=3600) == SourceStatus.FAILED.value


def test_evaluate_status_stale():
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
    dp = DataPoint(name="x", value=10, unit="u", source="s", fetched_at=old_ts)
    assert evaluate_status(dp, max_age_seconds=3600) == SourceStatus.STALE.value


def test_evaluate_status_healthy():
    dp = DataPoint(name="x", value=10, unit="u", source="s", fetched_at=now_iso())
    assert evaluate_status(dp, max_age_seconds=3600) == SourceStatus.HEALTHY.value


def test_pick_with_fallback_skips_missing_and_marks_fallback():
    bad = DataPoint(name="xau", value=None, unit="usd", source="primary")
    good = DataPoint(name="xau", value=4017, unit="usd", source="backup", fetched_at=now_iso())
    chosen = pick_with_fallback([bad, good], max_age_seconds=3600)
    assert chosen is good
    assert chosen.fallback_used is True
    assert chosen.status == SourceStatus.DEGRADED.value


def test_pick_with_fallback_first_candidate_no_fallback_flag():
    good = DataPoint(name="xau", value=4017, unit="usd", source="primary", fetched_at=now_iso())
    chosen = pick_with_fallback([good], max_age_seconds=3600)
    assert chosen is good
    assert chosen.fallback_used is False


def test_pick_with_fallback_returns_none_when_all_unusable():
    bad1 = DataPoint(name="xau", value=None, unit="usd", source="a")
    bad2 = DataPoint(name="xau", value=-1, unit="usd", source="b")
    assert pick_with_fallback([bad1, bad2], max_age_seconds=3600) is None


def test_requires_no_decision_flags_missing_critical_field():
    ok = DataPoint(name="xau", value=4017, unit="usd", source="s", fetched_at=now_iso())
    evaluate_status(ok, 3600)
    bad = DataPoint(name="vnindex", value=None, unit="pt", source="s")
    evaluate_status(bad, 3600)
    flag, reasons = requires_no_decision([ok, bad])
    assert flag is True
    assert any("vnindex" in r for r in reasons)


def test_requires_no_decision_all_healthy_returns_false():
    ok = DataPoint(name="xau", value=4017, unit="usd", source="s", fetched_at=now_iso())
    evaluate_status(ok, 3600)
    flag, reasons = requires_no_decision([ok])
    assert flag is False
    assert reasons == []


def test_priority_for_filters_blocked_sources():
    chain = priority_for("vn_index")
    assert "hose_api" not in chain
    assert "hose_api" in BLOCKED_SOURCES
    assert "web_search_summary" in chain


def test_confidence_enum_values():
    assert Confidence.HIGH.value == "HIGH"
    assert Confidence.LOW.value == "LOW"

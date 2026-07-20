"""Test cho decision/decision_log.py + analytics/decision_review.py (Phase 9).

Nguyên tắc kiểm chứng quan trọng nhất: CHỐNG LOOK-AHEAD-BIAS — một quyết định
tại kỳ (date, ky) chỉ được đánh giá bằng snapshot SAU kỳ đó (sáng < chiều),
không bao giờ bằng chính snapshot nó dựa vào hay snapshot trước đó.
"""
from analytics.decision_review import (
    Verdict,
    historical_accuracy_for_confidence,
    later_snapshots,
    period_key,
    review_all,
    review_one,
    summarize,
)
from decision.decision_log import append_decision, build_entry, extract_ref_price, load_decisions


def _snap(date: str, ky: str, ring_sell: float | None = 145.0) -> dict:
    gold: dict = {"xauusd": 3990}
    if ring_sell is not None:
        gold["ring_sell"] = ring_sell
    return {"date": date, "ky": ky, "gold": gold}


def _decision(date: str, ky: str, action: str = "TAKE_PARTIAL_PROFIT", ref: float = 145.0) -> dict:
    return {
        "date": date, "ky": ky, "asset": "Vàng nhẫn", "asset_class": "gold",
        "action": action, "action_vi": "x", "confidence": 80, "risk_veto": False,
        "data_quality": "GOOD", "ref_price_field": "ring_sell", "ref_price": ref,
    }


# ---------- decision_log ----------

def test_extract_ref_price_prefers_ring_sell_for_gold():
    assert extract_ref_price(_snap("2026-07-20", "sang"), "gold") == ("ring_sell", 145.0)


def test_extract_ref_price_falls_back_to_xauusd():
    assert extract_ref_price(_snap("2026-07-20", "sang", ring_sell=None), "gold") == ("xauusd", 3990)


def test_extract_ref_price_none_when_no_gold_data():
    assert extract_ref_price({"date": "2026-07-20", "ky": "sang"}, "gold") is None


def test_build_entry_records_ref_price_from_snapshot():
    decision = {"asset": "Vàng nhẫn", "action": "HOLD", "action_vi": "GIỮ",
                "confidence": 92, "risk_veto": False, "data_quality": "GOOD"}
    entry = build_entry(decision, asset_class="gold", ky="sang", snapshot=_snap("2026-07-20", "sang"))
    assert entry["date"] == "2026-07-20"
    assert entry["ky"] == "sang"
    assert entry["ref_price_field"] == "ring_sell"
    assert entry["ref_price"] == 145.0


def test_build_entry_honest_none_when_snapshot_missing():
    decision = {"asset": "Vàng nhẫn", "action": "HOLD", "action_vi": "GIỮ",
                "confidence": 92, "risk_veto": False, "data_quality": "GOOD"}
    entry = build_entry(decision, asset_class="gold", ky="sang", snapshot=None)
    assert entry["ref_price"] is None
    assert entry["ref_price_field"] is None


def test_append_decision_writes_and_loads_roundtrip(tmp_path):
    path = tmp_path / "decisions.jsonl"
    assert append_decision(_decision("2026-07-20", "sang"), path) is True
    loaded = load_decisions(path)
    assert len(loaded) == 1
    assert loaded[0]["asset"] == "Vàng nhẫn"


def test_append_decision_refuses_duplicate_same_period_and_asset(tmp_path):
    path = tmp_path / "decisions.jsonl"
    assert append_decision(_decision("2026-07-20", "sang"), path) is True
    assert append_decision(_decision("2026-07-20", "sang"), path) is False
    assert len(load_decisions(path)) == 1


def test_append_decision_allows_different_period(tmp_path):
    path = tmp_path / "decisions.jsonl"
    assert append_decision(_decision("2026-07-20", "sang"), path) is True
    assert append_decision(_decision("2026-07-20", "chieu"), path) is True
    assert len(load_decisions(path)) == 2


# ---------- chống look-ahead ----------

def test_period_key_orders_sang_before_chieu():
    assert period_key("2026-07-20", "sang") < period_key("2026-07-20", "chieu")
    assert period_key("2026-07-20", "chieu") < period_key("2026-07-21", "sang")


def test_later_snapshots_excludes_same_and_earlier_periods():
    snaps = [_snap("2026-07-19", "chieu"), _snap("2026-07-20", "sang"), _snap("2026-07-20", "chieu")]
    result = later_snapshots(_decision("2026-07-20", "sang"), snaps)
    assert [(s["date"], s["ky"]) for s in result] == [("2026-07-20", "chieu")]


def test_later_snapshots_handles_unordered_input():
    snaps = [_snap("2026-07-21", "sang"), _snap("2026-07-19", "sang"), _snap("2026-07-20", "chieu")]
    result = later_snapshots(_decision("2026-07-20", "sang"), snaps)
    assert [(s["date"], s["ky"]) for s in result] == [("2026-07-20", "chieu"), ("2026-07-21", "sang")]


# ---------- review ----------

def test_review_no_later_snapshot_is_insufficient_data():
    row = review_one(_decision("2026-07-20", "sang"), [_snap("2026-07-20", "sang")])
    assert row["verdict"] == Verdict.CHUA_DU_DU_LIEU.value


def test_review_take_partial_profit_correct_when_price_falls():
    snaps = [_snap("2026-07-21", "sang", ring_sell=140.0)]
    row = review_one(_decision("2026-07-20", "sang", "TAKE_PARTIAL_PROFIT", ref=145.0), snaps)
    assert row["verdict"] == Verdict.DUNG_HUONG.value
    assert row["change_pct"] < 0


def test_review_take_partial_profit_wrong_when_price_rises():
    snaps = [_snap("2026-07-21", "sang", ring_sell=150.0)]
    row = review_one(_decision("2026-07-20", "sang", "TAKE_PARTIAL_PROFIT", ref=145.0), snaps)
    assert row["verdict"] == Verdict.SAI_HUONG.value


def test_review_buy_small_correct_when_price_rises():
    snaps = [_snap("2026-07-21", "sang", ring_sell=150.0)]
    row = review_one(_decision("2026-07-20", "sang", "BUY_SMALL", ref=145.0), snaps)
    assert row["verdict"] == Verdict.DUNG_HUONG.value


def test_review_flat_move_is_not_scored():
    snaps = [_snap("2026-07-21", "sang", ring_sell=145.2)]  # +0.14% — đi ngang
    row = review_one(_decision("2026-07-20", "sang", "BUY_SMALL", ref=145.0), snaps)
    assert row["verdict"] == Verdict.DI_NGANG.value


def test_review_hold_is_risk_action_not_scored():
    snaps = [_snap("2026-07-21", "sang", ring_sell=150.0)]
    row = review_one(_decision("2026-07-20", "sang", "HOLD", ref=145.0), snaps)
    assert row["verdict"] == Verdict.KHONG_CHAM_DIEM.value


def test_review_missing_ref_price_is_insufficient():
    d = _decision("2026-07-20", "sang")
    d["ref_price"] = None
    row = review_one(d, [_snap("2026-07-21", "sang")])
    assert row["verdict"] == Verdict.CHUA_DU_DU_LIEU.value


def test_review_later_snapshot_missing_same_field_is_insufficient():
    # Quyết định tham chiếu ring_sell nhưng snapshot sau chỉ có xauusd —
    # KHÔNG được so chéo 2 đơn vị khác nhau.
    snaps = [_snap("2026-07-21", "sang", ring_sell=None)]
    row = review_one(_decision("2026-07-20", "sang"), snaps)
    assert row["verdict"] == Verdict.CHUA_DU_DU_LIEU.value


def test_review_uses_latest_later_snapshot():
    snaps = [_snap("2026-07-21", "sang", ring_sell=150.0), _snap("2026-07-22", "sang", ring_sell=138.0)]
    row = review_one(_decision("2026-07-20", "sang", "TAKE_PARTIAL_PROFIT", ref=145.0), snaps)
    assert row["compared_with"] == {"date": "2026-07-22", "ky": "sang"}
    assert row["verdict"] == Verdict.DUNG_HUONG.value


# ---------- summary + historical accuracy ----------

def test_summarize_counts_and_accuracy():
    decisions = [
        _decision("2026-07-18", "sang", "TAKE_PARTIAL_PROFIT", ref=145.0),
        _decision("2026-07-18", "chieu", "BUY_SMALL", ref=145.0),
        _decision("2026-07-19", "sang", "HOLD", ref=145.0),
    ]
    snaps = [_snap("2026-07-20", "sang", ring_sell=140.0)]
    s = summarize(review_all(decisions, snaps))
    assert s["total"] == 3
    assert s["dung_huong"] == 1  # TAKE_PARTIAL_PROFIT: giá giảm → đúng
    assert s["sai_huong"] == 1  # BUY_SMALL: giá giảm → sai
    assert s["khong_cham_diem"] == 1  # HOLD
    assert s["accuracy_pct"] == 50.0


def test_summarize_accuracy_none_when_nothing_scored():
    s = summarize(review_all([_decision("2026-07-20", "sang", "HOLD")], [_snap("2026-07-21", "sang")]))
    assert s["accuracy_pct"] is None


def test_historical_accuracy_needs_minimum_sample():
    # <5 quyết định đã chấm điểm → trả None (không nạp nhiễu vào confidence)
    assert historical_accuracy_for_confidence({"scored": 4, "accuracy_pct": 100.0}) is None
    assert historical_accuracy_for_confidence({"scored": 5, "accuracy_pct": 60.0}) == 60.0
    assert historical_accuracy_for_confidence({"scored": 10, "accuracy_pct": None}) is None

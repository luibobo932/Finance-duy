"""Test cho analytics/anomaly_detector.py (Phase 6).

Nguyên tắc bắt buộc: output KHÔNG BAO GIỜ khẳng định "giao dịch nội gián"/
"insider trading" — chỉ được "cần theo dõi, chưa đủ căn cứ".
"""
from analytics.anomaly_detector import detect, top_volume_records


def test_detect_no_data():
    result = detect("CTD", [])
    assert result["alert_level"] == 0
    assert result["anomaly_type"] == "no_data"


def test_detect_no_anomaly_for_random_small_orders():
    rows = [(f"09:{i:02d}", 81000, 100 + i) for i in range(30)]
    result = detect("CTD", rows)
    assert result["alert_level"] == 0
    assert result["anomaly_type"] == "none"


def test_detect_flags_repeated_round_lots():
    rows = [("09:00", 81000, 200), ("09:01", 81000, 150)]
    rows += [(f"10:{i:02d}", 81000, 50_000) for i in range(6)]
    result = detect("CTD", rows)
    assert result["alert_level"] > 0
    assert "repeated_round_lot_orders" in result["anomaly_types"]
    assert any("50,000" in e for e in result["evidence"])


def test_detect_conclusion_never_claims_insider_certainty():
    rows = [(f"10:{i:02d}", 81000, 50_000) for i in range(6)]
    result = detect("CTD", rows)
    conclusion = result["conclusion"].lower()
    assert "nội gián" not in conclusion
    assert "insider" not in conclusion
    assert "chưa đủ căn cứ" in conclusion


def test_detect_flags_unusual_volume_share():
    rows = [(f"09:{i:02d}", 81000, 100) for i in range(10)]
    rows.append(("10:00", 81000, 20_000))  # 1 lệnh lớn chiếm đa số khối lượng
    result = detect("CTD", rows)
    assert "unusual_volume" in result["anomaly_types"]


def test_top_volume_records_sorted_and_marked():
    rows = [("09:00", 100, 500), ("09:01", 100, 50_000), ("09:02", 100, 300)]
    top = top_volume_records(rows, n=2)
    assert top[0]["volume"] == 50_000
    assert top[0]["is_round_lot"] is True
    assert len(top) == 2

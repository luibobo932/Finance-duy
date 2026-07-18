import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from scripts.decision_engine import DEFAULT_PROFILE, build_decision_report
from scripts.finance_data import DataValidationError
from scripts.scorecard import append_entry, build_scorecard, make_entry
from tests.test_decision_engine import verified_snapshot


class ScorecardTests(unittest.TestCase):
    def test_scorecard_waits_for_future_periods_then_assesses(self):
        first = verified_snapshot("2026-07-16", "chieu")
        current = verified_snapshot("2026-07-17", "chieu")
        report = build_decision_report([first, current], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 17))
        entry = make_entry(report)
        future = []
        for index in range(1, 6):
            day = (date(2026, 7, 17) + timedelta(days=index)).isoformat()
            snapshot = verified_snapshot(day, "chieu")
            snapshot["vcb"]["close"] = current["vcb"]["close"] + index * 100
            snapshot["ctd"]["close"] = current["ctd"]["close"] + index * 200
            snapshot["gold"]["xauusd"] = current["gold"]["xauusd"] + index * 5
            snapshot["gold"]["sjc_buy"] = current["gold"]["sjc_sell"] + index * 0.2
            future.append(snapshot)

        pending = build_scorecard([entry], [first, current], minimum_assessed=1)
        self.assertEqual(pending["assessed"], 0)
        assessed = build_scorecard([entry], [first, current, *future], minimum_assessed=1)
        self.assertEqual(assessed["status"], "READY")
        self.assertEqual(assessed["assessed"], 3)
        vcb = next(item for item in assessed["outcomes"] if item["asset_id"] == "vcb")
        self.assertIsNotNone(vcb["excess_vs_savings_pct"])

    def test_journal_blocks_duplicate_id(self):
        entry = {"id": "same", "assets": {}, "as_of": {}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "journal.jsonl"
            append_entry(entry, path)
            with self.assertRaisesRegex(DataValidationError, "đã có"):
                append_entry(entry, path)

    def test_gold_requires_distinct_observed_times(self):
        first = verified_snapshot("2026-07-16", "chieu")
        current = verified_snapshot("2026-07-17", "chieu")
        report = build_decision_report([first, current], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 17))
        entry = make_entry(report)
        repeated = []
        for index in range(1, 7):
            day = (date(2026, 7, 17) + timedelta(days=index)).isoformat()
            snapshot = verified_snapshot(day, "chieu")
            snapshot["gold"]["observed_at"] = current["gold"]["observed_at"]
            repeated.append(snapshot)
        scorecard = build_scorecard([entry], [first, current, *repeated], minimum_assessed=1)
        gold = [item for item in scorecard["outcomes"] if item["asset_id"] == "gold"]
        self.assertEqual(gold[0]["status"], "PENDING")

    def test_accuracy_is_hidden_before_minimum_sample(self):
        first = verified_snapshot("2026-07-16", "chieu")
        current = verified_snapshot("2026-07-17", "chieu")
        entry = make_entry(build_decision_report([first, current], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 17)))
        future = []
        for index in range(1, 6):
            day = (date(2026, 7, 17) + timedelta(days=index)).isoformat()
            future.append(verified_snapshot(day, "chieu"))
        scorecard = build_scorecard([entry], [first, current, *future], minimum_assessed=20)
        self.assertEqual(scorecard["status"], "INSUFFICIENT_HISTORY")
        self.assertIsNone(scorecard["directional_accuracy_pct"])


if __name__ == "__main__":
    unittest.main()

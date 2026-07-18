import json
import tempfile
import unittest
from pathlib import Path

from scripts.finance_data import DataValidationError, load_history, validate_snapshot


def valid_snapshot(date="2026-07-18", ky="sang"):
    return {
        "schema_version": 2,
        "date": date,
        "ky": ky,
        "vnindex": {"close": 1787.45, "change_pct": -0.93},
        "vcb": {"close": 57600, "volume_million_shares": None},
        "gold": {"sjc_sell": 146.6, "xauusd": 4017.3},
        "deposit_top": [{"bank": "Ngân hàng A", "term_months": 12, "rate_pct": 7.4}],
    }


class FinanceDataTests(unittest.TestCase):
    def test_validate_snapshot_accepts_valid_data(self):
        self.assertEqual(validate_snapshot(valid_snapshot())["ky"], "sang")

    def test_validate_snapshot_rejects_bad_date(self):
        snapshot = valid_snapshot(date="18/07/2026")
        with self.assertRaisesRegex(DataValidationError, "YYYY-MM-DD"):
            validate_snapshot(snapshot)

    def test_load_history_reports_line_number(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.jsonl"
            path.write_text(json.dumps(valid_snapshot()) + "\n{bad json}\n", encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "dòng 2"):
                load_history(path)

    def test_load_history_rejects_out_of_order_periods(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.jsonl"
            rows = [valid_snapshot("2026-07-18", "chieu"), valid_snapshot("2026-07-18", "sang")]
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "thứ tự thời gian"):
                load_history(path)

    def test_source_url_must_be_https(self):
        snapshot = valid_snapshot()
        snapshot["sources"] = [{"id": "bad", "name": "Nguồn", "url": "http://example.com", "retrieved_at": "2026-07-18T10:00:00+07:00", "fields": []}]
        with self.assertRaisesRegex(DataValidationError, "https://"):
            validate_snapshot(snapshot)

    def test_zero_market_prices_are_rejected(self):
        snapshot = valid_snapshot()
        snapshot["vnindex"]["close"] = 0
        with self.assertRaisesRegex(DataValidationError, "phải > 0"):
            validate_snapshot(snapshot)

    def test_wrong_schema_version_is_rejected(self):
        snapshot = valid_snapshot()
        snapshot["schema_version"] = 1
        with self.assertRaisesRegex(DataValidationError, "schema_version"):
            validate_snapshot(snapshot)

    def test_future_market_and_gold_times_are_rejected(self):
        snapshot = valid_snapshot()
        snapshot["collected_at"] = "2026-07-18T18:00:00+07:00"
        snapshot["market_date"] = "2026-07-19"
        snapshot["gold"]["observed_at"] = "2026-07-19T10:00:00+07:00"
        with self.assertRaisesRegex(DataValidationError, "market_date"):
            validate_snapshot(snapshot)


if __name__ == "__main__":
    unittest.main()

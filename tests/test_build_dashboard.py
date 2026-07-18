import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_dashboard import build_payload, load_market_history
from scripts.finance_data import DataValidationError
from tests.test_finance_data import valid_snapshot


def valid_market_history():
    def daily_rows():
        return [
            {"date": "2026-07-16", "open_vnd": 9900, "high_vnd": 10100, "low_vnd": 9800, "close_vnd": 10000, "change_pct": 1.0, "matched_volume": 2000},
            {"date": "2026-07-17", "open_vnd": 10000, "high_vnd": 10200, "low_vnd": 9900, "close_vnd": 10100, "change_pct": 1.0, "matched_volume": 3000},
        ]

    def intraday():
        return {
            "market_date": "2026-07-17", "bar_count": 3, "total_volume": 3000,
            "morning_volume": 1000, "afternoon_volume": 2000, "atc_volume": 500,
            "uptick_volume": 1200, "downtick_volume": 800, "flat_volume": 1000,
            "reconciled_with_daily": True, "daily_volume": 3000,
        }

    return {
        "schema_version": 1,
        "classification": "AUXILIARY_REFERENCE_ONLY",
        "decision_unlock": False,
        "market_date": "2026-07-17",
        "retrieved_at": "2026-07-18T08:00:00+07:00",
        "daily": {"VCB": daily_rows(), "CTD": daily_rows()},
        "intraday": {"VCB": intraday(), "CTD": intraday()},
        "warnings": [],
        "sources": [
            {"id": "cafef_history", "name": "CafeF", "url": "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx", "role": "Lịch sử giá/khối lượng ngày", "source_tier": "secondary", "decision_eligible": False, "retrieved_at": "2026-07-18T08:00:00+07:00", "fields": ["daily.VCB", "daily.CTD"], "request_urls": ["https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?Symbol=VCB&StartDate=&EndDate=&PageIndex=1&PageSize=40", "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/PriceHistory.ashx?Symbol=CTD&StartDate=&EndDate=&PageIndex=1&PageSize=40"], "license_note": "Chỉ dùng tham khảo"},
            {"id": "entrade_minute", "name": "DNSE/EnTrade", "url": "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock", "role": "Nến một phút phiên gần nhất", "source_tier": "secondary", "decision_eligible": False, "retrieved_at": "2026-07-18T08:00:00+07:00", "fields": ["intraday.VCB", "intraday.CTD"], "request_urls": ["https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from=1784221200&to=1784307600&symbol=VCB&resolution=1", "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?from=1784221200&to=1784307600&symbol=CTD&resolution=1"], "license_note": "Chỉ dùng tham khảo"},
        ],
    }


class BuildDashboardTests(unittest.TestCase):
    def test_build_payload_uses_latest_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            history = root / "history.jsonl"
            portfolio = root / "portfolio.json"
            snapshots = [
                valid_snapshot("2026-07-17", "chieu"),
                valid_snapshot("2026-07-18", "sang"),
            ]
            history.write_text(
                "\n".join(json.dumps(item, ensure_ascii=False) for item in snapshots) + "\n",
                encoding="utf-8",
            )
            portfolio.write_text('{"VCB":{"avg_cost":56000,"quantity":100}}', encoding="utf-8")
            market_history = root / "market_history.json"
            market_history.write_text(json.dumps(valid_market_history()), encoding="utf-8")
            payload = build_payload(history, portfolio, market_history_path=market_history)
            self.assertEqual(payload["latest"]["date"], "2026-07-18")
            self.assertEqual(payload["previous"]["ky"], "chieu")
            self.assertNotIn("portfolio", payload)
            self.assertIn("decision", payload)
            self.assertEqual(len(payload["history_provenance"]), 2)
            self.assertNotIn("portfolio", payload["decision"])
            self.assertIn("market_history", payload)
            self.assertFalse(payload["market_history"]["decision_unlock"])
            self.assertEqual(payload["market_history"]["quality"]["status"], "RECONCILED")

    def test_market_history_rejects_false_reconciliation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "market_history.json"
            payload = valid_market_history()
            payload["intraday"]["VCB"]["daily_volume"] = 2999
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "cờ đối soát"):
                load_market_history(path)

    def test_market_history_rejects_invalid_ohlc(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "market_history.json"
            payload = valid_market_history()
            payload["daily"]["CTD"][-1]["low_vnd"] = 10150
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "OHLC"):
                load_market_history(path)

    def test_market_history_rejects_non_object_root(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "market_history.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "schema"):
                load_market_history(path)

    def test_market_history_rejects_future_retrieval_time(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "market_history.json"
            payload = valid_market_history()
            payload["retrieved_at"] = "2099-01-01T08:00:00+07:00"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "tương lai"):
                load_market_history(path)

    def test_market_history_rejects_wrong_auxiliary_query(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "market_history.json"
            payload = valid_market_history()
            payload["sources"][0]["request_urls"][0] = payload["sources"][0]["request_urls"][0].replace("PageSize=40", "PageSize=20")
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "PageIndex/PageSize"):
                load_market_history(path)


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timezone

from scripts.collect_market_history import build_market_history, normalize_daily_payload, normalize_intraday_payload
from scripts.finance_data import DataValidationError


class MarketHistoryCollectorTests(unittest.TestCase):
    def test_normalize_daily_payload(self):
        payload = {"Success": True, "Data": {"Data": [{
            "Ngay": "17/07/2026", "GiaDongCua": 63.5, "GiaMoCua": 66,
            "GiaCaoNhat": 66.2, "GiaThapNhat": 63.5, "KhoiLuongKhopLenh": 426800,
            "GiaTriKhopLenh": 27.51, "KLThoaThuan": 0, "ThayDoi": "-2,70 (-4,08%)",
        }]}}
        row = normalize_daily_payload("CTD", payload)[0]
        self.assertEqual(row["close_vnd"], 63500)
        self.assertEqual(row["change_pct"], -4.08)
        self.assertEqual(row["matched_volume"], 426800)

    def test_intraday_rejects_misaligned_arrays(self):
        with self.assertRaisesRegex(DataValidationError, "không đồng nhất"):
            normalize_intraday_payload("CTD", "2026-07-17", {"t": [1], "o": [], "h": [], "l": [], "c": [], "v": []})

    def test_daily_rejects_impossible_ohlc(self):
        payload = {"Success": True, "Data": {"Data": [{
            "Ngay": "17/07/2026", "GiaDongCua": 63.5, "GiaMoCua": 66,
            "GiaCaoNhat": 65, "GiaThapNhat": 63.5, "KhoiLuongKhopLenh": 426800,
            "GiaTriKhopLenh": 27.51, "KLThoaThuan": 0, "ThayDoi": "-2,70 (-4,08%)",
        }]}}
        with self.assertRaisesRegex(DataValidationError, "OHLC"):
            normalize_daily_payload("CTD", payload)

    def test_build_reconciles_intraday_and_daily(self):
        def daily(symbol):
            return [{
                "date": "2026-07-17", "open_vnd": 10000, "high_vnd": 11000,
                "low_vnd": 9000, "close_vnd": 10000, "change_pct": 0,
                "matched_volume": 3000, "matched_value_billion_vnd": 0.03,
                "put_through_volume": 0,
            }]

        def intraday(symbol, market_date):
            return {"market_date": market_date, "total_volume": 3000}

        payload = build_market_history(
            daily_fetcher=daily,
            intraday_fetcher=intraday,
            now=datetime(2026, 7, 18, tzinfo=timezone.utc),
        )
        self.assertTrue(payload["intraday"]["VCB"]["reconciled_with_daily"])
        self.assertEqual(payload["market_date"], "2026-07-17")

    def test_build_requires_a_common_market_date(self):
        def daily(symbol):
            day = "2026-07-17" if symbol == "VCB" else "2026-07-18"
            return [{"date": day, "matched_volume": 1000}]

        with self.assertRaisesRegex(DataValidationError, "không có ngày giao dịch chung"):
            build_market_history(daily_fetcher=daily, intraday_fetcher=lambda *_: {})

    def test_intraday_failure_marks_auxiliary_payload_partial(self):
        def daily(symbol):
            return [{"date": "2026-07-17", "matched_volume": 3000}]

        def intraday(symbol, market_date):
            if symbol == "CTD":
                raise RuntimeError("CTD tạm thời không tải được")
            return {"market_date": market_date, "total_volume": 3000}

        payload = build_market_history(daily_fetcher=daily, intraday_fetcher=intraday)
        self.assertEqual(payload["quality"]["status"], "PARTIAL")
        self.assertEqual(payload["quality"]["coverage"]["intraday"], "1/2")
        self.assertFalse(payload["decision_unlock"])


if __name__ == "__main__":
    unittest.main()

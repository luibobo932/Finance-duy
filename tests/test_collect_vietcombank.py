import unittest
import urllib.error
from unittest.mock import patch

from scripts.collect_vietcombank import fetch_json, normalize_fx, normalize_rates


class VietcombankCollectorTests(unittest.TestCase):
    def test_normalize_fx(self):
        payload = {"UpdatedDate": "2026-07-18T10:00:00+07:00", "Data": [{"currencyCode": "USD", "cash": "26000", "transfer": "26100", "sell": "26400"}]}
        result = normalize_fx(payload, "2026-07-18")
        self.assertEqual(result["data"][0]["sell_vnd"], 26400)
        self.assertEqual(result["publisher"], "Vietcombank")

    def test_normalize_rates_filters_vnd_month_terms(self):
        payload = {"UpdatedDate": "2026-07-18T10:00:00+07:00", "Data": [
            {"tenorType": "Online", "tenor": "12-months", "currencyCode": "VND", "rates": 0.059},
            {"tenorType": "Online", "tenor": "Demand", "currencyCode": "VND", "rates": 0.001},
            {"tenorType": "Online", "tenor": "12-months", "currencyCode": "USD", "rates": 0.0},
        ]}
        result = normalize_rates(payload)
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["rate_pct"], 5.9)

    def test_empty_payload_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "rỗng"):
            normalize_fx({"Data": []}, "2026-07-18")
        with self.assertRaisesRegex(ValueError, "rỗng"):
            normalize_rates({"Data": []})

    def test_rate_schema_drift_is_rejected(self):
        payload = {"UpdatedDate": "2026-07-18T10:00:00+07:00", "Data": [
            {"tenorType": "Online", "tenor": "12-months", "currencyCode": "VND", "rates": 5.9},
        ]}
        with self.assertRaisesRegex(ValueError, "ngoài biên"):
            normalize_rates(payload)

    def test_fx_requires_positive_usd_sell(self):
        payload = {"UpdatedDate": "2026-07-18T10:00:00+07:00", "Data": [
            {"currencyCode": "USD", "cash": "26000", "transfer": "26100", "sell": "0"},
        ]}
        with self.assertRaisesRegex(ValueError, "không dương"):
            normalize_fx(payload, "2026-07-18")

    @patch("scripts.collect_vietcombank.urllib.request.urlopen", side_effect=urllib.error.URLError("offline"))
    def test_network_failure_is_wrapped(self, _urlopen):
        with self.assertRaisesRegex(RuntimeError, "không tải được"):
            fetch_json("https://example.invalid")


if __name__ == "__main__":
    unittest.main()

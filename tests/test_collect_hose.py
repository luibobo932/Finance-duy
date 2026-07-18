import unittest
import urllib.error
from unittest.mock import patch

from scripts.collect_hose import fetch_eod, normalize


class HoseCollectorTests(unittest.TestCase):
    def test_normalize_converts_hose_units(self):
        payload = {"data": [{
            "securitySymbol": "VCB",
            "priorClosePrice": "59.40",
            "openPrice": "59.30",
            "highPrice": "59.30",
            "lowPrice": "58.50",
            "closePrice": "58.50",
            "changePriceRatio": "-1.52",
            "mainVolume": "19,901.00",
            "mainValue": "117,052.67",
        }]}
        result = normalize(payload, "2026-07-17", ["VCB"])["data"][0]
        self.assertEqual(result["close_vnd"], 58500)
        self.assertEqual(result["volume_shares"], 1_990_100)
        self.assertEqual(result["volume_million_shares"], 1.9901)

    def test_missing_symbol_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "CTD"):
            normalize({"data": []}, "2026-07-17", ["CTD"])

    def test_null_price_is_rejected_cleanly(self):
        payload = {"data": [{
            "securitySymbol": "VCB",
            "priorClosePrice": "59.40",
            "openPrice": "59.30",
            "highPrice": "59.30",
            "lowPrice": "58.50",
            "closePrice": None,
            "changePriceRatio": "-1.52",
            "mainVolume": "19,901.00",
        }]}
        with self.assertRaisesRegex(ValueError, "closePrice"):
            normalize(payload, "2026-07-17", ["VCB"])

    @patch("scripts.collect_hose.urllib.request.urlopen", side_effect=urllib.error.URLError("offline"))
    def test_network_failure_is_wrapped(self, _urlopen):
        with self.assertRaisesRegex(RuntimeError, "không tải được HOSE"):
            fetch_eod("2026-07-17")


if __name__ == "__main__":
    unittest.main()

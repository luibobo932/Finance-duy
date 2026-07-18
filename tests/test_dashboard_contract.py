import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class DashboardParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "a" and str(values.get("href", "")).startswith("#"):
            self.links.append(values["href"][1:])


class DashboardContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
        cls.javascript = (ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
        cls.data = json.loads((ROOT / "dashboard" / "data.json").read_text(encoding="utf-8"))
        cls.parser = DashboardParser()
        cls.parser.feed(cls.html)

    def test_javascript_dom_ids_exist_and_are_unique(self):
        self.assertEqual(len(self.parser.ids), len(set(self.parser.ids)), "HTML có id trùng")
        referenced = set(re.findall(r'byId\("([^"]+)"\)', self.javascript))
        self.assertEqual(set(), referenced - set(self.parser.ids), "JavaScript tham chiếu id không tồn tại")

    def test_internal_navigation_targets_exist(self):
        self.assertEqual(set(), set(self.parser.links) - set(self.parser.ids))
        self.assertIn("mobile-nav", self.html)

    def test_decision_state_appears_before_auxiliary_charts(self):
        decision = self.html.index('id="decision-center"')
        snapshot = self.html.index('id="summary"')
        charts = self.html.index('id="market-lab"')
        self.assertLess(decision, snapshot)
        self.assertLess(snapshot, charts)

    def test_built_payload_contains_runtime_sla_and_non_decision_auxiliary_data(self):
        self.assertEqual(self.data["source_registry"]["hose_eod"]["stale_after_hours"], 30)
        auxiliary = self.data["market_history"]
        self.assertEqual(auxiliary["classification"], "AUXILIARY_REFERENCE_ONLY")
        self.assertIs(auxiliary["decision_unlock"], False)
        self.assertTrue(auxiliary["quality"]["official_hose_crosscheck"]["matched"])

    def test_scorecard_is_asset_specific(self):
        self.assertEqual(set(self.data["scorecard"]["asset_results"]), {"gold", "vcb", "ctd", "savings"})
        self.assertEqual(self.data["scorecard"]["status"], "INSUFFICIENT_HISTORY")


if __name__ == "__main__":
    unittest.main()

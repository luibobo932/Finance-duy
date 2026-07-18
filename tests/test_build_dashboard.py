import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_dashboard import build_payload
from tests.test_finance_data import valid_snapshot


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
            payload = build_payload(history, portfolio)
            self.assertEqual(payload["latest"]["date"], "2026-07-18")
            self.assertEqual(payload["previous"]["ky"], "chieu")
            self.assertNotIn("portfolio", payload)
            self.assertIn("decision", payload)
            self.assertEqual(len(payload["history_provenance"]), 2)
            self.assertNotIn("portfolio", payload["decision"])


if __name__ == "__main__":
    unittest.main()

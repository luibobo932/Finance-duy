import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.candidate_pipeline import create_candidate, promote_candidate, read_json, review_candidate
from scripts.finance_data import DataValidationError
from tests.test_finance_data import valid_snapshot


class CandidatePipelineTests(unittest.TestCase):
    def test_candidate_must_be_reviewed_before_promote(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            candidate = create_candidate(valid_snapshot(), root / "candidates")
            with self.assertRaisesRegex(DataValidationError, "chưa được rà soát"):
                promote_candidate(candidate, root / "history.jsonl")

    def test_review_then_promote(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixed = datetime(2026, 7, 18, tzinfo=timezone.utc)
            candidate = create_candidate(valid_snapshot(), root / "candidates", now=fixed)
            review_candidate(candidate, "Duy", "Đã đối chiếu nguồn", now=fixed)
            promote_candidate(candidate, root / "history.jsonl")
            self.assertEqual(read_json(candidate)["status"], "promoted")
            self.assertEqual(len((root / "history.jsonl").read_text(encoding="utf-8").splitlines()), 1)

    def test_changed_snapshot_fails_checksum(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            candidate = create_candidate(valid_snapshot(), root / "candidates")
            payload = read_json(candidate)
            payload["snapshot"]["vnindex"]["close"] += 1
            candidate.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(DataValidationError, "checksum"):
                review_candidate(candidate, "Duy")


if __name__ == "__main__":
    unittest.main()

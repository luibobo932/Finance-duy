import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import trend
from scripts.finance_data import DataValidationError
from tests.test_finance_data import valid_snapshot


class TrendTests(unittest.TestCase):
    def test_append_and_block_duplicate(self):
        with tempfile.TemporaryDirectory() as folder:
            history = Path(folder) / "history.jsonl"
            raw = json.dumps(valid_snapshot(), ensure_ascii=False)
            with patch.object(trend, "HIST", history):
                trend.cmd_append(raw)
                self.assertEqual(len(trend.load_history()), 1)
                with self.assertRaisesRegex(DataValidationError, "không ghi trùng"):
                    trend.cmd_append(raw)
                self.assertEqual(len(history.read_text(encoding="utf-8").splitlines()), 1)


if __name__ == "__main__":
    unittest.main()

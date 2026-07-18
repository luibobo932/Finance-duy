import contextlib
import io
import unittest

from scripts import tick


class TickTests(unittest.TestCase):
    def test_parse_vietnamese_thousands_separator(self):
        self.assertEqual(tick.parse_number("73.800"), 73800)
        self.assertEqual(tick.parse_number("10.000"), 10000)
        self.assertEqual(tick.parse_number("73.8"), 73.8)

    def test_repeated_round_orders_are_reported_as_signal_not_conclusion(self):
        rows = [
            ("09:15", 73800, 10000),
            ("09:16", 73800, 10000),
            ("09:17", 73900, 10000),
            ("09:18", 73900, 1250),
        ]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            tick.analyze(rows, "CTD test")
        text = output.getvalue()
        self.assertIn("CỤM LỆNH TRÒN SỐ", text)
        self.assertIn("chỉ là tín hiệu bất thường", text)

    def test_zero_volume_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "khối lượng"):
            tick.analyze([("09:15", 73800, 0)], "bad")

    def test_candle_data_never_runs_round_order_heuristic(self):
        rows = [("09:15", 73800, 10000), ("09:16", 73800, 10000), ("09:17", 73900, 10000)]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            tick.analyze(rows, "CTD nến", data_kind="candle")
        text = output.getvalue()
        self.assertIn("KHÔNG phải từng lệnh", text)
        self.assertNotIn("CỤM LỆNH TRÒN SỐ", text)

    def test_candle_metrics_separates_sessions_atc_and_direction(self):
        rows = [
            ("09:15", 66.0, 1000),
            ("09:16", 65.9, 2000),
            ("13:00", 66.0, 3000),
            ("14:45", 63.5, 4000),
        ]
        metrics = tick.candle_metrics(rows)
        self.assertEqual(metrics["morning"], 3000)
        self.assertEqual(metrics["afternoon"], 7000)
        self.assertEqual(metrics["atc"], 4000)
        self.assertEqual(metrics["up"], 3000)
        self.assertEqual(metrics["down"], 6000)


if __name__ == "__main__":
    unittest.main()

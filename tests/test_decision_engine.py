import copy
import unittest
from datetime import date

from scripts.decision_engine import DEFAULT_PROFILE, build_decision_report
from tests.test_finance_data import valid_snapshot


def verified_snapshot(day, period):
    snapshot = valid_snapshot(day, period)
    snapshot["market_date"] = day
    snapshot["collected_at"] = f"{day}T18:00:00+07:00"
    snapshot["vcb"] = {"prior_close": 57500, "close": 58000, "change_pct": 0.87, "volume_million_shares": 10.0, "fundamentals": {"report_end_date": "2026-06-30", "earnings_growth_pct": 12, "roe_pct": 18, "pe": 11}}
    snapshot["ctd"] = {"prior_close": 73000, "close": 74000, "change_pct": 1.37, "volume_million_shares": 2.0, "fundamentals": {"report_end_date": "2026-06-30", "earnings_growth_pct": 20, "roe_pct": 14, "pe": 13}}
    snapshot["foreign_net_ty"] = 500
    snapshot["gold"].update({"sjc_buy": 143.6, "premium_trieu": 18.3, "observed_at": f"{day}T17:00:00+07:00"})
    snapshot["fx_vcb_sell"] = 26490
    snapshot["deposit_top"] = [{
        "bank": "Vietcombank",
        "term_months": 12,
        "rate_pct": 7.4,
        "channel": "online",
        "minimum_amount_vnd": 1_000_000,
        "maximum_amount_vnd": 999_999_999,
        "conditions": "Khách hàng cá nhân",
        "effective_date": day,
        "payout_method": "Cuối kỳ",
        "source_id": "vietcombank_deposit",
        "source_url": "https://www.vietcombank.com.vn/vi-VN/api/interestrates?accountType=Personal",
        "retrieved_at": f"{day}T10:00:00+07:00",
    }]
    snapshot["sources"] = [
        {"id": "hose_eod", "name": "HOSE", "url": "https://www.hsx.vn/vi/du-lieu-giao-dich/thong-ke/du-lieu-cuoi-ngay", "retrieved_at": f"{day}T18:00:00+07:00", "fields": ["vnindex.close", "vnindex.change_pct", "vcb.prior_close", "vcb.close", "vcb.change_pct", "vcb.volume_million_shares", "ctd.prior_close", "ctd.close", "ctd.change_pct", "ctd.volume_million_shares", "market_date", "foreign_net_ty"]},
        {"id": "sjc_gold", "name": "SJC", "url": "https://www.sjc.com.vn/gia-vang-online", "retrieved_at": f"{day}T17:00:00+07:00", "fields": ["gold.sjc_buy", "gold.sjc_sell", "gold.observed_at"]},
        {"id": "lbma_gold", "name": "LBMA", "url": "https://www.lbma.org.uk/prices-and-data/lbma-gold-price", "retrieved_at": f"{day}T16:00:00+07:00", "fields": ["gold.xauusd"]},
        {"id": "vietcombank_fx", "name": "Vietcombank", "url": "https://www.vietcombank.com.vn/api/exchangerates", "retrieved_at": f"{day}T17:00:00+07:00", "fields": ["fx_vcb_sell"]},
        {"id": "vietcombank_deposit", "name": "Vietcombank", "url": "https://www.vietcombank.com.vn/vi-VN/api/interestrates?accountType=Personal", "retrieved_at": f"{day}T10:00:00+07:00", "fields": ["deposit_top"]},
        {"id": "vcb_ir", "name": "VCB IR", "url": "https://www.vietcombank.com.vn/vi-VN/Nha-dau-tu", "retrieved_at": f"{day}T10:00:00+07:00", "fields": ["vcb.fundamentals"]},
        {"id": "ctd_ir", "name": "CTD IR", "url": "https://www.coteccons.vn/investor-relations-vn/", "retrieved_at": f"{day}T10:00:00+07:00", "fields": ["ctd.fundamentals"]},
    ]
    return snapshot


class DecisionEngineTests(unittest.TestCase):
    def test_no_sources_forces_wait_data(self):
        history = [valid_snapshot("2026-07-17", "chieu"), valid_snapshot("2026-07-18", "sang")]
        report = build_decision_report(history, {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        self.assertTrue(all(item["decision_status"] == "WAIT_DATA" for item in report["asset_classes"]))

    def test_verified_data_can_cross_decision_gate(self):
        first = verified_snapshot("2026-07-17", "chieu")
        second = verified_snapshot("2026-07-18", "chieu")
        first["vcb"]["volume_million_shares"] = 5.0
        first["ctd"]["volume_million_shares"] = 1.0
        report = build_decision_report([first, second], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        self.assertGreaterEqual(report["data_quality"]["score"], 80)
        self.assertEqual(report["savings"]["decision_status"], "READY")
        self.assertTrue(any(item["decision_status"] == "READY" for item in report["stocks"]))

    def test_high_gold_premium_reduces_score(self):
        first = verified_snapshot("2026-07-17", "chieu")
        low = verified_snapshot("2026-07-18", "chieu")
        high = copy.deepcopy(low)
        low["gold"]["premium_trieu"] = 8
        high["gold"]["premium_trieu"] = 25
        low_score = build_decision_report([first, low], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))["gold"]["score"]
        high_score = build_decision_report([first, high], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))["gold"]["score"]
        self.assertGreater(low_score, high_score)

    def test_stale_data_forces_wait_even_with_sources(self):
        first = verified_snapshot("2026-06-16", "chieu")
        second = verified_snapshot("2026-06-17", "chieu")
        report = build_decision_report([first, second], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        self.assertTrue(report["data_quality"]["is_stale"])
        self.assertTrue(all(item["decision_status"] == "WAIT_DATA" for item in report["asset_classes"]))

    def test_unrelated_sources_do_not_unlock_decision(self):
        first = verified_snapshot("2026-07-17", "chieu")
        second = verified_snapshot("2026-07-18", "chieu")
        for snapshot in (first, second):
            snapshot["sources"] = [
                {"id": "sjc_gold", "name": "Tin khác", "url": "https://www.sjc.com.vn/gia-vang-online", "retrieved_at": f"{snapshot['date']}T10:00:00+07:00", "fields": ["unrelated_news"]}
            ]
        report = build_decision_report([first, second], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        self.assertEqual(report["data_quality"]["source_coverage_pct"], 0)
        self.assertTrue(all(item["decision_status"] == "WAIT_DATA" for item in report["asset_classes"]))

    def test_missing_collected_at_blocks_all_asset_classes(self):
        first = verified_snapshot("2026-07-17", "chieu")
        second = verified_snapshot("2026-07-18", "chieu")
        second.pop("collected_at")
        report = build_decision_report([first, second], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        self.assertTrue(all(item["decision_status"] == "WAIT_DATA" for item in report["asset_classes"]))

    def test_missing_market_date_blocks_stock_class(self):
        first = verified_snapshot("2026-07-17", "chieu")
        second = verified_snapshot("2026-07-18", "chieu")
        second.pop("market_date")
        report = build_decision_report([first, second], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        stocks = next(item for item in report["asset_classes"] if item["id"] == "stocks")
        self.assertEqual(stocks["decision_status"], "WAIT_DATA")

    def test_missing_fundamentals_blocks_stock_class(self):
        first = verified_snapshot("2026-07-17", "chieu")
        second = verified_snapshot("2026-07-18", "chieu")
        second["vcb"].pop("fundamentals")
        second["ctd"].pop("fundamentals")
        report = build_decision_report([first, second], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        stocks = next(item for item in report["asset_classes"] if item["id"] == "stocks")
        self.assertEqual(stocks["decision_status"], "WAIT_DATA")
        self.assertTrue(stocks["hard_blockers"])

    def test_missing_core_stock_fields_blocks_stock_class(self):
        first = verified_snapshot("2026-07-17", "chieu")
        second = verified_snapshot("2026-07-18", "chieu")
        for ticker in ("vcb", "ctd"):
            second[ticker].pop("close")
            second[ticker].pop("change_pct")
            second[ticker].pop("volume_million_shares")
        report = build_decision_report([first, second], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        stocks = next(item for item in report["asset_classes"] if item["id"] == "stocks")
        self.assertEqual(stocks["decision_status"], "WAIT_DATA")

    def test_old_collected_at_blocks_all_assets(self):
        first = verified_snapshot("2026-07-17", "chieu")
        second = verified_snapshot("2026-07-18", "chieu")
        for snapshot in (first, second):
            snapshot["collected_at"] = "2020-07-18T18:00:00+07:00"
            for source in snapshot["sources"]:
                source["retrieved_at"] = "2020-07-18T17:00:00+07:00"
        report = build_decision_report([first, second], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        self.assertTrue(report["data_quality"]["is_stale"])
        self.assertTrue(all(item["decision_status"] == "WAIT_DATA" for item in report["asset_classes"]))

    def test_future_effective_times_block_assets(self):
        first = verified_snapshot("2026-07-17", "chieu")
        second = verified_snapshot("2026-07-18", "chieu")
        second["market_date"] = "2030-01-01"
        second["gold"]["observed_at"] = "2030-01-01T10:00:00+07:00"
        report = build_decision_report([first, second], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        self.assertEqual(report["gold"]["decision_status"], "WAIT_DATA")
        stocks = next(item for item in report["asset_classes"] if item["id"] == "stocks")
        self.assertEqual(stocks["decision_status"], "WAIT_DATA")

    def test_missing_gold_critical_fields_blocks_gold(self):
        first = verified_snapshot("2026-07-17", "chieu")
        second = verified_snapshot("2026-07-18", "chieu")
        second["gold"].pop("sjc_buy")
        second["gold"].pop("premium_trieu")
        report = build_decision_report([first, second], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        self.assertEqual(report["gold"]["decision_status"], "WAIT_DATA")
        self.assertTrue(report["gold"]["hard_blockers"])

    def test_deposit_requiring_over_one_billion_is_excluded(self):
        first = verified_snapshot("2026-07-17", "chieu")
        second = verified_snapshot("2026-07-18", "chieu")
        second["deposit_top"][0]["minimum_amount_vnd"] = 500_000_000_000
        second["deposit_top"][0]["maximum_amount_vnd"] = 600_000_000_000
        report = build_decision_report([first, second], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        self.assertEqual(report["savings"]["decision_status"], "WAIT_DATA")
        self.assertIsNone(report["savings"]["metrics"]["top_rate_pct"])

    def test_unverified_promo_rate_is_not_renderable_as_eligible(self):
        first = verified_snapshot("2026-07-17", "chieu")
        second = verified_snapshot("2026-07-18", "chieu")
        fake = copy.deepcopy(second["deposit_top"][0])
        fake.update({"bank": "Ngân hàng không liên quan", "rate_pct": 19.9})
        second["deposit_top"].append(fake)
        report = build_decision_report([first, second], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        self.assertEqual(len(report["savings"]["eligible_products"]), 1)
        self.assertEqual(report["savings"]["metrics"]["bank"], "Vietcombank")

    def test_stale_fundamentals_block_stocks(self):
        first = verified_snapshot("2026-07-17", "chieu")
        second = verified_snapshot("2026-07-18", "chieu")
        second["vcb"]["fundamentals"]["report_end_date"] = "2000-03-31"
        second["ctd"]["fundamentals"]["report_end_date"] = "2000-03-31"
        report = build_decision_report([first, second], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        stocks = next(item for item in report["asset_classes"] if item["id"] == "stocks")
        self.assertEqual(stocks["decision_status"], "WAIT_DATA")

    def test_unverified_risk_flags_do_not_change_scores(self):
        first = verified_snapshot("2026-07-17", "chieu")
        baseline = verified_snapshot("2026-07-18", "chieu")
        flagged = copy.deepcopy(baseline)
        flagged["risk_flags"] = {"war": "Tin chưa có nguồn", "arrest": "Tin chưa có nguồn"}
        plain_report = build_decision_report([first, baseline], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        flagged_report = build_decision_report([first, flagged], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        self.assertEqual(plain_report["gold"]["score"], flagged_report["gold"]["score"])
        self.assertEqual([item["score"] for item in plain_report["stocks"]], [item["score"] for item in flagged_report["stocks"]])
        self.assertEqual(flagged_report["verified_risks"], {})

    def test_unverified_optional_foreign_flow_does_not_change_stock_scores(self):
        first = verified_snapshot("2026-07-17", "chieu")
        baseline = verified_snapshot("2026-07-18", "chieu")
        unverified = copy.deepcopy(baseline)
        unverified["foreign_net_ty"] = -999_999
        for snapshot in (baseline, unverified):
            for source in snapshot["sources"]:
                source["fields"] = [field for field in source["fields"] if field != "foreign_net_ty"]
        plain = build_decision_report([first, baseline], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        altered = build_decision_report([first, unverified], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        self.assertEqual([item["score"] for item in plain["stocks"]], [item["score"] for item in altered["stocks"]])

    def test_unverified_previous_gold_is_not_used_for_momentum(self):
        second = verified_snapshot("2026-07-18", "chieu")
        first_a = verified_snapshot("2026-07-17", "chieu")
        first_b = copy.deepcopy(first_a)
        first_a["gold"]["xauusd"] = 1000
        first_b["gold"]["xauusd"] = 9000
        for snapshot in (first_a, first_b):
            for source in snapshot["sources"]:
                source["fields"] = [field for field in source["fields"] if field != "gold.xauusd"]
        report_a = build_decision_report([first_a, second], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        report_b = build_decision_report([first_b, second], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        self.assertIsNone(report_a["gold"]["metrics"]["momentum_pct"])
        self.assertEqual(report_a["gold"]["score"], report_b["gold"]["score"])

    def test_unverified_current_market_input_does_not_change_scores(self):
        first = verified_snapshot("2026-07-17", "chieu")
        low = verified_snapshot("2026-07-18", "chieu")
        high = copy.deepcopy(low)
        low["vnindex"]["change_pct"] = -20
        high["vnindex"]["change_pct"] = 20
        for snapshot in (low, high):
            for source in snapshot["sources"]:
                source["fields"] = [field for field in source["fields"] if field != "vnindex.change_pct"]
        low_report = build_decision_report([first, low], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        high_report = build_decision_report([first, high], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        self.assertEqual([item["score"] for item in low_report["stocks"]], [item["score"] for item in high_report["stocks"]])

    def test_unverified_current_gold_premium_does_not_change_score(self):
        first = verified_snapshot("2026-07-17", "chieu")
        low = verified_snapshot("2026-07-18", "chieu")
        high = copy.deepcopy(low)
        low["gold"]["premium_trieu"] = 5
        high["gold"]["premium_trieu"] = 30
        for snapshot in (low, high):
            for source in snapshot["sources"]:
                source["fields"] = [field for field in source["fields"] if field != "fx_vcb_sell"]
        low_report = build_decision_report([first, low], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        high_report = build_decision_report([first, high], {}, dict(DEFAULT_PROFILE), today=date(2026, 7, 18))
        self.assertEqual(low_report["gold"]["score"], high_report["gold"]["score"])


if __name__ == "__main__":
    unittest.main()

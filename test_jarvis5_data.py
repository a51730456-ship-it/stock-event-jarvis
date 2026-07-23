import unittest
from datetime import datetime

import jarvis5_data as j5


class Jarvis5DataTests(unittest.TestCase):
    def _raw_theme(self, no, name, changes, intervals, *, repeated_code=None):
        stocks = []
        for index, (change, interval) in enumerate(zip(changes, intervals), 1):
            code = repeated_code if index == 1 and repeated_code else f"{no:03d}{index:03d}"
            stocks.append({
                "code": code,
                "name": f"종목{no}-{index}",
                "price": 10_000,
                "change_pct": change,
                "trading_value": 1_000_000_000 + interval,
                "volume": 100,
                "previous_volume": 90,
                "parser_version": 2,
            })
        return {"no": no, "name": name, "change_pct": 1.0, "stocks": stocks}

    def _previous(self, raw):
        return {
            (theme["no"], stock["code"]): 1_000_000_000
            for theme in raw for stock in theme["stocks"]
        }

    def test_first_snapshot_does_not_invent_interval_flow(self):
        raw = [self._raw_theme(1, "A", [1, 2, 3], [10, 20, 30])]
        themes, stocks = j5.build_theme_snapshot(raw)
        self.assertIsNone(themes[0]["interval_trading_value"])
        self.assertTrue(all(row["interval_trading_value"] is None for row in stocks))

    def test_overlap_weight_reduces_repeated_stock_contribution(self):
        shared = "005930"
        raw = [
            self._raw_theme(1, "A", [1, 1, 1], [1e9, 1e8, 1e8], repeated_code=shared),
            self._raw_theme(2, "B", [1, 1, 1], [1e9, 1e8, 1e8], repeated_code=shared),
        ]
        themes, stocks = j5.build_theme_snapshot(raw, previous_values=self._previous(raw))
        shared_rows = [row for row in stocks if row["stock_code"] == shared]
        self.assertTrue(all(row["theme_count"] == 2 for row in shared_rows))
        self.assertTrue(all(row["contribution_weight"] < 1 for row in shared_rows))
        self.assertGreater(themes[0]["weighted_interval_value"], 0)

    def test_interval_is_normalized_to_per_minute(self):
        raw = [self._raw_theme(1, "A", [1], [300_000_000])]
        themes, stocks = j5.build_theme_snapshot(
            raw, previous_values=self._previous(raw), interval_seconds=180
        )
        self.assertAlmostEqual(stocks[0]["interval_trading_value"], 100_000_000)
        self.assertAlmostEqual(themes[0]["interval_trading_value"], 100_000_000)

    def test_rank_alone_and_single_stock_event_do_not_fire(self):
        rows = []
        for no in range(1, 21):
            rows.append({
                "theme_no": no, "theme_name": str(no), "member_count": 10,
                "active_count": 1 if no == 20 else 0, "advancers": 8,
                "weighted_interval_value": 2e9 if no == 20 else 1e8 + no,
                "top_contributor_share": 0.95 if no == 20 else 0.2,
                "baseline_ratio": 2.0, "relative_change_pct": 0.5,
                "median_change_pct": 1.0,
            })
        signals = j5.detect_experiment_signals(rows, created_at=datetime(2026, 7, 23, 10))
        self.assertEqual(signals, [])

    def test_multi_stock_diffusion_can_fire_experimental_models(self):
        rows = []
        for no in range(1, 41):
            rows.append({
                "theme_no": no, "theme_name": str(no), "member_count": 10,
                "active_count": 6 if no == 40 else 2,
                "advancers": 8 if no == 40 else 4,
                "weighted_interval_value": 4e9 if no == 40 else 1e8 + no,
                "top_contributor_share": 0.25,
                "baseline_ratio": 2.0 if no == 40 else 0.8,
                "relative_change_pct": 0.6 if no == 40 else 0.0,
                "median_change_pct": 1.0 if no == 40 else 0.2,
            })
        signals = j5.detect_experiment_signals(rows, created_at=datetime(2026, 7, 23, 10))
        self.assertEqual({row["model"] for row in signals}, {"A", "B", "C"})
        self.assertTrue(all(row["stage"] == "실험감지" for row in signals))

    def test_same_top_contributors_do_not_duplicate_theme_alert(self):
        rows = []
        for no in range(1, 41):
            hot = no in (39, 40)
            rows.append({
                "theme_no": no, "theme_name": str(no), "member_count": 10,
                "active_count": 6 if hot else 1, "advancers": 8 if hot else 4,
                "weighted_interval_value": (4e9 + no) if hot else 1e8 + no,
                "activity_intensity": (2e9 + no) if hot else 1e7 + no,
                "top_contributor_share": 0.25,
                "top_contributors": ["005930", "000660", "035420", "035720", "066570"] if hot else [],
                "baseline_ratio": 2.0 if hot else 0.8,
                "relative_change_pct": 0.6 if hot else 0.0,
                "median_change_pct": 1.0 if hot else 0.2,
            })
        signals = j5.detect_experiment_signals(rows, created_at=datetime(2026, 7, 23, 10))
        for model in ("A", "B", "C"):
            self.assertEqual(sum(row["model"] == model for row in signals), 1)

    def test_lead_rank_is_not_raw_money_rank(self):
        rows = [{
            "theme_no": 1, "theme_name": "대형주 한종목", "member_count": 20,
            "active_count": 2, "advancers": 10, "activity_intensity": 10e9,
            "top_contributor_share": .82, "baseline_ratio": 1.1,
            "relative_change_pct": .2, "median_change_pct": .5,
        }, {
            "theme_no": 2, "theme_name": "다종목 확산", "member_count": 10,
            "active_count": 8, "advancers": 8, "activity_intensity": 2e9,
            "top_contributor_share": .25, "baseline_ratio": 2.0,
            "relative_change_pct": .5, "median_change_pct": 1.0,
        }]
        ranked = j5.rank_lead_themes(rows)
        self.assertEqual(ranked[0]["theme_name"], "다종목 확산")
        self.assertGreater(ranked[0]["lead_score"], ranked[1]["lead_score"])
        self.assertIn("단일종목 집중", ranked[1]["lead_flags"])

    def test_learning_score_limits_raw_activity_to_twenty_points(self):
        rows = [{
            "theme_no": 1, "theme_name": "A", "member_count": 10,
            "active_count": 10, "advancers": 10, "activity_intensity": 1e9,
            "top_contributor_share": .2, "baseline_ratio": None,
            "median_change_pct": 1.0,
        }]
        ranked = j5.rank_lead_themes(rows)
        self.assertEqual(ranked[0]["lead_stage"], "학습점수")
        self.assertLessEqual(ranked[0]["lead_components"]["횡단면 활동"], 20)


if __name__ == "__main__":
    unittest.main()

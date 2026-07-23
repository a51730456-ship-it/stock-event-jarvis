import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import jarvis5_store as store


class Jarvis5StoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "jarvis5.sqlite3"

    def tearDown(self):
        self.tempdir.cleanup()

    def _run(self):
        return {
            "captured_at": datetime(2026, 7, 23, 10, 30),
            "trade_date": "2026-07-23",
            "kind": "full",
            "status": "ok",
            "theme_count": 1,
            "stock_row_count": 1,
            "elapsed_seconds": 3.2,
            "interval_seconds": 180,
            "parser_version": 2,
        }

    def test_uses_separate_database_and_saves_atomic_snapshot(self):
        theme = {
            "theme_no": 7,
            "theme_name": "테스트테마",
            "change_pct": 1.2,
            "median_change_pct": 0.8,
            "relative_change_pct": 0.3,
            "member_count": 1,
            "advancers": 1,
            "active_count": 1,
            "total_trading_value": 5e10,
            "interval_trading_value": 2e9,
            "weighted_interval_value": 1.5e9,
            "top_contributor_share": 1.0,
        }
        stock = {
            "theme_no": 7,
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "price": 80_000,
            "change_pct": 1.0,
            "volume": 100,
            "trading_value": 8_000_000,
            "previous_volume": 90,
            "interval_trading_value": 2_000_000,
            "theme_count": 3,
            "contribution_weight": 3 ** -0.5,
            "parser_version": 2,
        }
        run_id = store.save_collection(
            self._run(), [theme], [stock], db_path=self.db_path
        )
        self.assertEqual(run_id, 1)
        self.assertEqual(store.latest_run(db_path=self.db_path)["theme_count"], 1)
        self.assertEqual(store.latest_theme_rows(db_path=self.db_path)[0]["theme_name"], "테스트테마")
        self.assertNotEqual(self.db_path, store.DB_PATH)

    def test_signal_is_idempotent_per_run_theme_model(self):
        run_id = store.save_collection(self._run(), [], [], db_path=self.db_path)
        signal = {
            "theme_no": 7,
            "model": "A",
            "score": 82,
            "stage": "실험",
            "reason": "테스트",
            "features": {"breadth": 0.7, "activity_intensity": 1.0},
            "created_at": datetime(2026, 7, 23, 10, 30),
        }
        self.assertEqual(store.save_signals(run_id, [signal], db_path=self.db_path), 1)
        self.assertEqual(store.save_signals(run_id, [signal], db_path=self.db_path), 0)

    def test_failed_run_does_not_require_snapshot_rows(self):
        run = dict(self._run(), error="network")
        run_id = store.save_failed_run(run, db_path=self.db_path)
        self.assertEqual(run_id, 1)
        self.assertEqual(store.latest_run(db_path=self.db_path)["status"], "failed")

    def test_previous_values_and_small_sample_outcome_summary(self):
        theme = {
            "theme_no": 7, "theme_name": "테스트테마", "median_change_pct": 0.5,
            "member_count": 2, "active_count": 2, "weighted_interval_value": 1e9,
        }
        stock = {
            "theme_no": 7, "stock_code": "005930", "stock_name": "삼성전자",
            "trading_value": 8_000_000, "theme_count": 1,
        }
        run_id = store.save_collection(self._run(), [theme], [stock], db_path=self.db_path)
        values = store.previous_stock_values("2026-07-23", db_path=self.db_path)
        self.assertEqual(values[(7, "005930")], 8_000_000)

        signal = {
            "theme_no": 7, "model": "A", "score": 82, "stage": "실험",
            "reason": "테스트", "features": {"activity_intensity": 1.0},
            "created_at": datetime(2026, 7, 23, 10, 30),
        }
        store.save_signals(run_id, [signal], db_path=self.db_path)
        pending = store.pending_signals(db_path=self.db_path)
        self.assertEqual(len(pending), 1)
        saved = store.save_outcomes([{
            "signal_id": pending[0]["id"], "horizon_minutes": 5,
            "evaluated_run_id": run_id, "forward_return_pct": 0.4,
            "relative_forward_return_pct": 0.2, "success": 1,
            "evaluated_at": datetime(2026, 7, 23, 10, 35),
        }], db_path=self.db_path)
        self.assertEqual(saved, 1)
        summary = store.outcome_summary(db_path=self.db_path)
        self.assertEqual(summary[0]["sample_count"], 1)
        self.assertFalse(summary[0]["enough_samples"])
        self.assertIsNone(summary[0]["hit_rate"])

    def test_same_time_baseline_uses_one_closest_run_per_distinct_day(self):
        for day, exact_value in ((20, 100.0), (21, 200.0), (22, 300.0)):
            theme = {
                "theme_no": 7, "theme_name": "테스트", "member_count": 1,
                "weighted_interval_value": 10_000.0,
            }
            run = dict(
                self._run(), captured_at=datetime(2026, 7, day, 10, 28),
                trade_date=f"2026-07-{day:02d}", interval_seconds=180,
            )
            store.save_collection(run, [theme], [], db_path=self.db_path)
            theme["weighted_interval_value"] = exact_value
            run["captured_at"] = datetime(2026, 7, day, 10, 30)
            store.save_collection(run, [theme], [], db_path=self.db_path)
        baseline = store.same_time_interval_baselines(
            datetime(2026, 7, 23, 10, 30), db_path=self.db_path
        )
        self.assertEqual(baseline[7], 200.0)

    def test_theme_activity_history_returns_latest_day_in_time_order(self):
        for minute, intensity in ((30, 100.0), (33, 180.0), (36, 240.0)):
            run = dict(
                self._run(),
                captured_at=datetime(2026, 7, 23, 10, minute),
                interval_seconds=180,
            )
            theme = {
                "theme_no": 7, "theme_name": "테스트테마", "member_count": 5,
                "active_count": 4, "activity_intensity": intensity,
            }
            store.save_collection(run, [theme], [], db_path=self.db_path)
        history = store.theme_activity_history([7], limit_runs=12, db_path=self.db_path)
        self.assertEqual(
            [row["activity_intensity"] for row in history[7]],
            [100.0, 180.0, 240.0],
        )


if __name__ == "__main__":
    unittest.main()

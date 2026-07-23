import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import jarvis5_collector as collector
import jarvis5_store as store


class Jarvis5CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "j5.sqlite3"

    def tearDown(self):
        self.tempdir.cleanup()

    def _raw(self, trading_value=2_000_000_000):
        return [{
            "no": 1, "name": "테스트", "change_pct": 1.0,
            "stocks": [
                {"code": f"00000{i}", "name": f"종목{i}", "price": 10_000,
                 "change_pct": 1.0, "trading_value": trading_value + i * 100,
                 "volume": 100, "previous_volume": 90, "parser_version": 2}
                for i in range(1, 5)
            ],
        }]

    def test_first_and_second_collection_are_separate_runs(self):
        with patch.object(collector, "fetch_raw_themes", return_value=(self._raw(), [])):
            first = collector.collect_once(db_path=self.db_path)
        with patch.object(
            collector, "fetch_raw_themes", return_value=(self._raw(3_000_000_000), [])
        ):
            second = collector.collect_once(db_path=self.db_path)
        self.assertTrue(first["ok"] and second["ok"])
        self.assertTrue(first["first_snapshot"])
        self.assertFalse(second["first_snapshot"])
        self.assertGreater(second["interval_seconds"], 0)
        self.assertEqual(len(store.recent_runs(db_path=self.db_path)), 2)
        self.assertGreater(
            store.latest_theme_rows(db_path=self.db_path)[0]["interval_trading_value"], 0
        )

    def test_fetch_failure_is_recorded_without_touching_other_database(self):
        with patch.object(collector, "fetch_raw_themes", side_effect=RuntimeError("network")):
            result = collector.collect_once(db_path=self.db_path)
        self.assertFalse(result["ok"])
        self.assertEqual(store.latest_run(db_path=self.db_path)["status"], "failed")

    def test_duplicate_collector_instance_is_rejected(self):
        with collector.collector_instance_lock(port=51656):
            with self.assertRaisesRegex(RuntimeError, "이미 실행"):
                with collector.collector_instance_lock(port=51656):
                    pass


if __name__ == "__main__":
    unittest.main()

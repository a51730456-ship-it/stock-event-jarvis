"""자비스5 클라우드 동기화 테스트 — 네트워크 없이 내보내기·들여오기만 검증한다.

노트북을 꺼 둔 날의 자료가 사라지지 않고, 여러 번 합쳐도 중복되지 않는 것이 핵심이다.
"""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import jarvis5_store as store
import jarvis5_sync as sync

SEOUL = ZoneInfo("Asia/Seoul")


def _theme_row(theme_no, intensity):
    return {
        "theme_no": theme_no,
        "theme_name": f"테마{theme_no}",
        "change_pct": 1.25,
        "median_change_pct": 0.5,
        "relative_change_pct": 0.75,
        "member_count": 12,
        "advancers": 8,
        "decliners": 3,
        "unchanged": 1,
        "active_count": 9,
        "total_trading_value": 1.2345678901e11,
        "interval_trading_value": 3.456789012e8,
        "weighted_interval_value": 2.345678901e8,
        "activity_intensity": intensity,
        "baseline_ratio": 1.234567,
        "top_contributor_share": 0.4321,
        "stale_count": 0,
    }


def _stock_row(theme_no, code):
    return {
        "theme_no": theme_no,
        "stock_code": code,
        "stock_name": f"종목{code}",
        "price": 61500.0,
        "change_pct": -1.5,
        "volume": 123456.0,
        "trading_value": 7.6543210987e9,
        "previous_volume": 98765.0,
        "interval_trading_value": 1.234567e7,
        "theme_count": 2,
        "contribution_weight": 0.7071,
        "parser_version": 2,
    }


def _fill(db_path, trade_date="2026-07-23", runs=3):
    """하루치 수집을 흉내 내 DB를 채운다."""
    base = datetime.fromisoformat(f"{trade_date}T09:00:00+09:00")
    for index in range(runs):
        captured_at = base + timedelta(minutes=3 * index)
        store.save_collection(
            {
                "captured_at": captured_at,
                "trade_date": trade_date,
                "kind": "full",
                "status": "ok",
                "elapsed_seconds": 2.5,
                "interval_seconds": None if index == 0 else 180.0,
                "parser_version": 2,
                "error": None,
            },
            [_theme_row(1, 1.0e8 + index * 1e7), _theme_row(2, 5.0e7 + index * 1e6)],
            [_stock_row(1, "005930"), _stock_row(2, "000660")],
            db_path=db_path,
        )


class ExportImportTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.source_db = self.dir / "source.sqlite3"
        self.target_db = self.dir / "target.sqlite3"
        self.out = self.dir / "out"
        _fill(self.source_db)

    def test_export_writes_three_files(self):
        result = sync.export_day("2026-07-23", out_dir=self.out, db_path=self.source_db)
        self.assertTrue(result["ok"])
        self.assertEqual(result["run_count"], 3)
        self.assertEqual(result["theme_row_count"], 6)
        # 종목행은 마지막 수집분만 담는다 — 저장소가 감당할 크기로 줄이기 위해서다.
        self.assertEqual(result["stock_row_count"], 2)
        for part in ("runs", "themes", "stocks"):
            self.assertTrue(sync.part_path("2026-07-23", part, self.out).exists(), part)
        # 쓰다 만 임시 파일이 남으면 안 된다.
        self.assertEqual(list(self.out.glob("*.tmp")), [])

    def test_export_of_missing_day_is_reported_not_raised(self):
        result = sync.export_day("2020-01-02", out_dir=self.out, db_path=self.source_db)
        self.assertFalse(result["ok"])
        self.assertIn("자료가 없습니다", result["error"])

    def test_import_restores_values_and_is_idempotent(self):
        sync.export_day("2026-07-23", out_dir=self.out, db_path=self.source_db)
        first = sync.import_day("2026-07-23", directory=self.out, db_path=self.target_db)
        self.assertEqual(first["added_runs"], 3)
        self.assertEqual(first["added_theme_rows"], 6)

        # 두 번째로 합쳐도 늘어나지 않아야 한다(자료받기를 여러 번 눌러도 안전).
        second = sync.import_day("2026-07-23", directory=self.out, db_path=self.target_db)
        self.assertEqual(second["added_runs"], 0)
        self.assertEqual(second["skipped_runs"], 3)

        runs = store.recent_runs(limit=50, db_path=self.target_db)
        self.assertEqual(len(runs), 3)

    def test_imported_values_match_the_source(self):
        sync.export_day("2026-07-23", out_dir=self.out, db_path=self.source_db)
        sync.import_day("2026-07-23", directory=self.out, db_path=self.target_db)

        def rows(db):
            with store.connection(db) as conn:
                return [
                    dict(row)
                    for row in conn.execute(
                        """
                        SELECT r.captured_at, r.interval_seconds, t.theme_no,
                               t.theme_name, t.member_count, t.advancers,
                               t.activity_intensity, t.top_contributor_share
                        FROM theme_snapshots t JOIN collection_runs r ON r.id = t.run_id
                        ORDER BY r.captured_at, t.theme_no
                        """
                    )
                ]

        before, after = rows(self.source_db), rows(self.target_db)
        self.assertEqual(len(before), len(after))
        for left, right in zip(before, after):
            self.assertEqual(left["captured_at"], right["captured_at"])
            self.assertEqual(left["theme_no"], right["theme_no"])
            self.assertEqual(left["theme_name"], right["theme_name"])
            self.assertEqual(left["member_count"], right["member_count"])
            self.assertEqual(left["interval_seconds"], right["interval_seconds"])
            # 유효숫자 8자리로 줄여 담으므로 아주 작은 차이만 허용한다.
            self.assertAlmostEqual(
                left["activity_intensity"], right["activity_intensity"],
                delta=abs(left["activity_intensity"]) * 1e-7,
            )

    def test_import_keeps_minichart_inputs(self):
        """미니차트는 captured_at과 interval_seconds가 있어야 그려진다."""
        sync.export_day("2026-07-23", out_dir=self.out, db_path=self.source_db)
        sync.import_day("2026-07-23", directory=self.out, db_path=self.target_db)
        history = store.theme_activity_history([1], limit_runs=12, db_path=self.target_db)
        points = history[1]
        # 첫 수집은 interval_seconds가 없어 기록에서 빠진다 — 나머지 둘이 남는다.
        self.assertEqual(len(points), 2)
        self.assertTrue(all(point["captured_at"] for point in points))
        self.assertTrue(all(point["interval_seconds"] for point in points))

    def test_import_dir_merges_every_day_and_lists_dates(self):
        _fill(self.source_db, trade_date="2026-07-22", runs=2)
        sync.export_day("2026-07-22", out_dir=self.out, db_path=self.source_db)
        sync.export_day("2026-07-23", out_dir=self.out, db_path=self.source_db)

        self.assertEqual(sync.available_dates(self.out), ["2026-07-22", "2026-07-23"])
        merged = sync.import_dir(self.out, db_path=self.target_db)
        self.assertTrue(merged["ok"])
        self.assertEqual(merged["day_count"], 2)
        self.assertEqual(merged["added_runs"], 5)

    def test_import_dir_without_files_reports_instead_of_crashing(self):
        empty = self.dir / "none"
        result = sync.import_dir(empty, db_path=self.target_db)
        self.assertFalse(result["ok"])
        self.assertIn("자료가 아직 없습니다", result["error"])


class RoundingTests(unittest.TestCase):
    def test_significant_digits_keep_practical_precision(self):
        self.assertEqual(sync._round(5238241.703046003), 5238241.7)
        self.assertEqual(sync._round(0.0), 0.0)
        self.assertIsNone(sync._round(None))
        self.assertEqual(sync._round("글자"), "글자")
        self.assertEqual(sync._round(12), 12)


if __name__ == "__main__":
    unittest.main()

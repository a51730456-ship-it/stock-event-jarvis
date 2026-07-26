"""당일 시가·고가·저가 저장 경로 전체 검증 (2026-07-26 추가).

이 값은 지나가면 소급할 수 없다. 그래서 다음 세 구간이 하나라도 끊기면
그날 자료가 영영 반쪽이 된다.

    시세 조회 → 종목행 병합 → DB 저장 → 클라우드 내보내기 → 다시 들여오기

각 구간을 네트워크 없이 확인한다. 특히 마지막 두 구간은 CLAUDE.md 10항
("스키마를 바꾸면 jarvis5_sync.py 필드 목록도 같이 고친다")을 어겼을 때
조용히 자료가 빠지는 자리라 반드시 왕복으로 본다.
"""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import jarvis5_collector as collector
import jarvis5_data as engine
import jarvis5_store as store
import jarvis5_sync as sync

SEOUL = ZoneInfo("Asia/Seoul")


def _query(db_path, sql):
    """조회하고 연결을 확실히 닫는다.

    ``with sqlite3.connect(...)``는 파이썬에서 연결을 닫지 않고 트랜잭션만
    정리한다. 윈도우에서는 열린 채로 남으면 임시폴더를 지울 때 막힌다.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql)]
    finally:
        conn.close()


def _raw_themes(codes=("005930", "000660")):
    return [{
        "no": 1, "name": "테스트테마", "change_pct": 1.0,
        "stocks": [
            {"code": code, "name": f"종목{code}", "price": 1100.0,
             "change_pct": 1.0, "trading_value": 2_000_000_000.0,
             "volume": 100.0, "previous_volume": 90.0, "parser_version": 2}
            for code in codes
        ],
    }]


def _quote(code, *, high=1200.0, low=900.0, open_=1000.0, tradable=True, cap=5.0e11):
    return {
        "code": code, "price": 1100.0,
        "day_open": open_, "day_high": high, "day_low": low,
        "market_cap": cap, "tradable": tradable,
    }


class SnapshotMergeTests(unittest.TestCase):
    """종목행에 시세가 제대로 붙는가."""

    def test_day_prices_and_market_cap_are_merged(self):
        _themes, stocks = engine.build_theme_snapshot(
            _raw_themes(), quotes={"005930": _quote("005930")}
        )
        row = next(row for row in stocks if row["stock_code"] == "005930")
        self.assertEqual(row["day_open"], 1000.0)
        self.assertEqual(row["day_high"], 1200.0)
        self.assertEqual(row["day_low"], 900.0)
        self.assertEqual(row["market_cap"], 5.0e11)

    def test_trade_stopped_stock_keeps_prices_empty(self):
        """거래정지 종목은 고가·저가가 0이거나 옛값으로 굳어 있다.

        저장해 두면 나중에 종가위치를 계산할 때 0으로 나누거나 어제 값으로
        오늘을 판정하게 된다. 아예 비워 둬야 '자료 없음'으로 걸러진다.
        """
        _themes, stocks = engine.build_theme_snapshot(
            _raw_themes(), quotes={"005930": _quote("005930", high=0.0, low=0.0, tradable=False)}
        )
        row = next(row for row in stocks if row["stock_code"] == "005930")
        self.assertIsNone(row.get("day_high"))
        self.assertIsNone(row.get("day_low"))
        # 시가총액은 거래정지와 무관하게 유효하므로 남긴다.
        self.assertEqual(row["market_cap"], 5.0e11)

    def test_missing_quote_keeps_old_behaviour(self):
        """시세를 못 받은 종목도 예전처럼 저장돼야 한다. 수집이 멈추면 안 된다."""
        _themes, stocks = engine.build_theme_snapshot(_raw_themes(), quotes={})
        row = next(row for row in stocks if row["stock_code"] == "005930")
        self.assertIsNone(row.get("day_high"))
        self.assertEqual(row["price"], 1100.0)
        self.assertEqual(row["trading_value"], 2_000_000_000.0)

    def test_quotes_argument_is_optional(self):
        """옛 호출부가 quotes 없이 불러도 깨지지 않는다."""
        themes, stocks = engine.build_theme_snapshot(_raw_themes())
        self.assertTrue(themes and stocks)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "j5.sqlite3"

    def tearDown(self):
        self.tempdir.cleanup()

    def _collect(self, quotes):
        with patch.object(collector, "fetch_raw_themes", return_value=(_raw_themes(), [])), \
             patch.object(collector, "_fetch_quotes", return_value=quotes):
            return collector.collect_once(db_path=self.db_path)

    def _stored(self):
        return {
            row["stock_code"]: row
            for row in _query(
                self.db_path,
                "SELECT stock_code, day_open, day_high, day_low, market_cap "
                "FROM theme_stock_snapshots",
            )
        }

    def test_collected_day_prices_reach_the_database(self):
        result = self._collect({"005930": _quote("005930")})
        self.assertTrue(result["ok"])
        stored = self._stored()
        self.assertEqual(stored["005930"]["day_high"], 1200.0)
        self.assertEqual(stored["005930"]["day_low"], 900.0)
        self.assertIsNone(stored["000660"]["day_high"])  # 시세를 못 받은 종목

    def test_quote_failure_does_not_stop_collection(self):
        """시세 조회가 통째로 실패해도 테마 수집은 예전대로 끝나야 한다.

        시세는 덤이고 테마 수집이 본체다. 네이버 시세가 잠깐 막혔다고 그날
        수집이 통째로 비면 안 된다. ``_fetch_quotes``가 예외를 안에서 삼키는
        것이 그 장치이므로, 진짜 호출 경로로 확인한다.
        """
        with patch.object(collector, "fetch_raw_themes", return_value=(_raw_themes(), [])), \
             patch("naver_stock_quote.get_quotes", side_effect=RuntimeError("네트워크 오류")):
            result = collector.collect_once(db_path=self.db_path)

        self.assertTrue(result["ok"])
        self.assertEqual(result["stock_row_count"], 2)
        stored = self._stored()
        self.assertIsNone(stored["005930"]["day_high"])   # 시세는 비고
        self.assertEqual(len(stored), 2)                  # 종목행은 그대로 남는다

    def test_fetch_quotes_asks_for_every_collected_code(self):
        captured = {}

        def fake(codes, **kwargs):
            captured["codes"] = list(codes)
            return {}

        with patch("naver_stock_quote.get_quotes", side_effect=fake):
            collector._fetch_quotes(_raw_themes(("005930", "000660", "005930")))
        self.assertEqual(captured["codes"], ["000660", "005930"])  # 중복 제거·정렬


class CloudRoundTripTests(unittest.TestCase):
    """클라우드가 모은 자료를 내보내고 다시 들여올 때 새 칸이 빠지지 않는가.

    CLAUDE.md 10항을 어겨 필드 목록을 안 고치면 여기서 잡힌다.
    """

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.source_db = Path(self.tempdir.name) / "source.sqlite3"
        self.target_db = Path(self.tempdir.name) / "target.sqlite3"
        self.out_dir = Path(self.tempdir.name) / "out"
        self.trade_date = "2026-07-27"

        captured_at = datetime.fromisoformat(f"{self.trade_date}T15:18:00+09:00")
        stocks = [
            {"theme_no": 1, "stock_code": "005930", "stock_name": "종목A",
             "price": 1100.0, "change_pct": 1.0, "volume": 100.0,
             "trading_value": 2.0e9, "previous_volume": 90.0,
             "interval_trading_value": 1.0e7, "theme_count": 1,
             "contribution_weight": 1.0, "parser_version": 2,
             "day_open": 1000.0, "day_high": 1200.0, "day_low": 900.0,
             "market_cap": 5.0e11},
        ]
        store.save_collection(
            {"captured_at": captured_at, "trade_date": self.trade_date, "kind": "full",
             "status": "ok", "elapsed_seconds": 2.0, "interval_seconds": 180.0,
             "parser_version": 2, "error": None},
            [{"theme_no": 1, "theme_name": "테마1", "change_pct": 1.0,
              "median_change_pct": 0.5, "relative_change_pct": 0.5, "member_count": 1,
              "advancers": 1, "decliners": 0, "unchanged": 0, "active_count": 1,
              "total_trading_value": 2.0e9, "interval_trading_value": 1.0e7,
              "weighted_interval_value": 1.0e7, "activity_intensity": 1.0e7,
              "baseline_ratio": None, "top_contributor_share": 1.0, "stale_count": 0}],
            stocks,
            db_path=self.source_db,
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_day_prices_survive_export_and_import(self):
        exported = sync.export_day(
            self.trade_date, out_dir=self.out_dir, db_path=self.source_db
        )
        self.assertTrue(exported["ok"], exported.get("error"))

        imported = sync.import_day(
            self.trade_date, directory=self.out_dir, db_path=self.target_db
        )
        self.assertTrue(imported["ok"], imported.get("error"))

        rows = _query(
            self.target_db,
            "SELECT day_open, day_high, day_low, market_cap "
            "FROM theme_stock_snapshots WHERE stock_code = '005930'",
        )
        row = rows[0] if rows else None

        self.assertIsNotNone(row, "내보낸 종목행이 들여오기에서 사라졌다")
        self.assertEqual(row["day_open"], 1000.0)
        self.assertEqual(row["day_high"], 1200.0)
        self.assertEqual(row["day_low"], 900.0)
        self.assertEqual(row["market_cap"], 5.0e11)

    def test_stock_field_list_matches_the_table(self):
        """필드 목록과 실제 표의 칸이 어긋나면 조용히 자료가 샌다."""
        store.ensure_schema(self.source_db)
        columns = {
            row["name"]
            for row in _query(self.source_db, "PRAGMA table_info(theme_stock_snapshots)")
        }
        missing = set(sync._STOCK_FIELDS) - columns - {"captured_at"}
        self.assertFalse(missing, f"내보내기 목록에 표에 없는 칸이 있다: {missing}")
        for column in ("day_open", "day_high", "day_low", "market_cap"):
            self.assertIn(column, sync._STOCK_FIELDS,
                          f"{column}이 내보내기 목록에 없다 (CLAUDE.md 10항)")


if __name__ == "__main__":
    unittest.main()

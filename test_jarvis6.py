"""자비스6 테스트 — 조건 계산·기록·익일 결과 채우기.

여기서 지키려는 것.
1) 종가위치·윗꼬리에서 0으로 나누지 않는다
2) 클릭 한 번에 그 순간이 통째로 저장된다
3) **익일 결과를 채우는 코드가 실제로 불린다** — 이걸 빠뜨려 한 번 사고가 났다
4) 표본이 적으면 성적을 숨긴다
5) 경고가 있어도 막지 않는다
"""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

import jarvis6_data as j6
import jarvis6_store as store


def _stock(**over):
    base = {"price": 92400.0, "day_open": 90000.0, "day_high": 92800.0,
            "day_low": 89500.0, "trading_value": 4.18e11, "market_cap": 2.2e13,
            "reason": "", "continuation": "", "invalidation": ""}
    base.update(over)
    return base


def _metrics(**over):
    base = {"from_high_pct": -2.1, "high52_days_ago": 38, "avg_trading_value": 1.9e11,
            "change_pct": 5.2, "ret5": 8.0, "prev_close": 87900.0, "current": 92400.0}
    base.update(over)
    return base


class ConditionTests(unittest.TestCase):
    def test_all_chart_and_strength_conditions_pass(self):
        e = j6.evaluate(_stock(), _metrics(), {"both_buy_days5": 4}, {"advancers": 4})
        self.assertEqual(e["passed"], 7)
        self.assertEqual(e["total"], 7)

    def test_material_is_empty_until_a_person_writes_it(self):
        """재료 두 칸은 사람만 채운다. 기계가 채운 척하면 안 된다."""
        e = j6.evaluate(_stock(), _metrics(), {}, {})
        self.assertFalse(any(ok for _n, ok, _v in e["material"]))
        e2 = j6.evaluate(_stock(reason="방산 수출", continuation="내일 발표"),
                         _metrics(), {}, {})
        self.assertTrue(all(ok for _n, ok, _v in e2["material"]))

    def test_high_equals_low_does_not_divide_by_zero(self):
        """상한가 직행이나 거래정지면 고가=저가다."""
        e = j6.evaluate(_stock(day_high=90000.0, day_low=90000.0, price=90000.0),
                        _metrics(), {}, {})
        self.assertIsNone(e["upper_wick"])
        self.assertIsNone(e["location"])

    def test_missing_day_prices_are_tolerated(self):
        e = j6.evaluate(_stock(day_high=None, day_low=None), _metrics(), {}, {})
        self.assertIsNone(e["location"])

    def test_big_cap_needs_more_supply_days_than_small_cap(self):
        """시총 1조 위에서는 외인·기관을 무겁게 본다. 중소형은 개인이 주도하기도 한다."""
        big = j6.evaluate(_stock(market_cap=2.2e13), _metrics(), {"both_buy_days5": 2}, {})
        small = j6.evaluate(_stock(market_cap=3.0e11), _metrics(), {"both_buy_days5": 2}, {})
        supply = lambda e: dict((n, ok) for n, ok, _v in e["strength"])["외인·기관 동반"]
        self.assertFalse(supply(big))
        self.assertTrue(supply(small))

    def test_overheated_stock_is_warned_not_blocked(self):
        """막지 않는다. 경고만 남기고 클릭은 되게 둔다."""
        e = j6.evaluate(_stock(), _metrics(change_pct=25.0), {}, {})
        self.assertTrue(e["warnings"])
        self.assertGreater(e["passed"], 0)   # 조건 계산은 그대로 돈다

    def test_cutoff_is_before_closing_auction(self):
        """15:20이 지나면 종가가 정해진다. 그 전에 끊어야 한다."""
        self.assertLess(j6.CUTOFF.hour * 60 + j6.CUTOFF.minute, 15 * 60 + 20)


class PhaseTests(unittest.TestCase):
    """실시간 값을 언제 쓰는가.

    한 번 사고가 났다. '관찰 구간(14:30~)'으로 실시간을 껐더니 09:00~14:29
    내내 어제 고가·저가가 오늘 값으로 나왔다. watching과 live는 다르다.
    """

    def _at(self, day: str, clock: str) -> dict:
        stamp = pd.Timestamp(f"{day} {clock}", tz="Asia/Seoul").to_pydatetime()
        return j6.market_phase(stamp)

    # 2026-07-27은 월요일, 2026-07-26은 일요일이다.
    def test_morning_is_live_but_not_watching(self):
        phase = self._at("2026-07-27", "10:30")
        self.assertTrue(phase["live"], "오전에도 체결은 정상이다")
        self.assertFalse(phase["watching"])

    def test_watch_window_is_live_too(self):
        phase = self._at("2026-07-27", "15:00")
        self.assertTrue(phase["live"])
        self.assertTrue(phase["watching"])

    def test_closing_auction_is_not_live(self):
        """15:20부터는 단일가라 실시간에 NXT가 섞인다."""
        for clock in ("15:19", "15:25", "16:00"):
            with self.subTest(clock=clock):
                self.assertFalse(self._at("2026-07-27", clock)["live"])

    def test_before_open_and_weekend_are_not_live(self):
        self.assertFalse(self._at("2026-07-27", "08:30")["live"])
        self.assertFalse(self._at("2026-07-26", "15:00")["live"])

    def test_screen_text_and_cutoff_agree(self):
        """화면·설명·명세가 전부 15:18이다. 코드만 다르면 안 된다."""
        self.assertEqual((j6.CUTOFF.hour, j6.CUTOFF.minute), (15, 18))
        self.assertTrue(self._at("2026-07-27", "15:18:30")["watching"])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Path(self.tempdir.name) / "j6.sqlite3"

    def tearDown(self):
        self.tempdir.cleanup()

    def _row(self, **over):
        stock = _stock(**over.pop("stock", {}))
        metrics = _metrics()
        return {"code": "042660", "name": "한화오션", "theme": "조선",
                "stock": stock, "metrics": metrics, "theme_row": {"advancers": 4},
                "eval": j6.evaluate(stock, metrics, {"both_buy_days5": 4},
                                    {"advancers": 4}), **over}

    def test_one_click_stores_the_whole_snapshot(self):
        store.save_pick(self._row(), db_path=self.db)
        saved = store.list_picks(db_path=self.db)[0]
        self.assertEqual(saved["action"], "bought")
        self.assertEqual(saved["price"], 92400.0)
        self.assertEqual(saved["day_high"], 92800.0)
        self.assertAlmostEqual(saved["from_high_pct"], -2.1)
        self.assertEqual(saved["passed"], 7)

    def test_same_day_same_stock_updates_instead_of_duplicating(self):
        store.save_pick(self._row(), db_path=self.db)
        store.save_pick(self._row(), action="skipped", db_path=self.db)
        picks = store.list_picks(db_path=self.db)
        self.assertEqual(len(picks), 1)
        self.assertEqual(picks[0]["action"], "skipped")

    def test_reason_can_be_written_later(self):
        pid = store.save_pick(self._row(), db_path=self.db)
        store.update_notes(pid, reason="방산 수출 보도", db_path=self.db)
        self.assertEqual(store.list_picks(db_path=self.db)[0]["reason"], "방산 수출 보도")

    def test_outcome_subtracts_cost(self):
        pid = store.save_pick(self._row(), db_path=self.db)
        store.save_outcome(pid, next_open=93400.0, entry=92400.0, db_path=self.db)
        saved = store.list_picks(db_path=self.db)[0]
        gross = (93400 / 92400 - 1) * 100
        self.assertAlmostEqual(saved["net_pct"], gross - store.ROUND_TRIP_COST * 100, places=6)

    def test_fill_outcomes_is_actually_wired(self):
        """익일 결과를 채우는 코드가 실제로 도는지.

        save_outcome만 있고 부르는 곳이 없어 결과가 영영 안 붙던 적이 있다.
        """
        pid = store.save_pick(self._row(), db_path=self.db)
        trade_date = store.list_picks(db_path=self.db)[0]["trade_date"]
        after = pd.Timestamp(trade_date) + pd.Timedelta(days=1)
        frame = pd.DataFrame({"Open": [90000.0, 93400.0]},
                             index=[pd.Timestamp(trade_date), after])

        result = store.fill_outcomes(
            quote_fn=lambda codes: {},
            daily_fn=lambda code: frame,
            db_path=self.db,
        )
        self.assertEqual(result, {"checked": 1, "filled": 1})
        saved = store.list_picks(db_path=self.db)[0]
        self.assertEqual(saved["next_open"], 93400.0)
        self.assertIsNotNone(saved["net_pct"])
        self.assertEqual(pid, saved["id"])

    def test_fill_outcomes_waits_when_next_day_has_not_come(self):
        store.save_pick(self._row(), db_path=self.db)
        trade_date = store.list_picks(db_path=self.db)[0]["trade_date"]
        frame = pd.DataFrame({"Open": [90000.0]}, index=[pd.Timestamp(trade_date)])
        result = store.fill_outcomes(quote_fn=lambda c: {}, daily_fn=lambda c: frame,
                                     db_path=self.db)
        self.assertEqual(result["filled"], 0)

    def test_review_hides_numbers_until_enough_samples(self):
        """10건 보고 승률을 말하면 그건 거짓말이다."""
        pid = store.save_pick(self._row(), db_path=self.db)
        store.save_outcome(pid, next_open=93400.0, entry=92400.0, db_path=self.db)
        summary = store.review(db_path=self.db)
        self.assertLess(summary["total"], store.MIN_SAMPLE)
        self.assertFalse(summary["groups"][0]["enough"])
        self.assertNotIn("win", summary["groups"][0])

    def test_skipped_picks_are_not_given_outcomes(self):
        store.save_pick(self._row(), action="skipped", db_path=self.db)
        self.assertEqual(store.pending_outcomes(db_path=self.db), [])


class AutoLogTests(unittest.TestCase):
    """사람이 안 눌러도 자료가 쌓이는가.

    이게 자비스6의 목숨줄이다. 안 쌓이면 30건이 영영 안 차고,
    30건이 안 차면 이 매매가 되는지 끝까지 모른다.
    """

    def setUp(self):
        import jarvis6_autolog as autolog
        self.autolog = autolog
        self.tempdir = tempfile.TemporaryDirectory()
        self.out = Path(self.tempdir.name) / "jarvis6"
        self.db = Path(self.tempdir.name) / "j6.sqlite3"
        stock = _stock()
        metrics = _metrics()
        self.row = {"code": "042660", "name": "한화오션", "theme": "조선",
                    "stock": stock, "metrics": metrics,
                    "flow": {"both_buy_days5": 4}, "theme_row": {"advancers": 4},
                    "eval": j6.evaluate(stock, metrics, {"both_buy_days5": 4},
                                        {"advancers": 4})}
        self.when = datetime(2026, 7, 27, 15, 18, tzinfo=ZoneInfo("Asia/Seoul"))

    def tearDown(self):
        self.tempdir.cleanup()

    def _build(self):
        return {"ok": True, "rows": [self.row], "market": {}, "checked_at": "15:18"}

    def test_only_good_rows_are_written(self):
        """화면에서 초록으로 보이는 것만 남긴다. 기준은 한 곳에만 있다."""
        weak = dict(self.row, code="000660", name="약한종목",
                    eval=j6.evaluate(_stock(day_high=99999.0), _metrics(from_high_pct=-40.0),
                                     {}, {}))
        result = self.autolog.collect(
            now=self.when, export_dir=self.out,
            builder=lambda: {"ok": True, "rows": [self.row, weak]})
        self.assertEqual(result["saved"], 1)

    def test_importing_twice_does_not_double_count(self):
        """다시 불러도 성적이 부풀면 안 된다."""
        self.autolog.collect(now=self.when, export_dir=self.out, builder=self._build)
        for _ in range(3):
            store.import_auto_logs(source_dir=self.out, db_path=self.db)
        self.assertEqual(store.headline(db_path=self.db)["recorded"], 1)

    def test_trade_date_comes_from_the_file_not_today(self):
        """어제 남긴 것을 오늘 들여와도 어제 것이어야 한다."""
        self.autolog.collect(now=self.when, export_dir=self.out, builder=self._build)
        store.import_auto_logs(source_dir=self.out, db_path=self.db)
        self.assertEqual(store.list_picks(db_path=self.db)[0]["trade_date"], "2026-07-27")

    def test_broken_file_does_not_stop_the_rest(self):
        self.autolog.collect(now=self.when, export_dir=self.out, builder=self._build)
        (self.out / "2026-07-28.json").write_text("{쓰다 만", encoding="utf-8")
        self.assertEqual(
            store.import_auto_logs(source_dir=self.out, db_path=self.db)["rows"], 1)

    def _run_main(self, when: datetime):
        """시각을 시험이 쥐고 부른다.

        예전에는 `main()`이 진짜 시계를 봤다. 그래서 평일 한국시각
        14:30~15:18에 시험을 돌리면 정말 관찰 구간이라 파일이 남고 이 시험이
        깨졌다(2026-08-20 재현). 종목도 시험이 준다 — 진짜 시세를 받으러
        나가면 시험 한 건에 14초가 걸렸다.
        """
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.autolog.main(["--export-dir", str(self.out)],
                                     now=when, builder=self._build)
        return code, buf.getvalue()

    def test_writes_during_the_watch_window(self):
        """관찰 구간에는 사람이 안 눌러도 그날 것이 남아야 한다."""
        code, out = self._run_main(self.when)   # 2026-07-27(월) 15:18
        self.assertEqual(code, 0)
        self.assertEqual([p.name for p in self.out.glob("*.json")],
                         ["2026-07-27.json"])
        self.assertIn("관찰 구간", out)

    def test_refuses_to_run_after_the_closing_auction(self):
        """15:20이 지난 뒤 남기면 종가를 보고 종가에 샀다고 적는 셈이다."""
        after = datetime(2026, 7, 27, 15, 25, tzinfo=ZoneInfo("Asia/Seoul"))
        code, out = self._run_main(after)
        self.assertEqual(code, 0)
        self.assertFalse(list(self.out.glob("*.json")) if self.out.exists() else [])
        self.assertIn("남기지 않습니다", out)

    def test_headline_hides_the_score_until_enough(self):
        head = store.headline(db_path=self.db)
        self.assertFalse(head["enough"])
        self.assertIsNone(head["avg"])


if __name__ == "__main__":
    unittest.main()

"""날짜별 목록 창고(picklist_store)와 수집기가 지켜야 할 것들.

가장 중요한 두 가지를 시험으로 굳혀 둔다.
  * 저장은 **값을 고치지 않는다** — 화면에 뜬 숫자가 그대로 남아야 나중에 성적을
    잴 수 있다.
  * 조회에 실패한 날이 **멀쩡한 어제 자료를 지우면 안 된다.**
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import picklist_store as store


def _crash_result():
    """급락 갈래 결과 흉내 — 실제 jarvis3_data가 내는 모양을 줄여 놓은 것."""
    return {
        "ok": True,
        "mode": "crash",
        "rows": [
            {
                "ticker": "TSM", "name": "TSMC", "themes": ["반도체", "AI·데이터센터"],
                "score": 78.5, "pullback_rank": 1,
                "metrics": {"current": 210.5, "change_pct": -1.2, "from_high_pct": -12.69},
                "judged_from_high_pct": -21.78,
                "bucket_label": "고점 대비 -20~-30%",
                "hold_days": 60, "together_count": 4, "recent_gain_pct": -6.3,
            },
            {
                "ticker": "AMD", "name": "AMD", "themes": ["반도체"],
                "score": 61.0, "pullback_rank": 2,
                "metrics": {"current": 150.0, "change_pct": 0.4, "from_high_pct": -31.0},
                "judged_from_high_pct": -35.2,
                "bucket_label": "고점 대비 -30~-50%",
                "hold_days": 60, "together_count": 1, "recent_gain_pct": 2.0,
            },
        ],
    }


def _pullback_result():
    """눌림목 갈래 — 점수가 ``pullback.score`` 안에 들어 있는 모양이다."""
    return {
        "ok": True,
        "rows": [{
            "ticker": "NVDA", "name": "엔비디아", "themes": ["AI·데이터센터"],
            "pullback_rank": 1,
            "pullback": {"score": 88.0, "from_high_pct": -7.5, "high52_days_ago": 4},
            "metrics": {"current": 900.0, "change_pct": 1.1},
        }],
    }


def _top7_result():
    return {
        "ok": True,
        "rows": [{
            "ticker": "MSFT", "name": "마이크로소프트", "sources": ["클라우드·SaaS"],
            "score": 84.0, "pick_rank": 1, "top7_origin": "상승장",
            "plan": {"state": "기준가 대기"},
            "metrics": {"current": 500.0, "change_pct": 0.2},
        }],
    }


class NormalizeTests(unittest.TestCase):
    def test_values_are_copied_not_recomputed(self):
        rows = store.rows_from_result(
            _crash_result(), market="US", list_kind="crash",
            trade_date="2026-08-09", saved_at="2026-08-09T16:00:00+09:00")
        self.assertEqual(len(rows), 2)
        first = rows[0]
        self.assertEqual(first["rank"], 1)
        self.assertEqual(first["code"], "TSM")
        self.assertEqual(first["name"], "TSMC")
        self.assertEqual(first["themes"], "반도체 · AI·데이터센터")
        self.assertEqual(first["score"], 78.5)
        # 급락 갈래의 두 낙폭이 **따로** 남아야 한다. 갈래를 정한 것은 기준일 낙폭이고
        # 오늘 낙폭은 보여만 주는 값이라, 한 칸에 섞으면 나중에 못 가른다.
        self.assertEqual(first["judged_from_high_pct"], -21.78)
        self.assertEqual(first["from_high_pct"], -12.69)
        self.assertEqual(first["bucket_label"], "고점 대비 -20~-30%")
        self.assertEqual(first["price"], 210.5)

    def test_pullback_score_is_found_inside_its_own_box(self):
        rows = store.rows_from_result(
            _pullback_result(), market="US", list_kind="pullback",
            trade_date="2026-08-09")
        self.assertEqual(rows[0]["score"], 88.0)
        # 상승장·눌림목에서 '고점 찍고 며칠'은 이 칸에 담는다.
        self.assertEqual(rows[0]["wait_days"], 4)
        self.assertEqual(rows[0]["from_high_pct"], -7.5)

    def test_top7_ranks_by_its_own_number_not_the_pullback_one(self):
        """순위 7의 줄은 눌림목에서 데려온 것이라 눌림목 번호를 달고 있다.

        그것을 먼저 보면 순위 7 표에 같은 번호가 두 번 찍힌다(2026-08-09 실제 자료).
        """
        result = {"ok": True, "rows": [
            {"ticker": "A", "name": "가", "pick_rank": 1, "pullback_rank": 3},
            {"ticker": "B", "name": "나", "pick_rank": 2, "pullback_rank": 1},
        ]}
        rows = store.rows_from_result(result, market="KR", list_kind="top7",
                                      trade_date="2026-08-09")
        self.assertEqual([row["rank"] for row in rows], [1, 2])

    def test_top7_keeps_the_branch_it_came_from(self):
        rows = store.rows_from_result(
            _top7_result(), market="US", list_kind="top7", trade_date="2026-08-09")
        self.assertEqual(rows[0]["origin"], "상승장")
        self.assertEqual(rows[0]["state"], "기준가 대기")
        self.assertEqual(rows[0]["score"], 84.0)

    def test_missing_numbers_stay_empty_never_zero(self):
        """0과 '못 잰 값'은 다르다. 0으로 채우면 나중에 성적이 거짓이 된다."""
        rows = store.rows_from_result(
            {"ok": True, "rows": [{"ticker": "X", "name": "X"}]},
            market="US", list_kind="crash", trade_date="2026-08-09")
        self.assertIsNone(rows[0]["score"])
        self.assertIsNone(rows[0]["price"])
        self.assertIsNone(rows[0]["judged_from_high_pct"])

    def test_failed_result_gives_no_rows(self):
        self.assertEqual(
            store.rows_from_result({"ok": False, "error": "조회 실패"},
                                   market="US", list_kind="crash",
                                   trade_date="2026-08-09"),
            [],
        )

    def test_unknown_kind_is_refused(self):
        with self.assertRaises(ValueError):
            store.rows_from_result(_crash_result(), market="US",
                                   list_kind="아무거나", trade_date="2026-08-09")


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _save(self, kind, result, day="2026-08-09", market="US"):
        rows = store.rows_from_result(result, market=market, list_kind=kind,
                                      trade_date=day)
        return store.save_rows(rows, trade_date=day, market=market, out_dir=self.dir)

    def test_round_trip_keeps_numbers_as_numbers(self):
        self._save("crash", _crash_result())
        rows = store.load_rows("2026-08-09", "US", out_dir=self.dir)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["score"], 78.5)
        self.assertEqual(rows[0]["rank"], 1)
        self.assertEqual(rows[0]["name"], "TSMC")

    def test_two_branches_live_in_one_file_side_by_side(self):
        self._save("crash", _crash_result())
        self._save("pullback", _pullback_result())
        rows = store.load_rows("2026-08-09", "US", out_dir=self.dir)
        self.assertEqual(len(rows), 3)
        # 갈래 차례는 화면 차례(눌림목 → 상승장 → 급락 → 순위 7)를 따른다.
        self.assertEqual([row["list_kind"] for row in rows],
                         ["pullback", "crash", "crash"])

    def test_saving_the_same_branch_again_replaces_it(self):
        """장중에 눌러 본 것 위에 마감값이 덮여야 한다 — 줄이 두 배로 늘면 안 된다."""
        self._save("crash", _crash_result())
        smaller = {"ok": True, "rows": [_crash_result()["rows"][0]]}
        self._save("crash", smaller)
        rows = store.load_rows("2026-08-09", "US", out_dir=self.dir)
        self.assertEqual(len(rows), 1)

    def test_saving_one_branch_does_not_wipe_the_others(self):
        self._save("pullback", _pullback_result())
        self._save("crash", _crash_result())
        kinds = {row["list_kind"] for row in store.load_rows("2026-08-09", "US", out_dir=self.dir)}
        self.assertEqual(kinds, {"pullback", "crash"})

    def test_empty_rows_never_touch_an_existing_day(self):
        """조회에 실패한 날이 어제 자료를 빈 파일로 덮으면 안 된다."""
        self._save("crash", _crash_result())
        self.assertIsNone(
            store.save_rows([], trade_date="2026-08-09", market="US", out_dir=self.dir))
        self.assertEqual(len(store.load_rows("2026-08-09", "US", out_dir=self.dir)), 2)

    def test_markets_do_not_share_a_file(self):
        self._save("crash", _crash_result(), market="US")
        self._save("crash", _crash_result(), market="KR")
        self.assertEqual(store.available_dates("US", out_dir=self.dir), ["2026-08-09"])
        self.assertEqual(store.available_dates("KR", out_dir=self.dir), ["2026-08-09"])
        self.assertEqual(len(store.load_rows("2026-08-09", "US", out_dir=self.dir)), 2)

    def test_dates_come_back_newest_first(self):
        self._save("crash", _crash_result(), day="2026-08-07")
        self._save("crash", _crash_result(), day="2026-08-09")
        self.assertEqual(store.available_dates("US", out_dir=self.dir),
                         ["2026-08-09", "2026-08-07"])

    def test_missing_day_is_empty_not_an_error(self):
        self.assertEqual(store.load_rows("1999-01-01", "US", out_dir=self.dir), [])
        self.assertEqual(store.available_dates("US", out_dir=self.dir), [])

    def test_saved_kinds_tells_what_is_already_written(self):
        self._save("crash", _crash_result())
        self.assertEqual(store.saved_kinds("2026-08-09", "US", out_dir=self.dir), {"crash"})


class DownloadTests(unittest.TestCase):
    def test_csv_has_a_bom_so_excel_shows_hangul(self):
        rows = store.rows_from_result(_crash_result(), market="US", list_kind="crash",
                                      trade_date="2026-08-09")
        blob = store.to_csv_bytes(rows)
        self.assertTrue(blob.startswith(b"\xef\xbb\xbf"), "BOM이 없으면 엑셀에서 한글이 깨진다")
        text = blob.decode("utf-8-sig")
        self.assertIn("TSMC", text)
        # 갈래는 내려받는 파일에서는 화면에 쓰는 말로 적힌다.
        self.assertIn("급락 후 반등장 (낙폭종목)", text)

    def test_excel_is_a_real_xlsx_or_politely_absent(self):
        rows = store.rows_from_result(_crash_result(), market="US", list_kind="crash",
                                      trade_date="2026-08-09")
        blob = store.to_excel_bytes(rows)
        if blob is None:
            self.skipTest("openpyxl이 없는 판 — CSV로 내려받는다")
        self.assertTrue(blob.startswith(b"PK"), "xlsx는 zip이라 PK로 시작한다")

    def test_download_carries_the_profit_columns_when_measured(self):
        """엑셀로 받아 놓고 손익을 못 보면 받을 값이 없다(2026-08-09 상하님 지시)."""
        rows = store.rows_from_result(_crash_result(), market="US", list_kind="crash",
                                      trade_date="2026-08-09")
        # 아직 안 쟀으면 없던 칸이 붙지 않는다 — 빈 칸만 늘어나면 표가 안 읽힌다.
        self.assertEqual(store.download_fields(rows), store.FIELDS)

        rows = store.set_buy_opens(rows, {"TSM": 214.0})
        measured = store.with_profit(rows, {"TSM": 231.55})
        fields = store.download_fields(measured)
        for name in ("now_price", "profit_pct", "days_since"):
            self.assertIn(name, fields)
        text = store.to_csv_bytes(measured).decode("utf-8-sig")
        self.assertIn("profit_pct", text.splitlines()[0])
        self.assertIn("231.55", text)

    def test_summary_reads_in_screen_words(self):
        rows = store.rows_from_result(_crash_result(), market="US", list_kind="crash",
                                      trade_date="2026-08-09")
        self.assertIn("급락 후 반등장 (낙폭종목) 2", store.summarize(rows))


class ProfitTests(unittest.TestCase):
    """산 값과 지금 값을 견주는 자리. 저장된 값은 절대 안 바뀐다."""

    def test_plain_gain_and_loss(self):
        self.assertAlmostEqual(store.profit_pct(100, 110), 10.0)
        self.assertAlmostEqual(store.profit_pct(100, 90), -10.0)
        self.assertAlmostEqual(store.profit_pct(200, 200), 0.0)

    def test_unmeasurable_stays_empty_not_zero(self):
        """0%는 '본전'이라는 뜻이다. 못 잰 것을 0으로 적으면 둘이 섞인다."""
        self.assertIsNone(store.profit_pct(None, 100))
        self.assertIsNone(store.profit_pct(100, None))
        self.assertIsNone(store.profit_pct(0, 100))     # 0으로 나눌 수 없다
        self.assertIsNone(store.profit_pct(-5, 100))    # 값이 음수일 리 없다

    def test_profit_is_measured_from_the_next_day_open_not_the_close(self):
        """설명서 규칙 — 종가를 보고 **다음 거래일 시가**에 산다(2026-08-09 지시).

        신호일 종가로 재면 반나절 이른 값이라 실제로 살 수 없었던 자리가 된다.
        """
        rows = store.rows_from_result(_crash_result(), market="US", list_kind="crash",
                                      trade_date="2026-08-09")
        before = store.to_json(rows)
        filled = store.set_buy_opens(rows, {"TSM": 214.0})    # 다음날 시가
        out = store.with_profit(filled, {"TSM": 231.55})
        # 원본은 그대로여야 한다.
        self.assertEqual(before, store.to_json(rows))
        # 종가(210.5)가 아니라 시가(214.0) 기준이다.
        self.assertAlmostEqual(out[0]["profit_pct"], (231.55 / 214.0 - 1) * 100)
        self.assertNotAlmostEqual(out[0]["profit_pct"], (231.55 / 210.5 - 1) * 100)
        self.assertEqual(out[0]["now_price"], 231.55)

    def test_no_open_yet_means_no_profit_number(self):
        """시가를 아직 모르면 수익률을 내지 않는다 — 종가로 대신 재지 않는다."""
        rows = store.rows_from_result(_crash_result(), market="US", list_kind="crash",
                                      trade_date="2026-08-09")
        out = store.with_profit(rows, {"TSM": 231.55})
        self.assertIsNone(out[0]["profit_pct"])
        self.assertEqual(out[0]["now_price"], 231.55)

    def test_a_filled_open_is_never_overwritten(self):
        """과거의 시가는 고정된 사실이다. 자료원이 바뀌어도 옛 손익률이 흔들리면 안 된다."""
        rows = store.rows_from_result(_crash_result(), market="US", list_kind="crash",
                                      trade_date="2026-08-09")
        once = store.set_buy_opens(rows, {"TSM": 214.0})
        twice = store.set_buy_opens(once, {"TSM": 999.0})
        self.assertEqual(twice[0]["buy_open"], 214.0)

    def test_missing_price_leaves_the_row_blank(self):
        """상장폐지·조회 실패한 종목은 빈칸이다. 지어내지 않는다."""
        rows = store.rows_from_result(_crash_result(), market="US", list_kind="crash",
                                      trade_date="2026-08-09")
        rows = store.set_buy_opens(rows, {"TSM": 214.0, "AMD": 152.0})
        out = store.with_profit(rows, {"TSM": 231.55})
        self.assertIsNone(out[1]["profit_pct"])
        self.assertIsNone(out[1]["now_price"])


class DaysSinceTests(unittest.TestCase):
    """수익률은 **다음 날부터** 뜻이 생긴다. 당일 0%는 '본전'이 아니다."""

    def test_counts_calendar_days_from_the_buy_date(self):
        from datetime import date as _date
        self.assertEqual(store.days_since("2026-08-09", _date(2026, 8, 9)), 0)
        self.assertEqual(store.days_since("2026-08-09", _date(2026, 8, 10)), 1)
        self.assertEqual(store.days_since("2026-08-09", _date(2026, 8, 16)), 7)

    def test_bad_date_is_none_not_zero(self):
        self.assertIsNone(store.days_since("", None))
        self.assertIsNone(store.days_since("어제", None))

    def test_with_profit_marks_the_buy_day(self):
        from datetime import date as _date
        rows = store.rows_from_result(_crash_result(), market="US", list_kind="crash",
                                      trade_date="2026-08-09")
        rows = store.set_buy_opens(rows, {"TSM": 214.0})
        same = store.with_profit(rows, {"TSM": 210.5}, today=_date(2026, 8, 9))
        later = store.with_profit(rows, {"TSM": 231.55}, today=_date(2026, 8, 16))
        self.assertEqual(same[0]["days_since"], 0)
        self.assertEqual(later[0]["days_since"], 7)
        self.assertAlmostEqual(later[0]["profit_pct"], (231.55 / 214.0 - 1) * 100)


class SeparateDaysTests(unittest.TestCase):
    """날짜마다 매수금액이 따로 저장돼야 한다.

    상하님 물음 — "그날 종가가 매번 매수 시점이니, 같은 종목이 이튿날 또 나와도
    손익율만 달라지겠지." 그 말대로 되는지 굳혀 둔다.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_same_stock_on_two_days_keeps_two_buy_prices(self):
        first = _crash_result()
        second = {"ok": True, "rows": [dict(first["rows"][0])]}
        second["rows"][0]["metrics"] = dict(second["rows"][0]["metrics"])
        second["rows"][0]["metrics"]["current"] = 220.0   # 이튿날 종가

        for day, result in (("2026-08-09", first), ("2026-08-10", second)):
            rows = store.rows_from_result(result, market="US", list_kind="crash",
                                          trade_date=day)
            store.save_rows(rows, trade_date=day, market="US", out_dir=self.dir)

        day1 = store.load_rows("2026-08-09", "US", out_dir=self.dir)
        day2 = store.load_rows("2026-08-10", "US", out_dir=self.dir)
        self.assertEqual(day1[0]["price"], 210.5)
        self.assertEqual(day2[0]["price"], 220.0)

        # 같은 지금 값(231.55)이라도 **그날의 다음날 시가**가 달라 손익률이 갈린다.
        day1 = store.set_buy_opens(day1, {"TSM": 214.0})
        day2 = store.set_buy_opens(day2, {"TSM": 222.5})
        p1 = store.with_profit(day1, {"TSM": 231.55})[0]["profit_pct"]
        p2 = store.with_profit(day2, {"TSM": 231.55})[0]["profit_pct"]
        self.assertAlmostEqual(p1, (231.55 / 214.0 - 1) * 100)
        self.assertAlmostEqual(p2, (231.55 / 222.5 - 1) * 100)
        self.assertNotAlmostEqual(p1, p2)
        # 두 날이 따로 남아 있어야 나중에 골라 볼 수 있다.
        self.assertEqual(store.available_dates("US", out_dir=self.dir),
                         ["2026-08-10", "2026-08-09"])


class TradeDateTests(unittest.TestCase):
    def test_us_uses_the_new_york_date_not_the_seoul_one(self):
        """한국시각 새벽 6시에 미국장이 끝나면 서울 날짜는 이미 다음 날이다."""
        seoul_dawn = datetime(2026, 8, 8, 6, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        self.assertEqual(store.trade_date_for("US", seoul_dawn), "2026-08-07")
        self.assertEqual(store.trade_date_for("KR", seoul_dawn), "2026-08-08")


if __name__ == "__main__":
    unittest.main()

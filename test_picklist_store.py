"""날짜별 목록 창고(picklist_store)와 수집기가 지켜야 할 것들.

가장 중요한 두 가지를 시험으로 굳혀 둔다.
  * 저장은 **값을 고치지 않는다** — 화면에 뜬 숫자가 그대로 남아야 나중에 성적을
    잴 수 있다.
  * 조회에 실패한 날이 **멀쩡한 어제 자료를 지우면 안 된다.**
"""

from __future__ import annotations

import tempfile
import unittest
import pathlib
import shutil
from unittest.mock import patch
from datetime import date, datetime
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



class UsSessionGateTests(unittest.TestCase):
    """미국은 **장이 끝난 뒤에만** 화면이 목록을 남긴다 (2026-08-19 상하님 지적).

    그전에는 시간을 아예 안 봤다. 한국 오후 5시 반(뉴욕 새벽 4시 반, 장 열리기
    전)에 화면을 열었더니 파일 이름은 그날 뉴욕 날짜인데 안에 든 값은 전날
    마감가인 목록이 저장됐다.

    **서머타임은 저절로 맞아야 한다** — 시각을 UTC로 못박지 않고 뉴욕
    시간대로 재기 때문이다. 여름·겨울 둘 다 확인한다.
    """

    def _seoul(self, iso: str):
        return datetime.fromisoformat(iso).replace(tzinfo=ZoneInfo("Asia/Seoul"))

    def test_before_the_bell_is_not_saved(self):
        # 한국 오후 5시 32분 = 뉴욕 새벽 4시 32분. 장이 아직 안 열렸다.
        self.assertFalse(store.us_session_is_over(self._seoul("2026-08-19T17:32:00")))

    def test_during_the_session_is_not_saved(self):
        # 한국 밤 11시 = 뉴욕 오전 10시. 장중이라 아직 마감값이 아니다.
        self.assertFalse(store.us_session_is_over(self._seoul("2026-08-19T23:00:00")))

    def test_after_the_close_is_saved(self):
        # 한국 다음날 새벽 6시 40분 = 뉴욕 오후 5시 40분. 마감 뒤다.
        self.assertTrue(store.us_session_is_over(self._seoul("2026-08-20T06:40:00")))

    def test_holidays_are_not_saved(self):
        """휴장일에는 저장하지 않는다 (2026-08-19 상하님 지시로 넣은 공휴일표)."""
        ny = ZoneInfo("America/New_York")
        for day in ("2026-01-01", "2026-04-03", "2026-07-03", "2026-11-26",
                    "2026-12-25", "2025-06-19"):
            stamp = datetime.fromisoformat(f"{day}T17:00:00").replace(tzinfo=ny)
            self.assertFalse(store.us_session_is_over(stamp), day)

    def test_half_days_close_at_one(self):
        """반휴장일은 뉴욕 오후 1시가 마감이다 — 4시를 기다리면 그날이 빈다."""
        ny = ZoneInfo("America/New_York")
        for day in ("2026-11-27", "2026-12-24"):       # 추수감사절 다음 날 · 성탄 전날
            self.assertIn(datetime.fromisoformat(day).date(),
                          store.us_half_days(2026), day)
            before = datetime.fromisoformat(f"{day}T12:59:00").replace(tzinfo=ny)
            after = datetime.fromisoformat(f"{day}T13:01:00").replace(tzinfo=ny)
            self.assertFalse(store.us_session_is_over(before), day)
            self.assertTrue(store.us_session_is_over(after), day)

    def test_the_holiday_table_matches_the_real_calendar(self):
        """실제 뉴욕증권거래소 달력과 맞아야 한다 — 표가 아니라 규칙으로 센다."""
        self.assertEqual(
            ["2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26",
             "2025-06-19", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25"],
            sorted(d.isoformat() for d in store.us_market_holidays(2025)))
        # 2026: 독립기념일이 토요일이라 **7월 3일 금요일**에 쉰다.
        self.assertIn(date(2026, 7, 3), store.us_market_holidays(2026))
        self.assertNotIn(date(2026, 7, 4), store.us_market_holidays(2026))
        # 2027: 성탄절이 토요일이라 12월 24일에 쉬고, 그러면 반휴장은 없다.
        self.assertIn(date(2027, 12, 24), store.us_market_holidays(2027))
        self.assertNotIn(date(2027, 12, 24), store.us_half_days(2027))
        # 새해 첫날이 토요일인 해는 **12월 31일에 쉬지 않는다**(거래소 규칙).
        year = next(y for y in range(2026, 2040) if date(y, 1, 1).weekday() == 5)
        self.assertNotIn(date(year - 1, 12, 31), store.us_market_holidays(year - 1))
        self.assertNotIn(date(year, 1, 1), store.us_market_holidays(year))

    def test_the_cloud_collector_skips_holidays(self):
        """GitHub 자동 저장도 휴장일에는 안 찍는다."""
        source = pathlib.Path("picklist_collector.py").read_text(encoding="utf-8")
        self.assertIn("us_market_is_open", source,
                      "클라우드 수집기가 휴장일을 안 본다")

    def test_weekend_is_never_saved(self):
        self.assertFalse(store.us_session_is_over(self._seoul("2026-08-22T14:00:00")))
        self.assertFalse(store.us_session_is_over(self._seoul("2026-08-23T14:00:00")))

    def test_summer_and_winter_use_the_same_new_york_clock(self):
        """서머타임이 바뀌어도 **뉴욕 오후 4시**가 기준이어야 한다."""
        ny = ZoneInfo("America/New_York")
        for day in ("2026-07-15", "2026-12-15"):        # 여름 · 겨울
            before = datetime.fromisoformat(f"{day}T15:59:00").replace(tzinfo=ny)
            after = datetime.fromisoformat(f"{day}T16:01:00").replace(tzinfo=ny)
            self.assertFalse(store.us_session_is_over(before), day)
            self.assertTrue(store.us_session_is_over(after), day)

    def test_korea_waits_for_the_close_too(self):
        """한국도 서울 15시 30분이 지나야 저장한다 (2026-08-19 저녁 상하님 지시).

        미국과 같은 구멍이 한국에도 있었다 — 서울 오전에 화면을 열면 전날 종가가
        오늘 날짜로 저장됐다.
        """
        seoul = ZoneInfo("Asia/Seoul")

        def at(iso):
            return datetime.fromisoformat(iso).replace(tzinfo=seoul)

        self.assertFalse(store.kr_session_is_over(at("2026-08-19T10:00:00")))
        self.assertFalse(store.kr_session_is_over(at("2026-08-19T15:29:00")))
        self.assertTrue(store.kr_session_is_over(at("2026-08-19T15:30:00")))
        self.assertTrue(store.kr_session_is_over(at("2026-08-19T16:10:00")))
        # 주말은 장이 없다.
        self.assertFalse(store.kr_session_is_over(at("2026-08-22T16:00:00")))
        # 한 창구로 두 시장을 다 본다.
        self.assertTrue(store.session_is_over("KR", at("2026-08-19T16:10:00")))
        self.assertFalse(store.session_is_over("KR", at("2026-08-19T10:00:00")))

    def test_korea_holidays_are_asked_of_the_data_not_a_calendar(self):
        """한국 휴장일은 **코스피 일봉에 오늘 봉이 있나**로 가린다.

        설·추석이 음력이라 규칙으로 셀 수 없다. 달력을 손으로 채워 두면 해마다
        고쳐 넣어야 하고 잊으면 그해부터 조용히 틀린다.
        """
        source = pathlib.Path("jarvis4_data.py").read_text(encoding="utf-8")
        self.assertIn("def kr_market_traded_today", source)
        for where in ("picklist_ui.py", "picklist_collector.py"):
            text = pathlib.Path(where).read_text(encoding="utf-8")
            self.assertIn("kr_market_traded_today", text, f"{where}가 휴장일을 안 본다")
        # 조회가 안 될 때(None) **막지 않아야** 한다 — 그날 목록이 통째로 비면 안 된다.
        ui = pathlib.Path("picklist_ui.py").read_text(encoding="utf-8")
        block = ui.split("def _kr_market_open_today(")[1].split(chr(10) + "def ")[0]
        self.assertIn("traded is None", block, "못 읽었을 때 막아 버린다")

    def test_the_screen_autosave_checks_the_gate(self):
        """화면 자동 저장이 이 판정을 실제로 부르는지 본다."""
        source = pathlib.Path("picklist_ui.py").read_text(encoding="utf-8")
        block = source.split("def autosave(")[1].split(chr(10) + "def ")[0]
        self.assertIn("us_session_is_over", block,
                      "화면 자동 저장이 장 마감을 안 본다")


if __name__ == "__main__":
    unittest.main()


class BuyOpenBackfillTests(unittest.TestCase):
    """**매수금액은 자동으로 채워져야 한다** (2026-08-12 상하님 지적).

    "전날 종가에 저장하고 다음날 매수 하는 것으로 자동저장되게 해서 하기로 했는데
    하나도 저장이 안 되어 있고" — 확인해 보니 저장된 232줄 전부 매수금액이
    빈칸이었다. 목록은 잘 저장되고 있었는데, 신호일에는 알 수 없는 '다음 거래일
    시가'를 나중에 채워 넣는 일을 **아무도 하지 않았다.** 화면 단추로만 채울 수
    있었고 온라인에서 채운 값은 저장소에 안 올라갔다.
    """

    def setUp(self):
        self._dir = tempfile.mkdtemp()
        self.out = pathlib.Path(self._dir)

    def tearDown(self):
        shutil.rmtree(self._dir, ignore_errors=True)

    def _save(self, trade_date, codes):
        store.save_rows(
            [store.normalize_row({"ticker": code, "name": code, "price": 100.0},
                                 market="US", list_kind="breakout",
                                 trade_date=trade_date, rank=index, saved_at="x")
             for index, code in enumerate(codes, 1)],
            trade_date=trade_date, market="US", out_dir=self.out)

    def test_it_fills_yesterdays_blank_buy_price(self):
        self._save("2026-08-10", ["AAA", "BBB"])
        with patch.object(store, "fetch_buy_opens", return_value={"AAA": 11.0, "BBB": 22.0}):
            filled = store.backfill_buy_opens("US", out_dir=self.out)
        self.assertEqual({"2026-08-10": 2}, filled)
        rows = store.load_rows("2026-08-10", "US", self.out)
        self.assertEqual([11.0, 22.0], [row["buy_open"] for row in rows])

    def test_a_filled_price_is_never_overwritten(self):
        """과거의 시가는 고정된 사실이다. 자료원이 바뀌어도 옛 손익이 흔들리면 안 된다."""
        self._save("2026-08-10", ["AAA"])
        with patch.object(store, "fetch_buy_opens", return_value={"AAA": 11.0}):
            store.backfill_buy_opens("US", out_dir=self.out)
        with patch.object(store, "fetch_buy_opens", return_value={"AAA": 99.0}) as again:
            store.backfill_buy_opens("US", out_dir=self.out)
        # 이미 다 찼으면 조회조차 하지 않는다.
        again.assert_not_called()
        self.assertEqual(11.0, store.load_rows("2026-08-10", "US", self.out)[0]["buy_open"])

    def test_one_bad_day_does_not_stop_the_others(self):
        self._save("2026-08-10", ["AAA"])
        self._save("2026-08-11", ["BBB"])
        calls = []

        def _flaky(market, rows):
            calls.append(rows[0]["trade_date"])
            if rows[0]["trade_date"] == "2026-08-11":
                raise RuntimeError("조회 실패")
            return {"AAA": 11.0}

        with patch.object(store, "fetch_buy_opens", side_effect=_flaky):
            filled = store.backfill_buy_opens("US", out_dir=self.out)
        self.assertEqual({"2026-08-10": 1}, filled)
        self.assertEqual(2, len(calls), "한 날이 막히면 나머지도 멈췄다")

    def test_the_cloud_collector_calls_it(self):
        """화면 단추가 아니라 **클라우드 수집기**가 채워야 한다 — 상하님이 로그인
        하지 않아도 쌓여야 한다는 것이 이 기능의 요구다."""
        source = pathlib.Path("picklist_collector.py").read_text(encoding="utf-8")
        self.assertIn("backfill_buy_opens", source)
        # 목록 저장 **뒤**에 해야 한다 — 여기서 막혀도 오늘 목록은 파일에 남는다.
        self.assertLess(source.index("save_rows("), source.index("backfill_buy_opens"))


class HolidayRunIsNotAFailureTests(unittest.TestCase):
    """장이 안 열린 날 수집기가 **죽지 않아야** 한다 (2026-08-29 상하님 지적).

    상하님 — "저장해 둔 목록 자꾸 문제 생긴다."

    까닭 하나가 여기였다. 건너뛴 판이 돌려주던 요약에 `rows` 칸이 없어서
    `main()` 이 `summary["rows"]` 를 읽다가 **KeyError 로 죽었다.** 그래서
    토요일에 밀려 뜬 한국 몫 두 판이 통째로 빨갛게 떴다(실행 33203643713 ·
    33218787536, 2026-08-28). 자료는 멀쩡한데 작업만 실패로 보이면 **진짜
    실패한 날을 가려낼 수가 없다.**
    """

    def test_skipped_summary_has_the_same_shape_as_a_saved_one(self):
        import picklist_collector as collector

        summary = collector._skipped("KR", "2026-08-28")
        for field in ("market", "trade_date", "path", "rows", "counts",
                      "errors", "buy_opens_filled"):
            self.assertIn(field, summary, f"{field} 칸이 없다")
        self.assertEqual(0, summary["rows"])
        self.assertTrue(summary["skipped"])

    def test_a_closed_market_does_not_fail_the_job(self):
        import picklist_collector as collector

        with patch.object(collector, "collect_market",
                          return_value=collector._skipped("KR", "2026-08-28")):
            self.assertEqual(0, collector.main(["--market", "KR"]),
                             "쉬는 날인데 작업이 빨갛게 떴다")

    def test_a_real_empty_run_still_fails(self):
        """정말 한 줄도 못 찍은 날은 **그대로 실패**여야 한다 —
        조용히 빈 날이 쌓이는 것보다 빨갛게 뜨는 편이 낫다."""
        import picklist_collector as collector

        empty = {"market": "US", "trade_date": "2026-08-28", "path": "",
                 "rows": 0, "counts": {}, "errors": ["시세 실패"]}
        with patch.object(collector, "collect_market", return_value=empty):
            self.assertEqual(1, collector.main(["--market", "US"]))


class Theme15IsSavedByTheScreenTooTests(unittest.TestCase):
    """「상위 테마 5개 · 각 종목 1~3위」가 화면에서도 남아야 한다 (2026-08-29).

    상하님 — *"08-28일자에 상위 테마 5개 각 종목 1~3위 15종목 리스트가 왜 또
    빠지냐!"*

    2026-08-15에 이 갈래를 만들 때 **클라우드 수집기에만** 넣고 화면 쪽 보조
    저장에는 안 넣었다. 그래서 깃허브 예약이 제때 뜬 날에만 15줄이 들어가고,
    예약이 밀려 화면 자동 저장만 걸린 날에는 통째로 빠졌다(8/26 · 8/28).
    """

    PAGE = pathlib.Path("pages/2_자비스3.py")

    def test_the_screen_saves_theme15(self):
        source = self.PAGE.read_text(encoding="utf-8")
        self.assertIn('picklist_ui.autosave("US", "theme15"', source,
                      "화면이 이 갈래를 안 남긴다")
        # **수집기가 부르는 함수를 같은 인자로 부른다**(CLAUDE.md 10-1).
        # 여기에 고르는 계산을 따로 쓰면 저장 목록이 조용히 갈라진다.
        helper = source[source.index("def _autosave_theme15()"):]
        helper = helper[:helper.index(chr(10) + "def ", 10)]
        self.assertIn("j3data.find_theme_top_picks(", helper)
        collector = pathlib.Path("picklist_collector.py").read_text(encoding="utf-8")
        self.assertIn("find_theme_top_picks(", collector)
        # **남길 때만 만든다** — 매 판 만들면 화면이 그만큼 느려진다(0-0).
        self.assertIn('picklist_ui.needs_autosave("US", "theme15")', helper)
        self.assertLess(helper.index("needs_autosave"),
                        helper.index("find_theme_top_picks"),
                        "물어보기 전에 만들면 매 판 대장주 다섯 판을 조회한다")
        # 화면을 **다 그린 뒤**에 부른다 — 앞에 두면 보실 것이 밀린다.
        body = source[source.index("def _render_existing_theme_content()"):]
        body = body[:body.index(chr(10) + "def ", 10)]
        self.assertLess(body.index("_render_radar_tab(market)"),
                        body.index("_autosave_theme15()"))

    def test_needs_autosave_agrees_with_autosave(self):
        """물어본 답과 실제 저장이 갈라지면 안 된다."""
        import picklist_ui

        # 미국 화면에 없는 갈래는 물어볼 것도 없다.
        self.assertFalse(picklist_ui.needs_autosave("US", "pullback"))
        # 한국 화면에 없는 갈래도 마찬가지다.
        self.assertFalse(picklist_ui.needs_autosave("KR", "theme15"))
        # 장이 안 끝났으면 안 남긴다 — 토요일 뉴욕 정오.
        with patch.object(store, "session_is_over", return_value=False):
            self.assertFalse(picklist_ui.needs_autosave("US", "theme15"))
        # 장이 끝났고 그날 것이 아직 없으면 남긴다.
        with patch.object(store, "session_is_over", return_value=True), \
                patch.object(store, "saved_kinds", return_value=set()):
            self.assertTrue(picklist_ui.needs_autosave("US", "theme15"))
        # 이미 남아 있으면 다시 안 남긴다 — 장중에 눌러 본 값이 마감값을 덮으면 안 된다.
        with patch.object(store, "session_is_over", return_value=True), \
                patch.object(store, "saved_kinds", return_value={"theme15"}):
            self.assertFalse(picklist_ui.needs_autosave("US", "theme15"))

    def test_it_never_raises(self):
        """못 물어보면 False — 화면이 이것 때문에 죽으면 안 된다."""
        import picklist_ui

        with patch.object(store, "session_is_over", side_effect=RuntimeError("고장")):
            self.assertFalse(picklist_ui.needs_autosave("US", "theme15"))


class DateBoxKeepsTheKeyboardDownTests(unittest.TestCase):
    """날짜 칸을 눌러도 폰 자판이 안 떠야 한다 — **판이 바뀌어도** (2026-08-29).

    상하님 — "날짜별로 저장해 둔 목록 보기에 날짜 클릭하면 또 자판 뜬다.
    이거 몇 번째 이야기하냐."

    세 번째였다. 표를 붙이는 코드는 맞았는데 **붙인 것이 지워진 뒤 다시 안 붙었다.**
    감시자를 작은 창(iframe) 안에서 만들었는데 스트림릿이 다시 그리며 그 창을
    없애 버리고, "한 번만 붙인다"는 표식은 바깥 화면에 남아서 다음 창이 곧바로
    돌아가 버렸다.

    실물 브라우저로 전·후를 나란히 쟀다(chromium, 창을 실제로 만들고 지움) —
        고치기 전  1판 막힘 · 2판 **자판 뜸** · 3판 **자판 뜸**
        고친 뒤    1판 막힘 · 2판 막힘 · 3판 막힘
    """

    def _script(self):
        import picklist_ui
        return picklist_ui._KEYBOARD_SCRIPT

    def test_every_run_applies_it_before_any_early_return(self):
        """판마다 **바로 한 번** 붙인다 — 표식을 보고 먼저 돌아가면 안 된다."""
        js = self._script()
        self.assertLess(js.index("hush();"), js.index("__jarvisNoKeyboard"),
                        "표식을 보고 돌아간 뒤에 붙이면 첫 판에만 막힌다")

    def test_the_watcher_is_planted_in_the_outer_page(self):
        """감시자는 **바깥 화면 안에서** 만든다 — 작은 창은 다시 그릴 때 없어진다."""
        js = self._script()
        self.assertIn("createElement('script')", js, "감시자를 창 안에서 만든다")
        self.assertIn("doc.head.appendChild", js)
        self.assertIn("MutationObserver", js)
        # 감시자를 만드는 코드가 **심는 글 안**에 있어야 한다 — 창 안에 있으면 죽는다.
        planted = js[js.index("tag.textContent"):js.index("doc.head.appendChild")]
        self.assertIn("MutationObserver", planted, "감시자가 아직 창 안에 있다")

    def test_the_selector_carries_no_double_quotes(self):
        """셀렉터에 큰따옴표가 섞이면 심는 글줄이 그 자리에서 끊긴다."""
        import picklist_ui
        self.assertNotIn('"', picklist_ui._DATE_INPUT_SELECTOR)
        self.assertIn("st-key-picklist_date_", picklist_ui._DATE_INPUT_SELECTOR)

    def test_each_run_sends_a_different_body(self):
        """보내는 글이 그대로면 화면이 창을 다시 안 연다 — scroll_to 와 같은 함정."""
        import picklist_ui

        class _St:
            def __init__(self):
                self.session_state = {}

        sent = []
        st = _St()
        with patch.object(picklist_ui, "_KEYBOARD_SCRIPT", "<script></script>"):
            import streamlit.components.v1 as components
            real = components.html
            components.html = lambda body, height=0: sent.append(body)
            try:
                picklist_ui._keep_keyboard_down(st, "US")
                picklist_ui._keep_keyboard_down(st, "US")
            finally:
                components.html = real
        self.assertEqual(2, len(sent))
        self.assertNotEqual(sent[0], sent[1], "두 판에 같은 글을 보내면 창이 안 열린다")

    def test_it_never_raises(self):
        """못 붙여도 화면은 그대로 돌아야 한다."""
        import picklist_ui

        class _St:
            def __init__(self):
                self.session_state = {}

        import streamlit.components.v1 as components
        real = components.html

        def _boom(body, height=0):
            raise RuntimeError("컴포넌트를 못 그린다")

        components.html = _boom
        try:
            picklist_ui._keep_keyboard_down(_St(), "US")   # 터지면 안 된다
        finally:
            components.html = real


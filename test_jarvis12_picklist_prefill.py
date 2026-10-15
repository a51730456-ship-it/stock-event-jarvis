"""자비스12 날짜별 목록 — 자비스12 전용 사본(jarvis12_picklist_ui) · 급락 칸을 기준일 10종목으로 · 장 닫힘 종가 바로.

2026-10-14 상하님 — "날짜별로 저장해 둔 목록 보기 왜 로딩이 오래 걸리냐?"
2026-10-15 상하님 — 9월 1일 목록의 급락 칸이 성적표 10종목과 다르다 → 「10종목으로 바꿔 보여 주기」.
"""
from __future__ import annotations

import contextlib
import sys
import types
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import pandas as pd

import jarvis12_picklist_ui as j12ui
import picklist_store as real_store

ROOT = Path(__file__).resolve().parent
J12 = (ROOT / "pages" / "11_자비스12.py").read_text(encoding="utf-8")
J3 = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
QUICK = J12[J12.index("def _picklist_quick_closes("):J12.index("def _picklist_toggle(")]
DAY_ROWS = J12[J12.index("def _crash12_day_rows("):J12.index("def _scorecard_span_start(")]


def _frame(last_day: str, close: float, periods: int = 3) -> pd.DataFrame:
    days = pd.bdate_range(end=last_day, periods=periods)
    closes = [close - periods + 1 + i for i in range(periods)]
    return pd.DataFrame({"Open": [c - 0.5 for c in closes], "High": closes, "Low": closes, "Close": closes,
                         "Volume": 1}, index=days)


class QuickClosesTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.frames = {"AAA": _frame("2026-10-13", 101.5), "BBB": _frame("2026-10-13", 52.25)}
        self.saved = sys.modules.get("us_market_calendar")
        sys.modules["us_market_calendar"] = types.SimpleNamespace(previous_session_date=lambda: date(2026, 10, 13))

    def tearDown(self):
        if self.saved is None:
            sys.modules.pop("us_market_calendar", None)
        else:
            sys.modules["us_market_calendar"] = self.saved

    def _run(self, codes, *, open_now=False):
        def download(codes, **kwargs):
            self.calls.append((codes, kwargs))
            return self.frames, {}

        ns = {"_regular_open": lambda: open_now, "pd": pd,
              "j3data": types.SimpleNamespace(_download_cached=download, US_BATCH_TTL=1800.0)}
        exec(QUICK, ns)
        return ns["_picklist_quick_closes"](codes)

    def test_closed_market_gives_the_last_close_from_the_shared_daily_batch(self):
        self.assertEqual({"AAA": 101.5, "BBB": 52.25}, self._run(["AAA", "BBB", "AAA"]))
        self.assertEqual(("AAA", "BBB"), self.calls[0][0])
        self.assertEqual({"period": "2y", "interval": "1d", "ttl_seconds": 1800.0}, self.calls[0][1])

    def test_lagging_or_missing_ticker_and_regular_session_fall_back(self):
        self.assertIsNone(self._run(["AAA", "CCC"]))                      # 못 받은 종목
        self.frames["BBB"] = _frame("2026-10-10", 52.0)                   # 야후가 마지막 장을 아직 안 올림
        self.assertIsNone(self._run(["AAA", "BBB"]))
        calls = len(self.calls)
        self.assertIsNone(self._run(["AAA"], open_now=True))              # 정규장 중에는 예전처럼
        self.assertEqual(calls, len(self.calls))


class DayRowsTests(unittest.TestCase):
    """그날 들고 있던 기준일 10종목 — 성적표와 같은 셈(그날 목록 → 다음 거래일 시가 · 저장된 매수금액 먼저)."""

    def _ns(self, cohort, frames):
        ns = {"date": date, "pd": pd,
              "_crash12_cohort_rows": lambda: [dict(row) for row in cohort],
              "j3data": types.SimpleNamespace(_download_cached=lambda codes, **kw: (frames, {}), US_BATCH_TTL=1800.0,
                                              _series_metrics=lambda frame: {"ok": True, "from_high_pct": -1.0}),
              "jarvis12_crash": types.SimpleNamespace(
                  _dates=lambda index: [stamp.date() for stamp in pd.DatetimeIndex(index)])}
        exec(DAY_ROWS, ns)
        return ns

    def setUp(self):
        days = pd.bdate_range("2026-08-03", "2026-09-04")
        self.frame = pd.DataFrame({"Open": [100.0 + i for i in range(len(days))],
                                   "Close": [100.5 + i for i in range(len(days))]}, index=days)
        self.days = list(days.date)
        base = {"list_kind": "crash", "score": 70.0, "themes": "반도체", "judged_from_high_pct": -40.0,
                "bucket_label": "고점 대비 -30~-50%", "j12_fixed": True}
        self.cohort = [{**base, "trade_date": "2026-07-29", "code": "NEW1", "rank": 1, "shown_until": ""},
                       {**base, "trade_date": "2026-07-29", "code": "NEW2", "rank": 2, "shown_until": ""},
                       {**base, "trade_date": "2026-03-30", "code": "MAR1", "rank": 1, "shown_until": "2026-07-20"}]
        self.ns = self._ns(self.cohort, {"NEW1": self.frame, "NEW2": self.frame})

    def test_saved_crash_rows_are_replaced_by_the_held_ten_and_other_parts_stay(self):
        saved = [{"list_kind": "crash", "code": "OLD1", "buy_open": 10.0},
                 {"list_kind": "theme15", "code": "NEW2", "buy_open": 77.0}]       # 같은 날 다른 파트에 같은 종목
        shown = self.ns["_crash12_view_rows"]("2026-09-01", saved)
        self.assertEqual(["theme15", "crash", "crash"], [row["list_kind"] for row in shown])
        crash = [row for row in shown if row["list_kind"] == "crash"]
        self.assertEqual(["NEW1", "NEW2"], [row["code"] for row in crash])       # 다음 급락 뒤의 3월 줄은 없다
        nxt = self.days.index(date(2026, 9, 2))
        self.assertEqual(100.0 + nxt, crash[0]["buy_open"])                      # 9/1 목록 → 9/2 시가
        self.assertEqual(77.0, crash[1]["buy_open"])                             # 저장된 매수금액이 먼저
        self.assertEqual(100.5 + self.days.index(date(2026, 9, 1)), crash[0]["price"])
        self.assertEqual(("2026-09-01", 70.0, "반도체", -40.0, "2026-07-29"),
                         (crash[0]["trade_date"], crash[0]["score"], crash[0]["themes"],
                          crash[0]["judged_from_high_pct"], crash[0]["reference_date"]))

    def test_saturday_list_buys_at_the_first_session_after(self):
        crash = self.ns["_crash12_day_rows"]("2026-08-08", [])
        self.assertEqual(100.5 + self.days.index(date(2026, 8, 7)), crash[0]["price"])    # 금요일 종가
        self.assertEqual(100.0 + self.days.index(date(2026, 8, 10)), crash[0]["buy_open"])  # 월요일 시가

    def test_latest_list_has_no_buy_yet_and_failures_keep_the_saved_rows(self):
        self.assertIsNone(self.ns["_crash12_day_rows"]("2026-09-04", [])[0]["buy_open"])   # 다음 장이 아직 없다
        self.assertEqual([], self.ns["_crash12_day_rows"]("2026-07-25", []))                # 그날 보여 주던 급락 없음
        saved = [{"list_kind": "crash", "code": "OLD1"}]
        self.assertEqual(saved, self._ns([], {})["_crash12_view_rows"]("2026-09-01", saved))  # 못 재면 그대로
        note = self.ns["_crash12_list_note"]("crash", self.ns["_crash12_day_rows"]("2026-09-01", []))
        self.assertIn("7/29 급락 기준일에 점수 높은 차례로 정한 10종목", note)
        self.assertIsNone(self.ns["_crash12_list_note"]("crash", saved))


class Top7CrashTests(unittest.TestCase):
    """순위 9 의 급락 3개 = 그날 10종목을 급락 배점 차례로 세운 위 3개 (2026-10-15 상하님 — "너가 자동으로 배점 높은 것 순으로"
    · "배점은 급락 후 반등 종목 이야기다")."""

    def setUp(self):
        ten = [{"code": f"C{i}", "name": f"C{i}", "buy_open": 10.0 + i, "score_order": order, "j12_fixed": True,
                "list_kind": "crash", "trade_date": "DAY"}
               for i, order in enumerate([5, 0, 9, 1, 7, 2, 8, 3, 6, 4])]
        self.calls = []

        def day_rows(day, saved, light=False):
            self.calls.append((day, light))
            return [dict(row, trade_date=day) for row in ten]

        self.ns = {"j3data": types.SimpleNamespace(TOP_PICK_QUOTA=(("테마 대장주", 3), ("상승장", 3), ("급락 후 반등장", 3))),
                   "_crash12_day_rows": day_rows, "date": date}
        source = DAY_ROWS[DAY_ROWS.index("# 순위 9 의 급락 몇 개"):DAY_ROWS.index("def _crash12_view_rows(")]
        exec(source, self.ns)

    def test_top_three_by_crash_score_order(self):
        self.assertEqual(["C1", "C3", "C5"], [row["code"] for row in self.ns["_crash12_top3"](self.ns["_crash12_day_rows"]("D", []))])

    def test_saved_rank9_crash_rows_are_swapped_only_where_parts_are_known(self):
        rows = [
            {"trade_date": "2026-09-01", "list_kind": "top7", "origin": "테마 대장주", "code": "LEAD"},
            {"trade_date": "2026-09-01", "list_kind": "top7", "origin": "급락 후 반등장", "code": "CRSP"},
            {"trade_date": "2026-09-01", "list_kind": "theme15", "origin": "반도체", "code": "THM"},
            {"trade_date": "2026-08-12", "list_kind": "top7", "origin": "", "code": "OLD"},     # 파트 적기 전 — 그대로
        ]
        out = self.ns["_top7_crash12_swap"](rows, light=True)
        top7 = [(row["trade_date"], row["origin"], row["code"], row.get("rank")) for row in out if row["list_kind"] == "top7"]
        self.assertIn(("2026-09-01", "테마 대장주", "LEAD", None), top7)
        self.assertNotIn("CRSP", [row["code"] for row in out])
        self.assertEqual([("2026-09-01", "급락 후 반등장", "C1", 1), ("2026-09-01", "급락 후 반등장", "C3", 2),
                          ("2026-09-01", "급락 후 반등장", "C5", 3)], [t for t in top7 if t[1] == "급락 후 반등장"])
        self.assertIn(("2026-08-12", "", "OLD", None), top7)
        self.assertEqual([("2026-09-01", True)], self.calls)                      # 성적표용 가벼운 판으로 그날만
        self.assertIn("THM", [row["code"] for row in out])

    def test_scorecard_three_places_and_today_use_it(self):
        self.assertEqual(3, J12.count("    rows = _top7_crash12_swap(rows, light=True)\n"))
        view = J12[J12.index("def _crash12_view_rows("):J12.index("def _crash12_list_note(")]
        self.assertIn("_crash12_top3(fixed)", view)
        note = J12[J12.index("def _crash12_list_note("):J12.index("def _scorecard_span_start(")]
        self.assertIn("급락 배점 높은 차례로 위 3개", note)


class _Box:
    def __init__(self, st):
        self.st = st

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def download_button(self, label, data=None, **kwargs):
        self.st.downloads.append(label)

    def button(self, *args, **kwargs):
        return False

    def columns(self, count):
        return [_Box(self.st) for _ in range(count)]


class _FakeSt(_Box):
    def __init__(self, state=None):
        super().__init__(self)
        self.session_state = dict(state or {})
        self.text = []
        self.downloads = []

    def markdown(self, body, **kwargs):
        self.text.append(body)

    def selectbox(self, label, options, index=0, key=None):
        return self.session_state.setdefault(key, options[index])

    @contextlib.contextmanager
    def spinner(self, text):
        yield

    def container(self, **kwargs):
        return _Box(self)

    def caption(self, text):
        self.text.append(text)

    info = warning = caption


class RenderTests(unittest.TestCase):
    """베낀 render — 파일에 적는 것은 저장된 줄 · 화면·그날 엑셀은 보여 줄 줄."""

    def setUp(self):
        self.saved_rows = [
            {"trade_date": "2026-09-01", "market": "US", "list_kind": "crash", "code": "OLD1", "name": "OLD1", "buy_open": None},
            {"trade_date": "2026-09-01", "market": "US", "list_kind": "theme15", "code": "THM1", "name": "THM1", "buy_open": None},
        ]
        self.written, self.fetched, self.excel = [], [], []
        store = types.SimpleNamespace(
            available_dates=lambda market: ["2026-09-01"],
            load_rows=lambda day, market: [dict(row) for row in self.saved_rows],
            save_rows=lambda rows, trade_date, market: self.written.append([dict(row) for row in rows]),
            to_excel_bytes=lambda rows: self.excel.append([row["code"] for row in rows]) or b"x",
            to_csv_bytes=lambda rows: b"x",
            _num=real_store._num, set_buy_opens=real_store.set_buy_opens, with_profit=real_store.with_profit,
            KIND_ORDER=real_store.KIND_ORDER, should_show=real_store.should_show, kind_label=real_store.kind_label)
        self.patches = [mock.patch.object(j12ui, "store", store),
                        mock.patch.object(j12ui, "_keep_keyboard_down", lambda st, market: None),
                        mock.patch.object(j12ui, "fetch_buy_opens", lambda market, rows: {"OLD1": 5.0, "THM1": 6.0}),
                        mock.patch.object(j12ui, "fetch_prices",
                                          lambda market, codes: self.fetched.append(list(codes)) or {"NEW1": 9.0})]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()

    def _view(self, day, rows):
        return [row for row in rows if row["list_kind"] != "crash"] + [
            {"trade_date": day, "list_kind": "crash", "code": "NEW1", "name": "NEW1", "buy_open": 8.0, "j12_fixed": True}]

    def _render(self, st, **kwargs):
        j12ui.render(st, "US", toggle=lambda *a, **k: True, rows_view=self._view,
                     kind_note=lambda kind, part: "기준일 10종목" if kind == "crash" else None, **kwargs)

    def test_file_gets_only_the_saved_rows_and_the_screen_shows_the_ten(self):
        st = _FakeSt()
        self._render(st, quick_prices=lambda codes: {code: 1.0 for code in codes})
        # 매수금액을 채워 파일에 적을 때 — 저장된 줄(OLD1)만, 바꿔 보인 줄(NEW1)은 절대 안 적힌다
        self.assertEqual([["OLD1", "THM1"]], [[row["code"] for row in rows] for rows in self.written])
        self.assertEqual([5.0, 6.0], [row["buy_open"] for row in self.written[0]])
        page = "".join(st.text)
        self.assertIn("NEW1", page)
        self.assertNotIn("OLD1", page)
        self.assertIn("<div class='pl-note'>기준일 10종목</div>", page)
        self.assertEqual([["THM1", "NEW1"]], self.excel)                         # 그날 엑셀 = 화면 그대로
        # 장 닫힘 종가를 받았으니 하나씩 받으러 가지 않았다 · 자비스12 전용 칸
        self.assertEqual([], self.fetched)
        self.assertEqual({"THM1": 1.0, "NEW1": 1.0}, st.session_state["j12_picklist_prices_US_2026-09-01"])
        self.assertNotIn("picklist_prices_US_2026-09-01", st.session_state)      # 자비스3 칸은 안 건드린다

    def test_without_quick_prices_it_fetches_the_codes_on_screen(self):
        st = _FakeSt()
        self._render(st, quick_prices=lambda codes: None)
        self.assertEqual([["THM1", "NEW1"]], self.fetched)

    def test_jarvis3_values_in_the_same_session_are_not_reused(self):
        st = _FakeSt({"picklist_prices_US_2026-09-01": {"OLD1": 1.0, "THM1": 1.0}})
        self._render(st)
        self.assertEqual([["THM1", "NEW1"]], self.fetched)

    def test_a_broken_view_keeps_the_saved_rows(self):
        st = _FakeSt()
        j12ui.render(st, "US", toggle=lambda *a, **k: True, rows_view=lambda day, rows: 1 / 0)
        self.assertIn("OLD1", "".join(st.text))


class WiringTests(unittest.TestCase):
    def test_jarvis12_uses_the_copy_and_jarvis3_keeps_picklist_ui(self):
        section = J12[J12.index("def _render_picklist_section("):]
        section = section[:section.index("_render_scorecard_section()")]
        self.assertIn("jarvis12_picklist_ui.render(", section)
        self.assertIn("rows_view=_crash12_view_rows, quick_prices=_picklist_quick_closes, kind_note=_crash12_list_note,",
                      section)
        self.assertIn("_REQUIRED_J12_PICKLIST_REVISION = 2026101510", J12)
        self.assertEqual(2026101510, j12ui.MODULE_REVISION)
        self.assertNotIn("jarvis12_picklist_ui", J3)
        self.assertIn("picklist_ui.render(", J3)
        # 베낀 render 의 파일 적기는 원본과 같은 두 곳뿐이고 언제나 저장된 줄(rows)이다
        body = Path(j12ui.__file__).read_text(encoding="utf-8")
        self.assertEqual(2, body.count("store.save_rows(rows, trade_date=picked, market=market)"))
        self.assertNotIn("save_rows(shown", body)


class ScorecardCacheTests(unittest.TestCase):
    def test_scorecard_counter_keeps_its_ten_minute_store(self):
        """급락 함수를 끼워 넣다 성적표 세기의 10분 보관 줄이 밀려났던 것(2026-10-14 바로잡음)."""
        for name in ("_scorecard_counts_cached", "_crash12_cohort_rows"):
            head = J12[:J12.index(f"def {name}(")]
            self.assertTrue(head.rstrip().endswith("@st.cache_data(ttl=600, show_spinner=False)"), name)


if __name__ == "__main__":
    unittest.main()

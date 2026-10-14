"""자비스12 날짜별 목록 — 장이 닫혀 있으면 마지막 장 종가를 미리 넣는다 (2026-10-14 상하님 — "날짜별로 저장해 둔
목록 보기 왜 로딩이 오래 걸리냐?")."""
from __future__ import annotations

import sys
import types
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parent
J12 = (ROOT / "pages" / "11_자비스12.py").read_text(encoding="utf-8")
PICKLIST_UI = (ROOT / "picklist_ui.py").read_text(encoding="utf-8")
SOURCE = J12[J12.index("def _picklist_prefill_closes("):J12.index("def _picklist_toggle(")]


def _frame(last_day: str, close: float) -> pd.DataFrame:
    days = pd.bdate_range(end=last_day, periods=3)
    return pd.DataFrame({"Close": [close - 2, close - 1, close]}, index=days)


class PrefillTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.frames = {"AAA": _frame("2026-10-13", 101.5), "BBB": _frame("2026-10-13", 52.25)}
        self.store = types.SimpleNamespace(
            available_dates=lambda market: ["2026-10-13", "2026-09-01"],
            load_rows=lambda day, market: [{"code": "AAA"}, {"code": "BBB"}, {"code": "AAA"}])
        self.calendar = types.SimpleNamespace(previous_session_date=lambda: date(2026, 10, 13))
        self.saved = {name: sys.modules.get(name) for name in ("picklist_store", "us_market_calendar")}
        sys.modules["picklist_store"] = self.store
        sys.modules["us_market_calendar"] = self.calendar

    def tearDown(self):
        for name, module in self.saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def _run(self, *, open_now=False, state=None):
        def download(codes, **kwargs):
            self.calls.append((codes, kwargs))
            return self.frames, {}

        st = types.SimpleNamespace(session_state=dict(state or {}))
        ns = {"st": st, "_regular_open": lambda: open_now, "_PICKLIST_DATE_KEY": "picklist_date_US",
              "j3data": types.SimpleNamespace(_download_cached=download, US_BATCH_TTL=1800.0),
              "pd": pd, "datetime": datetime, "_PAGE_SEOUL": ZoneInfo("Asia/Seoul")}
        exec(SOURCE, ns)
        ns["_picklist_prefill_closes"]()
        return st.session_state

    def test_closed_market_fills_the_same_slot_picklist_ui_reads(self):
        state = self._run(state={"picklist_date_US": "2026-09-01"})
        self.assertEqual({"AAA": 101.5, "BBB": 52.25}, state["picklist_prices_US_2026-09-01"])
        self.assertRegex(state["picklist_prices_US_2026-09-01_at"], r"^\d\d:\d\d$")
        self.assertEqual(("AAA", "BBB"), self.calls[0][0])
        self.assertEqual({"period": "2y", "interval": "1d", "ttl_seconds": 1800.0}, self.calls[0][1])
        # picklist_ui 는 이 칸이 차 있으면 받으러 가지 않는다(같은 이름)
        self.assertIn('cache_key = f"picklist_prices_{market}_{picked}"', PICKLIST_UI)
        self.assertIn("if cache_key not in st.session_state:", PICKLIST_UI)

    def test_no_date_picked_yet_uses_the_newest(self):
        self.assertIn("picklist_prices_US_2026-10-13", self._run())

    def test_lagging_daily_bar_leaves_it_to_the_old_way(self):
        self.frames["BBB"] = _frame("2026-10-10", 52.0)       # 야후가 마지막 장을 아직 안 올림
        state = self._run(state={"picklist_date_US": "2026-09-01"})
        self.assertNotIn("picklist_prices_US_2026-09-01", state)

    def test_missing_ticker_leaves_it_to_the_old_way(self):
        del self.frames["BBB"]
        self.assertNotIn("picklist_prices_US_2026-09-01", self._run(state={"picklist_date_US": "2026-09-01"}))

    def test_regular_session_and_already_fetched_are_untouched(self):
        self.assertNotIn("picklist_prices_US_2026-09-01", self._run(open_now=True, state={"picklist_date_US": "2026-09-01"}))
        kept = {"picklist_date_US": "2026-09-01", "picklist_prices_US_2026-09-01": {"AAA": 1.0}}
        self.assertEqual({"AAA": 1.0}, self._run(state=kept)["picklist_prices_US_2026-09-01"])
        self.assertEqual([], self.calls)

    def test_called_from_the_toggle_while_open(self):
        toggle = J12[J12.index("def _picklist_toggle("):J12.index("def _picklist_no_scorecard(")]
        self.assertIn("        _picklist_prefill_closes()\n    return is_open", toggle)


class ScorecardCacheTests(unittest.TestCase):
    def test_scorecard_counter_keeps_its_ten_minute_store(self):
        """급락 함수를 끼워 넣다 성적표 세기의 10분 보관 줄이 밀려났던 것(2026-10-14 바로잡음)."""
        for name in ("_scorecard_counts_cached", "_crash12_cohort_rows"):
            head = J12[:J12.index(f"def {name}(")]
            self.assertTrue(head.rstrip().endswith("@st.cache_data(ttl=600, show_spinner=False)"), name)


if __name__ == "__main__":
    unittest.main()

"""파트별 성적표 「나스닥 종합과 견줘 보기」 (2026-10-07 상하님 지시) — 계산·그림·화면 자리."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import pandas as pd

import scorecard_compare as vx

ROOT = Path(__file__).resolve().parent
PAGE = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")


def _frame(rows: dict, columns=("Open", "Close")) -> pd.DataFrame:
    index = pd.to_datetime(list(rows))
    data = {name: [values[place] for values in rows.values()] for place, name in enumerate(columns)}
    return pd.DataFrame(data, index=index)


# 2026-09-14(월) ~ 09-18(금) 다섯 장. 나스닥은 날마다 시가 1000 → 종가가 1%씩 오른다.
IXIC = _frame({
    "2026-09-11": (990.0, 1000.0),
    "2026-09-14": (1000.0, 1010.0),
    "2026-09-15": (1010.0, 1020.0),
    "2026-09-16": (1020.0, 1030.0),
    "2026-09-17": (1030.0, 1040.0),
    "2026-09-18": (1040.0, 1050.0),
})
FRAMES = {
    "AAA": _frame({"2026-09-11": (100.0,), "2026-09-14": (110.0,), "2026-09-15": (120.0,),
                   "2026-09-16": (100.0,), "2026-09-17": (130.0,), "2026-09-18": (140.0,)}, ("Close",)),
    "BBB": _frame({"2026-09-11": (50.0,), "2026-09-14": (50.0,), "2026-09-15": (55.0,),
                   "2026-09-16": (60.0,), "2026-09-17": (60.0,), "2026-09-18": (45.0,)}, ("Close",)),
}


def _row(day, kind, code, buy, name=None):
    return {"trade_date": day, "list_kind": kind, "code": code, "buy_open": buy, "name": name or code}


class ComputeTests(unittest.TestCase):
    def test_same_money_each_buy_day_against_nasdaq_bought_the_same_days(self):
        rows = [
            _row("2026-09-11", "theme15", "AAA", 100.0),   # 9/14 시가 100 에 산다
            _row("2026-09-11", "theme15", "BBB", 50.0),
            _row("2026-09-15", "theme15", "AAA", 100.0),   # 9/16 시가 100 에 산다
        ]
        data = vx.compute(rows, FRAMES, IXIC)
        self.assertEqual(data["days"][0], "2026-09-14")
        self.assertEqual(data["last"], "2026-09-18")
        cum = data["parts"]["theme15"]["cum"]
        # 9/14 — 첫 묶음만: (110/100 + 50/50)/2 = 1.05 → +5%
        self.assertAlmostEqual(cum[0], 5.0)
        # 9/18 — 첫 묶음 (140/100 + 45/50)/2 = 1.15, 둘째 묶음 140/100 = 1.4 → 평균 1.275 → +27.5%
        self.assertAlmostEqual(cum[-1], 27.5)
        # 나스닥도 9/14·9/16 시가에 같은 돈 — 9/18 종가 1050: (1050/1000 + 1050/1020)/2
        expected = ((1050 / 1000 + 1050 / 1020) / 2 - 1) * 100
        self.assertAlmostEqual(data["nasdaq"]["theme"][-1], round(expected, 2))
        bars = data["parts"]["theme15"]["cohorts"]
        self.assertEqual([b[0] for b in bars], ["2026-09-14", "2026-09-16"])
        self.assertAlmostEqual(bars[0][1], 15.0)
        self.assertAlmostEqual(bars[1][1], 40.0)
        # 쌓인 수익의 끝값 = 산 날마다 막대의 평균(같은 돈이므로)
        self.assertAlmostEqual(cum[-1], sum(b[1] for b in bars) / len(bars))

    def test_stocks_are_grouped_by_code(self):
        rows = [_row("2026-09-11", "crash", "AAA", 100.0, "에이"),
                _row("2026-09-15", "crash", "AAA", 100.0, "에이"),
                _row("2026-09-11", "crash", "BBB", 50.0, "비")]
        data = vx.compute(rows, FRAMES, IXIC)
        stocks = data["parts"]["crash"]["stocks"]
        self.assertEqual([s[0] for s in stocks], ["AAA", "BBB"])      # 잘 된 것부터
        self.assertEqual(stocks[0][2], 2)                             # 두 번 샀다
        self.assertAlmostEqual(stocks[0][3], 40.0)
        self.assertAlmostEqual(stocks[1][3], -10.0)
        self.assertEqual(data["parts"]["crash"]["rows"], 3)

    def test_unmeasurable_rows_are_skipped_not_zero_filled(self):
        rows = [
            _row("2026-09-11", "breakout", "AAA", None),     # 매수금액 없음
            _row("2026-09-11", "breakout", "ZZZ", 10.0),     # 주가 없음
            _row("2026-09-18", "breakout", "AAA", 100.0),    # 아직 안 산 줄(다음 장이 없다)
            _row("2026-09-11", "top7", "AAA", 100.0),        # 견주는 세 파트가 아니다
        ]
        data = vx.compute(rows, FRAMES, IXIC)
        self.assertEqual(data["parts"], {})
        self.assertEqual(vx.compute([], FRAMES, IXIC)["days"], [])

    def test_range_stops_at_the_end_day(self):
        rows = [_row("2026-09-11", "theme15", "AAA", 100.0)]
        data = vx.compute(rows, FRAMES, IXIC, last_day=pd.Timestamp("2026-09-16").date())
        self.assertEqual(data["last"], "2026-09-16")
        self.assertAlmostEqual(data["parts"]["theme15"]["cohorts"][0][1], 0.0)   # 100/100

    def test_tab_nasdaq_buys_on_union_of_the_tabs_parts(self):
        rows = [_row("2026-09-11", "breakout", "AAA", 100.0),
                _row("2026-09-15", "crash", "BBB", 55.0)]
        data = vx.compute(rows, FRAMES, IXIC)
        self.assertNotIn("theme", data["nasdaq"])
        expected = ((1050 / 1000 + 1050 / 1020) / 2 - 1) * 100
        self.assertAlmostEqual(data["nasdaq"]["swing"][-1], round(expected, 2))
        self.assertAlmostEqual(data["nasdaq"]["all"][-1], round(expected, 2))


class BucketTests(unittest.TestCase):
    def test_week_and_month_labels(self):
        self.assertEqual(vx.bucket("2026-09-17", "w")[1], "9/14 주")
        self.assertEqual(vx.bucket("2026-09-17", "m")[1], "9월")
        self.assertEqual(vx.bucket("2026-09-17", "m", True)[1], "26.09")
        self.assertEqual(vx.bucket("2026-09-17", "d")[1], "9/17")

    def test_line_takes_last_point_and_bars_take_average(self):
        days = ["2026-09-14", "2026-09-15", "2026-09-21"]
        self.assertEqual(vx.line_points(days, [1.0, 2.0, 3.0], "w"), [("9/14 주", 2.0), ("9/21 주", 3.0)])
        groups = vx.bar_groups([["2026-09-14", 10.0, 1.0, 1], ["2026-09-16", 20.0, 3.0, 1]], "w")
        label, gain, nq, count = groups["2026-09-14"]
        self.assertEqual((label, gain, nq, count), ("9/14 주", 15.0, 2.0, 2))


class DrawTests(unittest.TestCase):
    def setUp(self):
        self.data = vx.compute([_row("2026-09-11", "theme15", "AAA", 100.0),
                                _row("2026-09-11", "crash", "BBB", 50.0),
                                _row("2026-09-15", "breakout", "AAA", 100.0)], FRAMES, IXIC)

    def test_nasdaq_is_a_thick_translucent_band(self):
        chart = vx.line_chart_html(self.data, "all", "d")
        self.assertIn(f"stroke='{vx.NASDAQ_COLOR}' stroke-width='{vx.NASDAQ_WIDTH}'", chart)
        self.assertEqual(vx.NASDAQ_WIDTH, 10)
        self.assertIn("vector-effect='non-scaling-stroke'", chart)
        for kind in vx.PARTS:
            self.assertIn(vx.PART_COLORS[kind], chart)

    def test_tabs_show_only_their_parts(self):
        theme = vx.line_chart_html(self.data, "theme", "d")
        self.assertIn(vx.PART_COLORS["theme15"], theme)
        self.assertNotIn(vx.PART_COLORS["breakout"], theme)
        swing = vx.cards_html(self.data, "swing")
        self.assertIn("상승장", swing)
        self.assertNotIn("상위 테마", swing)

    def test_bars_and_cards_and_stock_list(self):
        chart, note = vx.bar_chart_html(self.data, "all", "w")
        self.assertIn("<rect", chart)
        self.assertEqual(note, "")
        cards = vx.cards_html(self.data, "all")
        self.assertIn("같은 날 나스닥 종합", cards)
        self.assertIn("나스닥보다 나았습니다", cards)
        stocks = vx.stocks_html(self.data, "all", names={"AAA": "에이"}, first="2026-09-14", last="2026-09-18")
        self.assertIn("이 기간에 산 종목", stocks)
        self.assertIn("에이", stocks)

    def test_daily_bars_are_capped_on_long_spans(self):
        cohorts = [[f"2026-{month:02d}-{day:02d}", 1.0, 0.5, 1] for month in (7, 8) for day in range(1, 29)]
        data = {"days": [c[0] for c in cohorts], "parts": {"theme15": {"cohorts": cohorts}}}
        chart, note = vx.bar_chart_html(data, "theme", "d")
        self.assertIn(str(vx.DAILY_BAR_KEEP), note)
        self.assertEqual(chart.count("<rect"), vx.DAILY_BAR_KEEP * 2)

    def test_plain_words_on_screen(self):
        html = vx.cards_html(self.data, "all") + vx.CSS
        for jargon in ("%p", "합격", "그물", "초과수익", "벤치마크"):
            self.assertNotIn(jargon, html)


class PageWiringTests(unittest.TestCase):
    def test_compare_sits_inside_the_scorecard_under_the_bars_above_the_close(self):
        panel = PAGE[PAGE.index("def _render_picklist_scorecard("):PAGE.index("def _render_picklist_section")]
        self.assertIn('st.container(key="j3sc_top")', panel)
        self.assertLess(panel.index('key="j3sc_top"'), panel.index("_render_scorecard_compare(span, picked)"))
        self.assertLess(panel.index("_render_scorecard_compare(span, picked)"),
                        panel.index('key="picklist_scorecard_US_close"'))
        # 순위 9 창은 막대까지를 싼 칸의 가운데에 뜬다(밑의 그림 때문에 멀어지지 않게).
        self.assertRegex(PAGE, r'div\[class\*="st-key-j3sc_top"\]\{position:relative\}')

    def test_compare_uses_the_same_rows_as_the_bars(self):
        body = PAGE[PAGE.index("def _scorecard_compare_cached("):PAGE.index("def _pick_scorecard_vx(")]
        for needle in ("newest and day >= newest", "_scorecard_in_span(when, anchor, span_days)",
                       "day < _SCORECARD_START", "_us_next_trading_day(when) > last",
                       'period="2y"', "IXIC_HISTORY_PERIOD"):
            self.assertIn(needle, body)

    def test_stock_list_only_for_a_picked_range(self):
        body = PAGE[PAGE.index("def _render_scorecard_compare("):PAGE.index("# 성적표 머리 자리")]
        self.assertIn("if span == _SCORECARD_RANGE and picked:", body)
        self.assertIn("vx.stocks_html(", body)
        self.assertIn("<div class='j3vx-body'>", body)

    def test_module_revision_guard(self):
        match = re.search(r"_REQUIRED_SCORECARD_COMPARE_REVISION = (\d+)", PAGE)
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), vx.MODULE_REVISION)

    def test_phone_rows_stay_in_one_line(self):
        import mobile_ui

        css = mobile_ui.page_css()
        self.assertIn('div[class*="st-key-j3vx_row"] [data-testid="stHorizontalBlock"]', css)
        self.assertIn("flex-wrap: nowrap", css[css.index("st-key-j3vx_row"):])
        required = int(re.search(r"_REQUIRED_MOBILE_REVISION = (\d+)", PAGE).group(1))
        self.assertEqual(required, mobile_ui.MODULE_REVISION)


if __name__ == "__main__":
    unittest.main()

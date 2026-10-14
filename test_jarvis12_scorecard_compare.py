"""자비스12 전용 「나스닥 종합과 견줘 보기」 — 순위 9 를 넣은 사본 (2026-10-14 상하님 — "매수심사결과 높은 순위 9 부분이
「세 파트 한눈에」 표에 빠져 있다 · 그래프에도 넣어 줘")."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import jarvis12_scorecard_compare as vx12
import scorecard_compare as vx3
from test_scorecard_compare import FRAMES, IXIC, _row

ROOT = Path(__file__).resolve().parent
J12 = (ROOT / "pages" / "11_자비스12.py").read_text(encoding="utf-8")
J3 = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")


class Jarvis12CompareTests(unittest.TestCase):
    def test_rank9_is_a_part_of_the_first_tab_in_its_table_colour(self):
        self.assertEqual(("theme15", "breakout", "top7", "crash"), vx12.PARTS)
        self.assertEqual("매수심사결과 높은 순위 9", vx12.PART_NAMES["top7"])
        self.assertEqual(("all", "네 파트 한눈에", vx12.PARTS), vx12.TABS[0])
        # 다른 탭은 그대로 — 순위 9 는 첫 탭에만
        self.assertEqual(vx3.TABS[1:], vx12.TABS[1:])

    def test_rank9_rows_are_counted_the_same_way_and_join_the_nasdaq_days(self):
        rows = [_row("2026-09-11", "theme15", "AAA", 100.0),
                _row("2026-09-15", "top7", "BBB", 50.0)]          # 순위 9 는 9/16 시가 50 에 산다
        data = vx12.compute(rows, FRAMES, IXIC)
        self.assertIn("top7", data["parts"])
        self.assertAlmostEqual(data["parts"]["top7"]["cohorts"][0][1], -10.0)   # 45/50
        # 「네 파트 한눈에」 나스닥은 넷 중 하나라도 산 날 — 9/14·9/16
        expected = ((1050 / 1000 + 1050 / 1020) / 2 - 1) * 100
        self.assertAlmostEqual(data["nasdaq"]["all"][-1], round(expected, 2))
        # 얼린 원본은 순위 9 를 안 센다(자비스3 은 그대로)
        self.assertNotIn("top7", vx3.compute(rows, FRAMES, IXIC)["parts"])
        # 순위 9 만 뺀 줄은 원본과 값이 같다 — 계산 방법은 그대로
        same = [r for r in rows if r["list_kind"] != "top7"]
        mine = vx12.compute(same, FRAMES, IXIC)["parts"]
        for part in mine.values():                                   # 사본은 종목 줄 끝에 산 날 둘을 더 붙인다
            part["stocks"] = [item[:5] for item in part["stocks"]]
        self.assertEqual(vx3.compute(same, FRAMES, IXIC)["parts"], mine)

    def test_cards_legend_and_lines_show_rank9(self):
        rows = [_row("2026-09-11", "theme15", "AAA", 100.0), _row("2026-09-11", "top7", "BBB", 50.0)]
        data = vx12.compute(rows, FRAMES, IXIC)
        for html_text in (vx12.cards_html(data, "all"), vx12.legend_html("all", data)):
            self.assertIn("매수심사결과 높은 순위 9", html_text)
        self.assertIn(vx12.PART_COLORS["top7"], vx12.line_chart_html(data, "all", "d"))

    def test_daily_bars_keep_the_same_thickness_with_five_lanes(self):
        import pandas as pd

        days = pd.bdate_range("2026-08-03", periods=40)
        ixic = pd.DataFrame({"Open": [1000.0 + i for i in range(40)], "Close": [1001.0 + i for i in range(40)]},
                            index=days)
        frames = {code: pd.DataFrame({"Close": [100.0 + i for i in range(40)]}, index=days) for code in "ABCD"}
        rows = [_row(str(day.date()), kind, code, 100.0)
                for day in days[:-1] for kind, code in zip(vx12.PARTS, "ABCD")]
        data = vx12.compute(rows, frames, ixic)
        chart, note = vx12.bar_chart_html(data, "all", "d")
        self.assertIn("최근 24일만", note)                          # 다섯 줄이면 24일(넷일 때 30일과 같은 굵기)
        widths = {round(float(w), 1) for w in re.findall(r"<rect x='[^']+' y='[^']+' width='([^']+)'", chart)}
        self.assertEqual({round(1000.0 / 24 * 0.78 / 5, 1)}, widths)
        _chart, note2 = vx12.bar_chart_html(data, "swing", "d")
        self.assertIn("최근 30일만", note2)                         # 둘 + 나스닥은 그대로

    def test_buy_column_shows_dates_not_a_count_read_as_a_day(self):
        """「왜 날짜가 산 날이 1일이냐?」 (2026-10-14 상하님) — 「산 날」 칸은 날짜. 여러 번이면 처음~마지막과 횟수."""
        rows = [_row("2026-09-11", "theme15", "AAA", 100.0), _row("2026-09-15", "theme15", "AAA", 100.0),
                _row("2026-09-11", "breakout", "BBB", 50.0)]
        data = vx12.compute(rows, FRAMES, IXIC)
        text = vx12.stocks_html(data, "all", first="2026-09-11", last="2026-09-15")
        self.assertIn("<td>9/14~9/16<br><small>2번</small></td>", text)     # 9/11·9/15 목록 → 다음 거래일에 삼
        self.assertIn("<td>9/14</td>", text)
        self.assertNotIn("1일</td>", text)
        cards = vx12.cards_html(data, "all")
        self.assertIn("2번 산 것 중", cards)                                  # 상위 테마 — 9/14 · 9/16
        self.assertIn("9/14 한 번 산 것입니다", cards)                        # 상승장 — 하루
        self.assertNotIn("일 중", cards)
        # 보관에 남은 옛 판(날짜 없는 다섯 칸)도 깨지지 않는다
        for part in data["parts"].values():
            part["stocks"] = [item[:5] for item in part["stocks"]]
        self.assertIn("<td>2번</td>", vx12.stocks_html(data, "all"))

    def test_jarvis12_uses_the_copy_and_jarvis3_keeps_the_frozen_one(self):
        self.assertIn("import jarvis12_scorecard_compare as scorecard_compare", J12)
        self.assertIn("_REQUIRED_SCORECARD_COMPARE_REVISION = 2026101450", J12)
        self.assertEqual(2026101450, vx12.MODULE_REVISION)
        self.assertIn("네 파트를 한 그림에", J12)
        self.assertIn("\nimport scorecard_compare\n", J3)
        self.assertNotIn("jarvis12_scorecard_compare", J3)


if __name__ == "__main__":
    unittest.main()

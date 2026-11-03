"""자비스13 디자인 2차 — 자비스12 형식 (2026-11-04 상하님).

「테마 디자인 숨기기 하고 미국테마 형식대로」 · 「이것도 미국테마 디자인처럼 · 누르면 직전 저장이 나와야지」 ·
「재무 한눈에 보기 이것도 클릭하면 열리고 닫히고」 · 「각 차트 … 누르면 확대 열리고 닫히고」 · 「연간 실적 분기 실적 … 각 파트별로」.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
PAGE = ROOT / "pages" / "12_자비스13.py"


class FlowCardTests(unittest.TestCase):
    def test_folds_like_jarvis12_and_shows_previous_only_when_opened(self):
        source = (ROOT / "jarvis13_flow_card.py").read_text(encoding="utf-8")
        body = source.split("def render()")[1]
        closed, opened = body.split("if not is_open:")[1].split("return", 1)
        self.assertIn("_peek_gauge_html", closed)                      # 닫힘 — 당일 계기판 하나
        self.assertNotIn("_previous_kr_flow_comparison", closed)
        self.assertIn("_previous_kr_flow_comparison", opened)           # 열면 — 직전 저장까지
        self.assertIn("comparison_result=previous_result", opened)
        self.assertIn('key="j13_flow_refresh"', source)                 # 이름은 j13 (자비스4 kr_flow_refresh 와 섞이지 않게)
        self.assertIn("@st.fragment(run_every=60)", source)             # 1분 자동 확인은 그대로

    def test_page_uses_the_folding_card(self):
        source = PAGE.read_text(encoding="utf-8")
        self.assertIn("jarvis13_flow_card.render()", source)
        self.assertNotIn("    market_signal_ui.render_kr_flow_card()", source)


class ChartTests(unittest.TestCase):
    def test_zoom_html_has_switch_cell_and_popup_with_j13_names(self):
        import jarvis13_charts as charts

        text = charts.zoom_html([("당일", "<svg class='j13-pretty-chart'></svg>", "2026-11-04 10:00"),
                                 ("일봉", "<svg class='j13-pretty-chart'></svg>", "")], "j13cz-t_1")
        self.assertEqual(2, text.count("class='j13cz-tap"))
        self.assertIn("j13cz-cell", text)
        self.assertIn("j13cz-pop j13cz-p1", text)
        self.assertIn("다시 누르면 닫힘", text)
        self.assertNotIn("j3cz-", text)                                 # 자비스12 이름과 섞이지 않는다
        self.assertNotIn("@media (max-width: 600px)", charts.CSS)      # 폰 규칙은 mobile_ui 에만(CLAUDE.md 12)
        self.assertIn("window.__j13ZoomClone", charts.CLONE_JS)

    def test_candles_and_lines_draw(self):
        import jarvis13_charts as charts

        index = pd.date_range("2026-01-01", periods=80, freq="B")
        close = pd.Series([100 + i * 0.5 for i in range(80)], index=index)
        frame = pd.DataFrame({"Open": close - 1, "High": close + 2, "Low": close - 2, "Close": close}, index=index)
        self.assertIn("j13-candle-chart", charts.candle_svg(frame))
        self.assertEqual("", charts.candle_svg(None))
        self.assertIn("<polyline", charts.pretty_svg([1, 2, 1.5, 3], base=2))
        self.assertEqual("", charts.pretty_svg([1]))

    def test_page_charts_are_one_bundle_that_zooms(self):
        source = PAGE.read_text(encoding="utf-8")
        self.assertIn('"📊 당일 · 일봉 · 주봉 · 월봉 보기"', source)
        self.assertIn("jarvis13_charts.zoom_html(boxes, zoom_id)", source)
        self.assertIn("'j13cz-clone-script'", source)


class ResultsCellTests(unittest.TestCase):
    def test_cells_read_the_file_and_mark_missing(self):
        import jarvis13_fundamentals as fundamentals

        cells = fundamentals.results_cells(["005930", "없는코드"])
        self.assertIn("j13rc", cells["005930"][0])
        self.assertIn("매출", cells["005930"][1])
        self.assertEqual(cells["없는코드"][0], cells["없는코드"][1])
        self.assertIn("—", cells["없는코드"][0])

    def test_growth_uses_korean_colors(self):
        import jarvis13_fundamentals as fundamentals

        up = fundamentals._result_cell([["24.12", 100.0, 10.0, 5.0], ["25.12", 120.0, 12.0, 6.0]],
                                       ["24.12", 100.0, 10.0, 5.0])
        down = fundamentals._result_cell([["24.12", 100.0, 10.0, 5.0], ["25.12", 80.0, -1.0, -2.0]],
                                         ["24.12", 100.0, 10.0, 5.0])
        self.assertIn("#ff5b5b'>매출 +20.0%", up)                       # 늘면 빨강(한국장 색)
        self.assertIn("#4da6ff'>매출 -20.0%", down)                     # 줄면 파랑
        self.assertIn("영업적자", down)

    def test_every_stock_table_has_the_two_columns(self):
        source = PAGE.read_text(encoding="utf-8")
        for name in ("def _render_leader_table", "def _render_top_reviewed", "def _render_rulebook_finder",
                     "widths = [0.55, 2.0, 1.4, 1.1, 1.6"):
            block = source.split(name)[1][:9000]
            self.assertIn('"연간 실적", "분기 실적"', block, name)
            self.assertIn("_results_cells(", block, name)


class FundamentalsPopupTests(unittest.TestCase):
    def test_box_opens_as_a_popup_like_jarvis12(self):
        source = PAGE.read_text(encoding="utf-8")
        block = source.split("def _render_fundamentals_box(")[1].split("\ndef ")[0]
        self.assertIn("class='j13fz-tap'", block)
        self.assertNotIn("j13dp-", block)          # 4주간 일별 시세 창(j13dp-)과 이름이 섞이지 않는다
        self.assertIn("class='j13fz-open'>📑 재무 한눈에 보기", block)
        self.assertIn("다시 누르면 닫힘", block)
        self.assertNotIn("<details", block)


if __name__ == "__main__":
    unittest.main()

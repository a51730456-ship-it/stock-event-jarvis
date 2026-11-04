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


class Theme15Tests(unittest.TestCase):
    """2026-11-04 상하님 「해라」 — 한국 상위 테마 5개 · 각 1~3위를 쌓아 「코스피와 견줘 보기」에 줄로."""

    def test_picks_top5_themes_three_each_in_theme_order(self):
        import jarvis13_theme15 as t15

        class Fake:
            def get_theme_leaders(self, theme_row, market_score=0, theme_score=0):
                return {"ok": True, "rows": [{"code": f"{theme_row['name']}{i}", "name": f"{theme_row['name']}{i}", "rank": i}
                                             for i in range(1, 7)]}

        themes = [{"name": n, "score": s, "ok": True} for n, s in (("가", 50), ("나", 90), ("다", 70), ("라", 10), ("마", 60), ("바", 80))]
        out = t15.find_theme_top_picks(themes, data=Fake())
        self.assertEqual(["나", "바", "다", "마", "가"], out["themes"])          # 점수 순 위 5개
        self.assertEqual(15, len(out["rows"]))
        self.assertEqual([1, 2, 3], [row["rank"] for row in out["rows"][:3]])   # 테마 안 등수 그대로
        self.assertEqual(1, out["rows"][0]["theme_place"])

    def test_rows_save_and_load_from_its_own_folder(self):
        import tempfile

        import jarvis13_theme15 as t15
        import picklist_store as store

        result = {"ok": True, "rows": [{"code": "005930", "name": "삼성전자", "rank": 1, "theme_place": 1, "score": 80.0}]}
        with tempfile.TemporaryDirectory() as folder:
            rows = store.rows_from_result(result, market="KR", list_kind="theme15", trade_date="2026-11-04")
            self.assertTrue(store.save_rows(rows, trade_date="2026-11-04", market="KR", out_dir=folder))
            loaded = t15.load_all(store, out_dir=folder)
        self.assertEqual(["005930"], [row["code"] for row in loaded])
        self.assertEqual("theme15", loaded[0]["list_kind"])
        self.assertEqual([], t15.load_all(store, out_dir="/없는/폴더"))

    def test_compare_has_the_theme_tab_and_page_reads_the_folder(self):
        import jarvis13_scorecard_compare as vx

        self.assertEqual("theme15", vx.PARTS[0])
        self.assertIn("theme", vx.TAB_PARTS)
        self.assertIn("jarvis13_theme15.load_all(picklist_store)", PAGE.read_text(encoding="utf-8"))


class FixesNov4Tests(unittest.TestCase):
    """2026-11-04 상하님 폰 캡처 — 지수 칸 빈자리 · 밑 막대 크기 · 느린 첫 화면 · 자비스12 관심종목 「한국테마」 단추."""

    def test_hidden_daily_chart_stays_stacked(self):
        import jarvis13_skin as skin

        self.assertNotIn(".j4-idx-more,body:has(.j13-market-top) .j4-idx-solo{position:relative}", skin.SKIN)
        self.assertIn(".j4-idx-now,body:has(.j13-market-top) .j4-idx-solo{position:relative}", skin.SKIN)

    def test_bottom_nav_uses_jarvis12_sizes(self):
        source = PAGE.read_text(encoding="utf-8")
        self.assertIn(".j13b-bottom-nav{height:50px!important", source)
        self.assertIn("width:min(286.667px,66.667vw)!important", source)

    def test_screen_tells_us_worker_it_is_waiting(self):
        import importlib
        import sys
        import types

        fake = types.SimpleNamespace(_FG_WAITING={"n": 0}, _FG_WAITING_LOCK=__import__("threading").Lock())
        saved = sys.modules.get("jarvis3_data")
        sys.modules["jarvis3_data"] = fake
        try:
            source = PAGE.read_text(encoding="utf-8")
            block = source.split("class _ScreenWaitsForUS:")[1].split("\n# **1분 자동 갱신 표시는")[0]
            space = {"importlib": importlib}
            exec("class _ScreenWaitsForUS:" + block, space)
            with space["_ScreenWaitsForUS"]():
                self.assertEqual(1, fake._FG_WAITING["n"])
            self.assertEqual(0, fake._FG_WAITING["n"])
        finally:
            if saved is not None:
                sys.modules["jarvis3_data"] = saved
            else:
                sys.modules.pop("jarvis3_data", None)
        block = source.split("with _ScreenWaitsForUS():")[1][:400]
        self.assertIn('overview = jarvis13_shared.remember(("market_overview", id(j4data.get_market_overview)), j4data.get_market_overview,', block)

    def test_jarvis12_watch_hero_has_korea_link(self):
        source = (ROOT / "pages" / "11_자비스12.py").read_text(encoding="utf-8")
        hero = source.split('with st.container(key="j12b_hero_box"):')[1][:2500]
        self.assertIn('method_help.cross_link(st, "US")', hero)
        self.assertIn("_J12B_CROSS_CSS", hero)
        self.assertLess(source.index("_J12B_CROSS_CSS = "), source.index("\nmain()"))


class FragmentPlacementTests(unittest.TestCase):
    def test_market_overview_refreshes_every_minute(self):
        # 1분 자동 갱신 표시가 시장 개요 함수에 붙어 있어야 한다(2026-11-04 class 에 붙어 있던 것을 바로잡음).
        source = PAGE.read_text(encoding="utf-8")
        self.assertIn("@st.fragment(run_every=60)\ndef _render_market_overview() -> None:", source)
        self.assertNotIn("@st.fragment(run_every=60)\nclass ", source)


class SharedKeepTests(unittest.TestCase):
    """2026-11-04 상하님 「로딩 문제 해결하고」 — 손님끼리 55초 같이 쓴다 · 못 받은 판은 안 담는다."""

    def test_keeps_good_values_and_skips_failures(self):
        import jarvis13_shared as shared

        calls = []

        def ok():
            calls.append(1)
            return {"ok": True, "n": len(calls)}

        good = lambda value: bool(value.get("ok"))
        shared._BOX.clear()
        self.assertEqual(1, shared.remember("t", ok, good=good)["n"])
        self.assertEqual(1, shared.remember("t", ok, good=good)["n"])     # 두 번째 손님은 받으러 안 간다
        self.assertEqual(1, len(calls))
        shared._BOX.clear()
        bad = lambda: {"ok": False}
        shared.remember("b", bad, good=good)
        self.assertIsNone(shared.peek("b"))                                 # 실패는 안 담는다
        shared.put("p", {"x": 1})
        self.assertEqual({"x": 1}, shared.peek("p"))
        self.assertIsNone(shared.peek("p", keep=-1))

    def test_flow_card_adopts_shared_result(self):
        source = (ROOT / "jarvis13_flow_card.py").read_text(encoding="utf-8")
        self.assertIn("jarvis13_shared.peek((SHARED_KEY, id(msu.run_kr_flow_check)))", source)
        self.assertIn("jarvis13_shared.put((SHARED_KEY, id(msu.run_kr_flow_check))", source)
        self.assertIn('not st.session_state.get("kr_flow_foreign_futures_manual")', source)


if __name__ == "__main__":
    unittest.main()

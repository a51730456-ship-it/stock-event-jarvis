import ast
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


SOURCE = Path("app.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _function(name):
    return next(
        node
        for node in TREE.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


class CloudStartupPerformanceTests(unittest.TestCase):
    def test_login_screen_precedes_heavy_market_imports(self):
        auth_gate = SOURCE.index('if not st.session_state.get("authenticated"):')
        stop_at = SOURCE.index("    st.stop()", auth_gate)

        for import_line in (
            "import pandas as pd",
            "import database as db",
            "import news_data",
            "import performance",
            "import bookmaker_data",
            "import theme_data",
            "import price_data",
        ):
            self.assertGreater(SOURCE.index(import_line), stop_at, import_line)

    def test_snapshot_batch_is_parallel_and_isolates_one_ticker_failure(self):
        class PriceData:
            @staticmethod
            def get_snapshot_defaults(ticker):
                if ticker == "FAIL":
                    raise TimeoutError("mock timeout")
                return {"ok": True, "current": 100.0, "ticker": ticker}

        namespace = {
            "ThreadPoolExecutor": ThreadPoolExecutor,
            "as_completed": as_completed,
            "price_data": PriceData(),
        }
        exec(
            compile(ast.Module(body=[_function("_fetch_kr_snapshot_results")], type_ignores=[]), "app.py", "exec"),
            namespace,
        )

        result = namespace["_fetch_kr_snapshot_results"](("A", "FAIL", "B"))

        self.assertTrue(result["A"]["ok"])
        self.assertTrue(result["B"]["ok"])
        self.assertFalse(result["FAIL"]["ok"])

    def test_cloud_auto_fetch_uses_short_shared_caches(self):
        self.assertIn("@st.cache_resource(show_spinner=False)\ndef _initialize_database_once", SOURCE)
        self.assertIn("@st.cache_data(ttl=45, show_spinner=False)\ndef _cached_fetch_market_overview", SOURCE)
        self.assertIn("@st.cache_data(ttl=60, show_spinner=False)\ndef _cached_kr_mood_source_results", SOURCE)
        self.assertIn("@st.cache_data(ttl=90, show_spinner=False)\ndef _cached_kr_snapshot_results", SOURCE)
        self.assertIn("@st.cache_data(ttl=300, show_spinner=False)\ndef _cached_fetch_kr_theme_snapshot", SOURCE)
        self.assertIn("@st.cache_data(ttl=120, show_spinner=False)\ndef _cached_fetch_bookmaker_snapshot", SOURCE)
        self.assertIn("@st.cache_data(ttl=3600, show_spinner=False)\ndef _cached_translate_bookmaker_texts", SOURCE)

        tab_prelude = SOURCE[SOURCE.index("def _render_tab_kr():"):SOURCE.index('_render_market_overview("KR")', SOURCE.index("def _render_tab_kr():"))]
        self.assertIn('_cached_fetch_market_overview("KR")', tab_prelude)
        self.assertIn("_cached_get_top_kr_stocks_by_amount(12)", tab_prelude)
        self.assertIn("run_kr_mood_auto_check()", tab_prelude)
        self.assertIn("run_kr_snapshot_auto_fill()", tab_prelude)

    def test_manual_buttons_force_fresh_market_and_stock_queries(self):
        actions = SOURCE[
            SOURCE.index("def _render_kr_primary_actions"):
            SOURCE.index("def _render_kr_fable_mockup1_preview")
        ]
        self.assertIn("run_kr_mood_auto_check(force_refresh=True)", actions)
        self.assertIn("run_kr_snapshot_auto_fill(force_refresh=True)", actions)

    def test_manual_stock_prepare_does_not_force_a_second_full_rerun(self):
        actions = SOURCE[
            SOURCE.index("def _render_kr_primary_actions"):
            SOURCE.index("def _render_kr_fable_mockup1_preview")
        ]
        self.assertNotIn("st.rerun()", actions)

    def test_us_tab_auto_runs_market_overview_sector_and_stock_snapshot_once(self):
        # 2026-07-15 사용자 요청: 미국장 탭도 한국장 탭처럼 로그인(탭 진입) 후 한 번
        # 자동으로 시장자료/섹터ETF/8종목 스냅샷을 순서대로 불러와야 한다.
        us_tab = SOURCE[SOURCE.index('def _render_tab_us():'):SOURCE.index('_render_market_overview("US")', SOURCE.index('def _render_tab_us():'))]
        self.assertIn('if not st.session_state.get("us_auto_run_stage1_done"):', us_tab)
        self.assertIn('_cached_fetch_market_overview("US")', us_tab)
        self.assertIn('_cached_fetch_us_sector_snapshot()', us_tab)
        self.assertIn('_cached_fetch_us_theme_indicators()', us_tab)
        self.assertIn('_cached_kr_snapshot_results(_us_auto_tickers)', us_tab)
        self.assertIn('st.session_state["us_auto_run_stage1_done"] = True', us_tab)

    def test_relogin_resets_us_auto_run_flags_alongside_kr(self):
        login_button_at = SOURCE.index('if st.button("로그인"')
        login_handler = SOURCE[login_button_at:SOURCE.index("st.stop()", login_button_at)]
        self.assertIn('"us_auto_run_version"', login_handler)
        self.assertIn('"us_auto_run_stage1_done"', login_handler)
        self.assertIn('"kr_bookmaker_auto_fetch_pending"', login_handler)

    def test_us_dynamic_stock_selection_ranks_by_turnover_and_isolates_failures(self):
        # 2026-07-15 사용자 요청: 미국장도 한국장처럼 거래대금 상위 종목을 자동 선정해야
        # 한다(대형주 후보군 안에서). 조회 실패/거래대금 0 종목은 후보에서 빠져야 한다.
        class PriceData:
            @staticmethod
            def get_snapshot_defaults(ticker):
                turnovers = {"TSLA": 300.0, "AMD": 500.0, "AAPL": 100.0}
                if ticker == "FAIL":
                    raise TimeoutError("mock timeout")
                if ticker == "ZERO":
                    return {"ok": True, "turnover": 0}
                return {"ok": True, "turnover": turnovers.get(ticker, 1.0)}

        namespace = {
            "ThreadPoolExecutor": ThreadPoolExecutor,
            "as_completed": as_completed,
            "price_data": PriceData(),
        }
        exec(
            compile(
                ast.Module(
                    body=[_function("_fetch_kr_snapshot_results"), _function("_fetch_top_us_stocks_by_amount")],
                    type_ignores=[],
                ),
                "app.py",
                "exec",
            ),
            namespace,
        )
        namespace["US_CANDIDATE_UNIVERSE"] = [
            {"name": "TSLA", "ticker": "TSLA", "sector": "x"},
            {"name": "AMD", "ticker": "AMD", "sector": "x"},
            {"name": "AAPL", "ticker": "AAPL", "sector": "x"},
            {"name": "FAIL", "ticker": "FAIL", "sector": "x"},
            {"name": "ZERO", "ticker": "ZERO", "sector": "x"},
        ]

        result = namespace["_fetch_top_us_stocks_by_amount"](2)

        self.assertEqual([s["ticker"] for s in result], ["AMD", "TSLA"])

    def test_us_stock_selection_stage_precedes_detail_fetch_stage(self):
        us_tab = SOURCE[SOURCE.index('def _render_tab_us():'):SOURCE.index('_render_market_overview("US")', SOURCE.index('def _render_tab_us():'))]
        select_stage = us_tab.index('if not st.session_state.get("us_auto_run_stage1_done"):')
        detail_stage = us_tab.index('if not st.session_state.get("us_auto_run_stage2_done"):')
        self.assertLess(select_stage, detail_stage)
        self.assertIn('_cached_get_top_us_stocks_by_amount(8)', us_tab)
        self.assertIn('st.session_state["dynamic_us_snapshot_stocks"]', us_tab)

    def test_us_primary_action_reselects_stocks_before_refreshing_details(self):
        primary_action = SOURCE[
            SOURCE.index('key="us_auto_preview_run"'):
            SOURCE.index('st.session_state["us_auto_preview_done_at"]')
        ]
        self.assertIn("_short_cached_top_us_stocks_by_amount(8)", primary_action)
        self.assertIn('st.session_state["dynamic_us_snapshot_stocks"] = _us_reselected', primary_action)

    def test_refresh_buttons_use_short_cache_not_a_full_bypass(self):
        # 2026-07-15 사용자 요청: "새로고침 버튼을 바로 다시 누르면 또 느리다"는 지적으로,
        # force_refresh 경로가 캐시를 완전히 무시하던 것을 8초짜리 짧은 캐시로 바꿨다.
        # 연속 재클릭은 즉시 응답되면서도, 몇 초 뒤 실제 새로고침 의도는 그대로 살아있다.
        self.assertIn(
            "@st.cache_data(ttl=FORCE_REFRESH_SHORT_TTL, show_spinner=False)\ndef _short_cached_fetch_market_overview",
            SOURCE,
        )
        self.assertIn(
            "@st.cache_data(ttl=FORCE_REFRESH_SHORT_TTL, show_spinner=False)\ndef _short_cached_kr_mood_source_results",
            SOURCE,
        )
        self.assertIn(
            "@st.cache_data(ttl=FORCE_REFRESH_SHORT_TTL, show_spinner=False)\ndef _short_cached_kr_snapshot_results",
            SOURCE,
        )
        self.assertIn(
            "@st.cache_data(ttl=FORCE_REFRESH_SHORT_TTL, show_spinner=False)\ndef _short_cached_fetch_kr_theme_snapshot",
            SOURCE,
        )
        self.assertIn(
            "@st.cache_data(ttl=FORCE_REFRESH_SHORT_TTL, show_spinner=False)\ndef _short_cached_fetch_us_sector_snapshot",
            SOURCE,
        )
        self.assertIn(
            "@st.cache_data(ttl=FORCE_REFRESH_SHORT_TTL, show_spinner=False)\ndef _short_cached_fetch_us_theme_indicators",
            SOURCE,
        )
        self.assertIn(
            "@st.cache_data(ttl=FORCE_REFRESH_SHORT_TTL, show_spinner=False)\ndef _short_cached_top_us_stocks_by_amount",
            SOURCE,
        )

        run_mood_fn = SOURCE[SOURCE.index("def run_kr_mood_auto_check"):SOURCE.index("def run_kr_snapshot_auto_fill")]
        self.assertIn("_short_cached_kr_mood_source_results()", run_mood_fn)
        self.assertNotIn("_fetch_kr_mood_source_results()\n        if force_refresh", run_mood_fn)

        run_fill_fn = SOURCE[SOURCE.index("def run_kr_snapshot_auto_fill"):SOURCE.index("_AUTO_FETCH_FIELD_LABELS")]
        self.assertIn("_short_cached_kr_snapshot_results(_snapshot_tickers)", run_fill_fn)


if __name__ == "__main__":
    unittest.main()

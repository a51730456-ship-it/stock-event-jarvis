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

        tab_prelude = SOURCE[SOURCE.index("with tab_kr:"):SOURCE.index('_render_market_overview("KR")', SOURCE.index("with tab_kr:"))]
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
        us_tab = SOURCE[SOURCE.index('with tab_us:'):SOURCE.index('_render_market_overview("US")', SOURCE.index('with tab_us:'))]
        self.assertIn('if not st.session_state.get("us_auto_run_stage1_done"):', us_tab)
        self.assertIn('_cached_fetch_market_overview("US")', us_tab)
        self.assertIn('theme_data.fetch_us_sector_snapshot()', us_tab)
        self.assertIn('theme_data.fetch_us_theme_indicators()', us_tab)
        self.assertIn('_cached_kr_snapshot_results(_us_auto_tickers)', us_tab)
        self.assertIn('st.session_state["us_auto_run_stage1_done"] = True', us_tab)

    def test_relogin_resets_us_auto_run_flags_alongside_kr(self):
        login_button_at = SOURCE.index('if st.button("로그인"')
        login_handler = SOURCE[login_button_at:SOURCE.index("st.stop()", login_button_at)]
        self.assertIn('"us_auto_run_version"', login_handler)
        self.assertIn('"us_auto_run_stage1_done"', login_handler)
        self.assertIn('"kr_bookmaker_auto_fetch_pending"', login_handler)


if __name__ == "__main__":
    unittest.main()

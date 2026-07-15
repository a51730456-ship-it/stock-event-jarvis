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

    def test_kr_mockup_preview_is_computed_after_primary_actions_button(self):
        # 2026-07-15: 미리보기 데이터가 버튼 처리보다 먼저 계산되면, 버튼이 종목을
        # 재선정해도 그 실행에서는 이전(3종목) 목록이 보인다 — 반드시 버튼 뒤여야 한다.
        mockup_fn = SOURCE[
            SOURCE.index("def _render_kr_fable_mockup1_preview"):
            SOURCE.index("def _render_us_stock_judgment_preview")
        ]
        self.assertLess(
            mockup_fn.index("_render_kr_primary_actions()"),
            mockup_fn.index("stage2_preview = _memoized_kr_stage2_preview()"),
        )

    def test_login_warmup_runs_all_auto_fetches_in_parallel(self):
        # 2026-07-15 사용자 요청("순차 실행하지 마라"): 로그인 직후 KR/US 자동조회
        # 전부를 병렬로 데워서 탭 렌더링은 캐시 히트만 하게 한다.
        warmup = SOURCE[
            SOURCE.index('if not st.session_state.get("parallel_warmup_done"):'):
            SOURCE.index('KR_AUTO_RUN_VERSION = ')
        ]
        for call in (
            '_cached_fetch_market_overview, "KR"',
            '_cached_fetch_market_overview, "US"',
            "_cached_kr_mood_source_results",
            "_cached_fetch_kr_theme_snapshot",
            "_cached_fetch_us_sector_snapshot",
            "_cached_fetch_us_theme_indicators",
            "_cached_fetch_bookmaker_snapshot",
            "_cached_get_top_kr_stocks_by_amount, 12",
            "_cached_get_top_us_stocks_by_amount, 8",
        ):
            self.assertIn(call, warmup)

    def test_fragments_refresh_dynamic_stock_globals_each_run(self):
        kr_fragment = SOURCE[SOURCE.index("def _render_tab_kr():"):SOURCE.index("with tab_kr:\n    _render_tab_kr()")]
        self.assertIn('globals()["SNAPSHOT_STOCKS"]', kr_fragment)
        us_fragment = SOURCE[SOURCE.index("def _render_tab_us():"):SOURCE.index("with tab_us:\n    _render_tab_us()")]
        self.assertIn('globals()["US_SNAPSHOT_STOCKS"]', us_fragment)

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

    def test_kr_theme_table_has_stable_key_so_row_selection_persists(self):
        # 2026-07-15: st.dataframe을 key 없이 호출하면 Streamlit이 위젯 id를 data
        # 내용까지 포함해 해시한다(streamlit/elements/lib/utils.py의
        # compute_and_register_element_id 실측 확인). 이 표는 선택된 테마가 바뀔
        # 때마다 "세부 입력" 열 값이 바뀌어 매 클릭마다 위젯 id가 달라졌고, 그
        # 결과 방금 클릭한 행의 체크 표시가 다음 rerun에서 사라졌다(사용자 반복
        # 지적). key를 명시하면 selection_mode/is_selection_activated만 id 계산에
        # 쓰이고 data는 제외되어 선택 상태가 유지된다 — 이 key가 다시 빠지지
        # 않도록 회귀 테스트로 고정한다.
        theme_editor_fn = SOURCE[
            SOURCE.index("def _render_kr_theme_chip_editor"):
            SOURCE.index("def _render_kr_primary_actions")
        ]
        self.assertIn("_kr_theme_table_event = st.dataframe(", theme_editor_fn)
        self.assertIn('key="kr_theme_table_df"', theme_editor_fn)
        self.assertIn('on_select="rerun"', theme_editor_fn)

    def test_memoized_kr_stage2_preview_reuses_cache_but_detects_manual_edits(self):
        # 2026-07-15: 카드 클릭 시 12종목 점수를 매번 새로 계산하던 것을 캐싱했다.
        # 캐시 키가 "언제 자동조회했는지" 타임스탬프만 보면, 사용자가 종목별 입력
        # 카드에서 값을 직접 고친 직후에도 캐시가 옛 점수를 그대로 돌려주는 사고가
        # 날 수 있다(_get_snapshot_value/_collect_risk_fields가 읽는 snap_{ticker}_*
        # 값 전체를 캐시 키가 반영해야 함) — 이를 회귀 테스트로 고정한다.
        session_state = {}

        class SessionState:
            def get(self, key, default=None):
                return session_state.get(key, default)

            def __setitem__(self, key, value):
                session_state[key] = value

            def items(self):
                return session_state.items()

        class St:
            session_state = SessionState()

        call_count = {"n": 0}

        def fake_build_kr_stage2_preview():
            call_count["n"] += 1
            return {"rows": [], "call": call_count["n"]}

        namespace = {
            "st": St(),
            "SNAPSHOT_STOCKS": [{"name": "테스트종목", "ticker": "000001"}],
            "build_kr_stage2_preview": fake_build_kr_stage2_preview,
        }
        exec(
            compile(ast.Module(body=[_function("_memoized_kr_stage2_preview")], type_ignores=[]), "app.py", "exec"),
            namespace,
        )
        memoized = namespace["_memoized_kr_stage2_preview"]

        first = memoized()
        self.assertEqual(call_count["n"], 1)

        second = memoized()
        self.assertEqual(call_count["n"], 1, "입력값이 그대로면 캐시를 재사용해야 한다")
        self.assertEqual(first, second)

        session_state["snap_000001_current"] = 12345.0
        memoized()
        self.assertEqual(call_count["n"], 2, "가격 입력값이 바뀌면 캐시를 무효화해야 한다")

        session_state["snap_000001_entry_price"] = 9999.0
        memoized()
        self.assertEqual(
            call_count["n"], 3,
            "진입가 등 위험관리 입력값이 바뀌어도 캐시를 무효화해야 한다(risk_fields도 이 함수의 결과에 포함됨)",
        )

        memoized()
        self.assertEqual(call_count["n"], 3, "위험관리 입력값도 그대로면 다시 캐시를 재사용해야 한다")

    def test_fragment_scoped_rerun_tries_fragment_scope_then_falls_back(self):
        # 2026-07-15 사용자 지적("뭐든 클릭하면 속도가 여전히 느린이유가 뭐냐"):
        # st.rerun()을 scope 없이 부르면 fragment 안에서 호출해도 항상 전체 앱을
        # 다시 실행한다(Streamlit 기본값 scope="app" - 소스 실측 확인). 지난 세션엔
        # scope="fragment"가 AppTest에서 예외가 나서 "플랫폼 제약"이라 결론지었지만,
        # AppTest는 st.dataframe 행 선택 같은 진짜 프래그먼트 트리거를 재현할 방법이
        # 없어(select_rows 같은 API 자체가 없음) 그 결론 자체가 테스트 한계였을 가능성이
        # 높다. 실제 배포에서는 성립할 수 있으므로 먼저 시도하고, 안 되면(StreamlitAPIException)
        # 항상 기존과 동일하게 안전하게 되돌아가는 래퍼를 검증한다.
        class FakeAPIException(Exception):
            pass

        class FakeErrors:
            StreamlitAPIException = FakeAPIException

        calls = []

        class StFragmentOk:
            errors = FakeErrors

            def rerun(self, *, scope="app"):
                calls.append(scope)

        namespace = {"st": StFragmentOk()}
        exec(
            compile(ast.Module(body=[_function("_fragment_scoped_rerun")], type_ignores=[]), "app.py", "exec"),
            namespace,
        )
        namespace["_fragment_scoped_rerun"]()
        self.assertEqual(calls, ["fragment"], "fragment rerun이 가능하면 그것만 부르고 끝나야 한다")

        calls.clear()

        class StFragmentBlocked:
            errors = FakeErrors

            def rerun(self, *, scope="app"):
                calls.append(scope)
                if scope == "fragment":
                    raise FakeAPIException("scope=fragment can only be specified ...")

        namespace2 = {"st": StFragmentBlocked()}
        exec(
            compile(ast.Module(body=[_function("_fragment_scoped_rerun")], type_ignores=[]), "app.py", "exec"),
            namespace2,
        )
        namespace2["_fragment_scoped_rerun"]()
        self.assertEqual(
            calls, ["fragment", "app"],
            "fragment rerun이 막히면 예외를 삼키고 전체 rerun으로 안전하게 돌아가야 한다",
        )

    def test_theme_table_and_candidate_card_clicks_use_fragment_scoped_rerun(self):
        # 위 헬퍼가 실제로 3곳(테마 표 클릭, 한국장/미국장 후보 카드 클릭)에 연결돼
        # 있는지 고정한다 - 그냥 만들어만 두고 안 쓰면 의미가 없다.
        theme_editor_fn = SOURCE[
            SOURCE.index("def _render_kr_theme_chip_editor"):
            SOURCE.index("def _render_kr_primary_actions")
        ]
        self.assertIn('st.session_state["_kr_theme_pending_select"] = _kr_theme_clicked_name', theme_editor_fn)
        self.assertIn("_fragment_scoped_rerun()", theme_editor_fn)

        kr_mockup_fn = SOURCE[
            SOURCE.index("def _render_kr_fable_mockup1_preview"):
            SOURCE.index("def _render_us_stock_judgment_preview")
        ]
        self.assertIn('st.session_state["mockup1_pending_ticker"] = row["ticker"]', kr_mockup_fn)
        self.assertIn("_fragment_scoped_rerun()", kr_mockup_fn)

        us_judgment_fn = SOURCE[
            SOURCE.index("def _render_us_stock_judgment_preview"):
            SOURCE.index("def _render_review_tag_editors")
        ]
        self.assertIn('st.session_state["us_mockup_pending_ticker"] = row["ticker"]', us_judgment_fn)
        self.assertIn("_fragment_scoped_rerun()", us_judgment_fn)

    def test_bookmaker_expander_title_is_2x_red_on_light_cobalt_background(self):
        # 2026-07-15 사용자 요청: "오늘 한국장 도박사(예측시장) 의견" 제목 글자를
        # 2배 크기(기존 17px -> 34px), 붉은색, 배경은 연한 코발트 블루로.
        # st.expander는 label에 HTML을 못 써서 key로 범위를 좁혀 CSS로 덮어썼다 -
        # 그 key와 CSS 규칙이 실제로 있는지, KR/US 둘 다 고유한 key를 쓰는지 고정한다.
        self.assertIn('key=f"{prefix}_bookmaker_expander"', SOURCE)
        self.assertIn(".st-key-{prefix}_bookmaker_expander", SOURCE)
        self.assertIn("font-size: 34px !important", SOURCE)
        self.assertIn("color: #ef4444 !important", SOURCE)
        self.assertIn("background-color: rgba(0, 71, 171, 0.16) !important", SOURCE)
        self.assertIn("prefix = market.lower()", SOURCE)


if __name__ == "__main__":
    unittest.main()

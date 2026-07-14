import ast
import math
from datetime import datetime
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

import naver_market_data


SOURCE = Path("app.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
WANTED = {"_market_overview_status", "_market_overview_direction", "_dedup_market_overview_news", "_market_overview_price_item", "_get_kr_index_intraday", "_get_recent_market_intraday", "_fetch_market_overview"}
NODES = [node for node in TREE.body if isinstance(node, ast.FunctionDef) and node.name in WANTED]
NAMESPACE = {
    "math": math,
    "datetime": datetime,
    "timedelta": __import__("datetime").timedelta,
    "ZoneInfo": ZoneInfo,
    "MARKET_OVERVIEW_MIN_SIGNALS": 3,
    "MARKET_OVERVIEW_PRICE_SPECS": {
        "KR": [("KOSPI·KOSDAQ", ("KOSPI", "^KS11"), ("KOSDAQ", "^KQ11")), ("달러/원", ("달러/원", "KRW=X")), ("반도체", ("SOXX", "SOXX")), ("나스닥100 선물", ("NQ=F", "NQ=F"))],
        "US": [("S&P500·Nasdaq", ("S&P500", "^GSPC")), ("미국 10년물", ("미국 10년물", "^TNX")), ("VIX", ("VIX", "^VIX")), ("반도체", ("SOXX", "SOXX"))],
    },
    "MARKET_OVERVIEW_NEWS_QUERIES": {"KR": ("q1", "q2"), "US": ("q1", "q2")},
    "MARKET_OVERVIEW_NEWS_CONTEXT": {
        "KR": ("코스피", "코스닥", "국내증시", "국내 증시", "증시", "환율", "원달러", "외국인", "기관"),
        "US": ("뉴욕증시", "미국증시", "미국 증시", "나스닥", "S&P500", "연준", "미국 국채금리", "국채금리"),
    },
    "MARKET_OVERVIEW_OTHER_MARKET_TERMS": {
        "KR": ("뉴욕증시", "미국 증시", "나스닥", "일본 증시", "중국 증시", "홍콩 증시", "유럽 증시"),
        "US": ("한국 증시", "코스피", "코스닥", "일본 증시", "중국 증시", "홍콩 증시", "유럽 증시"),
    },
    "MARKET_OVERVIEW_HISTORY_TERMS": ("과거", "역사", "회고", "몇 년 전", "10년 전", "지난해"),
    "_safe_pct_diff": lambda a, b: None if not b else (a - b) / b * 100,
    "_recent_naver_news_items": lambda items: items or [],
    "naver_market_data": naver_market_data,
}
exec(compile(ast.Module(body=NODES, type_ignores=[]), "app.py", "exec"), NAMESPACE)
GET_KR_INDEX_INTRADAY = NAMESPACE["_get_kr_index_intraday"]
GET_RECENT_MARKET_INTRADAY = NAMESPACE["_get_recent_market_intraday"]


class MarketOverviewTests(unittest.TestCase):
    def test_signal_states(self):
        status = NAMESPACE["_market_overview_status"]
        self.assertEqual(status("KR", {"a": 1, "b": 0.5, "c": 0.1})[0], "우호")
        self.assertEqual(status("KR", {"a": 1, "b": -1, "c": 0})[0], "혼조")
        self.assertEqual(status("US", {"a": -1, "b": -0.5, "c": 0.1})[0], "경계")
        self.assertEqual(status("US", {"a": 1, "b": None})[0], "자료 부족")

    def test_dynamic_interpretation_uses_actual_directions(self):
        status, explanation = NAMESPACE["_market_overview_status"](
            "KR",
            {"KOSPI·KOSDAQ": 1.0, "달러/원": 0.5, "반도체": -0.2, "나스닥100 선물": 0.4},
            {
                "KOSPI·KOSDAQ": [1.0, 1.0],
                "달러/원": [-0.5],
                "반도체": [1.0, -1.0],
                "나스닥100 선물": [0.4],
            },
        )
        self.assertEqual(status, "우호")
        self.assertIn("코스피·코스닥 동반 상승", explanation)
        self.assertIn("달러/원 하락", explanation)
        self.assertIn("반도체 ETF 흐름 엇갈림", explanation)
        self.assertNotIn("긍정 신호가 상대적으로 우세", explanation)

    def test_news_dedup_by_url_and_normalized_title(self):
        dedup = NAMESPACE["_dedup_market_overview_news"]
        result = dedup(
            [
                {"title": " 같은 제목 ", "link": "https://example/a", "pub_date": "2026-07-12"},
                {"title": "같은 제목", "link": "https://example/b", "pub_date": "2026-07-11"},
                {"title": "다른 제목", "link": "https://example/a", "pub_date": "2026-07-10"},
                {"title": "새 제목", "link": "https://example/c", "pub_date": "2026-07-09"},
            ]
        )
        self.assertEqual([row["title"] for row in result], ["같은 제목", "새 제목"])

    def test_market_news_filter_prefers_direct_market_context(self):
        dedup = NAMESPACE["_dedup_market_overview_news"]
        result = dedup(
            [
                {"title": "테스트기업 신제품 출시", "link": "https://example/company", "pub_date": "2026-07-12"},
                {"title": "코스피 마감, 외국인 순매수", "link": "https://example/market", "pub_date": "2026-07-11"},
                {"title": "지난해 뉴욕증시 회고", "link": "https://example/history", "pub_date": "2026-07-10"},
            ],
            "KR",
        )
        self.assertEqual([row["title"] for row in result], ["코스피 마감, 외국인 순매수"])

    def test_market_overview_contracts(self):
        self.assertIn('"오늘 한국장 한눈에"', SOURCE)
        self.assertIn('"오늘 미국장 한눈에"', SOURCE)
        self.assertIn('key=button_key', SOURCE)
        self.assertIn('news_data.fetch_naver_news(client_id, client_secret, query, display=10, sort="date")', SOURCE)
        self.assertIn("시장 주요 뉴스 후보", SOURCE)
        self.assertIn("원문 도메인", SOURCE)
        render_source = SOURCE[SOURCE.index("def _render_market_overview"):SOURCE.index("def _get_snapshot_value")]
        for size in ("font-size:26px", "font-size:23px", "font-size:20px", "font-size:19px", "font-size:18px"):
            self.assertIn(size, render_source)
        self.assertIn("#CBD5E1", render_source)
        self.assertIn("-webkit-line-clamp:2", render_source)
        self.assertNotIn("원문 보기", render_source)
        render_source = SOURCE[SOURCE.index("def _render_market_overview"):SOURCE.index("def _get_snapshot_value")]
        self.assertNotIn("실시간", render_source)
        for phrase in ("장중 {item['asof']} 기준", "{item['asof']} 종가 기준", "조회 기준 확인 불가"):
            self.assertIn(phrase, render_source)
        self.assertIn("deepl_translate.translate_market_text_locally", render_source)
        self.assertIn("영어 원문:", render_source)
        self.assertIn("font-size:23px", render_source)
        self.assertIn("font-size:17px", render_source)

    def test_no_market_fetch_before_button(self):
        panel = SOURCE[SOURCE.index("def _render_market_overview"):]
        self.assertLess(panel.index("st.button"), panel.index("_fetch_market_overview"))

    def test_kr_and_us_bookmaker_fetch_both_get_auto_fetch_pending_flag(self):
        # 2026-07-15: 사용자 요청으로 KR·US 둘 다 로그인/탭 진입 후 자동 조회 체인에
        # 도박사 신호를 포함시켰다(prefix별 pending 플래그, {prefix}_bookmaker_fetch).
        panel = SOURCE[SOURCE.index("def _render_market_overview"):SOURCE.index("def _get_snapshot_value")]
        button = 'st.button("오늘 도박사 신호 불러오기(Polymarket/Kalshi)"'
        self.assertLess(panel.index(button), panel.index("_cached_fetch_bookmaker_snapshot()"))
        self.assertIn('st.session_state.pop(f"{prefix}_bookmaker_auto_fetch_pending"', panel)
        cached_fetch = SOURCE[
            SOURCE.index("def _cached_fetch_bookmaker_snapshot"):
            SOURCE.index("def _cached_translate_bookmaker_texts")
        ]
        self.assertIn("bookmaker_data.fetch_bookmaker_snapshot()", cached_fetch)

    def test_kr_stage2_arms_bookmaker_auto_fetch_pending_flag(self):
        stage2 = SOURCE[
            SOURCE.index('if not st.session_state.get("kr_auto_run_stage2_done")'):
            SOURCE.index('_render_market_overview("KR")')
        ]
        self.assertIn('st.session_state["kr_bookmaker_auto_fetch_pending"] = True', stage2)
        self.assertIn('st.session_state["kr_theme_auto_fetch_pending"] = True', stage2)

    def test_login_followup_reruns_restore_three_kr_auto_actions(self):
        self.assertIn("로그인 후 한국장 자료·종목 판단·테마 참고판을 자동으로 불러오는 중입니다.", SOURCE)
        self.assertIn("로그인 후 한국장 자료를 자동으로 불러왔습니다.", SOURCE)
        tab_start = SOURCE.index("def _render_tab_kr():")
        panel_start = SOURCE.index('_render_market_overview("KR")', tab_start)
        tab_prelude = SOURCE[tab_start:panel_start]
        self.assertIn("not _login_transition_pending", tab_prelude)
        self.assertIn("kr_auto_run_stage1_done", tab_prelude)
        self.assertIn("kr_auto_run_stage2_done", tab_prelude)
        self.assertIn("KR_AUTO_RUN_VERSION", tab_prelude)
        for required_call in (
            "get_top_kr_stocks_by_amount(",
            '_fetch_market_overview("KR")',
            "run_kr_mood_auto_check()",
            "run_kr_snapshot_auto_fill()",
            'st.session_state["kr_theme_auto_fetch_pending"] = True',
        ):
            self.assertIn(required_call, tab_prelude)

        login_start = SOURCE.index('if not st.session_state.get("authenticated"):')
        login_source = SOURCE[login_start:SOURCE.index("st.stop()", login_start)]
        self.assertIn('st.session_state.pop(_kr_auto_key, None)', login_source)

    def test_intraday_failure_falls_back_to_dated_close(self):
        class Price:
            intraday_calls = []

            def get_snapshot_defaults(self, ticker, completed_only=False):
                return {
                    "ok": True,
                    "current": 101.0,
                    "prev_close": 100.0,
                    "as_of_date": "2026-07-10",
                }

            def get_intraday_last(self, ticker):
                self.intraday_calls.append(ticker)
                return {"ok": False, "error": "empty"}

            def get_ohlc_history_for_chart(self, *args):
                return None

        class Secrets:
            def get(self, key):
                return None

        price = Price()
        NAMESPACE["price_data"] = price
        NAMESPACE["_get_kr_index_intraday"] = price.get_intraday_last
        NAMESPACE["st"] = type("StreamlitStub", (), {"secrets": Secrets()})()

        result = NAMESPACE["_fetch_market_overview"]("KR")

        items = result["price_cards"][0]["items"]
        self.assertEqual(price.intraday_calls, ["^KS11", "^KQ11", "KRW=X", "SOXX", "NQ=F"])
        self.assertTrue(all(item["data_kind"] == "daily_close" for item in items))
        self.assertTrue(all(item["asof"] == "2026-07-10" for item in items))

    def test_kis_is_preferred_and_yahoo_is_not_called(self):
        class Kis:
            def get_index_snapshot(self, ticker, app_key, app_secret):
                return {"ok": True, "current": 102.0, "prev_close": 100.0, "source": "한국투자증권"}

        class Price:
            calls = []

            def get_intraday_last(self, ticker):
                self.calls.append(ticker)
                return {"ok": False}

        class Naver:
            calls = []

            def get_index_snapshot(self, ticker):
                self.calls.append(ticker)
                return {"ok": False}

        class Secrets:
            def get(self, key):
                return "configured"

        price = Price()
        naver = Naver()
        NAMESPACE["kis_market_data"] = Kis()
        NAMESPACE["naver_market_data"] = naver
        NAMESPACE["price_data"] = price
        NAMESPACE["st"] = type("StreamlitStub", (), {"secrets": Secrets()})()

        result = GET_KR_INDEX_INTRADAY("^KS11")

        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "한국투자증권")
        self.assertEqual(naver.calls, [])
        self.assertEqual(price.calls, [])

    def test_naver_is_used_before_yahoo_when_kis_is_unavailable(self):
        class Kis:
            def get_index_snapshot(self, ticker, app_key, app_secret):
                return {"ok": False, "error": "no key"}

        class Naver:
            def get_index_snapshot(self, ticker):
                return {
                    "ok": True,
                    "current": 101.5,
                    "prev_close": 100.0,
                    "as_of_time": "11:26",
                    "source": "네이버 금융 현재지수",
                }

        class Price:
            calls = []

            def get_intraday_last(self, ticker):
                self.calls.append(ticker)
                return {"ok": False}

        class Secrets:
            def get(self, key):
                return None

        price = Price()
        NAMESPACE["kis_market_data"] = Kis()
        NAMESPACE["naver_market_data"] = Naver()
        NAMESPACE["price_data"] = price
        NAMESPACE["st"] = type("StreamlitStub", (), {"secrets": Secrets()})()

        result = GET_KR_INDEX_INTRADAY("^KS11")

        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "네이버 금융 현재지수")
        self.assertEqual(result["as_of_time"], "11:26")
        self.assertEqual(price.calls, [])

    def test_yahoo_fallback_is_labeled_as_delayed(self):
        class Kis:
            def get_index_snapshot(self, ticker, app_key, app_secret):
                return {"ok": False, "error": "no key"}

        class Price:
            def get_intraday_last(self, ticker):
                return {"ok": True, "current": 101.0, "prev_close": 100.0}

        class Naver:
            def get_index_snapshot(self, ticker):
                return {"ok": False, "error": "network"}

        class Secrets:
            def get(self, key):
                return None

        NAMESPACE["kis_market_data"] = Kis()
        NAMESPACE["naver_market_data"] = Naver()
        NAMESPACE["price_data"] = Price()
        NAMESPACE["st"] = type("StreamlitStub", (), {"secrets": Secrets()})()

        result = GET_KR_INDEX_INTRADAY("^KS11")

        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "Yahoo 1분봉(지연 가능)")

    def test_recent_intraday_accepts_current_fx_and_nq_but_rejects_closed_etf(self):
        class Price:
            rows = {
                "KRW=X": ("11:46", 1492.08, 1497.02),
                "NQ=F": ("11:36", 29383.0, 29475.75),
                "SOXX": ("04:59", 553.16, 581.34),
            }

            def get_intraday_last(self, ticker):
                as_of_time, current, previous = self.rows[ticker]
                return {
                    "ok": True,
                    "current": current,
                    "prev_close": previous,
                    "as_of_date": "2026-07-14",
                    "as_of_time": as_of_time,
                    "data_kind": "intraday",
                }

        NAMESPACE["price_data"] = Price()
        now = datetime(2026, 7, 14, 11, 46, tzinfo=ZoneInfo("Asia/Seoul"))

        fx = GET_RECENT_MARKET_INTRADAY("KRW=X", now=now)
        nq = GET_RECENT_MARKET_INTRADAY("NQ=F", now=now)
        soxx = GET_RECENT_MARKET_INTRADAY("SOXX", now=now)

        self.assertTrue(fx["ok"])
        self.assertTrue(nq["ok"])
        self.assertEqual(nq["as_of_time"], "11:36")
        self.assertEqual(nq["source"], "Yahoo 1분봉(지연 가능)")
        self.assertFalse(soxx["ok"])

    def test_nq_older_than_fifteen_minutes_is_not_labeled_intraday(self):
        class Price:
            def get_intraday_last(self, ticker):
                return {
                    "ok": True,
                    "current": 29383.0,
                    "prev_close": 29475.75,
                    "as_of_date": "2026-07-14",
                    "as_of_time": "11:30",
                }

        NAMESPACE["price_data"] = Price()
        result = GET_RECENT_MARKET_INTRADAY(
            "NQ=F", now=datetime(2026, 7, 14, 11, 46, tzinfo=ZoneInfo("Asia/Seoul"))
        )
        self.assertFalse(result["ok"])

    def test_news_caption_distinguishes_query_time_from_publication_time(self):
        render_source = SOURCE[SOURCE.index("def _render_market_overview"):SOURCE.index("def _get_snapshot_value")]
        self.assertIn("뉴스는 자동 반복 갱신이 아닌 조회 시점의 검색 결과", render_source)
        self.assertIn("발행시각은 한국시간 기준", render_source)

    def test_today_intraday_replaces_only_kr_index_close(self):
        class Price:
            def get_snapshot_defaults(self, ticker, completed_only=False):
                return {
                    "ok": True,
                    "current": 101.0,
                    "prev_close": 100.0,
                    "as_of_date": "2026-07-10",
                }

            def get_intraday_last(self, ticker):
                return {
                    "ok": True,
                    "current": 102.0,
                    "prev_close": 100.0,
                    "prev_close_as_of_date": "2026-07-13",
                    "asof": "12:17",
                    "as_of_time": "12:17",
                    "as_of_date": "2026-07-14",
                    "data_kind": "intraday",
                }

            def get_ohlc_history_for_chart(self, *args):
                return None

        class Secrets:
            def get(self, key):
                return None

        NAMESPACE["price_data"] = Price()
        NAMESPACE["_get_kr_index_intraday"] = NAMESPACE["price_data"].get_intraday_last
        NAMESPACE["st"] = type("StreamlitStub", (), {"secrets": Secrets()})()

        result = NAMESPACE["_fetch_market_overview"]("KR")

        items = result["price_cards"][0]["items"]
        self.assertTrue(all(item["data_kind"] == "intraday" for item in items))
        self.assertTrue(all(item["as_of_date"] == "2026-07-14" for item in items))
        self.assertTrue(all(item["as_of_time"] == "12:17" for item in items))
        self.assertTrue(all(item["change_pct"] == 2.0 for item in items))

    def test_kis_intraday_does_not_depend_on_yahoo_daily_success(self):
        class Price:
            daily_calls = []

            def get_snapshot_defaults(self, ticker, completed_only=False):
                self.daily_calls.append(ticker)
                return {"ok": False, "error": "yahoo down"}

            def get_ohlc_history_for_chart(self, *args):
                return None

        class Secrets:
            def get(self, key):
                return None

        price = Price()
        NAMESPACE["price_data"] = price
        NAMESPACE["_get_kr_index_intraday"] = lambda ticker: {
            "ok": True,
            "current": 102.0,
            "prev_close": 100.0,
            "as_of_time": "11:09",
            "as_of_date": "2026-07-14",
            "source": "한국투자증권",
        }
        NAMESPACE["st"] = type("StreamlitStub", (), {"secrets": Secrets()})()

        result = NAMESPACE["_fetch_market_overview"]("KR")

        items = result["price_cards"][0]["items"]
        self.assertTrue(all(item["status"] == "정상" for item in items))
        self.assertTrue(all(item["source"] == "한국투자증권" for item in items))
        self.assertNotIn("^KS11", price.daily_calls)
        self.assertNotIn("^KQ11", price.daily_calls)

    def test_price_lookup_failure_has_unknown_reference_time(self):
        class Price:
            def get_snapshot_defaults(self, ticker, completed_only=False):
                return {"ok": False, "error": "network"}

        class Secrets:
            def get(self, key):
                return None

        NAMESPACE["price_data"] = Price()
        NAMESPACE["_get_kr_index_intraday"] = lambda ticker: {"ok": False, "error": "network"}
        NAMESPACE["st"] = type("StreamlitStub", (), {"secrets": Secrets()})()

        result = NAMESPACE["_fetch_market_overview"]("KR")

        items = result["price_cards"][0]["items"]
        self.assertTrue(all(item["status"] == "확인 불가" for item in items))
        self.assertTrue(all(item["data_kind"] == "unknown" for item in items))
        self.assertTrue(all(item["asof"] is None for item in items))

    def test_partial_price_failure_does_not_drop_news(self):
        class Price:
            def get_snapshot_defaults(self, ticker):
                if ticker == "^TNX":
                    raise TimeoutError("mock")
                return {"ok": True, "current": 101.0, "prev_close": 100.0}

        class News:
            def __init__(self):
                self.calls = []

            def fetch_naver_news(self, client_id, client_secret, query, **kwargs):
                self.calls.append(query)
                return {"status": "정상", "data": [{"title": f"미국 증시 {query}", "link": f"https://example/{query}", "pub_date": "2026-07-12"}]}

        class Secrets:
            def get(self, key):
                return "configured"

        news = News()
        NAMESPACE["price_data"] = Price()
        NAMESPACE["news_data"] = news
        NAMESPACE["st"] = type("StreamlitStub", (), {"secrets": Secrets()})()
        result = NAMESPACE["_fetch_market_overview"]("US")
        self.assertEqual(len(news.calls), 2)
        self.assertEqual(len(result["news"]), 2)
        self.assertEqual(result["price_cards"][1]["items"][0]["status"], "확인 불가")


if __name__ == "__main__":
    unittest.main()

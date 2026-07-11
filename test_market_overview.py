import ast
import math
from datetime import datetime
import unittest
from pathlib import Path


SOURCE = Path("app.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
WANTED = {"_market_overview_status", "_market_overview_direction", "_dedup_market_overview_news", "_market_overview_price_item", "_fetch_market_overview"}
NODES = [node for node in TREE.body if isinstance(node, ast.FunctionDef) and node.name in WANTED]
NAMESPACE = {
    "math": math,
    "datetime": datetime,
    "MARKET_OVERVIEW_MIN_SIGNALS": 3,
    "MARKET_OVERVIEW_PRICE_SPECS": {
        "KR": [("KOSPI·KOSDAQ", ("KOSPI", "^KS11")), ("달러/원", ("달러/원", "KRW=X")), ("반도체", ("SOXX", "SOXX")), ("나스닥100 선물", ("NQ=F", "NQ=F"))],
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
}
exec(compile(ast.Module(body=NODES, type_ignores=[]), "app.py", "exec"), NAMESPACE)


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
        self.assertNotIn("실시간", render_source)

    def test_no_market_fetch_before_button(self):
        panel = SOURCE[SOURCE.index("def _render_market_overview"):]
        self.assertLess(panel.index("st.button"), panel.index("_fetch_market_overview"))

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

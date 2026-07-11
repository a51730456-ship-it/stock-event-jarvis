import json
import unittest
import urllib.error

import news_data as n


def response(payload, status=200):
    class Response:
        def read(self):
            return payload
    Response.status = status
    return Response()


class NewsDataTests(unittest.TestCase):
    def test_materiality_categories_and_title_priority(self):
        cases = [
            ({"title": "기업 실적 발표", "description": ""}, "실적"),
            ({"title": "기업 소식", "description": "영업이익 전망 공개"}, "실적"),
            ({"title": "대형 공급계약 체결", "description": ""}, "수주·계약"),
            ({"title": "신규 투자 및 인수", "description": ""}, "투자·M&A"),
            ({"title": "배당·자사주 정책", "description": ""}, "주주환원·자본"),
            ({"title": "당국 조사 및 소송", "description": ""}, "규제·법적위험"),
            ({"title": "신제품 출시와 특허", "description": ""}, "제품·기술"),
        ]
        for item, category in cases:
            result = n.classify_news_materiality(item, "테스트기업", "000000")
            self.assertEqual(result["level"], "중요 재료")
            self.assertEqual(result["category"], category)
            self.assertTrue(result["matched_keywords"])
        title_first = n.classify_news_materiality({"title": "매출 확대", "description": "대형 수주"}, "기업")
        self.assertEqual(title_first["category"], "실적")

    def test_materiality_general_mentions_and_neutral_reason(self):
        for item in (
            {"title": "삼성전자 언급 ETF 동향", "description": "시장 순위와 정치인 방문"},
            {"title": "테스트기업 관련 시장 공급 동향", "description": "업계 일반 뉴스"},
            {"title": "종목 000000 오늘 거래량 순위", "description": ""},
        ):
            result = n.classify_news_materiality(item, "테스트기업", "000000")
            self.assertEqual(result["level"], "일반 참고")
            self.assertEqual(result["category"], "기타")
        result = n.classify_news_materiality({"title": "기업 실적 발표", "description": "흑자 전환"}, "기업")
        self.assertIn("실적", result["matched_keywords"])
        self.assertIn("제목", result["reason"])
        self.assertNotIn("긍정", result["reason"])
        self.assertNotIn("부정", result["reason"])

    def test_materiality_does_not_mutate_original_news_item(self):
        item = {"title": "기업 수주 발표", "description": "원본 설명", "link": "https://example"}
        before = dict(item)
        n.classify_news_materiality(item, "기업", "000000")
        self.assertEqual(item, before)

    def test_normal_two_items_and_order(self):
        payload = {"items": [{"title": "A", "originallink": "https://a", "link": "https://n/a", "description": "D", "pubDate": "Tue, 11 Jul 2026 10:00:00 +0900"}, {"title": "B", "link": "https://b"}]}
        result = n.fetch_naver_news("ID", "SECRET", "삼성", http_get=lambda *a, **k: response(json.dumps(payload).encode()))
        self.assertEqual(result["status"], "정상")
        self.assertEqual([x["title"] for x in result["data"]], ["A", "B"])

    def test_empty_and_html_entity_normalization(self):
        payload = {"items": [{"title": " <b>A &amp; B</b> ", "description": " <p>D&nbsp;now</p> ", "link": "u", "pubDate": "bad"}]}
        result = n.fetch_naver_news("ID", "SECRET", "q", http_get=lambda *a, **k: response(json.dumps(payload).encode()))
        self.assertEqual((result["data"][0]["title"], result["data"][0]["description"]), ("A & B", "D\xa0now"))
        self.assertEqual(result["data"][0]["pub_date"], "bad")
        empty = n.fetch_naver_news("ID", "SECRET", "q", http_get=lambda *a, **k: response(b'{"items":[]}'))
        self.assertEqual(empty["status"], "데이터 없음")

    def test_dedup_prefers_originallink_then_link_and_date(self):
        payload = {"items": [{"originallink": "same", "link": "n1", "title": "1", "pubDate": "Tue, 11 Jul 2026 10:00:00 +0900"}, {"originallink": "same", "link": "n2", "title": "2"}, {"link": "n1", "title": "3"}, {"link": "n3", "title": "4"}]}
        result = n.fetch_naver_news("ID", "SECRET", "q", http_get=lambda *a, **k: response(json.dumps(payload).encode()))
        self.assertEqual([x["title"] for x in result["data"]], ["1", "3", "4"])
        self.assertEqual(result["data"][0]["pub_date"], "2026-07-11 01:00:00")

    def test_validation(self):
        get = lambda *a, **k: self.fail("HTTP called")
        for args in (("", "S", "q"), ("I", "", "q"), ("I", "S", "")):
            self.assertIn(n.fetch_naver_news(*args, http_get=get)["status"], ("인증 오류", "잘못된 요청"))
        for value in (0, 101):
            self.assertEqual(n.fetch_naver_news("I", "S", "q", display=value, http_get=get)["status"], "잘못된 요청")
        for value in (0, 1001):
            self.assertEqual(n.fetch_naver_news("I", "S", "q", start=value, http_get=get)["status"], "잘못된 요청")
        self.assertEqual(n.fetch_naver_news("I", "S", "q", sort="bad", http_get=get)["status"], "잘못된 요청")

    def test_http_statuses_and_json_error(self):
        for code, expected in ((401, "인증 오류"), (429, "요청 제한"), (400, "잘못된 요청"), (500, "서버 오류")):
            self.assertEqual(n.fetch_naver_news("I", "S", "q", http_get=lambda *a, c=code, **k: response(b"{}", c))["status"], expected)
        self.assertEqual(n.fetch_naver_news("I", "S", "q", http_get=lambda *a, **k: response(b"bad"))["status"], "응답 오류")

    def test_timeout_network_auth_headers_and_no_secret_leak(self):
        seen = {}
        def get(url, **kwargs):
            seen.update(kwargs)
            raise TimeoutError("ID SECRET should not escape")
        result = n.fetch_naver_news("ID", "SECRET", "q", display=2, start=3, sort="sim", http_get=get)
        self.assertEqual(result["status"], "네트워크 오류")
        self.assertEqual(seen["timeout"], n.TIMEOUT)
        self.assertEqual(seen["headers"], {"X-Naver-Client-Id": "ID", "X-Naver-Client-Secret": "SECRET"})
        self.assertNotIn("ID", repr(result))
        self.assertNotIn("SECRET", repr(result))
        self.assertNotIn("ID", result["message"])
        self.assertNotIn("SECRET", result["message"])

    def test_network_error_and_unexpected_error_are_statuses(self):
        result = n.fetch_naver_news("I", "S", "q", http_get=lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("offline")))
        self.assertEqual(result["status"], "네트워크 오류")
        result = n.fetch_naver_news("I", "S", "q", http_get=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("secret")))
        self.assertEqual(result["status"], "응답 오류")
        self.assertNotIn("secret", repr(result))


if __name__ == "__main__":
    unittest.main()

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

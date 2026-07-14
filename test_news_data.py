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
            ({"title": "테스트기업 실적 발표", "description": ""}, "실적"),
            ({"title": "테스트기업 소식", "description": "테스트기업 영업이익 전망 공개"}, "실적"),
            ({"title": "테스트기업 대형 공급계약 체결", "description": ""}, "수주·계약"),
            ({"title": "테스트기업 신규 투자 및 인수 결정", "description": ""}, "투자·M&A"),
            ({"title": "테스트기업 배당 결정·자사주 소각", "description": ""}, "주주환원·자본"),
            ({"title": "테스트기업 당국 조사 및 소송", "description": ""}, "규제·법적위험"),
            ({"title": "테스트기업 신제품 출시와 특허 취득", "description": ""}, "제품·기술"),
        ]
        for item, category in cases:
            result = n.classify_news_materiality(item, "테스트기업", "000000")
            self.assertEqual(result["level"], "기업 직접 재료 후보")
            self.assertEqual(result["category"], category)
            self.assertEqual(result["market_reaction"], "시장 반응 확인 전")
            self.assertTrue(result["matched_keywords"])
        title_first = n.classify_news_materiality({"title": "기업 매출 증가", "description": "기업 대형 수주"}, "기업")
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
        self.assertIn("실적 발표", result["matched_keywords"])
        self.assertIn("제목", result["reason"])
        self.assertNotIn("긍정", result["reason"])
        self.assertNotIn("부정", result["reason"])

    def test_real_false_positive_cases_are_general(self):
        cases = [
            ("테슬라, 스페이스X 제외한 ETF 뺏다…'반 머스크' 투자상품 등장", "테슬라", "테슬라 투자 단어가 포함된 설명"),
            ("장동혁 일몰법·성역법 헌법소원 할 것", "삼성전자", "삼성전자와 SK하이닉스 투자 논쟁이 이어졌다"),
            ("테슬라 주가 전망과 차트 분석", "테슬라", "목표주가와 차트 흐름 전망"),
            ("스페이스X IPO, 테슬라와 비교되나", "테슬라", "스페이스X가 주인공인 IPO 기사"),
        ]
        for title, company, description in cases:
            result = n.classify_news_materiality({"title": title, "description": description}, company)
            self.assertEqual(result["level"], "일반 참고", title)

    def test_direct_company_events_survive_exclusion_words(self):
        result = n.classify_news_materiality({"title": "삼성전자, ETF 운용사 인수 결정", "description": ""}, "삼성전자")
        self.assertEqual(result["level"], "일반 참고")
        result = n.classify_news_materiality({"title": "삼성전자 소식", "description": "삼성전자 시설투자 결정 발표"}, "삼성전자")
        self.assertEqual((result["level"], result["category"]), ("기업 직접 재료 후보", "투자·M&A"))
        result = n.classify_news_materiality({"title": "삼성전자 소식", "description": "삼성전자 투자 확대 전망"}, "삼성전자")
        self.assertEqual(result["level"], "일반 참고")

    def test_materiality_does_not_mutate_original_news_item(self):
        item = {"title": "기업 수주 발표", "description": "원본 설명", "link": "https://example"}
        before = dict(item)
        n.classify_news_materiality(item, "기업", "000000")
        self.assertEqual(item, before)

    def test_three_stage_labels_and_false_positive_subjects(self):
        direct = n.classify_news_materiality(
            {"title": "테스트기업 공급계약 체결", "description": ""}, "테스트기업", "000000"
        )
        self.assertEqual(
            (direct["level"], direct["category"], direct["market_reaction"]),
            ("기업 직접 재료 후보", "수주·계약", "시장 반응 확인 전"),
        )
        for item in (
            {"title": "정치인 발언과 시장 공급 동향", "description": "테스트기업 언급"},
            {"title": "다른회사 대형 수주", "description": "테스트기업과 비교되는 업계 기사"},
            {"title": "테스트기업 관련 시장 수주 동향", "description": ""},
        ):
            result = n.classify_news_materiality(item, "테스트기업", "000000")
            self.assertEqual(result["level"], "일반 참고")
            self.assertEqual(result["market_reaction"], "시장 반응 확인 전")

    def test_all_event_categories_have_pending_market_reaction(self):
        for category, phrase in (
            ("실적", "테스트기업 실적 발표"),
            ("수주·계약", "테스트기업 공급계약 체결"),
            ("투자·M&A", "테스트기업 시설투자 결정"),
            ("주주환원·자본", "테스트기업 배당 결정"),
            ("규제·법적위험", "테스트기업 당국 조사"),
            ("제품·기술", "테스트기업 신제품 출시"),
        ):
            result = n.classify_news_materiality({"title": phrase}, "테스트기업")
            self.assertEqual(result["category"], category)
            self.assertEqual(result["market_reaction"], "시장 반응 확인 전")

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
        self.assertEqual(result["data"][0]["pub_date"], "2026-07-11 10:00:00")

    def test_publication_time_is_displayed_in_seoul_time(self):
        payload = {
            "items": [
                {
                    "title": "시장 뉴스",
                    "link": "https://example/news",
                    "pubDate": "Tue, 14 Jul 2026 02:38:00 +0000",
                }
            ]
        }
        result = n.fetch_naver_news(
            "ID", "SECRET", "코스피", http_get=lambda *a, **k: response(json.dumps(payload).encode())
        )
        self.assertEqual(result["data"][0]["pub_date"], "2026-07-14 11:38:00")

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

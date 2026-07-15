import unittest
from unittest.mock import patch, MagicMock

import deepl_translate as dt


def _response(status_code=200, json_payload=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_payload or {}
    return resp


class DeeplTranslateTests(unittest.TestCase):
    def test_local_finance_title_fallbacks(self):
        self.assertEqual(dt.translate_market_title_locally("Fed Decision in July?"), "7월 연준 금리 결정")
        self.assertEqual(
            dt.translate_market_title_locally("What will WTI Crude Oil (WTI) hit in July 2026?"),
            "2026년 7월 WTI 원유 가격은 어디까지 오를까?",
        )
        self.assertIsNone(dt.translate_market_title_locally("Unrecognized entertainment event"))

    def test_local_finance_question_fallbacks(self):
        self.assertEqual(
            dt.translate_market_text_locally(
                "Will the Fed increase interest rates by 25 bps after the July 2026 meeting?"
            ),
            "2026년 7월 연준 회의 후 기준금리가 25bp 인상될까?",
        )
        self.assertEqual(
            dt.translate_market_text_locally("Will WTI Crude Oil (WTI) hit (HIGH) $80 in July?"),
            "7월 WTI 원유 가격이 80달러 이상 오를까?",
        )
        self.assertEqual(
            dt.translate_market_text_locally(
                "Will core CPI inflation exceed headline CPI inflation in June 2026?"
            ),
            "2026년 6월 근원 CPI 상승률이 전체 CPI 상승률을 웃돌까?",
        )
        self.assertEqual(
            dt.translate_market_text_locally("Will no Fed rate cuts happen in 2026?"),
            "2026년 연준이 금리를 한 번도 인하하지 않을까?",
        )
        self.assertEqual(
            dt.translate_market_text_locally(
                "Will NVIDIA be the largest company in the world by market cap on July 31?"
            ),
            "7월 31일 시가총액 세계 1위 기업이 NVIDIA일까?",
        )

    @patch("deepl_translate.requests.post")
    def test_empty_texts_makes_no_call(self, mock_post):
        result = dt.translate_texts_to_ko([], "some-key")
        self.assertTrue(result["ok"])
        self.assertEqual(result["translations"], {})
        mock_post.assert_not_called()

    @patch("deepl_translate.requests.post")
    def test_missing_api_key_makes_no_call(self, mock_post):
        result = dt.translate_texts_to_ko(["Will CPI reach 4%?"], None)
        self.assertFalse(result["ok"])
        self.assertIn("키", result["error"])
        mock_post.assert_not_called()

    @patch("deepl_translate.requests.post")
    def test_missing_api_key_empty_string_makes_no_call(self, mock_post):
        result = dt.translate_texts_to_ko(["Will CPI reach 4%?"], "")
        self.assertFalse(result["ok"])
        mock_post.assert_not_called()

    @patch("deepl_translate.requests.post")
    def test_success_maps_original_to_translation(self, mock_post):
        mock_post.return_value = _response(
            200, {"translations": [{"text": "CPI가 올해 4%에 도달할까요?"}]}
        )
        result = dt.translate_texts_to_ko(["Will CPI reach 4%?"], "fake-key")
        self.assertTrue(result["ok"])
        self.assertEqual(
            result["translations"]["Will CPI reach 4%?"], "CPI가 올해 4%에 도달할까요?"
        )
        mock_post.assert_called_once()

    @patch("deepl_translate.requests.post")
    def test_duplicate_titles_are_sent_once(self, mock_post):
        mock_post.return_value = _response(200, {"translations": [{"text": "연준 결정"}]})

        result = dt.translate_texts_to_ko(["Fed decision", "Fed decision"], "fake-key")

        self.assertTrue(result["ok"])
        self.assertEqual(result["translations"], {"Fed decision": "연준 결정"})
        self.assertEqual(mock_post.call_args.kwargs["data"]["text"], ["Fed decision"])

    @patch("deepl_translate.requests.post")
    def test_non_200_returns_generic_error_no_raw_leak(self, mock_post):
        mock_post.return_value = _response(456, {})
        result = dt.translate_texts_to_ko(["hello"], "super-secret-key-abc123")
        self.assertFalse(result["ok"])
        self.assertNotIn("super-secret-key-abc123", result["error"])
        self.assertNotIn("456", result["error"])  # raw status code not required to leak

    @patch("deepl_translate.requests.post")
    def test_request_exception_does_not_leak_key(self, mock_post):
        mock_post.side_effect = Exception("connection failed for key=super-secret-key-abc123")
        result = dt.translate_texts_to_ko(["hello"], "super-secret-key-abc123")
        self.assertFalse(result["ok"])
        self.assertNotIn("super-secret-key-abc123", result["error"])
        self.assertNotIn("key=", result["error"])

    @patch("deepl_translate.requests.post")
    def test_mismatched_translation_count_is_treated_as_failure(self, mock_post):
        mock_post.return_value = _response(200, {"translations": [{"text": "only one"}]})
        result = dt.translate_texts_to_ko(["hello", "world"], "fake-key")
        self.assertFalse(result["ok"])
        self.assertEqual(result["translations"], {})

    @patch("deepl_translate.requests.post")
    def test_empty_translation_item_is_treated_as_failure(self, mock_post):
        mock_post.return_value = _response(200, {"translations": [{"text": ""}]})

        result = dt.translate_texts_to_ko(["hello"], "fake-key")

        self.assertFalse(result["ok"])
        self.assertEqual(result["translations"], {})

    @patch("deepl_translate.requests.post")
    def test_over_forty_texts_are_split_into_multiple_requests(self, mock_post):
        # DeepL API는 요청당 text 50개 제한 — 예전엔 전체를 한 번에 보내다 한도 초과로
        # 요청 전체가 거부돼 화면이 통째로 영어로 남았다(2026-07-15 실사용 확인).
        texts = [f"sentence {i}" for i in range(90)]

        def post_side_effect(url, data=None, timeout=None):
            batch = data["text"]
            self.assertLessEqual(len(batch), dt.MAX_TEXTS_PER_REQUEST)
            return _response(200, {"translations": [{"text": f"ko:{t}"} for t in batch]})

        mock_post.side_effect = post_side_effect

        result = dt.translate_texts_to_ko(texts, "fake-key")

        self.assertTrue(result["ok"])
        self.assertIsNone(result["error"])
        self.assertEqual(len(result["translations"]), 90)
        self.assertEqual(result["translations"]["sentence 0"], "ko:sentence 0")
        self.assertEqual(mock_post.call_count, 3)

    @patch("deepl_translate.requests.post")
    def test_one_failed_batch_keeps_other_batches_translations(self, mock_post):
        texts = [f"sentence {i}" for i in range(80)]
        call_index = {"n": 0}

        def post_side_effect(url, data=None, timeout=None):
            call_index["n"] += 1
            if call_index["n"] == 2:
                return _response(456, {})  # 두 번째 묶음만 한도 초과로 거부
            batch = data["text"]
            return _response(200, {"translations": [{"text": f"ko:{t}"} for t in batch]})

        mock_post.side_effect = post_side_effect

        result = dt.translate_texts_to_ko(texts, "fake-key")

        self.assertTrue(result["ok"])
        self.assertEqual(len(result["translations"]), 40)
        self.assertIn("일부 문장 번역 실패", result["error"])

    def test_new_kalshi_local_title_rules(self):
        self.assertEqual(
            dt.translate_market_text_locally("Inflation surge in 2026?"),
            "2026년 인플레이션 급등 가능성",
        )
        self.assertEqual(
            dt.translate_market_text_locally("Who will dissent at the July 2026 FOMC meeting?"),
            "2026년 7월 FOMC 회의에서 반대표를 던질 위원은?",
        )

    @patch("deepl_translate.requests.post")
    def test_call_uses_post_body_not_query_string(self, mock_post):
        mock_post.return_value = _response(200, {"translations": [{"text": "안녕"}]})
        dt.translate_texts_to_ko(["hi"], "fake-key")
        _, kwargs = mock_post.call_args
        self.assertIn("data", kwargs)
        self.assertEqual(kwargs["data"]["auth_key"], "fake-key")
        # auth_key must not appear in the URL (first positional arg / url kwarg)
        called_url = mock_post.call_args[0][0] if mock_post.call_args[0] else kwargs.get("url")
        self.assertNotIn("fake-key", called_url or "")


if __name__ == "__main__":
    unittest.main()

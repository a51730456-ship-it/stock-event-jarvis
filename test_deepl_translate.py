import unittest
from unittest.mock import patch, MagicMock

import deepl_translate as dt


def _response(status_code=200, json_payload=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_payload or {}
    return resp


class DeeplTranslateTests(unittest.TestCase):
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

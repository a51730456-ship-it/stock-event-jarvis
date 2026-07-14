import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import kis_market_data


SEOUL = ZoneInfo("Asia/Seoul")


class KisMarketDataTests(unittest.TestCase):
    def setUp(self):
        kis_market_data._clear_token_cache_for_tests()

    def test_missing_keys_do_not_make_external_request(self):
        calls = []
        result = kis_market_data.get_index_snapshot(
            "^KS11",
            "",
            "",
            now=datetime(2026, 7, 14, 10, 0, tzinfo=SEOUL),
            request_json=lambda *args, **kwargs: calls.append((args, kwargs)),
        )
        self.assertFalse(result["ok"])
        self.assertEqual(calls, [])

    def test_outside_regular_session_does_not_make_external_request(self):
        calls = []
        result = kis_market_data.get_index_snapshot(
            "^KS11",
            "key",
            "secret",
            now=datetime(2026, 7, 14, 8, 59, tzinfo=SEOUL),
            request_json=lambda *args, **kwargs: calls.append((args, kwargs)),
        )
        self.assertFalse(result["ok"])
        self.assertEqual(calls, [])

    def test_kospi_snapshot_uses_official_endpoint_and_fields(self):
        calls = []

        def request_json(method, url, **kwargs):
            calls.append((method, url, kwargs))
            if url.endswith("/oauth2/tokenP"):
                return {"access_token": "mock-token", "expires_in": 3600}
            return {
                "rt_cd": "0",
                "output": {
                    "bstp_nmix_prpr": "6812.47",
                    "bstp_nmix_prdy_ctrt": "2.39",
                },
            }

        result = kis_market_data.get_index_snapshot(
            "^KS11",
            "key",
            "secret",
            now=datetime(2026, 7, 14, 10, 4, tzinfo=SEOUL),
            request_json=request_json,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["current"], 6812.47)
        self.assertAlmostEqual(result["change_pct"], 2.39)
        self.assertEqual(result["as_of_time"], "10:04")
        self.assertEqual(result["source"], "한국투자증권")
        self.assertIn("FID_INPUT_ISCD=0001", calls[1][1])
        self.assertEqual(calls[1][2]["headers"]["tr_id"], "FHPUP02100000")
        self.assertNotIn("주문", str(calls))

    def test_kosdaq_code_and_token_are_reused(self):
        calls = []

        def request_json(method, url, **kwargs):
            calls.append((method, url, kwargs))
            if url.endswith("/oauth2/tokenP"):
                return {"access_token": "mock-token", "expires_in": 3600}
            return {
                "rt_cd": "0",
                "output": {"bstp_nmix_prpr": "900.00", "bstp_nmix_prdy_ctrt": "-1.00"},
            }

        now = datetime(2026, 7, 14, 11, 0, tzinfo=SEOUL)
        first = kis_market_data.get_index_snapshot("^KS11", "key", "secret", now=now, request_json=request_json)
        second = kis_market_data.get_index_snapshot("^KQ11", "key", "secret", now=now, request_json=request_json)

        self.assertTrue(first["ok"] and second["ok"])
        self.assertEqual(sum(url.endswith("/oauth2/tokenP") for _, url, _ in calls), 1)
        self.assertIn("FID_INPUT_ISCD=1001", calls[-1][1])

    def test_invalid_or_failed_payload_is_safe(self):
        responses = iter(
            [
                {"access_token": "mock-token", "expires_in": 3600},
                {"rt_cd": "0", "output": {"bstp_nmix_prpr": "NaN", "bstp_nmix_prdy_ctrt": "2.0"}},
            ]
        )
        result = kis_market_data.get_index_snapshot(
            "^KS11",
            "key",
            "secret",
            now=datetime(2026, 7, 14, 10, 0, tzinfo=SEOUL),
            request_json=lambda *args, **kwargs: next(responses),
        )
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()

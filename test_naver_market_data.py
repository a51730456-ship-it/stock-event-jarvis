import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import naver_market_data


SEOUL = ZoneInfo("Asia/Seoul")


def _payload(**overrides):
    row = {
        "itemCode": "KOSPI",
        "closePrice": "6,618.69",
        "fluctuationsRatio": "-2.77",
        "localTradedAt": "2026-07-14T11:26:12+09:00",
        "marketStatus": "OPEN",
    }
    row.update(overrides)
    return {"pollingInterval": 7000, "datas": [row]}


class NaverMarketDataTests(unittest.TestCase):
    def test_current_index_uses_payload_timestamp_and_calculates_previous_close(self):
        calls = []

        def request_json(url, **kwargs):
            calls.append((url, kwargs))
            return _payload()

        result = naver_market_data.get_index_snapshot(
            "^KS11",
            now=datetime(2026, 7, 14, 11, 27, tzinfo=SEOUL),
            request_json=request_json,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["current"], 6618.69)
        self.assertAlmostEqual(result["change_pct"], -2.77)
        self.assertAlmostEqual(result["prev_close"], 6807.25, places=2)
        self.assertEqual(result["as_of_time"], "11:26")
        self.assertEqual(result["as_of_date"], "2026-07-14")
        self.assertEqual(result["source"], "네이버 금융 현재지수")
        self.assertTrue(calls[0][0].endswith("/KOSPI"))

    def test_utc_timestamp_is_converted_to_seoul(self):
        result = naver_market_data.get_index_snapshot(
            "KOSPI",
            now=datetime(2026, 7, 14, 11, 27, tzinfo=SEOUL),
            request_json=lambda *args, **kwargs: _payload(localTradedAt="2026-07-14T02:26:12+00:00"),
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["as_of_time"], "11:26")

    def test_kosdaq_endpoint_and_row_are_kept_separate(self):
        result = naver_market_data.get_index_snapshot(
            "^KQ11",
            now=datetime(2026, 7, 14, 11, 27, tzinfo=SEOUL),
            request_json=lambda *args, **kwargs: _payload(
                itemCode="KOSDAQ", closePrice="764.09", fluctuationsRatio="-4.41"
            ),
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["current"], 764.09)
        self.assertAlmostEqual(result["change_pct"], -4.41)

    def test_stale_or_previous_day_value_is_not_intraday(self):
        for traded_at in ("2026-07-14T11:20:00+09:00", "2026-07-13T15:30:00+09:00"):
            with self.subTest(traded_at=traded_at):
                result = naver_market_data.get_index_snapshot(
                    "^KS11",
                    now=datetime(2026, 7, 14, 11, 27, tzinfo=SEOUL),
                    request_json=lambda *args, **kwargs: _payload(localTradedAt=traded_at),
                )
                self.assertFalse(result["ok"])

    def test_closed_invalid_or_failed_payload_is_safe(self):
        payloads = [
            _payload(marketStatus="CLOSE"),
            _payload(closePrice="NaN"),
            _payload(fluctuationsRatio="Infinity"),
            {"datas": []},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                result = naver_market_data.get_index_snapshot(
                    "^KS11",
                    now=datetime(2026, 7, 14, 11, 27, tzinfo=SEOUL),
                    request_json=lambda *args, **kwargs: payload,
                )
                self.assertFalse(result["ok"])

        result = naver_market_data.get_index_snapshot(
            "^KS11",
            now=datetime(2026, 7, 14, 11, 27, tzinfo=SEOUL),
            request_json=lambda *args, **kwargs: (_ for _ in ()).throw(OSError("network")),
        )
        self.assertFalse(result["ok"])

    def test_outside_regular_session_makes_no_request(self):
        calls = []
        result = naver_market_data.get_index_snapshot(
            "^KS11",
            now=datetime(2026, 7, 14, 8, 59, tzinfo=SEOUL),
            request_json=lambda *args, **kwargs: calls.append((args, kwargs)),
        )
        self.assertFalse(result["ok"])
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()

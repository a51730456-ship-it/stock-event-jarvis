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


class NaverIndexDailyCloseTests(unittest.TestCase):
    # 2026-07-15 추가: 야간에 yfinance가 당일 종가를 하루 늦게 올려 KOSPI/KOSDAQ가
    # 어제 값으로 표시되던 문제 — 장이 닫혀 있어도 네이버의 최근 종가를 대체 조회한다.

    def test_closed_market_returns_latest_close(self):
        result = naver_market_data.get_index_daily_close(
            "^KS11",
            now=datetime(2026, 7, 14, 22, 30, tzinfo=SEOUL),
            request_json=lambda *args, **kwargs: _payload(
                marketStatus="CLOSE",
                closePrice="6,856.83",
                fluctuationsRatio="0.73",
                localTradedAt="2026-07-14T15:30:00+09:00",
            ),
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["current"], 6856.83)
        self.assertAlmostEqual(result["change_pct"], 0.73)
        self.assertEqual(result["as_of_date"], "2026-07-14")
        self.assertEqual(result["data_kind"], "daily_close")
        self.assertEqual(result["source"], "네이버 금융 종가")

    def test_stale_close_older_than_seven_days_is_rejected(self):
        result = naver_market_data.get_index_daily_close(
            "^KS11",
            now=datetime(2026, 7, 22, 22, 30, tzinfo=SEOUL),
            request_json=lambda *args, **kwargs: _payload(
                marketStatus="CLOSE", localTradedAt="2026-07-14T15:30:00+09:00",
            ),
        )
        self.assertFalse(result["ok"])

    def test_malformed_and_network_failures_do_not_raise(self):
        for bad_payload in ({}, {"datas": "x"}, {"datas": []}):
            with self.subTest(payload=bad_payload):
                result = naver_market_data.get_index_daily_close(
                    "^KS11",
                    now=datetime(2026, 7, 14, 22, 30, tzinfo=SEOUL),
                    request_json=lambda *args, **kwargs: bad_payload,
                )
                self.assertFalse(result["ok"])
        result = naver_market_data.get_index_daily_close(
            "^KS11",
            now=datetime(2026, 7, 14, 22, 30, tzinfo=SEOUL),
            request_json=lambda *args, **kwargs: (_ for _ in ()).throw(OSError("network")),
        )
        self.assertFalse(result["ok"])

    def test_unsupported_ticker_rejected(self):
        result = naver_market_data.get_index_daily_close("AAPL")
        self.assertFalse(result["ok"])


def _futures_html(first_date="26.07.22"):
    return (
        "<table><tr><th>날짜</th><th>개인</th><th>외국인</th><th>기관계</th></tr>"
        f'<tr><td class="date2">{first_date}</td>'
        "<td>265</td><td>1,679</td><td>-1,971</td><td>27</td></tr>"
        '<tr><td class="date2">26.07.21</td>'
        "<td>-164</td><td>-2,485</td><td>2,391</td><td>258</td></tr></table>"
    )


class ForeignFuturesDailyNetTests(unittest.TestCase):
    """네이버 파생 투자자별 매매동향(선물) — 외국인 순매수 자동 조회."""

    NOW = datetime(2026, 7, 22, 10, 30, tzinfo=SEOUL)

    def test_reads_foreign_net_from_today_row(self):
        result = naver_market_data.get_foreign_futures_daily_net(
            now=self.NOW, request_text=lambda url, **kwargs: _futures_html()
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["net_contracts"], 1679)
        self.assertEqual(result["trade_date"], "2026-07-22")
        self.assertIn("네이버", result["source"])

    def test_rejects_when_today_row_missing(self):
        result = naver_market_data.get_foreign_futures_daily_net(
            now=self.NOW, request_text=lambda url, **kwargs: _futures_html("26.07.21")
        )
        self.assertFalse(result["ok"])

    def test_network_failure_returns_not_ok(self):
        result = naver_market_data.get_foreign_futures_daily_net(
            now=self.NOW,
            request_text=lambda *args, **kwargs: (_ for _ in ()).throw(OSError("network")),
        )
        self.assertFalse(result["ok"])

    def test_layout_change_returns_not_ok_instead_of_wrong_number(self):
        result = naver_market_data.get_foreign_futures_daily_net(
            now=self.NOW, request_text=lambda url, **kwargs: "<html>구조가 바뀐 페이지</html>"
        )
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()

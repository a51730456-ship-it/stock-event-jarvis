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


def _investor_html(first_date="26.07.22"):
    return (
        "<table>"
        f'<tr><td class="date2">{first_date}</td>'
        "<td>-18,873</td><td>20,145</td><td>-1,169</td><td>-1,954</td><td>240</td>"
        "<td>-830</td><td>0</td><td>5</td><td>1,370</td><td>-102</td></tr>"
        '<tr><td class="date2">26.07.21</td>'
        "<td>-16,421</td><td>2,952</td><td>13,744</td><td>8,891</td><td>1,157</td>"
        "<td>3,158</td><td>0</td><td>12</td><td>500</td><td>-275</td></tr></table>"
    )


class MarketInvestorFlowTests(unittest.TestCase):
    """KIS 실패 시 쓰는 무료 대체 경로 — 코스피/코스닥 투자자별 매매동향."""

    NOW = datetime(2026, 7, 22, 13, 30, tzinfo=SEOUL)

    def test_parses_today_investor_row(self):
        result = naver_market_data.get_market_investor_flow(
            "KOSPI", now=self.NOW, request_text=lambda url, **kwargs: _investor_html()
        )
        self.assertTrue(result["ok"])
        values = result["values"]
        self.assertEqual(values["personal"], -18_873)
        self.assertEqual(values["foreign"], 20_145)
        self.assertEqual(values["institution"], -1_169)
        self.assertEqual(values["securities"], -1_954)
        self.assertEqual(values["pension"], 1_370)
        self.assertEqual(result["unit"], "억원")

    def test_sum_of_main_investors_is_near_zero(self):
        """개인+외국인+기관계+기타법인 ≈ 0이어야 열 순서가 맞는 것이다."""
        result = naver_market_data.get_market_investor_flow(
            "KOSPI", now=self.NOW, request_text=lambda url, **kwargs: _investor_html()
        )
        values = result["values"]
        total = values["personal"] + values["foreign"] + values["institution"] + values["etc_corp"]
        self.assertLessEqual(abs(total), 10)

    def test_kosdaq_supported(self):
        result = naver_market_data.get_market_investor_flow(
            "KOSDAQ", now=self.NOW, request_text=lambda url, **kwargs: _investor_html()
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["market"], "KOSDAQ")

    def test_unsupported_market_rejected(self):
        self.assertFalse(naver_market_data.get_market_investor_flow("NASDAQ")["ok"])

    def test_unit_conversion_to_engine_million_won(self):
        """엔진은 백만원 단위를 기대한다 — 억원×100이어야 화면 표시가 맞다.

        원(×1e8)으로 넣었더니 '+20,361,000,000억'처럼 1억 배 부풀려진 적이 있다
        (2026-07-22). 그 회귀를 막는다.
        """
        import kr_intraday_flow

        result = naver_market_data.get_market_investor_flow(
            "KOSPI", now=self.NOW, request_text=lambda url, **kwargs: _investor_html()
        )
        foreign_eok = result["values"]["foreign"]  # 20,145억
        self.assertEqual(kr_intraday_flow._fmt_amount(foreign_eok * 100), "+20,145억")
        self.assertNotEqual(kr_intraday_flow._fmt_amount(foreign_eok * 1e8), "+20,145억")

    def test_stale_date_rejected_instead_of_using_yesterday(self):
        result = naver_market_data.get_market_investor_flow(
            "KOSPI", now=self.NOW, request_text=lambda url, **kwargs: _investor_html("26.07.21")
        )
        self.assertFalse(result["ok"])

    def test_network_failure_returns_not_ok(self):
        result = naver_market_data.get_market_investor_flow(
            "KOSPI", now=self.NOW,
            request_text=lambda *args, **kwargs: (_ for _ in ()).throw(OSError("network")),
        )
        self.assertFalse(result["ok"])


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

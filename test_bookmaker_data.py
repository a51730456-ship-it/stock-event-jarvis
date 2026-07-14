import unittest
from threading import Barrier
from unittest.mock import patch, MagicMock

import bookmaker_data as bd


def _response(json_payload, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_payload
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception("http error")
    return resp


class WordBoundaryMatchTests(unittest.TestCase):
    def test_war_does_not_match_warriors(self):
        self.assertFalse(bd._question_matches("Will LeBron James play for the Warriors?"))

    def test_war_does_not_match_software(self):
        self.assertFalse(bd._question_matches("Will this software launch on time?"))

    def test_war_matches_trade_war(self):
        self.assertTrue(bd._question_matches("Will the US-China trade war escalate?"))

    def test_china_matches_whole_word(self):
        self.assertTrue(bd._question_matches("Will China overtake US GDP?"))

    def test_fed_matches(self):
        self.assertTrue(bd._question_matches("Will the Fed cut rates?"))

    def test_rate_and_oil_use_word_boundaries(self):
        self.assertTrue(bd._question_matches("Will the policy rate change?"))
        self.assertTrue(bd._question_matches("Will oil exceed $100?"))
        self.assertFalse(bd._question_matches("Will a pirate movie win?"))
        self.assertFalse(bd._question_matches("Will food spoil quickly?"))

    def test_election_keyword_removed(self):
        self.assertFalse(bd._question_matches("Will Pete Buttigieg win the 2028 US Presidential Election?"))


class ThresholdLabelTranslationTests(unittest.TestCase):
    def test_fed_decision_labels(self):
        self.assertEqual(bd._translate_threshold_label("No change"), "동결")
        self.assertEqual(bd._translate_threshold_label("25 bps increase"), "25bp 인상")
        self.assertEqual(bd._translate_threshold_label("25 bps decrease"), "25bp 인하")
        self.assertEqual(bd._translate_threshold_label("50+ bps decrease"), "50bp 이상 인하")

    def test_grouped_condition_labels(self):
        self.assertEqual(bd._translate_threshold_label("Exactly 3 cuts"), "3회 인하")
        self.assertEqual(bd._translate_threshold_label("0 (0 bps)"), "0회 인하")
        self.assertEqual(bd._translate_threshold_label("In June 2026"), "2026년 6월")
        self.assertEqual(bd._translate_threshold_label("≥ $80"), "$80 이상")
        self.assertEqual(bd._translate_threshold_label("¡è $85"), "$85 이상")

    def test_above_percent(self):
        self.assertEqual(bd._translate_threshold_label("Above 4.00%"), "4.00% 이상")

    def test_below_percent(self):
        self.assertEqual(bd._translate_threshold_label("Below 2.2%"), "2.2% 이하")

    def test_exactly(self):
        self.assertEqual(bd._translate_threshold_label("Exactly 0.5%"), "정확히 0.5%")

    def test_above_dollar_amount(self):
        self.assertEqual(bd._translate_threshold_label("Above $80 billion"), "$80 billion 이상")

    def test_unmatched_pattern_returned_unchanged(self):
        self.assertEqual(bd._translate_threshold_label("Maintain current rate"), "Maintain current rate")

    def test_empty_label(self):
        self.assertEqual(bd._translate_threshold_label(""), "")
        self.assertIsNone(bd._translate_threshold_label(None))


class ExpiryTests(unittest.TestCase):
    def test_past_date_is_expired(self):
        self.assertTrue(bd._is_expired("2020-01-01"))

    def test_future_date_is_not_expired(self):
        self.assertFalse(bd._is_expired("2099-01-01"))

    def test_missing_date_is_not_expired(self):
        self.assertFalse(bd._is_expired(None))
        self.assertFalse(bd._is_expired(""))


class PolymarketEventGroupingTests(unittest.TestCase):
    @patch("bookmaker_data.requests.get")
    def test_groups_same_event_and_excludes_zero_volume_and_expired(self, mock_get):
        markets = [
            {
                "question": "Will the Fed decrease interest rates by 25 bps after the July 2026 meeting?",
                "endDate": "2026-07-29T00:00:00Z",
                "lastTradePrice": 0.006,
                "volume24hr": 187958.36,
                "liquidity": 601192.7,
                "events": [{"id": "287395", "title": "Fed Decision in July?"}],
                "groupItemTitle": "25 bps decrease",
                "updatedAt": "2026-07-13T12:00:00Z",
                "id": "1654957",
            },
            {
                "question": "Will there be no change in Fed interest rates after the July 2026 meeting?",
                "endDate": "2026-07-29T00:00:00Z",
                "lastTradePrice": 0.77,
                "volume24hr": 219424.86,
                "liquidity": 553073.4,
                "events": [{"id": "287395", "title": "Fed Decision in July?"}],
                "groupItemTitle": "No change",
                "updatedAt": "2026-07-13T12:00:00Z",
                "id": "1654958",
            },
            {
                # 같은 사건 안에서도 거래량이 숫자 0인 개별 계약은 제외한다.
                "question": "Will the Fed increase interest rates after the July 2026 meeting?",
                "endDate": "2026-07-29T00:00:00Z",
                "lastTradePrice": 0.01,
                "volume24hr": 0,
                "liquidity": 100,
                "events": [{"id": "287395", "title": "Fed Decision in July?"}],
                "groupItemTitle": "25 bps increase",
                "updatedAt": "2026-07-13T12:00:00Z",
                "id": "1654959",
            },
            {
                # 거래량 0인 유령 이벤트 -> 이벤트 전체가 제외되어야 함
                "question": "Will a ghost event happen?",
                "endDate": "2099-01-01T00:00:00Z",
                "lastTradePrice": 0.5,
                "volume24hr": 0,
                "liquidity": 0,
                "events": [{"id": "999999", "title": "Ghost event"}],
                "groupItemTitle": "Yes",
                "updatedAt": "2026-07-13T12:00:00Z",
                "id": "1",
            },
            {
                # 마감일이 과거인 시장은 이미 끝난 시장이므로 제외되어야 함
                "question": "Will something already resolved happen?",
                "endDate": "2020-01-01T00:00:00Z",
                "lastTradePrice": 0.5,
                "volume24hr": 5000,
                "liquidity": 1000,
                "events": [{"id": "888888", "title": "Resolved event"}],
                "groupItemTitle": "Yes",
                "updatedAt": "2020-01-02T00:00:00Z",
                "id": "2",
            },
            {
                # 거시경제 키워드와 무관 -> 매칭 안 되어야 함
                "question": "Will the Lakers win the championship?",
                "endDate": "2099-01-01T00:00:00Z",
                "lastTradePrice": 0.5,
                "volume24hr": 5000,
                "liquidity": 1000,
                "events": [{"id": "777777", "title": "NBA championship"}],
                "groupItemTitle": "Yes",
                "updatedAt": "2026-07-13T12:00:00Z",
                "id": "3",
            },
        ]
        mock_get.return_value = _response(markets)

        result = bd.fetch_polymarket_events(limit_events=10, limit_scan=100)

        self.assertTrue(result["ok"])
        titles = [e["title"] for e in result["events"]]
        self.assertIn("Fed Decision in July?", titles)
        self.assertNotIn("Ghost event", titles)
        self.assertNotIn("Resolved event", titles)
        self.assertNotIn("NBA championship", titles)

        fed_event = next(e for e in result["events"] if e["title"] == "Fed Decision in July?")
        self.assertEqual(len(fed_event["contracts"]), 2)
        # 확률 내림차순 정렬 확인
        self.assertEqual(fed_event["contracts"][0]["label"], "No change")
        self.assertEqual(fed_event["contracts"][0]["probability_pct"], 77.0)
        self.assertEqual(fed_event["contracts"][1]["label"], "25 bps decrease")

    @patch("bookmaker_data.requests.get")
    def test_exact_duplicate_removed_but_threshold_variants_kept(self, mock_get):
        markets = [
            {
                "question": "Will CPI reach 4% this year?",
                "endDate": "2099-01-01T00:00:00Z",
                "lastTradePrice": 0.3,
                "volume24hr": 1000,
                "liquidity": 100,
                "events": [{"id": "111", "title": "US CPI this year"}],
                "groupItemTitle": "4%",
                "updatedAt": "2026-07-13T12:00:00Z",
                "id": "a1",
                "url": "https://example.test/markets/a1",
            },
            {
                # 완전 동일 질문+마감일 -> 완전 중복이므로 제거되어야 함
                "question": "Will CPI reach 4% this year?",
                "endDate": "2099-01-01T00:00:00Z",
                "lastTradePrice": 0.3,
                "volume24hr": 1000,
                "liquidity": 100,
                "events": [{"id": "111", "title": "US CPI this year"}],
                "groupItemTitle": "4%",
                "updatedAt": "2026-07-13T12:00:00Z",
                "id": "a1",
                "url": "https://example.test/markets/a1",
            },
            {
                # 임계값만 다름 -> 별도 계약으로 유지되어야 함(중복 아님)
                "question": "Will CPI reach 5% this year?",
                "endDate": "2099-01-01T00:00:00Z",
                "lastTradePrice": 0.12,
                "volume24hr": 800,
                "liquidity": 90,
                "events": [{"id": "111", "title": "US CPI this year"}],
                "groupItemTitle": "5%",
                "updatedAt": "2026-07-13T12:00:00Z",
                "id": "a2",
                "url": "https://example.test/markets/a2",
            },
        ]
        mock_get.return_value = _response(markets)

        result = bd.fetch_polymarket_events(limit_events=10, limit_scan=100)
        event = next(e for e in result["events"] if e["title"] == "US CPI this year")
        labels = sorted(c["label"] for c in event["contracts"])
        self.assertEqual(labels, ["4%", "5%"])
        first = next(c for c in event["contracts"] if c["label"] == "4%")
        self.assertEqual(first["market_id"], "a1")
        self.assertEqual(first["url"], "https://example.test/markets/a1")
        self.assertEqual(first["source"], "Polymarket")

    @patch("bookmaker_data.requests.get")
    def test_same_title_with_different_event_ids_is_not_merged(self, mock_get):
        mock_get.return_value = _response(
            [
                {
                    "question": "Will CPI exceed 4% in the US?",
                    "endDate": "2099-01-01T00:00:00Z",
                    "lastTradePrice": 0.3,
                    "volume24hr": 100,
                    "events": [{"id": "event-a", "title": "CPI threshold"}],
                    "groupItemTitle": "US",
                    "id": "market-a",
                },
                {
                    "question": "Will CPI exceed 4% in Europe?",
                    "endDate": "2099-01-01T00:00:00Z",
                    "lastTradePrice": 0.4,
                    "volume24hr": 200,
                    "events": [{"id": "event-b", "title": "CPI threshold"}],
                    "groupItemTitle": "Europe",
                    "id": "market-b",
                },
            ]
        )

        result = bd.fetch_polymarket_events(limit_events=10)

        self.assertEqual(len(result["events"]), 2)
        self.assertEqual({event["event_id"] for event in result["events"]}, {"event-a", "event-b"})

    @patch("bookmaker_data.requests.get")
    def test_unknown_volume_is_not_assumed_to_be_zero(self, mock_get):
        mock_get.return_value = _response(
            [
                {
                    "question": "Will CPI rise this year?",
                    "endDate": "2099-01-01T00:00:00Z",
                    "lastTradePrice": 0.5,
                    "volume24hr": None,
                    "events": [{"id": "unknown-volume", "title": "CPI this year"}],
                    "groupItemTitle": "Yes",
                    "id": "unknown-market",
                }
            ]
        )

        result = bd.fetch_polymarket_events(limit_events=10)

        self.assertEqual(len(result["events"]), 1)
        self.assertIsNone(result["events"][0]["contracts"][0]["volume_24h"])


class KalshiEventGroupingTests(unittest.TestCase):
    @patch("bookmaker_data.requests.get")
    def test_category_series_requests_run_in_parallel(self, mock_get):
        category_barrier = Barrier(2)
        completed = []

        def side_effect(url, params=None, timeout=None):
            if url == bd.KALSHI_SERIES_URL:
                category_barrier.wait(timeout=1)
                completed.append(params["category"])
                return _response({"series": []})
            raise AssertionError(f"unexpected url {url}")

        mock_get.side_effect = side_effect

        result = bd.fetch_kalshi_events(limit_events=10, max_series=15)

        self.assertTrue(result["ok"])
        self.assertCountEqual(completed, ["Economics", "Politics"])

    @patch("bookmaker_data.requests.get")
    def test_series_market_requests_run_in_parallel(self, mock_get):
        market_barrier = Barrier(2)
        completed = []

        def side_effect(url, params=None, timeout=None):
            if url == bd.KALSHI_SERIES_URL:
                if params.get("category") == "Economics":
                    return _response(
                        {
                            "series": [
                                {"ticker": "KXFED", "title": "Fed decision"},
                                {"ticker": "KXCPI", "title": "CPI inflation"},
                            ]
                        }
                    )
                return _response({"series": []})
            if url == bd.KALSHI_MARKETS_URL:
                market_barrier.wait(timeout=1)
                completed.append(params["series_ticker"])
                return _response({"markets": []})
            raise AssertionError(f"unexpected url {url}")

        mock_get.side_effect = side_effect

        result = bd.fetch_kalshi_events(limit_events=10, max_series=15)

        self.assertTrue(result["ok"])
        self.assertCountEqual(completed, ["KXFED", "KXCPI"])

    @patch("bookmaker_data.requests.get")
    def test_groups_by_event_ticker_and_filters_zero_volume_events(self, mock_get):
        def side_effect(url, params=None, timeout=None):
            if url == bd.KALSHI_SERIES_URL:
                if params.get("category") == "Economics":
                    return _response({"series": [{"ticker": "KXCPI", "title": "CPI inflation"}]})
                return _response({"series": []})
            if url == bd.KALSHI_MARKETS_URL:
                return _response(
                    {
                        "markets": [
                            {
                                "event_ticker": "KXCPI-26JUL",
                                "ticker": "KXCPI-26JUL-T0.2",
                                "url": "https://example.test/kalshi/t02",
                                "title": "Will CPI rise more than X in July 2026?",
                                "yes_sub_title": "Above -0.2%",
                                "yes_bid_dollars": 0.41,
                                "volume_24h_fp": 2469.12,
                                "liquidity_dollars": 0,
                                "close_time": "2099-07-14T00:00:00Z",
                                "updated_time": "2026-07-13T12:00:00Z",
                            },
                            {
                                "event_ticker": "KXCPI-26JUL",
                                "ticker": "KXCPI-26JUL-T0.3",
                                "url": "https://example.test/kalshi/t03",
                                "title": "Will CPI rise more than X in July 2026?",
                                "yes_sub_title": "Above -0.3%",
                                "yes_bid_dollars": 0.87,
                                "volume_24h_fp": 338.59,
                                "liquidity_dollars": 0,
                                "close_time": "2099-07-14T00:00:00Z",
                                "updated_time": "2026-07-13T12:00:00Z",
                            },
                        ]
                    }
                )
            raise AssertionError(f"unexpected url {url}")

        mock_get.side_effect = side_effect

        result = bd.fetch_kalshi_events(limit_events=10, max_series=15)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["events"]), 1)
        event = result["events"][0]
        self.assertEqual(len(event["contracts"]), 2)
        self.assertEqual(event["contracts"][0]["probability_pct"], 87.0)  # 확률 내림차순
        self.assertEqual(event["contracts"][0]["source"], "Kalshi")
        self.assertEqual(event["contracts"][0]["market_id"], "KXCPI-26JUL-T0.3")

    @patch("bookmaker_data.requests.get")
    def test_all_zero_volume_event_excluded(self, mock_get):
        def side_effect(url, params=None, timeout=None):
            if url == bd.KALSHI_SERIES_URL:
                if params.get("category") == "Economics":
                    return _response({"series": [{"ticker": "KXGHOST", "title": "Fed ghost series"}]})
                return _response({"series": []})
            if url == bd.KALSHI_MARKETS_URL:
                return _response(
                    {
                        "markets": [
                            {
                                "event_ticker": "KXGHOST-1",
                                "title": "Ghost Fed market",
                                "yes_sub_title": "Yes",
                                "yes_bid_dollars": 0.5,
                                "volume_24h_fp": 0,
                                "liquidity_dollars": 0,
                                "close_time": "2099-01-01T00:00:00Z",
                                "updated_time": "2026-07-13T12:00:00Z",
                            }
                        ]
                    }
                )
            raise AssertionError(f"unexpected url {url}")

        mock_get.side_effect = side_effect
        result = bd.fetch_kalshi_events(limit_events=10, max_series=15)
        self.assertEqual(result["events"], [])


class BookmakerSnapshotIsolationTests(unittest.TestCase):
    @patch("bookmaker_data.fetch_kalshi_events")
    @patch("bookmaker_data.fetch_polymarket_events")
    def test_two_sources_start_in_parallel(self, mock_poly, mock_kalshi):
        source_barrier = Barrier(2)

        def source_result(source):
            source_barrier.wait(timeout=1)
            return {"ok": True, "error": None, "events": []}

        mock_poly.side_effect = lambda **kwargs: source_result("Polymarket")
        mock_kalshi.side_effect = lambda **kwargs: source_result("Kalshi")

        snapshot = bd.fetch_bookmaker_snapshot()

        self.assertEqual(snapshot["errors"], [])

    @patch("bookmaker_data.fetch_kalshi_events")
    @patch("bookmaker_data.fetch_polymarket_events")
    def test_one_source_failure_does_not_block_the_other(self, mock_poly, mock_kalshi):
        mock_poly.return_value = {"ok": False, "error": "Polymarket 조회 실패", "events": []}
        mock_kalshi.return_value = {
            "ok": True,
            "error": None,
            "events": [
                {
                    "source": "Kalshi",
                    "event_id": "X",
                    "title": "Some event",
                    "end_date": "2099-01-01",
                    "contracts": [{"label": "Yes", "probability_pct": 50.0, "volume_24h": 10.0}],
                    "event_volume": 10.0,
                }
            ],
        }
        snapshot = bd.fetch_bookmaker_snapshot()
        self.assertTrue(snapshot["ok"])
        self.assertEqual(len(snapshot["events"]), 1)
        self.assertTrue(any("Polymarket" in e for e in snapshot["errors"]))

    @patch("bookmaker_data.fetch_kalshi_events")
    @patch("bookmaker_data.fetch_polymarket_events")
    def test_kalshi_failure_does_not_block_polymarket(self, mock_poly, mock_kalshi):
        mock_poly.return_value = {
            "ok": True,
            "error": None,
            "events": [
                {
                    "source": "Polymarket",
                    "event_id": "P",
                    "title": "Fed event",
                    "end_date": "2099-01-01",
                    "contracts": [{"label": "Yes", "probability_pct": 60.0, "volume_24h": 20.0}],
                    "event_volume": 20.0,
                }
            ],
        }
        mock_kalshi.return_value = {"ok": False, "error": "Kalshi 조회 실패", "events": []}

        snapshot = bd.fetch_bookmaker_snapshot()

        self.assertTrue(snapshot["ok"])
        self.assertEqual(len(snapshot["events"]), 1)
        self.assertEqual(snapshot["events"][0]["source"], "Polymarket")
        self.assertTrue(any("Kalshi" in error for error in snapshot["errors"]))


if __name__ == "__main__":
    unittest.main()

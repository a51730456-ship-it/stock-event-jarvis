"""실시간 시세 묶음조회 테스트 — 네트워크 없이 파싱과 경계만 확인한다.

여기서 지키려는 것은 두 가지다.
1) 거래정지 종목의 0이나 굳은 값이 종가위치 계산으로 새어 들어가지 않는 것
2) 한 묶음이 실패해도 나머지 종목은 살아남는 것 (수집이 멈추면 안 된다)
"""

import unittest
from unittest.mock import patch

import naver_stock_quote as quote_api


def _payload(code, *, open_=1000, high=1200, low=900, price=1100,
             tradable=True, cap=5.0e11):
    """네이버 응답 한 종목분 흉내. 실제 응답과 같은 문자열/숫자 혼용을 재현한다."""
    return {
        "itemCode": code,
        "closePrice": f"{price:,}",
        "closePriceRaw": price,
        "openPrice": f"{open_:,}",
        "openPriceRaw": open_,
        "highPrice": f"{high:,}",
        "highPriceRaw": high,
        "lowPrice": f"{low:,}",
        "lowPriceRaw": low,
        "accumulatedTradingVolumeRaw": 12345,
        "accumulatedTradingValueRaw": 678901234,
        "marketValueFullRaw": cap,
        "marketStatus": "CLOSE",
        "localTradedAt": "2026-07-24T15:30:00+09:00",
        "tradableStatusCode": "ok" if tradable else "stop",
        "tradeStopType": {"name": "TRADING" if tradable else "STOP"},
        "overMarketPriceInfo": {
            "tradingSessionType": "AFTER_MARKET",
            "overPrice": f"{price + 50:,}",
            "accumulatedTradingVolumeRaw": 500,
        },
        "integratedPriceInfo": {"accumulatedTradingVolumeRaw": 22345},
    }


class QuoteParsingTests(unittest.TestCase):
    def test_reads_day_prices_and_market_cap(self):
        picked = quote_api._pick(_payload("005930"))
        self.assertEqual(picked["code"], "005930")
        self.assertEqual(picked["day_open"], 1000)
        self.assertEqual(picked["day_high"], 1200)
        self.assertEqual(picked["day_low"], 900)
        self.assertEqual(picked["price"], 1100)
        self.assertEqual(picked["market_cap"], 5.0e11)
        self.assertTrue(picked["tradable"])

    def test_comma_strings_are_read_when_raw_missing(self):
        payload = _payload("000660")
        for key in ("closePriceRaw", "openPriceRaw", "highPriceRaw", "lowPriceRaw"):
            payload.pop(key)
        picked = quote_api._pick(payload)
        self.assertEqual(picked["day_high"], 1200)
        self.assertEqual(picked["price"], 1100)

    def test_trade_stopped_stock_is_marked_not_tradable(self):
        picked = quote_api._pick(_payload("111111", tradable=False))
        self.assertFalse(picked["tradable"])

    def test_after_hours_and_integrated_are_kept(self):
        picked = quote_api._pick(_payload("005930"))
        self.assertEqual(picked["after_price"], 1150)
        self.assertEqual(picked["after_session"], "AFTER_MARKET")
        self.assertEqual(picked["integrated_volume"], 22345)


class DerivedValueTests(unittest.TestCase):
    def test_intraday_location_and_wick(self):
        quote = quote_api._pick(_payload("005930", high=1200, low=900, price=1100))
        # (1100-900)/(1200-900) = 0.666...
        self.assertAlmostEqual(quote_api.intraday_location(quote), 2 / 3, places=4)
        self.assertAlmostEqual(quote_api.upper_wick_ratio(quote), 1 / 3, places=4)

    def test_high_equals_low_returns_none_instead_of_dividing_by_zero(self):
        """상한가 직행이나 거래정지면 고가=저가다. 여기서 0으로 나누면 안 된다."""
        quote = quote_api._pick(_payload("005930", high=1000, low=1000, price=1000))
        self.assertIsNone(quote_api.intraday_location(quote))
        self.assertIsNone(quote_api.upper_wick_ratio(quote))

    def test_zero_prices_return_none(self):
        """거래정지일은 고가·저가가 0으로 온다. 0/0을 만들지 않는다."""
        quote = quote_api._pick(_payload("005930", high=0, low=0, price=1000))
        self.assertIsNone(quote_api.intraday_location(quote))

    def test_missing_values_return_none(self):
        self.assertIsNone(quote_api.intraday_location({}))
        self.assertIsNone(quote_api.upper_wick_ratio({}))

    def test_location_is_clamped_between_zero_and_one(self):
        """수정주가 반올림 등으로 현재가가 고가를 살짝 넘어도 1을 넘지 않는다."""
        quote = quote_api._pick(_payload("005930", high=1200, low=900, price=1201))
        self.assertEqual(quote_api.intraday_location(quote), 1.0)


class BatchTests(unittest.TestCase):
    def test_codes_are_split_into_batches(self):
        codes = [f"{i:06d}" for i in range(1, 1801)]
        calls = []

        def fake(batch, *, timeout=10):
            calls.append(batch)
            return {code: _pick_stub(code) for code in batch}

        def _pick_stub(code):
            return quote_api._pick(_payload(code))

        with patch.object(quote_api, "_fetch_batch", side_effect=fake):
            result = quote_api.get_quotes(codes, batch_size=800)

        self.assertEqual(len(result), 1800)
        self.assertEqual([len(batch) for batch in sorted(calls, key=len, reverse=True)],
                         [800, 800, 200])

    def test_one_failed_batch_does_not_lose_the_others(self):
        codes = [f"{i:06d}" for i in range(1, 1201)]

        def fake(batch, *, timeout=10):
            if len(batch) == 800:
                raise RuntimeError("네트워크 오류")
            return {code: quote_api._pick(_payload(code)) for code in batch}

        with patch.object(quote_api, "_fetch_batch", side_effect=fake):
            result = quote_api.get_quotes(codes, batch_size=800)

        self.assertEqual(len(result), 400)  # 실패한 800개만 빠지고 나머지는 남는다

    def test_duplicate_and_blank_codes_are_removed(self):
        seen = []

        def fake(batch, *, timeout=10):
            seen.extend(batch)
            return {}

        with patch.object(quote_api, "_fetch_batch", side_effect=fake):
            quote_api.get_quotes(["005930", "005930", " ", None, "000660"])

        self.assertEqual(seen, ["005930", "000660"])

    def test_empty_input_makes_no_request(self):
        with patch.object(quote_api, "_fetch_batch", side_effect=AssertionError("요청 금지")):
            self.assertEqual(quote_api.get_quotes([]), {})


class PrevCloseTests(unittest.TestCase):
    """전일 종가를 되돌려 낸다.

    이걸 안 읽던 탓에 화면이 등락을 '저점 대비'로만 적었다. 저점 대비는
    폭락일에도 늘 플러스라, 코스피 -5.7%인 날 삼성전자가 '+1.2%'로 보였다
    (2026-07-29 사용자 지적).
    """

    def test_prev_close_is_current_minus_change(self):
        picked = quote_api._pick({
            "itemCode": "005930",
            "closePriceRaw": "210000",
            "compareToPreviousClosePriceRaw": "-10000",
        })
        self.assertEqual(picked["prev_close"], 220000.0)

    def test_rising_day_also_works(self):
        picked = quote_api._pick({
            "itemCode": "000660",
            "closePriceRaw": "1406000",
            "compareToPreviousClosePriceRaw": "56000",
        })
        self.assertEqual(picked["prev_close"], 1350000.0)

    def test_missing_change_gives_none_not_zero(self):
        """없는 값을 0으로 채우면 등락률이 조용히 틀린 채로 화면에 뜬다."""
        picked = quote_api._pick({"itemCode": "005930", "closePriceRaw": "210000"})
        self.assertIsNone(picked["prev_close"])

    def test_nonsense_change_does_not_make_a_zero_baseline(self):
        """전일 종가가 0 이하로 나오면 쓰지 않는다 — 나누다 터진다."""
        picked = quote_api._pick({
            "itemCode": "005930",
            "closePriceRaw": "210000",
            "compareToPreviousClosePriceRaw": "210000",
        })
        self.assertIsNone(picked["prev_close"])


if __name__ == "__main__":
    unittest.main()

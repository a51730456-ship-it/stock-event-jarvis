"""KIS 장중 수급 조회 어댑터 테스트 (외부 연결 없이 request_json 주입)."""

import unittest

import kis_market_data


def _token_response():
    return {"access_token": "tok", "expires_in": 3600}


class FakeKis:
    """호출된 URL/헤더를 기록하고 미리 정한 응답을 돌려주는 가짜 KIS."""

    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, method, url, *, headers=None, payload=None, timeout=5):
        if "tokenP" in url:
            return _token_response()
        self.calls.append({"url": url, "headers": headers or {}})
        return self.response


class ProgramTradeTest(unittest.TestCase):
    def setUp(self):
        kis_market_data._clear_token_cache_for_tests()

    def test_returns_rows_and_sends_tr_id(self):
        fake = FakeKis({"rt_cd": "0", "output": [{"bsop_hour": "1000", "whol_smtn_ntby_tr_pbmn": "1,234"}]})
        result = kis_market_data.get_program_trade_intraday("k", "s", request_json=fake)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(fake.calls[0]["headers"]["tr_id"], "FHPPG04600101")
        self.assertIn("FID_MRKT_CLS_CODE=K", fake.calls[0]["url"])

    def test_missing_keys_is_not_an_exception(self):
        result = kis_market_data.get_program_trade_intraday("", "", request_json=FakeKis({}))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "KIS API 키 없음")
        self.assertEqual(result["rows"], [])

    def test_error_response_is_reported_not_raised(self):
        fake = FakeKis({"rt_cd": "1", "msg1": "조회할 자료가 없습니다"})
        result = kis_market_data.get_program_trade_intraday("k", "s", request_json=fake)
        self.assertFalse(result["ok"])
        self.assertEqual(result["rows"], [])

    def test_network_failure_returns_ok_false(self):
        def boom(*args, **kwargs):
            if "tokenP" in args[1]:
                return _token_response()
            raise OSError("network down")

        result = kis_market_data.get_program_trade_intraday("k", "s", request_json=boom)
        self.assertFalse(result["ok"])


class InvestorProgramTest(unittest.TestCase):
    def setUp(self):
        kis_market_data._clear_token_cache_for_tests()

    def test_arbitrage_fields_returned(self):
        fake = FakeKis({
            "rt_cd": "0",
            "output": [{
                "invr_cls_name": "외국인",
                "arbt_ntby_amt": "1,000",
                "nabt_ntby_amt": "-2,500",
            }],
        })
        result = kis_market_data.get_program_trade_by_investor("k", "s", request_json=fake)
        self.assertTrue(result["ok"])
        self.assertEqual(result["rows"][0]["nabt_ntby_amt"], "-2,500")
        self.assertEqual(fake.calls[0]["headers"]["tr_id"], "HHPPG046600C1")


class MarketInvestorTest(unittest.TestCase):
    def setUp(self):
        kis_market_data._clear_token_cache_for_tests()

    def test_single_row_returned(self):
        fake = FakeKis({
            "rt_cd": "0",
            "output": [{"frgn_ntby_tr_pbmn": "5,000", "prsn_ntby_tr_pbmn": "-3,000"}],
        })
        result = kis_market_data.get_market_investor_intraday("k", "s", request_json=fake)
        self.assertTrue(result["ok"])
        self.assertEqual(result["row"]["frgn_ntby_tr_pbmn"], "5,000")
        self.assertIn("FID_INPUT_ISCD_2=S001", fake.calls[0]["url"])

    def test_sector_code_is_passed_through(self):
        fake = FakeKis({"rt_cd": "0", "output": [{"frgn_ntby_tr_pbmn": "1"}]})
        kis_market_data.get_market_investor_intraday(
            "k", "s", sector_code="0013", request_json=fake
        )
        self.assertIn("FID_INPUT_ISCD_2=0013", fake.calls[0]["url"])


class FuturesSnapshotTest(unittest.TestCase):
    def setUp(self):
        kis_market_data._clear_token_cache_for_tests()

    def test_no_futures_code_means_no_call(self):
        # 최근월물 코드를 모르면 임의 코드로 조회하지 않는다.
        fake = FakeKis({"rt_cd": "0", "output": {}})
        result = kis_market_data.get_kospi200_futures_snapshot("k", "s", request_json=fake)
        self.assertFalse(result["ok"])
        self.assertEqual(fake.calls, [])

    def test_basis_fields_parsed(self):
        fake = FakeKis({
            "rt_cd": "0",
            "output": {
                "futs_prpr": "352.40",
                "basis": "-0.35",
                "mrkt_basis": "-0.12",
                "hts_otst_stpl_qty": "123,456",
            },
        })
        result = kis_market_data.get_kospi200_futures_snapshot(
            "k", "s", futures_code="101W09", request_json=fake
        )
        self.assertTrue(result["ok"])
        self.assertAlmostEqual(result["market_basis"], -0.12)
        self.assertAlmostEqual(result["open_interest"], 123456.0)
        self.assertEqual(fake.calls[0]["headers"]["tr_id"], "FHMIF10000000")

    def test_blank_fields_become_none_not_zero(self):
        fake = FakeKis({"rt_cd": "0", "output": {"futs_prpr": "352.40", "mrkt_basis": ""}})
        result = kis_market_data.get_kospi200_futures_snapshot(
            "k", "s", futures_code="101W09", request_json=fake
        )
        self.assertTrue(result["ok"])
        self.assertIsNone(result["market_basis"])


class SectorCategoryTest(unittest.TestCase):
    def setUp(self):
        kis_market_data._clear_token_cache_for_tests()

    def test_rows_returned_for_sector_lookup(self):
        fake = FakeKis({
            "rt_cd": "0",
            "output": [
                {"bstp_cls_code": "0002", "hts_kor_isnm": "음식료품"},
                {"bstp_cls_code": "0013", "hts_kor_isnm": "전기·전자", "acml_tr_pbmn": "1,000"},
            ],
        })
        result = kis_market_data.get_sector_category_prices("k", "s", request_json=fake)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(fake.calls[0]["headers"]["tr_id"], "FHPUP02140000")


if __name__ == "__main__":
    unittest.main()

import unittest
from threading import Barrier
from unittest.mock import patch

import theme_data


class USSectorAndIndicatorParallelFetchTests(unittest.TestCase):
    @patch("price_data.get_snapshot_defaults")
    def test_sector_snapshot_requests_run_in_parallel(self, mock_get):
        tickers = [t for t, _label in theme_data.US_SECTOR_ETFS]
        barrier = Barrier(len(tickers))
        completed = []

        def side_effect(ticker):
            barrier.wait(timeout=1)
            completed.append(ticker)
            return {"ok": True, "current": 100.0, "prev_close": 99.0}

        mock_get.side_effect = side_effect

        result = theme_data.fetch_us_sector_snapshot()

        self.assertTrue(result["ok"])
        self.assertCountEqual(completed, tickers)

    @patch("price_data.get_snapshot_defaults")
    def test_theme_indicator_requests_run_in_parallel(self, mock_get):
        all_tickers = sorted({t for tickers in theme_data.US_THEME_INDICATOR_MAPPING.values() for t in tickers})
        barrier = Barrier(len(all_tickers))
        completed = []

        def side_effect(ticker):
            barrier.wait(timeout=1)
            completed.append(ticker)
            return {"ok": True, "current": 100.0, "prev_close": 99.0}

        mock_get.side_effect = side_effect

        result = theme_data.fetch_us_theme_indicators()

        self.assertTrue(result["ok"])
        self.assertCountEqual(completed, all_tickers)

    @patch("price_data.get_snapshot_defaults")
    def test_one_ticker_failure_does_not_block_others(self, mock_get):
        def side_effect(ticker):
            if ticker == "SOXX":
                raise TimeoutError("mock timeout")
            return {"ok": True, "current": 100.0, "prev_close": 99.0}

        mock_get.side_effect = side_effect

        result = theme_data.fetch_us_sector_snapshot()

        self.assertTrue(result["ok"])
        by_ticker = {s["ticker"]: s for s in result["sectors"]}
        self.assertFalse(by_ticker["SOXX"]["ok"])
        self.assertTrue(by_ticker["SMH"]["ok"])


if __name__ == "__main__":
    unittest.main()

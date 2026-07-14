import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo

import pandas as pd

import price_data


def _fake_ticker(history_df=None, fast_info_shares=None):
    ticker = MagicMock()
    ticker.history.return_value = history_df
    ticker.fast_info = MagicMock()
    ticker.fast_info.shares = fast_info_shares
    return ticker


class IntradayLastTests(unittest.TestCase):
    def setUp(self):
        now_patcher = patch(
            "price_data._now_seoul",
            return_value=datetime(2026, 7, 13, 12, 30, tzinfo=ZoneInfo("Asia/Seoul")),
        )
        now_patcher.start()
        self.addCleanup(now_patcher.stop)

    @patch("yfinance.Ticker")
    def test_success_keeps_local_exchange_time_not_utc(self, mock_ticker_cls):
        # 2026-07-13 12:17 KST(+09:00) 데이터 -> asof는 "12:17"이어야 한다(UTC로
        # 잘못 변환되면 "03:17"이 나오는 예전 버그 재현 방지용 회귀 테스트).
        idx = pd.DatetimeIndex(
            ["2026-07-13 12:16:00+09:00", "2026-07-13 12:17:00+09:00"], name="Datetime"
        )
        df = pd.DataFrame({"Close": [6950.0, 6955.5]}, index=idx)
        mock_ticker_cls.return_value = _fake_ticker(df)

        result = price_data.get_intraday_last("^KS11")
        self.assertTrue(result["ok"])
        self.assertEqual(result["current"], 6955.5)
        self.assertEqual(result["asof"], "12:17")
        self.assertEqual(result["as_of_time"], "12:17")
        self.assertEqual(result["as_of_date"], "2026-07-13")
        self.assertEqual(result["data_kind"], "intraday")
        mock_ticker_cls.return_value.history.assert_called_once_with(period="5d", interval="1m")

    @patch("yfinance.Ticker")
    def test_previous_session_last_minute_is_returned_for_change_baseline(self, mock_ticker_cls):
        idx = pd.DatetimeIndex(
            [
                "2026-07-10 15:29:00+09:00",
                "2026-07-10 15:30:00+09:00",
                "2026-07-13 12:17:00+09:00",
            ],
            name="Datetime",
        )
        df = pd.DataFrame({"Close": [100.0, 101.0, 102.0]}, index=idx)
        mock_ticker_cls.return_value = _fake_ticker(df)

        result = price_data.get_intraday_last("^KS11")

        self.assertTrue(result["ok"])
        self.assertEqual(result["current"], 102.0)
        self.assertEqual(result["prev_close"], 101.0)
        self.assertEqual(result["prev_close_as_of_date"], "2026-07-10")

    @patch("yfinance.Ticker")
    def test_official_previous_close_overrides_mismatched_previous_minute(self, mock_ticker_cls):
        idx = pd.DatetimeIndex(
            ["2026-07-10 15:30:00+09:00", "2026-07-13 12:17:00+09:00"],
            name="Datetime",
        )
        ticker = _fake_ticker(pd.DataFrame({"Close": [110.0, 102.0]}, index=idx))
        ticker.get_history_metadata.return_value = {"previousClose": 100.0}
        mock_ticker_cls.return_value = ticker

        result = price_data.get_intraday_last("^KS11")

        self.assertTrue(result["ok"])
        self.assertEqual(result["current"], 102.0)
        self.assertEqual(result["prev_close"], 100.0)
        self.assertEqual(result["prev_close_as_of_date"], "2026-07-10")

    @patch("yfinance.Ticker")
    def test_utc_index_is_explicitly_converted_to_seoul(self, mock_ticker_cls):
        idx = pd.DatetimeIndex(["2026-07-13 03:17:00+00:00"], name="Datetime")
        df = pd.DataFrame({"Close": [6955.5]}, index=idx)
        mock_ticker_cls.return_value = _fake_ticker(df)

        result = price_data.get_intraday_last("^KS11")

        self.assertTrue(result["ok"])
        self.assertEqual(result["asof"], "12:17")

    @patch("yfinance.Ticker")
    def test_empty_dataframe_returns_not_ok(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _fake_ticker(pd.DataFrame())
        result = price_data.get_intraday_last("^KS11")
        self.assertFalse(result["ok"])

    @patch("yfinance.Ticker")
    def test_none_dataframe_returns_not_ok(self, mock_ticker_cls):
        mock_ticker_cls.return_value = _fake_ticker(None)
        result = price_data.get_intraday_last("^KS11")
        self.assertFalse(result["ok"])

    @patch("yfinance.Ticker")
    def test_nan_close_returns_not_ok(self, mock_ticker_cls):
        idx = pd.DatetimeIndex(["2026-07-13 12:17:00+09:00"], name="Datetime")
        df = pd.DataFrame({"Close": [float("nan")]}, index=idx)
        mock_ticker_cls.return_value = _fake_ticker(df)
        result = price_data.get_intraday_last("^KS11")
        self.assertFalse(result["ok"])

    @patch("yfinance.Ticker")
    def test_latest_nan_row_uses_previous_valid_minute(self, mock_ticker_cls):
        idx = pd.DatetimeIndex(
            ["2026-07-13 12:16:00+09:00", "2026-07-13 12:17:00+09:00"],
            name="Datetime",
        )
        df = pd.DataFrame({"Close": [6955.5, float("nan")]}, index=idx)
        mock_ticker_cls.return_value = _fake_ticker(df)

        result = price_data.get_intraday_last("^KS11")

        self.assertTrue(result["ok"])
        self.assertEqual(result["current"], 6955.5)
        self.assertEqual(result["asof"], "12:16")

    @patch("yfinance.Ticker")
    def test_past_minute_is_not_presented_as_today_intraday(self, mock_ticker_cls):
        idx = pd.DatetimeIndex(["2026-07-10 12:17:00+09:00"], name="Datetime")
        df = pd.DataFrame({"Close": [6900.0]}, index=idx)
        mock_ticker_cls.return_value = _fake_ticker(df)

        result = price_data.get_intraday_last("^KS11")

        self.assertFalse(result["ok"])
        self.assertIn("오늘", result["error"])

    @patch("yfinance.Ticker")
    def test_zero_or_negative_close_returns_not_ok(self, mock_ticker_cls):
        idx = pd.DatetimeIndex(["2026-07-13 12:17:00+09:00"], name="Datetime")
        df = pd.DataFrame({"Close": [0.0]}, index=idx)
        mock_ticker_cls.return_value = _fake_ticker(df)
        result = price_data.get_intraday_last("^KS11")
        self.assertFalse(result["ok"])

    @patch("yfinance.Ticker")
    def test_exception_does_not_propagate(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("network down")
        result = price_data.get_intraday_last("^KS11")
        self.assertFalse(result["ok"])
        self.assertIn("error", result)

    @patch("yfinance.Ticker")
    def test_naive_index_is_used_as_is(self, mock_ticker_cls):
        # 타임존 정보가 아예 없는 경우(tzinfo None)에도 예외 없이 처리되어야 한다.
        idx = pd.DatetimeIndex(["2026-07-13 12:17:00"], name="Datetime")
        df = pd.DataFrame({"Close": [100.0]}, index=idx)
        mock_ticker_cls.return_value = _fake_ticker(df)
        result = price_data.get_intraday_last("SOME.TICKER")
        self.assertTrue(result["ok"])
        self.assertEqual(result["asof"], "12:17")


class SnapshotDefaultsAsOfDateTests(unittest.TestCase):
    @patch("price_data._try_yfinance_ohlcv")
    def test_as_of_date_reflects_last_row_date(self, mock_try_yf):
        idx = pd.DatetimeIndex(["2026-07-10", "2026-07-13"], name="Date")
        df = pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [102.0, 103.0],
                "Low": [99.0, 100.0],
                "Close": [101.0, 102.0],
                "Volume": [1000.0, 1200.0],
            },
            index=idx,
        )
        mock_try_yf.return_value = df
        result = price_data.get_snapshot_defaults("^KS11")
        self.assertTrue(result["ok"])
        self.assertEqual(result["as_of_date"], "2026-07-13")
        self.assertEqual(result["data_kind"], "daily_close")
        for existing_key in ("current", "prev_close", "open", "high", "low", "turnover"):
            self.assertIn(existing_key, result)

    @patch("price_data._try_yfinance_ohlcv")
    def test_completed_only_excludes_in_progress_today_daily_row(self, mock_try_yf):
        idx = pd.DatetimeIndex(["2026-07-09", "2026-07-10", "2026-07-13"], name="Date")
        mock_try_yf.return_value = pd.DataFrame(
            {
                "Open": [100.0, 101.0, 102.0],
                "High": [102.0, 103.0, 104.0],
                "Low": [99.0, 100.0, 101.0],
                "Close": [101.0, 102.0, 103.0],
                "Volume": [1000.0, 1200.0, 1400.0],
            },
            index=idx,
        )
        now = datetime(2026, 7, 13, 12, 30, tzinfo=ZoneInfo("Asia/Seoul"))

        with patch("price_data._now_seoul", return_value=now), patch("yfinance.Ticker") as ticker:
            ticker.return_value = _fake_ticker()
            result = price_data.get_snapshot_defaults("^KS11", completed_only=True)

        self.assertTrue(result["ok"])
        self.assertEqual(result["current"], 102.0)
        self.assertEqual(result["prev_close"], 101.0)
        self.assertEqual(result["as_of_date"], "2026-07-10")


if __name__ == "__main__":
    unittest.main()

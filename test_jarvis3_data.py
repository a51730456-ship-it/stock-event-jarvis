import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pandas as pd

import jarvis3_data as j3


def _daily_frame(start=100.0, slope=0.5, periods=260):
    index = pd.bdate_range("2025-07-01", periods=periods)
    close = pd.Series([start + slope * i for i in range(periods)], index=index)
    return pd.DataFrame(
        {
            "Open": close - 0.3,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": 2_000_000.0,
        },
        index=index,
    )


def _intraday_frame(value):
    index = pd.date_range("2026-07-17 09:30", periods=8, freq="min", tz="America/New_York")
    close = pd.Series([value + i * 0.1 for i in range(8)], index=index)
    return pd.DataFrame(
        {"Open": close, "High": close + .2, "Low": close - .2, "Close": close, "Volume": 1000},
        index=index,
    )


class Jarvis3DataTests(unittest.TestCase):
    def tearDown(self):
        j3.clear_runtime_cache()

    def test_twenty_unique_themes_include_quantum_and_bigtech(self):
        names = [theme["name"] for theme in j3.US_THEMES]
        self.assertEqual(len(names), 20)
        self.assertEqual(len(set(names)), 20)
        self.assertIn("양자컴퓨팅", names)
        self.assertIn("빅테크10", names)

    def test_series_metrics_calculates_high_trend_and_atr(self):
        metrics = j3._series_metrics(_daily_frame(), _intraday_frame(230))
        self.assertTrue(metrics["ok"])
        self.assertGreater(metrics["current"], metrics["sma20"])
        self.assertGreater(metrics["sma20"], metrics["sma50"])
        self.assertIsNotNone(metrics["from_high_pct"])
        self.assertGreater(metrics["atr_pct"], 0)
        self.assertGreater(metrics["avg_dollar_volume"], 0)

    def test_market_overview_puts_market_gate_first(self):
        daily = {
            "SPY": _daily_frame(100, .6),
            "QQQ": _daily_frame(100, .7),
            "IWM": _daily_frame(100, .4),
            "DIA": _daily_frame(100, .3),
            "^VIX": _daily_frame(22, -.02),
        }
        live = {
            "SPY": _intraday_frame(260),
            "QQQ": _intraday_frame(280),
            "IWM": _intraday_frame(230),
            "DIA": _intraday_frame(210),
            "^VIX": _intraday_frame(18),
        }

        def side_effect(_tickers, *, interval, **_kwargs):
            frames = live if interval == "1m" else daily
            return frames, {"ok": True, "stale": False, "error": None, "fetched_at": "2026-07-19T13:00:00+09:00"}

        with patch.object(j3, "_download_cached", side_effect=side_effect):
            result = j3.get_market_overview()
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["score"], 75)
        self.assertEqual(result["regime"], "상승 우위")
        self.assertIn("SPY 50일선 위", result["reasons"])
        self.assertEqual(sum(item["max"] for item in result["score_breakdown"]), 100)
        self.assertEqual(sum(item["earned"] for item in result["score_breakdown"]), result["score"])

    def test_entry_plan_blocks_chasing_even_with_high_score(self):
        metrics = {
            "current": 100.0, "atr": 4.0, "atr_pct": 6.0, "ret5": 18.0,
            "sma20": 92.0, "sma50": 85.0, "from_high_pct": -1.0, "volume_ratio": 2.0,
        }
        plan = j3._entry_plan(metrics, 90, 90, 90)
        self.assertEqual(plan["state"], "추격 금지")
        self.assertEqual(plan["recommendation"], "추천 제외")
        self.assertIsNone(plan["trigger"])

    def test_weekend_market_phase_is_not_reported_open(self):
        saturday = datetime(2026, 7, 18, 11, 0, tzinfo=ZoneInfo("America/New_York"))
        self.assertEqual(j3.market_phase(saturday)["label"], "주말 휴장")

    def test_chart_bundle_builds_three_periods_with_one_download(self):
        frame = _daily_frame(periods=520)
        meta = {"ok": True, "stale": False, "error": None, "fetched_at": "x"}
        with patch.object(j3, "_download_cached", return_value=({"NVDA": frame}, meta)) as download:
            result = j3.get_chart_bundle("NVDA")
        self.assertTrue(result["ok"])
        self.assertEqual(set(result["charts"]), {"일봉", "주봉", "월봉"})
        self.assertIsNotNone(result["charts"]["일봉"]["volume"])
        self.assertLessEqual(len(result["charts"]["일봉"]["price"]), 180)
        # 10년치로는 월봉 120개를 그릴 때 50개월선의 앞 49개월이 비어 선이
        # 토막났다(2026-07-29 실측: NVDA 월봉 50선 72/120). 상장 이후 전체를 받는다.
        download.assert_called_once_with(("NVDA",), period="max", interval="1d", ttl_seconds=300)

    def test_chart_history_fills_the_monthly_moving_averages(self):
        """월봉 120개를 그리려면 20·50개월선이 채워질 만큼 자료가 있어야 한다."""
        frame = _daily_frame(periods=200 * 22)   # 약 200개월치 영업일
        meta = {"ok": True, "stale": False, "error": None, "fetched_at": "x"}
        with patch.object(j3, "_download_cached", return_value=({"NVDA": frame}, meta)):
            result = j3.get_chart_bundle("NVDA")
        monthly = result["charts"]["월봉"]["price"]
        self.assertGreater(monthly["MA20"].notna().sum(), 0)
        self.assertGreater(monthly["MA50"].notna().sum(), 0)
        self.assertEqual(monthly["MA50"].isna().sum(), 0, "월봉 50선 앞부분이 비어 있다")

    def test_fear_greed_parses_cnn_payload_without_network(self):
        payload = {
            "fear_and_greed": {
                "score": 41.0, "rating": "fear", "previous_close": 45.0,
                "previous_1_week": 55.0, "previous_1_month": 57.0,
                "previous_1_year": 44.0, "timestamp": "2026-07-22T07:00:00+00:00",
            }
        }
        result = j3.get_fear_greed(request_json=lambda url: payload)
        self.assertTrue(result["ok"])
        self.assertEqual(result["score"], 41.0)
        self.assertEqual(result["rating_kr"], "공포")
        self.assertEqual(result["previous_close"], 45.0)

    def test_fear_greed_bad_payload_returns_not_ok(self):
        result = j3.get_fear_greed(request_json=lambda url: {"unexpected": True})
        self.assertFalse(result.get("ok"))

    def test_intraday_chart_payload_converts_timezone_and_keeps_prev_close(self):
        payload = j3._intraday_chart_payload(_intraday_frame(230), 229.0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["prev_close"], 229.0)
        self.assertIsNone(pd.DatetimeIndex(payload["price"].index).tz)
        self.assertEqual(len(payload["price"]), 8)

    def test_intraday_chart_payload_requires_enough_bars(self):
        self.assertIsNone(j3._intraday_chart_payload(None, 100.0))
        short = _intraday_frame(230).head(3)
        self.assertIsNone(j3._intraday_chart_payload(short, 100.0))

    def test_pullback_finder_keeps_single_theme_stock(self):
        frame = _daily_frame()
        # 5거래일 전 신고가 뒤 약 6% 조정, 장기 이동평균은 여전히 위다.
        for offset in range(5):
            frame.iloc[-(offset + 1), frame.columns.get_loc("Close")] *= 0.94
            frame.iloc[-(offset + 1), frame.columns.get_loc("High")] *= 0.94
            frame.iloc[-(offset + 1), frame.columns.get_loc("Low")] *= 0.94
            frame.iloc[-(offset + 1), frame.columns.get_loc("Open")] *= 0.94
        meta = {"ok": True, "stale": False, "error": None, "fetched_at": "x"}
        with patch.object(j3, "_download_cached", return_value=({"QCOM": frame}, meta)):
            result = j3.find_pullback_stocks(min_score=0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["rows"][0]["ticker"], "QCOM")
        self.assertEqual(result["rows"][0]["theme_count"], 1)

    def test_multi_theme_is_bonus_not_required(self):
        metrics = {
            "current": 100, "sma20": 100, "sma50": 90, "sma200": 80,
            "high52_days_ago": 5, "from_high_pct": -8,
            "avg_dollar_volume": 500_000_000,
        }
        single = j3._pullback_quality(metrics, 1)
        multi = j3._pullback_quality(metrics, 3)
        self.assertIsNotNone(single)
        self.assertGreater(multi["score"], single["score"])


class LastSessionChangeTests(unittest.TestCase):
    """'미국 전일'은 끝난 정규장이어야 한다.

    2026-07-24 실측 회귀: 한국 저녁(뉴욕 새벽)에 보면 전일 -1.23%가 프리마켓
    +0.22%로 뒤집혀 보였고, 한국 조건점수의 '미국 전일 15점'까지 잘못 붙었다.
    """

    def _closes(self, values, last_day="2026-07-23"):
        index = pd.bdate_range(end=last_day, periods=len(values))
        return pd.Series(values, index=index)

    def test_uses_finished_session_when_last_bar_is_yesterday(self):
        closes = self._closes([100.0, 98.77])  # -1.23%
        change = j3._last_session_change(
            closes, datetime(2026, 7, 23).date(), datetime(2026, 7, 24).date(),
            now_ny=datetime(2026, 7, 24, 5, 0),
        )
        self.assertAlmostEqual(change, -1.23, places=2)

    def test_today_bar_after_close_is_finished(self):
        """한국 장중(뉴욕 저녁)에는 오늘 일봉이 이미 끝난 장이다."""
        closes = self._closes([100.0, 98.77])
        change = j3._last_session_change(
            closes, datetime(2026, 7, 23).date(), datetime(2026, 7, 23).date(),
            now_ny=datetime(2026, 7, 23, 19, 0),
        )
        self.assertAlmostEqual(change, -1.23, places=2)

    def test_today_bar_before_close_is_skipped(self):
        """미국 장중에는 오늘 일봉이 진행 중이므로 한 칸 앞 세션을 쓴다."""
        closes = self._closes([100.0, 98.77, 105.0])
        change = j3._last_session_change(
            closes, datetime(2026, 7, 23).date(), datetime(2026, 7, 23).date(),
            now_ny=datetime(2026, 7, 23, 10, 0),
        )
        self.assertAlmostEqual(change, -1.23, places=2)

    def test_short_history_returns_none_instead_of_guessing(self):
        self.assertIsNone(j3._last_session_change(
            self._closes([100.0]), datetime(2026, 7, 23).date(),
            datetime(2026, 7, 24).date(), now_ny=datetime(2026, 7, 24, 5, 0),
        ))

    def test_metrics_expose_both_numbers_separately(self):
        """지금 값 기준(change_pct)과 끝난 장(last_session_change_pct)은 다른 값이다."""
        daily = _daily_frame()
        metrics = j3._series_metrics(daily, _intraday_frame(500.0))
        self.assertIn("last_session_change_pct", metrics)
        self.assertIsNotNone(metrics["last_session_change_pct"])
        self.assertNotEqual(metrics["change_pct"], metrics["last_session_change_pct"])


if __name__ == "__main__":
    unittest.main()


class PriorSessionCloseTests(unittest.TestCase):
    """지수 그림의 기준선 (2026-07-25 실측 사고).

    iloc[-2]로 잡았더니 야후 일봉에 금요일 줄이 아직 안 올라온 사이 기준선이 하루 더
    옛날(수요일) 종가가 됐다. S&P가 실제로는 +0.06%인데 화면에 -1.15%로 뜨고, 그림은
    선 전체가 기준선 아래로 내려가 4개 지수가 통째로 빨갛게 나왔다.
    """

    DAILY = pd.DataFrame(
        {"Close": [7498.96, 7408.30, 7411.98]},
        index=pd.to_datetime(["2026-07-22", "2026-07-23", "2026-07-24"]),
    )

    def test_uses_the_close_before_the_intraday_day(self):
        base = j3._prior_session_close(self.DAILY, pd.Timestamp("2026-07-24").date())
        self.assertAlmostEqual(base, 7408.30)

    def test_is_right_even_when_that_day_is_missing_from_the_daily_frame(self):
        """금요일 줄이 아직 없어도 기준선은 목요일 종가여야 한다 — 이게 그 사고다."""
        lagging = self.DAILY.iloc[:2]                     # 7/24 줄이 아직 없다
        self.assertAlmostEqual(float(lagging["Close"].iloc[-2]), 7498.96)   # 옛 방식
        base = j3._prior_session_close(lagging, pd.Timestamp("2026-07-24").date())
        self.assertAlmostEqual(base, 7408.30)             # 새 방식

    def test_returns_none_without_any_earlier_session(self):
        self.assertIsNone(
            j3._prior_session_close(self.DAILY, pd.Timestamp("2026-07-22").date()))

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


def _frame_with_high(peak_days_ago: int, from_high_pct: float, periods: int = 260):
    """지정한 거래일 전에 52주 고가를 찍고, 지금은 고점 대비 X% 아래인 일봉을 만든다."""
    index = pd.bdate_range("2025-07-01", periods=periods)
    values = [50.0 + i * 0.1 for i in range(periods)]
    peak_index = periods - 1 - peak_days_ago
    peak = 100.0
    values[peak_index] = peak
    # 고점 뒤 구간은 목표 낙폭까지 곧장 내려온 상태로 둔다.
    for i in range(peak_index + 1, periods):
        values[i] = peak * (1 + from_high_pct / 100.0)
    close = pd.Series(values, index=index)
    return pd.DataFrame(
        {
            "Open": close, "High": close, "Low": close, "Close": close,
            "Volume": 3_000_000.0,
        },
        index=index,
    )


class RulebookScreenTests(unittest.TestCase):
    """설명서 두 갈래(2026-08-01 사용자 지시)가 설명서 숫자 그대로 거르는지.

    화면 설명(method_help.US_TEXT)과 여기 숫자가 어긋나면 화면이 설명과 다른 것을
    찾게 된다. 그래서 기준값을 코드 한 곳(jarvis3_data)에 두고 여기서 굳혀 둔다.
    """

    def tearDown(self):
        j3.clear_runtime_cache()

    def test_universe_is_two_hundred_and_holds_every_theme_stock(self):
        self.assertEqual(200, len(j3.US_LARGE_CAP_UNIVERSE))
        self.assertEqual(200, len(set(j3.US_LARGE_CAP_UNIVERSE)))
        theme_stocks = {t for theme in j3.US_THEMES for t in theme["stocks"]}
        # 테마 종목을 다 품어야 야후를 한 번만 부르고 테마 검색이 잘라 쓴다.
        self.assertTrue(theme_stocks.issubset(set(j3.US_LARGE_CAP_UNIVERSE)))

    def test_rule_numbers_match_the_written_guide(self):
        import method_help

        rule = j3.BREAKOUT_PULLBACK_RULE
        self.assertEqual((3, 5), rule["wait_days"])
        self.assertEqual((-6.0, -4.0), rule["drop_band"])
        self.assertEqual(120, rule["hold_days"])
        self.assertIn("3~5거래일", method_help.US_TEXT)
        self.assertIn("4~6%", method_help.US_TEXT)
        self.assertIn("120거래일", method_help.US_TEXT)
        deep, mid = j3.CRASH_REBOUND_RULES
        self.assertEqual(((-50.0, -40.0), 20), (deep["band"], deep["hold_days"]))
        self.assertEqual(((-40.0, -30.0), 60), (mid["band"], mid["hold_days"]))
        self.assertIn("-40~-50%", method_help.US_TEXT)
        self.assertIn("-30~-40%", method_help.US_TEXT)

    def _run(self, finder, frames):
        with patch.object(j3, "_download_cached", return_value=(frames, {"fetched_at": "x"})):
            return finder()

    def test_breakout_takes_only_the_three_to_five_day_four_to_six_percent_window(self):
        frames = {
            "AAPL": _frame_with_high(4, -5.0),    # 자리에 맞음
            "MSFT": _frame_with_high(1, -5.0),    # 너무 이르다(1일 전)
            "AMZN": _frame_with_high(9, -5.0),    # 너무 늦다(9일 전)
            "GOOGL": _frame_with_high(4, -2.0),   # 덜 눌렸다
            "META": _frame_with_high(4, -9.0),    # 너무 눌렸다
        }
        result = self._run(j3.find_breakout_pullback_stocks, frames)
        self.assertTrue(result["ok"])
        self.assertEqual(["AAPL"], [row["ticker"] for row in result["rows"]])
        self.assertEqual(4, result["rows"][0]["wait_days"])
        self.assertEqual(120, result["rows"][0]["hold_days"])

    def test_neither_screen_filters_on_a_moving_average(self):
        """설명서에 없는 이동평균 조건을 더하면 화면이 설명과 다른 것을 찾는다.

        특히 낙폭 종목은 30~50% 빠진 상태라 50일선 위에 있을 리 없다
        (2026-08-01 사용자 확인: "굳이 50일선 맞출 필요가 있나").
        """
        import inspect

        for finder in (j3.find_breakout_pullback_stocks, j3.find_crash_rebound_stocks):
            source = inspect.getsource(finder)
            for moving_average in ("sma20", "sma50", "sma200"):
                self.assertNotIn(
                    f'metrics.get("{moving_average}")', source,
                    f"{finder.__name__}에 {moving_average} 조건이 들어갔다",
                )

    def test_crash_splits_the_two_depth_buckets_and_ignores_the_high_date(self):
        frames = {
            "AAPL": _frame_with_high(200, -45.0),   # 깊은 갈래
            "MSFT": _frame_with_high(3, -35.0),     # 얕은 갈래 — 신고가 날짜는 안 본다
            "AMZN": _frame_with_high(50, -20.0),    # 덜 빠졌다
            "GOOGL": _frame_with_high(50, -60.0),   # 너무 빠졌다
        }
        result = self._run(j3.find_crash_rebound_stocks, frames)
        self.assertTrue(result["ok"])
        picked = {row["ticker"]: row for row in result["rows"]}
        self.assertEqual({"AAPL", "MSFT"}, set(picked))
        self.assertEqual((20, "deep"), (picked["AAPL"]["hold_days"], picked["AAPL"]["bucket"]))
        self.assertEqual((60, "mid"), (picked["MSFT"]["hold_days"], picked["MSFT"]["bucket"]))
        # 깊은 갈래가 위에 온다.
        self.assertEqual("AAPL", result["rows"][0]["ticker"])
        self.assertEqual({"deep": 1, "mid": 1}, result["bucket_counts"])

    def test_crash_rows_carry_the_reference_numbers(self):
        frames = {"AAPL": _frame_with_high(200, -45.0)}
        row = self._run(j3.find_crash_rebound_stocks, frames)["rows"][0]
        self.assertEqual((100.0, 12, 11.2), (row["win_rate"], row["sample"], row["avg_return"]))

    def test_rank_uses_the_verified_signal_first(self):
        """순위 기준은 재 보고 정했다(2026-08-01) — docs/US_RANK_BACKTEST.md.

        ① 같은 테마에서 함께 걸린 종목 수(검증됨) ② 거래대금 평소 위 연속(약함)
        ③ 거래대금 액수(참고). 순서가 뒤집히면 검증 안 된 값이 앞서게 된다.
        """
        rows = [
            {"metrics": {"avg_dollar_volume": 9e9}, "together_tier": 0,
             "together_count": 0, "volume_streak": 0},
            {"metrics": {"avg_dollar_volume": 1e8}, "together_tier": 3,
             "together_count": 4, "volume_streak": 0},
            {"metrics": {"avg_dollar_volume": 1e8}, "together_tier": 3,
             "together_count": 4, "volume_streak": 12},
        ]
        ordered = sorted(rows, key=j3._rank_key)
        # 거래대금이 90배 커도 테마 동반이 0이면 뒤로 간다.
        self.assertEqual(0, ordered[-1]["together_tier"])
        # 테마 동반이 같으면 거래대금 연속일이 많은 쪽이 앞선다.
        self.assertEqual(12, ordered[0]["volume_streak"])

    def test_theme_together_tiers_and_volume_streak(self):
        self.assertEqual(3, j3.theme_together_tier(9)[0])
        self.assertEqual(2, j3.theme_together_tier(3)[0])
        self.assertEqual(1, j3.theme_together_tier(2)[0])
        self.assertEqual(0, j3.theme_together_tier(1)[0])
        index = pd.bdate_range("2025-01-01", periods=80)
        close = pd.Series([100.0] * 80, index=index)
        volume = pd.Series([1000.0] * 60 + [5000.0] * 20, index=index)
        frame = pd.DataFrame({"Close": close, "Volume": volume})
        self.assertGreaterEqual(j3.volume_streak_days(frame), 15)
        quiet = pd.DataFrame({"Close": close, "Volume": pd.Series([1000.0] * 80, index=index)})
        self.assertEqual(0, j3.volume_streak_days(quiet))

    def test_no_match_returns_an_empty_list_not_a_loosened_rule(self):
        frames = {"AAPL": _frame_with_high(4, -20.0)}
        self.assertEqual([], self._run(j3.find_breakout_pullback_stocks, frames)["rows"])


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

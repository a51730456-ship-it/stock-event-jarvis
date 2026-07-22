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
        download.assert_called_once_with(("NVDA",), period="10y", interval="1d", ttl_seconds=300)

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


if __name__ == "__main__":
    unittest.main()

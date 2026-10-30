"""자비스13 코스피·코스닥 「이번 하락」 값 (2026-10-30 · 자비스12 의 「📉 이번 하락(QQQ)」 을 한국에 맞춰 옮김)."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import jarvis4_data as j4data
import jarvis13_market

ROOT = Path(__file__).resolve().parent
PAGE = (ROOT / "pages" / "12_자비스13.py").read_text(encoding="utf-8")


def _frame():
    days = pd.bdate_range("2025-06-02", periods=300)
    close = pd.Series(100.0, index=days)
    close.iloc[100:] = 130.0         # 고점 뒤는 130 언저리
    close.iloc[100] = 150.0          # 1년 안 최고 종가
    close.iloc[150] = 105.0          # 그 뒤 가장 깊은 날
    close.iloc[-1] = 120.0           # 지금
    return pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close, "Volume": 1.0})


class Jarvis13MarketTests(unittest.TestCase):
    def setUp(self):
        with j4data._CACHE_LOCK:
            for key in [k for k in j4data._CACHE if k == "kr_crash_market_state" or (isinstance(k, tuple) and k[0] == "j13_index_episode")]:
                j4data._CACHE.pop(key, None)
        jarvis13_market._FAILED_AT.clear()

    def test_episode_values_and_same_ruler_as_the_crash_screen(self):
        frame = _frame()
        with patch("jarvis4_data._index_frame", return_value=frame):
            ep = jarvis13_market.episode("KOSPI")
            state = j4data.kr_crash_market_state()
        self.assertTrue(ep["ok"])
        self.assertEqual(150.0, ep["peak"])
        self.assertEqual(str(frame.index[100].date()), ep["peak_date"])
        self.assertEqual(str(frame.index[150].date()), ep["low_date"])
        self.assertAlmostEqual(-30.0, ep["low_drop"], places=6)
        self.assertAlmostEqual(-20.0, ep["drop"], places=6)
        # 막대의 큰 숫자(급락 화면과 같은 함수)와 같은 숫자다
        self.assertAlmostEqual(float(state["drop_pct"]), ep["drop"], places=9)

    def test_failure_is_quiet_and_not_retried_at_once(self):
        with patch("jarvis4_data._index_frame", side_effect=RuntimeError("막힘")) as fetch:
            first = jarvis13_market.episode("KOSDAQ")
            second = jarvis13_market.episode("KOSDAQ")
        self.assertFalse(first["ok"])
        self.assertFalse(second["ok"])
        self.assertEqual(1, fetch.call_count)          # 두 번째는 2분 안이라 다시 안 받으러 간다

    def test_date_words(self):
        self.assertEqual("6월 22일", jarvis13_market.md("2026-06-22"))
        self.assertEqual("10월 6일", jarvis13_market.md("2026-10-06"))

    def test_page_draws_the_two_lines_quietly(self):
        body = PAGE[PAGE.index("def _render_kospi_drawdown"):PAGE.index("def _render_theme_table")]
        self.assertIn('jarvis13_market.episode("KOSPI")', body)
        self.assertIn('jarvis13_market.episode("KOSDAQ")', body)
        self.assertIn("📉 <b>이번 하락</b>(코스피 종가)", body)
        self.assertIn("참고 · 코스닥 1년 최고 종가 대비", body)
        self.assertIn("+ episode_line + kosdaq_line + dist_line +", body)
        self.assertIn("except Exception:\n        episode_line = kosdaq_line = dist_line = \"\"", body)
        self.assertIn("_REQUIRED_J13_MARKET_REVISION = 2026103003", PAGE)
        self.assertGreaterEqual(jarvis13_market.MODULE_REVISION, 2026103003)


def _dist_frame(changes, volumes, *, end="2026-10-29"):
    """종가 변화(%)와 거래량으로 지수 일봉을 만든다 — 첫날 종가 1000."""
    days = pd.bdate_range(end=end, periods=len(changes) + 1)
    close = [1000.0]
    for change in changes:
        close.append(close[-1] * (1 + change / 100.0))
    return pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close,
                         "Volume": [100.0] + list(volumes)}, index=days)


class DistributionDayTests(unittest.TestCase):
    """분산일 — 0.2% 넘게 내리고 거래량이 전날보다 많은 날 · 25거래일 · 그 뒤 5% 넘게 오르면 지움 · 끝난 장만."""

    AFTER_CLOSE = pd.Timestamp("2026-10-29 16:00", tz="Asia/Seoul").to_pydatetime()

    def test_counts_only_falls_on_heavier_volume(self):
        changes = [0.1] * 30
        volumes = [100.0] * 30
        changes[-3], volumes[-3] = -0.5, 150.0     # 내리고 거래량 늘어남 → 분산일
        changes[-2], volumes[-2] = -0.5, 90.0      # 내렸지만 거래량 줄어듦 → 아님
        changes[-1], volumes[-1] = -0.1, 200.0     # 거래량은 늘었지만 0.2% 안 내림 → 아님
        frame = _dist_frame(changes, volumes)
        dist = jarvis13_market.distribution_days(frame, now=self.AFTER_CLOSE)
        self.assertEqual(1, dist["count"])
        self.assertEqual([str(frame.index[-3].date())], dist["dates"])
        self.assertEqual("2026-10-29", dist["last_day"])

    def test_only_the_last_25_sessions(self):
        changes, volumes = [0.1] * 40, [100.0] * 40
        changes[5], volumes[5] = -1.0, 150.0       # 35거래일 전 → 빠진다
        changes[-10], volumes[-10] = -1.0, 150.0   # 10거래일 전 → 센다
        frame = _dist_frame(changes, volumes)
        dist = jarvis13_market.distribution_days(frame, now=self.AFTER_CLOSE)
        self.assertEqual([str(frame.index[-10].date())], dist["dates"])

    def test_a_5pct_rally_after_it_wipes_it_out(self):
        changes, volumes = [0.0] * 30, [100.0] * 30
        changes[-12], volumes[-12] = -1.0, 150.0
        for index in range(-11, -1):
            changes[index] = 0.6                   # 그 뒤 열흘 동안 6% 넘게 오름 → 지워진다
        frame = _dist_frame(changes, volumes)
        self.assertEqual(0, jarvis13_market.distribution_days(frame, now=self.AFTER_CLOSE)["count"])

    def test_todays_unfinished_bar_is_left_out(self):
        changes, volumes = [0.1] * 30, [100.0] * 30
        changes[-1], volumes[-1] = -1.0, 150.0     # 오늘(10월 29일) 장중 — 아직 안 끝남
        frame = _dist_frame(changes, volumes)
        during = pd.Timestamp("2026-10-29 11:00", tz="Asia/Seoul").to_pydatetime()
        dist = jarvis13_market.distribution_days(frame, now=during)
        self.assertEqual(0, dist["count"])
        self.assertEqual("2026-10-28", dist["last_day"])
        self.assertEqual(1, jarvis13_market.distribution_days(frame, now=self.AFTER_CLOSE)["count"])

    def test_no_volume_or_too_short_gives_none(self):
        frame = _dist_frame([0.1] * 30, [0.0] * 30)
        frame["Volume"] = 0.0
        self.assertIsNone(jarvis13_market.distribution_days(frame, now=self.AFTER_CLOSE))
        self.assertIsNone(jarvis13_market.distribution_days(_dist_frame([0.1] * 10, [100.0] * 10), now=self.AFTER_CLOSE))
        self.assertIsNone(jarvis13_market.distribution_days(None))

    def test_episode_carries_it_and_survives_its_failure(self):
        def _clear():
            with j4data._CACHE_LOCK:
                for key in [k for k in j4data._CACHE if isinstance(k, tuple) and k[0] == "j13_index_episode"]:
                    j4data._CACHE.pop(key, None)
            jarvis13_market._FAILED_AT.clear()
        _clear()
        self.addCleanup(_clear)                             # 다른 시험에 가짜 값이 남지 않게
        frame = _frame()
        with patch("jarvis4_data._index_frame", return_value=frame), \
                patch.object(jarvis13_market, "distribution_days", side_effect=RuntimeError("셈 실패")):
            ep = jarvis13_market.episode("KOSPI")
        self.assertTrue(ep["ok"])                           # 분산일을 못 세도 「이번 하락」 값은 그대로
        self.assertIsNone(ep["dist"])
        self.assertAlmostEqual(-20.0, ep["drop"], places=6)

    def test_page_line_shows_count_and_dates_without_a_warning_color(self):
        body = PAGE[PAGE.index("def _render_kospi_drawdown"):PAGE.index("def _render_theme_table")]
        line = body[body.index("dist = ep.get(\"dist\")"):body.index("except Exception:\n        episode_line")]
        self.assertIn("🧮 <b>분산일</b>(코스피", line)
        self.assertIn("코스피로는 아직 재지 않았고", line)
        self.assertIn("점수·판정에 안 씀", line)
        self.assertIn("white-space:nowrap", line)          # 「7일」이 「7」 「일」로 갈라지지 않게(폰)
        self.assertNotIn("color:", line)                   # 문턱을 재기 전에는 색으로 경고하지 않는다


if __name__ == "__main__":
    unittest.main()

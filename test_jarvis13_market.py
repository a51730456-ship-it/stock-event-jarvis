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
        self.assertIn("+ episode_line + kosdaq_line +", body)
        self.assertIn("except Exception:\n        episode_line = kosdaq_line = \"\"", body)
        self.assertIn("_REQUIRED_J13_MARKET_REVISION = 2026103002", PAGE)


if __name__ == "__main__":
    unittest.main()

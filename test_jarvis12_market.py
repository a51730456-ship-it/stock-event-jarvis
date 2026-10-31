"""자비스12 시장분석 「🧮 분산일」(2026-10-31 상하님 「넣어라」)."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import jarvis12_market as market
import jarvis13_market

PAGE = Path(__file__).resolve().parent / "pages" / "11_자비스12.py"


def _frame(days: int = 80, seed: int = 3):
    rng = np.random.default_rng(seed)
    index = pd.bdate_range("2026-07-01", periods=days)
    close = 18000 * np.exp(np.cumsum(rng.normal(0, 0.012, days)))
    volume = rng.lognormal(21, 0.3, days)
    return pd.DataFrame({"Close": close, "Volume": volume}, index=index)


class CountTests(unittest.TestCase):
    def test_same_count_as_the_measured_rule(self):
        far = pd.Timestamp("2100-01-01 16:00", tz="Asia/Seoul").to_pydatetime()
        for seed in range(6):
            frame = _frame(seed=seed)
            mine = market.distribution_days(frame, now=datetime(2100, 1, 1, tzinfo=timezone.utc))
            measured = jarvis13_market.distribution_days(frame, now=far)       # 12년치 재기가 쓴 셈
            self.assertEqual(measured["count"], mine["count"])
            self.assertEqual(measured["dates"], mine["dates"])

    def test_todays_unfinished_bar_is_left_out(self):
        frame = _frame()
        last = frame.index[-1]
        during = datetime(last.year, last.month, last.day, 15, 0, tzinfo=market.NY)    # 장중
        after = datetime(last.year, last.month, last.day, 17, 0, tzinfo=market.NY)     # 장 끝난 뒤
        self.assertEqual(str(frame.index[-2].date()), market.distribution_days(frame, now=during)["last_day"])
        self.assertEqual(str(last.date()), market.distribution_days(frame, now=after)["last_day"])

    def test_no_volume_or_short_data_gives_nothing(self):
        self.assertIsNone(market.distribution_days(_frame().assign(Volume=0.0)))
        self.assertIsNone(market.distribution_days(_frame(days=20)))
        self.assertIsNone(market.distribution_days(None))


class LineTests(unittest.TestCase):
    def test_line_says_counts_and_that_it_is_not_a_warning(self):
        text = market.line_html({"count": 4}, {"count": 6})
        for word in ("🧮 분산일", "나스닥 종합 <b style='white-space:nowrap'>4일</b>", "S&amp;P 500", "6일",
                     "+3.6%", "+2.6%", "18%", "13%", "경고로 쓰지 않고 점수·판정에 안 씀"):
            self.assertIn(word, text)
        self.assertEqual("", market.line_html(None, None))
        self.assertNotIn("S&amp;P 500 <b", market.line_html({"count": 1}, None))


class PageTests(unittest.TestCase):
    def test_line_sits_under_the_nasdaq_gauge_and_guard_matches(self):
        source = PAGE.read_text(encoding="utf-8")
        self.assertIn(f"_REQUIRED_J12_MARKET_REVISION = {market.MODULE_REVISION}", source)
        body = source.split("def _render_nasdaq_drawdown(")[1].split("\ndef ")[0]
        self.assertIn("+ episode_line + ixic_line + dist_line +", body)
        self.assertNotIn("jarvis13", body)                   # 자비스13 파일을 부르지 않는다


if __name__ == "__main__":
    unittest.main()

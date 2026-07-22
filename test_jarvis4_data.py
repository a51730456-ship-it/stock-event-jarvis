"""자비스4(한국 테마) 엔진 테스트 — 네트워크 없이 순수 판정 로직만 검증한다."""

import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pandas as pd

import jarvis4_data as j4

SEOUL = ZoneInfo("Asia/Seoul")


def _daily_frame(start=100_000.0, slope=200.0, periods=260):
    index = pd.bdate_range("2025-07-01", periods=periods)
    close = pd.Series([start + slope * i for i in range(periods)], index=index)
    return pd.DataFrame(
        {
            "Open": close - 300,
            "High": close + 800,
            "Low": close - 800,
            "Close": close,
            "Volume": 500_000.0,
        },
        index=index,
    )


def _flow(net5_amount=50e8, streak=3, ok=True):
    return {
        "ok": ok, "net5_amount": net5_amount, "buy_streak_days": streak,
        "net20_amount": net5_amount * 3, "rows": [],
    }


class TickSizeTests(unittest.TestCase):
    """호가단위 — 기준가가 실제 주문 가능한 가격이어야 한다."""

    def test_tick_size_follows_krx_table(self):
        self.assertEqual(j4.tick_size(1_500), 1)
        self.assertEqual(j4.tick_size(3_000), 5)
        self.assertEqual(j4.tick_size(15_000), 10)
        self.assertEqual(j4.tick_size(30_000), 50)
        self.assertEqual(j4.tick_size(150_000), 100)
        self.assertEqual(j4.tick_size(300_000), 500)
        self.assertEqual(j4.tick_size(1_900_000), 1_000)

    def test_round_to_tick_produces_orderable_price(self):
        self.assertEqual(j4.round_to_tick(1_990_333), 1_990_000)
        self.assertEqual(j4.round_to_tick(148_777), 148_800)
        self.assertIsNone(j4.round_to_tick(None))
        self.assertIsNone(j4.round_to_tick(0))


class MarketPhaseTests(unittest.TestCase):
    def test_regular_session_label(self):
        weekday_noon = datetime(2026, 7, 22, 12, 0, tzinfo=SEOUL)
        self.assertEqual(j4.market_phase(weekday_noon)["label"], "정규장")
        self.assertTrue(j4.is_regular_session(weekday_noon))

    def test_weekend_is_not_open(self):
        saturday = datetime(2026, 7, 25, 12, 0, tzinfo=SEOUL)
        self.assertEqual(j4.market_phase(saturday)["label"], "주말 휴장")
        self.assertFalse(j4.is_regular_session(saturday))

    def test_pre_market_auction_label(self):
        auction = datetime(2026, 7, 22, 8, 45, tzinfo=SEOUL)
        self.assertEqual(j4.market_phase(auction)["label"], "장전 동시호가")


class SeriesMetricsTests(unittest.TestCase):
    def test_metrics_compute_trend_and_atr(self):
        metrics = j4._series_metrics(_daily_frame())
        self.assertTrue(metrics["ok"])
        self.assertGreater(metrics["current"], metrics["sma20"])
        self.assertGreater(metrics["sma20"], metrics["sma50"])
        self.assertIsNotNone(metrics["from_high_pct"])
        self.assertGreater(metrics["atr_pct"], 0)
        self.assertGreater(metrics["avg_trading_value"], 0)

    def test_short_history_is_rejected(self):
        self.assertFalse(j4._series_metrics(_daily_frame(periods=10)).get("ok"))
        self.assertFalse(j4._series_metrics(None).get("ok"))


class StockScoreTests(unittest.TestCase):
    def test_flow_score_is_normalized_by_trading_value(self):
        """대형주가 순매수 '금액'만으로 항상 만점이 되면 안 된다(2026-07-22 실측 편향)."""
        metrics = j4._series_metrics(_daily_frame())
        big = dict(metrics, avg_trading_value=1e12)   # 초대형주
        small = dict(metrics, avg_trading_value=1e9)  # 소형주
        same_amount = _flow(net5_amount=100e8, streak=0)
        big_score, big_parts = j4._stock_score(big, dict(same_amount), 0.0)
        small_score, small_parts = j4._stock_score(small, dict(same_amount), 0.0)
        # 같은 금액이면 거래대금이 작은 쪽이 수급 강도가 더 크다.
        self.assertGreater(small_parts[5], big_parts[5])

    def test_missing_flow_scores_zero_not_crash(self):
        metrics = j4._series_metrics(_daily_frame())
        score, parts = j4._stock_score(metrics, {"ok": False}, 0.0)
        self.assertEqual(parts[5], 0.0)
        self.assertGreaterEqual(score, 0)

    def test_score_has_six_parts_summing_to_hundred_max(self):
        metrics = j4._series_metrics(_daily_frame())
        score, parts = j4._stock_score(metrics, _flow(), 0.0)
        self.assertEqual(len(parts), 6)
        self.assertLessEqual(score, 100.0)
        self.assertGreaterEqual(score, 0.0)

    def test_daily_limit_up_is_penalized(self):
        metrics = dict(j4._series_metrics(_daily_frame()), change_pct=25.0)
        penalized, _ = j4._stock_score(metrics, _flow(), 0.0)
        normal, _ = j4._stock_score(dict(metrics, change_pct=1.0), _flow(), 0.0)
        self.assertLess(penalized, normal)


class EntryPlanTests(unittest.TestCase):
    def test_chase_block_on_daily_surge(self):
        metrics = dict(j4._series_metrics(_daily_frame()), change_pct=22.0)
        plan = j4._entry_plan(metrics, 90, 80, 80)
        self.assertEqual(plan["state"], "추격 금지")
        self.assertIsNone(plan["trigger"])

    def test_chase_block_on_five_day_surge(self):
        metrics = dict(j4._series_metrics(_daily_frame()), ret5=30.0)
        self.assertEqual(j4._entry_plan(metrics, 90, 80, 80)["state"], "추격 금지")

    def test_prices_are_rounded_to_tick(self):
        metrics = j4._series_metrics(_daily_frame())
        plan = j4._entry_plan(metrics, 85, 80, 80)
        for key in ("trigger", "zone_high", "invalidation", "target"):
            value = plan.get(key)
            if value is not None:
                self.assertEqual(value % j4.tick_size(value), 0, f"{key}가 호가단위가 아닙니다")

    def test_market_gate_blocks_even_with_high_score(self):
        metrics = j4._series_metrics(_daily_frame())
        plan = j4._entry_plan(metrics, 95, market_score=30, theme_score=90)
        self.assertNotEqual(plan["recommendation"], "조건부 후보")
        self.assertIn("방어", plan["buy_reason"])


class ExclusionTests(unittest.TestCase):
    def test_spac_and_preferred_shares_excluded(self):
        self.assertTrue(j4._is_excluded("미래에셋스팩5호", "123456"))
        self.assertTrue(j4._is_excluded("삼성전자우", "005935"))
        self.assertTrue(j4._is_excluded("현대차2우B", "005387"))
        self.assertFalse(j4._is_excluded("삼성전자", "005930"))


class ThemeScoreTests(unittest.TestCase):
    def _stocks(self, changes):
        # 거래대금은 실제 주도 테마 수준(종목당 500억)으로 둔다 — 점수의 20점이
        # 거래대금 항목이라 비현실적으로 작으면 주도 판정이 나오지 않는다.
        return [
            {"code": f"00000{i}", "name": f"종목{i}", "price": 10_000,
             "change_pct": change, "volume": 5_000_000, "trading_value": 5e10}
            for i, change in enumerate(changes)
        ]

    def test_strong_theme_scores_higher_than_weak(self):
        strong = j4._theme_score(self._stocks([5.0, 4.0, 6.0, 3.5]), 4.6, 0.5)
        weak = j4._theme_score(self._stocks([-2.0, 0.5, -1.0, 0.2]), -0.6, 0.5)
        self.assertTrue(strong["ok"] and weak["ok"])
        self.assertGreater(strong["score"], weak["score"])
        self.assertEqual(strong["status"], "주도")

    def test_empty_stock_list_is_not_ok(self):
        self.assertFalse(j4._theme_score([], 1.0, 0.5).get("ok"))


class StockFlowParsingTests(unittest.TestCase):
    def test_parses_naver_flow_table(self):
        html = (
            '<span class="tah p10 gray03">2026.07.21</span>'
            '<td><span>1,836,000</span></td><td><span>4,639,208</span></td>'
            '<td><span>+366,154</span></td><td><span>-237,417</span></td></tr>'
        )
        rows = j4._parse_stock_flow(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["institution_net"], 366_154)
        self.assertEqual(rows[0]["foreign_net"], -237_417)

    def test_layout_change_returns_no_rows_instead_of_wrong_values(self):
        self.assertEqual(j4._parse_stock_flow("<html>구조 변경</html>"), [])

    def test_flow_failure_returns_not_ok(self):
        with patch.object(j4, "_get_text", side_effect=RuntimeError("network")):
            j4.clear_runtime_cache()
            result = j4.get_stock_flow("000660")
        self.assertFalse(result["ok"])
        self.assertEqual(result["rows"], [])


if __name__ == "__main__":
    unittest.main()

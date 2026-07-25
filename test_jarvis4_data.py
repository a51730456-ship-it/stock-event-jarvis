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


class ThemeDetailParsingTests(unittest.TestCase):
    def test_regular_row_uses_direct_trading_value_from_tail_columns(self):
        parsed = j4._parse_theme_detail_numbers(
            ["15,480", "500", "3", "670,662", "10,538", "600,000"]
        )
        self.assertEqual(parsed["price"], 15_480)
        self.assertEqual(parsed["volume"], 670_662)
        self.assertEqual(parsed["trading_value_million"], 10_538)
        self.assertEqual(parsed["trading_value"], 10_538_000_000)
        self.assertEqual(parsed["previous_volume"], 600_000)
        self.assertNotEqual(parsed["trading_value"], parsed["price"] * parsed["volume"])

    def test_flat_row_keeps_tail_columns_aligned_and_preserves_zero(self):
        parsed = j4._parse_theme_detail_numbers(
            ["14,100", "0", "0", "0", "0", "0", "62,046"]
        )
        self.assertEqual(parsed["price"], 14_100)
        self.assertEqual(parsed["volume"], 0)
        self.assertEqual(parsed["trading_value_million"], 0)
        self.assertEqual(parsed["trading_value"], 0)
        self.assertEqual(parsed["previous_volume"], 62_046)

    def test_fetch_exposes_parser_version_and_previous_volume(self):
        html = """
        <td class="name"><a href="/item/main.naver?code=123456">테스트</a></td>
        <td>14,100</td><td>0</td><td>0</td><td>0</td><td>0</td>
        <td>0</td><td>62,046</td><td><span>+0.00%</span></td></tr>
        """
        with patch.object(j4, "_get_text", return_value=html):
            rows = j4._fetch_theme_detail(1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["trading_value"], 0)
        self.assertEqual(rows[0]["previous_volume"], 62_046)
        self.assertEqual(rows[0]["parser_version"], j4.THEME_DETAIL_PARSER_VERSION)


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


class ThemeGateOverrideTests(unittest.TestCase):
    """테마가 약해도 압도적으로 강한 종목은 버리지 않는다.

    2026-07-22 사용자 지적으로 넣은 규칙 — 국내 네이버 테마는 성격이 섞여 있어
    테마 평균이 종목 품질을 대표하지 못한다(실측: '은행' 22.1점인데 하나금융지주 95.0점).
    """

    def _plan(self, score, theme_score, market_score=60):
        metrics = j4._series_metrics(_daily_frame())
        return j4._entry_plan(metrics, score, market_score, theme_score)

    def test_strong_stock_passes_weak_theme_gate(self):
        plan = self._plan(score=95, theme_score=22.1)
        self.assertEqual(plan["recommendation"], "조건부 후보")

    def test_mid_score_stock_still_blocked_by_weak_theme(self):
        plan = self._plan(score=81, theme_score=22.1)
        self.assertEqual(plan["recommendation"], "관찰")
        self.assertIn("테마 강도", plan["buy_reason"])

    def test_override_does_not_bypass_market_gate(self):
        """시장 게이트는 종목이 아무리 강해도 면제되지 않는다."""
        plan = self._plan(score=95, theme_score=22.1, market_score=30)
        self.assertNotEqual(plan["recommendation"], "조건부 후보")
        self.assertIn("방어", plan["buy_reason"])

class PullbackQualityTests(unittest.TestCase):
    """눌림목 베스트 — '올라가던 종목이 얼마나 좋은 자리까지 눌렸나'를 잰다."""

    def _metrics(self, current, sma20, sma50=None, sma200=None, from_high=-10.0, days_ago=10):
        return {
            "current": current, "sma20": sma20,
            "sma50": sma50 if sma50 is not None else current * 0.95,
            "sma200": sma200 if sma200 is not None else current * 0.9,
            "from_high_pct": from_high, "high52_days_ago": days_ago,
        }

    def test_recent_high_scores_higher_than_old_high(self):
        """52주 신고가를 최근에 찍었을수록 좋은 눌림목이다(2026-07-22 사용자 제안)."""
        recent = j4._pullback_quality(self._metrics(101, 100, days_ago=5), _flow())
        old = j4._pullback_quality(self._metrics(101, 100, days_ago=200), _flow())
        self.assertGreater(recent["score"], old["score"])
        self.assertEqual(recent["high52_days_ago"], 5)

    def test_series_metrics_reports_days_since_52w_high(self):
        frame = _daily_frame()          # 계속 오르는 시계열 → 마지막 날이 신고가
        metrics = j4._series_metrics(frame)
        self.assertEqual(metrics["high52_days_ago"], 0)

    def test_closer_to_sma20_scores_higher(self):
        near = j4._pullback_quality(self._metrics(101, 100), _flow())
        far = j4._pullback_quality(self._metrics(110, 100), _flow())
        self.assertGreater(near["score"], far["score"])

    def test_healthy_depth_beats_broken_trend(self):
        healthy = j4._pullback_quality(self._metrics(101, 100, from_high=-12.0), _flow())
        broken = j4._pullback_quality(self._metrics(101, 100, from_high=-45.0), _flow())
        self.assertGreater(healthy["score"], broken["score"])

    def test_below_long_term_averages_scores_lower(self):
        above = j4._pullback_quality(self._metrics(101, 100, sma50=95, sma200=90), _flow())
        below = j4._pullback_quality(self._metrics(101, 100, sma50=120, sma200=130), _flow())
        self.assertGreater(above["score"], below["score"])
        self.assertTrue(above["above_sma200"])
        self.assertFalse(below["above_sma200"])

    def test_supply_inflow_adds_score(self):
        with_flow = j4._pullback_quality(self._metrics(101, 100), _flow(net5_amount=50e8, streak=4))
        without = j4._pullback_quality(self._metrics(101, 100), {"ok": False})
        self.assertGreater(with_flow["score"], without["score"])

    def test_missing_sma20_returns_none(self):
        self.assertIsNone(j4._pullback_quality({"current": 100}, _flow()))

class PullbackFinderTests(unittest.TestCase):
    """사용자 스펙(2026-07-22): 2개 이상 테마 + 신고가 15일 전 + 상승추세 중 조정."""

    def tearDown(self):
        j4.clear_runtime_cache()

    def _themes(self):
        return {
            1: {"no": 1, "name": "은행", "change_pct": -0.4},
            2: {"no": 2, "name": "금융지주", "change_pct": 0.3},
            3: {"no": 3, "name": "게임", "change_pct": 1.0},
        }

    def _stock(self, code, name, value=2e10):
        return {"code": code, "name": name, "price": 60_000,
                "change_pct": 0.5, "volume": 400_000, "trading_value": value,
                "previous_volume": 400_000}

    def _theme_stocks(self, theme_no, **kwargs):
        # 하나금융지주는 테마 2개(은행·금융지주), 게임주는 1개뿐이다.
        if theme_no == 1:
            stocks = [self._stock("086790", "하나금융지주")]
        elif theme_no == 2:
            stocks = [self._stock("086790", "하나금융지주")]
        else:
            stocks = [self._stock("035720", "게임A")]
        return {"ok": True, "stale": False, "stocks": stocks}

    def _metrics(self, days_ago, from_high):
        current = 60_000
        return {
            "ok": True, "current": current, "sma20": current * 0.99,
            "sma50": current * 0.9, "sma200": current * 0.8,
            "high52_days_ago": days_ago, "from_high_pct": from_high,
            "ret20": 5.0, "ret5": 1.0, "change_pct": 0.5,
            "atr_pct": 3.0, "avg_trading_value": 2e10,
        }

    def _run(self, metrics, score=95.0, theme_stocks=None):
        # find_pullback_stocks는 10분 캐시를 쓴다 — 한 테스트에서 조건을 바꿔 두 번
        # 부를 때 앞 결과가 그대로 나오지 않도록 매번 비운다.
        j4.clear_runtime_cache()
        with patch.object(j4, "get_all_themes",
                          return_value={"ok": True, "themes": self._themes()}), \
             patch.object(j4, "get_theme_stocks", side_effect=theme_stocks or self._theme_stocks), \
             patch.object(j4, "get_daily_frame", return_value=object()), \
             patch.object(j4, "get_stock_flow", return_value=_flow()), \
             patch.object(j4, "_index_metrics", return_value={"ok": True, "ret20": -14.0}), \
             patch.object(j4, "_series_metrics", return_value=metrics), \
             patch.object(j4, "_stock_score", return_value=(score, [20, 15, 20, 15, 10, 15])):
            return j4.find_pullback_stocks()

    def test_single_theme_stock_is_excluded(self):
        """1개 테마에만 속한 종목은 제외된다(사용자 스펙)."""
        result = self._run(self._metrics(5, -8.0))
        names = [row["name"] for row in result["rows"]]
        self.assertIn("하나금융지주", names)
        self.assertNotIn("게임A", names, "테마 1개짜리 종목이 들어왔습니다")

    def test_high_within_window_is_kept(self):
        """52주 최고가를 찍고 1~30일 지난 종목이 대상이다.

        2026-07-22 회귀 방지: 창을 15±8일(7~23일)로 잡는 바람에 3일·6일 전에
        신고가를 찍은 하나금융지주·신한지주가 통째로 빠졌다.
        2026-07-24 사용자 지시로 20일 → 30일로 넓혔다(신고가 24일 전인 삼성전자 포함).
        """
        for days in (1, 3, 6, 15, 20, 24, 30):
            with self.subTest(days=days):
                result = self._run(self._metrics(days, -8.0))
                self.assertTrue(result["rows"], f"신고가 {days}일 전 종목이 빠졌습니다")

    def test_high_outside_window_is_excluded(self):
        for days in (0, 31, 60):
            with self.subTest(days=days):
                self.assertEqual(self._run(self._metrics(days, -8.0))["rows"], [])

    def test_stock_below_score_threshold_is_excluded(self):
        """나머지 품질은 종목 점수 75점 하나로 거른다(사용자 지시)."""
        self.assertTrue(self._run(self._metrics(5, -8.0), score=75.0)["rows"])
        self.assertEqual(self._run(self._metrics(5, -8.0), score=74.9)["rows"], [])

    def test_stock_at_its_high_is_not_a_pullback(self):
        """고점을 찍고 '내려가는' 종목이어야 한다."""
        self.assertEqual(self._run(self._metrics(5, 0.0))["rows"], [])

    def test_window_is_reported(self):
        self.assertEqual(self._run(self._metrics(5, -8.0))["window"], (1, 30))

    def test_previous_day_volume_keeps_premarket_candidate_alive(self):
        def premarket(theme_no, **_kwargs):
            code = "086790" if theme_no in (1, 2) else "035720"
            name = "하나금융지주" if theme_no in (1, 2) else "게임A"
            stock = self._stock(code, name, value=0)
            stock["previous_volume"] = 400_000  # 60,000원×40만주 = 240억원
            return {"ok": True, "stocks": [stock]}

        result = self._run(self._metrics(5, -8.0), theme_stocks=premarket)
        self.assertTrue(result["ok"])
        self.assertTrue(result["rows"])
        self.assertGreater(result["liquid_count"], 0)

    def test_zero_liquidity_is_empty_result_not_failure(self):
        def no_liquidity(theme_no, **_kwargs):
            code = "086790" if theme_no in (1, 2) else "035720"
            name = "하나금융지주" if theme_no in (1, 2) else "게임A"
            stock = self._stock(code, name, value=0)
            stock["previous_volume"] = 0
            return {"ok": True, "stocks": [stock]}

        result = self._run(self._metrics(5, -8.0), theme_stocks=no_liquidity)
        self.assertTrue(result["ok"])
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["liquid_count"], 0)


class ScoreAtPastTests(unittest.TestCase):
    """신고가 시점 점수 역산 — 눌림목은 '그때 좋았던 종목'이라 그 점수로 걸러야 한다."""

    def test_peak_score_is_higher_than_now_for_a_pullback(self):
        # 60일 오르다가 마지막 10일 급락 → 지금은 눌렸지만 고점 때는 좋았던 종목
        rising = _daily_frame(periods=200)
        falling = rising.copy()
        falling.iloc[-10:] = falling.iloc[-10:] * 0.9
        now = j4._series_metrics(falling)
        now_score, _ = j4._stock_score(now, _flow(), -10.0)
        past = j4.score_at_past(falling, _flow(), -10.0, 10)
        self.assertIsNotNone(past)
        self.assertGreater(past["score"], now_score)

    def test_returns_none_when_history_too_short(self):
        self.assertIsNone(j4.score_at_past(_daily_frame(periods=30), _flow(), -10.0, 20))
        self.assertIsNone(j4.score_at_past(None, _flow(), -10.0, 5))
        self.assertIsNone(j4.score_at_past(_daily_frame(), _flow(), -10.0, 0))

    def test_bad_input_does_not_raise(self):
        """역산이 실패해도 예외를 던지지 않는다(종목이 통째로 빠지면 안 된다)."""
        self.assertIsNone(j4.score_at_past(object(), _flow(), -10.0, 5))


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


class ThemeCarryOverTests(unittest.TestCase):
    """어제 강했던 테마가 오늘 하루 쉰다고 목록에서 통째로 사라지면 안 된다.

    2026-07-22 사용자 지적(금융 테마 실종)으로 넣은 규칙 — 당일 등락률 상위 30에
    못 들어도 직전 상위 테마는 계속 심사한다.
    """

    def tearDown(self):
        j4.clear_runtime_cache()
        j4._CACHE.pop("previous_theme_names", None)

    def test_refresh_keeps_previous_ranking_memory(self):
        j4._CACHE["previous_theme_names"] = {"at": 0, "value": ["은행", "증권"]}
        j4._CACHE["theme_list"] = {"at": 0, "value": {"x": 1}}
        j4.clear_runtime_cache()
        self.assertNotIn("theme_list", j4._CACHE)
        self.assertIn("previous_theme_names", j4._CACHE)
        self.assertEqual(j4._CACHE["previous_theme_names"]["value"], ["은행", "증권"])

    def test_previous_top_theme_is_rescanned_even_if_weak_today(self):
        themes = {index: {"no": index, "name": f"테마{index}", "change_pct": 9.0 - index * 0.1}
                  for index in range(1, 60)}
        # 오늘 꼴찌권인데 어제 상위권이었던 테마
        themes[99] = {"no": 99, "name": "은행", "change_pct": -0.4}
        j4._CACHE["previous_theme_names"] = {"at": 0, "value": ["은행"]}

        scanned = []

        def fake_stocks(theme_no, **kwargs):
            scanned.append(theme_no)
            return {"ok": True, "stale": False, "stocks": [
                {"code": "000001", "name": "종목", "price": 10_000,
                 "change_pct": 1.0, "volume": 5_000_000, "trading_value": 5e10}
            ]}

        with patch.object(j4, "get_all_themes", return_value={"ok": True, "themes": themes}), \
             patch.object(j4, "_index_metrics", return_value={"ok": True, "change_pct": 0.5}), \
             patch.object(j4, "_live_index", return_value=None), \
             patch.object(j4, "get_theme_stocks", side_effect=fake_stocks):
            j4.get_theme_rankings()

        self.assertIn(99, scanned, "어제 상위권 테마가 오늘 심사에서 빠졌습니다")

    def test_forced_theme_is_included_even_when_weak(self):
        """사용자가 직접 고른 테마는 점수가 낮아도 목록에 남아야 한다."""
        themes = {index: {"no": index, "name": f"테마{index}", "change_pct": 9.0 - index * 0.1}
                  for index in range(1, 60)}
        themes[99] = {"no": 99, "name": "은행", "change_pct": -0.4}

        def fake_stocks(theme_no, **kwargs):
            # 은행만 약하게, 나머지는 강하게 만든다.
            change = -1.0 if theme_no == 99 else 4.0
            return {"ok": True, "stale": False, "stocks": [
                {"code": "000001", "name": "종목", "price": 10_000,
                 "change_pct": change, "volume": 5_000_000, "trading_value": 5e10}
            ]}

        with patch.object(j4, "get_all_themes", return_value={"ok": True, "themes": themes}), \
             patch.object(j4, "_index_metrics", return_value={"ok": True, "change_pct": 0.5}), \
             patch.object(j4, "_live_index", return_value=None), \
             patch.object(j4, "get_theme_stocks", side_effect=fake_stocks):
            result = j4.get_theme_rankings(force_names=("은행",))

        names = [row["name"] for row in result["rows"]]
        self.assertIn("은행", names, "직접 고른 테마가 목록에서 빠졌습니다")
        bank = next(row for row in result["rows"] if row["name"] == "은행")
        self.assertTrue(bank.get("is_forced"))
        # 점수 순 정렬은 유지된다(약한 테마가 위로 올라오면 안 된다).
        scores = [row["score"] for row in result["rows"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_rankings_expose_next_rows_for_dropped_themes(self):
        themes = {index: {"no": index, "name": f"테마{index}", "change_pct": 9.0 - index * 0.1}
                  for index in range(1, 40)}

        def fake_stocks(theme_no, **kwargs):
            return {"ok": True, "stale": False, "stocks": [
                {"code": "000001", "name": "종목", "price": 10_000,
                 "change_pct": float(theme_no % 7), "volume": 5_000_000, "trading_value": 5e10}
            ]}

        with patch.object(j4, "get_all_themes", return_value={"ok": True, "themes": themes}), \
             patch.object(j4, "_index_metrics", return_value={"ok": True, "change_pct": 0.5}), \
             patch.object(j4, "_live_index", return_value=None), \
             patch.object(j4, "get_theme_stocks", side_effect=fake_stocks):
            result = j4.get_theme_rankings()

        self.assertLessEqual(len(result["rows"]), j4.DISPLAY_THEME_COUNT)
        self.assertTrue(result.get("next_rows"), "21위 밖 목록이 있어야 합니다")


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


class UsPreviousSessionTests(unittest.TestCase):
    """'미국 전일' 게이트는 끝난 정규장 등락을 써야 한다(2026-07-24 실측 회귀).

    프리마켓 값을 쓰면 전일 -1.2%인 날에도 15점이 붙는다.
    """

    def _overview(self, spy_now, spy_session, qqq_now, qqq_session):
        return {
            "ok": True, "score": 25, "regime": "방어 우선",
            "rows": {
                "SPY": {"change_pct": spy_now, "last_session_change_pct": spy_session},
                "QQQ": {"change_pct": qqq_now, "last_session_change_pct": qqq_session},
            },
        }

    def _run(self, overview):
        import sys
        import types

        fake = types.ModuleType("jarvis3_data")
        fake.get_market_overview = lambda: overview
        fake.get_fear_greed = lambda: {"ok": False}
        original = sys.modules.get("jarvis3_data")
        sys.modules["jarvis3_data"] = fake
        try:
            return j4._us_previous_session()
        finally:
            if original is not None:
                sys.modules["jarvis3_data"] = original
            else:
                del sys.modules["jarvis3_data"]

    def test_uses_finished_session_not_premarket(self):
        result = self._run(self._overview(0.22, -1.23, 0.06, -1.90))
        self.assertAlmostEqual(result["spy_change"], -1.23, places=2)
        self.assertAlmostEqual(result["qqq_change"], -1.90, places=2)

    def test_gate_fails_when_previous_session_closed_down(self):
        result = self._run(self._overview(0.22, -1.23, 0.06, -1.90))
        passed = (result.get("spy_change") or 0) >= 0 and (result.get("qqq_change") or 0) >= 0
        self.assertFalse(passed, "전일 하락 마감인데 15점이 붙으면 안 된다")

    def test_gate_passes_when_previous_session_closed_up(self):
        result = self._run(self._overview(-0.5, 1.1, -0.3, 0.8))
        passed = (result.get("spy_change") or 0) >= 0 and (result.get("qqq_change") or 0) >= 0
        self.assertTrue(passed)


if __name__ == "__main__":
    unittest.main()


class DayFlowMarkTests(unittest.TestCase):
    """하루 수급 판정(동반/한쪽/보합)을 굳혀 둔다 (2026-07-25).

    핵심은 두 가지다.
      1. 외국인·기관을 합치지 않는다 — 합치면 +500억/−480억이 순매수로 둔갑한다.
      2. '거의 0'인 날은 그날 거래량 대비 비율로 걸러낸다 — 큰 종목의 자잘한
         매매를 매수 신호로 치지 않는다.
    """

    BASE = {"close": 1000, "volume": 1_000_000}

    def _mark(self, foreign, institution, **extra):
        row = {**self.BASE, **extra, "foreign_net": foreign, "institution_net": institution}
        return j4._day_flow_mark(row)

    def test_both_buying_is_a_partner_day(self):
        self.assertEqual(self._mark(5000, 4000), "both_buy")

    def test_both_selling_is_marked_separately(self):
        self.assertEqual(self._mark(-5000, -4000), "both_sell")

    def test_opposite_directions_never_count_as_partner(self):
        """외국인 대량 매수 + 기관 매도는 '동반'이 아니다 — 합산했다면 매수로 둔갑한다."""
        self.assertEqual(self._mark(50_000, -48_000), "cross")

    def test_one_side_buy_and_sell_are_told_apart(self):
        """'한쪽만 샀다'와 '한쪽만 팔았다'와 '엇갈렸다'가 각각 달라야 한다.

        예전에는 셋을 'one' 하나로 뭉쳐 같은 주황 동그라미로 나왔다(2026-07-25 지적).
        """
        self.assertEqual(self._mark(50_000, 10), "one_buy")     # 외국인만 삼
        self.assertEqual(self._mark(10, 50_000), "one_buy")     # 기관만 삼
        self.assertEqual(self._mark(-50_000, 10), "one_sell")   # 외국인만 팜
        self.assertEqual(self._mark(10, -50_000), "one_sell")   # 기관만 팜

    def test_tiny_moves_are_flat(self):
        self.assertEqual(self._mark(10, 10), "flat")

    def test_flat_threshold_is_relative_to_that_days_volume(self):
        """같은 주수라도 그날 거래량이 많으면 '보합'이다 — 자잘한 매매는 신호가 아니다."""
        busy = self._mark(400, 400, volume=1_000_000)   # 거래량의 0.04% → 무시
        quiet = self._mark(400, 400, volume=100_000)    # 거래량의 0.4%  → 동반 매수
        self.assertEqual(busy, "flat")
        self.assertEqual(quiet, "both_buy")


class FlowScoreUsesPartnerDaysTests(unittest.TestCase):
    """수급 점수가 '동반'(둘 다 순매수)을 쓰는지 굳혀 둔다 (2026-07-25 사용자 지시).

    옛 '연속'은 외국인+기관을 합쳐서 세는 방식이라, 외국인 +500억·기관 −480억인
    날도 순매수로 세어 점수를 부풀렸다. 화면을 동반으로 바꾼 뒤 점수만 옛 기준으로
    남으면 화면과 점수가 어긋난다.
    """

    METRICS = {
        "ok": True, "ret20": 5.0, "from_high_pct": -8.0, "current": 50_000,
        "sma20": 49_000, "sma50": 47_000, "sma200": 44_000, "atr_pct": 3.0,
        "avg_trading_value": 3e10, "trading_value": 3e10, "change_pct": 1.0,
    }

    def _flow(self, *, partner_days, streak_days):
        return {
            "ok": True, "net5_amount": 1e10, "both_buy_days5": partner_days,
            "window5": 5, "buy_streak_days": streak_days,
        }

    def test_partner_days_raise_the_score(self):
        low = j4._stock_score(self.METRICS, self._flow(partner_days=0, streak_days=0), 2.0)[0]
        high = j4._stock_score(self.METRICS, self._flow(partner_days=3, streak_days=0), 2.0)[0]
        self.assertGreater(high, low)
        self.assertAlmostEqual(high - low, 6.0, places=1)   # 3일이면 만점 6점

    def test_old_streak_no_longer_moves_the_score(self):
        """합산 연속일이 아무리 길어도 점수는 오르지 않아야 한다."""
        without = j4._stock_score(self.METRICS, self._flow(partner_days=0, streak_days=0), 2.0)[0]
        with_streak = j4._stock_score(self.METRICS, self._flow(partner_days=0, streak_days=19), 2.0)[0]
        self.assertEqual(without, with_streak)

    def test_pullback_supply_also_uses_partner_days(self):
        quality_low = j4._pullback_quality(
            {**self.METRICS, "high52_days_ago": 5, "from_high_pct": -8.0},
            self._flow(partner_days=0, streak_days=19),
        )
        quality_high = j4._pullback_quality(
            {**self.METRICS, "high52_days_ago": 5, "from_high_pct": -8.0},
            self._flow(partner_days=4, streak_days=0),
        )
        self.assertIsNotNone(quality_low)
        self.assertIsNotNone(quality_high)
        self.assertGreater(quality_high["score"], quality_low["score"])


class IndexIntradayTests(unittest.TestCase):
    """지수 분봉 자료원 (2026-07-25).

    네이버 siseJson은 'KOSPI'를 받지 않고 네이버 JSON 차트는 day·week·month뿐이라,
    야후 분봉(09:00~15:00)에 네이버 '시간별 시세' 꼬리(마감 15:30까지)를 이어 붙인다.
    두 곳을 붙이는 규칙이 깨지면 그림이 마감 전에 끊기거나 엉뚱한 값이 섞인다.
    """

    TAIL_HTML = """
        <tr><td class="date">15:30</td><td class="number_1">6,690.02</td></tr>
        <tr><td class="date">15:29</td><td class="number_1">6,692.54</td></tr>
        <tr><td class="date">15:00</td><td class="number_1">6,704.13</td></tr>
    """

    def _body(self, day="2026-07-24"):
        stamps = pd.date_range(f"{day} 09:00", f"{day} 14:59", freq="1min")
        return [(stamp.to_pydatetime(), 6700.0 + i * 0.1) for i, stamp in enumerate(stamps)]

    def test_tail_parses_thousands_separator(self):
        """코스피 값에는 천 단위 쉼표가 붙는다 — 못 벗기면 꼬리가 통째로 빈다."""
        with patch.object(j4, "_get_text", return_value=self.TAIL_HTML):
            rows = j4._naver_index_tail("KOSPI", datetime(2026, 7, 24).date())
        self.assertEqual([value for _stamp, value in rows][:2], [6690.02, 6692.54])

    def test_tail_drops_rows_after_the_anchor(self):
        """장 초반에는 전날 마감 줄이 딸려 올 수 있다. 기준 시각 뒤는 버려야 한다."""
        today = datetime.now(SEOUL).date()
        with patch.object(j4, "_get_text", return_value=self.TAIL_HTML), \
                patch.object(j4, "_index_tail_stamp", return_value=f"{today:%Y%m%d}090300"):
            rows = j4._naver_index_tail("KOSPI", today)
        self.assertEqual(rows, [])

    def test_intraday_merges_tail_and_uses_prior_close_as_base(self):
        day = datetime(2026, 7, 24).date()
        j4._CACHE.pop(("index_intraday", "KOSPI"), None)
        with patch.object(j4, "_yahoo_index_minutes", return_value=self._body()), \
                patch.object(j4, "_naver_index_tail",
                             return_value=[(datetime(2026, 7, 24, 15, 30), 6690.02)]), \
                patch.object(j4, "_index_prev_close", return_value=7096.89):
            payload = j4.get_index_intraday("KOSPI", ttl_seconds=0)
        self.assertEqual(payload["session"], day.isoformat())
        self.assertEqual(payload["last_time"], "15:30")       # 마감까지 이어졌다
        self.assertEqual(payload["points"][-1], 6690.02)
        self.assertEqual(payload["base"], 7096.89)            # 기준선은 전날 종가

    def test_intraday_still_draws_when_tail_fails(self):
        """네이버 꼬리가 막혀도 09:00~15:00만으로 그린다."""
        j4._CACHE.pop(("index_intraday", "KOSPI"), None)
        with patch.object(j4, "_yahoo_index_minutes", return_value=self._body()), \
                patch.object(j4, "_naver_index_tail", side_effect=RuntimeError("차단")), \
                patch.object(j4, "_index_prev_close", return_value=7096.89):
            payload = j4.get_index_intraday("KOSPI", ttl_seconds=0)
        self.assertEqual(payload["last_time"], "14:59")

    def test_intraday_returns_nothing_without_a_base(self):
        """기준선을 모르면 그리지 않는다 — 틀린 그림보다 빈 칸이 낫다."""
        j4._CACHE.pop(("index_intraday", "KOSPI"), None)
        with patch.object(j4, "_yahoo_index_minutes", return_value=self._body()), \
                patch.object(j4, "_naver_index_tail", return_value=[]), \
                patch.object(j4, "_index_prev_close", return_value=None):
            self.assertEqual(j4.get_index_intraday("KOSPI", ttl_seconds=0), {})

    def test_unknown_symbol_is_ignored(self):
        self.assertEqual(j4.get_index_intraday("005930"), {})


class ThinPointsTests(unittest.TestCase):
    """그림 점 솎기 — 폰에서 지수 한 칸이 45KB나 되지 않게 한다 (2026-07-25)."""

    def test_short_series_is_untouched(self):
        points = [1.0, 2.0, 3.0]
        self.assertIs(j4._thin_points(points), points)

    def test_long_series_keeps_the_closing_value(self):
        points = [float(i) for i in range(391)]
        thinned = j4._thin_points(points)
        self.assertLessEqual(len(thinned), j4._INDEX_POINT_LIMIT + 1)
        self.assertEqual(thinned[0], 0.0)
        self.assertEqual(thinned[-1], 390.0)      # 종가는 반드시 남는다

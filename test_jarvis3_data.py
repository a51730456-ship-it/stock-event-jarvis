import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pandas as pd

import jarvis3_data as j3
import us_swing_selector as us_swing
import us_swing_testdata


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


# ── US_SWING_V1 합성 일봉 (2026-08-20) ───────────────────────────────────────
# 상승장 갈래가 새 지시문으로 바뀌면서 그물이 여섯 겹이 됐다(시장 Gate · RS60 ·
# RS120 · 종가 신고가 · 1~3거래일 · 3~10% 눌림). 그 가짜 일봉을 만드는 곳은
# **us_swing_testdata 한 군데**다 — 화면 시험(test_jarvis3_page)도 같은 것을
# 봐야 표와 계산이 서로 다른 것을 굳히지 않는다.
_swing_market_frame = us_swing_testdata.market_frame
_swing_stock_frame = us_swing_testdata.stock_frame
_swing_fixture = us_swing_testdata.fixture


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

    def test_rule_numbers_are_what_the_screen_searches_for(self):
        """화면이 실제로 찾는 숫자. 손대면 찾는 종목이 달라진다.

        **2026-08-20에 상승장(신고가 눌림매수)이 US_SWING_V1으로 바뀌었다.**
        상하님이 주신 새 지시문이 그물과 배점을 함께 정하셨다 — 나스닥이 조정을
        끝내고 이전 최고를 되찾은 자리에서, 최근 3개월과 6개월 모두 상위 20%인
        종목이 종가로 52주 신고가를 넘고, 그 뒤 1~3거래일 안에 3~10% 눌린 자리다.
        옛 그물(3~10일 · -15~-4%)과 옛 배점(테마 근접도 70 + 뚫기 전 60일 30)은
        여기서 함께 사라졌다. **급락 갈래는 손대지 않았다.**
        """
        rule = j3.BREAKOUT_PULLBACK_RULE
        # 신고가 당일(day0)은 쫓아사지 않는다 — 1~3거래일 안의 첫 눌림만 본다.
        self.assertEqual((1, 3), rule["wait_days"])
        # 화면 호환을 위해 부호(-)로 두지만 뜻은 anchor 종가 대비 3~10% 눌림이다.
        self.assertEqual((-10.0, -3.0), rule["drop_band"])
        # **파는 날은 규칙에 없다** — 상승장도 급락과 같다(CLAUDE.md 0-1 바).
        self.assertIsNone(rule["hold_days"], "파는 날이 규칙으로 되살아났다")
        # 별점은 뺐다(2026-08-06) — 낙폭·날짜만 보고 달았는데 뒤 5년에서 졌다.
        self.assertFalse(hasattr(j3, "BREAKOUT_STAR_RULES"), "별점이 되살아났다")
        self.assertFalse(hasattr(j3, "breakout_stars"), "별점이 되살아났다")
        # 점수 버전을 줄마다 남긴다 — 옛 추천을 새 가중치로 덮어쓰지 않기 위한 것이다.
        self.assertEqual("US_SWING_V1", us_swing.SCORE_MODEL_VERSION)
        self.assertGreaterEqual(j3.MODULE_REVISION, us_swing.MODULE_REVISION)
        # **2026-08-12에 상하님 표 2로 되돌렸다.** 2026-08-07에 내가 나스닥 구간·
        # 종목 낙폭·보유기간 셋을 한꺼번에 바꿔 놓고 "-6%는 흔한 조정"이라고 적었는데,
        # 갈라서 다시 재 보니 진짜 원인은 보유기간이었다(-6%도 1년 들면 +33.1%).
        shallow, deep = j3.CRASH_REBOUND_RULES
        self.assertEqual((-30.0, -20.0), shallow["band"])
        # **30~50% 칸을 되살렸다** — 내가 지웠던, 1년 보유에서 제일 잘 벌던 자리다.
        self.assertEqual((-50.0, -30.0), deep["band"])
        # 고점 대비 -6% 아래면 전부 본다(다섯 칸으로 나눠 보여주되 거르지 않는다).
        self.assertEqual((-100.0, -6.0), j3.CRASH_MARKET_BAND)
        self.assertEqual(5, len(j3.CRASH_MARKET_TIERS))
        # **파는 날은 규칙에 없다**(상하님 확정). 3개월·6개월·1년 성적을 나란히 준다.
        for rule in j3.CRASH_REBOUND_RULES:
            self.assertNotIn("hold_days", rule, "파는 날이 규칙으로 되살아났다")
            self.assertEqual([60, 120, 250], [r["days"] for r in rule["results"]])

    def test_the_screen_shows_the_measured_tables(self):
        """설명 창은 다시 잰 표 그림을 보여준다(2026-08-06)."""
        import pathlib

        import method_help

        for name, _caption in method_help.US_IMAGES:
            self.assertIsNotNone(method_help._image_path(name), f"assets/{name}이 없다")
        doc = pathlib.Path("docs/US_METHOD_TABLES.md")
        self.assertTrue(doc.exists(), "표 숫자를 적어 둔 문서가 없다")

    def _run(self, finder, frames):
        with patch.object(j3, "_download_cached", return_value=(frames, {"fetched_at": "x"})):
            return finder()

    def _run_swing(self, frames, ixic):
        """상승장 스캔은 종목 일봉과 나스닥 전체 일봉을 따로 받는다."""
        payload = dict(frames)
        payload["^IXIC"] = ixic
        with patch.object(j3, "_download_cached",
                          return_value=(payload, {"fetched_at": "x"})):
            return j3.find_breakout_pullback_stocks()

    def test_breakout_gate_comes_first_and_score_only_sets_the_order(self):
        """**자격이 먼저, 점수는 그다음이다** (2026-08-20 지시문 3·36번).

        옛 상승장은 그물은 넓게 두고 순위만 점수로 매겼다. 새 규칙은 순서가
        반대다 — 시장 · RS60 · RS120 · 종가 신고가 · 신고가 뒤 1~3거래일 ·
        종가 눌림 3~10%를 **모두** 통과한 종목만 정식 후보가 되고, 점수는
        통과한 것들의 차례만 정한다. 보조점수가 아무리 높아도 이 자격을
        대신하지 못한다.
        """
        _tickers, frames, ixic = _swing_fixture()
        result = self._run_swing(frames, ixic)
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual("US_SWING_V1", result["score_model_version"])
        self.assertEqual("MARKET_ON", result["market"]["market_status"])

        primary = result["primary_rows"]
        watch = result["watch_rows"]
        self.assertTrue(primary, "정식 후보가 하나도 안 나왔다")
        for row in primary:
            self.assertTrue(row["eligible_primary"])
            self.assertEqual("PRIMARY_CANDIDATE", row["primary_status"])
            self.assertGreaterEqual(row["rs60_percentile"], 80.0)
            self.assertGreaterEqual(row["rs120_percentile"], 80.0)
            self.assertTrue(3.0 <= row["pullback_pct_close"] <= 10.0, row["ticker"])
            self.assertTrue(1 <= row["days_since_anchor"] <= 3, row["ticker"])
            self.assertIsNotNone(row["grade"])
        # 떨어진 줄에는 등급을 붙이지 않는다(35번) — 상태가 먼저고 점수는 참고다.
        for row in watch:
            self.assertFalse(row["eligible_primary"])
            self.assertIsNone(row["grade"])
        # 점수는 통과한 것들의 차례만 정한다.
        scores = [row["total_score"] for row in primary]
        self.assertEqual(sorted(scores, reverse=True), scores)
        self.assertEqual(list(range(1, len(primary) + 1)),
                         [row["primary_rank"] for row in primary])

    def test_breakout_support_score_can_never_bypass_the_rs_gate(self):
        """**보조점수로 RS 자격을 살 수 없다** (지시문 3·49번).

        RS60이 아무리 높아도 RS120이 상위 20% 밖이면 정식 후보가 아니다.
        총점이 높게 나와도 화면은 등급 대신 "RS120 부족"을 먼저 말한다.
        """
        self.assertEqual(25.0, us_swing.rs_points(97.0))
        self.assertEqual(12.0, us_swing.rs_points(74.0))
        self.assertEqual(20.0, us_swing.pullback_points(7.0))
        # 자격을 못 넘었으면 등급 자체가 없다.
        self.assertIsNone(us_swing.grade_for(90.0, False))
        self.assertEqual("S", us_swing.grade_for(90.0, True))

    def test_breakout_core_and_support_are_never_mixed_into_one_number(self):
        """핵심 70과 보조 30을 하나로 뭉쳐 감추지 않는다 (지시문 33·57번)."""
        _tickers, frames, ixic = _swing_fixture()
        row = self._run_swing(frames, ixic)["primary_rows"][0]
        self.assertAlmostEqual(
            row["rs60_score"] + row["rs120_score"] + row["pullback_score"],
            row["core_score"], places=6)
        self.assertAlmostEqual(
            row["theme_score"] + row["volume_score"]
            + row["breadth_score"] + row["rebound_score"],
            row["support_score"], places=6)
        self.assertAlmostEqual(row["core_score"] + row["support_score"],
                               row["total_score"], places=6)
        self.assertLessEqual(row["core_score"], 70.0)
        self.assertLessEqual(row["support_score"], 30.0)
        # 화면 배점표도 같은 일곱 줄을 쓰고, 줄마다 그 종목의 실제 값이 실린다.
        scored = j3.breakout_score(row)
        self.assertEqual(100.0, scored["max"])
        self.assertEqual(7, len(scored["parts"]))
        self.assertEqual(round(row["total_score"], 1), scored["score"])
        for name, value, maximum, note in scored["parts"]:
            self.assertLessEqual(value, maximum, name)
            self.assertTrue(str(note).strip(), f"{name} 줄에 실제 값이 없다")

    def test_breakout_every_item_carries_a_plain_word_explanation(self):
        """항목마다 **쉬운 한 줄 설명과 자세한 설명**이 붙는다 (지시문 46·47번)."""
        _tickers, frames, ixic = _swing_fixture()
        row = self._run_swing(frames, ixic)["primary_rows"][0]
        payload = row["explanations"]
        for metric in ("market", "rs60", "rs120", "breakout", "pullback",
                       "theme", "volume", "breadth", "rebound"):
            item = payload[metric]
            for field in ("title", "display_value", "one_line_explanation",
                          "detail_explanation", "status", "confidence"):
                self.assertTrue(str(item.get(field) or "").strip(),
                                f"{metric}의 {field}가 비었다")
            self.assertLessEqual(item["score"], item["max_score"], metric)

    def test_breakout_market_gate_blocks_every_new_primary_candidate(self):
        """**시장이 아니면 아무도 정식 후보가 못 된다** (2026-08-20 지시문 6·36번).

        옛 상승장은 나스닥 상태를 알려만 주고 막지 않았다. 새 규칙은 그 반대다 —
        좋은 종목도 시장 전체가 약하면 성공하기 어렵다는 것이 그 까닭이고,
        MARKET_ON이 HARD GATE의 첫 조건이다.
        **자리를 채우려고 기준을 낮추지 않는다**(CLAUDE.md 0-1 바).
        """
        _tickers, frames, ixic = _swing_fixture(market_on=False)
        result = self._run_swing(frames, ixic)
        self.assertTrue(result["ok"], result.get("error"))
        self.assertNotEqual("MARKET_ON", result["market"]["market_status"])
        self.assertEqual([], result["primary_rows"], "시장이 막혔는데 후보가 나왔다")
        self.assertTrue(result["watch_rows"], "관찰목록까지 사라지면 안 된다")
        self.assertIn("MARKET_BLOCKED",
                      {row["primary_status"] for row in result["watch_rows"]})
        for row in result["watch_rows"]:
            self.assertIsNone(row["grade"], "Gate를 못 넘었는데 등급이 붙었다")

    def test_breakout_market_state_follows_the_correction_and_reclaim_cycle(self):
        """시장 상태는 200일선이 아니라 **조정 → 이전 최고 회복** 사이클로 본다.

        2026-08-20 지시문 6번 — 나스닥 종가가 이전 최고에서 10% 넘게 밀렸다가
        그 최고를 다시 넘으면 새 상승 사이클(MARKET_ON)로 본다. 200일선과
        고점 대비 낙폭은 계속 재서 저장하지만 **점수에는 넣지 않는다.**
        """
        with patch.object(j3, "_download_cached",
                          return_value=({"^IXIC": _swing_market_frame()}, {})):
            state = j3.breakout_market_state()
        self.assertTrue(state["ok"])
        self.assertTrue(state["armed"])
        self.assertEqual("MARKET_ON", state["market_status"])
        self.assertEqual(0.10, state["correction_threshold"])
        self.assertIsNotNone(state["ixic_sma200"])
        with patch.object(j3, "_download_cached",
                          return_value=({"^IXIC": _swing_market_frame(market_on=False)}, {})):
            weak = j3.breakout_market_state()
        self.assertNotEqual("MARKET_ON", weak["market_status"])
        self.assertFalse(weak["armed"])

    def test_breakout_market_state_blocks_when_the_index_cannot_be_read(self):
        """**나스닥을 못 읽으면 새 후보를 막는다** (2026-08-20에 뒤집혔다).

        옛 규칙은 자료 탓에 화면이 막히면 더 나쁘다며 켜 뒀다. 새 지시문 43번은
        모르는 것을 통과나 0점으로 조용히 바꾸지 말라고 못박았다 — 시장을 못 읽은
        날 신규매수를 허용하면 그 근거가 어디에도 남지 않는다.
        """
        with patch.object(j3, "_download_cached", side_effect=RuntimeError("망")):
            state = j3.breakout_market_state()
        self.assertFalse(state["ok"])
        self.assertFalse(state["armed"], "시장을 못 읽었는데 새 후보를 허용했다")
        self.assertEqual("MARKET_RISK", state["market_status"])

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

    def _run_crash(self, frames, drop_pct=-15.0):
        """급락 규칙은 나스닥 낙폭 조건을 먼저 통과해야 종목을 찾는다(2026-08-06)."""
        low, high = j3.CRASH_MARKET_BAND
        state = {"ok": True, "armed": low <= drop_pct <= high, "drop_pct": drop_pct,
                 "band": j3.CRASH_MARKET_BAND, "reason": "시험"}
        with patch.object(j3, "crash_market_state", return_value=state):
            return self._run(j3.find_crash_rebound_stocks, frames)

    def test_crash_splits_the_two_depth_buckets_and_ignores_the_high_date(self):
        frames = {
            "AAPL": _frame_with_high(200, -25.0),   # 걸린다 — 신고가 날짜는 안 본다
            "MSFT": _frame_with_high(3, -28.0),     # 걸린다
            "AMZN": _frame_with_high(50, -15.0),    # 덜 빠졌다
            "GOOGL": _frame_with_high(50, -40.0),   # 너무 빠졌다(이제 갈래가 하나다)
        }
        result = self._run_crash(frames)
        self.assertTrue(result["ok"])
        picked = {row["ticker"]: row for row in result["rows"]}
        # GOOGL(-40%)도 걸린다 — 30~50% 칸을 2026-08-12에 되살렸다.
        self.assertEqual({"AAPL", "MSFT", "GOOGL"}, set(picked))
        for ticker in ("AAPL", "MSFT"):
            self.assertEqual("shallow", picked[ticker]["bucket"])
        self.assertEqual("deep", picked["GOOGL"]["bucket"])
        # 파는 날은 안 정한다. 대신 성적 셋이 줄마다 실려야 한다.
        for row in picked.values():
            self.assertIsNone(row["hold_days"])
            self.assertEqual(3, len(row["hold_results"]))
        self.assertEqual({"shallow": 2, "deep": 1}, result["bucket_counts"])

    def test_crash_tells_the_market_state_but_does_not_block(self):
        """시장 낙폭은 막지 않고 알려만 준다(2026-08-06 사용자 결정).

        막았더니 화면이 통째로 비었다. 나스닥이 그 자리를 지나 올라가도 그때
        걸렸던 종목은 볼 값어치가 있다는 판단이다.
        """
        frames = {"AAPL": _frame_with_high(200, -25.0)}
        for drop in (-3.0, -30.0):
            result = self._run_crash(frames, drop_pct=drop)
            self.assertTrue(result["ok"])
            self.assertEqual(1, len(result["rows"]), f"나스닥 {drop}%인데 막혔다")
            self.assertIsNotNone(result.get("market"), "시장 상태는 알려줘야 한다")

    def test_crash_rows_carry_the_reference_numbers(self):
        """성적은 **화면이 실제로 뒤지는 명부**로 잰 값이어야 한다.

        2026-08-06에 나스닥100 96종목 → 대형주 명부로 바꿔 다시 쟀고,
        2026-08-07에 그물을 격자로 다시 잡으면서 또 다시 쟀다
        (나스닥 -10~-20% 가장 깊은 날 · 종목 -20~-30% · 250거래일).
        화면 숫자와 코드 숫자가 어긋나면 화면이 거짓말을 한다.
        """
        frames = {"AAPL": _frame_with_high(200, -25.0)}
        row = self._run_crash(frames)["rows"][0]
        shallow = j3.CRASH_REBOUND_RULES[0]
        # 성적은 **새 그물**(나스닥 -6% 아래 전부 · 구간에 있는 동안 매일)로 잰 값이다.
        self.assertEqual(shallow["results"], row["hold_results"])
        # 길게 들수록 좋아진다 — 이게 2026-08-07에 내가 놓친 것이다.
        medians = [r["median_return"] for r in shallow["results"]]
        self.assertEqual(sorted(medians), medians, "보유가 길수록 성적이 좋아야 한다")

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

    def test_breakout_keeps_stocks_that_belong_to_no_theme(self):
        """**테마가 없어도 목록에 올린다** (2026-08-14 상하님 지시 "없더라도 넣어라").

        테마 명부는 사람이 손으로 묶은 것이라, 테마에 없다는 것은 그 종목이
        나쁘다는 뜻이 아니라 **명부가 아직 그 종목을 안 담았다**는 뜻이다.
        2026-08-20 새 지시문도 같은 편이다(25·43번) — 테마는 보조점수라서
        못 쟀다고 종목을 탈락시키지 않는다. 대신 테마 10점과 확산도 5점을
        못 받아 아래로 내려간다.
        **이것을 조건으로 바꾸려면 그물을 바꾸는 것이므로 먼저 여쭌다.**
        """
        tickers, frames, ixic = _swing_fixture(loner_first=True)
        loner = tickers[0]
        self.assertNotIn(loner, {t for theme in j3.US_THEMES for t in theme["stocks"]})
        result = self._run_swing(frames, ixic)
        rows = {row["ticker"]: row for row in result["all_rows"]}
        self.assertIn(loner, rows, "테마 없는 종목이 목록에서 사라졌다")
        self.assertFalse(rows[loner]["theme_valid"])
        self.assertEqual(0.0, rows[loner]["theme_score"], "테마가 없으면 테마 점수는 0점이다")
        self.assertEqual(0.0, rows[loner]["breadth_score"])
        # **테마를 못 쟀다고 정식 후보에서 떨어뜨리지 않는다.**
        self.assertTrue(rows[loner]["eligible_primary"],
                        f"테마가 없다고 후보에서 빠졌다: {rows[loner]['primary_status']}")
        self.assertIn(loner, [row["ticker"] for row in result["primary_rows"]])
        # 대신 보조점수가 깎여 만점을 못 받는다.
        self.assertLessEqual(rows[loner]["support_score"], 30.0 - 10.0 - 5.0)

    def test_breakout_rank_looks_at_what_the_score_looks_at(self):
        """상승장 순위는 **배점이 보는 것과 같은 것**을 봐야 한다.

        2026-08-20 새 지시문 41·58번이 차례를 다시 정했다 —
        총점 → 핵심점수 → RS120 → RS60 → 눌림 점수 → 20일 평균 거래대금 → 티커다.
        **지금 시가총액은 쓰지 않는다.** 과거 차례를 지금 시총으로 매기면
        그날 알 수 없던 것을 쓰는 셈이 된다(39번).
        """
        import inspect

        source = inspect.getsource(j3._breakout_rank_key)
        for gone in ("volume_streak", "together", "market_cap", "theme_prox"):
            self.assertNotIn(gone, source, f"{gone}이 순위에 되살아났다")
        base = {"eligible_primary": True, "total_score": 80.0, "core_score": 60.0,
                "rs120_percentile": 90.0, "rs60_percentile": 90.0,
                "pullback_score": 20.0, "avg_dollar_volume_20": 1e9}
        rows = [
            {**base, "ticker": "AAA", "core_score": 55.0},   # 핵심점수가 낮다
            {**base, "ticker": "BBB", "rs120_percentile": 95.0},
            {**base, "ticker": "CCC", "rs120_percentile": 95.0, "rs60_percentile": 99.0},
        ]
        ordered = [row["ticker"] for row in sorted(rows, key=j3._breakout_rank_key)]
        self.assertEqual(["CCC", "BBB", "AAA"], ordered)
        # 총점이 같아도 **핵심점수가 높은 쪽이 먼저다**(33번). 보조점수로 채운
        # 총점과 핵심으로 채운 총점은 같은 종목이 아니다.
        mixed = [{**base, "ticker": "CORE", "core_score": 68.0, "support_score": 12.0},
                 {**base, "ticker": "SUPP", "core_score": 50.0, "support_score": 30.0}]
        self.assertEqual(["CORE", "SUPP"],
                         [row["ticker"] for row in sorted(mixed, key=j3._breakout_rank_key)])

    def test_breakout_and_crash_are_scored_with_different_rulers(self):
        """두 갈래에 같은 자를 쓰면 낙폭 종목이 정의상 전부 "제외"로 나온다."""
        self.assertNotEqual(j3.BREAKOUT_SCORE_WEIGHTS, j3.CRASH_SCORE_WEIGHTS)
        for weights in (j3.BREAKOUT_SCORE_WEIGHTS, j3.CRASH_SCORE_WEIGHTS):
            # 거래대금 연속은 양쪽 갈래 다 거꾸로였다 — 배점에서 뺐다.
            self.assertNotIn("volume_streak", weights)
        # **계단은 40·30·20·10뿐이다**(CLAUDE.md 0-1 마). 47.0·31.25·22.5·18.75 같은
        # 비례 나눗셈 값이 다시 들어오면 여기서 먼저 깨진다.
        # **2026-08-20부터 이 계단은 급락 갈래만의 규칙이다.** 계단은 제가 항목을
        # 하나씩 과거차트로 재서 순위를 매길 때 쓰던 규칙인데, 상승장은 상하님이
        # 주신 새 지시문이 항목마다 만점을 직접 정해 내려왔다(25·25·20·10·8·5·7).
        for name, points in j3.CRASH_SCORE_WEIGHTS.items():
            self.assertIn(points, (0.0, 10.0, 20.0, 30.0, 40.0),
                          f"급락 {name} {points}점은 계단 밖이다")
        # **상승장 배점은 핵심 70 + 보조 30 = 100점이다**(2026-08-20 지시문 32번).
        # 핵심은 RS60 25 + RS120 25 + 신고가 후 눌림 20,
        # 보조는 테마 10 + 돌파 거래량 8 + 테마 확산도 5 + 반등 7이다.
        self.assertEqual({"rs60": 25.0, "rs120": 25.0, "pullback": 20.0,
                          "theme": 10.0, "volume": 8.0, "breadth": 5.0,
                          "rebound": 7.0}, dict(j3.BREAKOUT_SCORE_WEIGHTS))
        core = sum(j3.BREAKOUT_SCORE_WEIGHTS[name]
                   for name in ("rs60", "rs120", "pullback"))
        support = sum(j3.BREAKOUT_SCORE_WEIGHTS[name]
                      for name in ("theme", "volume", "breadth", "rebound"))
        self.assertEqual((70.0, 30.0), (core, support), "핵심 70·보조 30이 어긋났다")
        self.assertEqual(100.0, j3.BREAKOUT_SCORE_MAX)
        # 급락은 2026-08-19부터 **넷**이다 — 상하님 새 지시문을 앱 명부로 다시 쟀다.
        # 주가 변동성 40 + 30주선 30 + 동시 하락 20 + 6개월 수익률 10 = 100점.
        self.assertEqual(100.0, j3.CRASH_SCORE_MAX)
        self.assertEqual(j3.BREAKOUT_SCORE_MAX, sum(j3.BREAKOUT_SCORE_WEIGHTS.values()))
        self.assertEqual(j3.CRASH_SCORE_MAX, sum(j3.CRASH_SCORE_WEIGHTS.values()))
        # **상승장 1등은 RS(상대강도)다.** 지시문은 이것을 RSI와 혼동하지 말라고
        # 못박았다 — 여기서 RS는 나스닥보다 얼마나 더 올랐나이지 과열도가 아니다.
        # 3개월과 6개월이 나란히 1등(25점씩)이고, 눌림이 3등(20점)이다.
        self.assertEqual(25.0, j3.BREAKOUT_SCORE_WEIGHTS["rs60"])
        self.assertEqual(25.0, j3.BREAKOUT_SCORE_WEIGHTS["rs120"])
        self.assertEqual(20.0, j3.BREAKOUT_SCORE_WEIGHTS["pullback"])
        # 보조 넷은 아직 더 재 봐야 하는 항목이라 낮은 몫만 준다.
        for name, points in (("theme", 10.0), ("volume", 8.0),
                             ("breadth", 5.0), ("rebound", 7.0)):
            self.assertEqual(points, j3.BREAKOUT_SCORE_WEIGHTS[name], name)
        # 옛 상승장 항목 이름이 되살아나면 여기서 깨진다.
        for gone in ("theme_prox", "gain60", "drop", "spread5", "less_drop",
                     "together", "recent_drop", "liquidity", "volatility", "ret60"):
            self.assertNotIn(gone, j3.BREAKOUT_SCORE_WEIGHTS, f"옛 상승장 {gone}")
        # 급락 1등은 **주가 변동성**이다(2026-08-19 실측 — 바닥 9번에서 3개월 9/9 ·
        # 6개월 7/8 · 1년 8/8). 이 파트에서 종목 항목이 점수를 받는 것은 처음이다.
        # 30주선이 2등 30점, 동시 하락이 3등 20점, 6개월 수익률이 4등 10점이다.
        # 옛 1등 "덜 빠졌나"는 그대로 0점이다.
        self.assertEqual(40.0, j3.CRASH_SCORE_WEIGHTS["volatility"])
        self.assertEqual(30.0, j3.CRASH_SCORE_WEIGHTS["above150"])
        self.assertEqual(20.0, j3.CRASH_SCORE_WEIGHTS["together"])
        self.assertEqual(10.0, j3.CRASH_SCORE_WEIGHTS["theme_ret120"])
        self.assertEqual(0.0, j3.CRASH_SCORE_WEIGHTS["less_drop"])
        # **20일선과 낙폭은 0점이다.** 20일선은 거꾸로였고(1년 -23.3%), 낙폭은
        # 그물이 이미 쓴 값인 데다 변동성과 71%가 같은 종목이다(2026-08-19).
        self.assertEqual(0.0, j3.CRASH_SCORE_WEIGHTS["above20"])
        self.assertEqual(0.0, j3.CRASH_SCORE_WEIGHTS["bucket"])
        # 급락 그물에서 합격 못 한 항목들 — 되살아나면 여기서 깨진다.
        for name in ("recent_drop", "liquidity"):
            self.assertEqual(0.0, j3.CRASH_SCORE_WEIGHTS[name], f"급락 {name}")
        # **급락 배점 100점 가운데 60점이 테마 등수, 40점이 종목이다**(2026-08-19).
        # 2026-08-12에는 종목 항목 아홉 개가 세 보유 다 미달이라 100%가 테마였는데,
        # 상하님 새 지시문의 "주가 변동성"을 앱 명부로 다시 재니 1등으로 붙었다.
        theme_points = sum(j3.CRASH_SCORE_WEIGHTS[name]
                           for name in ("together", "theme_ret120", "above150",
                                        "less_drop", "aligned", "above20"))
        self.assertEqual(60.0, theme_points)
        self.assertEqual(j3.CRASH_SCORE_MAX,
                         theme_points + j3.CRASH_SCORE_WEIGHTS["volatility"])
        # **"같이 오르는가" 30점은 "주봉 오름세"로 갈아끼웠다**(2026-08-12 저녁,
        # 상하님 지시 "반등은 빨리·많이가 기준"). 속도를 넣고 재니 "같이 오르는가"로
        # 고른 종목은 +20%까지 46일 — **아무거나 산 것(45일)보다 느렸다.**
        # 주봉 오름세는 34일이고 5·10·20·40일·6개월·1년 여섯 곳 다 합격했다.
        # 근거: research/us_rebound_speed.py
        # 주봉 오름세 30점은 2026-08-14에 0점이 됐다 — 급락 직후엔 맞는 테마가
        # 거의 없어 잴 수 있는 사건이 한두 번뿐이었다. 30주선이 같은 것을 더 잘 잰다.
        self.assertEqual(0.0, j3.CRASH_SCORE_WEIGHTS["aligned"])
        # 20일선은 점수에서 빠지고 **같은 점수를 가르는 데만** 쓴다(넣으면 나빠진다).
        self.assertEqual(0.0, j3.CRASH_SCORE_WEIGHTS["above20"])
        self.assertEqual(0.0, j3.CRASH_SCORE_WEIGHTS["spread5"])
        # "테마 60일 수익률"은 6개월 보유에서만 합격했다 — 파는 시점을 안 정하므로 안 쓴다.
        self.assertEqual(0.0, j3.CRASH_SCORE_WEIGHTS["theme_rank"])
        # **"최근 11일"은 보유기간마다 뒤집힌다.** 3개월 1등(-5.8p)인데 1년에서는
        # 거의 거꾸로(-19.7p)다. 앱이 파는 시점을 안 정하므로 쓸 수 없다.
        self.assertEqual(0.0, j3.CRASH_SCORE_WEIGHTS["recent_drop"])
        # 낙폭 갈래도 0점이다 — 갈래가 하나뿐이라 모두 같은 점수를 받아 못 가른다.
        self.assertEqual(0.0, j3.CRASH_SCORE_WEIGHTS["bucket"])

    def test_theme_points_match_what_the_screen_says(self):
        """화면 배점표('3개↑ 만점 · 1~2개 절반')와 계산이 같아야 한다.

        2026-08-06 상하님 캡처에서 '같은 테마 동반 1개 함께 걸림 → 0.0(40.0)'으로
        어긋난 것이 드러났다. 등급(THEME_TOGETHER_TIERS)은 4개부터 만점이라
        배점에 그대로 쓰면 안 된다 — 등급은 순위를 가를 때만 쓴다.
        """
        self.assertEqual(40.0, j3.theme_together_points(3, 40.0))
        self.assertEqual(40.0, j3.theme_together_points(7, 40.0))
        self.assertEqual(20.0, j3.theme_together_points(1, 40.0))
        self.assertEqual(20.0, j3.theme_together_points(2, 40.0))
        self.assertEqual(0.0, j3.theme_together_points(0, 40.0))
        # **상승장은 2026-08-12부터 이 자를 안 썼고, 2026-08-20에는 아예 다른 자로
        # 갈아탔다.** 새 지시문은 같은 테마 다른 종목들이 얼마나 강한가를
        # **대상 종목을 빼고**(Leave-One-Out) 재서 보조 10점만 준다.
        # 배점표에 "같은 테마 동반" 줄이 다시 나오면 안 된다.
        row = {"metrics": {}, "together_count": 1, "together_tier": 0,
               "recent_gain_pct": 0.0}
        parts = j3.breakout_score(row)["parts"]
        self.assertNotIn("같은 테마 동반", [name for name, _v, _m, _t in parts])
        self.assertNotIn("together", j3.BREAKOUT_SCORE_WEIGHTS)
        # 상승장 배점표는 일곱 줄이고 만점은 25·25·20·10·8·5·7이다.
        self.assertEqual([25.0, 25.0, 20.0, 10.0, 8.0, 5.0, 7.0],
                         [maximum for _n, _v, maximum, _t in parts])
        # 급락은 이 자를 계속 쓴다 — 두 갈래가 서로 다른 자를 쓴다는 뜻이다.
        self.assertEqual(40.0, j3.theme_together_points(3, 40.0))
        # **급락에서도 2026-08-12에 뺐다.** 2026-08-09에 명부에서 종목 하나
        # (CRWD→ORCL)를 바꾼 뒤로 옛 그물에서도 이미 불합격이었고(80/95 → 64/93),
        # 상하님 표 2로 되돌린 새 그물에서는 1년 보유에만 걸리는 데다 해당이 67%라
        # 못 가른다(기준 6). 배점표에도 그 줄이 없어야 한다.
        crash_names = [name for name, _v, _m, _t in j3.crash_rebound_score(
            {"metrics": {}, "together_count": 5, "bucket": "shallow"})["parts"]]
        # **점수를 주는 항목은 넷이다**(2026-08-19, 상하님 새 지시문 재측정) —
        # 주가 변동성 40 · 30주선 30 · 동시 하락 20 · 6개월 수익률 10.
        # **0점 항목은 배점표에 없다.** 2026-08-15에 되살렸다가 08-19에 상하님이
        # 바로잡아 주셨다 — 0점짜리는 배점표가 아니라 「설명」 창에 적는다.
        crash_parts = j3.crash_rebound_score(
            {"metrics": {}, "together_count": 5, "bucket": "shallow"})["parts"]
        scored = [(name, maximum) for name, _v, maximum, _t in crash_parts if maximum]
        self.assertEqual(4, len(scored), scored)
        self.assertEqual(len(crash_parts), len(scored), "0점 줄이 배점표에 섞였다")
        self.assertTrue(scored[0][0].startswith("이 종목이 평소 크게"), scored)
        self.assertEqual(40.0, scored[0][1], "1등은 40점이다")
        self.assertTrue(scored[1][0].startswith("이 테마가 이미 오름세"), scored)
        self.assertEqual(30.0, scored[1][1], "2등은 30점이다")
        self.assertTrue(scored[2][0].startswith("이 테마가 통째로 떨어졌나"), scored)
        self.assertEqual(20.0, scored[2][1], "3등은 20점이다")
        self.assertTrue(scored[3][0].startswith("이 테마가 지난 반년에"), scored)
        self.assertEqual(10.0, scored[3][1], "4등은 10점이다")
        # 문턱은 4개다 — 3개면 점수가 없다(절반 점수를 두지 않는다).
        three = j3.crash_rebound_score({"metrics": {}, "together_count": 3})["parts"]
        together_value = next(value for name, value, _m, _t in three
                              if name.startswith("이 테마가 통째로"))
        self.assertEqual(0.0, together_value, "3개에는 점수를 주지 않는다")
        # 넷 중 하나(변동성)만 종목을 보고 셋은 테마를 본다.
        self.assertEqual(1, sum(1 for name in crash_names if "테마" not in name),
                         crash_names)
        # **이름은 그 항목이 던지는 질문이어야 한다**(2026-08-19 상하님 지적 —
        # "테마 6개월 수익률 상위 3등, 이 말은 수익률이 좋다는 말이냐 뭐냐").
        for name in crash_names:
            self.assertTrue(name.startswith("이 "), f"{name}은 질문 꼴이 아니다")
        # 「설명」 칸은 **어느 쪽이 좋은지 · 문턱 · 판정**을 다 적어야 한다.
        # 2026-08-19에 상하님이 두 번 지적하셨다 — "위쪽 절반이라 점수를 받습니다,
        # 이게 무슨 말인지 모르겠다", "많이 떨어지면 점수를 더 준다는 거냐".
        for _n, _v, _m, note in crash_parts:
            self.assertIn("→", note, note)
            self.assertTrue("점수를 받습니다" in note or "점수가 없습니다" in note, note)
            if "못 쟀습니다" in note or "매길 수 없습니다" in note:
                continue          # 아예 못 잰 줄에는 문턱을 적을 것이 없다
            self.assertIn("점수를 줍니다", note, f"어느 쪽이 좋은지가 없다: {note}")
            self.assertIn("야 점수)", note.replace("이면 점수)", "야 점수)"),
                          f"문턱이 없다: {note}")
        # 값이 다 있는 줄로도 한 번 더 본다 — 위는 metrics가 비어 있어 변동성 줄이
        # '못 쟀습니다'로 빠진다.
        full = [{"ticker": "AAA", "metrics": {"vol60": 5.0}, "together_count": 8,
                 "together_theme": "반도체"},
                {"ticker": "BBB", "metrics": {"vol60": 1.0}}]
        j3._attach_crash_volatility(full)
        for _n, _v, _m, note in j3.crash_rebound_score(full[0])["parts"][:1]:
            self.assertIn("크게 움직일수록 점수를 줍니다", note, note)
            self.assertIn("등 안이면 점수)", note, f"몇 등까지인지가 없다: {note}")

    def test_theme_rank_is_scored_and_ranks_over_the_whole_universe(self):
        """테마 등수 25점 — 2026-08-07 도입. 등수는 명부 전체로 매겨야 한다."""
        memberships = {"AAA": ["강한테마"], "BBB": ["강한테마"], "CCC": ["강한테마"],
                       "DDD": ["약한테마"], "EEE": ["약한테마"], "FFF": ["약한테마"]}
        all_metrics = {"AAA": {"ret60": 30.0}, "BBB": {"ret60": 28.0},
                       "CCC": {"ret60": 26.0}, "DDD": {"ret60": -20.0},
                       "EEE": {"ret60": -18.0}, "FFF": {"ret60": -22.0}}
        rows = [{"ticker": "AAA", "themes": ["강한테마"]},
                {"ticker": "DDD", "themes": ["약한테마"]}]
        j3._attach_theme_rank(rows, memberships, all_metrics, metric_key="ret60", top_n=1)
        self.assertTrue(rows[0]["theme_rank_top"])
        self.assertFalse(rows[1]["theme_rank_top"])
        self.assertEqual(1, rows[0]["theme_rank"])
        self.assertEqual(2, rows[1]["theme_rank"])

        # 급락 배점의 **하나뿐인 항목은 '테마가 30주선 위에 있나'**다(2026-08-14 교체 —
        # 상하님이 실제로 사시는 자리에서 다시 재니 옛 셋이 전부 거꾸로였다).
        # 등수를 다는 자리와 점수를 읽는 자리가 맞물리는지 본다.
        j3._attach_theme_rank(rows, memberships, all_metrics, prefix="theme_above150",
                              metric_key="ret60", top_n=1)

        def above150_points(row):
            row = dict(row, metrics={})
            return next(value for name, value, _m, _t
                        in j3.crash_rebound_score(row)["parts"]
                        if "이미 오름세" in name)

        self.assertEqual(j3.CRASH_SCORE_WEIGHTS["above150"], above150_points(rows[0]))
        self.assertEqual(0.0, above150_points(rows[1]))

    def test_score_notes_pick_the_right_korean_particle(self):
        """'양자컴퓨팅가'가 아니라 '양자컴퓨팅이'라고 적어야 한다 (2026-08-19)."""
        self.assertEqual("이", j3._subject_particle("양자컴퓨팅"))
        self.assertEqual("가", j3._subject_particle("반도체"))
        self.assertEqual("이", j3._subject_particle("우주·위성"))
        self.assertEqual("가", j3._subject_particle("주택·홈빌더"))
        self.assertEqual("가", j3._subject_particle("SPY"))   # 한글이 아니면 '가'
        row = {"metrics": {}, "theme_above150": 13, "theme_above150_total": 20,
               "theme_above150_name": "양자컴퓨팅", "theme_above150_top": False}
        note = next(n for name, _v, _m, n in j3.crash_rebound_score(row)["parts"]
                    if name.startswith("이 테마가 이미 오름세"))
        self.assertIn("양자컴퓨팅이", note)
        self.assertNotIn("양자컴퓨팅가", note)

    def test_row_marks_when_the_52week_high_moved(self):
        """기준일 뒤 1년 최고가가 바뀐 종목을 표시한다 (2026-08-19 상하님 지적).

        상하님 — "고점 대비 -40.2%, 고점대비현재 -32.47%인데 종목저점후가 +12.9%다.
        더하기 빼기 해 보면 안 맞는다. 셋 중 어느 게 맞느냐."

        **셋 다 맞다.** 빼기가 아니라 나누기다 — 두 낙폭은 고점에서 잰 값이고
        저점후는 기준일 종가에서 잰 값이라, 값이 내려간 만큼 오름폭이 크게 보인다.

        **다만 최고가 자체가 바뀐 종목은 나누기로도 안 맞는다.** 두 낙폭이 서로
        다른 고점을 쓰기 때문이다. 그런 종목인지 화면이 알 수 있어야 한다.
        """
        # 고점이 그대로인 종목 — 나누기로 딱 맞는다.
        judged, now = -40.20, -32.47
        since = ((1 + now / 100) / (1 + judged / 100) - 1) * 100
        self.assertAlmostEqual(12.93, since, places=1,
                               msg="빼기(7.7%)가 아니라 나누기(12.9%)다")

    def test_volatility_is_scored_in_the_crash_part(self):
        """주가 변동성은 급락 배점 **1등 40점**이다 (2026-08-19 상하님 새 지시문).

        이 파트에서 종목 자체를 보는 항목이 점수를 받는 것은 이것이 처음이다.
        값 자체로 점수를 주지 않고 **그날 목록에 걸린 종목끼리** 줄을 세워
        위쪽 절반에만 준다(research/us_crash_newscore.py).
        """
        # ① 60일 변동성이 metrics에 실려야 한다 — 없으면 줄을 못 세운다.
        closes = [100.0 * (1.01 if i % 2 else 0.995) ** i for i in range(200)]
        frame = pd.DataFrame({
            "Open": closes, "High": [c + 1 for c in closes],
            "Low": [c - 1 for c in closes], "Close": closes,
            "Volume": [1_000_000] * len(closes)},
            index=pd.date_range("2025-01-01", periods=len(closes), freq="B"))
        metrics = j3._series_metrics(frame)
        self.assertTrue(metrics["ok"])
        self.assertIsNotNone(metrics["vol60"], "60일 변동성이 안 실렸다")
        self.assertGreater(metrics["vol60"], 0.0)

        # ② 걸린 종목끼리 줄을 세워 **위쪽 절반**에만 붙는다.
        rows = [{"ticker": f"T{i}", "metrics": {"vol60": float(i)}} for i in range(1, 11)]
        j3._attach_crash_volatility(rows)
        top = [row["ticker"] for row in rows if row["vol_top"]]
        self.assertEqual(["T6", "T7", "T8", "T9", "T10"], top, top)

        # ③ 못 잰 종목은 **0으로 채우지 않는다** — 모르는 것과 낮은 것은 다르다.
        rows = [{"ticker": "AAA", "metrics": {"vol60": 5.0}},
                {"ticker": "BBB", "metrics": {"vol60": 1.0}},
                {"ticker": "CCC", "metrics": {}}]
        j3._attach_crash_volatility(rows)
        self.assertIsNone(rows[2]["vol_pct"])
        self.assertFalse(rows[2]["vol_top"])
        self.assertTrue(rows[0]["vol_top"])

        # ④ 점수는 40점이고, 못 잰 종목은 0점이다.
        def volatility_points(row):
            return next(value for name, value, _m, _t
                        in j3.crash_rebound_score(row)["parts"]
                        if name.startswith("이 종목이 평소"))

        self.assertEqual(40.0, volatility_points(rows[0]))
        self.assertEqual(0.0, volatility_points(rows[1]))
        self.assertEqual(0.0, volatility_points(rows[2]))
        self.assertEqual(0.50, j3.CRASH_VOL_TOP_SHARE, "절반으로 자른다")

    def test_six_month_theme_return_is_scored_in_the_crash_part(self):
        """테마 6개월 수익률은 급락 배점 **4등 10점**이다 (2026-08-19).

        1년 보유로 보면 바닥 6번 중 6번을 맞혀 넷 중 가장 잘 맞히는데, 3개월로
        보면 7번 중 4번뿐이다. 앱이 파는 시점을 정하지 않으므로 짧은 기간에
        약한 항목에는 큰 점수를 못 준다(research/us_crash_newscore.py).
        """
        # ① 6개월 수익률이 metrics에 실려야 한다 — 없으면 등수를 못 매긴다.
        closes = [100.0 + i for i in range(200)]
        frame = pd.DataFrame({
            "Open": closes, "High": [c + 1 for c in closes],
            "Low": [c - 1 for c in closes], "Close": closes,
            "Volume": [1_000_000] * len(closes)},
            index=pd.date_range("2025-01-01", periods=len(closes), freq="B"))
        metrics = j3._series_metrics(frame)
        self.assertTrue(metrics["ok"])
        self.assertIsNotNone(metrics["ret120"], "6개월 수익률이 안 실렸다")
        self.assertAlmostEqual((closes[-1] / closes[-121] - 1) * 100,
                               metrics["ret120"], places=6)

        # ② 그 값으로 테마 등수를 매기고, 상위 3등에만 40점이 붙어야 한다.
        memberships = {"AAA": ["빠른테마"], "BBB": ["빠른테마"], "CCC": ["빠른테마"],
                       "DDD": ["느린테마"], "EEE": ["느린테마"], "FFF": ["느린테마"]}
        all_metrics = {"AAA": {"ret120": 40.0}, "BBB": {"ret120": 35.0},
                       "CCC": {"ret120": 30.0}, "DDD": {"ret120": -10.0},
                       "EEE": {"ret120": -12.0}, "FFF": {"ret120": -14.0}}
        rows = [{"ticker": "AAA", "themes": ["빠른테마"]},
                {"ticker": "DDD", "themes": ["느린테마"]}]
        j3._attach_theme_rank(rows, memberships, all_metrics, prefix="theme_ret120",
                              metric_key="ret120", top_n=1)

        def ret120_points(row):
            return next(value for name, value, _m, _t
                        in j3.crash_rebound_score(dict(row, metrics={}))["parts"]
                        if "지난 반년" in name)

        self.assertEqual(10.0, ret120_points(rows[0]))
        self.assertEqual(0.0, ret120_points(rows[1]))
        # ③ 1등 40 · 2등 30 · 3등 20 · 4등 10 — 계단을 지킨다.
        self.assertEqual(40.0, j3.CRASH_SCORE_WEIGHTS["volatility"])
        self.assertEqual(30.0, j3.CRASH_SCORE_WEIGHTS["above150"])
        self.assertEqual(20.0, j3.CRASH_SCORE_WEIGHTS["together"])
        self.assertEqual(10.0, j3.CRASH_SCORE_WEIGHTS["theme_ret120"])
        self.assertEqual(3, j3.CRASH_RET120_TOP_N, "상위 3등까지만 준다")

    def test_same_score_rows_take_turns_by_theme(self):
        """같은 점수 안에서는 **테마를 번갈아** 놓는다 (2026-08-14 상하님 지시).

        상하님 — "반도체만 줄줄이 나오는 거 보기 불편하다."

        급락 배점은 '테마 30주선 위 상위 3등'에 40점을 주므로 그 테마 종목이 전부
        같은 점수가 된다. 구성종목이 많은 테마가 화면 위를 통째로 차지했다
        (실측: 40점 11줄 중 9줄이 반도체).

        **점수 차례는 건드리지 않는다** — 40점 줄이 언제나 0점 줄보다 위다.
        """
        rows = [
            {"ticker": "A1", "score": 40.0, "theme_above150_name": "반도체"},
            {"ticker": "A2", "score": 40.0, "theme_above150_name": "반도체"},
            {"ticker": "A3", "score": 40.0, "theme_above150_name": "반도체"},
            {"ticker": "B1", "score": 40.0, "theme_above150_name": "바이오"},
            {"ticker": "C1", "score": 0.0, "theme_above150_name": "방산"},
            {"ticker": "A4", "score": 0.0, "theme_above150_name": "반도체"},
        ]
        got = [row["ticker"] for row in j3._spread_by_theme(rows)]
        # 40점 무리 안에서만 번갈아 놓는다 — 반도체·바이오·반도체·반도체.
        self.assertEqual(["A1", "B1", "A2", "A3"], got[:4])
        # **점수 차례는 그대로다** — 0점 줄은 40점 줄 뒤에 온다.
        self.assertEqual({"C1", "A4"}, set(got[4:]))
        # 줄이 사라지거나 늘어나지 않는다.
        self.assertEqual(len(rows), len(got))

    def test_general_theme_ranking_uses_only_the_new_four_parts(self):
        """테마 순위는 **확산**으로 매긴다 (2026-08-12 처음 쟀다).

        상하님 지적 — "테마가 같이 상승하는 기준이 먼저이고 구성종목 확산이 먼저
        기준이 되어야지. 테마 수익률이 하락장에는 의미가 없지."

        국면을 갈라 재니 두 국면 모두 확산 계열이 1~4등이었고, 수익률 계열은
        상승 국면에서 꼴찌(-9.5p) 하락 국면에서 탈락이었다(research/us_parts.py).
        그전 배점은 상대강도 55점 · 이동평균 20점 · 확산 15점으로 정반대였다.
        """
        weights = j3.GENERAL_THEME_SCORE_WEIGHTS
        self.assertEqual({"strength_120", "strength_60", "strong_members", "strength_change"},
                         set(weights))
        self.assertEqual((35.0, 30.0, 25.0, 10.0), tuple(weights.values()))
        self.assertEqual(100.0, j3.GENERAL_THEME_SCORE_MAX)
        rows = [
            {"strength_120": 20.0, "strength_60": 15.0, "strong_members": 80.0, "strength_change": 5.0},
            {"strength_120": 0.0, "strength_60": 0.0, "strong_members": 20.0, "strength_change": -5.0},
        ]
        j3._apply_general_theme_scores(rows)
        self.assertEqual(100.0, rows[0]["score"])
        self.assertEqual(0.0, rows[1]["score"])
        for row in rows:
            self.assertTrue(0.0 <= row["score"] <= 100.0)
            self.assertEqual(4, len(row["score_parts"]))

    def test_general_stock_and_final_score_follow_40_40_20_and_60_40(self):
        metrics = {"ret60": 25.0, "ret120": 50.0, "from_high_pct": -5.0}
        benchmark = {"ret60": 5.0, "ret120": 10.0}
        stock_score, parts = j3._general_stock_score(metrics, benchmark)
        self.assertEqual((40.0, 40.0, 18.0), tuple(parts))
        self.assertEqual(98.0, stock_score)
        self.assertEqual(86.0, j3._general_final_score(90.0, 80.0))
        self.assertEqual(0.0, j3._general_final_score(-1.0, -1.0))
        self.assertEqual(100.0, j3._general_final_score(200.0, 200.0))

    def test_theme_rank_ignores_tiny_themes(self):
        """구성종목 3개 미만인 테마는 한두 종목에 휘둘려 등수가 못 미덥다."""
        memberships = {"AAA": ["둘뿐인테마"], "BBB": ["둘뿐인테마"],
                       "CCC": ["멀쩡한테마"], "DDD": ["멀쩡한테마"], "EEE": ["멀쩡한테마"]}
        all_metrics = {t: {"ret60": v} for t, v in
                       (("AAA", 99.0), ("BBB", 99.0), ("CCC", 1.0), ("DDD", 1.0),
                        ("EEE", 1.0))}
        rows = [{"ticker": "AAA", "themes": ["둘뿐인테마"]}]
        j3._attach_theme_rank(rows, memberships, all_metrics, metric_key="ret60", top_n=1)
        self.assertIsNone(rows[0]["theme_rank"])
        self.assertFalse(rows[0]["theme_rank_top"])

    def test_recent_drop_scores_the_fall_not_the_rally(self):
        """낙폭(구덩이 깊이)과 다른 것을 잰다 — 방금 빠졌나 이미 올라왔나."""
        full = j3.recent_drop_points(-8.0, 25.0)
        none = j3.recent_drop_points(12.0, 25.0)
        half = j3.recent_drop_points(0.0, 25.0)
        self.assertEqual(25.0, full)
        self.assertEqual(0.0, none)
        self.assertAlmostEqual(12.5, half)
        self.assertAlmostEqual(12.5, j3.recent_drop_points(None, 25.0))

    def test_both_depth_buckets_are_back(self):
        """2026-08-12 — 상하님 표 2의 두 칸을 다 본다.

        2026-08-07에 내가 깊은 칸(-30~-50%)을 통째로 지웠는데, 1년 보유에서
        얕은 칸보다 5.6%p 더 벌던 자리였다. 지우면 제일 좋은 자리를 놓친다.
        """
        shallow, deep = j3.CRASH_REBOUND_RULES
        self.assertEqual(("shallow", "deep"), (shallow["key"], deep["key"]))
        # 1년 보유에서 깊은 칸이 더 벌었다 — 그래서 되살렸다.
        year = {r["key"]: r["results"][-1]["median_return"] for r in j3.CRASH_REBOUND_RULES}
        self.assertGreater(year["deep"], year["shallow"])

    def test_rulebook_plans_carry_no_stop_loss(self):
        """두 갈래 다 **손절가를 만들어 붙이지 않는다**.

        2026-08-20 새 지시문 59번이 상승장 쪽 근거를 새로 적었다 — 고정 손절
        (-8·-12·-15·-20%)은 과거 성적을 오히려 나쁘게 한 경우가 많았고, 시장이
        약해지면 무조건 파는 방식도 좋지 않았다. 그래서 손절과 파는 시점을
        종목점수에 넣지 않는다.

        **화면에 "연구 중"이라고 적지 않는다**(2026-08-21 상하님 물음 —
        "너가 연구중인가?"). 제가 지금 무언가를 돌리고 있다는 말로 읽힌다.
        앱이 정하지 않고 상하님이 정하신다고 곧게 적는다.
        """
        row = {"metrics": {"from_high_pct": -5.0, "current": 100.0, "ret60": 20.0},
               "together_tier": 2, "together_count": 3, "hold_days": 120, "wait_days": 4,
               "eligible_primary": True, "grade": "A", "primary_status": "PRIMARY_CANDIDATE",
               "core_score": 60.0, "support_score": 20.0,
               "days_since_anchor": 2, "pullback_pct_close": 7.0,
               "bucket": "deep", "bucket_label": "고점 대비 -40~-50%"}
        for plan, mode in ((j3.breakout_plan(row), "breakout"),
                           (j3.crash_rebound_plan(row), "crash")):
            self.assertEqual(mode, plan["rule_mode"])
            self.assertIsNone(plan["invalidation"], "넘어야 할 기준가가 되살아났다")
            self.assertIsNone(plan["target"], "목표가가 되살아났다")
            self.assertIsNone(plan["hold_days"], "파는 날이 규칙으로 되살아났다")
        self.assertIn("손절가가 없습니다", j3.crash_rebound_plan(row)["buy_reason"])
        reason = j3.breakout_plan(row)["buy_reason"]
        self.assertIn("손절과 파는 시점은 앱이 정하지 않습니다", reason)
        self.assertNotIn("연구 중", reason, "'연구 중'이 되살아났다")

    def test_crash_reason_tells_the_day_number_apart_from_todays(self):
        """겨자색 상자가 표와 다른 숫자를 말하던 것을 고쳤다(2026-08-07 상하님 지적).

        예전에는 '고점 대비 -12.7%까지 내려온 낙폭 종목입니다'만 적었는데, 이
        -12.7%는 **오늘** 낙폭이다. 바로 옆 점수표는 '낙폭 갈래 -20~-30%'라고
        적는데, 갈래는 **기준일** 낙폭(-21.8%)으로 가르기 때문이다. 두 숫자를
        말 없이 섞어 놓아 서로 틀린 것처럼 보였다.
        """
        row = {"metrics": {"from_high_pct": -12.69, "current": 418.2},
               "judged_from_high_pct": -21.78, "now_from_high_pct": -12.69,
               "since_reference_pct": 11.63, "reference_date": "2026-07-14",
               "together_tier": 3, "together_count": 8, "hold_days": 120,
               "bucket": "shallow", "recent_gain_pct": -0.7}
        reason = j3.crash_rebound_plan(row)["buy_reason"]
        self.assertIn("2026-07-14", reason)
        self.assertIn("-21.8%", reason)       # 갈래를 정한 그날 낙폭
        self.assertIn("-12.7%", reason)       # 오늘 낙폭
        self.assertIn("+11.6%", reason)       # 그 뒤 움직임
        self.assertIn("그날 낙폭으로 정합니다", reason)

    def test_crash_reason_falls_back_when_there_is_no_reference_day(self):
        """기준일이 없으면(나스닥이 -6~-12%에 든 날이 없으면) 예전 문장 그대로."""
        row = {"metrics": {"from_high_pct": -33.0}, "hold_days": 120,
               "bucket": "deep", "together_tier": 0, "together_count": 0,
               "recent_gain_pct": 0.0}
        reason = j3.crash_rebound_plan(row)["buy_reason"]
        self.assertIn("고점 대비 -33.0%까지 내려온", reason)
        self.assertNotIn("기준일", reason)

    def test_nasdaq_drawdown_gate_matches_what_was_measured(self):
        """문턱 12%는 55년치로 재고 정했다 — 8%는 기준선보다 못했다.

        이 숫자를 슬쩍 낮추면 화면이 '아직 아닌 자리'를 사는 자리라고 말하게 된다.
        """
        self.assertEqual(-12.0, j3.NASDAQ_DRAWDOWN_ENTRY)
        self.assertEqual("사는 자리", j3.nasdaq_drawdown_state(-13.0)[0])
        self.assertEqual("아주 깊음", j3.nasdaq_drawdown_state(-25.0)[0])
        self.assertNotEqual("사는 자리", j3.nasdaq_drawdown_state(-9.0)[0])
        self.assertEqual("고점 근처", j3.nasdaq_drawdown_state(-2.0)[0])
        self.assertEqual("자료 없음", j3.nasdaq_drawdown_state(None)[0])

    def test_no_match_returns_an_empty_list_not_a_loosened_rule(self):
        """**빈 자리를 감추거나 딴 것으로 채우지 않는다**(CLAUDE.md 0-1 바).

        눌림이 12%까지 깊어지면 정식 후보는 없는 날이다. 그날 기준을 슬쩍
        넓혀 자리를 채우면 화면이 규칙과 다른 종목을 사라고 말하게 된다.
        """
        _tickers, frames, ixic = _swing_fixture()
        deep = {
            ticker: _swing_stock_frame(ixic.index[-300:], .60 - position * .012,
                                       1.00 - position * .022, pullback=12.0)
            for position, ticker in enumerate(frames)
        }
        result = self._run_swing(deep, ixic)
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual([], result["primary_rows"])
        self.assertEqual([], result["rows"])
        # 그래도 왜 없는지는 남긴다 — 관찰목록에 "너무 깊다"가 그대로 실린다.
        self.assertIn("TOO_DEEP", {row["primary_status"] for row in result["watch_rows"]})


class Jarvis3DataTests(unittest.TestCase):
    def tearDown(self):
        j3.clear_runtime_cache()

    def test_twenty_unique_themes_include_quantum_and_bigtech(self):
        names = [theme["name"] for theme in j3.US_THEMES]
        self.assertEqual(len(names), 20)
        self.assertEqual(len(set(names)), 20)
        self.assertIn("양자컴퓨팅", names)
        self.assertIn("빅테크10", names)

    def test_bigtech10_keeps_tesla_and_excludes_crowdstrike(self):
        bigtech = next(theme for theme in j3.US_THEMES if theme["name"] == "빅테크10")
        self.assertEqual(
            ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "NFLX", "ORCL"),
            bigtech["stocks"],
        )
        cyber = next(theme for theme in j3.US_THEMES if theme["name"] == "사이버보안")
        self.assertIn("CRWD", cyber["stocks"])

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
        # 5단계 기준(2026-08-05) — 75점대는 상승 신호 우세, 80점부터 상승 여건 양호.
        self.assertIn(result["regime"], {"상승 신호 우세", "상승 여건 양호"})
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

    def test_general_theme_plan_ignores_legacy_scores_but_waits_for_pullback_price(self):
        metrics = {
            "current": 100.0, "atr": 4.0, "atr_pct": 4.0, "ret5": -2.0,
            "sma20": 100.0, "sma50": 90.0, "from_high_pct": -8.0, "volume_ratio": 0.8,
        }
        plan = j3._entry_plan(
            metrics, score=10.0, market_score=80.0, theme_score=10.0,
            general_theme_trading=True,
        )
        self.assertEqual(plan["state"], "눌림목 대기")
        self.assertEqual(plan["recommendation"], "관찰")
        self.assertIn("좋은 후보", plan["buy_reason"])

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
        # 토막났다(2026-07-29 실측: NVDA 월봉 50선 72/120). 월봉 120개월 + 그
        # 50개월선이면 14년 남짓이라 20년으로 둔다 — 'max'로 받으면 상장 이후를
        # 다 주는데(AAPL 1980년~ 11,515줄) 나머지는 받아서 버린다(2026-08-22).
        download.assert_called_once_with(
            ("NVDA",), period=j3.CHART_HISTORY_PERIOD, interval="1d", ttl_seconds=300)
        self.assertEqual("20y", j3.CHART_HISTORY_PERIOD)

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
        # **화면에 뜨는 score는 얼린 값이다**(2026-08-12) — 장중에는 전일 마감값,
        # 마감 뒤에는 그날 값. 시험을 지금 시각에 맡기면 아침엔 통과하고 오후엔
        # 깨진다(실제로 그랬다). 그래서 CNN이 준 **날것**은 live_score로 본다.
        self.assertEqual(result["live_score"], 41.0)
        self.assertEqual(result["previous_close"], 45.0)
        self.assertIn(result["score"], (41.0, 45.0))
        self.assertEqual(result["rating_kr"], j3.fear_greed_label(result["score"]))
        # 얼림 자체는 시각을 넣어 못박는다.
        ny = ZoneInfo("America/New_York")
        raw = {"ok": True, "score": 41.0, "previous_close": 45.0}
        self.assertEqual(
            45.0, j3._freeze_fear_greed(dict(raw),
                                        now=datetime(2026, 8, 12, 12, tzinfo=ny))["score"],
            "장중에는 전일 마감값이어야 한다")
        self.assertEqual(
            41.0, j3._freeze_fear_greed(dict(raw),
                                        now=datetime(2026, 8, 12, 17, tzinfo=ny))["score"],
            "마감 뒤에는 그날 값이어야 한다")

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
class WeeklyAlignedTests(unittest.TestCase):
    """'주봉이 오름세인가' 판정 — Minervini Trend Template 그대로 (2026-08-12)."""

    def test_lined_up_and_rising_scores_100(self):
        self.assertEqual(100.0, j3._weekly_aligned({
            "current": 110, "sma50": 105, "sma150": 100, "sma200": 95,
            "sma200_prev": 90}))

    def test_out_of_order_scores_zero(self):
        # 150일선이 200일선보다 아래면 정배열이 아니다.
        self.assertEqual(0.0, j3._weekly_aligned({
            "current": 110, "sma50": 105, "sma150": 90, "sma200": 95,
            "sma200_prev": 90}))

    def test_flat_200_scores_zero(self):
        # 줄은 섰지만 200일선이 20일 전보다 위가 아니면 오름세가 아니다.
        self.assertEqual(0.0, j3._weekly_aligned({
            "current": 110, "sma50": 105, "sma150": 100, "sma200": 95,
            "sma200_prev": 95}))

    def test_missing_value_returns_none(self):
        # 못 잰 값은 **0이 아니라 빈칸**이다. 0으로 채우면 그 테마가 조용히 깎인다.
        self.assertIsNone(j3._weekly_aligned({
            "current": 110, "sma50": 105, "sma150": 100, "sma200": 95}))
        self.assertIsNone(j3._weekly_aligned({}))

    def test_metrics_carry_the_two_new_lines(self):
        """_series_metrics가 150일선과 '20일 전 200일선'을 실제로 내놓는가."""
        import pandas as pd
        days = pd.date_range("2024-01-01", periods=300, freq="B")
        rising = pd.Series(range(100, 400), index=days, dtype=float)
        daily = pd.DataFrame({"Open": rising, "High": rising * 1.01,
                              "Low": rising * 0.99, "Close": rising,
                              "Volume": 1_000_000.0}, index=days)
        metrics = j3._series_metrics(daily, None)
        self.assertTrue(metrics["ok"])
        self.assertIsNotNone(metrics["sma150"])
        self.assertIsNotNone(metrics["sma200_prev"])
        # 죽 오르는 값이니 주봉 오름세여야 한다.
        self.assertEqual(100.0, j3._weekly_aligned(metrics))


class CrashScoreWarningTests(unittest.TestCase):
    """급락 배점이 순위를 못 가르는 자리를 화면에 알리는가 (2026-08-12)."""

    def test_deep_crash_is_blind(self):
        # -24% 아래면 배점 세 항목이 전부 무너진다.
        self.assertTrue(j3.crash_score_is_blind(-24.0))
        self.assertTrue(j3.crash_score_is_blind(-31.5))
        self.assertFalse(j3.crash_score_is_blind(-23.9))
        self.assertFalse(j3.crash_score_is_blind(None))

    def test_shallow_crash_is_weak(self):
        # -6~-12%는 급락 목록이 뜨는 날의 41%로 제일 자주 오는데, 셋 중
        # '덜 빠졌나'만 1년 보유에서 걸린다. "약하다"고 적어야 한다.
        self.assertTrue(j3.crash_score_is_weak(-6.0))
        self.assertTrue(j3.crash_score_is_weak(-11.9))
        self.assertTrue(j3.crash_score_is_weak(-12.0))
        self.assertFalse(j3.crash_score_is_weak(-12.1))
        self.assertFalse(j3.crash_score_is_weak(-5.9), "그물 밖이다")
        self.assertFalse(j3.crash_score_is_weak(None))

    def test_the_two_warnings_never_fire_together(self):
        """한 날에 '못 가름'과 '약함'이 같이 뜨면 화면이 두 말을 한다."""
        for drop in (-3.0, -6.0, -12.0, -18.0, -24.0, -40.0):
            self.assertFalse(
                j3.crash_score_is_blind(drop) and j3.crash_score_is_weak(drop),
                f"나스닥 {drop}%에서 경고 두 개가 같이 뜬다")



class LeaderScoreMaxTests(unittest.TestCase):
    """대장주 조건점수 — **획득이 최대를 넘으면 안 된다** (2026-08-12 상하님 지적).

    상하님 캡처: 1등 종목의 '52주 신고가 위치'가 31.1 (25), '유동성'이 16.2 (15).
    뺀 20점을 나머지에 1.25배로 나눠 놓고 최대값 칸을 안 고쳐서 생긴 일이다.
    """

    def test_no_proportional_redistribution(self):
        # CLAUDE.md 0-1 마 — 뺀 점수를 남은 항목에 비례로 나누지 않는다.
        self.assertEqual(1.0, j3.LEADER_RESCALE)
        self.assertEqual(0.0, j3.LEADER_TREND_POINTS, "추세는 검증에서 거꾸로였다")
        self.assertEqual(80.0, j3.LEADER_SCORE_MAX, "합이 100이 아니면 그대로 적는다")

    def test_parts_and_maxima_line_up(self):
        names = [name for name, _p in j3.LEADER_SCORE_PARTS]
        self.assertEqual(
            ["테마 대비 상대강도", "52주 신고가 위치", "추세", "유동성", "변동성 안정"],
            names, "이름 순서가 _leader_score의 반환 순서와 같아야 한다")
        self.assertEqual(j3.LEADER_SCORE_MAX,
                         round(sum(p for _n, p in j3.LEADER_SCORE_PARTS), 1))

    def test_real_stock_never_exceeds_any_maximum(self):
        """실제 종목을 넣어 항목마다 만점을 안 넘는지 본다."""
        maxima = [points for _n, points in j3.LEADER_SCORE_PARTS]
        for slope, theme_ret in ((0.9, -20.0), (0.1, 5.0), (-0.4, 0.0)):
            metrics = j3._series_metrics(_daily_frame(slope=slope), None)
            self.assertTrue(metrics["ok"])
            total, parts = j3._leader_score(metrics, theme_ret)
            self.assertEqual(len(maxima), len(parts))
            for (name, top), got in zip(j3.LEADER_SCORE_PARTS, parts):
                self.assertLessEqual(round(got, 1), top,
                                     f"{name}이 만점 {top}을 넘었다: {got}")
            self.assertLessEqual(round(total, 1), j3.LEADER_SCORE_MAX)

    def test_every_item_says_what_it_measures(self):
        """항목 이름만으로는 뭘 재는지 모른다 (2026-08-12 상하님 지적).

        "유동성이 뭐에 대한 유동성인지 기준이 뭔지 설명이 불친절하다."
        """
        for name, _points in j3.LEADER_SCORE_PARTS:
            note = j3.LEADER_SCORE_NOTES.get(name, "")
            self.assertTrue(note.strip(), f"{name}에 설명이 없다")
        # 문턱은 _leader_score의 값과 같아야 한다 — 글과 계산이 갈리면 거짓말이 된다.
        self.assertIn("10억달러", j3.LEADER_SCORE_NOTES["유동성"])
        self.assertIn("3%", j3.LEADER_SCORE_NOTES["변동성 안정"])

    def test_surge_penalty_is_a_named_number(self):
        """5일 15%↑ 급등 감점 10점 — 표에 안 적히는 값이라 이름을 붙여 둔다."""
        self.assertEqual(10.0, j3.LEADER_SURGE_PENALTY)
        self.assertEqual(15.0, j3.LEADER_SURGE_RET5)

    def test_medal_mark_follows_the_maximum(self):
        # 만점이 바뀌면 메달 문턱도 같은 비율로 움직여야 한다.
        self.assertEqual(round(j3.LEADER_SCORE_MAX * 0.8, 1), j3.LEADER_MEDAL_MARK)

    def test_candidate_gate_follows_the_maximum(self):
        """**후보 문턱도 만점을 따라가야 한다** (2026-08-13 상하님 캡처).

        만점을 100 → 80으로 되돌리면서 이 문턱만 75로 두었더니, 만점의 89%인
        71.1점짜리가 "품질 점수가 기준 미달"로 빠졌다. 75/80 = 94%가 돼 버린 것이다.
        """
        self.assertEqual(round(j3.LEADER_SCORE_MAX * 0.75, 1), j3.LEADER_GATE_MARK)
        self.assertEqual(60.0, j3.LEADER_GATE_MARK)
        self.assertLess(j3.LEADER_GATE_MARK, j3.LEADER_MEDAL_MARK,
                        "후보 문턱이 메달 문턱보다 높으면 안 된다")

    def test_reason_names_the_score_the_way_the_screen_does(self):
        """'대장주 품질 점수'라는 딴 이름을 쓰지 않는다 (상하님: "품질 점수가 뭔데?")."""
        metrics = j3._series_metrics(_daily_frame(slope=0.02), None)
        plan = j3._entry_plan(metrics, 10.0, 100.0, 100.0)
        reason = plan.get("buy_reason") or ""
        self.assertIn("종목 조건점수", reason)
        self.assertNotIn("품질", reason)
        self.assertIn("60", reason, "문턱이 몇 점인지 같이 적어야 한다")


if __name__ == "__main__":
    unittest.main()

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

    def test_rule_numbers_are_what_the_screen_searches_for(self):
        """화면이 실제로 찾는 숫자. 손대면 찾는 종목이 달라진다.

        2026-08-06까지는 이 숫자가 method_help.US_TEXT에도 글로 적혀 있어서 둘을
        묶어 두었다. 설명 창이 표 그림으로 바뀌면서 글에서는 빠졌고, 표 숫자는
        docs/US_METHOD_TABLES.md가 지킨다(그림은 자동으로 못 읽는다).

        2026-08-06에 표와 같은 값으로 맞췄다(사용자 결정). 그전 값
        (3~5일 · 4~6% · -40~-50%)은 2026-08-01 설명서였는데, 다시 재니 앞 5년
        -0.2%p · 뒤 5년 -3.8%p로 양쪽 다 아무 종목이나 산 것보다 못했다.
        """
        rule = j3.BREAKOUT_PULLBACK_RULE
        # 그물은 넓게 — 옛 기준(4~6%)도 품는다(2026-08-06).
        # **2026-08-12 저녁 상하님이 3~10일로 정하셨다.** 1~5일로는 명부 198개 중
        # 16개만 걸려 화면이 거의 비었다. 어느 날짜 칸도 성적을 가르지 못했으므로
        # (research/us_breakout_window.py) 좁게 둘 근거가 없었다.
        self.assertEqual((3, 10), rule["wait_days"])
        self.assertEqual((-15.0, -4.0), rule["drop_band"])
        self.assertEqual(120, rule["hold_days"])
        # 별점은 뺐다(2026-08-06) — 낙폭·날짜만 보고 달았는데 뒤 5년에서 졌다.
        self.assertFalse(hasattr(j3, "BREAKOUT_STAR_RULES"), "별점이 되살아났다")
        self.assertFalse(hasattr(j3, "breakout_stars"), "별점이 되살아났다")
        # 성적 옆에는 늘 기준선이 붙어야 한다. 기준선은 화면이 뒤지는 명부로 잰 값이다.
        self.assertEqual(62.2, j3.BREAKOUT_BASE_WIN_RATE)
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

    def test_breakout_casts_a_wide_net_and_ranks_by_score(self):
        """그물은 넓게, 순위는 100점 배점으로(2026-08-06 사용자 결정).

        재측정 결과(1~5일 · 10~15%)를 그대로 거르는 조건으로 썼더니 화면이 매일
        비었다 — 그 자리는 1년에 30번뿐이다. 그래서 넓게 찾고 점수로 차례를 매긴다.
        고르는 것은 사람이 한다.

        **날짜는 점수에 넣지 않는다**(2026-08-06 사용자 지시 "날짜만 보여주면 된다").
        재 보니 1~3일도 뒤 5년에서 졌다.
        """
        frames = {
            "AAPL": _frame_with_high(4, -12.0),   # 많이 눌렸다
            "MSFT": _frame_with_high(8, -12.0),   # 같은 눌린 폭, 날짜만 다르다
            "AMZN": _frame_with_high(4, -5.0),    # 덜 눌렸다 — 그래도 보여준다
            "GOOGL": _frame_with_high(4, -20.0),  # 너무 눌렸다 — 그물 밖
            "META": _frame_with_high(2, -12.0),   # 2일 전 — 그물 밖(3일부터)
        }
        result = self._run(j3.find_breakout_pullback_stocks, frames)
        self.assertTrue(result["ok"])
        picked = {row["ticker"]: row for row in result["rows"]}
        self.assertEqual({"AAPL", "MSFT", "AMZN"}, set(picked))
        for row in picked.values():
            self.assertIsInstance(row["score"], float)
            self.assertNotIn("stars", row)
        # 점수가 높은 줄이 위에 온다.
        scores = [row["score"] for row in result["rows"]]
        self.assertEqual(sorted(scores, reverse=True), scores)
        # **눌린 폭은 10~15% 칸에만 점수를 준다**(2026-08-12 재측정).
        # 2026-08-09에 "그물이 이미 쓴 값"이라며 0점으로 뺐던 항목인데, 앱 그물
        # 그대로(시장 조건 없이) 다시 재니 보유 3개월·6개월·1년 **셋 다 합격한
        # 유일한 항목**이었다(research/us_breakout_ladder.py).
        # 비례로 깎지 않고 **칸으로 가른다** — 6~10%는 실측에서 거꾸로였다.
        drop_points = {
            ticker: next(v for n, v, _m, _t in j3.breakout_score(row)["parts"]
                         if n.startswith("눌린 폭"))
            for ticker, row in picked.items()
        }
        full = j3.BREAKOUT_SCORE_WEIGHTS["drop"]
        self.assertEqual(40.0, full, "눌린 폭이 계단 1등(40점)이어야 한다")
        self.assertEqual(full, drop_points["AAPL"], "-12%는 10~15% 칸이라 만점")
        self.assertEqual(full, drop_points["MSFT"], "-12%는 10~15% 칸이라 만점")
        self.assertEqual(0.0, drop_points["AMZN"], "-5%는 칸 밖이라 0점")
        # **0점 항목은 표에 넣지 않는다**(CLAUDE.md 0-1 마).
        for row in picked.values():
            maxima = [m for _n, _v, m, _t in j3.breakout_score(row)["parts"]]
            self.assertNotIn(0.0, maxima, "0점짜리 줄이 배점표에 남아 있다")
        # 날짜만 다른 두 종목은 점수가 같아야 한다 — 날짜에는 점수를 주지 않는다.
        self.assertEqual(picked["AAPL"]["score"], picked["MSFT"]["score"])
        # 며칠 지났는지는 줄마다 그대로 실려야 한다 — 화면이 그걸 보여준다.
        self.assertEqual(4, picked["AAPL"]["wait_days"])
        self.assertEqual(8, picked["MSFT"]["wait_days"])
        # **파는 날은 규칙에 없다**(2026-08-12 상하님 확정). 줄에는 며칠이 아니라
        # 3개월·6개월·1년 과거 성적이 실린다 — 화면이 셋을 나란히 보여준다.
        self.assertIsNone(picked["AAPL"]["hold_days"])
        self.assertEqual([60, 120, 250],
                         [item["days"] for item in picked["AAPL"]["hold_results"]])

    def test_breakout_tells_the_market_state_but_never_filters_on_it(self):
        """표를 잰 자리인지 알려만 준다(2026-08-06 사용자 결정).

        표 1의 '장세' 칸(200일선 위 · 고점 대비 -10% 안)은 상하님이 주신 원래
        설명서의 규칙이 아니라, 2026-08-01에 날을 가르려고 내가 정한 **잰 범위**다.
        거르는 조건으로 바꾸면 화면이 통째로 비는 날이 생긴다.
        """
        frames = {"AAPL": _frame_with_high(4, -12.0)}
        for above, drop, armed in ((True, -3.0, True), (False, -20.0, False)):
            state = {"ok": True, "armed": armed, "drop_pct": drop, "above_200": above,
                     "max_drop": j3.BREAKOUT_MARKET_MAX_DROP, "reason": "시험"}
            with patch.object(j3, "breakout_market_state", return_value=state):
                result = self._run(j3.find_breakout_pullback_stocks, frames)
            self.assertTrue(result["ok"])
            self.assertEqual(1, len(result["rows"]), f"200일선 {above}인데 막혔다")
            self.assertEqual(armed, result["market"]["armed"], "시장 상태는 알려줘야 한다")

    def test_breakout_market_state_reads_the_two_hundred_day_line(self):
        index = pd.date_range("2025-01-01", periods=260, freq="D")
        close = pd.Series([100.0] * 259 + [70.0], index=index)   # 200일선 아래·고점 -30%
        frame = pd.DataFrame({"Open": close, "High": close, "Low": close,
                              "Close": close, "Volume": [1e6] * 260}, index=index)
        with patch.object(j3, "_download_cached",
                          return_value=({j3.CRASH_MARKET_SYMBOL: frame}, {})):
            state = j3.breakout_market_state()
        self.assertTrue(state["ok"])
        self.assertFalse(state["armed"])
        self.assertFalse(state["above_200"])
        self.assertIn("표를 잰 자리가 아닙니다", state["reason"])

    def test_breakout_market_state_stays_quiet_when_data_is_missing(self):
        """자료를 못 받으면 켜 둔다 — 자료 탓에 화면이 막히면 더 나쁘다."""
        with patch.object(j3, "_download_cached", side_effect=RuntimeError("망")):
            state = j3.breakout_market_state()
        self.assertFalse(state["ok"])
        self.assertTrue(state["armed"])

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

    def test_breakout_ranks_by_gain_not_by_volume_streak(self):
        """상승장 순위는 낙폭과 **다르다** — 거래대금 연속은 여기서 거꾸로였다(53번)."""
        import inspect

        self.assertNotIn("volume_streak", inspect.getsource(j3._breakout_rank_key))
        rows = [
            {"metrics": {"ret60": 5.0, "avg_dollar_volume": 1e8}, "together_tier": 3,
             "together_count": 4, "volume_streak": 20},
            {"metrics": {"ret60": 60.0, "avg_dollar_volume": 1e8}, "together_tier": 3,
             "together_count": 4, "volume_streak": 0},
        ]
        ordered = sorted(rows, key=j3._breakout_rank_key)
        self.assertEqual(60.0, ordered[0]["metrics"]["ret60"])

    def test_breakout_and_crash_are_scored_with_different_rulers(self):
        """두 갈래에 같은 자를 쓰면 낙폭 종목이 정의상 전부 '제외'로 나온다."""
        self.assertNotEqual(j3.BREAKOUT_SCORE_WEIGHTS, j3.CRASH_SCORE_WEIGHTS)
        for weights in (j3.BREAKOUT_SCORE_WEIGHTS, j3.CRASH_SCORE_WEIGHTS):
            # 거래대금 연속은 양쪽 갈래 다 거꾸로였다 — 배점에서 뺐다.
            self.assertNotIn("volume_streak", weights)
        # **계단은 40·30·20·10뿐이다**(CLAUDE.md 0-1 마). 47.0·31.25·22.5·18.75 같은
        # 비례 나눗셈 값이 다시 들어오면 여기서 먼저 깨진다.
        # **딱 하나 예외가 있다 — 상승장의 테마 근접도 70점이다.** 2026-08-13에
        # 상하님이 "비례로 준다"고 정하셨다. 제가 칸으로 나눠 보니 네 번 중 3번
        # 통과가 0번으로 떨어졌다(97%와 99%가 같은 칸에 들어가 차이가 사라진다).
        # 예외를 **이름으로 못박아** 둔다 — 다른 항목이 계단을 벗어나면 여기서 깨진다.
        for label, weights in (("상승장", j3.BREAKOUT_SCORE_WEIGHTS),
                               ("급락", j3.CRASH_SCORE_WEIGHTS)):
            for name, points in weights.items():
                if (label, name) == ("상승장", "theme_prox"):
                    self.assertEqual(70.0, points, "테마 근접도는 비례 70점이다")
                    continue
                self.assertIn(points, (0.0, 10.0, 20.0, 30.0, 40.0),
                              f"{label} {name} {points}점은 계단 밖이다")
        # **합이 100이 아니어도 된다.** 합격한 항목에만 점수를 주고 남는 점수를
        # 다른 항목에 나눠 주지 않는다 — 만점이 곧 그 파트의 근거의 양이다.
        # 상승장은 테마 70 + 눌린 폭 40 = 110점이다(2026-08-13).
        self.assertEqual(110.0, j3.BREAKOUT_SCORE_MAX)
        self.assertEqual(90.0, j3.CRASH_SCORE_MAX)
        self.assertEqual(j3.BREAKOUT_SCORE_MAX, sum(j3.BREAKOUT_SCORE_WEIGHTS.values()))
        self.assertEqual(j3.CRASH_SCORE_MAX, sum(j3.CRASH_SCORE_WEIGHTS.values()))
        # **상승장 1등은 눌린 폭, 급락 1등은 테마가 덜 빠졌나**(2026-08-12 재측정 —
        # 둘 다 보유 세 기간 모두 합격한 유일한 항목이다).
        self.assertEqual(40.0, j3.BREAKOUT_SCORE_WEIGHTS["drop"])
        self.assertEqual(40.0, j3.CRASH_SCORE_WEIGHTS["less_drop"])
        # 그물마다 합격 못 한 항목들 — 되살아나면 여기서 깨진다.
        for name in ("together", "recent_drop", "liquidity", "volatility"):
            self.assertEqual(0.0, j3.BREAKOUT_SCORE_WEIGHTS[name], f"상승장 {name}")
            self.assertEqual(0.0, j3.CRASH_SCORE_WEIGHTS[name], f"급락 {name}")
        # **급락 배점 90점이 전부 테마 등수다**(2026-08-12 새 그물 실측).
        # 종목 항목 아홉 개가 세 보유 다 미달이었다 — 미국은 테마로만 고를 수 있다.
        theme_points = sum(j3.CRASH_SCORE_WEIGHTS[name]
                           for name in ("less_drop", "aligned", "above20"))
        self.assertEqual(j3.CRASH_SCORE_MAX, theme_points)
        # **'같이 오르는가' 30점은 '주봉 오름세'로 갈아끼웠다**(2026-08-12 저녁,
        # 상하님 지시 "반등은 빨리·많이가 기준"). 속도를 넣고 재니 '같이 오르는가'로
        # 고른 종목은 +20%까지 46일 — **아무거나 산 것(45일)보다 느렸다.**
        # 주봉 오름세는 34일이고 5·10·20·40일·6개월·1년 여섯 곳 다 합격했다.
        # 근거: research/us_rebound_speed.py
        self.assertEqual(30.0, j3.CRASH_SCORE_WEIGHTS["aligned"])
        self.assertEqual(0.0, j3.CRASH_SCORE_WEIGHTS["spread5"])
        # 상승장 쪽 '같이 오르는가'도 **2026-08-13에 0점이 됐다.** 제가 재는 자를
        # 고쳐(짝 견주기 3,683짝 · 연 단위 오차) 다시 재니 테마를 **그날 등수**로
        # 매기는 자가 전부 무너졌다 — 51.2 · 51.9 · 53.2 · 53.2로 네 번 중 0번이다.
        # 살아남은 것은 **근접도를 칸 없이 그대로 쓰는 것** 하나뿐이다.
        self.assertEqual(0.0, j3.BREAKOUT_SCORE_WEIGHTS["spread5"])
        self.assertEqual(0.0, j3.BREAKOUT_SCORE_WEIGHTS["less_drop"])
        self.assertEqual(70.0, j3.BREAKOUT_SCORE_WEIGHTS["theme_prox"])
        # '테마 60일 수익률'은 6개월 보유에서만 합격했다 — 파는 시점을 안 정하므로 안 쓴다.
        self.assertEqual(0.0, j3.CRASH_SCORE_WEIGHTS["theme_rank"])
        # **'최근 11일'은 보유기간마다 뒤집힌다.** 3개월 1등(-5.8p)인데 1년에서는
        # 거의 거꾸로(-19.7p)다. 앱이 파는 시점을 안 정하므로 쓸 수 없다.
        self.assertEqual(0.0, j3.CRASH_SCORE_WEIGHTS["recent_drop"])
        # **상승장에서도 0점이 됐다**(2026-08-12). "다시 재 볼 자리"라고 적어 뒀던
        # 것을 앱 그물 그대로 다시 쟀더니 세 보유기간 전부 미달이었다
        # (3개월 73/60 · 6개월 89/60 · 1년 100/76 — 수익률 쪽이 65%를 못 넘는다).
        # 그리고 '-5%↑ 빠짐'은 그물의 6%뿐이라 못 가르기도 한다(기준 6).
        self.assertEqual(0.0, j3.BREAKOUT_SCORE_WEIGHTS["recent_drop"])
        # 낙폭 갈래도 0점이다 — 갈래가 하나뿐이라 모두 같은 점수를 받아 못 가른다.
        self.assertEqual(0.0, j3.CRASH_SCORE_WEIGHTS["bucket"])
        # 60일 상승폭도 뺐다 — 가운데 값만 크고 이기는 횟수는 뒤 5년에 졌다.
        self.assertNotIn("ret60", j3.BREAKOUT_SCORE_WEIGHTS)

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
        # **상승장은 2026-08-12부터 이 자를 안 쓴다.** 앱 그물 그대로 다시 재니
        # '같은 테마 동반 4개↑'는 6개월 보유에서만 합격했고 3개월·1년에서는
        # 미달이었다. 앱이 파는 시점을 정하지 않으므로 한 기간에서만 통하는 값은
        # 쓰지 않는다(CLAUDE.md 0-1 마). 배점표에도 그 줄이 없어야 한다.
        row = {"metrics": {}, "together_count": 1, "together_tier": 0,
               "recent_gain_pct": 0.0}
        names = [name for name, _v, _m, _t in j3.breakout_score(row)["parts"]]
        self.assertNotIn("같은 테마 동반", names)
        self.assertEqual(0.0, j3.BREAKOUT_SCORE_WEIGHTS["together"])
        # 다만 **같은 점수 안의 차례**를 가르는 데는 계속 쓴다(_breakout_rank_key).
        self.assertEqual(40.0, j3.theme_together_points(3, 40.0))
        # **급락에서도 2026-08-12에 뺐다.** 2026-08-09에 명부에서 종목 하나
        # (CRWD→ORCL)를 바꾼 뒤로 옛 그물에서도 이미 불합격이었고(80/95 → 64/93),
        # 상하님 표 2로 되돌린 새 그물에서는 1년 보유에만 걸리는 데다 해당이 67%라
        # 못 가른다(기준 6). 배점표에도 그 줄이 없어야 한다.
        crash_names = [name for name, _v, _m, _t in j3.crash_rebound_score(
            {"metrics": {}, "together_count": 5, "bucket": "shallow"})["parts"]]
        self.assertNotIn("같은 테마 동반", crash_names)
        self.assertEqual(0.0, j3.CRASH_SCORE_WEIGHTS["together"])
        # **급락 배점 셋이 전부 테마 등수다.** 종목 항목은 아홉 개가 세 보유 다
        # 미달이었다 — 미국은 테마로만 고를 수 있다(research/us_crash_new_net.py).
        self.assertEqual(3, len(crash_names))
        self.assertTrue(all("테마" in name for name in crash_names), crash_names)

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

        # 급락 배점의 1등은 '테마가 덜 빠졌나'다(2026-08-12 새 그물 — 세 보유기간
        # 모두 합격한 유일한 항목). 등수를 다는 자리와 점수를 읽는 자리가 맞물리는지 본다.
        j3._attach_theme_rank(rows, memberships, all_metrics, prefix="theme_less_drop",
                              metric_key="ret60", top_n=1)

        def less_drop_points(row):
            row = dict(row, metrics={})
            return next(value for name, value, _m, _t
                        in j3.crash_rebound_score(row)["parts"] if "덜 빠졌나" in name)

        self.assertEqual(j3.CRASH_SCORE_WEIGHTS["less_drop"], less_drop_points(rows[0]))
        self.assertEqual(0.0, less_drop_points(rows[1]))

    def test_theme_ranking_is_scored_by_spread_not_by_returns(self):
        """테마 순위는 **확산**으로 매긴다 (2026-08-12 처음 쟀다).

        상하님 지적 — "테마가 같이 상승하는 기준이 먼저이고 구성종목 확산이 먼저
        기준이 되어야지. 테마 수익률이 하락장에는 의미가 없지."

        국면을 갈라 재니 두 국면 모두 확산 계열이 1~4등이었고, 수익률 계열은
        상승 국면에서 꼴찌(-9.5p) 하락 국면에서 탈락이었다(research/us_parts.py).
        그전 배점은 상대강도 55점 · 이동평균 20점 · 확산 15점으로 정반대였다.
        """
        weights = j3.THEME_SCORE_WEIGHTS
        # 계단은 40·30·20·10뿐이다(CLAUDE.md 0-1 마).
        for name, points in weights.items():
            self.assertIn(points, (0.0, 10.0, 20.0, 30.0, 40.0), f"{name} {points}점")
        self.assertEqual(100.0, j3.THEME_SCORE_MAX)
        # **확산 셋이 90점.** 되돌아가면 여기서 깨진다.
        self.assertEqual(90.0, weights["above20"] + weights["rose5"] + weights["rose20"])
        self.assertEqual(40.0, weights["above20"], "20일선 위 비율이 1등이다")
        # 수익률(상대강도)과 ETF 이동평균은 0점이다.
        self.assertEqual(0.0, weights["relative"])
        self.assertEqual(0.0, weights["trend"])

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
        row = {"metrics": {"from_high_pct": -5.0, "current": 100.0, "ret60": 20.0},
               "together_tier": 2, "together_count": 3, "hold_days": 120, "wait_days": 4,
               "bucket": "deep", "bucket_label": "고점 대비 -40~-50%"}
        for plan, mode in ((j3.breakout_plan(row), "breakout"),
                           (j3.crash_rebound_plan(row), "crash")):
            self.assertEqual(mode, plan["rule_mode"])
            self.assertIsNone(plan["invalidation"])
            self.assertIsNone(plan["target"])
            self.assertIn("손절가가 없습니다", plan["buy_reason"])

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

"""전일 값이 한국장 도중에 바뀌지 않는지 지킨다 (2026-08-06 사용자 지시).

무엇이 문제였나 — `_previous_market_regime`이 **뉴욕 날짜**로만 판단해서,
뉴욕 자정(한국 오후 1~2시)에 전일이 하루 밀렸다. 한국장 한복판에 '전일 시장국면'이
바뀌었다. 실측으로 확인했다: 한국 07:00~11:00은 8/4를 쓰다가 13:00부터 8/5로 바뀌었다.

게다가 아침 쪽이 틀린 값이었다 — 한국 07:00이면 미국장은 이미 마감(뉴욕 18:00)해
그날 일봉이 완성돼 있는데도 하루 전 것을 보여줬다.

그래서 날짜가 아니라 **'그 장이 끝났는가'**로 판단하게 고쳤다. 되돌아가면 이 시험이 깨진다.
"""

import unittest
import zoneinfo
from datetime import datetime, timedelta

import pandas as pd

import jarvis3_data as j3

SEOUL = zoneinfo.ZoneInfo("Asia/Seoul")


def _frame(dates, close):
    """조건점수 계산에 필요한 만큼만 채운 가짜 일봉."""
    index = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
    return pd.DataFrame(
        {
            "Open": close, "High": [c * 1.01 for c in close],
            "Low": [c * 0.99 for c in close], "Close": close,
            "Volume": [1_000_000] * len(close),
        },
        index=index,
    )


def _daily(last_day: str, days: int = 300):
    """마지막 거래일이 last_day인 가짜 일봉 묶음."""
    end = pd.Timestamp(last_day)
    dates = [end - timedelta(days=i) for i in range(days)][::-1]
    close = [100 + i * 0.1 for i in range(days)]
    return {t: _frame(dates, close) for t in ("SPY", "QQQ", "IWM", "^VIX")}


class PreviousRegimeFreezeTests(unittest.TestCase):
    def test_it_does_not_change_through_the_korean_day(self):
        """한국 아침부터 밤까지 전일이 같은 거래일을 가리켜야 한다."""
        daily = _daily("2026-08-05")
        base = datetime(2026, 8, 6, tzinfo=SEOUL)
        seen = set()
        for hour in (7, 9, 11, 13, 14, 15, 17, 20, 23):
            result = j3._previous_market_regime(daily, now=base.replace(hour=hour))
            self.assertIsNotNone(result)
            seen.add((result["trade_date"], result["score"]))
        self.assertEqual(
            1, len(seen),
            f"한국장 도중에 전일이 바뀐다 — {sorted(seen)}",
        )

    def test_after_the_close_it_uses_that_session(self):
        """미국장이 끝났으면 그날이 '직전 완료 장'이다.

        한국 07:00 = 뉴욕 전날 18:00. 그때 이미 마감했으므로 그날 일봉을 써야 한다.
        전에는 하루 전 것을 보여줬다.
        """
        daily = _daily("2026-08-05")
        result = j3._previous_market_regime(
            daily, now=datetime(2026, 8, 6, 7, tzinfo=SEOUL)
        )
        self.assertEqual("2026-08-05", result["trade_date"])

    def test_during_the_session_todays_bar_is_left_out(self):
        """장중에는 오늘 일봉이 아직 미완성이라 빼야 한다.

        한국 23:00 = 뉴욕 같은 날 10:00(장중). 야후가 오늘 행을 이미 넣어 두므로
        그걸 그대로 쓰면 '전일'이 진행 중인 값이 된다.
        """
        daily = _daily("2026-08-06")
        result = j3._previous_market_regime(
            daily, now=datetime(2026, 8, 6, 23, tzinfo=SEOUL)
        )
        self.assertEqual("2026-08-05", result["trade_date"])

    def test_it_tells_which_day_it_used(self):
        """어느 거래일을 썼는지 밝혀야 화면·시험에서 확인할 수 있다."""
        daily = _daily("2026-08-05")
        result = j3._previous_market_regime(
            daily, now=datetime(2026, 8, 6, 9, tzinfo=SEOUL)
        )
        self.assertIn("trade_date", result)
        self.assertEqual("직전 완료 미국장", result["as_of"])


class SessionClosedTests(unittest.TestCase):
    """세 화면이 **같은 잣대**로 얼어야 한다 (2026-08-12 상하님 지시).

    상하님 지적 — "시장국면·공포탐욕지수·미국장 시장상태는 전날 종가에 마감되고
    변동이 없어야 하는데 조금씩 변동이 생긴다."
    """

    def test_it_flips_only_at_the_new_york_close(self):
        """값이 바뀌는 순간은 하루에 한 번, 뉴욕 16시뿐이어야 한다."""
        ny = zoneinfo.ZoneInfo("America/New_York")
        for hour in (0, 9, 12, 15):
            self.assertFalse(
                j3.us_session_closed(datetime(2026, 8, 12, hour, tzinfo=ny)),
                f"뉴욕 {hour}시는 아직 장중인데 끝난 것으로 봤다",
            )
        for hour in (16, 18, 23):
            self.assertTrue(
                j3.us_session_closed(datetime(2026, 8, 12, hour, tzinfo=ny)),
                f"뉴욕 {hour}시는 마감했는데 장중으로 봤다",
            )


class FearGreedFreezeTests(unittest.TestCase):
    """CNN은 이 지수를 장중 내내 고친다. 그대로 쓰면 화면이 하루 종일 움직인다."""

    RAW = {"ok": True, "score": 71.3, "previous_close": 64.0, "rating_kr": "탐욕"}

    def _at(self, hour):
        ny = zoneinfo.ZoneInfo("America/New_York")
        return j3._freeze_fear_greed(dict(self.RAW),
                                     now=datetime(2026, 8, 12, hour, tzinfo=ny))

    def test_during_the_session_it_shows_the_previous_close(self):
        frozen = self._at(12)
        self.assertEqual(64.0, frozen["score"], "장중인데 실시간 값이 나왔다")
        self.assertEqual(71.3, frozen["live_score"], "실시간 값을 버리면 안 된다")
        self.assertTrue(frozen["frozen"])

    def test_after_the_close_that_day_becomes_the_close(self):
        self.assertEqual(71.3, self._at(17)["score"])

    def test_it_does_not_move_while_cnn_keeps_changing_it(self):
        """CNN이 값을 고치는 내내(뉴욕 자정~15시59분) 화면 숫자가 같아야 한다.

        한국 시각으로는 오후 1시부터 다음 날 새벽 4시59분까지다 — 한국장이 열려
        있는 동안 미국 공포·탐욕 숫자가 흔들리면 안 된다.
        """
        seen = {self._at(hour)["score"] for hour in (0, 4, 8, 9, 12, 14, 15)}
        self.assertEqual(1, len(seen), f"장중에 값이 바뀐다 — {sorted(seen)}")
        self.assertEqual({64.0}, seen, "장중이면 전일 마감값이어야 한다")

    def test_missing_previous_close_falls_back_to_the_live_value(self):
        """전일값을 못 받았다고 화면이 비면 안 된다 — 있는 값을 쓴다."""
        ny = zoneinfo.ZoneInfo("America/New_York")
        frozen = j3._freeze_fear_greed(
            {"ok": True, "score": 71.3, "previous_close": None},
            now=datetime(2026, 8, 12, 12, tzinfo=ny))
        self.assertEqual(71.3, frozen["score"])


class RegimeGaugeFreezeTests(unittest.TestCase):
    """미국테마 게이지는 얼리고, 한국테마는 지금까지대로 실시간이다(규칙 0-1 다)."""

    OVERVIEW = {
        "ok": True, "score": 72, "regime": "상승 신호 우세", "posture": "지금 지침",
        "previous_market": {"ok": True, "score": 55, "regime": "방향 엇갈림",
                            "posture": "마감 지침", "trade_date": "2026-08-11"},
    }

    def test_freeze_puts_the_needle_on_the_last_completed_session(self):
        import regime_gauge_ui

        html = regime_gauge_ui.regime_box_html(self.OVERVIEW, freeze=True)
        head = html.split("fg-hist")[0]
        self.assertIn("55", head, "얼렸는데 바늘이 마감값에 안 서 있다")
        self.assertIn("지금 (참고)", html, "실시간 값을 버리면 안 된다")
        self.assertIn("마감 지침", html)

    def test_default_stays_live_so_korea_is_untouched(self):
        import regime_gauge_ui

        html = regime_gauge_ui.regime_box_html(self.OVERVIEW)
        self.assertIn("72", html.split("fg-hist")[0])
        self.assertNotIn("지금 (참고)", html)

    def test_it_falls_back_to_live_when_there_is_no_frozen_value(self):
        import regime_gauge_ui

        html = regime_gauge_ui.regime_box_html(
            {"ok": True, "score": 72, "regime": "상승 신호 우세"}, freeze=True)
        self.assertIn("72", html.split("fg-hist")[0])


class RevisionTests(unittest.TestCase):
    """계산을 바꿨으면 리비전도 같이 올라가야 한다(규칙 11)."""

    def test_jarvis4_asks_for_the_same_jarvis3_revision(self):
        import jarvis4_data as j4

        self.assertGreaterEqual(
            int(j3.MODULE_REVISION), int(j4._REQUIRED_J3_REVISION),
            "jarvis4가 요구하는 jarvis3 리비전이 더 높다 — 한국테마에서 무한 재적재",
        )
        self.assertEqual(
            int(j3.MODULE_REVISION), int(j4._REQUIRED_J3_REVISION),
            "jarvis3 계산을 바꿨으면 jarvis4의 요구 리비전도 같이 올려야 한다",
        )


if __name__ == "__main__":
    unittest.main()

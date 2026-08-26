"""미국 증시 휴장일·조기 폐장·세션 날짜 시험.

실제로 있었던 날짜로 맞춰 본다. 규칙만 맞고 날짜가 틀리면 화면이 하루씩 어긋난다.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, time as dt_time
from zoneinfo import ZoneInfo

import us_market_calendar as cal


NY = ZoneInfo("America/New_York")
SEOUL = ZoneInfo("Asia/Seoul")


class HolidayTests(unittest.TestCase):
    def test_2026_holidays_match_the_exchange_calendar(self):
        got = cal.holidays(2026)
        expected = {
            date(2026, 1, 1): "새해 첫날",
            date(2026, 1, 19): "마틴 루서 킹 데이",
            date(2026, 2, 16): "대통령의 날",
            date(2026, 4, 3): "성금요일",
            date(2026, 5, 25): "현충일",
            date(2026, 6, 19): "준틴스",
            date(2026, 7, 3): "독립기념일",       # 7월 4일이 토요일 → 하루 앞
            date(2026, 9, 7): "노동절",
            date(2026, 11, 26): "추수감사절",
            date(2026, 12, 25): "성탄절",
        }
        self.assertEqual(got, expected)

    def test_new_year_on_saturday_is_not_moved_back(self):
        """설날만 예외다 — 토요일에 걸려도 전해 12월 31일에는 열려 있다."""
        self.assertNotIn(date(2021, 12, 31), cal.holidays(2021))
        self.assertTrue(cal.is_trading_day(date(2021, 12, 31)))

    def test_sunday_holiday_moves_to_monday(self):
        self.assertEqual(cal.holiday_name(date(2021, 7, 5)), "독립기념일")
        self.assertFalse(cal.is_trading_day(date(2021, 7, 5)))

    def test_good_friday_is_closed(self):
        self.assertEqual(cal.holiday_name(date(2026, 4, 3)), "성금요일")
        self.assertEqual(cal.holiday_name(date(2025, 4, 18)), "성금요일")

    def test_juneteenth_starts_in_2022(self):
        self.assertNotIn("준틴스", cal.holidays(2021).values())
        self.assertIn("준틴스", cal.holidays(2022).values())


class EarlyCloseTests(unittest.TestCase):
    def test_black_friday_closes_at_one(self):
        black_friday = date(2026, 11, 27)
        self.assertEqual(cal.early_close_name(black_friday), "추수감사절 다음날")
        self.assertEqual(cal.close_time(black_friday), dt_time(13, 0))

    def test_christmas_eve_closes_at_one(self):
        self.assertEqual(cal.close_time(date(2026, 12, 24)), dt_time(13, 0))

    def test_normal_day_closes_at_four(self):
        self.assertEqual(cal.close_time(date(2026, 8, 25)), dt_time(16, 0))

    def test_early_close_day_is_over_at_one(self):
        """일찍 닫는 날 오후 1시 30분은 이미 끝난 장이다."""
        after = datetime(2026, 11, 27, 13, 30, tzinfo=NY)
        self.assertTrue(cal.session_closed(after))
        before = datetime(2026, 11, 27, 12, 30, tzinfo=NY)
        self.assertFalse(cal.session_closed(before))


class SessionDateTests(unittest.TestCase):
    def test_capture_moment_from_2026_08_26(self):
        """상하님 캡처 시각 — 한국 8/26 01:23 = 뉴욕 8/25(화) 12:23, 장중."""
        now = datetime(2026, 8, 26, 1, 23, tzinfo=SEOUL)
        self.assertEqual(cal.phase(now)["label"], "정규장 시간")
        self.assertEqual(cal.current_session_date(now), date(2026, 8, 25))
        self.assertEqual(cal.previous_session_date(now), date(2026, 8, 24))

    def test_current_day_moves_on_at_the_closing_bell(self):
        """마감 종이 울리면 당일은 곧바로 다음 장으로 넘어간다."""
        before = datetime(2026, 8, 25, 15, 59, tzinfo=NY)
        after = datetime(2026, 8, 25, 16, 0, tzinfo=NY)
        self.assertEqual(cal.current_session_date(before), date(2026, 8, 25))
        self.assertEqual(cal.previous_session_date(before), date(2026, 8, 24))
        self.assertEqual(cal.current_session_date(after), date(2026, 8, 26))
        self.assertEqual(cal.previous_session_date(after), date(2026, 8, 25))

    def test_friday_close_points_at_monday(self):
        friday_evening = datetime(2026, 8, 21, 17, 0, tzinfo=NY)
        self.assertEqual(cal.current_session_date(friday_evening), date(2026, 8, 24))
        self.assertEqual(cal.previous_session_date(friday_evening), date(2026, 8, 21))

    def test_holiday_is_skipped_on_both_sides(self):
        """9월 7일 노동절(월). 금요일 마감 뒤의 당일은 화요일이다."""
        friday_evening = datetime(2026, 9, 4, 17, 0, tzinfo=NY)
        self.assertEqual(cal.current_session_date(friday_evening), date(2026, 9, 8))
        self.assertEqual(cal.previous_session_date(friday_evening), date(2026, 9, 4))
        labor_day_noon = datetime(2026, 9, 7, 12, 0, tzinfo=NY)
        self.assertEqual(cal.phase(labor_day_noon)["label"], "휴장")
        self.assertEqual(cal.phase(labor_day_noon)["holiday"], "노동절")
        self.assertTrue(cal.session_closed(labor_day_noon))

    def test_thanksgiving_week(self):
        """추수감사절(목) 휴장, 다음날(금) 오후 1시 마감."""
        thursday = datetime(2026, 11, 26, 12, 0, tzinfo=NY)
        self.assertEqual(cal.phase(thursday)["holiday"], "추수감사절")
        self.assertEqual(cal.current_session_date(thursday), date(2026, 11, 27))
        friday_after_one = datetime(2026, 11, 27, 14, 0, tzinfo=NY)
        self.assertEqual(cal.previous_session_date(friday_after_one), date(2026, 11, 27))
        self.assertEqual(cal.current_session_date(friday_after_one), date(2026, 11, 30))

    def test_phase_names_before_and_after_the_bell(self):
        day = date(2026, 8, 25)
        cases = [(3, "정규장 전"), (5, "프리마켓"), (10, "정규장 시간"),
                 (17, "애프터마켓"), (21, "장 마감")]
        for hour, label in cases:
            with self.subTest(hour=hour):
                moment = datetime(day.year, day.month, day.day, hour, tzinfo=NY)
                self.assertEqual(cal.phase(moment)["label"], label)

    def test_summer_time_switch_is_handled(self):
        """썸머타임은 뉴욕 시간대가 알아서 바꾼다 — 한국과의 시차가 달라진다."""
        summer = datetime(2026, 8, 25, 16, 0, tzinfo=NY).astimezone(SEOUL)
        winter = datetime(2026, 12, 15, 16, 0, tzinfo=NY).astimezone(SEOUL)
        self.assertEqual(summer.hour, 5)    # 한국 새벽 5시
        self.assertEqual(winter.hour, 6)    # 한국 새벽 6시


if __name__ == "__main__":
    unittest.main()

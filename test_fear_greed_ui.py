"""공포·탐욕 게이지 그림 테스트 — 그림만 검증한다(점수 계산은 이 모듈이 하지 않는다)."""

import re
import unittest

import fear_greed_ui as fg
import gauge_ui


class ZoneTests(unittest.TestCase):
    def test_zone_boundaries_match_cnn_ranges(self):
        """CNN과 같은 다섯 구간이며 이름은 한국어다."""
        cases = [
            (0, "극단적 공포"), (25, "극단적 공포"),
            (25.1, "공포"), (44.9, "공포"),
            (45.1, "중립"), (55, "중립"),
            (55.1, "탐욕"), (74.9, "탐욕"),
            (75.1, "극단적 탐욕"), (100, "극단적 탐욕"),
        ]
        for score, expected in cases:
            with self.subTest(score=score):
                self.assertEqual(fg.zone_of(score)[0], expected)

    def test_missing_score_is_reported_not_guessed(self):
        self.assertEqual(fg.zone_of(None)[0], "자료 부족")

    def test_out_of_range_score_is_clamped(self):
        self.assertEqual(fg.zone_of(-10)[0], "극단적 공포")
        self.assertEqual(fg.zone_of(140)[0], "극단적 탐욕")


class GaugeTests(unittest.TestCase):
    def test_needle_points_left_for_fear_and_right_for_greed(self):
        """바늘 방향이 점수를 따라가야 한다 — 그림이 값과 어긋나면 안 된다."""

        def needle_x(score):
            match = re.search(r"<line[^>]*class='fg-needle'", fg.gauge_svg(score))
            self.assertIsNotNone(match, "바늘이 없습니다")
            return float(re.search(r"x2='([\d.]+)'", fg.gauge_svg(score)).group(1))

        low, middle, high = needle_x(5), needle_x(50), needle_x(95)
        self.assertLess(low, middle)
        self.assertLess(middle, high)
        self.assertAlmostEqual(middle, fg._CENTER_X, delta=1.0)

    def test_no_needle_when_score_missing(self):
        svg = fg.gauge_svg(None)
        self.assertNotIn("fg-needle", svg)
        self.assertIn("자료 부족", svg)

    def test_five_zones_are_drawn(self):
        self.assertEqual(fg.gauge_svg(50).count("<path"), len(fg.ZONES))


class CardTests(unittest.TestCase):
    def _data(self, **extra):
        base = {
            "ok": True, "score": 41.0, "rating_kr": "공포", "previous_close": 45.0,
            "previous_1_week": 55.0, "previous_1_month": 57.0, "previous_1_year": 44.0,
        }
        base.update(extra)
        return base

    def test_card_shows_score_zone_and_history(self):
        html = fg.card_html(self._data())
        self.assertIn("공포·탐욕 지수", html)
        self.assertIn(">41<", html)
        self.assertIn("전일 종가", html)
        self.assertIn("1주 전", html)
        self.assertIn("1년 전", html)

    def test_previous_close_row_is_purple(self):
        """맨 아랫줄('전일 종가')만 보라색이다 (2026-08-21 상하님 지시).

        위 셋(1주·1개월·1년 전)은 지금까지대로 구간 색을 쓴다.
        """
        html = fg.card_html(self._data())
        self.assertIn("color:#c084fc; font-weight:800'>전일 종가", html)
        self.assertIn("<span class='fg-hist-value' style='background:#c084fc'>45", html)
        # 1주 전(55 = 탐욕 구간)은 보라가 아니어야 한다.
        self.assertIn("<span class='fg-hist-label'>1주 전</span>", html)

    def test_card_says_it_is_not_used_for_judgement(self):
        """점수·판정에 반영하지 않는다는 사실이 화면에 남아 있어야 한다."""
        self.assertIn("판정에는 반영하지 않습니다", fg.card_html(self._data()))

    def test_missing_data_is_reported_not_blank(self):
        html = fg.card_html({"ok": False})
        self.assertIn("자료 부족", html)
        self.assertIn("받아오지 못했습니다", html)

    def test_stale_value_is_disclosed(self):
        self.assertIn("마지막 정상값", fg.card_html(self._data(stale=True)))

    def test_history_skips_missing_entries(self):
        html = fg.card_html({"ok": True, "score": 41.0, "previous_close": 45.0})
        self.assertIn("전일 종가", html)
        self.assertNotIn("1주 전", html)

    def test_labels_are_korean_only(self):
        html = fg.card_html(self._data())
        for english in ("EXTREME FEAR", "GREED", "NEUTRAL", "Fear & Greed"):
            self.assertNotIn(english, html)

    def test_us_country_suffix_only_uses_bright_green(self):
        html = fg.box_html(self._data(), title="공포·탐욕 지수 (미국)")
        self.assertIn(
            f"공포·탐욕 지수 <span style='color:{gauge_ui.TITLE_GREEN}'>(미국)</span>",
            html,
        )


if __name__ == "__main__":
    unittest.main()

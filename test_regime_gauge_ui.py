"""시장 국면·미국 전일 게이지 테스트 — 그림만 검증한다(판정은 이 모듈이 하지 않는다)."""

import re
import unittest

import gauge_ui
import regime_gauge_ui as rg


class ZoneTests(unittest.TestCase):
    def test_zones_match_the_judgement_thresholds(self):
        """0~49 방어 · 50~74 중립 · 75~100 상승 — 데이터 모듈 기준과 같아야 한다."""
        cases = [
            (0, "방어 우선"), (49, "방어 우선"),
            (50, "중립·선별"), (74, "중립·선별"),
            (75, "상승 우위"), (100, "상승 우위"),
        ]
        for score, expected in cases:
            with self.subTest(score=score):
                self.assertEqual(gauge_ui.zone_of(score, rg.ZONES)[0], expected)

    def test_color_of_matches_the_zone(self):
        self.assertEqual(rg.color_of(30), "#ff5b5b")
        self.assertEqual(rg.color_of(62), "#ff9d3b")
        self.assertEqual(rg.color_of(85), "#44f0a1")
        self.assertEqual(rg.color_of(None), "#e6e6e6")


class RegimeBoxTests(unittest.TestCase):
    def _overview(self, score=30, regime="방어 우선"):
        return {"ok": True, "score": score, "regime": regime, "posture": "신규 매수 보류"}

    def test_box_shows_score_regime_and_all_three_ranges(self):
        html = rg.regime_box_html(self._overview())
        self.assertIn(">30<", html)
        self.assertIn("방어 우선", html)
        self.assertIn("0~49", html)
        self.assertIn("50~74", html)
        self.assertIn("75~100", html)
        self.assertIn("신규 매수 보류", html)

    def test_current_zone_is_marked_and_others_dimmed(self):
        html = rg.regime_box_html(self._overview(score=62, regime="중립·선별"))
        rows = ["<div class='fg-hist-row'" + part
                for part in html.split("<div class='fg-hist-row'")[1:]]
        self.assertEqual(len(rows), 3)
        current = [row for row in rows if "지금" in row]
        self.assertEqual(len(current), 1)
        self.assertIn("50~74", current[0])
        self.assertNotIn("opacity", current[0], "지금 구간은 흐리게 하지 않는다")
        self.assertTrue(all("opacity" in row for row in rows if "지금" not in row))

    def test_needle_follows_the_score(self):
        def needle_x(score):
            html = rg.regime_box_html(self._overview(score=score))
            return float(re.search(r"class='fg-needle'[^>]*", html) and
                         re.search(r"x2='([\d.]+)'", html).group(1))

        self.assertLess(needle_x(10), needle_x(60))
        self.assertLess(needle_x(60), needle_x(95))

    def test_missing_data_draws_no_needle(self):
        html = rg.regime_box_html({"ok": False})
        self.assertNotIn("fg-needle", html)
        self.assertIn("자료 부족", html)

    def test_title_colour_differs_from_fear_greed(self):
        """세 박스가 나란히 서므로 제목 색이 겹치면 안 된다."""
        self.assertIn(gauge_ui.TITLE_GREEN, rg.regime_box_html(self._overview()))
        self.assertIn(gauge_ui.TITLE_GREEN_DEEP, rg.us_prev_box_html({
            "ok": True, "score": 65, "regime": "중립·선별", "spy_change": 0.1, "qqq_change": 0.2,
        }))
        self.assertNotEqual(gauge_ui.TITLE_GREEN, gauge_ui.TITLE_GREEN_DEEP)
        self.assertNotEqual(gauge_ui.TITLE_GREEN, gauge_ui.TITLE_BLUE)


class UsPrevBoxTests(unittest.TestCase):
    def _us(self, **extra):
        base = {"ok": True, "score": 65, "regime": "중립·선별",
                "spy_change": 0.08, "qqq_change": 0.23}
        base.update(extra)
        return base

    def test_box_shows_index_changes_with_us_colours(self):
        html = rg.us_prev_box_html(self._us())
        self.assertIn("S&amp;P500", html)
        self.assertIn("나스닥100", html)
        self.assertIn("+0.08%", html)
        # 미국장 색 규칙 — 상승은 파랑
        self.assertIn("#4da6ff", html)

    def test_box_also_shows_all_three_score_ranges(self):
        """이 점수는 자비스3 '시장 국면'과 같은 계산이므로 구간도 같이 보여준다."""
        html = rg.us_prev_box_html(self._us())
        for text in ("방어 우선", "0~49", "중립·선별", "50~74", "상승 우위", "75~100"):
            self.assertIn(text, html)
        rows = ["<div class='fg-hist-row'" + part
                for part in html.split("<div class='fg-hist-row'")[1:]]
        self.assertEqual(len(rows), 5, "구간 3줄 + 지수 2줄")
        current = [row for row in rows if "지금" in row]
        self.assertEqual(len(current), 1)
        self.assertIn("50~74", current[0], "65점은 중립·선별 구간이다")

    def test_falling_index_uses_red(self):
        html = rg.us_prev_box_html(self._us(spy_change=-1.2))
        self.assertIn("-1.20%", html)
        self.assertIn("#ff5b5b", html)

    def test_missing_data_is_reported_not_guessed(self):
        html = rg.us_prev_box_html({"ok": False})
        self.assertIn("자료 없음", html)
        self.assertNotIn("fg-needle", html)


if __name__ == "__main__":
    unittest.main()

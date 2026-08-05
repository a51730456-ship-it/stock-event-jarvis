"""시장 국면·미국 전일 게이지 테스트 — 그림만 검증한다(판정은 이 모듈이 하지 않는다)."""

import re
import unittest

import gauge_ui
import regime_gauge_ui as rg


class ZoneTests(unittest.TestCase):
    def test_zones_match_the_judgement_thresholds(self):
        """다섯 칸 — 데이터 모듈(jarvis3_data·jarvis4_data) 기준과 같아야 한다."""
        cases = [
            (0, "하락 압력 큼"), (29, "하락 압력 큼"),
            (30, "약세 신호 우세"), (49, "약세 신호 우세"),
            (50, "방향 엇갈림"), (64, "방향 엇갈림"),
            (65, "상승 신호 우세"), (79, "상승 신호 우세"),
            (80, "상승 여건 양호"), (100, "상승 여건 양호"),
        ]
        for score, expected in cases:
            with self.subTest(score=score):
                self.assertEqual(gauge_ui.zone_of(score, rg.ZONES)[0], expected)

    def test_zones_match_the_data_modules(self):
        """화면 구간과 판정 함수가 어긋나면 같은 점수에 다른 이름이 붙는다."""
        import jarvis3_data
        import jarvis4_data

        for score in (0, 15, 29, 30, 40, 49, 50, 60, 64, 65, 70, 79, 80, 95, 100):
            with self.subTest(score=score):
                self.assertEqual(
                    jarvis4_data._market_regime_label(score)[0],
                    gauge_ui.zone_of(score, rg.ZONES)[0],
                )

        # 자비스3은 점수를 안에서 만들므로 양끝만 확인한다.
        def _rows(above: bool):
            price = 110.0 if above else 90.0
            row = {"current": price, "sma20": 100.0, "sma50": 100.0}
            return {"SPY": dict(row), "QQQ": dict(row), "IWM": dict(row),
                    "^VIX": {"ok": True, "current": 15.0 if above else 40.0}}

        best = jarvis3_data._market_regime_from_rows(_rows(True))
        worst = jarvis3_data._market_regime_from_rows(_rows(False))
        self.assertEqual(best["regime"], gauge_ui.zone_of(best["score"], rg.ZONES)[0])
        self.assertEqual(worst["regime"], gauge_ui.zone_of(worst["score"], rg.ZONES)[0])

    def test_color_of_matches_the_zone(self):
        self.assertEqual(rg.color_of(20), "#ff5b5b")
        self.assertEqual(rg.color_of(40), "#ff9d3b")
        self.assertEqual(rg.color_of(62), "#ffd23f")
        self.assertEqual(rg.color_of(70), "#2ee6c5")
        self.assertEqual(rg.color_of(85), "#44f0a1")
        self.assertEqual(rg.color_of(None), "#e6e6e6")


class RegimeBoxTests(unittest.TestCase):
    def _overview(self, score=20, regime="하락 압력 큼"):
        return {"ok": True, "score": score, "regime": regime, "posture": "신규 매수 보류"}

    def test_box_shows_score_regime_and_all_five_ranges(self):
        html = rg.regime_box_html(self._overview())
        self.assertIn(">20<", html)
        self.assertIn("하락 압력 큼", html)
        for text in ("0~29", "30~49", "50~64", "65~79", "80~100"):
            self.assertIn(text, html)
        self.assertIn("신규 매수 보류", html)

    def test_current_zone_is_marked_and_others_dimmed(self):
        html = rg.regime_box_html(self._overview(score=62, regime="방향 엇갈림"))
        rows = ["<div class='fg-hist-row" + part
                for part in html.split("<div class='fg-hist-row")[1:]]
        self.assertEqual(len(rows), 5)
        current = [row for row in rows if "지금" in row]
        self.assertEqual(len(current), 1)
        self.assertIn("50~64", current[0])
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

    def test_titles_and_previous_label_use_sky_blue(self):
        """시장 국면·미국 시장·전일 비교 제목은 스카이블루로 통일한다."""
        current = rg.regime_box_html({
            **self._overview(),
            "previous_market": {
                "ok": True, "score": 25, "regime": "하락 압력 큼",
            },
        })
        self.assertIn(gauge_ui.TITLE_BLUE, current)
        self.assertIn(
            f"class='fg-hist-label' style='color:{gauge_ui.TITLE_BLUE}'",
            current,
        )
        self.assertIn(gauge_ui.TITLE_BLUE, rg.us_prev_box_html({
            "ok": True, "score": 65, "regime": "상승 신호 우세",
            "spy_change": 0.1, "qqq_change": 0.2,
        }))

    def test_us_country_suffix_only_uses_bright_green(self):
        html = rg.regime_box_html(self._overview(), title="시장 국면 (미국)")
        self.assertIn(
            f"시장 국면 <span style='color:{gauge_ui.TITLE_GREEN}'>(미국)</span>",
            html,
        )

    def test_previous_regime_falls_back_from_score_when_label_is_missing(self):
        """전일 국면명이 빠져도 점수 구간에서 복원해 카드가 깨지지 않는다."""
        html = rg.regime_box_html({
            **self._overview(),
            "previous_market": {"ok": True, "score": 25},
        })
        self.assertIn("전일 시장국면", html)
        self.assertIn("하락 압력 큼", html)
        self.assertIn("25점", html)


class UsPrevBoxTests(unittest.TestCase):
    def _us(self, **extra):
        base = {"ok": True, "score": 65, "regime": "상승 신호 우세",
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

    def test_box_also_shows_all_five_score_ranges(self):
        """이 점수는 자비스3 '시장 국면'과 같은 계산이므로 구간도 같이 보여준다."""
        html = rg.us_prev_box_html(self._us())
        for text in ("하락 압력 큼", "0~29", "약세 신호 우세", "30~49", "방향 엇갈림",
                     "50~64", "상승 신호 우세", "65~79", "상승 여건 양호", "80~100"):
            self.assertIn(text, html)
        rows = ["<div class='fg-hist-row" + part
                for part in html.split("<div class='fg-hist-row")[1:]]
        self.assertEqual(len(rows), 7, "구간 5줄 + 지수 2줄")
        current = [row for row in rows if "지금" in row]
        self.assertEqual(len(current), 1)
        self.assertIn("65~79", current[0], "65점은 상승 신호 우세 구간이다")

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

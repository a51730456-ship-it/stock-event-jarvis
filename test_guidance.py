"""'지금 할 일' 지침 (2026-07-30 사용자 지적: 뭘 하라는 건지 표시가 없다).

지침은 판정을 사람 말로 다시 쓴 것이다. **판정과 어긋나면 안 된다** — 그 규칙을
여기서 붙잡는다. 화면에 새 판정이 생기는 순간 이 테스트가 깨져야 한다.
"""

import unittest

import guidance


def _won(value):
    return f"{float(value):,.0f}원"


class BuildTests(unittest.TestCase):
    def test_conditional_candidate_tells_the_four_prices(self):
        plan = {
            "state": "돌파 확인", "recommendation": "조건부 후보",
            "trigger": 857000, "zone_high": 865000,
            "invalidation": 618000, "target": 1335000,
            "buy_reason": "52주 신고가 부근에서 거래량이 증가해 종가 돌파 확인 후 진입합니다.",
        }
        guide = guidance.build(plan, money=_won, market_score=72)
        self.assertEqual(guidance.GO, guide["level"])
        self.assertIn("진입 자리", guide["headline"])
        self.assertIn("돌파 확인", guide["headline"])
        for value in ("857,000원", "865,000원", "618,000원", "1,335,000원"):
            self.assertIn(value, guide["detail"], f"{value}가 지침에 없다")

    def test_chase_block_is_a_stop(self):
        guide = guidance.build(
            {"state": "추격 금지", "recommendation": "추천 제외",
             "buy_reason": "단기 급등 또는 변동성 과열로 추격 매수를 금지합니다."},
            money=_won, market_score=80,
        )
        self.assertEqual(guidance.STOP, guide["level"])
        self.assertIn("손대지 않습니다", guide["headline"])

    def test_excluded_is_a_stop(self):
        guide = guidance.build({"state": "제외", "recommendation": "추천 제외"},
                               money=_won, market_score=80)
        self.assertEqual(guidance.STOP, guide["level"])

    def test_weak_market_says_do_not_buy_today_with_the_number(self):
        guide = guidance.build(
            {"state": "관찰", "recommendation": "관찰",
             "buy_reason": "시장 국면이 약세 구간이라 신규 매수를 보류합니다."},
            money=_won, market_score=15,
        )
        self.assertEqual(guidance.WAIT, guide["level"])
        self.assertIn("오늘은 새로 사지 않습니다", guide["headline"])
        self.assertIn("15점", guide["detail"])
        self.assertIn("50점", guide["detail"])

    def test_setup_ready_but_gates_fail_says_so(self):
        guide = guidance.build(
            {"state": "눌림목 대기", "recommendation": "관찰",
             "buy_reason": "테마 강도가 기준 미달이라 종목 점수가 높아도 매수하지 않습니다."},
            money=_won, market_score=70,
        )
        self.assertEqual(guidance.WAIT, guide["level"])
        self.assertIn("가격 자리는 맞지만", guide["headline"])
        self.assertIn("테마 강도", guide["detail"])

    def test_missing_data_is_never_presented_as_a_verdict(self):
        for plan in ({}, None, {"state": "자료 부족", "recommendation": "추천 불가"}):
            guide = guidance.build(plan, money=_won, market_score=None)
            self.assertEqual(guidance.WAIT, guide["level"])
            self.assertIn("자료가 모자랍니다", guide["headline"])

    def test_market_score_can_be_missing_without_crashing(self):
        guide = guidance.build({"state": "관찰", "recommendation": "관찰"},
                               money=_won, market_score=None)
        self.assertEqual(guidance.WAIT, guide["level"])
        guide = guidance.build({"state": "관찰", "recommendation": "관찰"},
                               money=_won, market_score="자료없음")
        self.assertEqual(guidance.WAIT, guide["level"])

    def test_gate_number_matches_the_engines(self):
        """지침이 말하는 50점 문턱은 실제 게이트와 같아야 한다."""
        import pathlib
        import re

        for name in ("jarvis3_data.py", "jarvis4_data.py"):
            source = re.sub(r"\s+", " ", pathlib.Path(name).read_text(encoding="utf-8"))
            self.assertIn("market_score >= 50", source, f"{name}의 시장 게이트가 바뀌었다")
        self.assertEqual(50.0, guidance.MARKET_GATE)


class RulebookGuideTests(unittest.TestCase):
    """설명서 두 갈래는 기준가도 손절도 시장 문턱도 없다 — 그대로 말해야 한다."""

    def _plan(self, **over):
        plan = {"state": "규칙에 맞는 자리", "recommendation": "조건부 후보",
                "rule_mode": "crash", "entry": "다음 거래일 시가", "hold_days": 20,
                "buy_reason": "낙폭 종목입니다"}
        plan.update(over)
        return plan

    def test_says_when_to_buy_and_sell_and_that_there_is_no_stop(self):
        guide = guidance.build(self._plan(), money=str)
        self.assertEqual(guidance.GO, guide["level"])
        self.assertIn("다음 거래일 시가", guide["detail"])
        self.assertIn("20거래일", guide["detail"])
        self.assertIn("손절가가 없습니다", guide["detail"])

    def test_market_gate_does_not_apply_to_the_rulebook(self):
        """이 규칙에는 시장 점수 문턱이 없다 — '오늘은 새로 사지 않습니다'가 붙으면 안 된다."""
        guide = guidance.build(self._plan(recommendation="관찰"), money=str, market_score=10)
        self.assertEqual(guidance.WAIT, guide["level"])
        self.assertNotIn("오늘은 새로 사지 않습니다", guide["headline"])
        self.assertIn("손절가가 없습니다", guide["detail"])

    def test_ordinary_plans_are_untouched(self):
        guide = guidance.build(
            {"state": "돌파 확인", "recommendation": "조건부 후보", "trigger": 100},
            money=str)
        self.assertEqual(guidance.GO, guide["level"])
        self.assertIn("100", guide["detail"])


class HtmlTests(unittest.TestCase):
    def test_html_uses_the_page_prefix_and_level_colour(self):
        guide = {"level": guidance.STOP, "headline": "손대지 않습니다", "detail": "이유"}
        markup = guidance.html(guide, css_class="j4-guide")
        self.assertIn("class='j4-guide'", markup)
        self.assertIn("j4-guide-tag", markup)
        self.assertIn("j4-guide-head", markup)
        self.assertIn("지금 할 일", markup)
        self.assertIn(guidance.LEVEL_STYLE[guidance.STOP][0], markup)

    def test_both_pages_carry_the_guide_styles(self):
        import pathlib

        for path, prefix in (("pages/2_자비스3.py", "j3"), ("pages/3_자비스4.py", "j4")):
            source = pathlib.Path(path).read_text(encoding="utf-8")
            self.assertIn(f".{prefix}-guide {{", source, f"{path}에 지침 상자 CSS가 없다")
            self.assertIn(f"css_class=\"{prefix}-guide\"", source, f"{path}가 지침을 안 그린다")


if __name__ == "__main__":
    unittest.main()

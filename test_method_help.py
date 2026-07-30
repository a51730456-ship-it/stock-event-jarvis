"""'이 테마 기법에 대한 설명' 단추와 문구 계약 테스트.

2026-07-30 사용자 지시로 내용을 두 쪽 분량으로 줄였다. 자세한 근거는
docs/METHOD_ORIGINS.md에 있고, 화면에는 핵심만 남긴다.
숫자는 2026-07-29에 실제로 잰 값이다(코스피 5,253일 · S&P500 5,357일).
문구를 고칠 때 숫자를 함께 바꾸지 않으면 화면이 거짓말을 하게 되므로 묶어 둔다.
"""

import pathlib
import re
import unittest

import guidance
import method_help
import mobile_ui


class ButtonTests(unittest.TestCase):
    def test_label_is_what_the_user_asked_for(self):
        self.assertIn("이 테마 기법에 대한 설명", method_help.BUTTON_LABEL)

    def test_button_hugs_its_text_and_sits_on_the_right(self):
        css = method_help.BUTTON_CSS
        self.assertIn("width: auto !important", css)
        # 오른쪽으로 미는 것은 margin-left:auto다 — 스트림릿이 align-items를
        # start로 못박아 둬서 정렬 속성으로는 안 밀린다(2026-07-29 실측).
        self.assertIn("margin-left: auto !important", css)
        self.assertIn("#cfe9ff", css)
        self.assertIn("#c15f3c", css)

    def test_phone_rules_live_in_mobile_ui_only(self):
        """CLAUDE.md 12번 — 폰 규칙은 mobile_ui.py 폰 묶음 안에만 둔다."""
        self.assertNotIn("max-width: 600px", method_help.BUTTON_CSS)

    def test_button_drops_two_lines_on_phone_and_tablet(self):
        """2026-07-30 사용자 지시 — 스마트폰과 태블릿에서 두 줄 밑으로.

        폰 묶음(600px)이 아니라 태블릿까지 걸리는 묶음(1200px)에 있어야 한다.
        """
        self.assertIn("st-key-jarvis_method_help", mobile_ui.TOP_ROW_CSS)
        self.assertIn("margin-top: 3.2rem !important", mobile_ui.TOP_ROW_CSS)
        self.assertEqual(1200, mobile_ui.SIDEBAR_MAX_WIDTH)


class PanelTests(unittest.TestCase):
    def test_panel_does_not_follow_the_page(self):
        """2026-07-30 사용자 지적 — 굴릴 때 따라와 본문을 가려 불편하다.

        붙박이(position:fixed)로 되돌아가면 이 테스트가 깨진다.
        """
        css = method_help.BUTTON_CSS
        body = css.split('[data-testid="stPopoverBody"] {')[1].split("}")[0]
        self.assertNotIn("position: fixed", body)
        self.assertNotIn("transform: none", body)
        # 높이만 화면 절반으로 묶어 둔다 — 나머지 절반으로 표를 봐야 한다.
        self.assertIn("max-height: 50vh !important", body)
        self.assertIn("overflow-y: auto !important", body)

    def test_colors_are_split_three_ways(self):
        css = method_help.BUTTON_CSS
        for name in ("--j-title", "--j-step", "--j-mark"):
            self.assertIn(name, css)
        self.assertIn('[data-testid="stPopoverBody"] h3 { color: var(--j-title)', css)
        # 붉은색은 문단·인용문의 굵은 글씨에만. 표·목록까지 붉히면 온통 붉어진다.
        self.assertIn('[data-testid="stPopoverBody"] p > strong,', css)
        self.assertIn("td strong,", css)
        self.assertIn("li strong { color: inherit !important; }", css)
        # 앱에 테마 파일이 없어 보는 사람의 밝기 설정을 따라간다 — 두 벌 다 있어야 한다.
        self.assertIn("prefers-color-scheme: dark", css)

    def test_there_is_a_way_to_close_it(self):
        import inspect

        self.assertIn("다시 누르", method_help.CLOSE_HINT)
        self.assertIn("CLOSE_HINT", inspect.getsource(method_help.render))

    def test_bold_runs_are_not_broken_by_korean_particles(self):
        """닫는 ** 앞이 %·)·' 이고 뒤에 한글이 붙으면 별표가 그대로 찍힌다."""
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            broken = re.findall(r"\*\*[^*\n]*[%)'\]）]\*\*[가-힣]", text)
            self.assertEqual([], broken, f"굵은 글씨가 깨진다: {broken}")


class LengthTests(unittest.TestCase):
    """2026-07-30 사용자 지시 — 핵심만 두 쪽. 길어지면 아무도 안 읽는다."""

    # 두 쪽 분량의 상한. 예전 글은 7,000자가 넘어 스무 번 굴려야 했다.
    MAX_CHARS = 2600

    def test_each_text_fits_two_pages(self):
        for market, text in (("US", method_help.US_TEXT), ("KR", method_help.KR_TEXT)):
            self.assertLess(
                len(text), self.MAX_CHARS,
                f"{market} 설명이 {len(text)}자다 — {self.MAX_CHARS}자 안으로 줄여라",
            )

    def test_the_long_version_still_exists_somewhere(self):
        """화면에서 뺀 자세한 근거는 문서에 남아 있어야 한다."""
        doc = pathlib.Path("docs/METHOD_ORIGINS.md")
        self.assertTrue(doc.exists())
        self.assertIn("docs/METHOD_ORIGINS.md", method_help.US_TEXT)


class TextTests(unittest.TestCase):
    def test_both_markets_have_their_own_text(self):
        self.assertNotEqual(method_help.US_TEXT, method_help.KR_TEXT)
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            self.assertIn("지금 사면 얼마나 위험한가", text)

    def test_measured_numbers_are_present(self):
        """실제로 잰 숫자다. 문구만 고치고 숫자를 빼면 근거 없는 주장이 된다."""
        us = method_help.US_TEXT
        for token in ("3.5% → 1.1%", "+0.65%", "+1.12%"):
            self.assertIn(token, us, f"미국 문구에 {token}가 없다")
        kr = method_help.KR_TEXT
        for token in ("2.9% vs 3.6%", "1.1% vs 3.5%"):
            self.assertIn(token, kr, f"한국 문구에 {token}가 없다")

    def test_gate_numbers_match_the_engines(self):
        """문턱 숫자는 실제 게이트와 같아야 한다."""
        us_engine = re.sub(r"\s+", " ", pathlib.Path("jarvis3_data.py").read_text(encoding="utf-8"))
        self.assertIn("market_score >= 50 and theme_score >= 70 and score >= 75", us_engine)
        for token in ("**50점**↑", "**70점**↑", "**75점**↑"):
            self.assertIn(token, method_help.US_TEXT)

        kr_engine = re.sub(r"\s+", " ", pathlib.Path("jarvis4_data.py").read_text(encoding="utf-8"))
        self.assertIn("theme_score >= 60 or score >= STRONG_STOCK_OVERRIDE", kr_engine)
        self.assertIn("market_score >= 50 and theme_ok and score >= 70", kr_engine)
        for token in ("**50점**↑", "**60점**↑", "**70점**↑", "85점"):
            self.assertIn(token, method_help.KR_TEXT)

    def test_it_says_what_the_score_is_not(self):
        """'점수=수익 예측'으로 읽히지 않게 하는 문장이 반드시 있어야 한다."""
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            self.assertIn("틀린 말", text)
            self.assertIn("지어내지 않습니다", text)

    def test_korea_says_it_fits_worse_and_what_was_added(self):
        kr = method_help.KR_TEXT
        self.assertIn("미국만큼 듣지 않았습니다", kr)
        self.assertIn("보강했습니다", kr)
        self.assertIn("수급", kr)
        self.assertIn("참고로만", kr)
        # 미국 문구에는 이 이야기가 없어야 한다(두 화면이 같은 말을 하면 안 된다).
        self.assertNotIn("보강했습니다", method_help.US_TEXT)

    def test_explanation_and_screen_agree_on_the_guidance(self):
        """설명이 소개하는 '지금 할 일' 문구는 guidance.py가 내보내는 것과 같아야 한다."""
        cases = [
            {"state": "돌파 확인", "recommendation": "조건부 후보", "trigger": 1.0},
            {"state": "추격 금지", "recommendation": "추천 제외"},
            {"state": "제외", "recommendation": "추천 제외"},
            {"state": "관찰", "recommendation": "관찰"},
            {"state": "눌림목 대기", "recommendation": "관찰"},
        ]
        for plan in cases:
            score = 15 if plan.get("state") == "관찰" else 70
            headline = guidance.build(plan, money=str, market_score=score)["headline"]
            stem = headline.split(" (")[0]
            for text in (method_help.US_TEXT, method_help.KR_TEXT):
                self.assertIn(stem, text, f"화면에는 '{headline}'이 뜨는데 설명에 없다")

    def test_it_names_where_the_method_came_from(self):
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            self.assertIn("한 편의 논문에서 나온 기법이 아닙니다", text)
            for name in ("Moskowitz & Grinblatt 1999", "George & Hwang 2004", "Weinstein"):
                self.assertIn(name, text, f"{name}가 빠졌다")

    def test_it_admits_there_is_no_sell_signal(self):
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            self.assertIn("파는 때는 아직 이 화면에 없습니다", text)
            self.assertIn("남의 자료로 잰 값", text)

    def test_screen_labels_match_the_pages(self):
        """설명이 인용한 칸 이름이 페이지 코드에 그대로 있어야 한다."""
        for market, path in (("US", "pages/2_자비스3.py"), ("KR", "pages/3_자비스4.py")):
            source = pathlib.Path(path).read_text(encoding="utf-8")
            for label in ("매수 심사 결과", "실제 매수 기록"):
                self.assertIn(label, source, f"{market} 페이지에 '{label}'이 없다")
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            self.assertNotIn("매수 타이밍", text)
            self.assertIn("매수 심사 결과", text)


if __name__ == "__main__":
    unittest.main()

"""'이 테마 기법에 대한 설명' 단추와 문구 계약 테스트.

여기 적힌 숫자는 2026-07-29에 실제로 잰 값이다(코스피 5,253일 · S&P500 5,357일).
문구를 고칠 때 숫자를 함께 바꾸지 않으면 화면이 거짓말을 하게 되므로 묶어 둔다.
"""

import unittest

import method_help
import mobile_ui


class ButtonTests(unittest.TestCase):
    def test_label_is_what_the_user_asked_for(self):
        self.assertIn("이 테마 기법에 대한 설명", method_help.BUTTON_LABEL)

    def test_button_hugs_its_text_and_sits_on_the_right(self):
        css = method_help.BUTTON_CSS
        # 좌우로 늘리지 않는다.
        self.assertIn("width: auto !important", css)
        # 오른쪽으로 미는 것은 margin-left:auto다 — 스트림릿이 align-items를
        # start로 못박아 둬서 정렬 속성으로는 안 밀린다(2026-07-29 실측).
        self.assertIn("margin-left: auto !important", css)
        # 눌림목 단추와 같은 옷.
        self.assertIn("#cfe9ff", css)
        self.assertIn("#c15f3c", css)

    def test_phone_rules_live_in_mobile_ui_only(self):
        """CLAUDE.md 12번 — 폰 규칙은 mobile_ui.py 폰 묶음 안에만 둔다."""
        self.assertNotIn("max-width: 600px", method_help.BUTTON_CSS)
        self.assertIn("st-key-jarvis_method_help", mobile_ui.CONTENT_CSS)


class TextTests(unittest.TestCase):
    def test_both_markets_have_their_own_text(self):
        self.assertNotEqual(method_help.US_TEXT, method_help.KR_TEXT)
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            self.assertIn("지금 사면 얼마나 위험한가", text)

    def test_measured_numbers_are_present(self):
        """실제로 잰 숫자다. 문구만 고치고 숫자를 빼면 근거 없는 주장이 된다."""
        us = method_help.US_TEXT
        for token in ("+0.65%", "+1.12%", "−10.4%", "−19.4%", "3.5%"):
            self.assertIn(token, us, f"미국 문구에 {token}가 없다")
        kr = method_help.KR_TEXT
        for token in ("+1.01%", "+0.83%", "−15.2%", "−15.5%"):
            self.assertIn(token, kr, f"한국 문구에 {token}가 없다")

    def test_it_says_what_the_score_is_not(self):
        """'점수=수익 예측'으로 읽히지 않게 하는 문장이 반드시 있어야 한다."""
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            self.assertIn("틀린 말", text)
            self.assertIn("지어내지 않습니다", text)

    def test_korea_tells_the_user_to_lean_on_flow(self):
        """한국은 방어 효과가 약하니 수급을 더 보라고 안내해야 한다."""
        self.assertIn("수급", method_help.KR_TEXT)
        self.assertIn("참고", method_help.KR_TEXT)


if __name__ == "__main__":
    unittest.main()

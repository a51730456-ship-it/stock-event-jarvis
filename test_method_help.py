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

    def test_each_text_walks_the_user_through_the_screen(self):
        """초보자가 '뭘 어떻게 하라는 건지' 알 수 있게 보는 순서가 있어야 한다.

        2026-07-29 사용자 지적 — 숫자만 있고 사용법이 없으면 이해가 안 된다.
        """
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            self.assertIn("이 순서로 보십시오", text)
            for step in ("①", "②", "③", "④", "⑤"):
                self.assertIn(step, text, f"{step} 단계가 빠졌다")
            # 화면에서 실제로 눌러야 하는 자리와 거르는 자리를 짚어야 한다.
            self.assertIn("눌림목 대기", text)
            self.assertIn("추격 금지", text)

    def test_only_labels_that_really_appear_on_screen(self):
        """설명이 가리키는 이름은 화면에 실제로 있는 이름이어야 한다.

        2026-07-29 사용자 지적 — '매수 타이밍'이라고 써 뒀는데 미국 화면에
        그런 이름이 없었다. 그건 아래 '판정 기준과 데이터 정책' 탭의 항목명이고,
        종목 화면에 뜨는 것은 '매수 심사 결과' 칸과 그 안의 상태 글자다.
        """
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            self.assertNotIn("매수 타이밍", text)
            self.assertIn("매수 심사 결과", text)
            self.assertIn("종목 조건점수", text)
            # jarvis3_data/jarvis4_data가 실제로 내보내는 상태 글자들.
            for state in ("돌파 확인", "눌림목 대기", "관찰", "제외", "추격 금지"):
                self.assertIn(state, text, f"화면 상태 '{state}'가 설명에 없다")
            self.assertIn("조건부 후보", text)

    def test_gate_numbers_match_the_engines(self):
        """문턱 숫자는 jarvis3_data/jarvis4_data의 실제 게이트와 같아야 한다.

        2026-07-29 사용자 요구 — '몇 점 이상 보라, 이유는 뭐다'까지 적을 것.
        엔진에서 문턱을 고치면 이 테스트가 먼저 깨져 설명도 같이 고치게 만든다.
        """
        import pathlib
        import re

        import jarvis4_data

        us_engine = pathlib.Path("jarvis3_data.py").read_text(encoding="utf-8")
        self.assertIn(
            "market_score >= 50 and theme_score >= 70 and score >= 75",
            re.sub(r"\s+", " ", us_engine),
            "미국 게이트가 바뀌었다 — US_TEXT의 문턱 숫자도 고쳐라",
        )
        for token in ("시장 점수 **50점 이상**", "70점 이상", "75점 이상"):
            self.assertIn(token, method_help.US_TEXT)

        kr_engine = re.sub(r"\s+", " ", pathlib.Path("jarvis4_data.py").read_text(encoding="utf-8"))
        self.assertIn("theme_score >= 60 or score >= STRONG_STOCK_OVERRIDE", kr_engine)
        self.assertIn("market_score >= 50 and theme_ok and score >= 70", kr_engine)
        self.assertEqual(85.0, jarvis4_data.STRONG_STOCK_OVERRIDE)
        for token in ("시장 점수 **50점 이상**", "60점 이상", "70점 이상", "85점"):
            self.assertIn(token, method_help.KR_TEXT)

    def test_setup_numbers_match_the_engines(self):
        """상태 판정 숫자(돌파·눌림·추격금지)도 엔진과 같아야 한다."""
        import pathlib
        import re

        us = re.sub(r"\s+", " ", pathlib.Path("jarvis3_data.py").read_text(encoding="utf-8"))
        self.assertIn("from_high >= -2.0", us)
        self.assertIn("ret5 >= 15", us)
        for token in ("−2% 안", "1.3배", "±3.5% 안", "+15% 이상"):
            self.assertIn(token, method_help.US_TEXT, f"미국 문구에 {token}가 없다")

        kr = re.sub(r"\s+", " ", pathlib.Path("jarvis4_data.py").read_text(encoding="utf-8"))
        self.assertIn("from_high >= -3.0", kr)
        self.assertIn("ret5 >= 25", kr)
        self.assertIn("change_pct >= 20", kr)
        for token in ("−3% 안", "1.3배", "±7% 안", "+20% 이상", "+25% 이상"):
            self.assertIn(token, method_help.KR_TEXT, f"한국 문구에 {token}가 없다")

    def test_it_admits_the_thresholds_are_unverified(self):
        """문턱은 아직 실매매로 검증된 값이 아니다 — 그 사실을 감추지 않는다."""
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            self.assertIn("아직 검증된 값이 아닙니다", text)
            self.assertIn("30건", text)

    def test_it_explains_every_price_box(self):
        """'매수 심사 결과' 네 칸이 각각 무슨 뜻인지 다 적어야 한다."""
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            for box in ("조건 기준가", "매수 허용 상단", "무효화 가격", "2R 목표 참고"):
                self.assertIn(box, text, f"'{box}' 칸 설명이 없다")

    def test_screen_labels_match_the_pages(self):
        """설명이 인용한 칸 이름이 페이지 코드에 그대로 있어야 한다."""
        import pathlib

        pages = {
            "US": pathlib.Path("pages/2_자비스3.py"),
            "KR": pathlib.Path("pages/3_자비스4.py"),
        }
        for market, path in pages.items():
            source = path.read_text(encoding="utf-8")
            for label in ("매수 심사 결과", "종목 조건점수"):
                self.assertIn(label, source, f"{market} 페이지에 '{label}'이 없다")

    def test_hard_words_are_explained_where_they_first_appear(self):
        """설명해야 아는 말은 화면에 그냥 두지 않는다(쉬운 말 규칙)."""
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            self.assertIn("50일선**(최근 50거래일 평균 가격선)", text)
        self.assertIn("외국인과 기관이 이 종목을 사고 있나", method_help.KR_TEXT)

    def test_the_two_markets_give_different_instructions(self):
        """미국은 시장 점수를 믿으라 하고, 한국은 수급을 보라 한다."""
        self.assertIn("이 안전장치가 잘 듣습니다", method_help.US_TEXT)
        self.assertIn("미국만큼 잘 듣지 않습니다", method_help.KR_TEXT)
        self.assertNotIn("미국만큼 잘 듣지 않습니다", method_help.US_TEXT)


if __name__ == "__main__":
    unittest.main()

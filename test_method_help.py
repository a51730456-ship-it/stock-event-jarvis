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

    def test_top_gap_is_only_as_tall_as_the_toolbar(self):
        """2026-07-30 사용자 지적 — 위 여백이 너무 많다, 전체를 위로 올려라.

        실측(폰 412px · PC 1280px) — 스트림릿 기본 여백 96px, 도구막대 60px.
        64px로 줄이면 본문이 도구막대 바로 밑에서 시작하고(단추 top 179→98,
        제목 238→156), 도구막대는 그대로 눌러 화면을 어둡게 바꿀 수 있다.
        더 줄이면 단추가 도구막대를 덮어 ⋮ 메뉴를 못 누른다.
        """
        css = method_help.BUTTON_CSS
        self.assertIn('[data-testid="stMainBlockContainer"],', css)
        self.assertIn("padding-top: 4rem !important", css)
        # 폰 전용이 아니라 모든 화면에 걸리는 규칙이다 — 폰 묶음에 있으면 안 된다.
        self.assertNotIn("st-key-jarvis_method_help", mobile_ui.TOP_ROW_CSS)


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


def _visible(text: str) -> str:
    """화면에 실제로 보이는 글자만 남긴다 — 미국 설명서는 HTML이라 태그가 섞여 있다."""
    return re.sub(r"<[^>]+>", "", text)


class LengthTests(unittest.TestCase):
    """2026-07-30 사용자 지시 — 핵심만 두 쪽. 길어지면 아무도 안 읽는다."""

    # 두 쪽 분량의 상한. 예전 글은 7,000자가 넘어 스무 번 굴려야 했다.
    MAX_CHARS = 2600

    def test_each_text_fits_two_pages(self):
        for market, text in (("US", method_help.US_TEXT), ("KR", method_help.KR_TEXT)):
            body = _visible(text)
            self.assertLess(
                len(body), self.MAX_CHARS,
                f"{market} 설명이 {len(body)}자다 — {self.MAX_CHARS}자 안으로 줄여라",
            )

    def test_the_long_version_still_exists_somewhere(self):
        """화면에서 뺀 자세한 근거는 문서에 남아 있어야 한다.

        2026-08-01에 미국 설명서를 '눌림목 매매 설명서'로 통째로 바꾸면서 미국
        문구에서는 이 안내가 빠졌다(사용자 지시: 기존 내용 지우고). 한국 문구는
        아직 예전 글이라 그대로 있어야 한다.
        """
        doc = pathlib.Path("docs/METHOD_ORIGINS.md")
        self.assertTrue(doc.exists())
        self.assertIn("docs/METHOD_ORIGINS.md", method_help.KR_TEXT)


class UsGuideTests(unittest.TestCase):
    """2026-08-01 사용자가 준 '미국장 눌림목 매매 설명서'를 그대로 지킨다.

    숫자는 사용자가 준 검증값이다. 문구를 손보다 숫자가 슬쩍 바뀌면 화면이
    거짓말을 하게 되므로 여기서 묶어 둔다.
    """

    def test_it_is_the_pullback_guide(self):
        us = method_help.US_TEXT
        self.assertIn("미국장 눌림목 매매 설명서", us)
        self.assertIn("정상 상승장", us)
        self.assertIn("급락 후 반등장", us)
        # 예전 조건점수·논문 이야기는 이 화면에서 뺐다.
        self.assertNotIn("한 편의 논문에서 나온 기법이 아닙니다", us)

    def test_verification_note_names_who_checked_it(self):
        us = method_help.US_TEXT
        for token in ("GPT-5.6 SOL", "Claude 5.8 Opus", "200개",
                      "학습 234건", "별도 검증 119건", "재검증 5,000회", "2025년 4월"):
            self.assertIn(token, us, f"검증 안내에 {token}가 없다")

    def test_normal_uptrend_numbers(self):
        us = method_help.US_TEXT
        for token in ("52주", "3~5거래일", "4~6%", "120거래일",
                      "59.7% (119건)", "+18.0%", "+8.9%",
                      "48건 (40.3%)", "-11.9%", "-10.4%", "-40.7%"):
            self.assertIn(token, us, f"정상 상승장 숫자에 {token}가 없다")

    def test_crash_rebound_numbers(self):
        us = method_help.US_TEXT
        for token in ("-40~-50%", "20거래일", "100.0% (12건)", "+11.2%", "+10.5%",
                      "-30~-40%", "60거래일", "92.6% (27건)", "+24.9%", "+29.6%"):
            self.assertIn(token, us, f"급락 반등장 숫자에 {token}가 없다")

    def test_the_warnings_survive(self):
        """높은 승률 옆의 경고가 사라지면 설명이 광고가 된다."""
        us = method_help.US_TEXT
        self.assertIn("당일에는 매수하지 않습니다", us)
        self.assertIn("추격 매수하지 않습니다", us)
        self.assertIn("손절", us)
        self.assertIn("미래 승률이 아닙니다", us)

    def test_it_is_html_and_the_renderer_allows_html(self):
        """색·기호·밑줄을 직접 입힌 HTML이라 unsafe_allow_html이 꺼지면 태그가 글자로 찍힌다."""
        import inspect

        self.assertIn('class="mh-doc"', method_help.US_TEXT)
        self.assertIn("unsafe_allow_html=True", inspect.getsource(method_help.render))
        for name in ("mh-h1", "mh-h2", "mh-buy-box", "mh-sell-box",
                     "mh-data-box", "mh-warn-box", "mh-key"):
            self.assertIn(name, method_help.BUTTON_CSS, f"{name} 옷이 없다")

    def test_html_has_no_blank_lines(self):
        """빈 줄이 있으면 스트림릿이 그 사이를 문단으로 갈라 <p>를 끼워 넣는다."""
        body = method_help.US_TEXT.strip("\n")
        self.assertNotIn("\n\n", body)


class TextTests(unittest.TestCase):
    def test_both_markets_have_their_own_text(self):
        self.assertNotEqual(method_help.US_TEXT, method_help.KR_TEXT)
        # 2026-08-01부터 미국은 눌림목 설명서, 한국은 예전 조건점수 설명이다.
        self.assertIn("지금 사면 얼마나 위험한가", method_help.KR_TEXT)

    def test_measured_numbers_are_present(self):
        """실제로 잰 숫자다. 문구만 고치고 숫자를 빼면 근거 없는 주장이 된다."""
        kr = method_help.KR_TEXT
        for token in ("2.9% vs 3.6%", "1.1% vs 3.5%"):
            self.assertIn(token, kr, f"한국 문구에 {token}가 없다")

    def test_gate_numbers_match_the_engines(self):
        """문턱 숫자는 실제 게이트와 같아야 한다.

        미국 문구는 2026-08-01에 눌림목 설명서로 바뀌어 문턱 이야기를 하지 않는다.
        미국 게이트 자체는 jarvis3_data가 지키고, 여기서는 한국만 본다.
        """
        kr_engine = re.sub(r"\s+", " ", pathlib.Path("jarvis4_data.py").read_text(encoding="utf-8"))
        self.assertIn("theme_score >= 60 or score >= STRONG_STOCK_OVERRIDE", kr_engine)
        self.assertIn("market_score >= 50 and theme_ok and score >= 70", kr_engine)
        for token in ("**50점**↑", "**60점**↑", "**70점**↑", "85점"):
            self.assertIn(token, method_help.KR_TEXT)

    def test_it_says_what_the_score_is_not(self):
        """'점수=수익 예측'으로 읽히지 않게 하는 문장이 반드시 있어야 한다.

        미국 문구는 조건점수 이야기를 더 이상 하지 않으므로 한국만 본다(2026-08-01).
        """
        self.assertIn("틀린 말", method_help.KR_TEXT)
        self.assertIn("지어내지 않습니다", method_help.KR_TEXT)

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
            # 미국 문구는 눌림목 설명서로 바뀌어 '지금 할 일' 표가 없다(2026-08-01).
            self.assertIn(stem, method_help.KR_TEXT,
                          f"화면에는 '{headline}'이 뜨는데 설명에 없다")

    def test_it_names_where_the_method_came_from(self):
        kr = method_help.KR_TEXT
        self.assertIn("한 편의 논문에서 나온 기법이 아닙니다", kr)
        for name in ("Moskowitz & Grinblatt 1999", "George & Hwang 2004", "Weinstein"):
            self.assertIn(name, kr, f"{name}가 빠졌다")

    def test_it_admits_there_is_no_sell_signal(self):
        """한국 문구는 아직 파는 때가 없다고 밝혀야 한다.

        미국 문구에는 2026-08-01부터 매도 규칙(120거래일·20거래일·60거래일 보유)이
        들어갔으므로 이 문장이 있으면 도리어 거짓말이 된다.
        """
        self.assertIn("파는 때는 아직 이 화면에 없습니다", method_help.KR_TEXT)
        self.assertIn("남의 자료로 잰 값", method_help.KR_TEXT)
        self.assertNotIn("파는 때는 아직 이 화면에 없습니다", method_help.US_TEXT)

    def test_screen_labels_match_the_pages(self):
        """설명이 인용한 칸 이름이 페이지 코드에 그대로 있어야 한다."""
        for market, path in (("US", "pages/2_자비스3.py"), ("KR", "pages/3_자비스4.py")):
            source = pathlib.Path(path).read_text(encoding="utf-8")
            for label in ("매수 심사 결과", "실제 매수 기록"):
                self.assertIn(label, source, f"{market} 페이지에 '{label}'이 없다")
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            self.assertNotIn("매수 타이밍", text)
        self.assertIn("매수 심사 결과", method_help.KR_TEXT)


if __name__ == "__main__":
    unittest.main()

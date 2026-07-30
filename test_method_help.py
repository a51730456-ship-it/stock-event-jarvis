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


class PanelTests(unittest.TestCase):
    """2026-07-30 사용자 지시 — 색 구분, 그리고 굴려도 따라오는 절반 크기 창."""

    def test_colors_are_split_three_ways(self):
        css = method_help.BUTTON_CSS
        # 큰 제목 초록 · 번호 항목 파랑 · 강조 붉은색.
        self.assertIn("--j-title", css)
        self.assertIn("--j-step", css)
        self.assertIn("--j-mark", css)
        self.assertIn('[data-testid="stPopoverBody"] h3 { color: var(--j-title)', css)
        self.assertIn('[data-testid="stPopoverBody"] h5 { color: var(--j-step)', css)
        # 붉은색은 문단·인용문의 굵은 글씨에만. 표·목록까지 붉히면 온통 붉어진다
        # (2026-07-30 사용자 지적).
        self.assertIn('[data-testid="stPopoverBody"] p > strong,', css)
        self.assertIn("blockquote strong { color: var(--j-mark)", css)
        self.assertIn("td strong,", css)
        self.assertIn("li strong { color: inherit !important; }", css)
        # 앱에 테마 파일이 없어 보는 사람의 밝기 설정을 따라간다 — 두 벌 다 있어야 한다.
        self.assertIn("prefers-color-scheme: dark", css)

    def test_panel_is_pinned_top_right_and_half_height(self):
        css = method_help.BUTTON_CSS
        # floating-ui의 inline transform을 지우지 않으면 단추를 따라 흘러간다.
        self.assertIn("transform: none !important", css)
        self.assertIn("position: fixed !important", css)
        self.assertIn("height: 50vh !important", css)
        self.assertIn("overflow-y: auto !important", css)
        # 아래가 아니라 오른쪽 '맨 위'다(2026-07-30 사용자 지시).
        self.assertIn("top: 4.2rem !important", css)
        self.assertIn("bottom: auto !important", css)

    def test_there_is_always_a_way_to_close_it(self):
        """본문을 내리면 여는 단추가 사라져 닫을 수 없었다(2026-07-30 사용자 지적).

        여는 단추를 sticky로 붙이는 방법은 안 먹었다(실측). 그래서 창 안에
        닫기 단추를 둔다 — 이게 유일한 닫는 길이므로 사라지면 안 된다.
        """
        import inspect

        # 여는 단추가 곧 닫는 단추다 — 화면에 못박혀 있어야 한다.
        self.assertIn(".st-key-jarvis_method_help {", method_help.BUTTON_CSS)
        self.assertIn("position: fixed !important", method_help.BUTTON_CSS)
        # 어떻게 닫는지 창 안에 적어 준다.
        self.assertIn("다시 누르", method_help.CLOSE_HINT)
        source = inspect.getsource(method_help.render)
        self.assertIn("CLOSE_HINT", source, "닫는 방법 안내가 창 안에 없다")

    def test_bold_runs_are_not_broken_by_korean_particles(self):
        """닫는 ** 앞이 %·)·' 이고 뒤에 한글이 붙으면 별표가 그대로 찍힌다.

        2026-07-30 실측 — '**−10%**면', '**분야(테마)**를'이 화면에 별표째 나왔다.
        조사를 굵은 글씨 안으로 넣어 피한다.
        """
        import re

        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            broken = re.findall(r"\*\*[^*\n]*[%)'\]）]\*\*[가-힣]", text)
            self.assertEqual([], broken, f"굵은 글씨가 깨진다: {broken}")

    def test_step_headings_are_h5_and_others_h3(self):
        """색이 h3/h5로 갈리므로 제목 단계가 흐트러지면 색이 엉킨다."""
        import re

        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            for line in text.split("\n"):
                if line.startswith("#####"):
                    self.assertRegex(
                        line, r"^##### [①②③④⑤⑥]", f"h5는 번호 항목만이어야 한다: {line}"
                    )
                elif line.startswith("#"):
                    self.assertTrue(
                        line.startswith("### ") and not line.startswith("#### "),
                        f"번호 항목 말고는 전부 h3여야 한다: {line}",
                    )
            # 단계 제목이 실제로 h5로 붙어 있어야 한다.
            self.assertTrue(re.search(r"^##### ①", text, re.M))


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

    def test_summary_comes_first(self):
        """2026-07-30 사용자 지시 — 핵심을 맨 앞에 짧게.

        무슨 기법인지 · 몇 년치 어떻게 검토했는지 · 언제 사고 · 어디에 적고 ·
        언제 파는지가 첫 화면에 다 있어야 한다.
        """
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            head = text.lstrip()
            self.assertTrue(
                head.startswith("### 한눈에 — 이게 무슨 기법인가"),
                "요약이 맨 앞에 없다",
            )
            summary = head.split("### 이 화면은 무엇을 하는 곳인가")[0]
            for key in ("무슨 기법", "어디서 왔나", "얼마나 검토", "언제 사나",
                        "어디에 적나", "언제 파나"):
                self.assertIn(key, summary, f"요약에 '{key}' 줄이 없다")
            # 파는 때가 없다는 사실은 요약에서부터 밝힌다.
            self.assertIn("아직 없습니다", summary)

    def test_korea_summary_says_it_fits_worse_and_what_was_added(self):
        """한국은 덜 맞는다는 것과, 그래서 무엇을 보강했는지가 요약에 있어야 한다."""
        summary = method_help.KR_TEXT.split("### 이 화면은 무엇을 하는 곳인가")[0]
        self.assertIn("미국만큼 듣지 않았습니다", summary)
        self.assertIn("2.9%", summary)
        self.assertIn("3.6%", summary)
        self.assertIn("보강했습니다", summary)
        self.assertIn("수급을 종목 점수 100점 중 20점", summary)
        # 미국 요약에는 이 이야기가 없어야 한다(두 화면이 같은 말을 하면 안 된다).
        us_summary = method_help.US_TEXT.split("### 이 화면은 무엇을 하는 곳인가")[0]
        self.assertNotIn("보강했습니다", us_summary)
        self.assertIn("이 안전장치가 잘 듣습니다", us_summary)

    def test_explanation_and_screen_agree_on_the_guidance(self):
        """2026-07-30 사용자 지적 — 지침이 명확하지 않다.

        설명이 소개하는 '지금 할 일' 문구는 guidance.py가 실제로 내보내는 문구와
        같아야 한다. 한쪽만 고치면 화면과 설명이 다른 말을 하게 된다.
        """
        import guidance

        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            self.assertIn("그래서 지금 뭘 하라는 건가", text)
            self.assertIn("지금 할 일", text)

        cases = [
            {"state": "돌파 확인", "recommendation": "조건부 후보", "trigger": 1.0},
            {"state": "추격 금지", "recommendation": "추천 제외"},
            {"state": "제외", "recommendation": "추천 제외"},
            {"state": "관찰", "recommendation": "관찰"},
            {"state": "눌림목 대기", "recommendation": "관찰"},
            {},
        ]
        for plan in cases:
            score = 15 if plan.get("state") == "관찰" else 70
            headline = guidance.build(plan, money=lambda v: f"{v}", market_score=score)["headline"]
            # 진입 자리 문구는 뒤에 상태 이름이 괄호로 붙는다("… (돌파 확인)").
            # 설명에는 상태별로 다 적을 수 없으니 괄호 앞부분만 맞춰 본다.
            stem = headline.split(" (")[0]
            for text in (method_help.US_TEXT, method_help.KR_TEXT):
                self.assertIn(
                    stem, text,
                    f"화면에는 '{headline}'이 뜨는데 설명에 그 말이 없다",
                )

    def test_it_names_where_the_method_came_from(self):
        """2026-07-30 사용자 지시 — 이 기법의 근원을 밝힐 것.

        조사 원본은 docs/METHOD_ORIGINS.md. 논문 이름을 빼면 근거 없는 계보가 된다.
        """
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            self.assertIn("이 방법은 어디서 왔나", text)
            for name in ("Moskowitz & Grinblatt (1999)", "George & Hwang (2004)", "Weinstein"):
                self.assertIn(name, text, f"{name}가 빠졌다")
            # 한 편의 논문에서 나온 것이 아니라는 사실을 분명히 한다.
            self.assertIn("한 편의 논문에서 나온 기법이 아닙니다", text)

    def test_it_admits_there_is_no_sell_signal(self):
        """매도 시점 — 지금 앱에 없다는 사실을 감추지 않는다."""
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            self.assertIn("언제 팔 것인가", text)
            self.assertIn("파는 때를 알려주지 않습니다", text)
            # Han·Zhou·Zhu의 −10% 손절 결과. 논문 값은 −49.79% → −11.36%이고
            # 화면에는 반올림해 적는다.
            self.assertIn("−49.8% → −11.4%", text)
            self.assertIn("Han·Zhou·Zhu", text)
            # 남의 자료로 잰 값이라는 것을 반드시 붙인다.
            self.assertIn("남의 자료로 잰 값입니다", text)

    def test_origins_doc_exists_and_lists_sources(self):
        import pathlib

        doc = pathlib.Path("docs/METHOD_ORIGINS.md")
        self.assertTrue(doc.exists(), "조사 원본 문서가 없다")
        body = doc.read_text(encoding="utf-8")
        for token in ("Do Industries Explain Momentum", "52-Week High", "Taming Momentum Crashes"):
            self.assertIn(token, body)

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

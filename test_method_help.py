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
        """닫는 길은 맨 아래 '창닫기' 단추와 그 옆 안내문 둘 다다(2026-08-06).

        예전에는 창 맨 위 안내문 한 줄뿐이었다. 글을 다 읽고 나면 여는 단추가
        화면 위로 올라가 안 보인다는 지적을 받아 아래에 단추를 뒀다.
        """
        import inspect

        # 안내문은 '창닫기 단추'를 가리켜야 한다 — 예전에는 여는 단추를 다시
        # 누르라는 말뿐이었는데, 이제 창닫기가 확실히 닫히므로 그쪽을 먼저 알린다.
        self.assertIn("창닫기", method_help.CLOSE_HINT)
        closer = inspect.getsource(method_help._close_button)
        self.assertIn("창닫기", closer)
        self.assertIn("CLOSE_HINT", closer)
        # 맨 위 하나(창이 위에서 열리게 붙잡는 구실) + 미국·한국 각 맨 아래 하나.
        self.assertEqual(3, inspect.getsource(method_help.render).count("_close_button("))
        self.assertIn('where="top"', inspect.getsource(method_help.render))

    def test_closing_goes_through_the_popover_state(self):
        """'창닫기'는 session_state를 꺼서 닫는다 — 되돌아가면 안 닫힌다.

        2026-08-07 실측: 단추를 누르면 스트림릿 프런트가 40ms 안에 창을 지우지만,
        서버가 '아직 열림'으로 다시 그리면 창이 도로 열린다. 그래서 단추만 놓고
        '다시 그려지니 닫히겠지' 하면 안 닫힌다(단추를 둘로 늘렸을 때 실제로 그랬다).
        `key`와 `on_change`를 준 팝오버라야 열림 상태가 session_state에 담긴다.
        """
        import inspect

        render = inspect.getsource(method_help.render)
        self.assertIn("key=popover_key(market)", render)
        self.assertIn('on_change="rerun"', render)
        self.assertIn("on_click=_shut", inspect.getsource(method_help._close_button))
        self.assertIn("= False", inspect.getsource(method_help._shut))

    def test_phone_and_tablet_get_the_window_sized_to_the_screen(self):
        """2026-08-07 지시 — 폰·태블릿도 되게, 태블릿을 눕히면 화면 너비에 맞게."""
        css = method_help.BUTTON_CSS
        self.assertIn("@media (max-width: 1200px) {", css)
        self.assertIn("@media (max-width: 1200px) and (orientation: landscape) {", css)
        # 눕히면 세로가 짧아지므로 높이를 더 준다.
        self.assertIn("max-height: 82vh !important", css)
        # 폰에서 좌우 칸이 위아래로 쌓여 단추가 왼쪽으로 가는 것은 폰 규칙이라
        # CLAUDE.md 12번에 따라 mobile_ui.py 폰 묶음에 둔다.
        self.assertIn("st-key-jarvis_method_help_close", mobile_ui.CONTENT_CSS)

    def test_bold_runs_are_not_broken_by_korean_particles(self):
        """닫는 ** 앞이 %·)·' 이고 뒤에 한글이 붙으면 별표가 그대로 찍힌다."""
        for text in (method_help.US_TEXT, method_help.KR_TEXT):
            broken = re.findall(r"\*\*[^*\n]*[%)'\]）]\*\*[가-힣]", text)
            self.assertEqual([], broken, f"굵은 글씨가 깨진다: {broken}")


def _visible(text: str) -> str:
    """화면에 실제로 보이는 글자만 남긴다 — 설명서가 HTML이라 태그·기호가 섞여 있다."""
    import html as _html

    return _html.unescape(re.sub(r"<[^>]+>", "", text))


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
    """2026-08-06 — 미국 설명은 사용자가 만든 **표 그림 두 장**이다.

    그전에는 사용자가 준 검증값(승률 59.7%(119건)·100.0%(12건)·92.6%(27건)·
    평균 +18.0%)을 글로 적어 두었다. 그 숫자는 표본이 119건·12건이고 급락 쪽은
    2025년 4월 한 번을 잰 값이라, 10년으로 다시 재니 유지되지 않았다
    (docs/REMEASURE_20260805.md). 그래서 표 그림으로 갈아 끼웠다.
    """

    def test_the_two_tables_are_shown_as_images(self):
        names = [name for name, _caption in method_help.US_IMAGES]
        self.assertEqual(
            ["us_method_uptrend.png", "us_method_drawdown.png"], names,
            "'정상적인 상승일때'가 먼저 나와야 한다(2026-08-06 사용자 지시)",
        )
        for name, _caption in method_help.US_IMAGES:
            self.assertIsNotNone(
                method_help._image_path(name), f"assets/{name}이 없다",
            )

    def test_the_renderer_actually_draws_them(self):
        import inspect

        source = inspect.getsource(method_help.render)
        self.assertIn("st.image", source)
        self.assertIn("US_IMAGES", source)
        # 그림이 빠져도 화면이 죽으면 안 된다(온라인 배포에서 실제로 생길 수 있다).
        self.assertIn("st.warning", source)

    def test_the_old_overstated_numbers_are_gone(self):
        """표본 119건·12건짜리 숫자가 다시 기어들어오면 화면이 거짓말을 한다."""
        whole = method_help.US_TEXT + method_help.US_MID_TEXT + method_help.US_TAIL_TEXT
        for token in ("59.7%", "119건", "100.0% (12건)", "92.6% (27건)",
                      "+18.0%", "+24.9%", "GPT-5.6 SOL", "재검증 5,000회"):
            self.assertNotIn(token, whole, f"옛 검증값 {token}이 남아 있다")

    def test_the_headline_says_only_when_to_buy_and_sell(self):
        """그림에 있는 말을 글로 또 적지 않는다(2026-08-06 사용자 지시).

        종목·기간·자료·지수는 두 그림 머리에 다 있고, 빨강·파랑과 색칠한 칸도
        그림을 보면 안다. 글에는 그림이 말해 주지 않는 **사고파는 때** 한 줄만 둔다.
        """
        us = _visible(method_help.US_TEXT)
        self.assertIn("다음 거래일 시가", us)
        self.assertIn("종가", us)
        for repeated in ("나스닥100 96종목", "Yahoo Finance", "QQQ", "2016년 8월",
                         "수익율", "승률", "가운데 값"):
            self.assertNotIn(repeated, us, f"그림이 이미 말하는 '{repeated}'를 또 적었다")

    def test_the_warnings_survive(self):
        """숫자만 크게 보이면 설명이 광고가 된다. 한계를 반드시 같이 적는다.

        다만 **표에 이미 있는 것은 적지 않는다** — 사건수는 표의 '얼마나 자주 오나'
        칸에 25번·7번·4번·2번·1번으로 다 적혀 있어서 뺐다(2026-08-06 사용자 지시).
        """
        tail = _visible(method_help.US_MID_TEXT + method_help.US_TAIL_TEXT)
        self.assertIn("해마다 20.9%씩 오른 기간", tail)
        self.assertIn("손절 규칙은 없습니다", tail)
        # 1~2개월 보유가 가장 나빴다는 것 — 표에는 3개월부터만 있어서 꼭 적어야 한다.
        self.assertIn("1~2개월", tail)
        # 표가 이미 말하는 것은 글로 또 적지 않는다.
        self.assertNotIn("사건수", tail)

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
        for market, text in (("US", method_help.US_TEXT), ("KR", method_help.KR_TEXT)):
            self.assertNotIn("\n\n", text.strip("\n"), f"{market} 설명서에 빈 줄이 있다")

    def test_korea_wears_the_same_clothes(self):
        """2026-08-01 — 한국 설명도 미국과 같은 옷(HTML·색·기호)으로 맞췄다.

        한국 눌림목 매매 검증 원고는 아직 못 받아서, 내용은 지금까지 화면에 있던
        한국 숫자 그대로다. 없는 숫자를 지어내지 않는다.
        """
        kr = method_help.KR_TEXT
        self.assertIn('class="mh-doc"', kr)
        for name in ("mh-h1", "mh-h2", "mh-note", "mh-warn-box", "mh-key"):
            self.assertIn(name, kr, f"{name} 옷이 한국 설명에 없다")
        # 규칙(3~5거래일·4~6%·120거래일 보유)은 같이 써도 된다 — 그건 '무엇을 보는가'다.
        # 옮겨 적으면 안 되는 것은 **미국 자료로 잰 성적**이다.
        for us_only in ("59.7%", "+18.0%", "92.6%", "GPT-5.6 SOL", "재검증 5,000회"):
            self.assertNotIn(us_only, kr, f"미국 검증값 {us_only}이 한국 설명에 새어 들어갔다")

    def test_korea_numbers_come_with_their_baseline(self):
        """2026-08-01에 한국 자료로 직접 쟀다. 성적만 적으면 오해한다.

        살아남은 종목만 보는 치우침은 '아무 날이나 샀으면'과 견줄 때만 상쇄된다.
        그래서 성적 옆에는 반드시 기준선이 붙어야 하고, 진 갈래는 졌다고 적어야 한다.
        """
        import jarvis4_data as j4

        kr = _visible(method_help.KR_TEXT)
        rule = j4.BREAKOUT_PULLBACK_RULE
        self.assertTrue(rule["verified_in_korea"])
        # 화면 숫자와 코드 숫자가 어긋나면 안 된다.
        self.assertIn(f"승률 {rule['win_rate']}%", kr)
        self.assertIn(f"승률 {rule['base_win_rate']}%", kr)
        self.assertIn(f"{rule['years_total']}년 중 {rule['years_better']}년", kr)
        # 2026-08-07 재측정 — 기준선에 진 얕은 갈래는 그물에서 아예 뺐다.
        # 그래서 갈래가 하나뿐이고, 그 하나는 기준선을 이긴다.
        for bucket in j4.CRASH_REBOUND_RULES:
            self.assertIn(f"승률 {bucket['win_rate']}%", kr)
            self.assertIn(f"승률 {bucket['base_win_rate']}%", kr)
            self.assertTrue(bucket["beats_baseline"])
        # 절대로는 여전히 잃는다는 것을 감추면 안 된다(상승장 가운데 -6.6%).
        self.assertIn("이기는 것과 버는 것은 다릅니다", kr)
        # 급락 신호가 몇 번뿐이었는지도 밝혀야 한다.
        self.assertIn("스물아홉 번", kr)
        self.assertIn("2014-05 ~ 2026-08", kr)

    def test_korea_documents_the_two_rulebook_screens(self):
        """화면에 단추를 만들었으면 설명서에도 그 기준이 있어야 한다(2026-08-01)."""
        import jarvis4_data as j4

        kr = _visible(method_help.KR_TEXT)
        self.assertIn("상승장 (신고가 눌림매수)", kr)
        self.assertIn("급락 후 반등장 (낙폭종목)", kr)
        # 설명서에 적힌 숫자와 실제로 찾는 기준이 같아야 한다.
        wait_min, wait_max = j4.BREAKOUT_PULLBACK_RULE["wait_days"]
        self.assertIn(f"{wait_min}~{wait_max}거래일", kr)
        self.assertIn("4~6%", kr)
        self.assertIn(f"{j4.BREAKOUT_PULLBACK_RULE['hold_days']}거래일", kr)
        # 2026-08-07 재측정 — 갈래가 하나(-40~-60%)로 줄었다.
        (deep,) = j4.CRASH_REBOUND_RULES
        self.assertIn("40~60% 빠진", kr)
        self.assertIn(f"{deep['hold_days']}거래일", kr)
        # 거래대금 문턱이 새로 들어갔다 — 그 아래는 아예 안 본다.
        self.assertIn("50억 이상", kr)
        # 이동평균을 안 본다는 것도 적혀 있어야 한다.
        self.assertIn("보지 않습니다", kr)


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
        # 2026-08-01부터 한국 설명도 HTML이라 굵게(**) 표시가 없다 — 보이는 글자로 본다.
        body = _visible(method_help.KR_TEXT)
        for token in ("50점↑", "60점↑", "70점↑", "85점"):
            self.assertIn(token, body, f"한국 문구에 {token}이 없다")

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
        kr = _visible(method_help.KR_TEXT)
        self.assertIn("한 편의 논문에서 나온 기법이 아닙니다", kr)
        for name in ("Moskowitz & Grinblatt 1999", "George & Hwang 2004", "Weinstein"):
            self.assertIn(name, kr, f"{name}가 빠졌다")

    def test_it_admits_there_is_no_sell_signal(self):
        """한국 문구는 아직 파는 때가 없다고 밝혀야 한다.

        미국 문구에는 2026-08-01부터 매도 규칙(120거래일·20거래일·60거래일 보유)이
        들어갔으므로 이 문장이 있으면 도리어 거짓말이 된다.
        """
        self.assertIn("파는 때는 아직 이 화면에 없습니다", method_help.KR_TEXT)
        # 그 문장이 어디 이야기인지 밝혀야 한다 — 두 갈래에는 보유일수가 있어서
        # 밝히지 않으면 서로 모순되게 읽힌다(2026-08-01).
        self.assertIn("눌림목 찾기 표", method_help.KR_TEXT)
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

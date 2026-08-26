"""'매수 심사 결과 높은 순위 7' 자료 함수 (2026-07-30 사용자 지시).

전수 검색을 새로 돌리지 않고, 이미 있는 테마 대장주 + 눌림목 결과만 모아
종목 조건점수 하나로 줄 세운다. 순위 기준이 둘이 되면 표를 못 읽으므로
'점수 하나'라는 규칙을 여기서 붙잡는다.
"""

import time
import unittest
from unittest.mock import patch

import jarvis3_data as j3
import jarvis4_data as j4


def _metrics(**over):
    base = {
        "ok": True, "current": 100.0, "sma20": 98.0, "sma50": 95.0,
        "high52": 110.0, "from_high_pct": -9.0, "ret5": 1.0, "ret20": 5.0,
        "atr": 2.0, "atr_pct": 2.0, "volume_ratio": 1.0, "change_pct": 0.5,
    }
    base.update(over)
    return base


def _kr_leader(code, name, score, **over):
    row = {"code": code, "name": name, "score": score, "metrics": _metrics(),
           "flow": {"ok": False}, "plan": {"state": "관찰"}, "rank": 1}
    row.update(over)
    return row


def _us_leader(ticker, score, **over):
    row = {"ticker": ticker, "name": ticker, "score": score, "metrics": _metrics(),
           "plan": {"state": "관찰"}, "rank": 1}
    row.update(over)
    return row


class KoreaTests(unittest.TestCase):
    def test_ranks_by_stock_score_only_and_caps_at_seven(self):
        themes = [{"name": f"테마{i}", "score": 50 + i} for i in range(4)]

        def fake_leaders(theme_row, market_score=0, theme_score=0, stock_limit=None):
            index = int(str(theme_row["name"])[-1])
            return {"ok": True, "rows": [
                _kr_leader(f"{index}0000{n}", f"종목{index}{n}", 90 - index * 10 - n)
                for n in range(3)
            ]}

        with patch.object(j4, "get_theme_leaders", side_effect=fake_leaders):
            result = j4.find_top_reviewed_stocks(themes, market_score=60)

        self.assertTrue(result["ok"])
        self.assertEqual(7, len(result["rows"]), "7개로 잘라야 한다")
        scores = [row["score"] for row in result["rows"]]
        self.assertEqual(sorted(scores, reverse=True), scores, "점수 내림차순이 아니다")
        self.assertEqual([1, 2, 3, 4, 5, 6, 7], [r["pick_rank"] for r in result["rows"]])
        self.assertEqual(4, result["scanned_themes"])

    def test_same_stock_in_two_themes_is_kept_once_with_the_better_score(self):
        themes = [{"name": "가", "score": 80}, {"name": "나", "score": 70}]

        def fake_leaders(theme_row, market_score=0, theme_score=0, stock_limit=None):
            score = 88.0 if theme_row["name"] == "가" else 61.0
            return {"ok": True, "rows": [_kr_leader("005930", "삼성전자", score)]}

        with patch.object(j4, "get_theme_leaders", side_effect=fake_leaders):
            result = j4.find_top_reviewed_stocks(themes, market_score=60)

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual(88.0, result["rows"][0]["score"])
        self.assertEqual(["가", "나"], sorted(result["rows"][0]["sources"]))

    def test_one_broken_theme_does_not_lose_the_others(self):
        themes = [{"name": "성한테마", "score": 80}, {"name": "고장테마", "score": 70}]

        def fake_leaders(theme_row, market_score=0, theme_score=0, stock_limit=None):
            if theme_row["name"] == "고장테마":
                raise RuntimeError("네이버 응답 없음")
            return {"ok": True, "rows": [_kr_leader("000660", "SK하이닉스", 77.0)]}

        with patch.object(j4, "get_theme_leaders", side_effect=fake_leaders):
            result = j4.find_top_reviewed_stocks(themes, market_score=60)

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual(1, result["scanned_themes"])
        self.assertTrue(any("고장테마" in message for message in result["errors"]))

    def test_pullback_rows_join_in_and_get_rejudged_with_the_real_market_score(self):
        """눌림목 결과는 게이트를 열어 둔 채 계산돼 있다 — 시장 점수로 다시 판정해야 한다."""
        pull = {"code": "035420", "name": "NAVER", "score": 92.0,
                "metrics": _metrics(), "themes": ["가"],
                "plan": {"state": "눌림목 대기", "recommendation": "조건부 후보"}}

        with patch.object(j4, "get_theme_leaders",
                          side_effect=lambda *a, **k: {"ok": True, "rows": []}):
            blocked = j4.find_top_reviewed_stocks(
                [{"name": "가", "score": 80}], market_score=10, extra_rows=[pull]
            )
            allowed = j4.find_top_reviewed_stocks(
                [{"name": "가", "score": 80}], market_score=90, extra_rows=[pull]
            )

        self.assertEqual(1, len(blocked["rows"]))
        self.assertNotEqual(
            "조건부 후보", blocked["rows"][0]["plan"]["recommendation"],
            "시장 점수 10점인데도 조건부 후보로 남았다",
        )
        self.assertEqual("조건부 후보", allowed["rows"][0]["plan"]["recommendation"])

    def test_empty_input_is_not_an_error(self):
        result = j4.find_top_reviewed_stocks([], market_score=60)
        self.assertFalse(result["ok"])
        self.assertEqual([], result["rows"])


class PageWiringTests(unittest.TestCase):
    """자료 함수만 있고 화면에 안 붙어 있으면 아무 소용이 없다."""

    PAGES = {
        "US": ("pages/2_자비스3.py", "j3"),
        "KR": ("pages/3_자비스4.py", "j4"),
    }
    # 2026-08-12에 미국만 7 → 9로 바꿨다(상하님 지시: 대장주 3 · 상승장 3 · 급락 3).
    # 한국은 아직 그대로다 — 한 시장을 고치면서 다른 시장을 같이 건드리지 않는다
    # (CLAUDE.md 0-1 다). 한국을 같은 기준으로 맞출 때 여기 숫자도 같이 고친다.
    COUNTS = {"US": 9, "KR": 7}

    def test_both_pages_show_the_section(self):
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            self.assertIn(f"매수심사결과 높은 순위 {self.COUNTS[market]}", source,
                          f"{market} 화면에 제목이 없다")
            self.assertIn("def _render_top_reviewed(", source, f"{market}에 그리는 함수가 없다")
            self.assertIn("_render_top_reviewed(market, ranking)", source,
                          f"{market}에서 부르지 않는다")
            # 미국은 2026-08-15부터 collect_top_picks(같은 모듈이 3·3·3까지 해 준다)를
            # 부른다. 한국은 아직 옛 방식이다 — 한국은 이번에 건드리지 않았다.
            self.assertTrue(
                "find_top_reviewed_stocks(" in source or "collect_top_picks(" in source,
                f"{market}가 자료를 안 부른다")
            # 눌림목/갈래 결과도 함께 넣어야 한다(사용자 지시).
            self.assertIn(f"{prefix}_pullback_result", source)
            if prefix == "j3":
                # 2026-08-06 사용자 지시 — "누르든 안 누르든 둘 다 자동으로".
                # 다만 **섞어서 한 줄로 세우지 않는다.** 세 군데가 자가 달라
                # 급락 종목이 대장주의 자로는 영원히 못 올라온다. 그래서 자리를
                # 나눠 각자 자기 자로 뽑는다(대장주 3 · 상승장 2 · 급락 2).
                # **뽑는 일은 2026-08-15에 jarvis3_data로 옮겼다** — 화면과 클라우드
                # 수집기가 같은 함수를 불러야 저장 목록이 화면과 갈라지지 않는다.
                module = pathlib.Path("jarvis3_data.py").read_text(encoding="utf-8")
                self.assertIn("def collect_top_picks(", module,
                              "순위 9를 만드는 함수가 모듈에 없다")
                self.assertIn("find_breakout_pullback_stocks", module,
                              "미국 순위 9가 상승장 갈래를 안 가져온다")
                self.assertIn("find_crash_rebound_stocks", module,
                              "미국 순위 9가 급락 갈래를 안 가져온다")
                self.assertIn("collect_top_picks(", source, "미국 화면이 순위 9를 안 부른다")
                self.assertIn("_TOP7_QUOTA", source, "미국 순위 9에 자리 배분이 없다")
                self.assertIn("top7_origin", module, "어느 갈래에서 왔는지 안 적는다")
                # 2026-08-06 사용자 지적 — 다른 구역에는 다 있는 맨 아래 닫기 단추가
                # 순위 7에만 없었다.
                self.assertIn('_section_close("j3_top7_open"', source,
                              "순위 7에 맨 아래 닫기 단추가 없다")
                # 종목을 누르면 상세와 차트가 한꺼번에 열려야 한다(상승장·급락과 같게).
                block = source.split("def _render_top_reviewed(")[1].split("\ndef ")[0]
                for key in ("j3_detail_open_top7", "j3_bundle_open_top7",
                            "j3_bundle_open_pullback"):
                    self.assertIn(key, block, f"종목을 눌러도 {key}가 안 열린다")
            else:
                self.assertIn("extra_rows=pull_rows", source)

    def test_clicking_a_row_opens_its_own_detail(self):
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            self.assertIn(f"{prefix}top7_", source, f"{market}에 종목 단추가 없다")
            self.assertIn(f"{prefix}_top7_pick_row", source)
            self.assertIn("def _render_top_reviewed_detail(", source)
            # 상세는 위 테마 상세·눌림목 상세와 키가 겹치면 안 된다.
            self.assertIn('panel="top7"', source, f"{market} 상세 패널 키가 안 갈렸다")

    def test_table_opens_straight_on_the_page(self):
        """2026-07-30 사용자 지시 — 창을 또 눌러 여는 방식을 없앤다.

        단추 한 번에 표가 바로 펴져야 한다. 팝오버로 되돌아가면 이 테스트가 깨진다.
        """
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            block = source.split("def _render_top_reviewed(")[1].split("\ndef ")[0]
            self.assertNotIn("st.popover", block, f"{market}가 아직 창을 또 열게 한다")
            self.assertNotIn("순위 7 펼쳐 보기", source)
            # 표는 위 테마 종목표와 같은 모양 — 점수 막대를 쓴다.
            self.assertIn(f"{prefix}-bar-fill", block, f"{market} 표에 점수 막대가 없다")
            self.assertIn("매수 상태", block)

    def test_the_buttons_are_not_full_width_bars(self):
        """바가 너무 길다는 지적(2026-07-30) — 글자 크기만큼만 차지한다."""
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            self.assertIn(
                f'"매수심사결과 높은 순위 {self.COUNTS[market]}", key="{prefix}_top7_find")',
                source, f"{market} 순위 단추가 아직 화면을 가로지른다")
            # 2026-08-01에 눌림목 단추는 설명서 두 갈래 단추와 나란히 놓이면서
            # 글자에 '●'를 붙이는 구조로 바뀌었다.
            # 2026-08-06에 **미국만** 눌림목 찾기를 뺐다(사용자 지시) — 목적이
            # 상승장 갈래와 같은데 10년치로 재니 기준선을 못 이겼다. 한국은 그대로다
            # (한국에서는 눌림목 점수가 제대로 작동한다, docs/KR_RULE_BACKTEST.md).
            if prefix == "j3":
                self.assertNotIn(f'("기본", "눌림목 찾기", "{prefix}_pullback_find")',
                                 source, f"{market} 눌림목 단추가 되살아났다")
            else:
                self.assertIn(f'"{prefix}_pullback_find"', source,
                              f"{market} 눌림목 단추가 없다")
                self.assertIn("눌림목 찾기", source, f"{market} 눌림목 단추 이름이 없다")
            for key in (f"{prefix}_pullback_find", f"{prefix}_pullback_breakout",
                        f"{prefix}_pullback_crash"):
                self.assertNotIn(f'key="{key}", width="stretch"', source,
                                 f"{market} {key} 단추가 화면을 가로지른다")
                self.assertNotIn(f'key="{key}", use_container_width=True', source)

    def test_pullback_button_is_a_deep_blue_gradient(self):
        """캡처 1과 같은 모양에 진한 푸른색(2026-07-30 사용자 지시)."""
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            block = source.split(f'div[class*="st-key-{prefix}_pullback_find"] button {{')[1]
            self.assertIn("linear-gradient(90deg, #0b2a4a", block, f"{market} 눌림목 단추가 그라데이션이 아니다")
            self.assertNotIn("#cfe9ff", block.split("}")[0], f"{market}에 옛 하늘색이 남았다")

    def test_the_list_toggles_open_and_closed(self):
        """한 번 더 누르면 접히고 또 누르면 펴진다(2026-07-30 사용자 지시)."""
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            block = source.split("def _render_top_reviewed(")[1].split("\ndef ")[0]
            self.assertIn(f'"{prefix}_top7_open"', block, f"{market}에 접었다 펴는 장치가 없다")
            # 두 페이지의 단추 짜임새가 서로 다르다(미국은 run_requested를 거친다).
            # 어느 쪽이든 '열려 있으면 접는' 갈래가 있으면 된다.
            self.assertTrue(
                "if run_requested and is_open:" in block or "if is_open:" in block,
                f"{market}가 다시 눌러도 안 접힌다",
            )

    def test_there_is_only_one_button(self):
        """단추는 하나다 (2026-07-30 사용자 지시: '새로 뽑기'를 따로 두지 마라).

        같은 날 '열기'와 '새로 뽑기'로 나눴다가 되돌렸다 — 묻지 않고 화면에 단추를
        늘린 것이 문제였다. 늘리려면 먼저 물어야 한다.
        """
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            block = source.split("def _render_top_reviewed(")[1].split("\ndef ")[0]
            self.assertNotIn('button("새로 뽑기"', block, f"{market}에 단추가 또 늘었다")
            self.assertNotIn(f"{prefix}_top7_refind", block)
            self.assertEqual(
                1, block.count(f'st.button("매수심사결과 높은 순위 {self.COUNTS[market]}"'),
                f"{market} 순위 단추가 하나가 아니다")

    def test_phone_slides_the_table_sideways(self):
        """폰에서 한 종목이 여섯 줄로 쌓이던 것을 옆으로 밀어 보게 바꿨다(2026-08-01).

        사용자 지시 — 오늘의 강한테마·테마 종목 1~6위·눌림목 찾기가 전부 옆으로
        미는 방식이니 순위 7도 같게 하라. 그래서 세로로 쌓던 규칙(table_css·
        hide_own_header)을 빼고, 나머지 세 표와 같은 규칙에 얹었다.
        """
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            # 세로로 쌓던 규칙이 되살아나면 다시 여섯 줄이 된다.
            self.assertNotIn(f'"{prefix}top7_", 6,', source,
                             f"{market} 순위 7이 다시 세로로 쌓인다")
            self.assertNotIn(f'hide_own_header("{prefix}_top7_table"', source,
                             f"{market} 순위 7 머리글이 다시 감춰진다")
            # 나머지 세 표와 같은 옆으로 밀기 규칙에 들어 있어야 한다.
            self.assertIn(f".st-key-{prefix}_top7_table,", source,
                          f"{market} 순위 7이 옆으로 밀리지 않는다")
            self.assertIn(f'.st-key-{prefix}_top7_table [data-testid="stHorizontalBlock"],',
                          source, f"{market} 순위 7 줄이 폰에서 접힌다")
            # 폰 규칙을 페이지에 직접 쓰면 안 된다.
            self.assertNotIn("max-width: 600px", source, f"{market}에 폰 규칙이 새어 나왔다")

    def test_closing_does_no_work(self):
        """닫는 데 5초가 걸렸다(2026-07-30 사용자 실측).

        닫을 때 조회를 돌리거나 st.rerun()을 부르면 화면을 통째로 다시 그린다.
        닫기는 값만 바꾸고 끝나야 한다.
        """
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            block = source.split("def _render_top_reviewed(")[1].split("\ndef ")[0]
            if "if run_requested and is_open:" in block:
                close = block.split("if run_requested and is_open:")[1].split("\n    if ")[0]
                run = block.split("\n    if run_requested:\n")[1]
            else:
                close = block.split("if is_open:")[1].split("else:")[0]
                run = block.split("else:")[1]
            # 미국은 2026-08-06부터 _blend_top7()이 세 군데를 뽑아 합친다.
            fetch = "_blend_top7(" if prefix == "j3" else "find_top_reviewed_stocks"
            self.assertNotIn("st.rerun()", close, f"{market}가 닫을 때 다시 그린다")
            self.assertNotIn(fetch, close, f"{market}가 닫을 때도 조회한다")
            # 조회는 '뽑는 쪽' 갈래에만 있어야 한다.
            self.assertIn(fetch, run, f"{market}에서 뽑는 자리가 사라졌다")

    def test_opening_does_not_preload_a_stock_detail(self):
        """1위 상세를 미리 펴면 분봉·일봉·주봉·월봉을 다 받아 오느라 느려진다."""
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            block = source.split("def _render_top_reviewed(")[1].split("\ndef ")[0]
            self.assertNotIn(f'st.session_state["{prefix}_top7_pick_row"] = first', block,
                             f"{market}가 1위 상세를 미리 편다")

    def test_pullback_also_toggles(self):
        """눌림목 찾기도 두 번째 클릭에 접혀야 한다(2026-07-30 사용자 지적)."""
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            marker = ("def _render_pullback_finder_body("
                  if "def _render_pullback_finder_body(" in source
                  else "def _render_pullback_finder(")
            block = source.split(marker)[1].split("\ndef ")[0]
            self.assertIn(f'"{prefix}_pullback_open"', block,
                          f"{market} 눌림목이 다시 눌러도 안 접힌다")

    def test_heavy_sections_open_only_when_clicked(self):
        """무거운 구역은 눌러야 열린다(2026-07-30 사용자 지시 + 로딩 단축).

        st.expander는 접혀 있어도 안을 다 그려 시세를 미리 받아 오므로 쓰지 않는다.
        _section_toggle이 빠지면 다시 늘 그리게 되어 느려진다.
        """
        import pathlib

        # (여는 열쇠, 화면에 뜨는 말)
        sections = [
            ("_detail_open_", "선택종목 세부사항 보기"),
            ("_intraday_open_", "당일 · 실시간 차트 보기"),
            ("_bundle_open_", "일봉 · 주봉 · 월봉 보기"),
            ("_buyform_open_", "실제 매수기록 저장하시겠습니까?"),
            ("_leadercmp_open", "대장주 1~3위 · 당일/일봉/주봉 비교"),
        ]
        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            for key, label in sections:
                self.assertIn(f'"{prefix}{key}', source, f"{market}에 '{label}' 여는 장치가 없다")
                self.assertIn(label, source, f"{market}에 '{label}' 문구가 없다")
            # 대장주 비교는 제목을 그대로 두고 안내만 뒤에 붙인다.
            self.assertIn("클릭하면 볼 수 있습니다", source)
            self.assertIn("다시 클릭하면 닫힙니다", source)

    def test_toggle_label_matches_what_is_shown(self):
        """닫았는데 '닫기'가 그대로 남던 버그(2026-07-30 사용자 지적).

        단추를 만든 뒤에 상태를 뒤집으면 그 판에는 이미 옛 글자가 찍혀 있다.
        on_click은 화면을 다시 그리기 전에 돌아서 글자와 속내용이 같은 판에서 맞는다.
        if st.button(...) 방식으로 되돌아가면 다시 뒤바뀐다.
        """
        import pathlib

        for market, (path, _prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            block = source.split("def _section_toggle(")[1].split("\ndef ")[0]
            self.assertIn("on_click=_flip", block, f"{market}가 on_click을 안 쓴다")
            self.assertNotIn("if st.button(", block,
                             f"{market}가 단추를 만든 뒤에 상태를 뒤집는다")

    def test_leader_comparison_button_is_red(self):
        """대장주 1~3위 비교만 붉은색 — 나머지 구역 단추(황금색)와 갈린다."""
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            block = source.split(
                f'div[class*="st-key-btn_{prefix}_leadercmp_open"] button {{'
            )[1].split("}")[0]
            self.assertIn("#4a0f12", block, f"{market} 대장주 비교가 붉은색이 아니다")
            self.assertNotIn("#6b4d16", block, f"{market} 대장주 비교에 황금색이 남았다")

    def test_stock_search_heading_is_a_purple_band(self):
        """'종목검색' 제목은 보라색 띠(2026-07-30 사용자 지시). 단추는 아니다."""
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            self.assertIn(f"{prefix}-band {{", source, f"{market}에 띠 CSS가 없다")
            self.assertIn(f"{prefix}-band-purple {{", source)
            self.assertIn("#7c3aed", source, f"{market} 띠가 보라색이 아니다")
            self.assertIn(
                f"'{prefix}-band {prefix}-band-purple'>종목검색 (검색종목 세부사항 보기)",
                source, f"{market} 제목에 띠가 안 붙었다",
            )
            # 누를 곳이 아니다 — 단추로 만들면 안 된다.
            self.assertNotIn('st.button("종목검색', source)

    def test_themes_are_fetched_in_parallel(self):
        """로딩이 너무 길다는 지적(2026-07-30) — 테마를 한꺼번에 돌린다."""
        import pathlib
        import re

        for name in ("jarvis3_data.py", "jarvis4_data.py"):
            source = pathlib.Path(name).read_text(encoding="utf-8")
            block = source.split("def find_top_reviewed_stocks(")[1].split("\ndef ")[0]
            self.assertIn("ThreadPoolExecutor", block, f"{name}가 아직 하나씩 돈다")
            self.assertTrue(re.search(r"max_workers=\d+", block))

    def test_long_theme_names_do_not_spill_into_the_next_column(self):
        """분야 이름이 길어 현재가 칸을 덮어썼다(2026-07-30 캡처)."""
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            self.assertIn(f".{prefix}-top7-src {{", source, f"{market}에 자르는 규칙이 없다")
            self.assertIn("text-overflow: ellipsis", source)

    def test_module_reload_guards_know_the_new_function(self):
        """규칙 11 — 새 함수를 가드에 안 넣으면 온라인에서 AttributeError가 난다."""
        import pathlib

        for market, (path, _prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            self.assertIn('"find_top_reviewed_stocks"', source,
                          f"{market} 모듈 리로드 가드에 새 함수가 없다")


class HttpSessionTests(unittest.TestCase):
    """느린 원인이었던 HTTPS 악수 (2026-07-30 사용자 실측: 순위 7이 15초).

    워커 스레드마다 세션을 따로 두면 테마마다 스레드가 죽고 살아나며 세션도 새로
    만들어져, 한 번 훑는 데 새 세션이 114개 생겼다. 지연이 큰 회선에서는 그 악수가
    그대로 대기 시간이 된다. 연결을 함께 쓰도록 되돌아가면 이 테스트가 깨진다.
    """

    def test_the_session_is_shared_not_per_thread(self):
        from concurrent.futures import ThreadPoolExecutor

        first = j4._http_session()
        with ThreadPoolExecutor(max_workers=8) as executor:
            others = list(executor.map(lambda _: j4._http_session(), range(16)))
        for session in others:
            self.assertIs(first, session, "스레드마다 세션이 따로 만들어진다")

    def test_the_pool_is_big_enough_for_the_workers(self):
        import pathlib
        import re

        source = pathlib.Path("jarvis4_data.py").read_text(encoding="utf-8")
        self.assertIn("pool_maxsize=_HTTP_POOL_SIZE", source)
        # 테마 6갈래 × 종목 8갈래 = 48. 풀이 그보다 작으면 워커가 줄을 선다.
        self.assertGreaterEqual(j4._HTTP_POOL_SIZE, 48)
        block = source.split("def find_top_reviewed_stocks(")[1].split("\ndef ")[0]
        workers = int(re.search(r"max_workers=(\d+)", block).group(1))
        self.assertLessEqual(workers * 8, j4._HTTP_POOL_SIZE)

    def test_thread_local_session_is_gone(self):
        self.assertFalse(hasattr(j4, "_HTTP_LOCAL"), "옛 스레드별 세션이 남아 있다")


class UnitedStatesTests(unittest.TestCase):
    def test_ranks_by_score_and_dedups_by_ticker(self):
        themes = [{"name": "반도체", "score": 80}, {"name": "AI", "score": 75}]

        seen_charts = []
        seen_live = []

        def fake_leaders(theme_name, market_score=0, theme_score=0, with_charts=True,
                         with_live=True):
            seen_charts.append(with_charts)
            seen_live.append(with_live)
            score = 91.0 if theme_name == "반도체" else 64.0
            return {"ok": True, "rows": [_us_leader("NVDA", score), _us_leader("AMD", 55.0)]}

        with patch.object(j3, "get_theme_leaders", side_effect=fake_leaders),              patch.object(j3, "_download_cached", return_value=({}, {})):
            result = j3.find_top_reviewed_stocks(themes, market_score=60)

        self.assertEqual(["NVDA", "AMD"], [row["ticker"] for row in result["rows"]])
        self.assertEqual(91.0, result["rows"][0]["score"])
        self.assertEqual(["AI", "반도체"], sorted(result["rows"][0]["sources"]))
        # 표만 그리는 자리라 차트 자료는 만들지 않는다(2026-07-30 속도).
        self.assertEqual([False, False], seen_charts)
        # 1차는 종가로만 줄 세운다 — 157종목 분봉을 받던 것을 없앴다(2026-07-31).
        self.assertEqual([False, False], seen_live)

    def test_slots_are_three_each_in_the_us(self):
        """2026-08-12 상하님 지시 — 대장주 3 · 상승장 3 · 급락 3, 합쳐 아홉이다.

        **빈 자리를 다른 갈래로 메우지 않는다.** 급락장에는 상승장 자리가 없고,
        그 사실이 화면에 남아야 한다.
        """
        self.assertEqual({"leader": 3, "breakout": 3, "crash": 3}, j3.TOP_REVIEW_SLOTS)
        self.assertEqual(9, j3.TOP_REVIEW_LIMIT)
        # 한국은 아직 7이다 — 같은 기준으로 맞출 때 같이 고친다(CLAUDE.md 0-1 다).
        self.assertEqual(7, j4.TOP_REVIEW_LIMIT)

    def test_the_us_page_does_not_backfill_empty_slots(self):
        """예전에는 남는 자리를 대장주가 채웠다. 그러면 자리가 비었다는 사실이 사라진다."""
        import pathlib

        # 2026-08-15에 뽑는 일이 jarvis3_data.blend_top_picks로 옮겨 갔다 —
        # 화면과 클라우드 수집기가 같은 함수를 불러야 저장 목록이 화면과 갈라지지
        # 않는다(CLAUDE.md 10-1).
        module = pathlib.Path("jarvis3_data.py").read_text(encoding="utf-8")
        block = module.split("def blend_top_picks(")[1].split("\ndef ")[0]
        self.assertNotIn("남는 자리는 대장주가 메운다", block, "빈 자리 메우기가 되살아났다")
        self.assertIn("empty_notes", block, "빈 자리를 왜 비웠는지 안 적는다")
        self.assertIn('("상승장", 3)', module)
        self.assertIn('("급락 후 반등장", 3)', module)
        # 화면은 그 결과를 **그대로 저장한다.** 섞기 전 재료를 저장하면 저장 목록과
        # 화면이 갈라진다(2026-08-15 상하님 지적으로 드러난 사고).
        source = pathlib.Path("pages/2_자비스3.py").read_text(encoding="utf-8")
        page_block = source.split("def _blend_top7(")[1].split("\ndef ")[0]
        self.assertIn('picklist_ui.autosave("US", "top7", result)', page_block,
                      "화면이 보여 주는 목록과 다른 것을 저장한다")


if __name__ == "__main__":
    unittest.main()

class TopPickMemoTests(unittest.TestCase):
    """순위 9를 여는 데 걸리던 7초를 줄인 기억장치 (2026-08-26 상하님 허락).

    상하님 지적 — "매수심사결과 높은 순위 9, 로딩 문제 아직 해결 안 된 것."
    노트북 실측 7.1초였고, 그 대부분이 이미 계산해 둔 것을 또 계산하는 것이었다.
    **점수·기준·명부·그물은 한 글자도 안 바뀐다.**
    """

    def setUp(self):
        with j3._CACHE_LOCK:
            for key in [k for k in j3._CACHE
                        if isinstance(k, str) and k.startswith(("top_leaders:", "top_finder:"))]:
                j3._CACHE.pop(key, None)

    tearDown = setUp

    def test_the_same_call_is_not_computed_twice(self):
        """두 번째부터는 다시 계산하지 않고 **같은 답**을 그대로 준다."""
        rows = [{"name": "바이오", "score": 90.8, "ok": True}]
        calls = {"leader": 0, "breakout": 0, "crash": 0}

        def leader(*a, **k):
            calls["leader"] += 1
            return {"ok": True, "rows": [{"ticker": "AAA", "score": 90.0}],
                    "scanned_themes": 1, "errors": []}

        def breakout():
            calls["breakout"] += 1
            return {"ok": True, "rows": []}

        def crash():
            calls["crash"] += 1
            return {"ok": True, "rows": []}

        with patch.object(j3, "find_top_reviewed_stocks", leader),              patch.object(j3, "find_breakout_pullback_stocks", breakout),              patch.object(j3, "find_crash_rebound_stocks", crash):
            first = j3.collect_top_picks(rows, market_score=65.0)
            second = j3.collect_top_picks(rows, market_score=65.0)

        self.assertEqual(calls, {"leader": 1, "breakout": 1, "crash": 1},
                         "두 번째에도 다시 계산했다")
        self.assertEqual(
            [(r.get("ticker"), r.get("score")) for r in first.get("rows") or []],
            [(r.get("ticker"), r.get("score")) for r in second.get("rows") or []],
            "기억해 둔 답이 처음 답과 다르다")

    def test_a_failure_is_never_remembered(self):
        """실패는 기억하지 않는다 — 기억하면 5분 내내 빈 화면이 굳는다."""
        rows = [{"name": "바이오", "score": 90.8, "ok": True}]
        with patch.object(j3, "find_top_reviewed_stocks",
                          lambda *a, **k: {"ok": True, "rows": [], "scanned_themes": 0, "errors": []}),              patch.object(j3, "find_breakout_pullback_stocks", lambda: {"ok": True, "rows": []}),              patch.object(j3, "find_crash_rebound_stocks",
                          lambda: {"ok": False, "error": "일부러 낸 실패", "rows": []}):
            j3.collect_top_picks(rows, market_score=65.0)
        with j3._CACHE_LOCK:
            self.assertNotIn("top_finder:급락 후 반등장", j3._CACHE,
                             "실패를 기억해 두었다")

    def test_an_empty_day_is_remembered(self):
        """걸린 종목이 0개인 것은 실패가 아니다 — 그대로 기억한다.

        CLAUDE.md 0-1 바 — 빈 자리를 감추거나 딴 것으로 채우지 않는다.
        "오늘은 이 자리가 없습니다"도 하나의 답이다.
        """
        rows = [{"name": "바이오", "score": 90.8, "ok": True}]
        with patch.object(j3, "find_top_reviewed_stocks",
                          lambda *a, **k: {"ok": True, "rows": [], "scanned_themes": 0, "errors": []}),              patch.object(j3, "find_breakout_pullback_stocks", lambda: {"ok": True, "rows": []}),              patch.object(j3, "find_crash_rebound_stocks", lambda: {"ok": True, "rows": []}):
            j3.collect_top_picks(rows, market_score=65.0)
        with j3._CACHE_LOCK:
            self.assertIn("top_finder:급락 후 반등장", j3._CACHE)

    def test_a_changed_theme_list_is_computed_again(self):
        """테마 줄이 바뀌면 기억한 것을 쓰지 않는다 — 옛 답이 되살아나면 안 된다."""
        calls = {"n": 0}

        def leader(*a, **k):
            calls["n"] += 1
            return {"ok": True, "rows": [], "scanned_themes": 1, "errors": []}

        with patch.object(j3, "find_top_reviewed_stocks", leader),              patch.object(j3, "find_breakout_pullback_stocks", lambda: {"ok": True, "rows": []}),              patch.object(j3, "find_crash_rebound_stocks", lambda: {"ok": True, "rows": []}):
            j3.collect_top_picks([{"name": "바이오", "score": 90.8}], market_score=65.0)
            j3.collect_top_picks([{"name": "바이오", "score": 91.9}], market_score=65.0)
            j3.collect_top_picks([{"name": "바이오", "score": 90.8}], market_score=70.0)
        self.assertEqual(calls["n"], 3, "테마 점수나 시장 점수가 바뀌었는데 옛 답을 썼다")

    def test_module_revision_was_raised(self):
        """규칙 11 — 계산이 도는 방식을 바꾸면 리비전을 같이 올린다."""
        from pathlib import Path
        page = (Path(__file__).resolve().parent / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        self.assertIn(f"_REQUIRED_J3_REVISION = {j3.MODULE_REVISION}", page,
                      "페이지가 요구하는 리비전이 모듈과 다르다")

class DiskPriceCacheTests(unittest.TestCase):
    """받아 온 시세를 파일로도 남긴다 (2026-08-26 상하님 허락받고 넣음).

    상하님 지적 — "미국테마 처음 들어갔을 때 로딩하고 있더라. 짧게 할 수 없나?"
    "매수심사결과 높은 순위 9 로딩시간 16초 걸린다. 스마트폰 기준이다."

    첫 화면 13.3초가 **전부 야후에서 시세를 받는 시간**이었다. 앱 기억에만 둬서
    온라인이 잠들었다 깨면 통째로 다시 받았다. 실측 — 프로세스를 따로 띄워
    재 보니 테마순위 8.3초 → 1.3초 → 0.5초, 순위 9 는 6.1초 → 2.8초 → 2.0초.
    """

    def test_the_saved_file_lives_under_the_ignored_cache_folder(self):
        """저장소가 공개다(CLAUDE.md 10번). 시세 파일이 올라가면 안 된다."""
        from pathlib import Path
        root = Path(__file__).resolve().parent
        self.assertEqual(j3._DISK_DIR.parent.name, "cache")
        ignored = (root / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("cache/", ignored)

    def test_how_stale_a_saved_file_may_be(self):
        """장중 3분 · 장 마감 뒤 30분. 상하님이 정하신 값이다."""
        self.assertEqual(j3.DISK_FRESH_OPEN_SECONDS, 180.0)
        self.assertEqual(j3.DISK_FRESH_CLOSED_SECONDS, 1800.0)
        with patch.object(j3.us_market_calendar, "session_closed", lambda *a: False):
            self.assertEqual(j3._disk_fresh_seconds(), 180.0)
        with patch.object(j3.us_market_calendar, "session_closed", lambda *a: True):
            self.assertEqual(j3._disk_fresh_seconds(), 1800.0)

    def test_a_stale_file_is_treated_as_missing(self):
        """묵은 파일은 없는 셈 친다 — 옛 시세를 오늘 값처럼 보이면 안 된다."""
        import os, time as _t
        name = "test_stale_probe"
        j3._disk_write(name, {"AAA": None}, "2026-08-26T00:00:00+09:00")
        path = j3._DISK_DIR / f"{name}.pkl"
        try:
            self.assertIsNotNone(j3._disk_read(name), "방금 쓴 것을 못 읽는다")
            old = _t.time() - j3.DISK_FRESH_CLOSED_SECONDS - 60
            os.utime(path, (old, old))
            self.assertIsNone(j3._disk_read(name), "묵은 파일을 그대로 썼다")
        finally:
            path.unlink(missing_ok=True)

    def test_a_broken_file_never_breaks_the_screen(self):
        """파일이 깨져도 조용히 넘어간다 — 화면이 죽으면 안 된다."""
        name = "test_broken_probe"
        j3._DISK_DIR.mkdir(parents=True, exist_ok=True)
        path = j3._DISK_DIR / f"{name}.pkl"
        path.write_bytes("이건 시세가 아니다".encode("utf-8"))
        try:
            self.assertIsNone(j3._disk_read(name))
        finally:
            path.unlink(missing_ok=True)

    def test_the_key_changes_when_the_question_changes(self):
        """묻는 것이 다르면 다른 파일이다 — 딴 종목 시세를 섞으면 안 된다."""
        a = j3._disk_name(("AAA", "BBB"), "2y", "1d", False)
        self.assertEqual(a, j3._disk_name(("AAA", "BBB"), "2y", "1d", False))
        self.assertNotEqual(a, j3._disk_name(("AAA", "CCC"), "2y", "1d", False))
        self.assertNotEqual(a, j3._disk_name(("AAA", "BBB"), "1y", "1d", False))
        self.assertNotEqual(a, j3._disk_name(("AAA", "BBB"), "2y", "5m", False))
        self.assertNotEqual(a, j3._disk_name(("AAA", "BBB"), "2y", "1d", True))

class WarmTopPicksTests(unittest.TestCase):
    """순위 9를 첫 화면 보시는 동안 미리 계산해 둔다 (2026-08-26 상하님 허락).

    상하님 — "매수심사결과 높은순위 9 로딩시간 10초 걸린다. 스마트폰 기준이다."
    "배점이나 딴거 건들이지 마라 - 해라."
    그래서 계산 내용은 손대지 않고 **시작 시점만** 앞당겼다.
    """

    def setUp(self):
        with j3._TOP_PICK_WARM_LOCK:
            j3._TOP_PICK_WARM["on"] = False
            j3._TOP_PICK_WARM["at"] = 0.0

    tearDown = setUp

    def test_the_screen_never_waits_for_it(self):
        """화면은 미리 계산을 기다리지 않는다 — 시키기만 하고 바로 지나간다."""
        import time as _t
        started = {"n": 0}

        def slow(*a, **k):
            started["n"] += 1
            _t.sleep(0.6)
            return {"ok": True, "rows": []}

        with patch.object(j3, "get_theme_rankings", lambda: {"ok": True, "rows": []}),              patch.object(j3, "get_market_overview", lambda: {"score": 65.0}),              patch.object(j3, "collect_top_picks", slow):
            t = _t.time()
            j3.warm_top_picks()
            elapsed = _t.time() - t
            self.assertLess(elapsed, 0.3, "화면이 미리 계산을 기다렸다")
            for _ in range(60):
                if not j3._TOP_PICK_WARM["on"]:
                    break
                _t.sleep(0.05)
        self.assertEqual(started["n"], 1, "뒤에서 한 번은 돌아야 한다")

    def test_it_does_not_run_twice_at_once(self):
        """이미 돌고 있으면 또 시키지 않는다."""
        import time as _t
        started = {"n": 0}

        def slow(*a, **k):
            started["n"] += 1
            _t.sleep(0.5)
            return {"ok": True, "rows": []}

        with patch.object(j3, "get_theme_rankings", lambda: {"ok": True, "rows": []}),              patch.object(j3, "get_market_overview", lambda: {"score": 65.0}),              patch.object(j3, "collect_top_picks", slow):
            j3.warm_top_picks()
            j3.warm_top_picks()
            j3.warm_top_picks()
            for _ in range(60):
                if not j3._TOP_PICK_WARM["on"]:
                    break
                _t.sleep(0.05)
        self.assertEqual(started["n"], 1, "여러 번 겹쳐 돌았다")

    def test_a_failure_never_reaches_the_screen(self):
        """뒤에서 터져도 화면으로 올리지 않는다 — 조용히 넘어간다."""
        import time as _t
        with patch.object(j3, "get_theme_rankings",
                          lambda: (_ for _ in ()).throw(RuntimeError("일부러 낸 실패"))):
            j3.warm_top_picks()          # 예외가 여기까지 오면 시험이 깨진다
            for _ in range(60):
                if not j3._TOP_PICK_WARM["on"]:
                    break
                _t.sleep(0.05)
        self.assertFalse(j3._TOP_PICK_WARM["on"], "실패한 뒤 표시가 안 내려갔다")

    def test_the_nasdaq_history_is_warmed_too(self):
        """나스닥 지수 25년치도 같이 미리 받는다 (2026-08-26 상하님이 "2번" 선택).

        상승장(신고가 눌림매수)만 그 25년치를 쓴다 — 지금 시장이 고점에서 얼마나
        내려와 있는지를 재려는 것이다. 급락 갈래는 안 쓴다. 2026-08-21에 상하님이
        "노트북은 3초, 스마트폰은 43초다" 하신 그 차이의 자리가 여기다. 그때
        warm_market_history 를 만들어 두고 화면에 잇지 않아 아무도 안 부르는 채로
        남아 있었다.
        """
        called = {"n": 0}
        with patch.object(j3, "warm_market_history", lambda: called.__setitem__("n", called["n"] + 1)),              patch.object(j3, "get_theme_rankings", lambda: {"ok": True, "rows": []}),              patch.object(j3, "get_market_overview", lambda: {"score": 65.0}),              patch.object(j3, "collect_top_picks", lambda *a, **k: {"ok": True, "rows": []}):
            j3.warm_top_picks()
            import time as _t
            for _ in range(60):
                if not j3._TOP_PICK_WARM["on"]:
                    break
                _t.sleep(0.05)
        self.assertEqual(called["n"], 1, "나스닥 25년치를 미리 안 받는다")

    def test_the_nasdaq_warm_runs_even_when_the_picks_are_fresh(self):
        """순위 9를 방금 해 뒀어도 나스닥 25년치는 따로 챙긴다."""
        called = {"n": 0}
        with j3._TOP_PICK_WARM_LOCK:
            j3._TOP_PICK_WARM["at"] = time.time()   # 방금 해 둔 것으로 친다
        with patch.object(j3, "warm_market_history", lambda: called.__setitem__("n", called["n"] + 1)):
            j3.warm_top_picks()
        self.assertEqual(called["n"], 1, "순위 9가 최신이면 나스닥까지 건너뛴다")

    def test_the_warm_starts_only_after_the_news_has_arrived(self):
        """미리 계산은 **뉴스가 다 온 뒤에** 시작한다 (2026-08-26 상하님 지적).

        상하님 — "노트북 메인화면 관심종목 로딩이 오래 걸린다."
        "관심종목에 뉴스 전부 다 안 나온다. 뉴스를 불러오는 중이란다."

        제가 이 미리 계산을 화면 그리기 맨 앞에 두었던 탓이다. 파이썬은 한 번에
        한 가지만 계산하므로, 뒤 일꾼이 17초를 쓰는 동안 첫 화면과 뉴스가 밀렸다.
        시장분석 화면은 이 도우미를 안 불러서 멀쩡했다 — 그것이 "시장분석은 잘
        열리는데 관심종목만 느리다"의 까닭이다.
        """
        from pathlib import Path
        page = (Path(__file__).resolve().parent / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        helper = page[page.index("def _warm_after_news("):]
        helper = helper[:helper.index(chr(10) + "def ", 10)]
        self.assertIn("all_ready(keys)", helper, "뉴스가 다 왔는지 안 본다")
        self.assertIn('getattr(j3data, "warm_top_picks", None)', helper,
                      "옛 모듈에서 죽지 않게 getattr 로 불러야 한다")
        self.assertIn("callable(warm)", helper)
        # 화면 **맨 앞**에서는 절대 부르지 않는다.
        head = page[page.index("def _render_stock_briefing()"):]
        head = head[:head.index("_briefing_css()")]
        self.assertNotIn("warm_top_picks", head, "화면 맨 앞에서 미리 계산을 시작한다")
        # 뉴스 예약 **뒤에** 불러야 한다.
        home = page[page.index("def _render_stock_briefing()"):]
        home = home[:home.index("def main()")]
        self.assertLess(home.index("_schedule_briefing_news_refresh(news_keys)"),
                        home.index("_warm_after_news(news_keys)"),
                        "뉴스 예약보다 먼저 미리 계산을 시작한다")

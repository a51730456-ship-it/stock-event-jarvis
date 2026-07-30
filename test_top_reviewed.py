"""'매수 심사 결과 높은 순위 7' 자료 함수 (2026-07-30 사용자 지시).

전수 검색을 새로 돌리지 않고, 이미 있는 테마 대장주 + 눌림목 결과만 모아
종목 조건점수 하나로 줄 세운다. 순위 기준이 둘이 되면 표를 못 읽으므로
'점수 하나'라는 규칙을 여기서 붙잡는다.
"""

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

    def test_both_pages_show_the_section(self):
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            self.assertIn("매수심사결과 높은 순위 7", source, f"{market} 화면에 제목이 없다")
            self.assertIn("def _render_top_reviewed(", source, f"{market}에 그리는 함수가 없다")
            self.assertIn("_render_top_reviewed(market, ranking)", source,
                          f"{market}에서 부르지 않는다")
            self.assertIn("find_top_reviewed_stocks(", source, f"{market}가 자료를 안 부른다")
            # 눌림목 결과도 함께 넣어야 한다(사용자 지시).
            self.assertIn(f"{prefix}_pullback_result", source)
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
            self.assertIn(f'"매수심사결과 높은 순위 7", key="{prefix}_top7_find")', source,
                          f"{market} 순위 7 단추가 아직 화면을 가로지른다")
            self.assertIn(f'"눌림목 찾기", key="{prefix}_pullback_find"', source,
                          f"{market} 눌림목 단추가 아직 화면을 가로지른다")
            self.assertNotIn(f'key="{prefix}_pullback_find", width="stretch"', source)

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
            self.assertIn("if run_requested and is_open:", block,
                          f"{market}가 다시 눌러도 안 접힌다")

    def test_reopening_uses_the_saved_result(self):
        """닫았다 다시 열 때 같은 순위를 또 뽑느라 시간을 다시 냈다.

        2026-07-30 폰 실측(미국테마): 열기 8초 · 닫기 3초 · 다시 열기 8초.
        시세 캐시가 45초라 사람이 표를 보고 닫고 다시 누르면 이미 만료돼 처음부터
        다시 받았다. 이제 뽑아 둔 것이 있으면 조회 없이 그대로 편다.
        """
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            block = source.split("def _render_top_reviewed(")[1].split("\ndef ")[0]
            self.assertIn(f'"새로 뽑기", key="{prefix}_top7_refind"', block,
                          f"{market}에 '새로 뽑기' 단추가 없다")
            reopen = block.split(
                f'if run_requested and st.session_state.get("{prefix}_top7_result") is not None:'
            )[1].split("\n    if ")[0]
            self.assertNotIn("find_top_reviewed_stocks", reopen,
                             f"{market}가 다시 열 때도 새로 뽑는다")
            self.assertIn(f'"{prefix}_top7_open"] = True', reopen,
                          f"{market}가 저장된 결과로 펴지지 않는다")
            # 언제 뽑은 것인지 화면에 남아야 한다 — 오래된 순위를 지금 것으로 보면 안 된다.
            self.assertIn(f'"{prefix}_top7_found_at"', block,
                          f"{market}에 뽑은 시각이 없다")

    def test_phone_rules_exist_and_live_in_mobile_ui(self):
        """폰에서 한 종목이 여섯 줄로 쌓였다(2026-07-30 캡처).

        규칙 12 — 폰 규칙은 mobile_ui.py 폰 묶음 안에만 둔다. 페이지는 칸 번호만 넘긴다.
        """
        import pathlib

        import mobile_ui

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            self.assertIn(f'mobile_ui.table_css(\n                "{prefix}top7_", 6,', source,
                          f"{market}에 폰 표 규칙이 없다")
            self.assertIn(f'hide_own_header("{prefix}_top7_table", "{prefix}top7_")', source,
                          f"{market} 머리글이 폰에서 여섯 줄로 남는다")
            # 폰 규칙을 페이지에 직접 쓰면 안 된다.
            self.assertNotIn("max-width: 600px", source, f"{market}에 폰 규칙이 새어 나왔다")

        # 이 표 머리글만 감춰야 한다 — 클래스로 감추면 눌림목 머리글까지 사라진다.
        rule = mobile_ui.hide_own_header("j4_top7_table", "j4top7_")
        self.assertIn("st-key-j4_top7_table", rule)
        self.assertIn(":not(:has(", rule)
        self.assertNotIn("j4-th-head", rule)

    def test_closing_does_no_work(self):
        """닫는 데 5초가 걸렸다(2026-07-30 사용자 실측).

        닫을 때 조회를 돌리거나 st.rerun()을 부르면 화면을 통째로 다시 그린다.
        닫기는 값만 바꾸고 끝나야 한다.
        """
        import pathlib

        for market, (path, prefix) in self.PAGES.items():
            source = pathlib.Path(path).read_text(encoding="utf-8")
            block = source.split("def _render_top_reviewed(")[1].split("\ndef ")[0]
            close = block.split("if run_requested and is_open:")[1].split("\n    if ")[0]
            self.assertNotIn("st.rerun()", close, f"{market}가 닫을 때 다시 그린다")
            self.assertNotIn("find_top_reviewed_stocks", close,
                             f"{market}가 닫을 때도 조회한다")
            # 조회는 마지막 '뽑는 쪽' 갈래에만 있어야 한다.
            run = block.split("\n    if run_requested:\n")[1]
            self.assertIn("find_top_reviewed_stocks", run,
                          f"{market}에서 뽑는 자리가 사라졌다")

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
            block = source.split("def _render_pullback_finder(")[1].split("\ndef ")[0]
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

        def fake_leaders(theme_name, market_score=0, theme_score=0, with_charts=True):
            seen_charts.append(with_charts)
            score = 91.0 if theme_name == "반도체" else 64.0
            return {"ok": True, "rows": [_us_leader("NVDA", score), _us_leader("AMD", 55.0)]}

        with patch.object(j3, "get_theme_leaders", side_effect=fake_leaders):
            result = j3.find_top_reviewed_stocks(themes, market_score=60)

        self.assertEqual(["NVDA", "AMD"], [row["ticker"] for row in result["rows"]])
        self.assertEqual(91.0, result["rows"][0]["score"])
        self.assertEqual(["AI", "반도체"], sorted(result["rows"][0]["sources"]))
        # 표만 그리는 자리라 차트 자료는 만들지 않는다(2026-07-30 속도).
        self.assertEqual([False, False], seen_charts)

    def test_limit_is_seven_by_default(self):
        self.assertEqual(7, j3.TOP_REVIEW_LIMIT)
        self.assertEqual(7, j4.TOP_REVIEW_LIMIT)


if __name__ == "__main__":
    unittest.main()

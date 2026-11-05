"""자비스13 화면 글이 스트림릿에서 깨지지 않는지 (2026-11-05 상하님 「너 사기쳤네」 · 「다른 부분도 검토하고 똑똑하게」).

세부사항 상자 셋이 화면에 0개였다 — 꾸밈 덩이를 다른 글 뒤에 붙여 한 번에 내보냈기 때문이다. 시험은 글 안에 그 말이 있는지만
봐서 못 잡았다. 그래서 여러 화면 상태를 띄워 **스트림릿이 읽는 규칙 그대로**(research/j13_render_audit.markdown_problems) 모든 글을 읽어 본다.
  · 물결표 둘 → 취소선(「40~60% … 3~5일」 · 2026-11-05 실제로 그려 확인) · 꾸밈 덩이 안 닫힘 · 네 칸 들여쓰기 → 코드 상자
  · 알림 상자 · 단추 이름처럼 HTML 을 못 쓰는 자리의 태그
「📘 이 테마 설명」 창(만화 · 엑셀표 · 캡처)은 건드리지 않는 자리라 이 시험이 안 띄운다(CLAUDE.md 말하는 법).
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

import jarvis13_watch_store as store
import test_jarvis13_page as page_test

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("j13_render_audit", ROOT / "research" / "j13_render_audit.py")
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)

DAYS = pd.bdate_range("2026-08-01", periods=80)


def _frame(start=100_000.0, step=500.0):
    closes = [start + i * step for i in range(len(DAYS))]
    return pd.DataFrame({"Open": closes, "High": [c * 1.01 for c in closes], "Low": [c * 0.99 for c in closes],
                         "Close": closes, "Volume": 1.0e6}, index=DAYS)


def _crash_result():
    row = {"code": "034020", "name": "두산에너빌리티", "themes": ["풍력에너지", "원자력발전"], "together_theme": "풍력에너지",
           "bucket": "deep", "bucket_label": "고점 대비 -40~-60%", "hold_days": 20, "pullback_rank": 1,
           "judged_from_high_pct": -58.55, "since_reference_pct": -8.0, "reference_date": "2026-10-20",
           "now_from_high_pct": -61.85, "partner5": 0, "liquidity_value": 1.0e11, "rule_score": 40.0, "score": 70.0,
           "metrics": {"current": 53100.0, "change_pct": 0.0, "from_high_pct": -61.85, "avg_trading_value": 1.0e11}}
    return {"ok": True, "rows": [row], "rules": [{"key": "deep", "label": "고점 대비 -40~-60%", "hold_days": 20}],
            "bucket_counts": {"deep": 1}, "universe_count": 1, "liquid_count": 1, "scanned_count": 1,
            "screened_count": 1, "result_limit": 20}


def _breakout_result():
    row = {"code": "000660", "name": "SK하이닉스", "themes": ["반도체/HBM"], "together_theme": "반도체/HBM", "wait_days": 4,
           "pullback_rank": 1, "partner5": 2, "liquidity_value": 2.0e12, "rule_score": 30.0, "score": 80.0,
           "metrics": {"current": 590000.0, "change_pct": 1.2, "from_high_pct": -5.0, "avg_trading_value": 1.5e12,
                       "ret60": 22.0}}
    rule = {"wait_days": (3, 5), "drop_band": (-6.0, -4.0), "liquidity_floor": 5.0e9, "hold_days": 250, "win_rate": 52,
            "base_win_rate": 48, "years_better": 9, "years_total": 12, "median_return": -1.2, "sample": 1234,
            "base_median_return": -3.4, "windows_won": 100}
    return {"ok": True, "rows": [row], "rule": rule, "universe_count": 1, "liquid_count": 1, "scanned_count": 1,
            "screened_count": 1, "result_limit": 20}


# (이름, 세션 값, 누를 단추 열쇠)
STATES = (
    ("시장분석", {}, None),
    ("시장분석 · 세부사항 다 펼침", {"__details__": True}, None),
    ("테마 순위표", {"j13_theme_rank_open": True}, None),
    ("파트별 성적표", {"j13sc_open": True}, None),
    ("상승장 · 설명", {"j13_pullback_open": True, "j13_pullback_mode": "breakout", "j13_rulebook_help_open": True,
                    "j13_pullback_result": "__breakout__"}, None),
    ("급락 · 설명", {"j13_pullback_open": True, "j13_pullback_mode": "crash", "j13_rulebook_help_open": True,
                  "j13_pullback_result": "__crash__"}, None),
    ("매수 기록 현황", {"j13_section": "매수 기록 현황"}, None),
    ("판정 기준", {"j13_section": "판정 기준"}, None),
    ("관심종목", {"j13_briefing_page": "watch"}, None),
    ("관심종목 · 세부사항", {"j13_briefing_page": "watch"}, "j13h_wdgo_005930"),
    # 2026-11-05 상하님 「관심종목에서 클릭해도 나와야겠지? 미국테마처럼 · 다하고」 — 종목을 누르는 나머지 자리
    ("종목검색 · 세부사항", {"j13_my_stock_query": "삼성"}, None),
    ("날짜별 목록 · 고른 종목", {"__picklist__": ("034020", "두산에너빌리티")}, None),
    ("날짜별 목록 · 오늘 없는 종목", {"__picklist__": ("005930", "삼성전자")}, None),
)


def run_states(states=STATES):
    """화면 상태마다 시험 자료로 띄운 판을 돌려준다(research/j13_render_audit 도 같이 쓴다)."""
    import shutil

    import jarvis13_picklist_ui
    import picklist_store

    with ExitStack() as stack, tempfile.TemporaryDirectory() as folder:
        archive = Path(folder) / "picklist"            # 날짜별 목록 — 진짜 10/30 한국 한 날치(conftest 는 빈 폴더로 돌려 둔다)
        archive.mkdir()
        shutil.copy(ROOT / "data" / "picklist" / "2026-10-30.KR.csv", archive / "2026-10-30.KR.csv")
        found = {"ok": True, "rows": [{"code": "005930", "name": "삼성전자", "market": "KOSPI"}]}
        for item in list(page_test._patches()) + [
            patch("jarvis4_data.get_daily_frame", return_value=_frame()),
            patch("jarvis13_market.index_frame", return_value=_frame(2_000, 10)),
            patch("jarvis4_data.search_stocks", return_value=found),
            patch("jarvis4_data.find_crash_rebound_stocks", return_value=_crash_result()),
            patch.object(picklist_store, "ARCHIVE_DIR", archive),
            patch.object(store, "DB_PATH", Path(folder) / "watch.sqlite3"),
        ]:
            stack.enter_context(item)
        store._READY = False
        store._forget()
        store.add("005930", "삼성전자", price=100_000, kospi=2_300)
        store.add("000660", "SK하이닉스", price=500_000, kospi=2_300, group="extra")
        try:
            for name, values, press in states:
                app = AppTest.from_file(str(page_test.PAGE), default_timeout=180)
                app.secrets["APP_PASSWORD"] = "test"
                app.session_state["authenticated"] = True
                for key, value in values.items():
                    if key == "__details__":
                        page_test._open_all_details(app)
                        continue
                    if key == "__picklist__":
                        pick_code, pick_name = value
                        app.session_state[jarvis13_picklist_ui.open_key("KR")] = True
                        app.session_state[jarvis13_picklist_ui.pick_key("KR")] = {
                            "code": pick_code, "name": pick_name, "kind": "crash",
                            "row": {"code": pick_code, "name": pick_name, "score": "32.5", "themes": "원자력발전 · 전력설비"}}
                        continue
                    if value == "__crash__":
                        value = _crash_result()
                    elif value == "__breakout__":
                        value = _breakout_result()
                    app.session_state[key] = value
                app.run(timeout=180)
                if press:
                    button = next((b for b in app.button if b.key == press), None)
                    if button is not None:
                        button.click()
                        app.run(timeout=180)
                yield name, app
        finally:
            store._READY = False
            store._forget()


class RenderAuditRuleTests(unittest.TestCase):
    """검사기 자체 — 이번에 실제로 깨졌던 글을 잡고, 고친 글은 통과시킨다."""

    def test_catches_the_zero_box_bug_and_passes_the_fix(self):
        import jarvis13_fundamentals as fn

        css_then_html = fn.OVERVIEW_CSS + "<div class='j13ov'>개요</div>" + fn.STREET_CSS + "<div class='j13st'>상자</div>"
        self.assertTrue(any("줄 가운데서 열려" in p for p in audit.markdown_problems(css_then_html)))
        self.assertEqual([], audit.markdown_problems(fn.STREET_CSS + "<div class='j13st'>상자</div>"))

    def test_tilde_pairs_strike_through_outside_html_only(self):
        self.assertTrue(audit.markdown_problems("40~60% 빠진 종목 → 3~5일 보유"))
        self.assertEqual([], audit.markdown_problems("<div>40~60% 빠진 종목 → 3~5일 보유</div>"))
        self.assertEqual([], audit.markdown_problems("40\\~60% 빠진 종목 → 3\\~5일 보유"))      # 막은 물결표
        self.assertEqual([], audit.markdown_problems("3 ~ 5일 · 7 ~ 9일"))                  # 띄운 물결표는 안 긋는다
        self.assertTrue(audit.markdown_problems("알림 40~60% 그리고 3~5일", allow_html=False))

    def test_style_inside_style_comment_is_not_counted(self):
        # 관심종목 꾸밈 주석 속 「<style data-j3-open>」 — 꾸밈 안의 글이라 괜찮다(2026-11-05 브라우저로 그려 확인)
        self.assertEqual([], audit.markdown_problems("<style>\n/* (<style data-j3-open>) 안으로 옮김 */\n.a{color:red}\n</style>"))
        self.assertTrue(audit.markdown_problems("<style>\n.a{color:red}\n</style><style>\n.b{color:blue}\n</style>"))
        self.assertEqual([], audit.markdown_problems("<style>\n.a{color:red}\n</style><style>.b{color:blue}</style><div>x</div>"))

    def test_two_dollar_signs_become_math(self):
        # 2026-11-05 실제로 그려 확인 — 「값 $10.75 그리고 $8.90」 사이가 회색 수식 상자로 나옴
        self.assertTrue(audit.markdown_problems("값 $10.75 그리고 $8.90 끝"))
        self.assertEqual([], audit.markdown_problems("<div>값 $10.75 그리고 $8.90 끝</div>"))
        self.assertEqual([], audit.markdown_problems("값 \\$10.75 그리고 \\$8.90 끝"))

    def test_tags_in_plain_widgets_and_indented_lines(self):
        self.assertTrue(audit.markdown_problems("<b>굵게</b>", allow_html=False))
        self.assertTrue(audit.markdown_problems("글\n\n    들여 쓴 줄"))


class RenderAuditPageTests(unittest.TestCase):
    """자비스13 여러 화면 상태 — 깨지는 글이 하나도 없어야 한다."""

    def test_no_broken_text_on_any_screen(self):
        found = []
        seen = set()
        for state, app in run_states():
            self.assertEqual(0, len(app.exception), (state, [e.value for e in app.exception]))
            for kind, text, allow_html in audit._texts(app):
                for problem in audit.markdown_problems(text, allow_html=allow_html):
                    item = (kind, problem)
                    if item not in seen:
                        seen.add(item)
                        found.append(f"[{state}] {kind} · {problem}")
        self.assertEqual([], found, "\n".join(found))

    def test_every_state_actually_opened(self):
        # 상태를 못 띄우면 검사가 빈 판만 보고 통과한다 — 열린 표시를 하나씩 본다
        marks = {"시장분석 · 세부사항 다 펼침": "j13st-box", "급락 · 설명": "낙폭 칸 셋",
                 "관심종목": "사용자 선정 종목", "관심종목 · 세부사항": "st-key-j13w_pane",
                 "종목검색 · 세부사항": "j13st-box", "날짜별 목록 · 고른 종목": "저장해 둔 목록에서 고른 종목 · 두산에너빌리티",
                 "날짜별 목록 · 오늘 없는 종목": "저장해 둔 목록 · 급락 후 반등장"}
        opened = {}
        for state, app in run_states(tuple(s for s in STATES if s[0] in marks)):
            opened[state] = marks[state] in " ".join(str(m.value) for m in app.markdown)
        self.assertEqual({state: True for state in marks}, opened)


if __name__ == "__main__":
    unittest.main()

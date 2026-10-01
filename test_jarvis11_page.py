"""자비스11 — 자비스3 미국테마를 베끼고 안 쓰는 코드만 뺀 화면 (2026-10-01 상하님 지시).

상하님 — *"필요없는 코드는 다 버리고 지금 있는 것 그대로 다 가져간다."*

그래서 이 시험의 중심은 **두 화면을 같은 가짜 자료로 그려, 보이는 글과 단추가 똑같은지** 견주는 것이다.
꾸밈(<style>)과 움직임 코드(손가락 넘기기)는 일부러 줄였으므로 견주지 않는다 — 그 대신 넘기기가
자비스3 과 한 탭에서 섞이지 않게 바꾼 이름을 따로 본다.
"""

import re
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import test_jarvis3_page as j3t

ROOT = Path(__file__).parent
J3 = ROOT / "pages" / "2_자비스3.py"
J11 = ROOT / "pages" / "10_자비스11.py"


def _same_words(value: str) -> str:
    """자비스11 이 일부러 바꾼 글자(화면 표식·제목 숫자)와 시각을 맞춰 둔다."""
    value = (value.replace("j11b-home", "j3b-home").replace("j11-market-top", "j3-market-top")
             .replace("JARVIS <b>11</b>", "JARVIS <b>3</b>"))
    return re.sub(r"\d{1,2}:\d{2}(:\d{2})?", "HH:MM", value)


def _visible(app):
    texts = [_same_words(str(node.value)) for node in app.markdown if "<style" not in str(node.value)]
    buttons = [(str(node.key), str(node.label)) for node in app.button]
    return texts, buttons


def _run_market(page: Path):
    with patch("jarvis3_data.get_market_overview", return_value=j3t._market()), \
         patch("jarvis3_data.get_fear_greed", return_value=j3t._fear_greed()), \
         patch("market_signal_ui._fetch_quotes", return_value={}), \
         patch("jarvis3_data.get_theme_rankings", return_value=j3t._ranking()), \
         patch("jarvis3_data.get_theme_leaders", return_value=j3t._leaders()), \
         patch("jarvis3_data.get_live_quote", return_value={
             "ok": True, "current": 179.0, "change_pct": 1.0, "from_high_pct": -1.0,
             "ret20": 7.0, "atr_pct": 3.0, "source_time": "x", "stale": False,
         }), \
         patch("jarvis3_data.get_chart_bundle", return_value=j3t._chart_bundle()), \
         patch("jarvis3_data.find_pullback_stocks", return_value=j3t._pullbacks()), \
         patch("jarvis3_data.find_breakout_pullback_stocks", return_value=j3t._breakout_result(2)), \
         patch("jarvis3_store.ensure_tables"), \
         patch("jarvis3_store.trade_progress", return_value={
             "total_count": 0, "open_count": 0, "closed_count": 0, "minimum_sample": 30,
         }), \
         patch("jarvis3_store.list_trades", return_value=j3t._sample_trades()):
        app = AppTest.from_file(str(page), default_timeout=60)
        app.secrets["APP_PASSWORD"] = "test"
        app.session_state["authenticated"] = True
        j3t._open_all_details(app)
        app.run(timeout=60)
        next(node for node in app.button if str(node.key or "") == "j3_pullback_breakout").click().run(timeout=60)
        next(node for node in app.button if str(node.key or "") == "j3rbf_00").click().run(timeout=60)
    return app


def _run_home(page: Path):
    stocks = {
        "selected": [
            {"position": 1, "ticker": "NVDA", "name": "NVIDIA"},
            {"position": 2, "ticker": "TSLA", "name": "Tesla"},
            {"position": 3, "ticker": "PLTR", "name": "Palantir"},
            {"position": 4, "ticker": "AMD", "name": "AMD"},
        ], "extra": [],
    }
    cards = {ticker: {"ticker": ticker, "name": ticker, "price": 100.0,
                      "change_pct": 1.0, "chart": [90, 95, 100], "stale": False}
             for ticker in ("NVDA", "TSLA", "PLTR", "AMD")}
    with patch("jarvis3_briefing_store.ensure_tables"), \
         patch("jarvis3_briefing_store.ensure_default_extras"), \
         patch("jarvis3_briefing_store.all_stocks", return_value=stocks), \
         patch("jarvis3_data.get_briefing_cards", return_value=cards), \
         patch("jarvis3_briefing_news.get_or_schedule", return_value={"ok": True, "items": []}):
        app = AppTest.from_file(str(page), default_timeout=30)
        app.secrets["APP_PASSWORD"] = "test"
        app.session_state["authenticated"] = True
        app.session_state["jarvis_access_role"] = "owner"
        app.run(timeout=30)
    return app


class SameScreenTests(unittest.TestCase):
    def test_market_screen_shows_the_same_words_and_buttons(self):
        # **한 번씩 먼저 그려 둔다.** 업종 지도·저장 목록 시세는 뒤 일꾼이 채우는 공책을 읽어서,
        # 먼저 돈 쪽은 비어 있고 뒤에 돈 쪽만 차 있다(차례 탓이지 코드 탓이 아니다 — 2026-10-01 실측).
        _run_market(J3), _run_market(J11)
        j3, j11 = _run_market(J3), _run_market(J11)
        self.assertEqual(len(j3.exception), 0)
        self.assertEqual(len(j11.exception), 0, [str(e.value) for e in j11.exception])
        a, b = _visible(j3), _visible(j11)
        self.assertGreater(len(a[0]), 20, "견줄 글이 너무 적다 — 화면이 덜 그려졌다")
        self.assertEqual(a[1], b[1], "단추가 다르다")
        self.assertEqual(len(a[0]), len(b[0]), "보이는 글 조각 수가 다르다")
        for left, right in zip(a[0], b[0]):
            self.assertEqual(left, right)

    def test_watch_screen_shows_the_same_words_and_buttons(self):
        j3, j11 = _run_home(J3), _run_home(J11)
        self.assertEqual(len(j3.exception), 0)
        self.assertEqual(len(j11.exception), 0, [str(e.value) for e in j11.exception])
        a, b = _visible(j3), _visible(j11)
        self.assertTrue(any("NVDA" in text for text in b[0]))
        self.assertEqual(a, b)


class SourceTests(unittest.TestCase):
    SOURCE = J11.read_text(encoding="utf-8")

    def test_asks_for_the_same_jarvis3_revision(self):
        """계산 모듈 리비전은 자비스3 과 **같은 값**이어야 한다(CLAUDE.md 11번) — 두 화면이 같은 계산을 쓴다."""
        pick = lambda text: re.search(r"^_REQUIRED_J3_REVISION = (\d+)", text, re.M).group(1)
        self.assertEqual(pick(J3.read_text(encoding="utf-8")), pick(self.SOURCE))

    def test_guard_and_title(self):
        self.assertIn('page_access.guard(st, "자비스11")', self.SOURCE)
        self.assertLess(self.SOURCE.index("st.set_page_config("), self.SOURCE.index("page_access.guard(st,"))
        self.assertIn("JARVIS <b>11</b>", self.SOURCE)
        self.assertIn('mark="11"', self.SOURCE)

    def test_finger_turning_does_not_mix_with_jarvis3(self):
        """자비스3 과 한 탭에서 오가도 두 넘기기 코드가 서로의 화면을 제 것으로 알면 안 된다.

        넘기기 코드는 바깥 문서에 한 번 심기면 화면을 옮겨도 남는다. 표식이 같으면 자비스3 코드가
        자비스11 화면에서 사진을 뜨고 홈에서 자비스3 으로 넘긴다.
        """
        for old in ("j3b-home", "j3-market-top", "'j3snap-host'", "'j3page-host'", "'j3curl-host'",
                    "'j3snap:v1:'", "t.id='j3b-swipe-script'"):
            self.assertNotIn(old, self.SOURCE, old)
        for new in ("j11b-home", "j11-market-top", "'j11snap-host'", "'j11page-host'", "'j11curl-host'",
                    "'j11snap:v1:'", "t.id='j11b-swipe-script'", "link: '자비스11'"):
            self.assertIn(new, self.SOURCE, new)
        # 자비스3 넘기기 코드가 이미 이 탭에 있으면 홈은 그쪽에 맡긴다(한 번 밀어 두 곳으로 가지 않게).
        self.assertIn("if (s === 'home' && d.getElementById('j3b-swipe-script')) { return ''; }", self.SOURCE)

    def test_no_explanations_inside_browser_code(self):
        """폰으로 보내는 꾸밈 안에 설명 글(/* … */)을 두지 않는다 — 폰이 받고 읽는 글자만 는다."""
        style_blocks = re.findall(r"<style>(.*?)</style>", self.SOURCE, flags=re.S)
        self.assertGreater(len(style_blocks), 5)
        for block in style_blocks:
            self.assertNotIn("/*", block)


if __name__ == "__main__":
    unittest.main()

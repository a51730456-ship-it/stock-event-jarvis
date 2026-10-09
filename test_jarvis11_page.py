"""자비스11 — 자비스3 미국테마를 베끼고 안 쓰는 코드만 뺀 화면 (2026-10-01 상하님 지시).

상하님 — *"필요없는 코드는 다 버리고 지금 있는 것 그대로 다 가져간다."*

그래서 이 시험의 중심은 **두 화면을 같은 가짜 자료로 그려, 보이는 글과 단추가 똑같은지** 견주는 것이다.
꾸밈(<style>)과 움직임 코드(손가락 넘기기)는 일부러 줄였으므로 견주지 않는다 — 그 대신 넘기기가
자비스3 과 한 탭에서 섞이지 않게 바꾼 이름을 따로 본다.
"""

import contextlib
import re
import tempfile
import time
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


def _slow_rankings(seconds: float):
    """뒤에서 받는 데 시간이 걸리는 테마 순위 — 다 받으면 jarvis3_data 공책에 남긴다(진짜와 같게)."""
    import jarvis3_data

    def produce():
        time.sleep(seconds)
        value = j3t._ranking()
        with jarvis3_data._CACHE_LOCK:
            jarvis3_data._CACHE["us_theme_rankings"] = {"at": time.time(), "value": value}
        return value
    return produce


def _run_market(page: Path, *, cold: bool = False, clicks: bool = True):
    """시장분석을 그린다. cold — 259종목 자료가 앱 기억에도 파일에도 없는 판(자비스11 은 테마를 뒤로 미룬다)."""
    if cold:
        tmp = tempfile.TemporaryDirectory(prefix="j11-empty-")
        theme_patches = (patch.dict("jarvis3_data._CACHE", {}, clear=True),
                         patch("jarvis3_data._DISK_DIR", Path(tmp.name)),
                         patch("jarvis3_data.get_theme_rankings", side_effect=_slow_rankings(1.0)))
    else:
        tmp = None
        theme_patches = (patch.dict("jarvis3_data._CACHE", {"us_theme_rankings": {
                             "at": time.time(), "value": j3t._ranking()}}),
                         patch("jarvis3_data.get_theme_rankings", return_value=j3t._ranking()))
    with contextlib.ExitStack() as stack:
        for item in theme_patches:
            stack.enter_context(item)
        app = _run_market_inner(page, clicks=clicks)
        if cold:
            app.j11_after_wait = None
            time.sleep(1.6)                       # 뒤 일꾼이 다 받기를 기다린 뒤 다시 그린다(지켜보는 조각이 하는 일)
            app.j11_after_wait = _visible(app.run(timeout=60))
            app.j11_after_raw = [str(node.value) for node in app.markdown]
    if tmp is not None:
        tmp.cleanup()
    return app


def _run_market_inner(page: Path, *, clicks: bool):
    with patch("jarvis3_data.get_market_overview", return_value=j3t._market()), \
         patch("jarvis3_data.get_fear_greed", return_value=j3t._fear_greed()), \
         patch("market_signal_ui._fetch_quotes", return_value={}), \
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
        app.j11_first = _visible(app)
        app.j11_first_raw = [str(node.value) for node in app.markdown]
        if clicks:
            next(node for node in app.button if str(node.key or "") == "j3_pullback_breakout").click().run(timeout=60)
            next(node for node in app.button if str(node.key or "") == "j3rbf_00").click().run(timeout=60)
    return app


def _run_home(page: Path, news: dict | None = None):
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
         patch("jarvis3_briefing_news.get_or_schedule",
               return_value=news if news is not None else {"ok": True, "items": []}):
        app = AppTest.from_file(str(page), default_timeout=30)
        app.secrets["APP_PASSWORD"] = "test"
        app.session_state["authenticated"] = True
        app.session_state["jarvis_access_role"] = "owner"
        app.run(timeout=30)
    return app


class SameScreenTests(unittest.TestCase):
    @unittest.skip("2026-10-07 — 자비스3 표(테마 종목·상승장·급락)에 연간·분기 실적 칸을 넣고 자비스11은 그대로 "
                   "둔다(상하님 — 「자비스3 이다 · 자비스11은 지금 실패다」). 두 시장분석 화면이 같다는 시험은 쉰다.")
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

    @unittest.skip("2026-10-09 — 자비스3 관심종목 카드에만 「🔎 선택종목 세부사항 보기」와 세부사항 창(숨은 단추)을 "
                   "넣었다. 자비스11은 그대로 둔다(상하님 — 자비스11은 지우고 다시 베낄 예정).")
    def test_watch_screen_shows_the_same_words_and_buttons(self):
        j3, j11 = _run_home(J3), _run_home(J11)
        self.assertEqual(len(j3.exception), 0)
        self.assertEqual(len(j11.exception), 0, [str(e.value) for e in j11.exception])
        a, b = _visible(j3), _visible(j11)
        self.assertTrue(any("NVDA" in text for text in b[0]))
        self.assertEqual(a, b)


class ThemeLaterTests(unittest.TestCase):
    """259종목 자료를 새로 받아야 하는 판 — 테마 칸만 「받는 중」, 나머지는 먼저 (2026-10-01 상하님 「1」)."""

    def test_rest_of_the_screen_comes_first_and_themes_fill_in(self):
        app = _run_market(J11, cold=True, clicks=False)
        self.assertEqual(len(app.exception), 0, [str(e.value) for e in app.exception])
        texts, buttons = app.j11_first
        keys = {key for key, _label in buttons}
        raw = app.j11_first_raw          # 「받는 중」 칸은 제 꾸밈과 한 덩어리라 꾸밈 든 조각까지 본다
        self.assertTrue(any("class='j11-theme-wait'" in text for text in raw), "「받는 중」 자리가 없다")
        self.assertFalse(any("class='j3-st5" in text or 'class="j3-st5' in text for text in raw),
                         "아직 안 온 테마 카드가 그려졌다")
        # 테마 자료 없이 먼저 그려야 하는 것들
        self.assertIn("j3_pullback_breakout", keys, "상승장 단추가 테마를 기다렸다")
        self.assertIn("j3b_nav_market", keys, "아래 이동막대가 테마를 기다렸다")
        # 다 받은 뒤 다시 그린 판 — 테마 칸이 채워지고 「받는 중」은 사라진다
        after_texts, after_buttons = app.j11_after_wait
        self.assertTrue(any("j3-st5" in text for text in after_texts), "다 받은 뒤에도 테마 카드가 없다")
        self.assertFalse(any("class='j11-theme-wait'" in text for text in app.j11_after_raw))
        self.assertIn("btn_j3_theme_rank_open", {key for key, _label in after_buttons})

    def test_opening_a_stock_while_themes_come_waits_for_them(self):
        """받는 중에 종목 상세를 열면 그 상세는 다 올 때까지 기다린다 — 테마 점수가 빈 채로 나오면 안 된다."""
        app = _run_market(J11, cold=True, clicks=True)
        self.assertEqual(len(app.exception), 0, [str(e.value) for e in app.exception])
        ranking = app.session_state["j3_theme_rankings"]
        self.assertTrue(ranking.get("ok"), ranking)
        self.assertFalse(ranking.get("pending"))
        markdowns = [str(node.value) for node in app.markdown]
        self.assertTrue(any("종목 선정 근거" in value and "j3-section-title" in value and "<style" not in value
                            for value in markdowns), "상세가 안 그려졌다")

    def test_ready_data_draws_exactly_like_jarvis3(self):
        """자료가 이미 있으면 기다리지 않는다 — 「받는 중」 자리가 한 번도 안 생긴다."""
        app = _run_market(J11, clicks=False)
        texts, _buttons = app.j11_first
        self.assertFalse(any("class='j11-theme-wait'" in text for text in app.j11_first_raw))
        self.assertTrue(any("j3-st5" in text for text in texts))


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


def _page_function(name: str, **namespace):
    """자비스11 화면 파일에서 함수 하나만 꺼내 돌려 본다(화면 전체를 띄우지 않고)."""
    import ast

    tree = ast.parse(J11.read_text(encoding="utf-8"))
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name)
    module = ast.Module(body=[node], type_ignores=[])
    exec(compile(module, str(J11), "exec"), namespace)
    return namespace[name]


class NewsRedrawTests(unittest.TestCase):
    """관심종목 뉴스 — 한 자리 올 때마다 판 전체를 다시 그리지 않는다 (2026-10-01 상하님 「2」).

    옛 뉴스를 새것으로 바꾸는 자리는 다 오면 한 번에. 「불러오는 중」 빈칸은 그때그때 채운다
    (2026-08-26 상하님 — 시장 브리핑·사용자 선정 종목을 빈칸으로 두면 안 된다) — 시장 브리핑은 곧바로,
    종목 뉴스는 8초에 한 번까지 모아서.
    """

    def setUp(self):
        self.redraw = _page_function("_news_redraw_now", _NEWS_REDRAW_GAP_SECONDS=8.0)

    def test_old_news_being_refreshed_waits_for_all(self):
        self.assertFalse(self.redraw(5, 11, False, [], 0.0, 100.0))
        self.assertTrue(self.redraw(11, 11, False, [], 0.0, 100.0))

    def test_blank_market_briefing_fills_at_once(self):
        self.assertTrue(self.redraw(1, 11, False, [("market", None)], 99.0, 100.0))

    def test_blank_stock_news_is_gathered_every_eight_seconds(self):
        filled = [("company", "NVDA")]
        self.assertFalse(self.redraw(3, 11, False, filled, 95.0, 100.0))
        self.assertTrue(self.redraw(3, 11, False, filled, 91.0, 100.0))
        self.assertTrue(self.redraw(3, 11, False, filled, 0.0, 100.0), "처음 채우는 것은 기다리지 않는다")

    def test_too_long_wait_draws_anyway(self):
        self.assertTrue(self.redraw(3, 11, True, [], 99.0, 100.0))

    def test_article_bodies_are_drawn_once_when_all_arrive(self):
        """기사 본문은 다 오면 한 번에(2026-10-01 상하님 「다 오면 한 번에」) — 끝내 안 오는 것은 45초에서 끊는다."""
        decide = _page_function("_article_batch_decision", _ARTICLE_BATCH_SECONDS=45.0)
        self.assertEqual("wait", decide(20, 5, 10.0), "아직 다섯 개가 안 왔으면 안 그린다")
        self.assertEqual("redraw", decide(20, 0, 10.0), "다 오면 곧바로 한 번")
        self.assertEqual("redraw", decide(20, 3, 45.0), "45초가 되면 온 만큼 한 번에")
        self.assertEqual("stop", decide(20, 20, 45.0), "하나도 안 왔으면 헛그리지 않고 그만 본다")

    def test_blank_spots_are_remembered_only_when_nothing_to_show(self):
        blank_run = _run_home(J11, {"ok": True, "items": [], "pending": True})
        self.assertEqual(len(blank_run.exception), 0)
        blank = blank_run.session_state["j11_news_blank"]
        self.assertIn(("market", None), blank)
        self.assertIn(("company", "NVDA"), blank)
        old_news = {"ok": True, "pending": True, "items": [
            {"sentiment": "neutral", "brief": "옛 뉴스", "headline": "old", "url": "https://example.test/a"}]}
        refresh_run = _run_home(J11, old_news)
        self.assertEqual(len(refresh_run.exception), 0)
        self.assertEqual([], refresh_run.session_state["j11_news_blank"],
                         "옛 뉴스를 보여 주는 자리는 빈칸이 아니다")


if __name__ == "__main__":
    unittest.main()

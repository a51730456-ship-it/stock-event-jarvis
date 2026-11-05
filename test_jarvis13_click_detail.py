"""한국테마 어디서 종목을 눌러도 세부사항(상자 셋 포함)이 열리는지 (2026-11-05 상하님 「한국테마 모든 파트에서 종목 클릭하면 캡처
화면처럼 할 수 없나?」 · 「관심종목에서 클릭해도 나와야겠지? 미국테마처럼 · 다하고」).

  · 관심종목 — 큰 카드의 「🔎」 → 판 위를 덮는 창(자비스12 와 같은 짜임 · 배점 없음) · 닫으면 창만 닫힌다
  · 종목검색 — 고르면 곧바로 세부사항이 열린다(한 번 더 누르지 않는다)
  · 날짜별 목록 — 종목명을 누르면 그 줄이 나온 파트의 오늘 목록에서 찾아 연다 · 오늘 없으면 그렇다고 적고 배점 없이 연다
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import jarvis13_picklist_ui
import jarvis13_watch_store as store
import test_jarvis13_page as page_test
from test_jarvis13_render_audit import _crash_result, _frame
from test_jarvis13_watch import _temp_store


class ClickDetailTests(unittest.TestCase):
    def _app(self, *, page=None, stocks=(), state=None, extra=()):
        _temp_store(self)
        for code, name in stocks:
            store.add(code, name, price=100_000, kospi=2_300)
        started = []
        for item in list(page_test._patches()) + [
            patch("jarvis4_data.get_daily_frame", return_value=_frame()),
            patch("jarvis13_market.index_frame", return_value=_frame(2_000, 10)),
            *extra,
        ]:
            item.start()
            started.append(item)
        self.addCleanup(lambda: [item.stop() for item in reversed(started)])
        app = AppTest.from_file(str(page_test.PAGE), default_timeout=180)
        app.secrets["APP_PASSWORD"] = "test"
        app.session_state["authenticated"] = True
        if page:
            app.session_state["j13_briefing_page"] = page
        for key, value in (state or {}).items():
            app.session_state[key] = value
        app.run(timeout=180)
        self.assertEqual(0, len(app.exception), [e.value for e in app.exception])
        return app

    @staticmethod
    def _text(app) -> str:
        return " ".join(str(m.value) for m in app.markdown)

    def _press(self, app, key):
        next(button for button in app.button if button.key == key).click()
        app.run(timeout=180)
        self.assertEqual(0, len(app.exception), [e.value for e in app.exception])

    # ── 관심종목 ──────────────────────────────────────────────────────────────────────────────────────────
    def test_watch_card_opens_a_pane_like_jarvis12_and_closes(self):
        app = self._app(page="watch", stocks=[("005930", "삼성전자")])
        self.assertNotIn("j13w_close_top", {b.key for b in app.button})        # 누르기 전에는 창이 없다
        self._press(app, "j13h_wdgo_005930")
        text = self._text(app)
        keys = {b.key for b in app.button}
        self.assertTrue({"j13w_close_top", "j13w_close_bottom"} <= keys, keys)
        self.assertIn("div.st-key-j13w_pane{position:fixed", text)             # 판 위를 덮는 창
        self.assertIn("j13st-box", text)                                        # 상자 셋
        for title in ("📅 실적 발표", "👥 애널리스트 의견", "🔍 공매도 · 내부자 · 배당"):
            self.assertIn(title, text)
        self.assertIn("배점·매수 심사는 파트마다 자가 달라", text)               # 자비스12 처럼 배점 없음
        self.assertNotIn("j13_buyform_open_watch", {b.key for b in app.button if b.key} | set())
        self._press(app, "j13w_close_top")
        self.assertNotIn("j13w_close_top", {b.key for b in app.button})        # 창만 닫힌다
        self.assertIn("j13h_wdgo_005930", {b.key for b in app.button})         # 카드 판은 그대로

    def test_wait_script_waits_for_the_pane_and_keeps_the_card(self):
        import jarvis13_home
        self.assertIn("div.st-key-j13w_pane .j4-stock-name", jarvis13_home.WD_OPEN_JS)
        self.assertNotIn("shell.open = false", jarvis13_home.WD_OPEN_JS)        # 큰 카드는 닫지 않는다(자비스12)

    # ── 종목검색 ──────────────────────────────────────────────────────────────────────────────────────────
    def test_search_opens_the_detail_without_a_second_press(self):
        found = {"ok": True, "rows": [{"code": "005930", "name": "삼성전자", "market": "KOSPI"}]}
        app = self._app(state={"j13_my_stock_query": "삼성"},
                        extra=[patch("jarvis4_data.search_stocks", return_value=found)])
        self.assertTrue(app.session_state["j13_detail_open_mystock"])
        self.assertIn("j13st-box", self._text(app))
        self.assertIn("close_j13_detail_open_mystock", {b.key for b in app.button})

    # ── 날짜별 목록 ──────────────────────────────────────────────────────────────────────────────────────
    def _archive(self):
        """시험용 목록 폴더 — 진짜 10/30 한국 목록 한 날치를 옮겨 둔다(conftest 가 목록 폴더를 빈 임시 폴더로 돌려 둔다)."""
        import shutil
        import tempfile
        from pathlib import Path

        import picklist_store
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        source = Path(__file__).resolve().parent / "data" / "picklist" / "2026-10-30.KR.csv"
        shutil.copy(source, Path(folder.name) / source.name)
        return patch.object(picklist_store, "ARCHIVE_DIR", Path(folder.name))

    def _picklist_state(self, code, name, kind="crash"):
        return {jarvis13_picklist_ui.open_key("KR"): True,
                jarvis13_picklist_ui.pick_key("KR"): {"code": code, "name": name, "kind": kind,
                                                      "row": {"code": code, "name": name, "score": "32.5",
                                                              "themes": "원자력발전 · 전력설비"}}}

    def test_saved_name_opens_that_parts_detail(self):
        app = self._app(state=self._picklist_state("034020", "두산에너빌리티"),
                        extra=[patch("jarvis4_data.find_crash_rebound_stocks", return_value=_crash_result()), self._archive()])
        text = self._text(app)
        self.assertIn("저장해 둔 목록에서 고른 종목 · 두산에너빌리티 · 급락 후 반등장 · 그날 점수 32.5", text)
        self.assertTrue(app.session_state["j13_detail_open_picklist"])
        self.assertIn("j13st-box", text)
        self.assertIn("close_j13_detail_open_picklist", {b.key for b in app.button})

    def test_saved_name_not_in_todays_list_says_so_and_shows_info_only(self):
        app = self._app(state=self._picklist_state("005930", "삼성전자"),
                        extra=[patch("jarvis4_data.find_crash_rebound_stocks", return_value=_crash_result()), self._archive()])
        text = self._text(app)
        self.assertIn("오늘 「급락 후 반등장」 목록에 없습니다", " ".join(str(w.value) for w in app.warning))
        self.assertIn("j13st-box", text)                                        # 배점 없이도 상자 셋은 보인다
        self.assertIn("close_j13_picklist_light", {b.key for b in app.button})
        self._press(app, "close_j13_picklist_light")
        self.assertNotIn(jarvis13_picklist_ui.pick_key("KR"), app.session_state)


if __name__ == "__main__":
    unittest.main()

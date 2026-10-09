"""자비스12 — 자비스3 미국테마를 그대로 베낀 화면 (2026-10-09 상하님 지시)."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
J3 = ROOT / "pages" / "2_자비스3.py"
J12 = ROOT / "pages" / "11_자비스12.py"


class SourceTests(unittest.TestCase):
    SOURCE = J12.read_text(encoding="utf-8")

    def test_asks_for_the_same_jarvis3_revision(self):
        """같은 계산(jarvis3_data)을 부르는 동안은 리비전이 자비스3 과 같아야 한다(CLAUDE.md 11번)."""
        pick = lambda text: re.search(r"^_REQUIRED_J3_REVISION = (\d+)", text, re.M).group(1)
        self.assertEqual(pick(J3.read_text(encoding="utf-8")), pick(self.SOURCE))

    def test_guard_and_title(self):
        self.assertIn('page_access.guard(st, "자비스12")', self.SOURCE)
        self.assertLess(self.SOURCE.index("st.set_page_config("), self.SOURCE.index("page_access.guard(st,"))
        self.assertIn('page_title="자비스12 — 미국테마"', self.SOURCE)
        self.assertIn("JARVIS <b>12</b>", self.SOURCE)
        self.assertIn('mark="12"', self.SOURCE)

    def test_finger_turning_is_gone_but_the_pull_guard_stays(self):
        """2026-10-09 상하님 — 손가락 넘기기를 아예 날려라 · 밑 막대로 옮긴다. 당겨도 안 불리는 장치는 남긴다."""
        for gone in ("_SWIPE_OUTER_JS", "j12b-swipe-script", "j12snap", "j3b_swipe_", "_briefing_slide_in_marker"):
            self.assertNotIn(gone, self.SOURCE, gone)
        for kept in ("_PAGE_GUARD_JS", "'j12b-page-guard'", "if (dy > 0 && Math.abs(dy) > Math.abs(dx)) { ev.preventDefault(); }",
                     "j3-help-closing", 'key="j3b_nav_home"', 'key="j3b_nav_watch"', 'key="j3b_nav_market"'):
            self.assertIn(kept, self.SOURCE, kept)

    def test_fundamentals_sit_right_under_the_street_boxes(self):
        body = self.SOURCE[self.SOURCE.index("def _render_stock_detail("):]
        self.assertLess(body.index("_render_fundamentals_box(ticker, metrics, panel=panel)"),
                        body.index("_render_selected_live_quote("))

    def test_menu_lists_it_and_hides_jarvis10_and_11(self):
        import page_access

        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertTrue(page_access.is_open("자비스12"))
        self.assertFalse(page_access.is_open("한국증시"))
        self.assertFalse(page_access.is_open("자비스11"))
        self.assertIn('"미국테마 (자비스12)": "pages/11_자비스12.py"', app)
        # 「미국테마」 앞부분에 먼저 걸려 자비스3 으로 가면 안 된다 — 자비스12 고리가 앞에 있어야 한다.
        self.assertLess(app.index('"미국테마 (자비스12)": "pages/11_자비스12.py"'),
                        app.index('"미국테마": "pages/2_자비스3.py"'))

    def test_phone_login_card_goes_to_jarvis12_with_the_us_flag(self):
        """로그인 첫 화면 오른쪽 판(폰·태블릿) — 숨긴 한국증시 대신 자비스12(2026-10-09 상하님 「1번으로 해라」)."""
        import login_prism

        page, name, _note, look = login_prism.PHONE_PANELS["KR"]
        self.assertEqual(("pages/11_자비스12.py", "미국테마 (자비스12)", "US"), (page, name, look))
        style = login_prism.panel_style(1, look, key="KRM")
        self.assertIn(login_prism.flag_url("US"), style)            # 한국 국기가 붙은 미국테마 판이 되지 않게
        self.assertIn("_REQUIRED_LOGIN_PRISM_REVISION = 2026100901", self.SOURCE)
        self.assertEqual(2026100901, login_prism.MODULE_REVISION)


if __name__ == "__main__":
    unittest.main()

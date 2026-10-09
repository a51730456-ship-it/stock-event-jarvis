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

    def test_lighter_screens(self):
        """2026-10-10 상하님 「1번 2번 3번 다 해라」 — 화면 무게 줄이기 · 세부 단추는 그 칸만 · 느린 단추 둘."""
        import re as _re
        src = self.SOURCE
        # 꾸밈 글에서 설명 메모·줄바꿈만 뺀다 — 이 화면의 이름 st 만 바꾼다(스트림릿 자체는 그대로)
        self.assertIn("st = _SlimStreamlit()", src)
        part = src.split("import streamlit as _streamlit", 1)[1].split("class _SlimStreamlit", 1)[0]
        ns = {"re": _re}
        exec(part, ns)
        sample = '<style>/* 메모 */\n.a{color:red}\n  /* 두 줄\n 메모 */ .b{content:"x  y"}</style><div>/* 글 */</div>'
        self.assertEqual('<style>.a{color:red} .b{content:"x  y"}</style><div>/* 글 */</div>', ns["_slim_css_text"](sample))
        self.assertEqual("글만", ns["_slim_css_text"]("글만"))
        # 그림은 static/j12asset 주소로 — 파일이 있어야 한다(없으면 예전처럼 글자로 박는다)
        self.assertIn('return f"app/static/j12asset/{served}"', src)
        import hashlib
        for name in ("hero_scene.webp", "hero_catbus_pop.webp", "soot_lamp_cut.webp", "NVDA.svg"):
            data = (ROOT / "assets" / "briefing" / name).read_bytes()
            stem, suffix = name.rsplit(".", 1)
            self.assertTrue((ROOT / "static" / "j12asset" / f"{stem}-{hashlib.sha1(data).hexdigest()[:10]}.{suffix}").is_file(), name)
        # 세부사항 안 단추 셋은 각자 작은 덩이
        for box in ("_day_price_box", "_stock_news_box", "_leader_comparison_box"):
            self.assertIn(f"@st.fragment\ndef {box}(", src)
        self.assertEqual(4, src.count("_day_price_box(metrics, ticker, panel)"))
        self.assertEqual(4, src.count("_stock_news_box(ticker, panel)"))
        # 날짜별 목록 「전부 엑셀」은 누를 때 만든다 · 종목검색 목록은 미리(뒤 일꾼)
        self.assertIn('lazy_slot = _picklist_lazy_all_excel("US")', src)
        self.assertIn("st.session_state.pop(lazy_slot, None)", src)
        self.assertIn("target=j3data._background(j3data._us_listing)", src)
        self.assertIn("_warm_us_listing_later()", src)

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

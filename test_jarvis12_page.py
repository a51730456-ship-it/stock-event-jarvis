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

    def test_finger_turning_does_not_mix_with_jarvis3(self):
        """넘기기 코드는 바깥 문서에 한 번 심기면 화면을 옮겨도 남는다 — 이름표가 같으면 자비스3 코드가
        자비스12 화면을 제 것으로 알고 손가락을 먼저 먹는다(2026-10-01 자비스11 때 실측)."""
        for old in ("j3b-home", "j3-market-top", "'j3snap-host'", "'j3page-host'", "'j3curl-host'",
                    "'j3snap:v1:'", "t.id='j3b-swipe-script'", "ev.__j3seen"):
            self.assertNotIn(old, self.SOURCE, old)
        for new in ("j12b-home", "j12-market-top", "'j12snap-host'", "'j12page-host'", "'j12curl-host'",
                    "'j12snap:v1:'", "t.id='j12b-swipe-script'", "ev.__j12seen", "link: '자비스12'"):
            self.assertIn(new, self.SOURCE, new)

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

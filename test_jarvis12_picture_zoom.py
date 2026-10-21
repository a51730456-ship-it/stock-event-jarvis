"""자비스12 설명 그림 크게 보기 — 새 탭 대신 이 화면 위에 (2026-10-21 상하님 — "노트북에서 이거 클릭했는데 되돌아가는 방법이 없다")."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
J12 = (ROOT / "pages" / "11_자비스12.py").read_text(encoding="utf-8")
J3 = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
ZOOM = J12[J12.index('_PICTURE_ZOOM_JS = """'):J12.index("def _briefing_outer_scripts(")]


class PictureZoomTests(unittest.TestCase):
    def test_installed_with_the_other_outer_scripts_under_a_j12_name(self):
        outer = J12[J12.index("def _briefing_outer_scripts("):J12.index("def _briefing_home_request(")]
        self.assertIn("q.id='j12-picture-zoom'", outer)
        # 페이지 가드보다 앞 — 가드가 이미 심겨 있으면 거기서 끝나므로 그 뒤에 두면 영영 안 심긴다
        self.assertLess(outer.index("j12-picture-zoom"), outer.index("if(d.getElementById('j12b-page-guard')){return;}"))
        self.assertEqual(1, outer.count("components.html("))          # 새 칸을 만들지 않는다

    def test_only_on_jarvis12_and_only_the_explanation_pictures(self):
        # 자비스12 화면일 때만 — 주소에 「자비스12」(글자 번호 uc790 · ube44 · uc2a4 + 12)가 있거나 자비스12 밑 막대 표식
        self.assertRegex(ZOOM, r"indexOf\('\\+uc790\\+ube44\\+uc2a412'\)")
        self.assertIn("d.querySelector('.j12-boot')", ZOOM)
        self.assertIn('div[class*="st-key-jarvis_method_pic"]', ZOOM)
        self.assertIn("ev.preventDefault(); ev.stopPropagation();", ZOOM)
        self.assertIn("}, true);", ZOOM)                              # 새 탭으로 가기 전에 먼저 받는다

    def test_it_closes_four_ways_and_sits_on_top(self):
        for piece in ("j12-pz-close", "ev.key === 'Escape'", "window.addEventListener('popstate', close)",
                      "layer.classList.toggle('j12-pz-full')", "z-index:2147483647!important"):
            self.assertIn(piece, ZOOM)

    def test_jarvis3_is_untouched(self):
        self.assertNotIn("j12-picture-zoom", J3)
        self.assertNotIn("_PICTURE_ZOOM_JS", J3)


if __name__ == "__main__":
    unittest.main()

"""설명 글 — 색 칩 + 「자세히 ▾」 (2026-11-04 상하님 「자비스12 13 다른 모든 설명서도 이해하기 쉽게 · 색깔도 구분해서 ·
전체 내용을 줄여라」). 원래 글은 지우지 않고 접는다(CLAUDE.md 0-1 마 — 재 보고 뺀 것은 설명에 남긴다)."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
J12 = (ROOT / "pages" / "11_자비스12.py").read_text(encoding="utf-8")
J13 = (ROOT / "pages" / "12_자비스13.py").read_text(encoding="utf-8")


class BriefTests(unittest.TestCase):
    def test_chips_and_folded_detail(self):
        import jarvis12_brief
        import jarvis13_brief

        for mod, name, other in ((jarvis13_brief, "j13br", "j12br"), (jarvis12_brief, "j12br", "j13br")):
            out = mod.wrap([("good", "📊 성적", "<b>63번</b>"), ("bad", "⚠", "주의")], "<p>원래 글</p>")
            self.assertIn(f"class='{name}-chip'", out)
            self.assertIn("#44f0a1", out)                       # 초록(좋은 것)
            self.assertIn("#ff7b7b", out)                       # 빨강(주의)
            self.assertIn(f"<details class='{name}-more'><summary>자세히 보기 ▾</summary><p>원래 글</p></details>", out)
            self.assertNotIn(other, out)                        # 자비스12 · 13 이름이 안 섞인다
            self.assertNotIn("<details", mod.wrap([("key", "a", "b")]))   # 원래 글이 없으면 접기도 없다
            self.assertNotIn("@media (max-width: 600px)", mod.CSS)        # 폰 규칙은 mobile_ui 에만

    def test_long_guides_keep_their_text_inside_the_fold(self):
        # 재 보고 뺀 것 · 0점 까닭은 그대로 남아 있다(접혀 있을 뿐)
        for text in ("<b>재 보고 뺀 것</b> — 낙폭 갈래(그물로 이미 한 번 썼습니다)",
                     "<b>재 보고 뺀 것</b> — 거래대금이 평소 위에 며칠 연속인가",
                     "이동평균 위(20점)는 창 107개 중 11개에서만 이겼고"):
            self.assertIn(text, J13)
        self.assertIn("jarvis13_brief.wrap([", J13)
        self.assertIn("⚠ 아직 검증 안 됨", J12)
        self.assertIn("144가지</b>를 3년 창으로 다 재 봤는데", J12)
        self.assertIn("jarvis12_brief.wrap([", J12)
        self.assertNotIn("jarvis12_brief", J13)
        self.assertNotIn("jarvis13_brief", J12)

    def test_method_help_windows_stay_as_they_were(self):
        # 2026-11-04 상하님 「액셀표나 캡쳐해서 올린 것은 건들이지 마라(이 테마 설명서) · 만화 액셀표」
        self.assertIn("        method_help.render_us_body(st)\n", J12)
        self.assertNotIn("_J12_HELP_POINTS", J12)
        self.assertIn("            st.markdown(jarvis13_crash_record.help_text(method_help.KR_TEXT), unsafe_allow_html=True)\n"
                      "            method_help._close_button(st, \"KR\")", J13)
        self.assertNotIn("_J13_HELP_POINTS", J13)

if __name__ == "__main__":
    unittest.main()

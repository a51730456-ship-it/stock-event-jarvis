"""「✕ 자비스 닫기」 (2026-11-04 상하님 「완전 창 닫는 것도 하나 만들자 · ↻ 실시간 왼쪽으로 · X 로고 · 디자인 멋지게」)."""
from __future__ import annotations

import unittest
from pathlib import Path

import jarvis12_exit
import jarvis13_exit

ROOT = Path(__file__).resolve().parent


class ExitButtonTests(unittest.TestCase):
    def test_each_screen_uses_its_own_names_and_banner(self):
        for mod, name, mark in ((jarvis12_exit, "j12", "12"), (jarvis13_exit, "j13", "13")):
            device, css, inject = mod.device(), mod.css(), mod.inject_html()
            self.assertIn(f"MARK = '{mark}'", device)                                # 그 화면 띠에만 붙는다
            self.assertIn(f".{name}x-btn", css)
            self.assertIn(f"'{name}-exit'", inject)
            other = "j13" if name == "j12" else "j12"
            self.assertNotIn(other, device + css + inject)                         # 서로 이름이 안 섞인다

    def test_actions_move_left_by_one_button(self):
        css = jarvis12_exit.css()
        self.assertIn(".j3hero-actions{right:62px!important}", css)              # 16 + 38 + 8
        self.assertIn("right:156px!important", css)                              # 겹친 ↻ 단추도 같이(110 + 46)
        self.assertIn("right:16px;top:14px", css)                                # ✕ 는 원래 ↻·실시간 자리

    def test_click_asks_first_then_exits_app_or_leaves(self):
        device = jarvis12_exit.device()
        for text in ("자비스를 닫을까요?", "계속 보기", "닫기", "JarvisApp.exit()", "window.top.close()", "about:blank"):
            self.assertIn(text, device)
        self.assertLess(device.index("JarvisApp"), device.index("about:blank"))   # 앱이면 앱을 끝내는 것이 먼저

    def test_pages_render_it_and_frozen_banner_untouched(self):
        p12 = (ROOT / "pages" / "11_자비스12.py").read_text(encoding="utf-8")
        p13 = (ROOT / "pages" / "12_자비스13.py").read_text(encoding="utf-8")
        self.assertIn("jarvis12_exit.render(st)", p12)
        self.assertIn("jarvis13_exit.render(st)", p13)
        self.assertNotIn("jarvis12_exit", p13)
        self.assertNotIn("@media (max-width: 600px)", jarvis12_exit.CSS + jarvis13_exit.CSS)


if __name__ == "__main__":
    unittest.main()

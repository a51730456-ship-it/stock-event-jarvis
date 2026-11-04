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
            mixed = (device + css + inject).replace("j13-android/jarvis.apk", "")   # 설치 파일 주소(갈래 이름)는 이름이 아니다
            self.assertNotIn(other, mixed)                                         # 서로 이름이 안 섞인다

    def test_actions_move_left_by_one_button(self):
        css = jarvis12_exit.css()
        self.assertIn(".j3hero-actions{right:62px!important}", css)              # 16 + 38 + 8
        self.assertIn("right:156px!important", css)                              # 겹친 ↻ 단추도 같이(110 + 46)
        self.assertIn("right:16px;top:14px", css)                                # ✕ 는 원래 ↻·실시간 자리

    def test_click_asks_first_then_exits_app_or_says_what_to_do(self):
        device = jarvis12_exit.device()
        for text in ("자비스를 닫을까요?", "계속 보기", "닫기", "JarvisApp.exit()", "window.top.close()",
                     "앱을 새 판으로 바꿔 주십시오", "새 판 받기", "j13-android/jarvis.apk", "이 창은 직접 닫아 주십시오"):
            self.assertIn(text, device)
        self.assertNotIn("about:blank", device)                                   # 빈 화면으로 보내지 않는다(상하님 「황당하게 남아 있냐」)
        self.assertLess(device.index("JarvisApp.exit()"), device.index("function tell()"))   # 앱이면 끄는 것이 먼저

    def test_x_is_not_a_button_tag_so_the_banner_does_not_collapse(self):
        # 2026-11-04 로컬 실측 — <button> 이면 띠 칸이 「↻ 겹치기」 규칙(:has(button))에 걸려 38px 로 접혔다
        for mod, hero, box in ((jarvis12_exit, ".j3b-hero", "j12b_hero_box"), (jarvis13_exit, ".j13h-hero", "j13h_hero_box")):
            device = mod.device()
            self.assertNotIn("createElement('button')", device)
            self.assertIn("setAttribute('role', 'button')", device)
            self.assertIn(hero, device)                                        # 관심종목 띠에도(상하님 「관심종목 띠에도 넣기」)
            self.assertIn(box, device)

    def test_pages_render_it_and_frozen_banner_untouched(self):
        p12 = (ROOT / "pages" / "11_자비스12.py").read_text(encoding="utf-8")
        p13 = (ROOT / "pages" / "12_자비스13.py").read_text(encoding="utf-8")
        self.assertIn("jarvis12_exit.render(st)", p12)
        self.assertIn("jarvis13_exit.render(st)", p13)
        self.assertNotIn("jarvis12_exit", p13)
        self.assertNotIn("@media (max-width: 600px)", jarvis12_exit.CSS + jarvis13_exit.CSS)

    def test_v5_app_uses_second_route_and_old_app_dialog_buttons_fit(self):
        # 2026-11-05 상하님 캡처 — 「새 판 받기」가 찌그러짐 · ✕ 가 안 꺼짐
        import jarvis12_exit
        import jarvis13_exit
        for module in (jarvis12_exit, jarvis13_exit):
            device = module.device()
            self.assertIn("jarvisapp://exit", device)
            self.assertIn("parseInt(ver, 10) >= 5", device)                         # 옛 판에서는 안 간다(오류 화면)
            self.assertLess(device.index("JarvisApp.exit()"), device.index("jarvisapp://exit"))   # 다리가 먼저
            self.assertIn("x-row a{flex:1 1 0", module.css())                       # 「새 판 받기」도 「닫기」와 같은 폭


if __name__ == "__main__":
    unittest.main()

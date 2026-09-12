"""닫아 둔 화면은 주소로 들어와도 막힌다 (2026-08-28 상하님 지시).

상하님 — "이 테마 지금 미국테마만 로딩되게 하고 나머지는 다 접근 금지하도록
해라" · "나머지 화면은 접근 금지로 해라."

막는 자리는 둘이다. ① 「어디로 갈까요」 목록에서 뺀다 ② 주소로 바로 들어와도
막는다. ②가 없으면 북마크나 뒤로가기로 그냥 들어가진다.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import page_access

ROOT = Path(__file__).parent
CLOSED_PAGES = {
    "pages/0_시장판단.py": "시장판단",
    "pages/1_자비스2.py": "자비스2",
    "pages/4_자비스5.py": "자비스5",
    "pages/5_자비스6.py": "자비스6",
    # 2026-09-11 상하님 지시로 닫았다 — "자비스6 온라인 화면에서 안 보이게 해라".
    "pages/6_자비스6_미국테마.py": "자비스6미국테마",
}


class OpenPagesTests(unittest.TestCase):
    def test_only_the_theme_pages_are_open(self):
        """지금 열어 둔 것은 셋이다 — 미국테마 · 한국테마 · 자비스7.

        2026-09-07에 미국테마 하나만 남겼다가 2026-09-08에 둘을 도로 열었고,
        **2026-09-11 상하님 지시로 자비스6미국테마를 다시 닫았다** —
        「어디로 갈까요」 캡처의 그 줄에 동그라미를 치시고 "자비스6 온라인
        화면에서 안 보이게 해라".
        """
        self.assertEqual(("미국테마", "한국테마", "자비스7"),
                         page_access.OPEN_PAGES)
        self.assertFalse(page_access.is_open("자비스6미국테마"))

    def test_every_name_is_a_real_page(self):
        """열어 둔 이름이 오타면 그 화면이 조용히 막힌다."""
        for name in page_access.OPEN_PAGES:
            self.assertIn(name, page_access.ALL_PAGES, name)

    def test_the_full_list_is_kept_for_restoring(self):
        """되살릴 이름을 지우지 않는다 — 지우면 무엇이 있었는지 알 수 없다."""
        self.assertEqual(9, len(page_access.ALL_PAGES))


class GuardPlacementTests(unittest.TestCase):
    def test_each_closed_page_guards_at_the_very_top(self):
        """**맨 앞**이어야 한다 — 뒤에 두면 그 앞의 시세 조회가 이미 다 돈다."""
        for path, name in CLOSED_PAGES.items():
            source = (ROOT / path).read_text(encoding="utf-8")
            self.assertIn(f'page_access.guard(st, "{name}")', source, path)
            guard_at = source.index("page_access.guard(st,")
            head = source[:guard_at]
            # 화면을 그리거나 자료를 받는 일이 막기보다 먼저 오면 안 된다.
            # **부르는 것**만 본다 — 파일 맨 위 설명글에 'database.py' 같은 말이
            # 나오는 것은 부르는 것이 아니다.
            for heavy in (r"st\.title\(", r"st\.dataframe\(", r"st\.altair_chart\(",
                          r"j3data\.\w+\(", r"j4data\.\w+\(", r"database\.\w+\("):
                self.assertIsNone(re.search(heavy, head),
                                  f"{path}: 막기 전에 {heavy} 가 돈다")
            # set_page_config 는 스트림릿이 첫 호출이어야 한다고 정해 둔 것이라
            # 그것만 앞에 온다.
            self.assertLess(head.index("st.set_page_config("), guard_at, path)

    def test_the_open_page_is_not_guarded(self):
        """열어 둔 화면에는 막는 장치를 두지 않는다.

        한국테마는 2026-09-07에 닫으면서 막는 장치를 붙였다가, 2026-09-08에
        도로 열면서 그 장치를 뗐다(상하님 지시 — "한국테마는 다시 살려라").
        자비스6미국테마는 2026-09-11에 도로 닫으면서 장치를 다시 붙였으므로
        여기서 빠지고 위 CLOSED_PAGES 로 옮겼다.
        """
        for path in ("pages/2_자비스3.py", "pages/3_자비스4.py"):
            source = (ROOT / path).read_text(encoding="utf-8")
            self.assertNotIn("page_access.guard(", source, path)

    def test_the_new_design_page_is_not_under_repair(self):
        """자비스6미국테마는 「수리 중입니다」 한 장만 그리고 멈추던 장치가 있었다.

        2026-09-07에 붙였다가(상하님 — "그냥 수리 중이라고만 내용 넣어라"),
        2026-09-08에 뗐다(상하님 — "자비스6 미국테마도 다시 살려라").
        열어 두기만 하고 이것을 남겨 두면 화면은 여전히 안 열린다 —
        그래서 여는 것과 함께 지킨다.
        """
        source = (ROOT / "pages/6_자비스6_미국테마.py").read_text(encoding="utf-8")
        self.assertNotIn("_UNDER_REPAIR", source)
        self.assertNotIn("수리 중입니다", source)


class SidebarTests(unittest.TestCase):
    """왼쪽 메뉴는 스트림릿이 pages/ 폴더를 보고 **저절로** 만든다.

    2026-09-11 상하님 지적 — "자비스6 왜 아직 온라인에 떠 있냐?"
    page_access 로 닫아도 그 목록에는 이름이 그대로 남아 있었다. 주소로 골라 감춘다.
    """

    def test_the_closed_new_design_is_hidden_from_the_sidebar(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('[data-testid="stSidebarNav"] a[href*="자비스6_미국테마"]', source,
                      "왼쪽 메뉴에서 자비스6 미국테마를 안 감춘다")
        # 주소가 %-로 바뀌어 오는 경우도 같이 걸어 둔다.
        self.assertIn("%EC%9E%90%EB%B9%84%EC%8A%A46_%EB%AF%B8%EA%B5%AD%ED%85%8C%EB%A7%88",
                      source, "%-주소일 때가 안 걸린다")
        # **줄 번호로 감추지 않는다** — 파일이 늘고 줄 때마다 엉뚱한 줄이 사라진다
        # (CLAUDE.md 12번). app.py 에 있는 nth-child 는 **차례(order)** 를 바꾸는
        # 것이지 감추는 것이 아니다. 감추는 규칙에는 display:none 이 붙으므로
        # 그 둘이 한 덩이로 붙어 있지 않은지만 본다.
        self.assertNotIn("li:nth-child(8) { display: none", source,
                         "줄 번호로 감추면 안 된다")


class ChooserTests(unittest.TestCase):
    def test_the_chooser_only_lists_open_pages(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("import page_access", source)
        self.assertIn("if page_access.is_open(key)", source)
        # 옵션 자체는 남겨 둔다 — 되살릴 때 이름을 여기서 가져다 쓴다.
        self.assertIn("_ALL_DEST_OPTIONS = [", source)
        names = re.search(r"_DEST_KEYS = \[(.*?)\]", source, re.S).group(1)
        for name in page_access.ALL_PAGES:
            self.assertIn(f'"{name}"', names, name)

    def test_the_jarvis1_url_mark_is_blocked_too(self):
        """주소에 표식이 있어도 닫혀 있으면 안 그린다."""
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('or not page_access.is_open("자비스1")', source)


if __name__ == "__main__":
    unittest.main()

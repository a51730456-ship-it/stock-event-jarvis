"""폰 표시 규칙 테스트.

핵심은 두 가지다.
  1. 폰 규칙이 반드시 미디어쿼리 안에만 있어야 한다 — 태블릿·PC 화면이 바뀌면 안 된다.
  2. 표에서 감출 칸과 남길 칸이 실제 표의 칸 수와 어긋나면 안 된다.
"""

import re
import unittest

import mobile_ui as m


class MediaQueryTests(unittest.TestCase):
    def test_no_rule_sits_outside_a_media_query(self):
        """규칙이 미디어쿼리 밖으로 새면 PC 화면까지 바뀐다.

        미디어쿼리는 둘이다 — 표·글자는 폰(600px), 메뉴는 태블릿까지(1200px).
        """
        css = m.page_css(m.table_css("x_", 4, {2: "이름"}, "j3-td"))
        self.assertEqual(css.count("@media"), 2)
        # <style> 바로 뒤부터 첫 @media 앞까지 규칙이 있으면 안 된다.
        head = css[len("<style>"): css.index("@media")]
        self.assertEqual(head.strip(), "")

    def test_phone_rules_stay_in_the_phone_media_query(self):
        """표·글자 규칙은 폰(600px) 묶음 안에 있어야 태블릿이 안 바뀐다."""
        css = m.page_css(m.table_css("x_", 4, {2: "이름"}, "j3-td"))
        phone_block = css[css.index(f"@media (max-width: {m.PHONE_MAX_WIDTH}px)"): css.rindex("}</style>")]
        self.assertIn(".fg-box", phone_block)
        self.assertIn(".j3-theme-table", phone_block)
        self.assertNotIn("stSidebarNav", phone_block)

    def test_phone_breakpoint_excludes_galaxy_tab_s8_plus(self):
        """갤럭시탭 S8+는 1138px이라 폰 규칙에 걸리면 안 된다."""
        self.assertLess(m.PHONE_MAX_WIDTH, 1138)
        # 갤럭시 S21 울트라(412px)는 걸려야 한다.
        self.assertGreater(m.PHONE_MAX_WIDTH, 412)

    def test_stacked_cells_get_a_wrapper_height(self):
        """그릇에 높이를 안 주면 칸이 10px로 눌려 글자가 서로 겹쳐 찍힌다.

        2026-07-25 폰 412px 실측: 이 규칙이 없으면 조건점수·상태·당일이 겹쳤다.
        """
        css = m.table_css("j3tbtn_", 8, {2: "", 4: "조건점수"}, "j3-td")
        self.assertIn("div:has(> [data-testid='stMarkdownContainer'])", css)
        self.assertIn("min-height: 1.75rem", css)

    def test_theme_table_keeps_supply_column_on_jarvis4(self):
        """자비스4의 8번 칸은 수급이라 폰에서도 남겨야 한다(자비스4의 핵심)."""
        css = m.THEME_TABLE_CSS
        self.assertIn(".j3-theme-table th:nth-child(8)", css)      # 미국은 매수 상태 → 접는다
        self.assertNotIn(".j4-theme-table th:nth-child(8)", css)   # 한국은 수급 → 남긴다

    def test_theme_table_numbers_do_not_wrap(self):
        """칸이 좁아 '+1.76%'가 한 글자씩 세로로 쪼개지던 것을 막는다."""
        self.assertIn("white-space: nowrap", m.THEME_TABLE_CSS)

    def test_phone_hides_only_the_first_three_sidebar_items(self):
        """폰 메뉴는 미국테마·한국테마·선행감지(li 4·5·6)만 남긴다.

        자비스1·시장판단·자비스2(li 1·2·3)는 감추되, 남길 4·5·6은 감추면 안 된다.
        규칙은 반드시 미디어쿼리 안에 있어야 태블릿·PC 메뉴가 그대로다.
        """
        css = m.page_css()
        # 사이드바 메뉴를 감추는 규칙 덩어리만 뽑아 nth-child 번호를 확인한다.
        block = next(b for b in css.split("}")
                     if "stSidebarNav" in b and "display: none" in b)
        hidden = {int(n) for n in re.findall(r"nth-child\((\d+)\)", block)}
        self.assertEqual(hidden, {1, 2, 3})

    def test_menu_rule_reaches_tablets_but_not_pc(self):
        """메뉴는 폰·태블릿에서만 3개다 — 갤럭시탭 S8+(1138px)도 걸려야 한다."""
        self.assertGreaterEqual(m.SIDEBAR_MAX_WIDTH, 1138)
        self.assertLess(m.SIDEBAR_MAX_WIDTH, 1280)  # 노트북은 6개 그대로
        self.assertIn(f"@media (max-width: {m.SIDEBAR_MAX_WIDTH}px)", m.SIDEBAR_NAV_CSS)


class TableCssTests(unittest.TestCase):
    def _hidden_indexes(self, css):
        line = next(l for l in css.split("\n") if "display: none" in l)
        return {int(n) for n in re.findall(r"nth-child\((\d+)\)", line)}

    def test_hides_exactly_the_columns_not_kept(self):
        css = m.table_css("j4pbf_", 12, {2: "", 4: "눌림", 6: "현재가"}, "j4-td")
        self.assertEqual(self._hidden_indexes(css), {1, 3, 5, 7, 8, 9, 10, 11, 12})

    def test_keeping_every_column_emits_no_hide_rule(self):
        css = m.table_css("x_", 3, {1: "", 2: "", 3: ""}, "j3-td")
        self.assertNotIn("display: none", css)

    def test_labels_are_attached_only_where_asked(self):
        css = m.table_css("j3pbf_", 12, {2: "", 4: "눌림", 7: "현재가"}, "j3-td")
        self.assertIn("content: '눌림 '", css)
        self.assertIn("content: '현재가 '", css)
        # 빈 이름표(종목 버튼 칸)에는 ::before를 붙이지 않는다.
        self.assertNotIn("nth-child(2) [data-testid='stMarkdownContainer'] > div::before", css)

    def test_rows_are_selected_by_their_button_key(self):
        """파이썬 렌더링 코드를 건드리지 않으려고 :has()로 줄을 집는다."""
        css = m.table_css("j4tbtn_", 8, {2: ""}, "j4-td")
        self.assertIn(":has(div[class*='st-key-j4tbtn_'])", css)

    def test_header_rows_are_hidden_by_their_class(self):
        css = m.hide_header_rows("j3-th-head", "j4-th-head")
        self.assertIn(":has(.j3-th-head)", css)
        self.assertIn(":has(.j4-th-head)", css)
        self.assertIn("display: none", css)


class RealPageMappingTests(unittest.TestCase):
    """화면에 실제로 쓰는 칸 수·번호가 표 제목과 맞는지 굳혀 둔다.

    표에 칸을 더하거나 빼면 이 테스트가 먼저 깨져서, 폰에서 엉뚱한 칸이
    숨겨지는 일을 막는다.
    """

    CASES = (
        ("자비스3 테마표", 8, {2, 4, 5, 6}),
        ("자비스3 눌림목표", 12, {2, 4, 5, 7, 8}),
        ("자비스4 테마표", 8, {2, 4, 5, 6}),
        ("자비스4 눌림목표", 12, {2, 4, 6, 7, 11}),
    )

    def test_kept_columns_are_within_range_and_include_the_name(self):
        for name, total, keep in self.CASES:
            with self.subTest(name):
                self.assertTrue(all(1 <= i <= total for i in keep), "칸 번호가 범위 밖")
                self.assertIn(2, keep, "종목·테마 이름 칸(2)은 반드시 남겨야 누를 수 있다")
                self.assertLessEqual(len(keep), 5, "폰에서 다섯 칸을 넘으면 다시 길어진다")


if __name__ == "__main__":
    unittest.main()

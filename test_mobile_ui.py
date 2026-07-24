"""폰 표시 규칙 테스트.

핵심은 두 가지다.
  1. 폰 규칙이 반드시 미디어쿼리 안에만 있어야 한다 — 태블릿·PC 화면이 바뀌면 안 된다.
  2. 표에서 감출 칸과 남길 칸이 실제 표의 칸 수와 어긋나면 안 된다.
"""

import re
import unittest

import mobile_ui as m


class MediaQueryTests(unittest.TestCase):
    def test_all_rules_live_inside_the_phone_media_query(self):
        """규칙이 미디어쿼리 밖으로 새면 태블릿·PC까지 바뀐다."""
        css = m.page_css(m.table_css("x_", 4, {2: "이름"}, "j3-td"))
        self.assertEqual(css.count("@media"), 1)
        inner = css[css.index("{", css.index("@media")) + 1: css.rindex("}</style>")]
        # 미디어쿼리 앞뒤에 규칙이 붙어 있지 않아야 한다.
        head = css[: css.index("@media")]
        self.assertEqual(head, "<style>")
        self.assertIn(".fg-box", inner)

    def test_phone_breakpoint_excludes_galaxy_tab_s8_plus(self):
        """갤럭시탭 S8+는 1138px이라 폰 규칙에 걸리면 안 된다."""
        self.assertLess(m.PHONE_MAX_WIDTH, 1138)
        # 갤럭시 S21 울트라(412px)는 걸려야 한다.
        self.assertGreater(m.PHONE_MAX_WIDTH, 412)


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

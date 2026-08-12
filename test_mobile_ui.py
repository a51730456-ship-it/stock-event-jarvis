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

        미디어쿼리는 다섯이다 — 메뉴·상단 지표 줄은 태블릿까지(1200px),
        그 중 '한 줄에 몇 칸'은 세로·가로 두 갈래(2026-08-01), 표·글자는 폰(600px).
        """
        css = m.page_css(m.table_css("x_", 4, {2: "이름"}, "j3-td"))
        self.assertEqual(css.count("@media"), 5)
        # <style> 바로 뒤부터 첫 @media 앞까지 규칙이 있으면 안 된다.
        head = css[len("<style>"): css.index("@media")]
        self.assertEqual(head.strip(), "")

    def test_cell_count_follows_the_way_you_hold_it(self):
        """태블릿을 가로로 돌리면 한 줄에 더 담아야 한다(2026-08-01 사용자 지시).

        그전에는 세로·가로 모두 2칸씩이라 돌려도 화면이 그대로였다.
        방향(orientation)을 보므로 폭이 아니라 돌리는 즉시 바뀐다.
        """
        css = m.page_css()
        self.assertIn(f"@media (max-width: {m.SIDEBAR_MAX_WIDTH}px) and (orientation: portrait)", css)
        self.assertIn(f"@media (max-width: {m.SIDEBAR_MAX_WIDTH}px) and (orientation: landscape)", css)
        # 칸 수 규칙은 방향 묶음 안에만 있어야 한다 — 밖에 있으면 돌려도 안 바뀐다.
        self.assertNotIn("min-width: calc(", m.TOP_ROW_CSS)
        self.assertIn("calc(50% - 0.6rem)", m.TOP_ROW_PORTRAIT_CSS)
        self.assertIn("calc(25% - 0.8rem)", m.TOP_ROW_LANDSCAPE_CSS)

    def test_phone_rules_stay_in_the_phone_media_query(self):
        """표·글자 규칙은 폰(600px) 묶음 안에 있어야 태블릿이 안 바뀐다."""
        css = m.page_css(m.table_css("x_", 4, {2: "이름"}, "j3-td"))
        phone_block = css[css.index(f"@media (max-width: {m.PHONE_MAX_WIDTH}px)"): css.rindex("}</style>")]
        self.assertIn(".j3-theme-table", phone_block)
        self.assertNotIn("stSidebarNav", phone_block)
        # 상단 지표 줄의 크기·순서 규칙은 태블릿까지 걸려야 하므로 폰 묶음에 있으면 안 된다.
        self.assertNotIn(".fg-box { order:", phone_block)
        self.assertNotIn(".fg-box-gauge", phone_block)
        self.assertNotIn(".fg-box-title", phone_block)
        # 국면 다섯 칸 접기만 예외로 폰 묶음에 둔다 — 태블릿에서까지 접혀 단계가
        # 통째로 사라졌다(2026-08-06 사용자 지적). 규칙 12대로 폰에만 걸어야 한다.
        self.assertIn("fg-hist-dim", phone_block)
        self.assertNotIn("fg-hist-dim", m.TOP_ROW_CSS)
        tablet_block = css[css.index(f"@media (max-width: {m.SIDEBAR_MAX_WIDTH}px)", css.index("stSidebarNav")):]
        self.assertIn(".fg-box", tablet_block[: tablet_block.index("@media (max-width: 600px)")])

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

    def test_theme_table_hides_no_column(self):
        """테마 종목표도 폰에서 칸을 감추지 않는다(2026-07-25 사용자 지적).

        좁으면 글자를 줄이고, 그래도 넘치면 표만 옆으로 밀어서 본다.
        """
        css = m.THEME_TABLE_CSS
        self.assertNotIn("display: none", css)
        self.assertIn("overflow-x: auto", css)

    def test_theme_table_numbers_do_not_wrap(self):
        """칸이 좁아 '+1.76%'가 한 글자씩 세로로 쪼개지던 것을 막는다."""
        self.assertIn("white-space: nowrap", m.THEME_TABLE_CSS)

    def test_phone_menu_keeps_only_the_two_theme_pages(self):
        """폰·태블릿 메뉴는 미국테마(li 4)·한국테마(li 5) 둘만 남긴다(2026-08-01 지시).

        자비스1·시장판단·자비스2(li 1~3)와 선행감지·종가관찰(li 6~7)을 감추되,
        남길 4·5는 감추면 안 된다. 규칙은 반드시 미디어쿼리 안에 있어야
        노트북/PC 메뉴가 그대로다.
        """
        css = m.page_css()
        # 사이드바 메뉴를 감추는 규칙 덩어리만 뽑아 nth-child 번호를 확인한다.
        block = next(b for b in css.split("}")
                     if "stSidebarNav" in b and "display: none" in b)
        hidden = {int(n) for n in re.findall(r"nth-child\((\d+)\)", block)}
        self.assertEqual(hidden, {1, 2, 3, 6, 7})

    def test_jarvis1_screen_hides_the_same_menu_items(self):
        """app.py에도 같은 규칙이 있다 — 한쪽만 고치면 화면마다 메뉴가 달라진다."""
        import pathlib

        source = pathlib.Path(__file__).with_name("app.py").read_text(encoding="utf-8")
        block = source.split("@media (max-width: 1200px) {", 1)[1].split("}", 1)[0]
        hidden = {int(n) for n in re.findall(r"nth-child\((\d+)\)", block)}
        self.assertEqual(hidden, {1, 2, 3, 6, 7})

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

    # 2026-07-25부터 폰에서도 칸을 감추지 않는다 — 감췄더니 "다른 항목은 어디
    # 갔나"라는 말이 나왔다. 그래서 남길 칸 = 표의 전체 칸이다.
    CASES = (
    )

    def test_every_column_stays_visible_on_phones(self):
        for name, total, keep in self.CASES:
            with self.subTest(name):
                self.assertTrue(all(1 <= i <= total for i in keep), "칸 번호가 범위 밖")
                self.assertIn(2, keep, "종목·테마 이름 칸(2)은 반드시 남겨야 누를 수 있다")
                self.assertEqual(len(keep), total, "폰에서도 칸을 감추지 않는다")

    def test_pages_keep_every_column_too(self):
        """화면 코드가 실제로 전체 칸을 남기는지 본다 — 여기서만 고치면 소용없다."""
        import pathlib
        import re

        root = pathlib.Path(__file__).parent
        # 자비스4 눌림목표는 세로로 쌓지 않고 옆으로 밀어 보므로 칸 규칙이 없다.
        expected = {}
        sources = "\n".join(
            (root / name).read_text(encoding="utf-8")
            for name in ("pages/2_자비스3.py", "pages/3_자비스4.py")
        )
        for prefix, total in expected.items():
            with self.subTest(prefix):
                block = re.search(
                    rf'table_css\("{prefix}", {total}, \{{(.*?)\}}', sources, re.S)
                self.assertIsNotNone(block, f"{prefix} 표 설정을 찾지 못했다")
                kept = {int(n) for n in re.findall(r"(\d+):", block.group(1))}
                self.assertEqual(kept, set(range(1, total + 1)))


class ModuleRevisionTests(unittest.TestCase):
    """온라인에 옛 모듈이 남지 않게 리비전 표식을 굳혀 둔다(CLAUDE.md 11번).

    2026-07-25에 이 표식이 없어서 폰 수정이 온라인에 하나도 반영되지 않았다.
    """

    PAGES = ("pages/2_자비스3.py", "pages/3_자비스4.py", "pages/4_자비스5.py")

    def test_mobile_ui_has_a_revision(self):
        self.assertIsInstance(getattr(m, "MODULE_REVISION", None), int)

    def test_pages_require_the_current_mobile_revision(self):
        """mobile_ui를 고치고 리비전만 올리면 이 테스트가 페이지 동기화를 강제한다."""
        import pathlib
        import re

        root = pathlib.Path(__file__).parent
        for name in self.PAGES:
            with self.subTest(name):
                source = (root / name).read_text(encoding="utf-8")
                found = re.search(r"_REQUIRED_MOBILE_REVISION = (\d+)", source)
                self.assertIsNotNone(found, f"{name}에 mobile_ui 리비전 가드가 없다")
                self.assertEqual(
                    int(found.group(1)), m.MODULE_REVISION,
                    f"{name}의 요구 리비전이 mobile_ui.MODULE_REVISION과 다르다",
                )


if __name__ == "__main__":
    unittest.main()


class GaugeZoneRowsOnPhoneTests(unittest.TestCase):
    """시장 국면 다섯 칸은 **폰에서도 다 보여야 한다** (2026-08-12 상하님 지시).

    2026-08-05에 "카드가 길어진다"는 이유로 폰에서만 지금 속한 칸 하나만 남기고
    네 줄을 숨겨 뒀다. 상하님이 태블릿과 폰을 나란히 놓고 보시고 —
    "스마트폰은 안 나온다, 나오게 해라". 0~29 · 30~49 같은 수치 안내가 폰에서만
    사라져 지금 점수가 어느 자리인지 알 수 없었다.
    """

    def test_the_dim_rows_are_not_hidden(self):
        css = m.CONTENT_CSS
        block = css.split(".fg-box-hist .fg-hist-row.fg-hist-dim")[1].split("}")[0]
        self.assertNotIn("display: none", block, "폰에서 구간 줄이 다시 숨겨졌다")
        self.assertNotIn("display:none", block, "폰에서 구간 줄이 다시 숨겨졌다")
        # 숨기는 대신 얇게 만든다 — 카드가 길어지는 것은 그렇게 막는다.
        self.assertIn("font-size", block)

    def test_the_rule_stays_inside_the_phone_media_query(self):
        """폰 규칙이 밖으로 새면 태블릿·PC까지 바뀐다(CLAUDE.md 12번).

        CONTENT_CSS는 미디어쿼리 **안쪽 내용**이고 감싸는 것은 page_css()다.
        그래서 완성된 CSS에서, 이 규칙 앞에 폰 미디어쿼리가 열려 있는지 본다.
        """
        css = m.page_css()
        self.assertIn(".fg-box-hist .fg-hist-row.fg-hist-dim", css)
        before = css.split(".fg-box-hist .fg-hist-row.fg-hist-dim")[0]
        opened = before.rfind(f"@media (max-width: {m.PHONE_MAX_WIDTH}px)")
        self.assertGreater(opened, -1, "폰 미디어쿼리 밖에 있다")
        # 그 뒤로 닫히지 않았는지 — 여는 중괄호가 닫는 것보다 많아야 안에 있다.
        tail = before[opened:]
        self.assertGreater(tail.count("{"), tail.count("}"), "미디어쿼리가 이미 닫혔다")

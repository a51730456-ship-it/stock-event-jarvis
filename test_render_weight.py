"""화면 한 판에 요소가 몇 개나 실리는지 지킨다.

2026-07-30 사용자 실측 — 폰·태블릿에서 눌림목 15초, 닫기 12초. 나가지 않고 다시
눌러도 느리다. 서버 쪽을 재보니 캐시가 따뜻하면 한 판이 0.5초였다. 즉 병목은
파이썬이 아니라 **브라우저로 보내 그리는 양**이었다.

세어 보니 아무것도 안 연 기본 화면이 요소 559개였고, 그중 476개가 테마표·대장주표
두 개에서 나왔다. 칸마다 st.columns 요소를 만들고 있었기 때문이다.
한 줄을 세 칸(순위 · 이름 단추 · 나머지 한 덩이)으로 줄여 251개가 됐다.

여기서 지키는 것은 '칸마다 요소를 만들지 않는다'이다. 옛 방식으로 돌아가면 깨진다.
"""

import pathlib
import re
import unittest

PAGES = {
    "US": ("pages/2_자비스3.py", "j3"),
    "KR": ("pages/3_자비스4.py", "j4"),
}


class RowWidthTests(unittest.TestCase):
    def _source(self, path):
        return pathlib.Path(path).read_text(encoding="utf-8-sig")

    def test_rows_use_three_columns_not_one_per_cell(self):
        for market, (path, prefix) in PAGES.items():
            source = self._source(path)
            for table in ("THEME", "LEADER"):
                self.assertIn(f"_{table}_ROW_WIDTHS = [", source,
                              f"{market} {table} 표가 아직 칸마다 요소를 만든다")
                # 세 칸이면 쉼표가 둘이다(대괄호 안의 sum(...[2:])에는 쉼표가 없다).
                widths = re.search(
                    rf"_{table}_ROW_WIDTHS = \[(.*?)\]\n", source, re.S
                ).group(1)
                self.assertEqual(2, widths.count(","), f"{market} {table} 줄이 세 칸이 아니다")

    def test_the_merged_cell_is_one_markdown(self):
        """나머지 칸은 _flex_row 한 덩이로 그려야 한다."""
        for market, (path, prefix) in PAGES.items():
            source = self._source(path)
            self.assertIn("def _flex_row(", source, f"{market}에 한 덩이로 그리는 함수가 없다")
            self.assertIn(f"_flex_row(_{'THEME'}_REST_WIDTHS", source)
            self.assertIn(f"_flex_row(_{'LEADER'}_REST_WIDTHS", source)
            # 옛 방식(칸 번호로 하나씩 쓰기)이 남아 있으면 안 된다.
            for fn in ("_render_theme_table", "_render_leader_table",
                       "_render_pullback_finder"):
                block = source.split(f"def {fn}(")[1].split("\ndef ")[0]
                stray = re.findall(r"cols\[[3-9]\]\.markdown", block)
                self.assertEqual([], stray, f"{market} {fn}에 옛 칸별 그리기가 남았다: {stray}")

    def test_pullback_table_also_uses_three_columns(self):
        """눌림목 표가 제일 컸다 — 13칸 × 15줄(2026-07-30 사용자 지시로 같이 줄임)."""
        for market, (path, _prefix) in PAGES.items():
            source = self._source(path)
            block = source.split("def _render_pullback_finder(")[1].split("\ndef ")[0]
            self.assertIn("row_widths = [widths[0], widths[1], sum(widths[2:])]", block,
                          f"{market} 눌림목 표가 아직 칸마다 요소를 만든다")
            self.assertIn("rest_widths = widths[2:]", block)
            self.assertIn("_flex_row(rest_widths", block)
            self.assertIn("table_box.columns(row_widths)", block)

    def test_widths_still_add_up_to_the_original(self):
        """폭 비율은 그대로여야 머리글과 본문이 줄 맞는다."""
        for market, (path, _prefix) in PAGES.items():
            source = self._source(path)
            for table in ("THEME", "LEADER"):
                self.assertIn(
                    f"_{table}_ROW_WIDTHS = [_{table}_COL_WIDTHS[0], _{table}_COL_WIDTHS[1], "
                    f"sum(_{table}_COL_WIDTHS[2:])]",
                    source, f"{market} {table} 폭이 원래 비율과 어긋난다",
                )
                self.assertIn(f"_{table}_REST_WIDTHS = _{table}_COL_WIDTHS[2:]", source)


if __name__ == "__main__":
    unittest.main()

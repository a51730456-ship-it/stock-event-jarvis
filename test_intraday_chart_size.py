"""종목 상세의 '당일 · 실시간' 차트 크기 (2026-07-30 사용자 지시).

화면 폭을 다 쓰던 것을 아래 일봉·주봉·월봉과 같은 3분할 폭으로 줄이고
가로세로를 4:3으로 맞췄다. 다시 화면을 가로지르면 이 테스트가 깨진다.
"""

import pathlib
import unittest

PAGES = {
    "US": ("pages/2_자비스3.py", "j3"),
    "KR": ("pages/3_자비스4.py", "j4"),
}

# 넓은 화면(1280px)에서 3분할 한 칸이 359px이었다(2026-07-30 실측).
COLUMN_WIDTH = 359


class IntradayChartSizeTests(unittest.TestCase):
    def _source(self, path):
        return pathlib.Path(path).read_text(encoding="utf-8-sig")

    def test_height_gives_four_to_three(self):
        for market, (path, _prefix) in PAGES.items():
            source = self._source(path)
            self.assertIn("INTRADAY_CHART_HEIGHT = 269", source, f"{market} 높이가 다르다")
        ratio = COLUMN_WIDTH / 269
        self.assertAlmostEqual(4 / 3, ratio, places=2, msg=f"4:3이 아니다({ratio:.2f})")

    def test_chart_sits_in_a_third_of_the_width(self):
        """세 칸 중 첫 칸에만 그려야 아래 일봉과 폭이 같아진다."""
        for market, (path, _prefix) in PAGES.items():
            source = self._source(path)
            self.assertIn("intraday_col, _, _ = st.columns(3)", source,
                          f"{market} 당일 차트가 아직 화면을 가로지른다")
            self.assertIn("_intraday_chart(intraday_payload, height=INTRADAY_CHART_HEIGHT)",
                          source, f"{market}가 맞춘 높이를 안 쓴다")

    def test_no_full_width_intraday_left_in_the_detail(self):
        """옛 코드가 남아 있으면 두 벌이 그려진다."""
        for market, (path, _prefix) in PAGES.items():
            source = self._source(path)
            self.assertNotIn(
                "st.altair_chart(_intraday_chart(intraday_payload, height=210)",
                source, f"{market}에 옛 전체폭 차트가 남았다",
            )


if __name__ == "__main__":
    unittest.main()

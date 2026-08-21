"""종목 상세의 '당일 · 실시간' 차트 크기.

2026-07-30에는 아래 일봉·주봉·월봉과 같은 3분할 폭에 4:3(269px)으로 맞췄다.
**2026-08-21에 상하님이 다시 정하셨다** — "당일차트 크기 두번째 캡쳐 크기로
바꿔라". 맨 위 지수 카드에 붙은 당일 그림과 같은 크기(120×90)다.

미국테마·한국테마가 **같은 크기**여야 한다. 한쪽만 바꾸면 같은 자리인데
화면마다 다른 크기가 된다.
"""

import pathlib
import unittest

PAGES = {
    "US": ("pages/2_자비스3.py", "j3"),
    "KR": ("pages/3_자비스4.py", "j4"),
}

# 맨 위 지수 카드가 쓰는 그림 크기(_sparkline_svg 기본값)와 같다.
CARD_CHART_WIDTH = 120
CARD_CHART_HEIGHT = 90


class IntradayChartSizeTests(unittest.TestCase):
    def _source(self, path):
        return pathlib.Path(path).read_text(encoding="utf-8-sig")

    def test_height_matches_the_index_cards(self):
        for market, (path, _prefix) in PAGES.items():
            source = self._source(path)
            self.assertIn(f"INTRADAY_CHART_HEIGHT = {CARD_CHART_HEIGHT}", source,
                          f"{market} 높이가 지수 카드와 다르다")
            self.assertIn(f'"width": {CARD_CHART_WIDTH}, "height": height', source,
                          f"{market} 폭이 지수 카드와 다르다")

    def test_small_charts_drop_the_axes(self):
        """120×90에 축 글자까지 넣으면 그림이 안 보인다."""
        for market, (path, _prefix) in PAGES.items():
            source = self._source(path)
            self.assertIn('alt.X("시각:T", title=None, axis=None)', source,
                          f"{market} 작은 차트에 가로 눈금이 남았다")
            self.assertIn("small=True", source, f"{market}가 작은 차트를 안 쓴다")

    def test_chart_does_not_stretch_to_the_column(self):
        """폭을 늘리면 그림만 길쭉해진다 — 칸이 아니라 그림 크기에 맞춘다."""
        for market, (path, _prefix) in PAGES.items():
            source = self._source(path)
            self.assertIn("intraday_col, _, _ = st.columns(3)", source,
                          f"{market} 당일 차트가 화면을 가로지른다")
            self.assertIn('width="content", theme="streamlit"', source,
                          f"{market}가 아직 칸 폭만큼 늘린다")

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

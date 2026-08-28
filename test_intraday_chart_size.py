"""종목 상세의 '당일' 차트.

한국테마(자비스4)는 2026-08-21에 상하님이 정하신 그대로다 — 맨 위 지수 카드에
붙은 당일 그림과 같은 크기(120×90)에 축 글자 없이.

**미국테마(자비스3)는 2026-08-28에 바뀌었다.** 상하님 지시 —
"당일·일봉(거래량 빼라)·주봉·월봉이 너무 못생겼다. 첫 번째 캡처처럼 하되
일·주·월봉은 20선 50선은 넣어 줘" · "스마트폰 기준으로 당일·일봉 차트 같은
선상에 2개 해 주고 그 밑에 주·월봉."

그래서 미국 쪽은 당일 차트가 따로 있지 않고 **네 그림 한 판**에 들어간다.
알테어(Vega) 그림도 아니다 — 서버가 만든 SVG 한 조각이다.
**한국테마는 안 건드렸다**(CLAUDE.md 0-1 다).
"""

import pathlib
import unittest

US_PAGE = "pages/2_자비스3.py"
KR_PAGE = "pages/3_자비스4.py"

# 맨 위 지수 카드가 쓰는 그림 크기(_sparkline_svg 기본값)와 같다.
CARD_CHART_WIDTH = 120
CARD_CHART_HEIGHT = 90


def _source(path):
    return pathlib.Path(path).read_text(encoding="utf-8-sig")


class KoreanIntradayChartTests(unittest.TestCase):
    """한국테마는 2026-08-21 상하님 결정 그대로 둔다."""

    def test_height_matches_the_index_cards(self):
        source = _source(KR_PAGE)
        self.assertIn(f"INTRADAY_CHART_HEIGHT = {CARD_CHART_HEIGHT}", source)
        self.assertIn(f'"width": {CARD_CHART_WIDTH}, "height": height', source)

    def test_small_charts_drop_the_axes(self):
        source = _source(KR_PAGE)
        self.assertIn('alt.X("시각:T", title=None, axis=None)', source)
        self.assertIn("small=True", source)

    def test_chart_does_not_stretch_to_the_column(self):
        source = _source(KR_PAGE)
        self.assertIn("intraday_col, _, _ = st.columns(3)", source)
        self.assertIn('width="content", theme="streamlit"', source)


class UsFourChartsTests(unittest.TestCase):
    """미국테마는 네 그림이 한 판에 2×2로 선다 (2026-08-28 상하님 지시)."""

    def test_the_four_charts_share_one_grid(self):
        source = _source(US_PAGE)
        block = source.split("def _render_price_chart_bundle(")[1].split("\ndef ")[0]
        for name in ("당일", "일봉", "주봉", "월봉"):
            self.assertIn(f'"{name}"', block, f"{name} 그림이 빠졌다")
        self.assertIn("j3-chart-grid", block, "한 판에 안 넣었다")
        # 스트림릿 칸은 폰에서 위아래로 쌓인다 — 그래서 CSS 격자를 쓴다.
        self.assertNotIn("st.columns(", block, "폰에서 한 줄에 하나가 된다")
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", source,
                      "폰에서 두 개씩 서게 안 했다")

    def test_the_charts_are_svg_not_vega(self):
        """알테어 그림은 규격 뭉치를 브라우저가 읽어 그린다 — 폰에서 느리다.

        2026-08-28 실측(노트북) — 종목을 누르고 차트가 뜨기까지 0.53초 → 0.14초,
        Vega 그림 4개 → 0개.
        """
        source = _source(US_PAGE)
        block = source.split("def _render_price_chart_bundle(")[1].split("\ndef ")[0]
        self.assertNotIn("st.altair_chart", block, "아직 알테어로 그린다")
        self.assertIn("_pretty_chart_svg(", block)

    def test_the_daily_chart_has_no_volume_and_has_both_lines(self):
        """거래량은 뺐고(상하님 지시) 20선·50선은 넣었다."""
        source = _source(US_PAGE)
        block = source.split("def _render_price_chart_bundle(")[1].split("\ndef ")[0]
        self.assertNotIn("include_volume", block, "거래량이 아직 있다")
        self.assertIn('ma20=_payload_series(payload, "MA20")', block)
        self.assertIn('ma50=_payload_series(payload, "MA50")', block)
        # 당일 그림에는 20선·50선이 없다 — 하루치라 잴 수가 없다.
        intraday_part = block.split("chart_bundle = ")[0]
        self.assertNotIn("ma20=", intraday_part)

    def test_no_separate_intraday_section_is_left(self):
        """따로 있던 당일 구역이 남아 있으면 같은 그림이 두 번 그려진다."""
        source = _source(US_PAGE)
        self.assertNotIn("def _render_intraday_section(", source)
        self.assertNotIn("당일 차트 닫기", source)


if __name__ == "__main__":
    unittest.main()

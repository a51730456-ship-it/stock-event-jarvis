"""자비스13 「시장 현황」 테마 지도 (2026-11-04 상하님 「미국테마에는 있는데 한국 테마에는 없다」)."""
from __future__ import annotations

import unittest
from pathlib import Path

import jarvis13_sector_map as sm

ROOT = Path(__file__).resolve().parent


def _ranking():
    return {
        "rows": [{"name": f"테마{i}", "ok": True, "change_pct": 2.0 - i} for i in range(6)],
        "all_scored": [
            {"name": "반도체", "change_pct": 2.5, "stocks": [
                {"code": "005930", "change_pct": 1.0, "trading_value": 3e12},
                {"code": "000660", "change_pct": -1.0, "trading_value": 2e12}]},
            {"name": "2차전지", "change_pct": -1.2, "stocks": [
                {"code": "373220", "change_pct": 0.0, "trading_value": 1e12},
                {"code": "005930", "change_pct": 1.0, "trading_value": 3e12}]},
            {"name": "값없음", "change_pct": 0.5, "stocks": [{"code": "111111", "change_pct": 3.0, "trading_value": None}]},
        ],
    }


class SectorMapTests(unittest.TestCase):
    def test_tiles_are_sized_by_trading_value_and_skip_unknown(self):
        rows = sm.tiles_from_ranking(_ranking())
        self.assertEqual(["반도체", "2차전지"], [row["name"] for row in rows])      # 거래대금 큰 차례 · 못 센 테마는 뺌
        self.assertEqual(5e12, rows[0]["weight"])

    def test_breadth_counts_each_stock_once(self):
        b = sm.breadth_from_ranking(_ranking())
        self.assertEqual({"up": 2, "down": 1, "flat": 1, "total": 4}, b)          # 005930 은 두 테마에 있어도 한 번

    def test_korean_colors_up_red_down_blue(self):
        self.assertEqual("#ff5b5b", sm.tone(6.0))                                   # 6% 이상 가장 밝은 빨강
        self.assertEqual("#4da6ff", sm.tone(-6.0))                                  # 6% 이상 내리면 가장 밝은 파랑
        self.assertEqual("#22304a", sm.tone(None))
        self.assertEqual(sm.FLAT_TONE, sm.tone(0.0))

    def test_bigger_moves_are_brighter(self):
        # 2026-11-04 상하님 「색깔 맞냐?」 — +2.26% 와 +8.47% 가 같은 빨강이었다. 크게 움직일수록 밝아야 한다.
        def red(change):
            return int(sm.tone(change)[1:3], 16)

        reds = [red(v) for v in (0.2, 1.0, 2.26, 3.15, 5.0, 8.47)]
        self.assertEqual(sorted(reds), reds)
        self.assertEqual(len(set(reds[:-1])), len(reds) - 1)                        # 6% 밑은 다 다른 색
        self.assertLess(red(2.26), red(8.47) - 60)                                  # 눈에 띄게 다르다

        def blue(change):
            return int(sm.tone(change)[5:7], 16)

        self.assertLess(blue(-0.3), blue(-3.0))

    def test_cell_has_map_strip_breadth_and_zoom(self):
        out = sm.cell_html(_ranking())
        for text in ("강한 테마 지도", "j13-sector-tile", "자비스 테마 상위 5", "▲ 오름 2", "▼ 내림 1",
                     "자비스가 보는 한국 4종목 기준", "j13sm-tap", "다시 누르면 닫힘"):
            self.assertIn(text, out)
        self.assertEqual(5, out.split("j13sm-pop")[0].count("class='j13-sector-theme'"))   # 상위 5 줄(작은 판)
        self.assertNotIn("j3sm", out)                                                  # 자비스12 이름과 안 섞임
        self.assertIn("받는 중", sm.cell_html(None))
        self.assertNotIn("@media (max-width: 600px)", sm.CSS)                           # 폰 규칙은 mobile_ui 에만

    def test_page_places_it_after_fx_and_reuses_ranking(self):
        page = (ROOT / "pages" / "12_자비스13.py").read_text(encoding="utf-8")
        block = page.split("        _fx_cell(),")[1][:600]
        self.assertIn("jarvis13_sector_map.cell_html(jarvis13_shared.peek(\"theme_rankings\"", block)
        self.assertIn('jarvis13_shared.put("theme_rankings", ranking)', page)
        self.assertIn("st.markdown(jarvis13_sector_map.CSS, unsafe_allow_html=True)", page)


if __name__ == "__main__":
    unittest.main()

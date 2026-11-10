"""한국 「시장 현황」 — 네이버 증시 현황처럼 시장 전체 업종 지도 (2026-11-05 상하님 「미국테마처럼 하라고 한국테마도 배치도」 · 「이거 네이버다」)."""
from __future__ import annotations

import ast
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import jarvis13_market_map as mm
import jarvis13_sector_map as sm

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("j13_render_audit", ROOT / "research" / "j13_render_audit.py")
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)

LIVE = [
    {"no": "278", "name": "반도체와반도체장비", "change": -7.89, "rise": 20, "steady": 3, "fall": 150},
    {"no": "999", "name": "기타", "change": -2.05, "rise": 400, "steady": 90, "fall": 600},
    {"no": "261", "name": "제약", "change": 4.49, "rise": 120, "steady": 10, "fall": 40},
    {"no": "301", "name": "크기 모름", "change": 1.0, "rise": 1, "steady": 0, "fall": 0},
]
SIZES = {"278": {"name": "반도체와반도체장비", "mcap": 24_734_435.0}, "999": {"name": "기타", "mcap": 2_476_188.0},
         "261": {"name": "제약", "mcap": 1_993_060.0}, "301": {"name": "크기 모름", "mcap": None}}


class MarketMapTests(unittest.TestCase):
    def test_snapshot_sizes_by_market_cap_and_counts_the_whole_market(self):
        snap = mm.snapshot(LIVE, SIZES)
        self.assertEqual(["반도체와반도체장비", "기타", "제약"], [row["name"] for row in snap["rows"]])   # 큰 순 · 크기 모르면 뺌
        self.assertEqual(-7.89, snap["rows"][0]["change"])
        self.assertEqual({"up": 541, "flat": 103, "down": 790, "total": 1434}, snap["breadth"])    # 업종마다 센 것을 더함
        self.assertIsNone(mm.snapshot(LIVE, {}))                                                   # 크기 자료가 없으면 None(테마 지도로)

    def test_market_cell_is_market_status_with_theme_strip_and_breadth(self):
        ranking = {"rows": [{"name": "인터넷 대표주", "change_pct": 9.69, "ok": True}]}
        html_text = sm.cell_html(ranking, market=mm.snapshot(LIVE, SIZES))
        for text in ("시장 현황", "칸 크기 = 한국 시장에서 차지하는 몫", "반도체와반도체장비", "-7.89%", "자비스 테마 상위 5",
                     "인터넷 대표주", "▲ 오름 541", "▼ 내림 790", "한국 시장 전체 1,434종목 기준(네이버)"):
            self.assertIn(text, html_text)
        self.assertNotIn("강한 테마 지도", html_text)
        self.assertEqual([], audit.markdown_problems(sm.CSS + "\n" + html_text))                    # 스트림릿에서 안 깨짐(CLAUDE.md 0-4)

    def test_falls_back_to_the_theme_map_without_sector_data(self):
        ranking = {"rows": [], "all_scored": [{"name": "반도체", "change_pct": 1.0, "stocks": [{"code": "005930", "trading_value": 5.0, "change_pct": 1.0}]}]}
        self.assertIn("강한 테마 지도", sm.cell_html(ranking, market=None))
        self.assertIn("강한 테마 지도", sm.cell_html(ranking))

    def test_sizes_file_and_the_real_collected_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "kr_sectors.json"
            path.write_text(json.dumps({"sectors": [{"no": "278", "name": "반도체", "mcap": 10.5}]}), encoding="utf-8")
            self.assertEqual({"278": {"name": "반도체", "mcap": 10.5}}, mm.sizes(path))
        real = mm.sizes()                                                                          # 깃허브가 모은 파일(2026-11-05 · 79업종)
        self.assertGreaterEqual(len(real), 70)
        self.assertTrue(all(v["mcap"] for v in real.values()))

    def test_no_link_to_old_jarvis_files(self):
        tree = ast.parse((ROOT / "jarvis13_market_map.py").read_text(encoding="utf-8"))
        mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        mods |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        self.assertTrue(mods <= {"__future__", "json", "threading", "pathlib", "requests"}, mods)

    def test_phone_order_follows_jarvis12(self):
        # 폰 · 태블릿(1200px 이하) — 얼린 폰 규칙이 게이지를 차례 10 으로 보낸다. 자비스12 처럼 원/달러 → 시장 현황 → 시장 국면(한국)
        # → 미국 지수(미국 국면 · 공포탐욕은 10 그대로).
        block = sm.CSS.split("@media (max-width:1200px){", 1)[1].split("\n}", 1)[0]
        for rule in (".j4-top-row > .j13-sector-map{order:5}", ".j4-top-row > .j13-kr-phase{order:6}",
                     ".j4-top-row > .j13-us-idx{order:7}"):
            self.assertIn(rule, block)
        page = (ROOT / "pages" / "12_자비스13.py").read_text(encoding="utf-8")
        self.assertIn("\"<div class='fg-box'>\", \"<div class='fg-box j13-kr-phase'>\", 1)", page)
        self.assertIn("\"<div class='j4-top-cell'\", \"<div class='j4-top-cell j13-us-idx'\", 1) for cell in _us_index_cells()", page)
        # PC(1201px 이상)는 숫자 칸 뒤에서 줄을 끊는다(첫 줄에 시장 국면이 같이 서면 선물 제목이 두 줄로 접혔다) · 폰 · 태블릿은 안 그림
        self.assertIn(".j13-top-break{display:none}", sm.CSS)
        self.assertIn("@media (min-width:1201px){.j4-top-row > .j13-top-break{display:block;flex:0 0 100%;height:0;", sm.CSS)
        self.assertNotIn("j13-top-break", block)
        import regime_gauge_ui                                                                     # 바꿔 끼우는 앞머리가 그대로인지
        self.assertTrue(regime_gauge_ui.regime_box_html(None, title="시장 국면 (한국)").startswith("<div class='fg-box'>"))

    def test_page_passes_the_market_map_and_guards_revisions(self):
        page = (ROOT / "pages" / "12_자비스13.py").read_text(encoding="utf-8")
        self.assertIn("market=_kr_market_map()", page)
        self.assertIn(f"_REQUIRED_J13_SECTOR_MAP_REVISION = {sm.MODULE_REVISION}", page)
        self.assertIn(f"_REQUIRED_J13_MARKET_MAP_REVISION = {mm.MODULE_REVISION}", page)


if __name__ == "__main__":
    unittest.main()

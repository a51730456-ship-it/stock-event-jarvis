"""한국 「시장 현황」 — 네이버 증시 현황처럼 시장 전체 업종 지도 (2026-11-05 상하님 「미국테마처럼 하라고 한국테마도 배치도」 · 「이거 네이버다」)."""
from __future__ import annotations

import ast
import importlib.util
import json
import tempfile
import threading
import time
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
    def setUp(self):
        with mm._LIVE_LOCK:
            mm._LIVE.update(rows=None, at=0.0, tried=0.0, busy=False)

    def _settle(self):
        for _ in range(300):
            with mm._LIVE_LOCK:
                if not mm._LIVE["busy"]:
                    return
            time.sleep(0.01)
        self.fail("뒤에서 받는 일이 안 끝남")

    def _pass_55_seconds(self):
        with mm._LIVE_LOCK:
            mm._LIVE["tried"] -= 60

    def test_live_rows_never_makes_the_screen_wait_once_a_value_exists(self):
        # CLAUDE.md 0-0 ① — 55초 지난 값이면 뒤에서 새로 받고 화면은 있던 값을 바로 쓴다(전 판은 55초마다 한 판이 네이버를 기다렸다)
        calls = []
        self.assertEqual(LIVE, mm.live_rows(lambda: calls.append("first") or LIVE))      # 값이 아예 없을 때만 받을 때까지 기다림
        self._settle()
        release = threading.Event()

        def slow():
            calls.append("slow")
            release.wait(5)
            return LIVE[:1]

        self._pass_55_seconds()
        started = time.time()
        self.assertEqual(LIVE, mm.live_rows(slow))                                       # 받는 동안 있던 값으로 바로
        self.assertLess(time.time() - started, 0.5)
        self.assertEqual(LIVE, mm.live_rows(slow))                                       # 받는 중에는 또 받으러 가지 않음
        release.set()
        self._settle()
        self.assertEqual(LIVE[:1], mm.live_rows(slow))                                   # 다 받으면 새 값
        self.assertEqual(["first", "slow"], calls)

    def test_live_rows_keeps_the_old_value_on_failure_and_retries_once_per_55_seconds(self):
        # CLAUDE.md 0-0 ② — 못 받았다고 있던 값을 지우지 않는다 · 전 판은 못 받으면 판마다 다시 받으러 갔다(한 번에 길어야 6초)
        mm.live_rows(lambda: LIVE)
        self._settle()
        calls = []

        def broken():
            calls.append(1)
            raise RuntimeError("네이버 안 됨")

        self._pass_55_seconds()
        for _ in range(5):
            self.assertEqual(LIVE, mm.live_rows(broken))
            self._settle()
        self.assertEqual(1, len(calls))
        self._pass_55_seconds()
        self.assertEqual(LIVE, mm.live_rows(broken))
        self._settle()
        self.assertEqual(2, len(calls))

    def test_first_visit_waits_at_most_first_wait(self):
        release = threading.Event()

        def hang():
            release.wait(5)
            return LIVE

        started = time.time()
        self.assertIsNone(mm.live_rows(hang, first_wait=0.3))                            # 늦으면 길어야 0.3초 뒤 None(테마 지도로)
        self.assertLess(time.time() - started, 1.0)
        self.assertIsNone(mm.snapshot(None, SIZES))
        release.set()
        self._settle()
        self.assertEqual(LIVE, mm.live_rows(hang))                                       # 다음 판에는 채워짐

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
        self.assertTrue(mods <= {"__future__", "json", "threading", "time", "pathlib", "requests"}, mods)

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
        self.assertIn("return jarvis13_market_map.snapshot(jarvis13_market_map.live_rows())", page)   # 화면은 받는 것을 안 기다림
        self.assertNotIn("kr_industry", page)
        self.assertIn(f"_REQUIRED_J13_SECTOR_MAP_REVISION = {sm.MODULE_REVISION}", page)
        self.assertIn(f"_REQUIRED_J13_MARKET_MAP_REVISION = {mm.MODULE_REVISION}", page)


if __name__ == "__main__":
    unittest.main()

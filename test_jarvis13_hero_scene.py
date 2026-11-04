"""한국테마 머리 띠 배경 — 여의도 밤 · 코스피 캔들 (2026-11-05 상하님 「한국 주식 배경 동영상 … 미국테마와 구분하자」)."""
from __future__ import annotations

import importlib.util
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import jarvis13_hero as hero
import jarvis13_hero_scene as scene
import jarvis13_home as home

ROOT = Path(__file__).resolve().parent
PAGE = ROOT / "pages" / "12_자비스13.py"
_spec = importlib.util.spec_from_file_location("j13_render_audit", ROOT / "research" / "j13_render_audit.py")
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


class SceneTests(unittest.TestCase):
    def test_svg_is_well_formed_and_light(self):
        for variant in ("market", "watch"):
            svg = scene.scene_svg(variant)
            ET.fromstring(svg)                                   # 글 짜임이 맞다
            self.assertLess(len(svg.encode("utf-8")), 80_000)    # 미국 영상(2.8MB)과 달리 가볍다
            self.assertNotIn("\n", svg)                          # 한 줄 — 스트림릿이 문단으로 쪼개지 않는다

    def test_korean_colors_and_no_us_assets(self):
        svg = scene.scene_svg("market")
        self.assertEqual(("#ff4d5e", "#3d8bff"), (scene.UP, scene.DOWN))       # 오름 빨강 · 내림 파랑
        self.assertIn(f'fill="{scene.UP}"', svg)
        self.assertIn(f'fill="{scene.DOWN}"', svg)
        for text in (hero.css() + hero.html("13"), home.hero_html([{"code": "005930", "name": "삼성전자"}])):
            for us in ("hero_snow_camp", "hero_scene", "catbus", "<video"):
                self.assertNotIn(us, text)

    def test_names_are_j13k_only(self):
        svg = scene.scene_svg("market")
        ids = re.findall(r'id="([^"]+)"', svg)
        classes = [c for group in re.findall(r'class="([^"]+)"', svg) for c in group.split()]
        self.assertTrue(ids and all(i.startswith("j13k") for i in ids), ids)
        self.assertTrue(all(c.startswith("j13k") for c in classes), classes)
        self.assertNotIn("j3b-", scene.CSS)
        self.assertNotIn("j12", scene.CSS)

    def test_candles_loop_without_a_seam_and_mostly_rise(self):
        rows = scene._series(56, 211)
        self.assertAlmostEqual(rows[0][0], rows[-1][3], places=9)          # 끝 값 = 처음 값 → 이어 붙여도 안 끊김
        rise = rows[:round(56 * .85)]
        self.assertGreaterEqual(sum(1 for o, h, l, c in rise if c >= o) / len(rise), .6)
        for opened, high, low, close in rows:
            self.assertGreaterEqual(high, max(opened, close))
            self.assertLessEqual(low, min(opened, close))

    def test_motion_stops_for_reduced_motion_and_uses_transform_opacity(self):
        self.assertIn("prefers-reduced-motion:reduce", scene.CSS)
        keyframes = re.findall(r"@keyframes [\w-]+\{(.*?)\}\}", scene.CSS)
        self.assertTrue(keyframes)
        for body in keyframes:
            props = set(re.findall(r"([a-z-]+):", body))
            self.assertTrue(props <= {"transform", "opacity"}, props)     # 폰이 덜 힘든 것만


class HeroTests(unittest.TestCase):
    def test_same_outer_shape_so_exit_and_refresh_still_attach(self):
        page = hero.html("13")
        for part in ('<div class="j3hero j13k-hero">', '<p class="j3hero-mark">JARVIS <b>13</b></p>',
                     '<div class="j3hero-actions"><span class="j3hero-round">↻</span>'):
            self.assertIn(part, page)                     # jarvis13_exit 가 .j3hero + 「13」 을 보고 ✕ 를 붙인다
        import hero_banner
        self.assertEqual(hero_banner.BOX_KEY, hero.BOX_KEY)   # ↻ 겹치기 규칙(얼린 꾸밈)이 이 이름을 찾는다

    def test_no_broken_markdown(self):
        self.assertEqual([], audit.markdown_problems(hero.css() + hero.html("13")))
        self.assertEqual([], audit.markdown_problems(home.hero_html([{"code": "005930", "name": "삼성전자"}])))

    def test_page_uses_the_korean_hero_and_guards_revisions(self):
        source = PAGE.read_text(encoding="utf-8")
        self.assertIn('jarvis13_hero.render(st, refresh_key="j13hero_refresh", mark="13")', source)
        self.assertNotIn("hero_banner.render(st", source)
        self.assertIn(f"_REQUIRED_J13_HERO_REVISION = {hero.MODULE_REVISION}", source)
        self.assertGreaterEqual(scene.MODULE_REVISION, hero.MODULE_REVISION)
        self.assertIn(f"_REQUIRED_J13_HOME_REVISION = {home.MODULE_REVISION}", source)


if __name__ == "__main__":
    unittest.main()

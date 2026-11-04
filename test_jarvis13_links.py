"""자비스13 이 옛 자비스(1~11) 파일에 **새로 이어지지 않는지** 본다 (2026-11-05 상하님 「과거 자비스 1~11까지 링크시키지 말아야
된다 · 참고해서 코딩하는 것은 괜찮다」).

옛 자비스 파일 = 자비스3 · 자비스4 가 쓰는 얼린 파일(jarvis3_frozen.json · jarvis4_frozen.json)과 옛 화면 파일(pages/ 의 자비스1~11).
자비스13 은 처음 만들 때(2026-10-30 · 자비스4 를 베낌) 옛 시세 엔진 · 판단 · 설명서 파일을 **부르기만** 하게 짜였다(CLAUDE.md 0-3).
그 연결은 아래 목록(_INHERITED)에 못박는다 — **줄이기만 하고 늘리지 않는다.** 새로 만드는 것은 옛 파일을 보고 베껴 자비스13 전용
파일(jarvis13_*)로 쓴다. 2026-11-05 시장분석 띠가 hero_banner(자비스3 띠)를 부르던 것을 끊었다(jarvis13_hero 로 베낌).
"""
from __future__ import annotations

import ast
import glob
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# 2026-11-05 지금 남아 있는 옛 연결(파일 → 부르는 옛 파일). 끊으면 여기서도 지운다. **더하지 않는다.**
_INHERITED = {
    "pages/12_자비스13.py": {"auth", "build_stamp", "fear_greed_ui", "gauge_ui", "guidance", "jarvis4_data", "jarvis4_store",
                            "login_prism", "market_signal_ui", "method_help", "mobile_ui", "page_access", "picklist_store",
                            "picklist_ui", "regime_gauge_ui", "us_index_data"},
    "jarvis13_flow_card.py": {"gauge_ui", "market_signal_ui"},
    "jarvis13_market.py": {"jarvis4_data"},
    "jarvis13_picklist_ui.py": {"picklist_ui"},
    "jarvis13_watch_store.py": {"database", "db_runtime"},
}


def _old_files() -> set:
    names = set()
    for frozen in ("jarvis3_frozen.json", "jarvis4_frozen.json"):
        data = json.loads((ROOT / frozen).read_text(encoding="utf-8"))
        table = data.get("files") if isinstance(data, dict) and isinstance(data.get("files"), dict) else data
        names |= {Path(name).stem for name in table if str(name).endswith(".py") and not str(name).startswith("pages/")}
    return names


def _imports(path: Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    return mods


class Jarvis13LinkTests(unittest.TestCase):
    def test_no_new_links_to_old_jarvis(self):
        old = _old_files()
        self.assertIn("hero_banner", old)                     # 목록이 제대로 읽혔다
        files = ["pages/12_자비스13.py"] + sorted(glob.glob(str(ROOT / "jarvis13_*.py")))
        new_links = {}
        for name in files:
            path = Path(name) if Path(name).is_absolute() else ROOT / name
            key = str(path.relative_to(ROOT))
            linked = _imports(path) & old
            extra = linked - _INHERITED.get(key, set())
            if extra:
                new_links[key] = sorted(extra)
        self.assertEqual({}, new_links, "옛 자비스 파일에 새로 이었다 — 보고 베껴 jarvis13_* 전용 파일로 쓴다(CLAUDE.md 0-5)")

    def test_inherited_list_only_shrinks(self):
        # 끊은 연결이 목록에 남아 있으면 목록을 줄인다(다시 이을 길을 열어 두지 않게)
        old = _old_files()
        stale = {}
        for key, allowed in _INHERITED.items():
            linked = _imports(ROOT / key) & old
            gone = allowed - linked
            if gone:
                stale[key] = sorted(gone)
        self.assertEqual({}, stale, "끊은 연결은 _INHERITED 에서도 지운다")

    def test_no_link_to_old_pages(self):
        # 옛 화면 파일(pages/ 자비스1~11)을 부르거나 그리로 보내지 않는다
        page = (ROOT / "pages" / "12_자비스13.py").read_text(encoding="utf-8")
        code = "\n".join(line for line in page.splitlines() if not line.lstrip().startswith("#"))
        for old_page in ("0_시장판단", "1_자비스2", "2_자비스3", "3_자비스4", "4_자비스5", "5_자비스6", "6_자비스6_미국테마",
                         "7_자비스7", "8_자비스8", "9_자비스10", "10_자비스11"):
            self.assertNotIn(f"pages/{old_page}.py", code)


if __name__ == "__main__":
    unittest.main()

"""자비스4 지킴이 (2026-10-30 상하님 「둘 다 해라」 — 한국테마는 자비스4 를 베낀 자비스13 에서 고친다).

자비스4 화면 파일과 자비스4 가 쓰는 파일(직접·간접) 중 하나라도 바뀌면 이 시험이 실패한다.
실패하면 **올리지 않는다.** 어떻게 하는지는 tools/freeze_jarvis4.py.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
import freeze_jarvis4  # noqa: E402


class Jarvis4FrozenTests(unittest.TestCase):
    def test_jarvis4_and_every_file_it_uses_are_unchanged(self):
        record = json.loads((ROOT / "jarvis4_frozen.json").read_text(encoding="utf-8"))["files"]
        now = freeze_jarvis4.current(ROOT)
        changed = sorted(name for name in set(record) | set(now) if record.get(name) != now.get(name))
        self.assertEqual(
            [], changed,
            "자비스4 가 쓰는 파일이 바뀌었다 — 자비스4 는 상하님이 고치라고 하시기 전에는 손대지 않는다. "
            "자비스13 을 고치다 생긴 것이면 되돌리고 자비스13 전용 사본(jarvis13_*.py)을 만들어 고칠 것. "
            "상하님이 자비스4 를 고치라고 하신 것이면 python tools/freeze_jarvis4.py 로 지문을 다시 적을 것.")

    def test_the_guard_watches_the_page_and_the_shared_files(self):
        names = freeze_jarvis4.closure(ROOT)
        self.assertEqual("pages/3_자비스4.py", names[0])
        for shared in ("jarvis4_data.py", "jarvis4_store.py", "mobile_ui.py", "picklist_ui.py", "scroll_to.py",
                       "back_nav.py", "method_help.py", "market_signal_ui.py"):
            self.assertIn(shared, names)
        for free in ("pages/12_자비스13.py", "jarvis13_picklist_ui.py", "jarvis13_scroll_to.py", "jarvis13_back_nav.py"):
            self.assertNotIn(free, names)          # 자비스13 과 그 사본은 지킴이 밖 — 마음껏 고친다


if __name__ == "__main__":
    unittest.main()

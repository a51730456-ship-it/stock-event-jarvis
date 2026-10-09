"""자비스3 지킴이 (2026-10-09 상하님 지시).

상하님 — *"자비스3 을 자비스12 에 그대로 복사한 뒤 자비스3 을 건들이지 않도록"*.
자비스3 화면 파일과 자비스3 이 쓰는 파일(직접·간접) 중 하나라도 바뀌면 이 시험이 실패한다.
실패하면 **올리지 않는다.** 어떻게 하는지는 CLAUDE.md 0-2 · tools/freeze_jarvis3.py.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
import freeze_jarvis3  # noqa: E402


class Jarvis3FrozenTests(unittest.TestCase):
    def test_jarvis3_and_every_file_it_uses_are_unchanged(self):
        record = json.loads((ROOT / "jarvis3_frozen.json").read_text(encoding="utf-8"))["files"]
        now = freeze_jarvis3.current(ROOT)
        changed = sorted(name for name in set(record) | set(now) if record.get(name) != now.get(name))
        self.assertEqual(
            [], changed,
            "자비스3 이 쓰는 파일이 바뀌었다 — 자비스3 은 상하님이 고치라고 하시기 전에는 손대지 않는다"
            "(CLAUDE.md 0-2). 자비스12 를 고치다 생긴 것이면 되돌리고 자비스12 전용 사본을 만들어 고칠 것. "
            "상하님이 자비스3 을 고치라고 하신 것이면 python tools/freeze_jarvis3.py 로 지문을 다시 적을 것.")

    def test_the_guard_watches_the_page_and_the_shared_files(self):
        names = freeze_jarvis3.closure(ROOT)
        self.assertEqual("pages/2_자비스3.py", names[0])
        for shared in ("jarvis3_data.py", "us_fundamentals.py", "mobile_ui.py", "scorecard_compare.py", "scroll_to.py"):
            self.assertIn(shared, names)
        self.assertNotIn("pages/11_자비스12.py", names)          # 자비스12 는 지킴이 밖 — 마음껏 고친다


if __name__ == "__main__":
    unittest.main()

"""화면 맨 밑 「판」 표시 (2026-09-02 상하님 지시).

상하님 — "너는 어디서 어디까지 반영을 했는지 안 했는지 몰라서 걱정된다고 했잖아."
폰(온라인)과 노트북을 나란히 놓고 같은 판인지 가르시는 자리다.
"""

from __future__ import annotations

import pathlib
import unittest
from unittest.mock import patch

import build_stamp

ROOT = pathlib.Path(__file__).resolve().parent


class BuildStampTests(unittest.TestCase):
    def setUp(self):
        build_stamp._CACHE.clear()

    def tearDown(self):
        build_stamp._CACHE.clear()

    def test_it_reads_the_last_commit_that_touched_code(self):
        """**자료가 아니라 코드**가 언제 바뀌었나를 본다.

        이 저장소에는 자비스5 수집이 10분마다 커밋을 쌓는다. 그 번호를 적으면
        노트북과 온라인이 영영 다르게 보여 아무 쓸모가 없다.
        """
        source = (ROOT / "build_stamp.py").read_text(encoding="utf-8")
        self.assertIn('"*.py"', source.replace("'", '"'), "코드 파일만 보지 않는다")
        # git 에 넘기는 말에 `--` 뒤 경로가 들어가야 그 파일만 센다.
        block = source.split("def _from_git(")[1].split("\ndef ")[0]
        self.assertIn('"--"', block, "경로를 안 넘겨 자료 커밋까지 센다")
        self.assertIn("_CODE_PATHS", block)

    def test_the_time_does_not_change_with_the_machine(self):
        """시각은 **커밋이 가진 시간대 그대로** 적는다.

        기계마다 바꿔 적으면(온라인 UTC · 노트북 한국시간) 같은 판인데 다른
        시각으로 보여, 견주시는 뜻이 없어진다.
        """
        block = (ROOT / "build_stamp.py").read_text(encoding="utf-8")
        block = block.split("def _from_git(")[1].split("\ndef ")[0]
        self.assertIn("--date=iso", block)
        self.assertNotIn("format-local", block)
        self.assertNotIn("astimezone", block)

    def test_it_says_something_even_when_git_is_gone(self):
        """git 이 없어도 **조용히** 물러선다. 화면이 죽으면 안 된다."""
        with patch.object(build_stamp, "_from_git", return_value=None), \
             patch.object(build_stamp, "_from_git_files", return_value=None):
            text = build_stamp.stamp()
        self.assertTrue(text)
        self.assertIn("파일 시각", text)

    def test_a_broken_stamp_never_breaks_the_screen(self):
        """무엇이 터져도 화면은 그대로 돈다."""
        class _Fake:
            def __init__(self):
                self.said = []

            def markdown(self, text, **kwargs):
                self.said.append(text)

        st = _Fake()
        build_stamp.render(st)
        self.assertTrue(st.said)
        self.assertIn("jarvis-build", st.said[0])
        self.assertIn("판 ", st.said[0])

        with patch.object(build_stamp, "stamp", side_effect=RuntimeError("boom")):
            build_stamp.render(st)          # 터지면 안 된다

    def test_both_screens_show_it_at_the_very_bottom(self):
        """어디로 갈까요 화면과 미국테마 화면 **맨 밑**에 있어야 한다.

        로그인 화면에는 안 넣는다 — 그 화면은 가장 빨리 떠야 한다(CLAUDE.md 0-0).
        """
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("build_stamp.render(st)", app)
        # 어디로 갈까요 화면을 끝내는 st.stop() **바로 앞**이어야 한다.
        entry = app[app.index('key="entry_go"'):]
        self.assertLess(entry.index("build_stamp.render(st)"), entry.index("st.stop()"))

        page = (ROOT / "pages" / "2_자비스3.py").read_text(encoding="utf-8")
        self.assertIn("build_stamp.render(st)", page)
        # 맨 밑이라는 것 — 화면을 다 그린 뒤(scroll_to.run) 다음이다.
        self.assertLess(page.index("scroll_to.run(st)"),
                        page.index("build_stamp.render(st)"))


if __name__ == "__main__":
    unittest.main()

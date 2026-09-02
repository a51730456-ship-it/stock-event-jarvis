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

    def test_every_screen_shows_it(self):
        """**모든 화면**에 있어야 한다 (2026-09-02 상하님 — "판 숫자 안 보인다").

        처음에는 「어디로 갈까요」와 미국테마 둘에만 넣었다. 그랬더니 로그인
        화면·한국테마에서는 안 보여 "안 보인다"는 말씀이 나왔다. 한 화면이라도
        빠지면 그 화면에서는 또 못 가르신다.
        """
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        # 로그인 화면과 「어디로 갈까요」 둘 다 — 각각 st.stop() 앞에 있다.
        self.assertGreaterEqual(app.count("build_stamp.render(st)"), 2,
                                "로그인 화면이나 어디로 갈까요에 빠졌다")
        entry = app[app.index('key="entry_go"'):]
        self.assertLess(entry.index("build_stamp.render(st)"), entry.index("st.stop()"))

        for name in ("0_시장판단.py", "1_자비스2.py", "2_자비스3.py",
                     "3_자비스4.py", "4_자비스5.py", "5_자비스6.py"):
            page = (ROOT / "pages" / name).read_text(encoding="utf-8")
            self.assertIn("build_stamp.render(st)", page, f"{name} 에 판 표시가 없다")

        # 미국·한국테마는 화면을 다 그린 뒤(scroll_to.run) 다음이어야 한다.
        for name in ("2_자비스3.py", "3_자비스4.py"):
            page = (ROOT / "pages" / name).read_text(encoding="utf-8")
            self.assertLess(page.index("scroll_to.run(st)"),
                            page.index("build_stamp.render(st)"))

    def test_it_is_big_enough_to_see(self):
        """어두운 바탕에서 **눈에 띄어야** 한다 — 안 보이면 쓸모가 없다."""
        css = build_stamp.CSS
        self.assertIn("border", css)
        self.assertNotIn("#6e7480", css)      # 처음의 흐린 회색
        size = css.split("font-size:")[1].split("rem")[0].strip()
        self.assertGreaterEqual(float(size), 0.85, "글자가 아직 너무 작다")


if __name__ == "__main__":
    unittest.main()

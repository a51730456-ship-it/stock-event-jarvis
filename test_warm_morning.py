"""깨우기(warm_morning) — 자비스12 도 열고, 코드를 올린 뒤에도 돌고, 새로 켜진 앱을 보고 데운다 (2026-10-10 상하님 지시)."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT = (ROOT / "warm_morning.py").read_text(encoding="utf-8")
FLOW = (ROOT / ".github" / "workflows" / "warm_morning.yml").read_text(encoding="utf-8")
J12 = (ROOT / "pages" / "11_자비스12.py").read_text(encoding="utf-8")


class WarmMorningTests(unittest.TestCase):
    def test_jarvis12_first_then_jarvis3_through_the_bottom_bar(self):
        """「깨우기 자비스12도 열고」 — 자비스12 먼저. 시장분석은 밑 막대 단추로(자비스3 넘기기 단추에 기대지 않는다)."""
        names = re.findall(r'\("(자비스\d+)", f"\{BASE\}/', SCRIPT)
        self.assertEqual(["자비스12", "자비스3"], names)
        body = SCRIPT[SCRIPT.index("def _warm_page("):SCRIPT.index("def main()")]
        self.assertIn('_click_key(page, "j3b_nav_market")', body)
        self.assertNotIn("시장분석으로", body)

    def test_runs_after_code_uploads(self):
        """「올린 뒤에도 돌게」 — push 로도 돈다. 판 표시가 보는 파일과 같은 것이 바뀐 올리기에만."""
        self.assertIn("  push:\n    branches: [master]\n    paths: [\"**.py\", \"**.bat\", \"**.toml\"]", FLOW)
        self.assertIn("git log -1 --format=%h FETCH_HEAD -- '*.py' 'pages/*.py' '*.bat' '*.toml'", FLOW)

    def test_after_a_list_save_it_waits_for_a_restarted_app_not_the_stamp(self):
        """목록 저장 뒤 16~26분 → 새로 켜진 앱을 보고 바로 (2026-10-10 상하님 「고쳐라」)."""
        step = FLOW[FLOW.index("- name: 앱 깨우기"):]
        # 판 표시(WAIT_FOR_SHA)는 push 일 때만 — 저장은 자료만 올려 판 표시가 안 바뀐다.
        sha = step.index('export WAIT_FOR_SHA=')
        self.assertLess(step.index('if [ "${{ github.event_name }}" = "push" ]; then'), sha)
        self.assertLess(sha, step.index("          fi"))
        self.assertNotIn("git rev-parse --short=7 FETCH_HEAD", step)
        self.assertIn('export WAIT_FOR_BOOT_AFTER="$(git log -1 --format=%ct FETCH_HEAD)"', step)
        wait = SCRIPT[SCRIPT.index("def _wait_for_restart("):SCRIPT.index("def _warm_page(")]
        self.assertIn("booted >= after", wait)
        self.assertIn("return False", wait)              # 표시가 없거나 한도가 차면 기다리지 않고 데운다
        self.assertIn('os.environ.get("RESTART_WAIT_LIMIT") or 480', SCRIPT)

    def test_jarvis12_hides_its_start_time_inside_the_bottom_bar_text(self):
        """켜진 시각은 서버 기억(cache_resource)에 — 앱이 껐다 켜질 때만 바뀐다. 새 칸을 만들지 않게 밑 막대 글 안에 숨긴다."""
        head = J12[:J12.index("def _app_booted_at(")]
        self.assertTrue(head.rstrip().endswith("@st.cache_resource(show_spinner=False)"))
        nav = J12[J12.index("def _render_briefing_bottom_nav("):]
        nav = nav[:nav.index("with st.container(")]
        self.assertIn('<span class="j12-boot" hidden style="display:none">', nav)
        self.assertIn("st.markdown(f'<nav class=\"j3b-bottom-nav\">{items}</nav>{boot}', unsafe_allow_html=True)", nav)
        self.assertEqual(1, nav.count("st.markdown("))     # 따로 한 칸 더 그리면 칸 사이 틈 12px 이 붙는다
        self.assertIn("'.j12-boot'", SCRIPT)


if __name__ == "__main__":
    unittest.main()

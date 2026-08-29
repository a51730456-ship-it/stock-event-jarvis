# -*- coding: utf-8 -*-
"""화면을 그 자리로 내려 주는 장치 (2026-08-29 상하님 지적 두 가지).

상하님 —
  ① *"상승장 신고가 눌림 매수 종목에서 종목을 처음 클릭하면 선택종목 세부사항으로
     화면이 밑으로 내려가는데, 두 번째 종목 세 번째 종목을 클릭하면 다시 안
     내려간다."*
  ② *"처음 시장분석 눌러 들어가면 화면 보면서 밑으로 내려가고 있는데 20개 테마
     실시간 순위 이 부분을 로딩하면서 또다시 맨 위 화면으로 올라가버린다."*

①은 **보내는 글이 지난번과 똑같아서** 브라우저가 iframe 을 다시 안 연 것이었다.
②는 **적어 둔 표시가 판 끝에서 쓰였기** 때문이다.

진짜 브라우저 없이도 두 규칙을 굳혀 둔다.
"""

import unittest

import scroll_to


class _FakeSt:
    def __init__(self):
        self.session_state = {}


class ScrollToTests(unittest.TestCase):
    def setUp(self):
        # 실제로 보내는 자리(components.html)만 잠깐 바꿔 끼워, 무엇을 몇 번
        # 보냈는지 적어 둔다. 화면은 띄우지 않는다.
        import streamlit.components.v1 as components

        self.sent = []
        self.components = components
        self._real_html = components.html
        components.html = lambda body, height=0: self.sent.append(body)

    def tearDown(self):
        self.components.html = self._real_html

    # ── ① 같은 자리로 두 번 불러도 두 번 다 내려가야 한다 ────────────────────
    def test_same_target_twice_sends_two_different_scripts(self):
        st = _FakeSt()
        scroll_to.request(st, "detail_pullback")
        scroll_to.run(st)
        scroll_to.request(st, "detail_pullback")
        scroll_to.run(st)
        self.assertEqual(2, len(self.sent), "두 번째는 아예 안 보냈다")
        self.assertNotEqual(
            self.sent[0], self.sent[1],
            "보낸 글이 똑같으면 화면이 iframe 을 다시 안 열어 스크립트가 안 돈다",
        )
        for body in self.sent:
            self.assertIn("jarvis-anchor-detail_pullback", body)

    def test_request_is_used_once(self):
        """한 번 쓰면 표시는 지워진다 — 다음 판에도 또 내려가면 화면이 붙잡힌다."""
        st = _FakeSt()
        scroll_to.request(st, "detail_top7")
        scroll_to.run(st)
        scroll_to.run(st)
        self.assertEqual(1, len(self.sent))

    def test_nothing_requested_sends_nothing(self):
        st = _FakeSt()
        scroll_to.run(st)
        self.assertEqual([], self.sent)

    # ── ② 바로 올리는 길 ─────────────────────────────────────────────────────
    def test_now_sends_at_once_and_clears_a_pending_request(self):
        st = _FakeSt()
        scroll_to.request(st, "top")          # 단추가 적어 둔 것이 남아 있어도
        scroll_to.now(st, "top")
        self.assertEqual(1, len(self.sent))
        self.assertIn("jarvis-anchor-top", self.sent[0])
        # 표시를 안 지우면 판 끝에서 **또** 올려 보시던 화면을 뿌리친다.
        self.assertNotIn(scroll_to.REQUEST_KEY, st.session_state)
        scroll_to.run(st)
        self.assertEqual(1, len(self.sent), "판 끝에서 또 올렸다")

    def test_now_hides_its_own_slot(self):
        """화면 한복판에 끼어드는 조각이라 제 칸을 스스로 숨겨야 한다.

        안 숨기면 스트림릿이 칸 사이에 넣는 16px 이 맨 위에 빈 줄로 남는다.
        """
        st = _FakeSt()
        scroll_to.now(st, "top")
        body = self.sent[0]
        self.assertIn("stElementContainer", body)
        self.assertIn('style.display = "none"', body)
        # 숨기는 것은 **내려간 뒤**다 — 먼저 숨기면 안 도는 브라우저가 있다.
        self.assertLess(body.index("go();"), body.index('style.display = "none"'))

    def test_broken_components_do_not_raise(self):
        """컴포넌트가 안 되면 조용히 넘어간다 — 화면이 죽으면 안 된다."""
        def _boom(body, height=0):
            raise RuntimeError("컴포넌트를 못 그린다")

        self.components.html = _boom
        st = _FakeSt()
        scroll_to.request(st, "top")
        scroll_to.run(st)          # 터지면 안 된다
        scroll_to.now(st, "top")   # 터지면 안 된다


if __name__ == "__main__":
    unittest.main()

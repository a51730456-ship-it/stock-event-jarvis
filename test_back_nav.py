# -*- coding: utf-8 -*-
"""폰·태블릿 뒤로가기 (2026-08-21 상하님 지시).

상하님 — "한번 누르면 밑으로 화면 내린 부분에서 바로 위로 가고,
두번 누르면 앞에 메뉴로."

진짜 브라우저 없이도 규칙을 굳혀 둔다. **몇 번을 눌러야 앞 메뉴로 나가는지가
언제나 같아야 한다**는 것이 이 파일이 지키는 전부다 — 상하님이 "어떨 때는 한 번만
눌러도 메인 메뉴로 간다"고 하신 것이 그 어긋남이었다.
"""

import unittest

import back_nav


class _FakeQueryParams(dict):
    """스트림릿 st.query_params 흉내 — 주소에 적힌 값 한 줄."""


class _FakeSt:
    def __init__(self, query=None):
        self.session_state = {}
        self.query_params = _FakeQueryParams(query or {})

    def go_back(self):
        """브라우저 뒤로가기 — 주소가 한 칸 앞으로 돌아간다."""
        self.query_params.pop("b", None)


class BackNavTests(unittest.TestCase):
    def test_first_screen_does_nothing(self):
        st = _FakeSt()
        self.assertEqual([], back_nav.sync(st))
        self.assertNotIn("b", st.query_params)

    def test_opening_something_leaves_one_mark(self):
        st = _FakeSt()
        back_nav.opened(st, "j3_pullback_open")
        self.assertEqual("1", st.query_params["b"])

    def test_opening_more_does_not_add_another_mark(self):
        """**칸은 하나만 쌓는다** — 안 그러면 몇 번 눌러야 나가는지 알 수 없다."""
        st = _FakeSt()
        back_nav.opened(st, "j3_pullback_open")
        back_nav.opened(st, "j3_detail_open_pullback",
                        "j3_intraday_open_pullback", "j3_bundle_open_pullback")
        back_nav.opened(st, "j3_theme_rank_open")
        self.assertEqual("1", st.query_params["b"], "기록이 여러 칸 쌓였다")
        self.assertEqual(5, len(back_nav.open_keys(st)))

    def test_one_press_closes_everything_that_was_opened(self):
        """**한 번 누르면** 열어 둔 것이 다 닫힌다 → 부르는 쪽이 화면을 맨 위로 올린다."""
        st = _FakeSt()
        back_nav.opened(st, "j3_pullback_open")
        back_nav.opened(st, "j3_detail_open_pullback", "j3_bundle_open_pullback")
        for key in back_nav.open_keys(st):
            st.session_state[key] = True

        st.go_back()
        closed = back_nav.sync(st)
        self.assertEqual({"j3_pullback_open", "j3_detail_open_pullback",
                          "j3_bundle_open_pullback"}, set(closed))
        for key in closed:
            self.assertFalse(st.session_state[key], key)

    def test_two_presses_always_reach_the_menu(self):
        """뒤로 한 번은 이 화면 안에서 쓰이고, **두 번째는 언제나 앞 메뉴**다."""
        st = _FakeSt()
        back_nav.opened(st, "a")
        back_nav.opened(st, "b2")
        back_nav.opened(st, "c")
        st.go_back()
        self.assertTrue(back_nav.sync(st), "첫 번째 누름이 이 화면에서 안 쓰였다")
        # 두 번째 누름은 여기서 할 일이 없다 = 브라우저가 앞 페이지로 나간다.
        self.assertEqual([], back_nav.sync(st))
        self.assertEqual([], back_nav.open_keys(st))

    def test_sync_does_not_touch_the_address(self):
        """뒤로가기로 닫을 때 주소를 또 쓰면 기록이 한 칸 더 쌓인다."""
        st = _FakeSt()
        back_nav.opened(st, "a")
        st.go_back()
        back_nav.sync(st)
        self.assertNotIn("b", st.query_params, "sync가 주소를 건드렸다")

    def test_nothing_happens_while_the_mark_is_still_there(self):
        st = _FakeSt()
        back_nav.opened(st, "a")
        st.session_state["a"] = True
        self.assertEqual([], back_nav.sync(st))
        self.assertTrue(st.session_state["a"])

    def test_broken_address_is_ignored(self):
        """주소를 못 읽어도 화면이 막히면 안 된다(CLAUDE.md 13번과 같은 뜻)."""
        st = _FakeSt()
        back_nav.opened(st, "a")
        st.session_state["a"] = True
        st.query_params["b"] = "뒤로"
        self.assertEqual([], back_nav.sync(st))
        self.assertTrue(st.session_state["a"])

    def test_query_params_failure_never_raises(self):
        class _Broken:
            def get(self, *a, **k):
                raise RuntimeError("주소를 못 읽는다")

            def __setitem__(self, *a):
                raise RuntimeError("주소를 못 쓴다")

            def pop(self, *a, **k):
                raise RuntimeError("주소를 못 지운다")

        st = _FakeSt()
        st.query_params = _Broken()
        back_nav.opened(st, "a")          # 터지면 안 된다
        self.assertEqual([], back_nav.sync(st))

    def test_reopening_after_a_back_press_marks_again(self):
        """뒤로 눌러 나갔다가 다시 열면, 그 화면에서 또 한 번은 위로 가야 한다."""
        st = _FakeSt()
        back_nav.opened(st, "a")
        st.go_back()
        back_nav.sync(st)
        back_nav.opened(st, "a")
        self.assertEqual("1", st.query_params["b"])

    def test_reset_clears_the_mark(self):
        st = _FakeSt()
        back_nav.opened(st, "a")
        back_nav.reset(st)
        self.assertEqual([], back_nav.open_keys(st))
        self.assertNotIn("b", st.query_params)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""폰·태블릿 뒤로가기 (2026-08-21 상하님 지시).

상하님 — "한번 누르면 방금 화면 전으로 가게 하고 두번 누르면 메인메뉴로."

진짜 브라우저 없이도 규칙을 굳혀 둔다. 주소와 세션 두 곳의 깊이가 어긋날 때
무엇을 닫는지가 이 파일이 지키는 전부다.
"""

import unittest

import back_nav


class _FakeQueryParams(dict):
    """스트림릿 st.query_params 흉내 — 주소에 적힌 값 한 줄."""


class _FakeSt:
    def __init__(self, query=None):
        self.session_state = {}
        self.query_params = _FakeQueryParams(query or {})


class BackNavTests(unittest.TestCase):
    def test_first_screen_has_no_depth(self):
        st = _FakeSt()
        self.assertEqual([], back_nav.sync(st))
        self.assertEqual([], back_nav.stack(st))

    def test_opening_a_section_writes_the_depth(self):
        st = _FakeSt()
        back_nav.opened(st, "j3_pullback_open")
        self.assertEqual("1", st.query_params["b"])
        back_nav.opened(st, "j3_detail_open_pullback")
        self.assertEqual("2", st.query_params["b"])

    def test_opening_the_same_section_twice_does_not_stack(self):
        """같은 구역을 여닫을 때마다 기록이 늘면 뒤로가기를 여러 번 눌러야 한다."""
        st = _FakeSt()
        back_nav.opened(st, "j3_pullback_open")
        back_nav.opened(st, "j3_pullback_open")
        self.assertEqual([["j3_pullback_open"]], back_nav.stack(st))
        self.assertEqual("1", st.query_params["b"])

    def test_one_press_closes_only_the_last_section(self):
        """**한 번 누르면 방금 연 것만 닫힌다.**"""
        st = _FakeSt()
        back_nav.opened(st, "j3_pullback_open")
        back_nav.opened(st, "j3_detail_open_pullback")
        st.session_state["j3_pullback_open"] = True
        st.session_state["j3_detail_open_pullback"] = True
        # 뒤로가기 — 브라우저가 주소를 한 칸 얕게 되돌린다.
        st.query_params["b"] = "1"
        self.assertEqual(["j3_detail_open_pullback"], back_nav.sync(st))
        self.assertFalse(st.session_state["j3_detail_open_pullback"])
        self.assertTrue(st.session_state["j3_pullback_open"], "위 구역까지 닫혔다")

    def test_two_presses_leave_the_first_screen(self):
        """**두 번 누르면 아무것도 안 열린 첫 화면**이 되고, 그다음이 메인이다."""
        st = _FakeSt()
        back_nav.opened(st, "j3_pullback_open")
        back_nav.opened(st, "j3_detail_open_pullback")
        st.session_state["j3_pullback_open"] = True
        st.session_state["j3_detail_open_pullback"] = True
        st.query_params["b"] = "1"
        back_nav.sync(st)
        st.query_params.pop("b")          # 주소가 …/자비스3으로 돌아왔다
        self.assertEqual(["j3_pullback_open"], back_nav.sync(st))
        self.assertFalse(st.session_state["j3_pullback_open"])
        self.assertEqual([], back_nav.stack(st))

    def test_sync_does_not_touch_the_address(self):
        """뒤로가기로 닫을 때 주소를 또 쓰면 방문기록이 한 칸 더 쌓인다."""
        st = _FakeSt()
        back_nav.opened(st, "a")
        back_nav.opened(st, "b2")
        st.query_params["b"] = "1"
        back_nav.sync(st)
        self.assertEqual("1", st.query_params["b"], "sync가 주소를 건드렸다")

    def test_forward_or_same_depth_changes_nothing(self):
        st = _FakeSt()
        back_nav.opened(st, "a")
        st.session_state["a"] = True
        st.query_params["b"] = "5"        # 앞으로 가기·이상한 값
        self.assertEqual([], back_nav.sync(st))
        self.assertTrue(st.session_state["a"])

    def test_broken_address_is_ignored(self):
        """주소를 못 읽어도 화면이 막히면 안 된다(CLAUDE.md 13번과 같은 뜻)."""
        st = _FakeSt({"b": "뒤로"})
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

    def test_one_click_that_opens_three_places_is_one_step_back(self):
        """종목을 누르면 상세·당일차트·일봉묶음이 같이 열린다 — **한 칸**이다."""
        st = _FakeSt()
        back_nav.opened(st, "j3_detail_open_pullback",
                        "j3_intraday_open_pullback", "j3_bundle_open_pullback")
        for key in ("j3_detail_open_pullback", "j3_intraday_open_pullback",
                    "j3_bundle_open_pullback"):
            st.session_state[key] = True
        self.assertEqual("1", st.query_params["b"])
        st.query_params.pop("b")
        self.assertEqual(["j3_detail_open_pullback"], back_nav.sync(st))
        for key in ("j3_detail_open_pullback", "j3_intraday_open_pullback",
                    "j3_bundle_open_pullback"):
            self.assertFalse(st.session_state[key], key)

    def test_reset_empties_the_record(self):
        st = _FakeSt()
        back_nav.opened(st, "a")
        back_nav.reset(st)
        self.assertEqual([], back_nav.stack(st))
        self.assertNotIn("b", st.query_params)


if __name__ == "__main__":
    unittest.main()

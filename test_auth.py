"""로그인 유지(쿠키) 핵심 로직 테스트.

실제 브라우저·쿠키 프런트엔드 없이 순수 로직만 굳힌다. 인증은 안전이 중요하므로
결정 규칙(_decide)과 토큰 생성(_expected_token)이 조용히 뒤집히지 않게 한다.
"""

import unittest
from unittest import mock

import auth


class DecideTests(unittest.TestCase):
    TOKEN = "abc123"

    def test_logged_in_and_cookie_matches_does_nothing(self):
        self.assertIsNone(auth._decide(True, self.TOKEN, self.TOKEN))

    def test_logged_in_but_cookie_missing_sets_cookie(self):
        self.assertEqual(auth._decide(True, None, self.TOKEN), "set")

    def test_logged_in_but_cookie_stale_resets_cookie(self):
        self.assertEqual(auth._decide(True, "old", self.TOKEN), "set")

    def test_logged_out_with_matching_cookie_restores(self):
        self.assertEqual(auth._decide(False, self.TOKEN, self.TOKEN), "restore")

    def test_logged_out_without_cookie_does_nothing(self):
        self.assertIsNone(auth._decide(False, None, self.TOKEN))

    def test_logged_out_with_wrong_cookie_does_not_restore(self):
        """엉뚱한 쿠키로는 절대 로그인이 되살아나면 안 된다."""
        self.assertIsNone(auth._decide(False, "forged", self.TOKEN))


class TokenTests(unittest.TestCase):
    def test_token_depends_on_password_and_hides_it(self):
        with mock.patch.object(auth.st, "secrets", {"APP_PASSWORD": "pw-one"}):
            t1 = auth._expected_token()
        with mock.patch.object(auth.st, "secrets", {"APP_PASSWORD": "pw-two"}):
            t2 = auth._expected_token()
        self.assertTrue(t1 and t2)
        self.assertNotEqual(t1, t2)                 # 비번이 다르면 토큰도 다르다
        self.assertNotIn("pw-one", t1)              # 비번이 토큰에 노출되지 않는다
        self.assertEqual(len(t1), 64)               # sha256 hex

    def test_token_is_stable_for_same_password(self):
        with mock.patch.object(auth.st, "secrets", {"APP_PASSWORD": "same"}):
            self.assertEqual(auth._expected_token(), auth._expected_token())

    def test_no_password_gives_no_token(self):
        with mock.patch.object(auth.st, "secrets", {}):
            self.assertIsNone(auth._expected_token())


class AccessRoleTests(unittest.TestCase):
    def test_guest_role_is_separate_from_owner_role(self):
        state = {}
        with mock.patch.object(auth.st, "session_state", state):
            auth.login_as_guest()
            self.assertTrue(state["authenticated"])
            self.assertTrue(auth.is_guest())
            auth.login_as_owner()
            self.assertTrue(state["authenticated"])
            self.assertFalse(auth.is_guest())
            self.assertEqual(state[auth.ACCESS_ROLE_KEY], auth.OWNER_ROLE)

    def test_guest_never_creates_owner_cookie(self):
        state = {"authenticated": True, auth.ACCESS_ROLE_KEY: auth.GUEST_ROLE}
        with mock.patch.object(auth.st, "session_state", state), \
             mock.patch.object(auth, "_controller", side_effect=AssertionError("cookie forbidden")):
            auth.sync_auth()
        self.assertEqual(state[auth.ACCESS_ROLE_KEY], auth.GUEST_ROLE)

    def test_clear_auth_removes_access_role(self):
        state = {"authenticated": True, auth.ACCESS_ROLE_KEY: auth.GUEST_ROLE}
        with mock.patch.object(auth.st, "session_state", state), \
             mock.patch.object(auth, "_controller", return_value=None):
            auth.clear_auth()
        self.assertNotIn("authenticated", state)
        self.assertNotIn(auth.ACCESS_ROLE_KEY, state)


if __name__ == "__main__":
    unittest.main()

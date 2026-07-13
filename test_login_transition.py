import socket
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).parent
SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")
EARTH_SVG = (ROOT / "assets" / "jarvis_earth.svg").read_text(encoding="utf-8")
TEST_PASSWORD = "jarvis-login-transition-test"


def _new_app():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=60)
    app.secrets["APP_PASSWORD"] = TEST_PASSWORD
    return app


def _overlay_count(app):
    return sum("jarvis-login-transition" in str(node.value) for node in app.markdown)


class LoginVisualContractTests(unittest.TestCase):
    def test_earth_is_small_local_svg_without_external_urls(self):
        self.assertLess((ROOT / "assets" / "jarvis_earth.svg").stat().st_size, 1_000_000)
        self.assertNotIn("http://", EARTH_SVG)
        self.assertNotIn("https://", EARTH_SVG)
        for marker in (
            "jarvis-earth-rotation-band",
            "jarvis-cloud-rotation-band",
            "jarvis-city-rotation-band",
            "jarvis-orbit-primary",
            "jarvis-atmosphere",
        ):
            self.assertIn(marker, EARTH_SVG)

    def test_transition_timing_responsive_and_reduced_motion_contract(self):
        for marker in (
            'st.session_state["login_transition_pending"] = True',
            'st.session_state.pop("login_transition_pending", None)',
            "ACCESS GRANTED",
            "JARVIS ONLINE",
            "인증 완료",
            "animation: jarvis-transition-overlay 1.2s",
            "pointer-events: none",
            "visibility: hidden",
            "@media (max-width: 1100px)",
            "@media (max-width: 640px)",
            "@media (prefers-reduced-motion: reduce)",
            "jarvis-transition-reduced .2s",
        ):
            self.assertIn(marker, SOURCE)
        self.assertNotIn("time.sleep(", SOURCE)
        self.assertNotIn("setTimeout(", SOURCE)


class LoginAppLifecycleTests(unittest.TestCase):
    @staticmethod
    def _socket_block():
        return patch.object(socket.socket, "connect", side_effect=AssertionError("external socket blocked"))

    def test_pre_auth_and_wrong_password_have_no_exceptions_or_network(self):
        app = _new_app()
        with self._socket_block():
            app.run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.text_input[0].key, "login_password_input")
            self.assertEqual(app.button[0].key, "login_submit")
            app.text_input[0].set_value("wrong-password")
            app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([error.value for error in app.error], ["비밀번호가 올바르지 않습니다."])
        self.assertIsNone(app.session_state.filtered_state.get("authenticated"))

    def test_success_transition_plays_once_and_normal_rerun_does_not_replay(self):
        app = _new_app()
        with self._socket_block():
            app.run()
            app.text_input[0].set_value(TEST_PASSWORD)
            app.button[0].click().run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(app.session_state.filtered_state.get("authenticated"))
        self.assertNotIn("login_transition_pending", app.session_state.filtered_state)
        self.assertEqual(_overlay_count(app), 1)
        self.assertTrue(any("ACCESS GRANTED" in str(node.value) for node in app.markdown))

        # The existing market auto-run is outside this feature; mark it complete so the
        # following rerun isolates the one-shot transition behavior.
        app.session_state["kr_auto_run_stage1_done"] = True
        app.session_state["kr_auto_run_stage2_done"] = True
        app.session_state["kr_theme_auto_fetch_pending"] = False
        with self._socket_block():
            app.run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(_overlay_count(app), 0)
        self.assertFalse(any("DuplicateWidgetID" in str(error.value) for error in app.exception))


if __name__ == "__main__":
    unittest.main()

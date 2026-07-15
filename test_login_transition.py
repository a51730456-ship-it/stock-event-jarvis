import socket
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).parent
SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")
VISUAL_SOURCE = (ROOT / "login_visual.py").read_text(encoding="utf-8")
TRANSITION_SOURCE = SOURCE + VISUAL_SOURCE
EARTH_PATH = ROOT / "assets" / "jarvis_earth.webp"
DOT_EARTH_PATH = ROOT / "assets" / "jarvis_dot_earth.webp"
TEST_PASSWORD = "jarvis-login-transition-test"


def _new_app():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=60)
    app.secrets["APP_PASSWORD"] = TEST_PASSWORD
    return app


def _overlay_count(app):
    return sum("jarvis-login-transition" in str(node.value) for node in app.markdown)


class LoginVisualContractTests(unittest.TestCase):
    def test_earth_is_1400px_local_webp_under_500kb(self):
        for earth_path in (EARTH_PATH, DOT_EARTH_PATH):
            self.assertLessEqual(earth_path.stat().st_size, 500_000)
            with Image.open(earth_path) as earth:
                self.assertEqual(earth.format, "WEBP")
                self.assertEqual(earth.size, (1400, 1400))
        for marker in (
            'Path(__file__).parent / "assets" / "jarvis_earth.webp"',
            'Path(__file__).parent / "assets" / "jarvis_dot_earth.webp"',
            "data:image/webp;base64,",
            "jarvis-waiting-earth-surface",
            "jarvis-waiting-earth-turn",
        ):
            self.assertIn(marker, SOURCE)
        self.assertNotIn("jarvis_earth.svg", SOURCE)

    def test_transition_timing_responsive_and_reduced_motion_contract(self):
        for marker in (
            'st.session_state["login_transition_pending"] = True',
            'st.session_state.pop("login_transition_pending", None)',
            "ACCESS GRANTED",
            "JARVIS ONLINE",
            "인증 완료",
            "z-index: 2147483647",
            "opacity: 1",
            "animation-duration: 2s",
            "animation-fill-mode: forwards",
            "pointer-events: none",
            "visibility: hidden",
            "@media (max-width: 1100px)",
            "@media (max-width: 640px)",
            "@media (prefers-reduced-motion: reduce)",
            "animation-duration: .2s",
        ):
            self.assertIn(marker, TRANSITION_SOURCE)
        self.assertLess(
            SOURCE.index("login_visual.render_login_transition"),
            SOURCE.index("db.init_db()"),
        )
        self.assertIn("animation: jarvis-waiting-earth-turn 60s linear infinite", SOURCE)
        self.assertIn("animation: jarvis-early-earth-surface-turn 80s linear infinite", VISUAL_SOURCE)
        self.assertIn("login_visual.render_login_transition(st, _jarvis_earth_markup)", SOURCE)
        self.assertIn("_jarvis_login_earth_markup + \"</div>\"", SOURCE)
        self.assertIn("background-position: 120% 50%", TRANSITION_SOURCE)
        self.assertIn("background-position: -80% 50%", TRANSITION_SOURCE)
        markup_source = SOURCE.split("_jarvis_earth_markup = (", 1)[1].split("except OSError", 1)[0]
        self.assertNotIn("jarvis-orbit", markup_source)
        self.assertNotIn("time.sleep(", SOURCE)
        self.assertNotIn("setTimeout(", SOURCE)

    def test_login_chime_is_short_quiet_inline_audio(self):
        # 2026-07-15 사용자 요청: 로그인 성공 시 아주 작은 소리를 짧게 재생한다.
        # 외부 URL 요청 없이(속도 영향 없음) base64로 인라인 삽입해야 하고, autoplay
        # 속성으로 재생하며, 소리 자체도 진폭이 작아야("아주 소리 작게") 한다.
        for marker in (
            "<audio autoplay preload=\"auto\"",
            "data:audio/wav;base64,",
            "_LOGIN_CHIME_WAV_BASE64",
        ):
            self.assertIn(marker, VISUAL_SOURCE)
        self.assertNotIn("<script", VISUAL_SOURCE)

        ns = {}
        exec(compile(VISUAL_SOURCE, "login_visual.py", "exec"), ns)
        b64 = ns["_LOGIN_CHIME_WAV_BASE64"]
        import base64
        import struct
        import wave
        import io

        raw = base64.b64decode(b64)
        self.assertEqual(raw[:4], b"RIFF")
        with wave.open(io.BytesIO(raw), "rb") as wf:
            duration_s = wf.getnframes() / wf.getframerate()
            frames = wf.readframes(wf.getnframes())
        self.assertLess(duration_s, 1.0, "로그인음은 짧아야 한다(1초 미만)")
        samples = struct.unpack(f"<{len(frames) // 2}h", frames)
        peak_ratio = max(abs(s) for s in samples) / 32768
        self.assertLess(peak_ratio, 0.15, "로그인음은 아주 작은 소리여야 한다(피크 진폭 15% 미만)")


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
        self.assertTrue(any("<audio autoplay" in str(node.value) for node in app.markdown))

        # The existing market auto-run is outside this feature; mark it complete so the
        # following rerun isolates the one-shot transition behavior.
        app.session_state["kr_auto_run_stage1_done"] = True
        app.session_state["kr_auto_run_stage2_done"] = True
        app.session_state["kr_theme_auto_fetch_pending"] = False
        with self._socket_block():
            app.run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(_overlay_count(app), 0)
        self.assertFalse(any("<audio autoplay" in str(node.value) for node in app.markdown))
        self.assertFalse(any("DuplicateWidgetID" in str(error.value) for error in app.exception))


if __name__ == "__main__":
    unittest.main()

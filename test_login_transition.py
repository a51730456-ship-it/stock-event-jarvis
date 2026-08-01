import socket
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).parent
SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")
VISUAL_SOURCE = (ROOT / "login_visual.py").read_text(encoding="utf-8")
TRANSITION_SOURCE = SOURCE + VISUAL_SOURCE
EARTH_PATH = ROOT / "assets" / "jarvis_earth.webp"
TEST_PASSWORD = "jarvis-login-transition-test"


@contextmanager
def _offline_market_stubs():
    """로그인 연출 테스트가 자동 시장 워밍업의 네트워크 시간에 좌우되지 않게 한다."""
    with patch("price_data.get_snapshot_defaults", return_value={"ok": False}), \
         patch("price_data.get_intraday_last", return_value={"ok": False}), \
         patch("price_data.get_ohlc_history_for_chart", return_value=None), \
         patch("price_data.get_top_kr_stocks_by_amount", return_value=[]), \
         patch("kis_market_data.get_index_snapshot", return_value={"ok": False}), \
         patch("naver_market_data.get_index_snapshot", return_value={"ok": False}), \
         patch("naver_market_data.get_index_daily_close", return_value={"ok": False}), \
         patch("news_data.fetch_naver_news", return_value={"status": "데이터 없음", "data": []}), \
         patch("theme_data.fetch_kr_theme_snapshot", return_value={"ok": False, "themes": {}}), \
         patch("theme_data.fetch_us_sector_snapshot", return_value={"ok": False, "sectors": []}), \
         patch("theme_data.fetch_us_theme_indicators", return_value={"ok": False, "values": {}}), \
         patch("bookmaker_data.fetch_bookmaker_snapshot", return_value={"ok": True, "events": [], "errors": []}):
        yield


def _new_app():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=60)
    app.secrets["APP_PASSWORD"] = TEST_PASSWORD
    return app


def _overlay_count(app):
    return sum("jarvis-login-transition" in str(node.value) for node in app.markdown)


class LoginVisualContractTests(unittest.TestCase):
    def test_earth_is_1400px_local_webp_under_500kb(self):
        # 2026-07-23: 로그인 화면도 실사 지구(jarvis_earth.webp)를 쓰기로 해
        # 점 지구는 더 이상 앱에서 읽지 않는다. 텍스처는 한 장만 검사한다.
        self.assertLessEqual(EARTH_PATH.stat().st_size, 500_000)
        with Image.open(EARTH_PATH) as earth:
            self.assertEqual(earth.format, "WEBP")
            self.assertEqual(earth.size, (1400, 1400))
        for marker in (
            'Path(__file__).parent / "assets" / "jarvis_earth.webp"',
            "data:image/webp;base64,",
            "login_globe.render_login_globe(st, _jarvis_earth_src)",
        ):
            self.assertIn(marker, SOURCE)
        self.assertNotIn("jarvis_earth.svg", SOURCE)
        # 평면 지도를 옆으로 밀던 옛 방식은 완전히 걷어냈다.
        self.assertNotIn("jarvis-waiting-earth", SOURCE)

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
        self.assertIn("animation: jarvis-early-earth-surface-turn 80s linear infinite", VISUAL_SOURCE)
        self.assertIn("login_visual.render_login_transition(st, _jarvis_earth_markup)", SOURCE)
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
        with self._socket_block(), _offline_market_stubs():
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
        with self._socket_block(), _offline_market_stubs():
            app.run()
            # 멀티페이지가 2개 이상이면 AppTest도 실제 switch_page를 수행한다.
            # 이 테스트는 자비스1 로그인 전환 자체를 검증하므로 목적지를 명시한다.
            app.radio[0].set_value("자비스1 (기록장)")
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
        app.session_state["kr_bookmaker_auto_fetch_pending"] = False
        app.session_state["kr_auto_run_version"] = "2026-07-14-previous-close-v2"
        app.session_state["us_auto_run_stage1_done"] = True
        app.session_state["us_auto_run_stage2_done"] = True
        app.session_state["us_auto_run_version"] = "2026-07-15-v1"
        app.session_state["parallel_warmup_done"] = True
        with self._socket_block(), _offline_market_stubs():
            app.run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(_overlay_count(app), 0)
        self.assertFalse(any("<audio autoplay" in str(node.value) for node in app.markdown))
        self.assertFalse(any("DuplicateWidgetID" in str(error.value) for error in app.exception))
        # 자비스1을 고른 사람은 주소에 표식이 남아야 한다 — 이 표식이 있어야 아래
        # '뒤로가기' 화면과 구별된다. (AppTest는 값을 목록으로 돌려준다.)
        mark = app.query_params.get("page")
        self.assertIn("jarvis1", mark if isinstance(mark, list) else [mark])

    def test_back_button_lands_on_the_chooser_not_on_jarvis1(self):
        """폰에서 뒤로가기를 여러 번 누르면 첫 주소로 돌아온다(2026-08-01 사용자 지시).

        그때 자비스1의 무거운 탭 화면을 그리면 검은 빈 화면이 한참 떠 있고 버벅인다.
        이미 로그인한 세션이므로 비밀번호는 다시 묻지 않고, 어디로 갈지 고르는
        화면만 띄운다. 무거운 모듈은 하나도 읽지 않아야 한다.
        """
        app = _new_app()
        app.session_state["authenticated"] = True  # 로그인은 이미 끝난 세션이다
        with self._socket_block(), _offline_market_stubs():
            app.run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        markdowns = [str(node.value) for node in app.markdown]
        self.assertTrue(any("어디로 갈까요" in value for value in markdowns))
        self.assertTrue(any("비밀번호를 다시 넣지 않아도 됩니다" in value for value in markdowns))
        # 비밀번호 칸은 없어야 한다 — 다시 로그인시키지 않는다.
        self.assertEqual([], [node for node in app.text_input if node.key == "login_password_input"])
        # 고르는 칸과 이동 단추가 있어야 한다.
        self.assertEqual(["entry_dest_choice"], [node.key for node in app.radio])
        self.assertIn("entry_go", [node.key for node in app.button])
        # 자비스1은 그려지지 않아야 한다 — 이게 그려지면 옛 동작으로 돌아간 것이다.
        self.assertFalse(any("① 한국장 판단" in value for value in markdowns))

    def test_the_chooser_moves_to_the_page_you_picked(self):
        """고른 곳으로 실제로 옮겨 가는지. 옮기지 못하면 화면에 갇힌다."""
        app = _new_app()
        app.session_state["authenticated"] = True
        with self._socket_block(), _offline_market_stubs():
            app.run(timeout=60)
            app.radio[0].set_value("미국테마 (자비스3)")
            next(node for node in app.button if node.key == "entry_go").click().run(timeout=60)
        # switch_page가 실제로 일어나면 자비스3 페이지가 열린다(멀티페이지 AppTest).
        self.assertEqual(len(app.exception), 0)
        self.assertNotIn("entry_go", [node.key for node in app.button])


if __name__ == "__main__":
    unittest.main()

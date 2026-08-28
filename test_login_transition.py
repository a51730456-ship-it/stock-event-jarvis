import re
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
PRISM_SOURCE = (ROOT / "login_prism.py").read_text(encoding="utf-8")
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
    def test_prism_starts_colored_and_stays_compact_on_phone_and_tablet(self):
        """첫 화면의 위 무지개와 작은 아래 프리즘이 한 화면 안에 보여야 한다."""
        for marker in (
            "@media (max-width: 1100px)",
            "@media (max-width: 600px)",
            ".jp-title { font-size: 1.45rem",
            "flex-direction: row !important",
            "width: 0 !important; flex: 1 1 0 !important",
            "background-size: auto 1.25rem !important",
            "viewBox='0 0 1200 190'",
            "x1='0' y1='0' x2='620' y2='0' spreadMethod='repeat'",
            "<animateTransform attributeName='gradientTransform' type='translate'",
            "from='-620 0' to='0 0' dur='6s'",
            "CSS\n        + \"<div class='jp-stage'>\"",
        ):
            self.assertIn(marker, PRISM_SOURCE)
        self.assertNotIn("@media (max-width: 640px)", PRISM_SOURCE)
        self.assertNotIn("viewBox='0 0 1200 132'", PRISM_SOURCE)
        self.assertNotIn("dur='20s'", PRISM_SOURCE)

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
            # 첫 화면의 도는 지구는 2026-08-09에 **프리즘으로 바꿨다**(상하님 지시).
            # 지구 그림은 그대로 남는다 — 로그인 성공 연출(ACCESS GRANTED)에서 쓴다.
            # 그래서 그림 파일 조건은 그대로 두고, 첫 화면에 그리는 자리만 바꿔 본다.
            "login_visual.render_login_transition(st, _jarvis_earth_markup)",
            "login_prism.render(st)",
        ):
            self.assertIn(marker, SOURCE)
        self.assertNotIn("login_globe.render_login_globe(st, _jarvis_earth_src)", SOURCE)
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
            self.assertIn("login_guest", [node.key for node in app.button])
            login_button = next(node for node in app.button if node.key == "login_submit")
            app.text_input[0].set_value("wrong-password")
            login_button.click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([error.value for error in app.error], ["비밀번호가 올바르지 않습니다."])
        self.assertIsNone(app.session_state.filtered_state.get("authenticated"))

    def test_success_transition_plays_once_and_normal_rerun_does_not_replay(self):
        """로그인 연출은 **'어디로 갈까요' 화면에서** 한 번만 돈다(2026-08-09).

        예전에는 로그인이 곧바로 자비스1로 옮겨 가(st.switch_page) 그 본문에서
        연출을 틀었다. 그 이동이 브라우저 기록에 같은 주소를 하나 더 쌓아
        뒤로가기가 맨홈을 두 번 지나게 만들어서, 로그인은 로그인만 하고 갈 곳은
        다음 화면에서 링크로 고르게 바꿨다. 연출도 그 화면으로 따라왔다.
        """
        app = _new_app()
        with self._socket_block(), _offline_market_stubs():
            app.run()
            app.text_input[0].set_value(TEST_PASSWORD)
            next(node for node in app.button if node.key == "login_submit").click().run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(app.session_state.filtered_state.get("authenticated"))
        self.assertNotIn("login_transition_pending", app.session_state.filtered_state)
        self.assertEqual(_overlay_count(app), 1)
        self.assertTrue(any("ACCESS GRANTED" in str(node.value) for node in app.markdown))
        self.assertTrue(any("<audio autoplay" in str(node.value) for node in app.markdown))
        # 로그인 뒤에는 '어디로 갈까요'가 나온다 — 무거운 자비스1을 바로 그리지 않는다.
        self.assertTrue(any("어디로 갈까요" in str(node.value) for node in app.markdown))

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
        # 갈 곳은 **누르면 바로 가는 링크**다(2026-08-09 상하님 승인).
        # 예전에는 동그라미로 고른 뒤 '이동'을 눌렀는데, 그 방식(st.switch_page)은
        # 스트림릿이 같은 주소를 기록에 하나 더 쌓아서 뒤로가기가 이 화면을 두 번
        # 지나갔다. 링크는 기록을 하나만 쌓는다.
        self.assertEqual([], [node.key for node in app.radio],
                         "고르는 동그라미는 없어야 한다 — 링크를 바로 누른다")
        targets = [node.page for node in app.get("page_link")]
        self.assertIn("자비스3", targets)
        self.assertIn("자비스4", targets)
        # 자비스1은 2026-08-28부터 닫아 두었다 — 그 단추도 없다(상하님 지시).
        self.assertNotIn("entry_go", [node.key for node in app.button])
        # 자비스1은 그려지지 않아야 한다 — 이게 그려지면 옛 동작으로 돌아간 것이다.
        self.assertFalse(any("① 한국장 판단" in value for value in markdowns))

    def test_phone_and_tablet_see_only_the_two_theme_pages(self):
        """폰·태블릿(≤1200px)에서는 미국테마·한국테마 둘만 보인다(2026-08-01 지시).

        옵션을 지우는 게 아니라 감추는 것이다 — 노트북/PC에서는 7개가 다 보여야 하고
        나중에 되살릴 수 있어야 한다(CLAUDE.md 12번). 목록 순서를 바꾸면 아래 번호도
        같이 고쳐야 하므로, 그 짝을 여기서 굳혀 둔다.
        """
        options = re.search(r"_DEST_OPTIONS = \[(.*?)\]", SOURCE, re.S).group(1)
        names = re.findall(r'"([^"]+)"', options)
        self.assertEqual(7, len(names))
        # 감추는 번호(1~3, 6~7)를 뺀 나머지가 미국테마·한국테마여야 한다.
        shown = [name for index, name in enumerate(names, 1) if 4 <= index <= 5]
        self.assertEqual(["미국테마 (자비스3)", "한국테마 (자비스4)"], shown)
        # 기본 선택은 감추는 항목에 들어가면 안 된다.
        default = int(re.search(r"_DEST_DEFAULT_INDEX = (\d+)", SOURCE).group(1))
        self.assertIn(names[default], shown)
        # 갈 곳을 고르는 자리는 **'어디로 갈까요' 한 곳뿐이다**(2026-08-09).
        # 로그인 화면의 '로그인 후 이동' 목록은 그날 없앴다 — 그 목록의 이동이
        # st.switch_page라 뒤로가기가 맨홈을 두 번 지나게 만들었다.
        self.assertNotIn("login_dest_choice", SOURCE.replace("login_dest_choice 목록", ""))
        # '어디로 갈까요'는 2026-08-09부터 링크 목록이라 감추는 자리가 바뀌었다.
        # 링크는 목록 상자(entry_dest_links)의 자식이므로 그 자식 번호로 감춘다.
        for rule in ("nth-child(-n+3)", "nth-child(n+6)"):
            self.assertIn(
                f".st-key-entry_dest_links > div:{rule}",
                SOURCE, f"entry_dest_links에 {rule} 규칙이 없다",
            )

    def test_the_chooser_offers_a_real_link_to_every_page(self):
        """갈 곳마다 진짜 링크가 있어야 한다. 없으면 그 화면에 갇힌다.

        링크여야 하는 까닭은 뒤로가기다 — st.switch_page는 같은 주소를 브라우저
        기록에 하나 더 쌓아, 뒤로가기를 눌러도 같은 화면이 한 번 더 나왔다
        (2026-08-09 최소 예제로 재현 확인).
        """
        app = _new_app()
        app.session_state["authenticated"] = True
        with self._socket_block(), _offline_market_stubs():
            app.run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        links = app.get("page_link")
        labels = [node.label for node in links]
        # **2026-08-28부터 열어 둔 곳은 둘뿐이다**(상하님 지시 — "나머지 화면은
        # 접근 금지로 해라"). 목록은 page_access.OPEN_PAGES 가 정한다.
        # 예전에는 여섯 링크 + 자비스1 단추였다. 되살리면 그때로 돌아온다.
        self.assertEqual(2, len(links), labels)
        for name in ("미국테마 (자비스3)", "한국테마 (자비스4)"):
            self.assertIn(name, labels)


if __name__ == "__main__":
    unittest.main()

"""안드로이드 설치 파일 설계도 (2026-11-04 상하님 — 「카톡으로 보내면 바탕화면에 어플」 · 「하나만 · 미국테마에서 한국테마로」)."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("j13_android_build", ROOT / "research" / "j13_android_build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)


class AndroidProjectTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.out = build.write_project(Path(self._tmp.name), version_code=7, icons=False)

    def _all_text(self) -> str:
        return "\n".join(p.read_text(encoding="utf-8") for p in self.out.rglob("*") if p.is_file())

    def test_one_launcher_icon_opens_jarvis12(self):
        manifest = (self.out / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertEqual(1, manifest.count("android.intent.category.LAUNCHER"))      # 아이콘은 하나
        java = "\n".join(p.read_text(encoding="utf-8") for p in self.out.rglob("*.java"))
        self.assertIn(build.screen_url("자비스12"), java)
        self.assertNotIn("%EC%9E%90%EB%B9%84%EC%8A%A413", java)                        # 한국테마는 화면 안 단추로 간다
        self.assertEqual("https://stock-event-jarvis.streamlit.app/%EC%9E%90%EB%B9%84%EC%8A%A412",
                         build.screen_url("자비스12"))

    def test_no_password_and_no_trading(self):
        text = self._all_text()
        for word in ("APP_PASSWORD", "secrets.toml", "password=", "order", "KIS"):
            self.assertNotIn(word, text)
        self.assertIn('System.getenv("JARVIS_KEY_PASS")', text)                       # 서명 암호는 깃허브 실행 값에서만

    def test_links_outside_the_app_open_in_the_browser(self):
        java = (self.out / "app" / "src" / "main" / "java" / "io" / "github" / "stockeventjarvis" / "app"
                / "WebActivity.java").read_text(encoding="utf-8")
        self.assertIn('host.endsWith("streamlit.app")', java)
        self.assertIn("openOutside(uri)", java)
        self.assertIn("setAcceptThirdPartyCookies", java)                             # 로그인 유지 쿠키
        self.assertIn("versionCode 7", (self.out / "app" / "build.gradle").read_text(encoding="utf-8"))

    def test_exit_bridge_closes_the_app(self):
        # 2026-11-04 상하님 「완전 창 닫는 것도 하나 만들자」 — 화면의 ✕ 가 JarvisApp.exit() 를 부르면 앱이 끝난다
        java = "\n".join(p.read_text(encoding="utf-8") for p in self.out.rglob("*.java"))
        self.assertIn('addJavascriptInterface(new Bridge(), "JarvisApp")', java)
        self.assertIn("@JavascriptInterface", java)
        self.assertIn("finishAndRemoveTask()", java)
        self.assertEqual(1, java.count("@JavascriptInterface"))                      # 연 것은 이것 하나

    def test_icon_is_drawn(self):
        try:
            import PIL  # noqa: F401
        except ImportError:
            self.skipTest("그림 도구 없음")
        out = build.write_project(Path(self._tmp.name) / "with_icons")
        icons = sorted(p.name for p in out.rglob("*.png"))
        self.assertEqual(len(build.ICON_SIZES), len(icons))

    def test_workflow_keeps_master_untouched(self):
        flow = (ROOT / ".github" / "workflows" / "j13_android.yml").read_text(encoding="utf-8")
        self.assertIn("j13-android", flow)
        self.assertNotIn("push -q -f \"https://x-access-token:${{ github.token }}@github.com/${GITHUB_REPOSITORY}.git\" master",
                         flow)


if __name__ == "__main__":
    unittest.main()

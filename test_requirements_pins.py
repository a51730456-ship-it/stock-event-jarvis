"""설치 목록 — 스트림릿 서버 부품의 판을 못 박아 둔다 (2026-10-21).

starlette 1.9.0 이 나오자 온라인이 사진 파일(png·webp·영상)을 내줄 때마다 서버 오류(500)를 내 자비스3·자비스12 그림이
다 깨졌다. 판을 안 적으면 앱을 다시 깔 때마다 최신 판을 받는다. 이 시험은 판 고정이 빠지면 먼저 깨진다.
"""
import re
import unittest
from pathlib import Path

REQ = (Path(__file__).resolve().parent / "requirements.txt").read_text(encoding="utf-8")


class RequirementPinTests(unittest.TestCase):
    def test_server_parts_are_pinned(self):
        for name in ("streamlit", "starlette", "uvicorn", "anyio", "httptools", "h11", "websockets"):
            self.assertRegex(REQ, rf"(?m)^{name}==\d", f"{name} 판이 안 박혀 있다")

    def test_starlette_is_not_the_broken_one(self):
        self.assertNotRegex(REQ, r"(?m)^starlette==1\.9\.")


if __name__ == "__main__":
    unittest.main()

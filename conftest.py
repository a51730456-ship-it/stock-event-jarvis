"""테스트가 실제 캐시 파일을 건드리지 않게 막는다.

2026-07-30에 파일 캐시(공책)를 넣으면서 생긴 문제다. 개발하며 쌓인
`cache/jarvis4/flow__000660.pkl` 같은 파일을 테스트가 읽어, 조회가 실패하는
상황을 흉내 냈는데도 성공한 값이 돌아왔다(test_flow_failure_returns_not_ok).

그래서 테스트가 도는 동안에는 공책 위치를 임시 폴더로 돌려 둔다.
실제 캐시는 손대지 않고, 테스트끼리도 서로의 파일을 안 본다.

주의 — 이 파일은 **pytest로 돌릴 때만** 읽힌다. `python -m unittest`로 돌리면
conftest를 아예 안 읽어 실제 캐시를 그대로 본다(2026-08-06에 그렇게 깨졌다).
그래서 test_jarvis4_data.py에는 같은 격리가 setUpModule로도 들어 있다.
겹쳐 보여도 지우면 안 된다 — 둘이 막는 실행 방법이 서로 다르다.
"""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True, scope="session")
def _isolate_disk_cache():
    with tempfile.TemporaryDirectory(prefix="jarvis-cache-") as temporary:
        try:
            import jarvis4_data
        except Exception:  # 그 모듈을 안 쓰는 테스트도 있다.
            yield
            return
        original = getattr(jarvis4_data, "_DISK_CACHE_DIR", None)
        jarvis4_data._DISK_CACHE_DIR = Path(temporary) / "jarvis4"
        try:
            yield
        finally:
            if original is not None:
                jarvis4_data._DISK_CACHE_DIR = original

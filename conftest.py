"""테스트가 실제 캐시 파일과 **저장해 둔 목록**을 건드리지 않게 막는다.

2026-07-30에 파일 캐시(공책)를 넣으면서 생긴 문제다. 개발하며 쌓인
`cache/jarvis4/flow__000660.pkl` 같은 파일을 테스트가 읽어, 조회가 실패하는
상황을 흉내 냈는데도 성공한 값이 돌아왔다(test_flow_failure_returns_not_ok).

그래서 테스트가 도는 동안에는 공책 위치를 임시 폴더로 돌려 둔다.
실제 캐시는 손대지 않고, 테스트끼리도 서로의 파일을 안 본다.
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


@pytest.fixture(autouse=True, scope="session")
def _isolate_picklist_archive():
    """날짜별 목록(`data/picklist`)을 시험이 못 쓰게 임시 폴더로 돌린다.

    **왜 필요한가 (2026-08-19).** 화면 시험(test_jarvis3_page·test_top_reviewed)은
    자비스3 화면을 통째로 돌린다. 그 화면에는 `picklist_ui.autosave`가 있어서,
    시험이 넣은 가짜 결과를 **진짜 자료 폴더에 그대로 저장했다.**

    그래서 `2026-08-15.US.csv` 같은 파일에 NVDA 값이 178.5, 등락이 1.0처럼
    딱 떨어지는 가짜 숫자가 들어갔고, 한 파일에 1등이 세 번 나오기도 했다.
    상하님이 커밋 목록에서 그 파일들을 걷어내신 일이 있다(75387f4).

    **지우는 게 아니라 쓰는 자리를 옮기는 것이다.** 진짜 목록은 그대로 있고,
    시험은 임시 폴더에만 쓴다(CLAUDE.md 10-1 — 목록은 지우지 않는다).

    out_dir을 직접 넘기는 시험(test_picklist_store)은 이 갈이와 상관없다.
    """
    with tempfile.TemporaryDirectory(prefix="jarvis-picklist-") as temporary:
        try:
            import picklist_store
        except Exception:      # 그 모듈을 안 쓰는 시험도 있다.
            yield
            return
        original = picklist_store.ARCHIVE_DIR
        picklist_store.ARCHIVE_DIR = Path(temporary)
        try:
            yield
        finally:
            picklist_store.ARCHIVE_DIR = original

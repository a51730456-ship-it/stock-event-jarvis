"""자비스13 손님끼리 같이 쓰는 짧은 보관 (2026-11-04 상하님 「로딩 문제 해결하고」).

깃허브 재기(research/j13_profile.py · 실행 41757644863) — 새 손님 4.6초(자비스12 1.7초). 손님마다 네이버에 시장 개요
(지수 · 투자자 수급 · 대형주 수급)와 수급 카드 값을 **새로 물었다**. 그중 대형주 수급은 네이버 화면이 바뀌어 늘 실패하는데,
실패는 담아 두지 않아 손님마다 다시 물었다(얼린 jarvis4_data — 고치지 않는다).

여기서는 **값을 바꾸지 않고** 방금 받은 것을 짧게(55초) 여러 손님이 같이 쓴다. 화면은 1분마다 새로 받으므로 보이는 값이
늦어지는 것은 길어야 1분 안쪽이다. 못 받은 값(ok 가 아닌 것)은 담지 않는다 — 다음 손님이 다시 받는다.
"""

from __future__ import annotations

import threading
import time

MODULE_REVISION = 2026110401
KEEP_SECONDS = 55.0
_BOX: dict = {}
_LOCK = threading.Lock()


def remember(key, producer, *, keep: float = KEEP_SECONDS, good=lambda value: True):
    """keep 초 안에 받은 값이 있으면 그것을, 없으면 producer() 를 불러 받는다. good(value) 가 참일 때만 담는다."""
    now = time.time()
    with _LOCK:
        kept = _BOX.get(key)
    if kept is not None and now - kept[0] < keep:
        return kept[1]
    value = producer()
    try:
        ok = bool(good(value))
    except Exception:
        ok = False
    if ok:
        with _LOCK:
            _BOX[key] = (time.time(), value)
    return value


def peek(key, *, keep: float = KEEP_SECONDS):
    """keep 초 안에 담긴 값(없으면 None) — 받으러 가지 않는다."""
    with _LOCK:
        kept = _BOX.get(key)
    if kept is not None and time.time() - kept[0] < keep:
        return kept[1]
    return None


def put(key, value) -> None:
    with _LOCK:
        _BOX[key] = (time.time(), value)

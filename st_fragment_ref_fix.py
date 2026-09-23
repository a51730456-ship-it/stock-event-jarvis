"""스트림릿 1.59 버그를 막는다 — 덩이(fragment)가 다시 그리다 버린 판의 「이미 가진 것」 표시를 같이 버린다.

2026-09-24 상하님 — *"급락 후 반등장 리스트 나온 종목 클릭하면 저 화면이 나온다"*(하얀 빈 화면).

**무슨 일이었나.** 스트림릿은 큰 조각을 한 번 보낸 뒤에는 똑같은 것을 「이미 가진 것」 표시(몇십 자)로
줄여 보낸다. 덩이 안 단추를 눌러 덩이가 다시 그리다가 곧바로 처음부터 다시 돌면
(`st.rerun(scope="fragment")`), 스트림릿은 버린 판의 조각을 보낼 줄에서 지운다. 그런데 이 표시만은
못 알아보고 남긴다 — 줄에서 조각을 가려낼 때 조각에 붙은 덩이 이름을 보는데, 줄여 보낸 표시에는
그 이름이 없다(`ForwardMsgQueue.clear`). 남은 표시는 부모 칸 없이 폰에 가고, 폰의 화면 그리는
쪽이 "'setIn' cannot be called on an ElementNode" 로 죽어 화면이 하얘진다.

**고침.** 덩이 판에서 만든 표시를 따로 적어 두었다가(1분만), 덩이 판을 버리는 그 지우기에서
같이 지운다. 표시는 그대로 쓰므로 보내는 양은 늘지 않는다. 판 전체를 다시 그리는 판은 손대지
않는다 — 그 판이 도중에 멈추면 스트림릿이 원래 남김없이 지운다.

스트림릿 1.59 에서만 건다(requirements 가 1.59.1 로 묶여 있다). 판이 바뀌면 걸지 않는다 —
그때는 이 파일을 다시 살펴야 한다. 걸다가 무엇이든 실패하면 조용히 넘어간다.
"""

from __future__ import annotations

import threading
import time

MODULE_REVISION = 2026092420
_MARK = "_j3_fragment_ref_fix"
# 덩이 판에서 만든 「이미 가진 것」 표시: id → (표시, 적은 시각). 보낼 줄은 몇 ms 안에 비워지므로
# 1분 넘게 남은 것은 이미 나갔거나 다른 조각에 덮인 것이다 — 그때 지운다.
_FRAGMENT_REFS: dict = {}
_KEEP_SECONDS = 60.0
_MAX_KEPT = 20000
_LOCK = threading.Lock()


def _remember(msg) -> None:
    with _LOCK:
        if len(_FRAGMENT_REFS) >= _MAX_KEPT:
            _FRAGMENT_REFS.clear()
        _FRAGMENT_REFS[id(msg)] = (msg, time.monotonic())


def install() -> bool:
    """한 번만 건다(서버 프로세스 전체). 걸렸거나 이미 걸려 있으면 True."""
    try:
        import streamlit
        from streamlit.runtime import forward_msg_queue as fmq
        from streamlit.runtime.scriptrunner_utils import script_run_context as src
    except Exception:
        return False
    ctx_cls = getattr(src, "ScriptRunContext", None)
    queue_cls = getattr(fmq, "ForwardMsgQueue", None)
    if ctx_cls is None or queue_cls is None:
        return False
    if not hasattr(ctx_cls, "enqueue") or not hasattr(queue_cls, "clear"):
        return False
    if getattr(ctx_cls.enqueue, _MARK, False) and getattr(queue_cls.clear, _MARK, False):
        return True
    if not str(getattr(streamlit, "__version__", "")).startswith("1.59."):
        return False
    original_enqueue = ctx_cls.enqueue
    original_clear = queue_cls.clear

    def enqueue(self, msg):
        if not getattr(self, "fragment_ids_this_run", None):
            return original_enqueue(self, msg)
        inner = self._enqueue

        def capture(sent):
            try:
                if sent.HasField("ref_hash"):
                    _remember(sent)
            except Exception:
                pass
            return inner(sent)

        self._enqueue = capture
        try:
            return original_enqueue(self, msg)
        finally:
            self._enqueue = inner

    def clear(self, retain_lifecycle_msgs=False, fragment_ids_this_run=None):
        original_clear(self, retain_lifecycle_msgs=retain_lifecycle_msgs,
                       fragment_ids_this_run=fragment_ids_this_run)
        if not _FRAGMENT_REFS:
            return
        now = time.monotonic()
        with _LOCK:
            if retain_lifecycle_msgs and fragment_ids_this_run is not None:
                kept = []
                for queued in self._queue:
                    if id(queued) in _FRAGMENT_REFS:
                        _FRAGMENT_REFS.pop(id(queued), None)
                        continue
                    kept.append(queued)
                self._queue = kept
            for key, (_msg, stamp) in list(_FRAGMENT_REFS.items()):
                if now - stamp > _KEEP_SECONDS:
                    _FRAGMENT_REFS.pop(key, None)

    setattr(enqueue, _MARK, True)
    setattr(clear, _MARK, True)
    enqueue.__wrapped__ = original_enqueue
    clear.__wrapped__ = original_clear
    ctx_cls.enqueue = enqueue
    queue_cls.clear = clear
    return True


# 1,000자 넘는 조각부터 「이미 가진 것」 표시로 줄여 보낸다(스트림릿 기본은 10,000자).
# 2026-09-23 밤 온라인 실측 — 화면 한 번 넘길 때 보내는 양 시장분석 84→26KB · 관심종목 53→28KB,
# 마지막 조각까지 시장분석 0.87~1.0→0.38~0.52초 · 관심종목 1.03~1.43→0.47~0.55초.
# 그때는 설정 파일(.streamlit/config.toml)에 넣어 **위 버그 막기보다 먼저** 모든 화면에 걸렸고,
# 급락 목록 종목을 누를 때마다 화면이 하얗게 죽었다. 이제는 버그를 막은 **뒤에만** 낮춘다 —
# 막기가 안 걸리면(스트림릿 판이 바뀌면) 낮추지 않는다.
SMALL_CACHE_SIZE = 1000


def lower_cache_threshold() -> bool:
    """install() 이 걸린 뒤에만 부른다. 이미 더 낮으면 그대로 둔다."""
    try:
        from streamlit import config

        current = float(config.get_option("global.minCachedMessageSize"))
        if current > SMALL_CACHE_SIZE:
            config.set_option("global.minCachedMessageSize", float(SMALL_CACHE_SIZE))
        return True
    except Exception:
        return False

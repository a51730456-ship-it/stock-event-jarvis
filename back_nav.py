# -*- coding: utf-8 -*-
"""폰·태블릿 뒤로가기 (2026-08-21 상하님 지시).

상하님 — *"한번 누르면 밑으로 화면 내린 부분에서 바로 위로 가고,
두번 누르면 앞에 메뉴로."*

**무엇이 문제였나.** 스트림릿에서 구역을 여닫는 것은 주소를 바꾸지 않는다.
상승장을 열고 종목을 눌러 화면 한참 아래까지 내려가도 브라우저가 보기에는
계속 같은 한 장이라, 뒤로가기 한 번에 앞 메뉴로 통째로 빠져나갔다.

**어떻게 고치나.** 그 화면에서 **무언가를 처음 열 때 딱 한 번** 주소 끝에
표식을 적는다(`?b=1`). 파이썬이 주소를 바꾸면 스트림릿이 브라우저 방문기록에
한 칸을 쌓는다(`handlePageInfoChanged` → `history.pushState`). 그래서

    미국테마 첫 화면            …/자비스3
    무엇이든 열면              …/자비스3?b=1     ← 기록 한 칸
      ← 뒤로 한 번             열어 둔 것이 다 닫히고 **화면 맨 위로** 간다
      ← 뒤로 한 번 더          앞 메뉴(어디로 갈까요)

**칸은 하나만 쌓는다.** 여러 겹으로 쌓으면 상하님이 몇 번을 눌러야 메뉴로
나가는지 알 수 없다("어떨 때는 한 번만 눌러도 메인 메뉴로 간다"). 그래서
**언제나 한 번은 위로, 두 번이면 앞 메뉴**가 되게 못박는다.

**손으로 닫았을 때는 주소를 건드리지 않는다.** 주소를 되돌리면 그것이 또
기록에 쌓여서 뒤로가기가 도로 열어 버린다.

**조용히 실패한다.** 주소를 못 읽거나 못 쓰면 그냥 넘어가 예전처럼 돈다.
이 장치 때문에 화면이 막히면 안 된다(CLAUDE.md 13번 쿠키 규칙과 같은 뜻).
"""

from __future__ import annotations

_STACK = "_backnav_open"
_PARAM = "b"


def _depth_in_url(st) -> int | None:
    """주소에 적힌 표식. 못 읽으면 None."""
    try:
        raw = st.query_params.get(_PARAM)
    except Exception:
        return None
    if raw in (None, ""):
        return 0
    try:
        return max(0, int(str(raw)))
    except (TypeError, ValueError):
        return None


def _write_depth(st, depth: int) -> None:
    """주소에 표식을 적는다 — 이때 방문기록이 한 칸 쌓인다."""
    try:
        if depth <= 0:
            st.query_params.pop(_PARAM, None)
        else:
            st.query_params[_PARAM] = str(depth)
    except Exception:
        pass


def open_keys(st) -> list:
    """뒤로가기 한 번에 닫을 열쇠들."""
    return list(st.session_state.get(_STACK) or [])


def opened(st, key: str, *also: str) -> None:
    """구역이 열렸다 — 뒤로가기가 닫을 목록에 넣는다.

    **기록은 처음 한 번만 쌓는다.** 두 번째부터는 목록에 열쇠만 보탠다.
    """
    keys = open_keys(st)
    first = not keys
    for name in (key, *also):
        if name and name not in keys:
            keys.append(name)
    st.session_state[_STACK] = keys
    if first and keys:
        _write_depth(st, 1)


def sync(st) -> list:
    """화면을 그리기 **전에** 부른다. 뒤로가기로 닫힌 열쇠들을 돌려준다.

    돌려준 것이 비어 있지 않으면 부르는 쪽이 화면을 맨 위로 올린다.
    **주소는 건드리지 않는다** — 이미 브라우저가 그 자리로 옮겨 놓았고,
    여기서 또 쓰면 기록이 한 칸 더 쌓인다.
    """
    keys = open_keys(st)
    if not keys:
        return []
    depth = _depth_in_url(st)
    if depth is None or depth >= 1:
        return []
    for name in keys:
        try:
            st.session_state[name] = False
        except Exception:
            pass
    st.session_state[_STACK] = []
    return keys


def reset(st) -> None:
    """화면을 처음부터 다시 볼 때 표식을 지운다."""
    st.session_state[_STACK] = []
    _write_depth(st, 0)

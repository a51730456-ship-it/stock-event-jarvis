# -*- coding: utf-8 -*-
"""폰·태블릿 뒤로가기 — 한 번 누르면 방금 연 구역만 닫힌다 (2026-08-21 상하님 지시).

**무엇이 문제였나.** 상하님 — *"태블릿과 스마트폰에서 뒤로가기 버튼을 누르면 맨처음
화면으로 간다. 한번 누르면 방금 화면 전으로 가게 하고 두번 누르면 메인메뉴로."*

스트림릿에서 구역을 여닫는 것은 **주소가 바뀌지 않는다.** 「상승장」을 열고 종목을
누르고 상세를 펴도 브라우저가 보기에는 계속 같은 한 장이라, 뒤로가기 한 번에
그 앞 화면(어디로 갈까요)으로 통째로 빠져나간다.

**어떻게 고치나.** 구역이 열릴 때마다 주소 끝에 깊이 하나를 적는다
(`?b=1` → `?b=2`). 스트림릿은 파이썬이 주소를 바꾸면 브라우저 방문기록에
한 칸을 **쌓는다**(`handlePageInfoChanged` → `history.pushState`). 그래서
뒤로가기를 누르면 주소가 한 칸 얕아지고, 스트림릿이 그 주소로 화면을 다시 그린다
(`popstate` → `onHistoryChange` → 같은 페이지 재실행). 그때 이 파일이 주소의 깊이와
세션의 깊이를 견줘 **더 깊은 만큼만 닫는다.**

    첫 화면            주소 …/자비스3          깊이 0
    상승장 열기         주소 …/자비스3?b=1      깊이 1
    선택종목 세부사항    주소 …/자비스3?b=2      깊이 2
      ← 뒤로 한 번      주소 …/자비스3?b=1      세부사항만 닫힌다
      ← 뒤로 한 번 더   주소 …/자비스3          상승장이 닫힌다
      ← 뒤로 한 번 더   어디로 갈까요(메인)

**손으로 닫았을 때는 주소를 건드리지 않는다.** 주소를 얕게 되돌리면 그것이 또
방문기록에 쌓여서, 뒤로가기가 도로 열어 버린다. 그래서 손으로 닫은 자리는
그대로 두고, 뒤로가기가 그 자리를 지날 때 이미 닫혀 있으니 아무 일도 안 일어난다.

**조용히 실패한다.** 주소를 못 읽거나 못 쓰면 그냥 넘어간다 — 예전처럼 동작한다.
이 장치 때문에 화면이 막히면 안 된다(CLAUDE.md 13번 쿠키 규칙과 같은 뜻).
"""

from __future__ import annotations

_STACK = "_backnav_stack"
_PARAM = "b"


def _depth_in_url(st) -> int | None:
    """주소에 적힌 깊이. 못 읽으면 None."""
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
    """주소에 깊이를 적는다 — 이때 방문기록이 한 칸 쌓인다."""
    try:
        if depth <= 0:
            st.query_params.pop(_PARAM, None)
        else:
            st.query_params[_PARAM] = str(depth)
    except Exception:
        pass


def stack(st) -> list:
    """지금까지 연 구역들. 한 칸은 **함께 여닫는 열쇠 묶음**이다."""
    return [list(entry) for entry in (st.session_state.get(_STACK) or [])]


def opened(st, key: str, *also: str) -> None:
    """구역 하나가 **새로** 열렸다 — 방문기록에 한 칸 쌓는다.

    `also`는 그 구역과 **함께 열리고 함께 닫히는** 열쇠들이다. 종목을 누르면
    상세·당일차트·일봉묶음 셋이 같이 열리는데, 셋을 따로 쌓으면 뒤로가기를
    세 번 눌러야 한 화면이 닫힌다. 그래서 한 칸으로 묶는다.

    이미 쌓아 둔 구역이면 아무 일도 하지 않는다.
    """
    entries = stack(st)
    if any(entry and entry[0] == key for entry in entries):
        return
    entries.append([key, *also])
    st.session_state[_STACK] = entries
    _write_depth(st, len(entries))


def sync(st) -> list:
    """화면을 그리기 **전에** 부른다. 뒤로가기로 닫힌 구역 이름들을 돌려준다.

    주소의 깊이가 세션의 깊이보다 얕으면 = 상하님이 뒤로가기를 누르신 것이다.
    그만큼 위에서부터 닫는다. **주소는 건드리지 않는다** — 이미 브라우저가
    그 자리로 옮겨 놓았고, 여기서 또 쓰면 기록이 한 칸 더 쌓인다.
    """
    names = stack(st)
    depth = _depth_in_url(st)
    if depth is None or depth >= len(names):
        return []
    closed = []
    while len(names) > depth:
        entry = names.pop()
        closed.append(entry[0] if entry else "")
        for key in entry:
            try:
                st.session_state[key] = False
            except Exception:
                pass
    st.session_state[_STACK] = names
    return closed


def reset(st) -> None:
    """화면을 처음부터 다시 볼 때 쌓아 둔 기록을 비운다."""
    st.session_state[_STACK] = []
    _write_depth(st, 0)

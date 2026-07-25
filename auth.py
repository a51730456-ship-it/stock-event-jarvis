"""로그인 유지 공용 모듈 (2026-07-25 도입).

문제: 폰 브라우저가 백그라운드 탭 연결을 끊으면 Streamlit이 새 세션을 만들고
`st.session_state["authenticated"]`가 사라져, 잠깐 나갔다 오면 로그인 화면으로
튕겼다. 이 모듈은 로그인 성공 시 브라우저 쿠키에 '해시 토큰'을 심고, 페이지가
열릴 때 쿠키를 보고 로그인을 되살린다.

안전 원칙(가장 중요):
  쿠키는 '추가 기능'일 뿐이다. 쿠키 컴포넌트나 secrets가 없거나 실패하면 모든
  함수가 조용히 아무 일도 하지 않고 넘어가, 지금까지와 똑같은 세션 기반 동작으로
  남는다. 그래야 온라인에 올려도 로그인이 깨져 못 들어가는 사고가 안 난다.

보안:
  쿠키에는 비밀번호가 아니라 sha256(소금 + 비밀번호) 해시만 담는다. 쿠키를 봐도
  비밀번호는 복원할 수 없다. 소금은 비밀이 아니어서 코드(공개 저장소)에 둬도 된다 —
  안전성은 APP_PASSWORD의 비밀 유지에서 나온다. 토큰을 가진 사람은 로그인된 것과
  같다(세션 탈취와 동일 수준의 위험)이며, 이 앱의 단일 공유 비밀번호 모델에서는
  받아들일 수 있는 수준이다.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

import streamlit as st

_COOKIE_NAME = "jarvis_auth"
# 소금은 비밀이 아니다. 토큰 형식을 바꾸고 싶을 때(예: 기존 쿠키 무효화) 값을 올린다.
_SALT = "jarvis-auth-v1"
_COOKIE_DAYS = 30


def _expected_token() -> str | None:
    """APP_PASSWORD로부터 기대 토큰을 만든다. 비밀번호가 없으면 None."""
    try:
        password = st.secrets.get("APP_PASSWORD")
    except Exception:
        password = None
    if not password:
        return None
    return hashlib.sha256((_SALT + str(password)).encode("utf-8")).hexdigest()


def _controller():
    """쿠키 컨트롤러를 만든다. 라이브러리·프런트엔드가 없으면 None(→ 기능 비활성)."""
    try:
        from streamlit_cookies_controller import CookieController

        return CookieController()
    except Exception:
        return None


def _decide(authenticated: bool, cookie_value, token: str) -> str | None:
    """세션·쿠키 상태로 할 일을 정한다(순수 함수 — 테스트로 굳혀 둔다).

    반환:
      "set"     : 로그인 상태인데 쿠키가 없거나 달라 → 쿠키를 심는다.
      "restore" : 로그인 상태가 아닌데 쿠키 토큰이 맞아 → 로그인을 되살린다.
      None      : 아무것도 하지 않는다.
    """
    if authenticated:
        return None if cookie_value == token else "set"
    return "restore" if cookie_value == token else None


def sync_auth(restore: bool = True) -> None:
    """세션과 쿠키를 맞춘다. 페이지 로그인 게이트 맨 앞에서 부른다.

    - 세션이 로그인 상태면: 쿠키에 토큰이 없거나 다를 때만 심는다.
    - 세션이 로그인 상태가 아니면: 쿠키 토큰이 맞으면 로그인을 되살린다.

    restore=False면 되살리지 않고 쿠키를 심기만 한다. 첫 화면(app.py)에서 쓴다 —
    거기서 되살리면 '어디로 갈지 고르는 로그인 화면'이 통째로 건너뛰어지고 무거운
    자비스1이 바로 열렸다(2026-07-25 사용자 지적). 첫 화면은 항상 보여야 한다.

    쿠키 관련이 하나라도 실패하면 조용히 넘어간다(세션 기반 동작 유지).
    """
    token = _expected_token()
    if not token:
        return
    controller = _controller()
    if controller is None:
        return
    try:
        action = _decide(
            bool(st.session_state.get("authenticated")),
            controller.get(_COOKIE_NAME),
            token,
        )
        if action == "set":
            controller.set(
                _COOKIE_NAME,
                token,
                expires=datetime.now() + timedelta(days=_COOKIE_DAYS),
                same_site="lax",
            )
        elif action == "restore" and restore:
            st.session_state["authenticated"] = True
    except Exception:
        # 쿠키가 안 되면 지금까지처럼 세션만으로 동작한다.
        pass


def clear_auth() -> None:
    """로그아웃 시 쿠키와 세션 표시를 지운다. 실패해도 조용히 넘어간다.

    주의: 이 함수를 부른 뒤 곧바로 `st.rerun()`을 하면 안 된다. 쿠키 삭제는
    화면에 그려지는 컴포넌트가 실제로 실행해야 브라우저에 반영되는데, rerun이
    그 렌더를 취소해 쿠키가 남는다(2026-07-25 실측). 부른 다음에는 그 실행이
    끝까지 그려지게 두고, 화면 전환은 그 다음 실행에서 한다.
    """
    st.session_state.pop("authenticated", None)
    controller = _controller()
    if controller is None:
        return
    try:
        controller.remove(_COOKIE_NAME)
    except Exception:
        pass

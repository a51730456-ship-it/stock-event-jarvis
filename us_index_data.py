"""미국 4대 지수 그림 자료를 화면들이 함께 쓰는 얇은 통로 (2026-07-25).

자비스4 페이지는 자비스3 자료 모듈을 직접 부르지 않는다는 규칙이 있다
(test_jarvis4_page의 계약). 그렇다고 같은 조회를 두 번 구현하면 값이 어긋나므로,
읽기 전용 통로를 하나 두고 양쪽이 이것만 쓰게 한다.
"""

from __future__ import annotations


def display() -> tuple:
    """(심볼, 이름) 목록. 실패하면 빈 튜플."""
    try:
        import jarvis3_data

        return tuple(jarvis3_data.US_INDEX_DISPLAY)
    except Exception:
        return ()


def sparklines() -> dict:
    """{심볼: {"points": 당일 분봉 종가들, "base": 전일 종가}}. 실패하면 빈 dict."""
    try:
        import jarvis3_data

        return jarvis3_data.get_index_sparklines()
    except Exception:
        return {}

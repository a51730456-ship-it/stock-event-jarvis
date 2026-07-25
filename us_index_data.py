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


def futures_sparkline(symbol: str = "NQ=F") -> dict:
    """미국 선물의 당일 분봉과 전일 종가. 실패하면 빈 dict.

    한국 장중에 미국 선물이 어디로 가는지 그림으로 보려고 쓴다(2026-07-25 요청).
    """
    try:
        import jarvis3_data

        intraday, _m1 = jarvis3_data._download_cached(
            (symbol,), period="1d", interval="5m", ttl_seconds=180)
        daily, _m2 = jarvis3_data._download_cached(
            (symbol,), period="1mo", interval="1d", ttl_seconds=600)
        frame, closes = intraday.get(symbol), daily.get(symbol)
        if frame is None or frame.empty or closes is None or len(closes) < 2:
            return {}
        points = [float(v) for v in frame["Close"].dropna().tolist()]
        base = float(closes["Close"].dropna().iloc[-2])
        return {"points": points, "base": base} if len(points) >= 2 else {}
    except Exception:
        return {}

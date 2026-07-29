"""미국 4대 지수 그림 자료를 화면들이 함께 쓰는 얇은 통로 (2026-07-25).

자비스4 페이지는 자비스3 자료 모듈을 직접 부르지 않는다는 규칙이 있다
(test_jarvis4_page의 계약). 그렇다고 같은 조회를 두 번 구현하면 값이 어긋나므로,
읽기 전용 통로를 하나 두고 양쪽이 이것만 쓰게 한다.
"""

from __future__ import annotations

# 이 통로의 반환 함수가 바뀌었는데 실행 중인 Streamlit 프로세스에 옛 모듈이 남는
# 경우를 막기 위한 표식이다.
MODULE_REVISION = 2026072901

# 자비스3 자료 모듈의 최소 리비전. 온라인에서 옛 모듈이 프로세스에 남으면 자비스4의
# 미국 지수 칸이 조용히 옛 계산을 계속 쓴다 — 자비스4 페이지에는 자비스3 리비전을
# 확인하는 문지기가 없으므로 이 통로가 대신 확인한다(2026-07-25).
_REQUIRED_J3_REVISION = 2026072515


def _j3():
    """자비스3 자료 모듈. 리비전이 낮으면 다시 읽는다."""
    import importlib

    import jarvis3_data

    if int(getattr(jarvis3_data, "MODULE_REVISION", 0)) < _REQUIRED_J3_REVISION:
        jarvis3_data = importlib.reload(jarvis3_data)
    return jarvis3_data


def display() -> tuple:
    """(심볼, 이름) 목록. 실패하면 빈 튜플."""
    try:
        return tuple(_j3().US_INDEX_DISPLAY)
    except Exception:
        return ()


def sparklines() -> dict:
    """{심볼: {"points": 당일 분봉 종가들, "base": 전일 종가}}. 실패하면 빈 dict."""
    try:
        return _j3().get_index_sparklines()
    except Exception:
        return {}


def market_overview() -> dict:
    """미국테마 상단 카드가 실제로 쓰는 시장 요약값을 그대로 돌려준다.

    한국테마가 차트 마지막 점으로 현재가와 등락률을 다시 계산하면 미국테마 카드와
    숫자가 달라진다. 숫자는 이 요약값, 그림만 ``sparklines()``를 사용한다.
    """
    try:
        return _j3().get_market_overview()
    except Exception:
        return {}


def futures_sparkline(symbol: str = "NQ=F") -> dict:
    """미국 선물의 당일 분봉과 전일 종가. 실패하면 빈 dict.

    한국 장중에 미국 선물이 어디로 가는지 그림으로 보려고 쓴다(2026-07-25 요청).
    """
    try:
        import pandas as pd

        jarvis3_data = _j3()
        intraday, _m1 = jarvis3_data._download_cached(
            (symbol,), period="1d", interval="5m", ttl_seconds=180)
        daily, _m2 = jarvis3_data._download_cached(
            (symbol,), period="1mo", interval="1d", ttl_seconds=600)
        frame, closes = intraday.get(symbol), daily.get(symbol)
        if frame is None or frame.empty or closes is None or len(closes) < 2:
            return {}
        points = [float(v) for v in frame["Close"].dropna().tolist()]
        # 기준선은 '분봉 날짜보다 앞선 마지막 종가'다. iloc[-2]로 잡으면 야후 일봉에
        # 그 날 줄이 아직 안 올라온 사이 기준선이 하루 더 옛날 것이 된다(2026-07-25).
        base = jarvis3_data._prior_session_close(
            closes, pd.Timestamp(frame.index[-1]).date())
        return {"points": points, "base": base} if len(points) >= 2 and base else {}
    except Exception:
        return {}

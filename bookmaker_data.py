"""도박사(예측시장) 신호 참고 조회 전용 모듈 (읽기 전용, DB 미저장, 점수·판정 미반영).

Polymarket Gamma API / Kalshi 공개 시장 데이터 API는 둘 다 인증 없이 조회 가능한
공개 API다(2026-07-13 확인, docs/PROJECT_SPEC.md 등에서 금지한 건 "자동연동"이지
"자동조회 자체가 불가능"이 아니라는 상하님 지적을 반영해 구현). theme_data.py와
동일한 원칙을 따른다:
- 버튼을 눌렀을 때만 조회한다(로그인/자동실행 시 자동으로 불러오지 않음).
- 결과는 session_state에만 유지되고 DB에 저장하지 않는다.
- 점수·판정 계산에 절대 반영하지 않는다. 순수 참고 표시 전용.
- 개별 실패는 예외를 던지지 않고 {"ok": False, "error": "..."}로 처리한다.

1차 구현은 "관련 시장을 자동으로 정확히 골라내는" 수준까지는 하지 않는다(상하님이
지적한 대로 이 부분이 진짜 어려운 부분). 대신 거래량 상위 활성 시장 중에서 거시경제/
금융 관련 키워드가 포함된 질문만 걸러 보여주고, 실제로 한국 증시에 의미가 있는지는
사람이 판단한다.
"""

import requests

POLYMARKET_GAMMA_URL = "https://gamma-api.polymarket.com/markets"
KALSHI_MARKETS_URL = "https://external-api.kalshi.com/trade-api/v2/markets"
KALSHI_SERIES_URL = "https://external-api.kalshi.com/trade-api/v2/series"
REQUEST_TIMEOUT = 10

# 자비스 도박사 구획이 다루는 "직접/간접 도박시장" 중 거시경제·금융 이벤트에 해당하는
# 키워드만 1차로 추린다(임의 선정, 필요하면 추가/수정 가능).
MACRO_KEYWORDS = (
    "fed", "rate cut", "rate hike", "interest rate", "inflation", "cpi",
    "recession", "tariff", "trade war", "china", "oil price", "opec",
    "nvidia", "chip", "semiconductor", "export control", "war", "ceasefire",
    "election", "shutdown", "debt ceiling", "powell", "trump",
)


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _question_matches(text):
    text_lower = (text or "").lower()
    return any(keyword in text_lower for keyword in MACRO_KEYWORDS)


def fetch_polymarket_signals(limit=6):
    """거래량 상위 활성 시장 중 거시경제 키워드가 포함된 질문 상위 limit개.

    반환: {"ok": bool, "error": str|None, "signals": [{"source","question",
    "probability_pct","change_note","volume_24h","end_date"}, ...]}
    """
    try:
        resp = requests.get(
            POLYMARKET_GAMMA_URL,
            params={
                "active": "true",
                "closed": "false",
                "order": "volume24hr",
                "ascending": "false",
                "limit": 100,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        markets = resp.json()
    except Exception as e:
        return {"ok": False, "error": str(e), "signals": []}

    if not isinstance(markets, list):
        return {"ok": False, "error": "예상치 못한 응답 형식", "signals": []}

    matched = []
    for m in markets:
        question = m.get("question")
        if not _question_matches(question):
            continue
        try:
            price = m.get("lastTradePrice")
            probability_pct = round(float(price) * 100, 1) if price is not None else None
        except (TypeError, ValueError):
            probability_pct = None
        matched.append(
            {
                "source": "Polymarket",
                "question": question,
                "probability_pct": probability_pct,
                "volume_24h": _to_float(m.get("volume24hr")),
                "end_date": (m.get("endDate") or "")[:10],
            }
        )

    matched.sort(key=lambda x: x.get("volume_24h") or 0, reverse=True)
    return {"ok": True, "error": None, "signals": matched[:limit]}


def fetch_kalshi_signals(limit=6, max_series=15):
    """Economics/Politics 카테고리 시리즈 중 거시경제 키워드가 제목에 포함된 것만 골라,
    그 시리즈들의 open 시장을 조회해 거래량 상위 limit개를 반환한다.

    Kalshi 공개 시장 목록(/markets)은 거래량 정렬도, 키워드 검색도 지원하지 않아
    전체를 페이지째 훑으면 스포츠/연예 시장에 묻혀 거시경제 시장이 거의 안 걸린다
    (2026-07-13 실측 확인). 대신 시리즈(/series) 목록을 먼저 키워드로 좁히고, 그
    시리즈에 속한 시장만 조회하는 2단계 방식을 쓴다.
    """
    matched_series = []
    try:
        for category in ("Economics", "Politics"):
            resp = requests.get(
                KALSHI_SERIES_URL, params={"category": category}, timeout=REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            for s in resp.json().get("series", []):
                if _question_matches(s.get("title")):
                    matched_series.append(s.get("ticker"))
    except Exception as e:
        return {"ok": False, "error": str(e), "signals": []}

    matched = []
    for ticker in matched_series[:max_series]:
        if not ticker:
            continue
        try:
            resp = requests.get(
                KALSHI_MARKETS_URL,
                params={"series_ticker": ticker, "status": "open", "limit": 3},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            for m in resp.json().get("markets", []):
                try:
                    yes_bid = m.get("yes_bid_dollars")
                    probability_pct = round(float(yes_bid) * 100, 1) if yes_bid is not None else None
                except (TypeError, ValueError):
                    probability_pct = None
                matched.append(
                    {
                        "source": "Kalshi",
                        "question": m.get("title"),
                        "probability_pct": probability_pct,
                        "volume_24h": _to_float(m.get("volume_24h_fp")),
                        "end_date": (m.get("close_time") or "")[:10],
                    }
                )
        except Exception:
            continue

    matched.sort(key=lambda x: x.get("volume_24h") or 0, reverse=True)
    return {"ok": True, "error": None, "signals": matched[:limit]}


def fetch_bookmaker_snapshot(limit_per_source=5):
    """Polymarket + Kalshi 거시경제 신호를 합쳐 거래량 순으로 정렬.

    한쪽이 실패해도 다른 쪽 결과는 살린다(theme_data.py의 개별 실패 허용 패턴과 동일).
    반환: {"ok": bool, "checked_at": str|None, "errors": [str, ...],
    "signals": [...]}
    """
    from datetime import datetime

    poly = fetch_polymarket_signals(limit=limit_per_source)
    kalshi = fetch_kalshi_signals(limit=limit_per_source)

    errors = []
    if not poly.get("ok"):
        errors.append(f"Polymarket: {poly.get('error')}")
    if not kalshi.get("ok"):
        errors.append(f"Kalshi: {kalshi.get('error')}")

    signals = (poly.get("signals") or []) + (kalshi.get("signals") or [])
    signals.sort(key=lambda x: x.get("volume_24h") or 0, reverse=True)

    return {
        "ok": bool(signals),
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S") if signals else None,
        "errors": errors,
        "signals": signals,
    }

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

2026-07-13 2차 수정: 임계값(threshold)만 다른 계약(예: "CPI 3% 이상"/"4% 이상"/
"5% 이상")은 확률분포를 나타내는 서로 다른 계약이지 중복이 아니라는 지적을 반영해,
"완전 중복 제거"와 "같은 사건을 임계값별로 묶어서 표시"를 구분했다:
- 완전 중복(질문·시장 ID·URL 동일)만 제거한다.
- 같은 사건(Polymarket의 events[0].id, Kalshi의 event_ticker)은 하나의 이벤트
  그룹으로 묶고, 그 안의 각 임계값 계약을 전부 보여준다(확률과 함께).
반환 형태가 완전히 바뀌었으므로(flat list of signals -> event groups) 이 모듈을
쓰는 app.py 쪽도 함께 갱신해야 한다.
"""

import math
import re
from datetime import datetime, timezone

import requests

POLYMARKET_GAMMA_URL = "https://gamma-api.polymarket.com/markets"
KALSHI_MARKETS_URL = "https://external-api.kalshi.com/trade-api/v2/markets"
KALSHI_SERIES_URL = "https://external-api.kalshi.com/trade-api/v2/series"
REQUEST_TIMEOUT = 10

# 자비스 도박사 구획이 다루는 "직접/간접 도박시장" 중 거시경제·금융 이벤트에 해당하는
# 키워드만 1차로 추린다(임의 선정, 필요하면 추가/수정 가능).
MACRO_KEYWORDS = (
    "fed", "rate", "rate cut", "rate hike", "interest rate", "inflation", "cpi",
    "recession", "tariff", "trade war", "china", "oil", "oil price", "opec",
    "nvidia", "chip", "semiconductor", "export control", "war", "ceasefire",
    "shutdown", "debt ceiling", "powell",
)
# "election" 키워드는 뺐다 — 대통령선거 개별 인물 베팅(예: "Pete Buttigieg 2028 당선?")
# 처럼 국내 증시와 무관한 잡음을 너무 많이 끌어왔다(2026-07-13, 실사용 확인).

_MACRO_KEYWORD_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in MACRO_KEYWORDS) + r")\b", re.IGNORECASE
)


def _to_float(value):
    """숫자로 명확히 해석되는 값만 반환한다. 누락/비정상 값은 0으로 만들지 않는다."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _question_matches(text):
    # 단순 부분문자열 매칭("war" in "Warriors")이 스포츠 등 무관한 시장을 끌어오는
    # 문제가 있어 단어 경계(\b) 매칭으로 바꿨다(2026-07-13, "LeBron James...Warriors"가
    # "war" 키워드에 잘못 걸린 것 확인 후 수정).
    return bool(_MACRO_KEYWORD_PATTERN.search(text or ""))


def _parse_iso_date(value):
    """ISO 형식 날짜/시각 문자열을 date로 파싱. 실패하면 None."""
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(text).date()
    except Exception:
        try:
            return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
        except Exception:
            return None


def _is_expired(end_date_str):
    """마감일이 오늘보다 과거면 True(명백히 오래되어 이미 끝났어야 할 시장)."""
    d = _parse_iso_date(end_date_str)
    if d is None:
        return False
    return d < datetime.now(timezone.utc).date()


_THRESHOLD_LABEL_PATTERN = re.compile(
    r"^(Above|Below|Exactly)\s+(-?\$?[\d.,]+%?\s*(trillion|billion|million)?)$", re.IGNORECASE
)
_LABEL_KO = {"above": "이상", "below": "이하", "exactly": "정확히"}
_BPS_LABEL_PATTERN = re.compile(r"^(\d+)(\+)?\s*bps?\s+(increase|decrease)$", re.IGNORECASE)
_SIMPLE_LABEL_KO = {
    "no change": "동결",
    "yes": "예",
    "no": "아니오",
}


def _translate_threshold_label(label):
    """"Above 4.00%" 같은 임계값 라벨을 규칙 기반으로 짧게 한국어화한다.

    번역 API를 쓰지 않는다 — 숫자·기호가 대부분이라 오역 위험 없이 규칙으로 충분하고,
    이벤트당 API 호출을 아낄 수 있다. 패턴에 안 맞으면 원문 그대로 반환한다(안전 대체).
    """
    if not label:
        return label
    stripped = label.strip()
    simple = _SIMPLE_LABEL_KO.get(stripped.lower())
    if simple:
        return simple
    bps_match = _BPS_LABEL_PATTERN.match(stripped)
    if bps_match:
        amount, plus, direction = bps_match.groups()
        amount_text = f"{amount}bp 이상" if plus else f"{amount}bp"
        direction_text = "인상" if direction.lower() == "increase" else "인하"
        return f"{amount_text} {direction_text}"
    m = _THRESHOLD_LABEL_PATTERN.match(stripped)
    if not m:
        return label
    direction, value = m.group(1).lower(), m.group(2).strip()
    if direction == "exactly":
        return f"정확히 {value}"
    return f"{value} {_LABEL_KO.get(direction, direction)}"


def fetch_polymarket_events(limit_events=6, limit_scan=100):
    """거래량 상위 활성 시장 중 거시경제 키워드가 포함된 것을 이벤트(사건) 단위로 묶는다.

    Polymarket Gamma API는 같은 사건의 여러 임계값 계약을 events[0].id로 묶어서
    제공한다(예: "Fed Decision in July?" 이벤트 아래 "25bps 인하"/"동결"/"25bps
    인상" 등 계약 여러 개). groupItemTitle이 그 계약의 임계값 라벨이다.

    반환: {"ok": bool, "error": str|None, "events": [{"source","event_id",
    "title","end_date","contracts":[{"label","probability_pct","volume_24h",
    "liquidity","updated_at"}]}, ...]}
    """
    try:
        resp = requests.get(
            POLYMARKET_GAMMA_URL,
            params={
                "active": "true",
                "closed": "false",
                "order": "volume24hr",
                "ascending": "false",
                "limit": limit_scan,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        markets = resp.json()
    except Exception:
        return {"ok": False, "error": "Polymarket 조회 실패", "events": []}

    if not isinstance(markets, list):
        return {"ok": False, "error": "Polymarket 응답 형식 오류", "events": []}

    events_by_id = {}
    for m in markets:
        question = m.get("question")
        if not _question_matches(question):
            continue
        end_date = (m.get("endDate") or "")[:10]
        if _is_expired(end_date):
            continue
        try:
            price = m.get("lastTradePrice")
            probability_pct = round(float(price) * 100, 1) if price is not None else None
        except (TypeError, ValueError):
            probability_pct = None

        events_field = m.get("events") or []
        event_id = events_field[0].get("id") if events_field else m.get("id")
        event_title = events_field[0].get("title") if events_field else question
        group_label = m.get("groupItemTitle")
        market_id = m.get("id")
        market_url = m.get("url")
        volume_24h = _to_float(m.get("volume24hr"))
        # 숫자 0으로 명확히 확인된 개별 시장만 제외한다. 값이 누락되거나 형식이
        # 불명확한 경우에는 0으로 단정하지 않고 그대로 보존한다.
        if volume_24h == 0:
            continue

        contract = {
            "source": "Polymarket",
            "market_id": market_id,
            "url": market_url,
            "label": group_label or "결과",
            "question": question,
            "probability_pct": probability_pct,
            "volume_24h": volume_24h,
            "liquidity": _to_float(m.get("liquidity")),
            "updated_at": m.get("updatedAt"),
        }
        group = events_by_id.setdefault(
            event_id,
            {
                "source": "Polymarket",
                "event_id": event_id,
                "title": event_title or question,
                "end_date": end_date,
                "contracts": [],
                "_seen": set(),
            },
        )
        # 질문·시장 ID·URL이 모두 같은 완전 중복만 제거한다. 같은 질문이라도 시장
        # ID나 URL이 다르면 별도 계약일 수 있으므로 보존한다.
        dedup_key = (
            (contract["question"], contract["market_id"], contract["url"])
            if contract["market_id"] is not None or contract["url"] is not None
            else (contract["question"], contract["label"], end_date)
        )
        if dedup_key in group["_seen"]:
            continue
        group["_seen"].add(dedup_key)
        group["contracts"].append(contract)
        group["end_date"] = min(group["end_date"], end_date) if group["end_date"] and end_date else (group["end_date"] or end_date)

    events = []
    for group in events_by_id.values():
        group.pop("_seen", None)
        if not group["contracts"]:
            continue
        known_volumes = [
            c["volume_24h"] for c in group["contracts"] if c["volume_24h"] is not None
        ]
        max_volume = max(known_volumes) if known_volumes else None
        group["contracts"].sort(key=lambda c: c.get("probability_pct") or 0, reverse=True)
        group["event_volume"] = max_volume
        events.append(group)

    events.sort(key=lambda e: e.get("event_volume") or -1, reverse=True)
    return {"ok": True, "error": None, "events": events[:limit_events]}


def fetch_kalshi_events(limit_events=6, max_series=15):
    """Economics/Politics 카테고리 시리즈 중 거시경제 키워드가 제목에 포함된 것만 골라,
    이벤트(event_ticker) 단위로 묶어서 반환한다.

    Kalshi 공개 시장 목록(/markets)은 거래량 정렬도, 키워드 검색도 지원하지 않아
    전체를 페이지째 훑으면 스포츠/연예 시장에 묻혀 거시경제 시장이 거의 안 걸린다
    (2026-07-13 실측 확인). 대신 시리즈(/series) 목록을 먼저 키워드로 좁히고, 그
    시리즈에 속한 시장만 조회하는 2단계 방식을 쓴다. 같은 event_ticker 아래 여러
    임계값 계약(yes_sub_title로 구분)이 있으면 하나의 이벤트로 묶는다.
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
    except Exception:
        return {"ok": False, "error": "Kalshi 시리즈 조회 실패", "events": []}

    events_by_ticker = {}
    for ticker in matched_series[:max_series]:
        if not ticker:
            continue
        try:
            resp = requests.get(
                KALSHI_MARKETS_URL,
                params={"series_ticker": ticker, "status": "open", "limit": 8},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            for m in resp.json().get("markets", []):
                end_date = (m.get("close_time") or "")[:10]
                if _is_expired(end_date):
                    continue
                volume_24h = _to_float(m.get("volume_24h_fp"))
                liquidity = _to_float(m.get("liquidity_dollars"))
                if volume_24h == 0:
                    continue
                try:
                    yes_bid = m.get("yes_bid_dollars")
                    probability_pct = round(float(yes_bid) * 100, 1) if yes_bid is not None else None
                except (TypeError, ValueError):
                    probability_pct = None

                event_ticker = m.get("event_ticker") or ticker
                market_id = m.get("ticker") or m.get("market_ticker")
                market_url = m.get("url")
                contract = {
                    "source": "Kalshi",
                    "market_id": market_id,
                    "url": market_url,
                    "label": m.get("yes_sub_title") or "결과",
                    "question": m.get("title"),
                    "probability_pct": probability_pct,
                    "volume_24h": volume_24h,
                    "liquidity": liquidity,
                    "updated_at": m.get("updated_time"),
                }
                group = events_by_ticker.setdefault(
                    event_ticker,
                    {
                        "source": "Kalshi",
                        "event_id": event_ticker,
                        "title": m.get("title"),
                        "end_date": end_date,
                        "contracts": [],
                        "_seen": set(),
                    },
                )
                dedup_key = (
                    (contract["question"], contract["market_id"], contract["url"])
                    if contract["market_id"] is not None or contract["url"] is not None
                    else (contract["question"], contract["label"], end_date)
                )
                if dedup_key in group["_seen"]:
                    continue
                group["_seen"].add(dedup_key)
                group["contracts"].append(contract)
        except Exception:
            continue

    events = []
    for group in events_by_ticker.values():
        group.pop("_seen", None)
        if not group["contracts"]:
            continue
        known_volumes = [
            c["volume_24h"] for c in group["contracts"] if c["volume_24h"] is not None
        ]
        max_volume = max(known_volumes) if known_volumes else None
        group["contracts"].sort(key=lambda c: c.get("probability_pct") or 0, reverse=True)
        group["event_volume"] = max_volume
        events.append(group)

    events.sort(key=lambda e: e.get("event_volume") or -1, reverse=True)
    return {"ok": True, "error": None, "events": events[:limit_events]}


def fetch_bookmaker_snapshot(limit_per_source=5):
    """Polymarket + Kalshi 거시경제 이벤트를 합쳐 거래량 순으로 정렬.

    한쪽이 실패해도 다른 쪽 결과는 살린다(theme_data.py의 개별 실패 허용 패턴과 동일).
    반환: {"ok": bool, "checked_at": str|None, "errors": [str, ...],
    "events": [...]}  (2026-07-13: 필드명이 "signals"에서 "events"로 바뀜 —
    이 함수를 쓰는 app.py도 함께 갱신해야 한다.)
    """
    poly = fetch_polymarket_events(limit_events=limit_per_source)
    kalshi = fetch_kalshi_events(limit_events=limit_per_source)

    errors = []
    if not poly.get("ok"):
        errors.append(f"Polymarket: {poly.get('error')}")
    if not kalshi.get("ok"):
        errors.append(f"Kalshi: {kalshi.get('error')}")

    events = (poly.get("events") or []) + (kalshi.get("events") or [])
    events.sort(key=lambda e: e.get("event_volume") or -1, reverse=True)

    return {
        "ok": bool(events),
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S") if events else None,
        "errors": errors,
        "events": events,
    }

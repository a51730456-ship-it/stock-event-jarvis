"""자비스3 종목 브리핑 뉴스: 작은 후보만 비동기로 해설한다.

뉴스가 실패해도 시세·시장판단 화면은 계속 열려야 한다. API 키는 환경변수나
Streamlit secrets에서 호출자가 전달하며 이 파일에는 저장하지 않는다.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen


CACHE_SECONDS = 600
_POOL = ThreadPoolExecutor(max_workers=3, thread_name_prefix="j3-brief-news")
_LOCK = threading.Lock()
_CACHE: dict[str, dict] = {}


def _text(value, limit=500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _time(value) -> datetime | None:
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _request(url: str, headers: dict | None = None) -> dict | list:
    request = Request(url, headers=headers or {"Accept": "application/json"})
    with urlopen(request, timeout=8) as response:  # nosec B310 - fixed HTTPS endpoints below
        return json.loads(response.read().decode("utf-8"))


def _dedupe(rows: list[dict]) -> list[dict]:
    seen, result = set(), []
    for row in rows:
        title, url = _text(row.get("headline")), _text(row.get("url"))
        if not title:
            continue
        words = " ".join(re.findall(r"[a-z0-9가-힣]+", title.lower())[:12])
        fingerprint = url or hashlib.sha1(words.encode("utf-8")).hexdigest()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        result.append(row)
    return result


def _finnhub(kind: str, ticker: str | None, key: str) -> list[dict]:
    now = datetime.now(timezone.utc)
    if kind == "market":
        params = {"category": "general", "token": key}
        endpoint = "https://finnhub.io/api/v1/news?" + urlencode(params)
    else:
        params = {
            "symbol": ticker, "from": (now - timedelta(hours=72)).date().isoformat(),
            "to": now.date().isoformat(), "token": key,
        }
        endpoint = "https://finnhub.io/api/v1/company-news?" + urlencode(params)
    payload = _request(endpoint)
    if not isinstance(payload, list):
        return []
    rows = []
    for raw in payload:
        published = _time(raw.get("datetime"))
        if published is None or published < now - timedelta(hours=72):
            continue
        rows.append({
            "headline": _text(raw.get("headline"), 300), "summary": _text(raw.get("summary"), 650),
            "source": _text(raw.get("source"), 80), "url": _text(raw.get("url"), 600),
            "published_at": published.isoformat(),
        })
    recent = [row for row in rows if _time(row["published_at"]) >= now - timedelta(hours=24)]
    return _dedupe(recent if recent else rows)[:10]


def _fallback(rows: list[dict]) -> list[dict]:
    return [{
        **row, "sentiment": "neutral", "brief": _text(row["headline"], 110),
    } for row in rows[:3]]


def _groq(rows: list[dict], label: str, key: str) -> list[dict]:
    if not rows:
        return []
    if not key:
        return _fallback(rows)
    prompt = (
        "당신은 투자 조언자가 아닌 뉴스 해설기다. 아래 뉴스 중 중복 사건은 하나로 줄이고, "
        "실제로 받은 뉴스만 최대 3건 골라 한국어 한줄평을 작성하라. 매수·매도·목표가·예측은 금지. "
        "각 항목은 sentiment(positive|negative|neutral), brief(90자 이내), index(0부터)를 가진 JSON 배열만 반환.\n"
        + json.dumps({"label": label, "news": rows}, ensure_ascii=False)
    )
    payload = {
        "model": "openai/gpt-oss-20b", "temperature": 0.1, "max_tokens": 600,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}],
    }
    # urllib POST를 분리해 GET 뉴스 호출과 같은 timeout/예외 정책을 유지한다.
    body = json.dumps(payload).encode("utf-8")
    request = Request("https://api.groq.com/openai/v1/chat/completions", data=body,
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urlopen(request, timeout=12) as response_obj:  # nosec B310 - fixed HTTPS endpoint
        response = json.loads(response_obj.read().decode("utf-8"))
    content = response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
    decoded = json.loads(content)
    picks = decoded.get("items", decoded) if isinstance(decoded, dict) else decoded
    result, used = [], set()
    for pick in picks if isinstance(picks, list) else []:
        index = pick.get("index")
        if not isinstance(index, int) or index < 0 or index >= len(rows) or index in used:
            continue
        used.add(index)
        result.append({**rows[index], "sentiment": pick.get("sentiment") if pick.get("sentiment") in {"positive", "negative", "neutral"} else "neutral", "brief": _text(pick.get("brief"), 110) or _text(rows[index]["headline"], 110)})
        if len(result) == 3:
            break
    return result or _fallback(rows)


def _load(cache_key: str, kind: str, ticker: str | None, finnhub_key: str, groq_key: str) -> dict:
    try:
        rows = _finnhub(kind, ticker, finnhub_key) if finnhub_key else []
        return {"ok": True, "items": _groq(rows, ticker or "미국시장", groq_key), "updated_at": time.time()}
    except Exception:
        return {"ok": False, "items": [], "message": "뉴스 브리핑 일시 사용 불가", "updated_at": time.time()}


def get_or_schedule(kind: str, ticker: str | None = None, *, finnhub_key: str = "", groq_key: str = "") -> dict:
    """기존 캐시를 즉시 반환하고, 만료분만 백그라운드에서 새로 만든다."""
    cache_key = f"{kind}:{str(ticker or '').upper()}"
    now = time.time()
    with _LOCK:
        current = _CACHE.get(cache_key)
        if current and now - current.get("updated_at", 0) < CACHE_SECONDS:
            return current.get("result", {"ok": True, "items": []})
        if current and current.get("future"):
            future = current["future"]
            if future.done():
                current["result"] = future.result()
                current["updated_at"] = now
                current.pop("future", None)
                return current["result"]
            return current.get("result", {"ok": True, "items": []})
        future = _POOL.submit(_load, cache_key, kind, ticker, finnhub_key, groq_key)
        _CACHE[cache_key] = {"future": future, "updated_at": now, "result": current.get("result", {"ok": True, "items": []}) if current else {"ok": True, "items": []}}
        return _CACHE[cache_key]["result"]

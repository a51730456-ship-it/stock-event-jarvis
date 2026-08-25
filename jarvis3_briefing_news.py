"""자비스3 종목 브리핑 뉴스: 작은 후보만 비동기로 해설한다.

뉴스가 실패해도 시세·시장판단 화면은 계속 열려야 한다. API 키는 환경변수나
Streamlit secrets에서 호출자가 전달하며 이 파일에는 저장하지 않는다.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import re
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

import news_data
import deepl_translate


CACHE_SECONDS = 600
ERROR_CACHE_SECONDS = 30
_POOL = ThreadPoolExecutor(max_workers=3, thread_name_prefix="j3-brief-news")
_LOCK = threading.Lock()
_CACHE: dict[str, dict] = {}


def _text(value, limit=500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _has_korean(value: str) -> bool:
    return bool(re.search(r"[가-힣]", str(value or "")))


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


def _request_text(url: str) -> str:
    request = Request(url, headers={
        "Accept": "application/rss+xml, application/xml, text/xml",
        "User-Agent": "Mozilla/5.0 (compatible; Jarvis3News/1.0)",
    })
    with urlopen(request, timeout=8) as response:  # nosec B310 - fixed Google News RSS endpoint below
        return response.read().decode("utf-8", errors="replace")


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


def _google_news_rss(kind: str, ticker: str | None) -> list[dict]:
    """미국 원문 기사를 받는 공개 RSS 뉴스원.

    첫 화면을 API 키 미설정 상태에서 영구적인 '불러오는 중'으로 남기지 않는다.
    RSS 원문·시간·출처를 그대로 보관하므로 사용자는 카드의 원문 확인에서 검증할 수 있다.
    """
    query = "US stock market" if kind == "market" else f"{str(ticker or '').upper()} stock"
    params = {"q": f"{query} when:3d", "hl": "en-US", "gl": "US", "ceid": "US:en"}
    endpoint = "https://news.google.com/rss/search?" + urlencode(params)
    root = ElementTree.fromstring(_request_text(endpoint))
    now = datetime.now(timezone.utc)
    rows = []
    for item in root.findall("./channel/item"):
        title = _text(item.findtext("title"), 300)
        link = _text(item.findtext("link"), 600)
        try:
            published = parsedate_to_datetime(str(item.findtext("pubDate") or "")).astimezone(timezone.utc)
        except (TypeError, ValueError, IndexError, OverflowError):
            continue
        if not title or published < now - timedelta(hours=72):
            continue
        source_node = item.find("source")
        source = _text(source_node.text if source_node is not None else "Google News", 80)
        rows.append({
            "headline": title, "summary": "", "source": source or "Google News", "url": link,
            "published_at": published.isoformat(),
        })
    recent = [row for row in rows if _time(row["published_at"]) >= now - timedelta(hours=24)]
    return _dedupe(recent if recent else rows)[:10]


def _naver_news(kind: str, ticker: str | None, client_id: str, client_secret: str) -> list[dict]:
    """기존 앱이 쓰는 Naver 뉴스 키가 있으면 우선 재사용한다."""
    if not client_id or not client_secret:
        return []
    result = news_data.fetch_naver_news(
        client_id, client_secret, "미국 증시" if kind == "market" else str(ticker or "").upper(), display=10, sort="date",
    )
    if result.get("status") not in {"정상", "데이터 없음"}:
        return []
    now = datetime.now(timezone.utc)
    rows = []
    for raw in result.get("data") or []:
        try:
            published = datetime.fromisoformat(str(raw.get("pub_date") or "").replace(" ", "T"))
            published = published.replace(tzinfo=timezone(timedelta(hours=9))).astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            continue
        if published < now - timedelta(hours=72):
            continue
        rows.append({
            "headline": _text(raw.get("title"), 300), "summary": _text(raw.get("description"), 650),
            "source": "Naver News", "url": _text(raw.get("originallink") or raw.get("link"), 600),
            "published_at": published.isoformat(),
        })
    recent = [row for row in rows if _time(row["published_at"]) >= now - timedelta(hours=24)]
    return _dedupe(recent if recent else rows)[:10]


def _fallback(rows: list[dict], deepl_key: str = "") -> list[dict]:
    """Groq가 없어도 미국 원문 제목을 한글로 묶음 번역한다."""
    selected = rows[:3]
    english = [_text(row.get("headline"), 300) for row in selected if not _has_korean(row.get("headline"))]
    translations = []
    if english and deepl_key:
        try:
            translations = deepl_translate.translate_texts_to_ko(english, deepl_key)
        except Exception:
            translations = []
    translated = iter(translations)
    result = []
    for row in selected:
        headline = _text(row.get("headline"), 300)
        brief = headline if _has_korean(headline) else _text(next(translated, ""), 110)
        if not _has_korean(brief):
            brief = "미국 원문 뉴스의 한글 번역을 잠시 불러오지 못했습니다."
        result.append({**row, "sentiment": "neutral", "brief": brief})
    return result


def _groq(rows: list[dict], label: str, key: str, deepl_key: str = "") -> list[dict]:
    if not rows:
        return []
    if not key:
        return _fallback(rows, deepl_key)
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
    try:
        with urlopen(request, timeout=12) as response_obj:  # nosec B310 - fixed HTTPS endpoint
            response = json.loads(response_obj.read().decode("utf-8"))
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        decoded = json.loads(content)
    except Exception:
        return _fallback(rows, deepl_key)
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
    if not result or any(not _has_korean(row.get("brief")) for row in result):
        return _fallback(rows, deepl_key)
    return result


def _load(cache_key: str, kind: str, ticker: str | None, finnhub_key: str, groq_key: str,
          naver_client_id: str = "", naver_client_secret: str = "", deepl_key: str = "") -> dict:
    rows = []
    loaders = []
    if finnhub_key:
        loaders.append(lambda: _finnhub(kind, ticker, finnhub_key))
    loaders.append(lambda: _google_news_rss(kind, ticker))
    if naver_client_id and naver_client_secret:
        loaders.append(lambda: _naver_news(kind, ticker, naver_client_id, naver_client_secret))
    for loader in loaders:
        try:
            rows = loader()
        except Exception:
            rows = []
        if rows:
            break
    return {"ok": True, "items": _groq(rows, ticker or "미국시장", groq_key, deepl_key), "updated_at": time.time()}


def get_or_schedule(kind: str, ticker: str | None = None, *, finnhub_key: str = "", groq_key: str = "",
                    naver_client_id: str = "", naver_client_secret: str = "", deepl_key: str = "") -> dict:
    """기존 캐시를 즉시 반환하고, 만료분만 백그라운드에서 새로 만든다."""
    cache_key = f"{kind}:{str(ticker or '').upper()}"
    now = time.time()
    with _LOCK:
        current = _CACHE.get(cache_key)
        if current and current.get("future"):
            future = current["future"]
            if future.done():
                current["result"] = future.result()
                current["updated_at"] = now
                current.pop("future", None)
                return current["result"]
            return {**current.get("result", {"ok": True, "items": []}), "pending": True}
        ttl = CACHE_SECONDS if current and current.get("result", {}).get("items") else ERROR_CACHE_SECONDS
        if current and now - current.get("updated_at", 0) < ttl:
            return current.get("result", {"ok": True, "items": []})
        future = _POOL.submit(_load, cache_key, kind, ticker, finnhub_key, groq_key,
                              naver_client_id, naver_client_secret, deepl_key)
        _CACHE[cache_key] = {"future": future, "updated_at": now, "result": current.get("result", {"ok": True, "items": []}) if current else {"ok": True, "items": []}}
        return {**_CACHE[cache_key]["result"], "pending": True}

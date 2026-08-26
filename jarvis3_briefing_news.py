"""자비스3 종목 브리핑 뉴스: 작은 후보만 비동기로 해설한다.

뉴스가 실패해도 시세·시장판단 화면은 계속 열려야 한다. API 키는 환경변수나
Streamlit secrets에서 호출자가 전달하며 이 파일에는 저장하지 않는다.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
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

import deepl_translate


CACHE_SECONDS = 600
ERROR_CACHE_SECONDS = 30
# 뒤 일꾼이 붙잡히면 화면이 「불러오는 중」에서 영영 굳는다(2026-08-26 상하님 지적).
# 이만큼 지나면 그 일을 버리고 새로 받는다.
STUCK_SECONDS = 90
# 뉴스 받기는 통신 대기가 대부분이라 일꾼을 늘려도 CPU를 거의 쓰지 않는다.
# 첫 화면이 한 번에 9곳(시장 1 + 종목 8)을 받으므로 3명이면 세 번을 기다렸다.
_POOL = ThreadPoolExecutor(max_workers=6, thread_name_prefix="j3-brief-news")
_LOCK = threading.Lock()
_CACHE: dict[str, dict] = {}
_TRANSLATION_LOCK = threading.Lock()
_TRANSLATION_CACHE: dict[str, str] = {}
# 한 번 옮긴 제목은 공책에 적어 둔다. 무료 번역기가 막히는 날에도 어제 본 기사는
# 한글로 그대로 나온다(2026-08-26 — gtx와 MyMemory가 같은 날 둘 다 429였다).
_TRANSLATION_FILE = Path(__file__).resolve().parent / "cache" / "j3_translations.json"
_TRANSLATION_LIMIT = 4000
_TRANSLATION_LOADED = False


def _load_translation_book() -> None:
    global _TRANSLATION_LOADED
    if _TRANSLATION_LOADED:
        return
    _TRANSLATION_LOADED = True
    try:
        saved = json.loads(_TRANSLATION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return
    if isinstance(saved, dict):
        with _TRANSLATION_LOCK:
            for key, value in saved.items():
                if isinstance(key, str) and isinstance(value, str):
                    _TRANSLATION_CACHE.setdefault(key, value)


def _save_translation_book() -> None:
    """실패해도 조용히 넘어간다. 공책이 없어도 화면은 그대로 돈다."""
    try:
        with _TRANSLATION_LOCK:
            items = list(_TRANSLATION_CACHE.items())[-_TRANSLATION_LIMIT:]
        _TRANSLATION_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = _TRANSLATION_FILE.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(dict(items), ensure_ascii=False), encoding="utf-8")
        temporary.replace(_TRANSLATION_FILE)
    except Exception:
        pass

# 한글 뉴스는 회사 한글 이름으로 찾아야 기사가 훨씬 많이 나온다.
# 여기에 없는 티커는 티커 그대로 찾고, 그래도 없으면 영문 원문을 받아 번역한다.
_KOREAN_NAMES = {
    "NVDA": "엔비디아", "TSLA": "테슬라", "PLTR": "팔란티어", "AMD": "AMD",
    "AAPL": "애플", "META": "메타", "AVGO": "브로드컴", "MSFT": "마이크로소프트",
    "GOOGL": "구글", "GOOG": "구글", "AMZN": "아마존", "NFLX": "넷플릭스",
    "INTC": "인텔", "MU": "마이크론", "QCOM": "퀄컴", "ARM": "ARM",
    "SMCI": "슈퍼마이크로", "COIN": "코인베이스", "RGTI": "리게티",
    "IONQ": "아이온큐", "MSTR": "마이크로스트래티지", "CRWD": "크라우드스트라이크",
    "ORCL": "오라클", "ADBE": "어도비", "UBER": "우버", "PANW": "팔로알토",
}

# 미국 매체는 회사 이름을 영어로 쓴다. 티커만으로는 안 걸리는 것을 여기에 적는다.
# (TSM 기사 제목은 "Taiwan Semiconductor…"라 티커 세 글자가 아예 없다)
_ENGLISH_ALIASES = {
    "NVDA": ("Nvidia",), "TSLA": ("Tesla",), "PLTR": ("Palantir",), "AMD": ("AMD",),
    "AAPL": ("Apple",), "META": ("Meta",), "AVGO": ("Broadcom",), "MSFT": ("Microsoft",),
    "GOOGL": ("Google", "Alphabet"), "GOOG": ("Google", "Alphabet"),
    "AMZN": ("Amazon",), "NFLX": ("Netflix",), "INTC": ("Intel",), "MU": ("Micron",),
    "QCOM": ("Qualcomm",), "ARM": ("Arm Holdings", "Arm "), "TSM": ("Taiwan Semiconductor", "TSMC"),
    "SMCI": ("Super Micro", "Supermicro"), "COIN": ("Coinbase",), "RGTI": ("Rigetti",),
    "IONQ": ("IonQ",), "MSTR": ("MicroStrategy", "Strategy"), "CRWD": ("CrowdStrike",),
    "ORCL": ("Oracle",), "ADBE": ("Adobe",), "UBER": ("Uber",), "PANW": ("Palo Alto",),
}

# 회사 이름이 여러 갈래로 적히는 종목만 여기에 더 적는다. 없으면 위 이름 하나만 쓴다.
_KOREAN_ALIASES = {
    "RGTI": ("리게티컴퓨팅", "리게티 컴퓨팅", "리게티"),
    "META": ("메타 플랫폼", "메타플랫폼", "메타"),
    "GOOGL": ("알파벳", "구글"), "GOOG": ("알파벳", "구글"),
    "AVGO": ("브로드컴",), "SMCI": ("슈퍼마이크로", "슈퍼 마이크로"),
}
# 시장 브리핑은 이 말 가운데 하나라도 든 기사만 쓴다. 없으면 국내장 기사가 섞인다.
_MARKET_MARKS = ("미국 증시", "미국증시", "미 증시", "뉴욕증시", "뉴욕 증시",
                 "나스닥", "S&P", "다우", "월가", "美 증시", "美증시",
                 "US STOCK", "U.S. STOCK", "WALL STREET", "NASDAQ", "DOW ",
                 "STOCK MARKET", "STOCKS", "TREASURY", "FED ", "S&P 500")
# 이름 뒤에 이 글자가 붙으면 여전히 그 회사다. 다른 글자가 붙으면 다른 낱말이다.
_PARTICLES = "은는이가을를의에도와과로만라야여요"


def _mentions(headline: str, name: str) -> bool:
    """이름이 딱 그 회사를 가리키며 나왔는지 본다.

    그냥 '들어 있나'로 보면 '메타'가 메타플래닛·메타바이오메드에도 걸린다.
    이름 뒤가 한글이면 다른 낱말이고, 조사(은·는·이·가…)면 그 회사다.
    """
    start = 0
    while True:
        found = headline.find(name, start)
        if found < 0:
            return False
        after = headline[found + len(name):found + len(name) + 1]
        if not ("가" <= after <= "힣") or after in _PARTICLES:
            return True
        start = found + 1


def _is_about(row: dict, kind: str, ticker: str | None) -> bool:
    """이 기사가 정말 그 시장·그 종목 이야기인지 본다.

    구글뉴스는 비슷하기만 해도 물어 온다. 거르지 않으면 테슬라 칸에 모더나 기사가,
    브로드컴 칸에 코스피 기사가 올라온다(2026-08-26 실제로 올라왔다).
    """
    headline = str(row.get("headline") or "")
    if kind == "market":
        upper_line = headline.upper()
        return any(mark.upper() in upper_line for mark in _MARKET_MARKS)
    symbol = str(ticker or "").upper()
    if not symbol:
        return True
    if symbol in headline.upper():
        return True
    english = _ENGLISH_ALIASES.get(symbol, ())
    upper = headline.upper()
    if any(alias.upper() in upper for alias in english):
        return True
    korean = _KOREAN_ALIASES.get(symbol) or ((_KOREAN_NAMES[symbol],) if symbol in _KOREAN_NAMES else ())
    if any(_mentions(headline, name) for name in korean):
        return True
    # 이름을 아는 종목인데 어느 이름도 안 나왔으면 다른 회사 기사다.
    # 이름을 모르는 종목은 거르지 않는다 — 거르면 카드가 통째로 빈다.
    return not (english or korean)


def _text(value, limit=500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _has_korean(value: str) -> bool:
    return bool(re.search(r"[가-힣]", str(value or "")))


def _public_translations(texts: list[str]) -> dict[str, str]:
    """DeepL 키가 없을 때 미국 원문 제목을 공개 번역으로 묶어 처리한다.

    화면 스레드가 아니라 기존 뉴스 백그라운드 작업에서만 호출된다. 같은 제목은
    프로세스 캐시에 남겨 10분 뉴스 갱신 때 번역 요청을 반복하지 않는다.
    """
    _load_translation_book()
    originals = list(dict.fromkeys(_text(text, 300) for text in texts if _text(text, 300)))
    with _TRANSLATION_LOCK:
        result = {text: _TRANSLATION_CACHE[text] for text in originals if text in _TRANSLATION_CACHE}
    missing = [text for text in originals if text not in result]
    # 익명 공개 번역의 한 요청 길이를 작게 유지한다. 제목은 화면 한줄용 160자까지만 쓴다.
    batches, batch, length = [], [], 0
    for original in missing:
        source = _text(original, 160)
        added = len(source) + (13 if batch else 0)
        if batch and length + added > 450:
            batches.append(batch)
            batch, length = [], 0
        batch.append((original, source))
        length += added
    if batch:
        batches.append(batch)
    def _record(original: str, translated_text: str) -> None:
        translated_text = _text(translated_text, 110)
        if not _has_korean(translated_text):
            return
        result[original] = translated_text
        with _TRANSLATION_LOCK:
            _TRANSLATION_CACHE[original] = translated_text

    def _by_chrome(pending: list[tuple[str, str]]) -> None:
        params = [("client", "dict-chrome-ex"), ("sl", "en"), ("tl", "ko")]
        params += [("q", source) for _, source in pending]
        payload = _request("https://clients5.google.com/translate_a/t?" + urlencode(params))
        rows = payload if isinstance(payload, list) else []
        if len(rows) != len(pending):
            return
        for (original, _), part in zip(pending, rows):
            if isinstance(part, str):
                _record(original, part)

    def _by_google(pending: list[tuple[str, str]]) -> None:
        delimiter = "|||59381|||"
        endpoint = "https://translate.googleapis.com/translate_a/single?" + urlencode({
            "client": "gtx", "sl": "en", "tl": "ko", "dt": "t",
            "q": f" {delimiter} ".join(source for _, source in pending),
        })
        payload = _request(endpoint)
        translated = "".join(
            str(part[0]) for part in (payload[0] if isinstance(payload, list) and payload else [])
            if isinstance(part, list) and part
        )
        parts = [part.strip() for part in translated.split(delimiter)]
        if len(parts) != len(pending):
            return
        for (original, _), part in zip(pending, parts):
            _record(original, part)

    def _by_mymemory(pending: list[tuple[str, str]]) -> None:
        joined = "\nJARVISBREAK\n".join(source for _, source in pending)
        endpoint = "https://api.mymemory.translated.net/get?" + urlencode({
            "q": joined, "langpair": "en|ko",
        })
        payload = _request(endpoint)
        translated = _text((payload.get("responseData") or {}).get("translatedText"), 1200)
        parts = re.split(r"\s*JARVISBREAK\s*", translated)
        if len(parts) != len(pending):
            return
        for (original, _), part in zip(pending, parts):
            _record(original, part)

    for items in batches:
        # 번역기 한 곳이 막히거나 구분자를 흐트러뜨려도 다음 번역기가 반드시 이어받는다.
        # 예전에는 첫 번역기가 실패하면 continue로 batch를 통째로 건너뛰어
        # 둘째 번역기가 영영 돌지 않았다(2026-08-26 실측).
        for translate in (_by_chrome, _by_mymemory, _by_google):
            pending = [(original, source) for original, source in items if original not in result]
            if not pending:
                break
            try:
                translate(pending)
            except Exception:
                continue
    if result:
        _save_translation_book()
    return result


def _time(value) -> datetime | None:
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _request(url: str, headers: dict | None = None) -> dict | list:
    request = Request(url, headers=headers or {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; Jarvis3News/1.0)",
    })
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
    """같은 사건을 두 번 싣지 않는다.

    주소와 제목을 **둘 다** 본다. 예전에는 주소가 있으면 주소만 봐서, 매체가 달라
    주소가 다르면 같은 기사가 두 줄로 올라왔다(2026-08-26 — 시장 브리핑 세 줄 가운데
    둘이 "US Stock Market Today: S&P 500 Futures Edge Lower…"로 겹쳤다).
    """
    seen, result = set(), []
    for row in rows:
        title, url = _text(row.get("headline")), _text(row.get("url"))
        if not title:
            continue
        words = " ".join(re.findall(r"[a-z0-9가-힣]+", title.lower())[:7])
        marks = {hashlib.sha1(words.encode("utf-8")).hexdigest()}
        if url:
            marks.add(url)
        if marks & seen:
            continue
        seen |= marks
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


def _rss_rows(params: dict) -> list[dict]:
    """구글뉴스 RSS 한 판을 읽어 기사 줄로 바꾼다. 영문·한글 뉴스원이 함께 쓴다."""
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


def _google_news_rss(kind: str, ticker: str | None) -> list[dict]:
    """미국 원문 기사를 받는 공개 RSS 뉴스원.

    첫 화면을 API 키 미설정 상태에서 영구적인 '불러오는 중'으로 남기지 않는다.
    RSS 원문·시간·출처를 그대로 보관하므로 사용자는 카드의 원문 확인에서 검증할 수 있다.
    """
    query = "US stock market" if kind == "market" else f"{str(ticker or '').upper()} stock"
    rows = _rss_rows({"q": f"{query} when:3d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
    kept = [row for row in rows if _is_about(row, kind, ticker)]
    # 걸러서 세 줄이 안 차면 거르기 전 것을 쓴다. 화면은 늘 세 줄이어야 한다
    # (2026-08-26 상하님 지시 — "한 줄씩 3줄로 만들어라, 원래 화면대로").
    return kept if len(kept) >= 3 else rows




def _fallback(rows: list[dict], deepl_key: str = "") -> list[dict]:
    """Groq가 없어도 미국 원문 제목을 한글로 묶음 번역한다."""
    selected = rows[:3]
    english = [_text(row.get("headline"), 300) for row in selected if not _has_korean(row.get("headline"))]
    translations = {}
    if english and deepl_key:
        try:
            translated_result = deepl_translate.translate_texts_to_ko(english, deepl_key)
            if isinstance(translated_result, dict):
                translations = translated_result.get("translations") or {}
        except Exception:
            translations = {}
    if english:
        missing = [headline for headline in english if headline not in translations]
        if missing:
            translations.update(_public_translations(missing))
    result = []
    for row in selected:
        headline = _text(row.get("headline"), 300)
        brief = headline if _has_korean(headline) else _text(translations.get(headline), 110)
        if not _has_korean(brief):
            # 번역이 다 막힌 날에도 화면은 진짜 기사 제목을 보여 준다. 예전에는 여기서
            # 안내 문구만 세 줄 되풀이돼 무슨 뉴스인지조차 알 수 없었다(2026-08-26).
            brief = _text(headline, 110)
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
    # 언제나 미국 원문 기사를 먼저 받는다(2026-08-26 상하님 — "미국 뉴스를 갖고
    # 오는 게 아니냐"). 로이터·워싱턴포스트·배런스 같은 미국 매체 기사를 받아
    # 한글로 옮긴다. 한글 매체 기사는 번역이 다 막힌 날의 대비책일 뿐이다.
    if finnhub_key:
        loaders.append(lambda: _finnhub(kind, ticker, finnhub_key))
    loaders.append(lambda: _google_news_rss(kind, ticker))
    for loader in loaders:
        try:
            rows = loader()
        except Exception:
            rows = []
        if rows:
            break
    return {"ok": True, "items": _groq(rows, ticker or "미국시장", groq_key, deepl_key),
            "updated_at": time.time()}


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
                try:
                    current["result"] = future.result()
                except Exception:
                    # 뒤에서 터진 일은 화면으로 올리지 않는다. 빈 결과로 두고 다시 받게 한다.
                    current["result"] = {"ok": True, "items": []}
                    current["updated_at"] = 0
                else:
                    current["updated_at"] = now
                current.pop("future", None)
                return current["result"]
            if now - current.get("started_at", now) > STUCK_SECONDS:
                # 너무 오래 붙잡혀 있다. 그 일은 버리고 아래에서 새로 시킨다.
                future.cancel()
                current.pop("future", None)
            else:
                return {**current.get("result", {"ok": True, "items": []}), "pending": True}
        ttl = CACHE_SECONDS if current and current.get("result", {}).get("items") else ERROR_CACHE_SECONDS
        if current and now - current.get("updated_at", 0) < ttl:
            return current.get("result", {"ok": True, "items": []})
        future = _POOL.submit(_load, cache_key, kind, ticker, finnhub_key, groq_key,
                              naver_client_id, naver_client_secret, deepl_key)
        _CACHE[cache_key] = {"future": future, "updated_at": now, "started_at": now,
                             "result": current.get("result", {"ok": True, "items": []}) if current else {"ok": True, "items": []}}
        return {**_CACHE[cache_key]["result"], "pending": True}


def peek(kind: str, ticker: str | None = None) -> str:
    """예약된 뉴스 작업이 끝났는지만 본다. 새 작업을 시작하지 않는다.

    화면이 '다 왔나' 물어보려고 부르는 자리다. 여기서 새 작업을 걸면 화면이
    스스로를 계속 깨우는 쳇바퀴가 된다.
    """
    cache_key = f"{kind}:{str(ticker or '').upper()}"
    with _LOCK:
        current = _CACHE.get(cache_key)
        if current is None:
            return "none"
        future = current.get("future")
        return "pending" if future is not None and not future.done() else "ready"


def all_ready(keys) -> bool:
    """이번 화면이 기다리는 뉴스가 하나도 안 남았으면 참."""
    return all(peek(kind, ticker) != "pending" for kind, ticker in keys)


def ready_count(keys) -> int:
    """지금까지 도착한 자리가 몇 곳인지 센다.

    화면은 다 오기를 기다리지 않고, 온 만큼 그때그때 채워 그린다. 무료 번역이
    한 번에 여러 요청을 받으면 뒤쪽이 느려지는데, 그동안 위쪽 시장 브리핑과
    사용자 선정 종목까지 빈칸으로 두면 안 된다(2026-08-26).
    """
    return sum(1 for kind, ticker in keys if peek(kind, ticker) != "pending")


def clear_cache() -> None:
    """담아 둔 뉴스를 비운다. 화면의 ↻ 단추가 부른다.

    옮겨 둔 번역 공책은 지우지 않는다 — 그건 다시 받을 필요가 없는 것이다.
    """
    with _LOCK:
        _CACHE.clear()

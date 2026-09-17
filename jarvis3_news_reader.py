"""자비스3 뉴스 — 기사를 **앱이 대신 받아 광고 없이 본문만 한글로** 보여 준다.

2026-09-17 상하님 지적 — *"관심종목에서 종목 뉴스 클릭하면 광고가 너무 많아
내용을 덮어 버려 내용을 볼 수가 없다. 해결해라."* 두 길을 여쭈었고 상하님이
**"가"** — 앱이 기사를 받아 글만 뽑아 번역 — 로 정하셨다.

하는 일 네 가지.
  ① 구글 뉴스 주소(news.google.com/rss/articles/…)를 **진짜 기사 주소로 푼다.**
  ② 그 기사를 받아 **본문 문단만** 뽑는다 — 광고·메뉴·구독 권유·관련 기사 목록은 버린다.
  ③ 앞에서부터 MAX_CHARS 글자까지를 **무료 번역기로** 한글로 옮긴다.
     **DeepL 은 쓰지 않는다** — 제목 번역이 그 한도를 쓰고 있어, 본문까지 보내면
     며칠 만에 한도가 차서 제목까지 영어로 돌아간다.
  ④ 결과를 기사 주소별로 공책(cache/j3_articles.json)에 적어 둔다. 한 번 옮긴 기사는
     다시 받지 않는다.

**못 받는 기사가 있다** — 유료 기사(배런스·WSJ)와 사람만 들이는 사이트(바차트·
스톡트윗·인베스팅)는 문을 닫는다. 그때는 사이트가 스스로 적어 둔 **요약 한두 줄**을
옮기고, 그것도 없으면 「앱이 본문을 못 받는 기사」라고 적는다. 원문 링크는 늘 남긴다.

**화면을 기다리게 하지 않는다**(CLAUDE.md 0-0). 모든 받기는 뒤 일꾼이 하고,
화면은 공책에 이미 있는 것만 읽는다.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, wait
from pathlib import Path
import json
import re
import threading
import time

import requests

MODULE_REVISION = 2026091710

# 번역에 보내는 본문 길이. 기사 앞부분(대개 문단 6~10개)이면 무슨 내용인지 다 나온다.
MAX_CHARS = 1800
MAX_HTML_CHARS = 2_000_000
# 통신이 잠깐 막힌 기사는 10분 뒤 다시 받는다. 문을 닫은 기사(유료·차단)는 하루 뒤.
RETRY_SECONDS = 600
BLOCKED_SECONDS = 86_400
BOOK_LIMIT = 400
_TIMEOUT = 8

_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="j3-news-read")
# 구글·번역기에 한꺼번에 몰아 보내면 막힌다(2026-08-26 번역기 429 실측) — 둘씩만.
_GOOGLE_GATE = threading.Semaphore(2)
_TRANSLATE_GATE = threading.Semaphore(2)
_LOCK = threading.Lock()
_CACHE: dict[str, dict] = {}
_INFLIGHT: dict[str, Future] = {}
_BOOK = Path(__file__).resolve().parent / "cache" / "j3_articles.json"
_BOOK_LOADED = False

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}
# 사이트가 문을 닫았다는 답 — 다시 두드려도 안 열린다.
_BLOCKED_STATUS = {202, 401, 402, 403, 451}


# ── 공책 ────────────────────────────────────────────────────────────────────
def _load_book() -> None:
    global _BOOK_LOADED
    if _BOOK_LOADED:
        return
    _BOOK_LOADED = True
    try:
        saved = json.loads(_BOOK.read_text(encoding="utf-8"))
    except Exception:
        return
    if isinstance(saved, dict):
        with _LOCK:
            for url, row in saved.items():
                if isinstance(url, str) and isinstance(row, dict):
                    _CACHE.setdefault(url, row)


def _save_book() -> None:
    """실패해도 조용히 넘어간다. 공책이 없어도 화면은 그대로 돈다."""
    try:
        with _LOCK:
            rows = sorted(_CACHE.items(), key=lambda pair: float(pair[1].get("at") or 0))
            keep = dict(rows[-BOOK_LIMIT:])
        _BOOK.parent.mkdir(parents=True, exist_ok=True)
        temporary = _BOOK.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(keep, ensure_ascii=False), encoding="utf-8")
        temporary.replace(_BOOK)
    except Exception:
        pass


def _expired(row: dict, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    age = now - float(row.get("at") or 0)
    status = row.get("status")
    if status in ("ok", "summary"):
        return False
    if status == "blocked":
        return age > BLOCKED_SECONDS
    return age > RETRY_SECONDS       # english(번역만 막힘) · failed(통신 실패)


def get(url: str) -> dict | None:
    """공책에 있는 것만 돌려준다. 받으러 가지 않는다 — 화면이 부르는 자리다."""
    url = str(url or "").strip()
    if not url:
        return None
    _load_book()
    with _LOCK:
        row = _CACHE.get(url)
    return dict(row) if row else None


def pending(url: str) -> bool:
    """지금 뒤에서 받는 중이면 참."""
    with _LOCK:
        future = _INFLIGHT.get(str(url or "").strip())
    return future is not None and not future.done()


def schedule(urls) -> list[Future]:
    """아직 없거나 다시 받을 때가 된 기사만 뒤 일꾼에게 맡긴다. 기다리지 않는다."""
    _load_book()
    futures = []
    now = time.time()
    for url in dict.fromkeys(str(u or "").strip() for u in (urls or [])):
        if not url.startswith("http"):
            continue
        with _LOCK:
            running = _INFLIGHT.get(url)
            if running is not None and not running.done():
                futures.append(running)
                continue
            row = _CACHE.get(url)
            if row is not None and not _expired(row, now):
                continue
            try:
                future = _POOL.submit(_read_and_keep, url)
            except Exception:
                continue
            _INFLIGHT[url] = future
        futures.append(future)
    return futures


def read_now(urls, budget: float) -> None:
    """맡기고 **budget 초까지만** 기다린다. 늦는 것은 뒤에서 마저 받는다."""
    futures = schedule(urls)
    if futures and budget > 0:
        wait(futures, timeout=budget)


def _read_and_keep(url: str) -> dict:
    try:
        row = read_article(url)
    except Exception:
        row = {"status": "failed", "paragraphs": []}
    row["at"] = time.time()
    with _LOCK:
        _CACHE[url] = row
        _INFLIGHT.pop(url, None)
    _save_book()
    return row


# ── 받기 ────────────────────────────────────────────────────────────────────
def resolve_google_news(url: str) -> str | None:
    """news.google.com/rss/articles/<id> → 진짜 기사 주소. 구글 주소가 아니면 그대로.

    구글이 주소를 암호처럼 감춰 두어, 그 기사 쪽지에 적힌 서명(data-n-a-sg)과
    시각(data-n-a-ts)을 받아 구글에 한 번 더 물어야 원래 주소를 알려 준다.
    """
    match = re.search(r"news\.google\.com/(?:rss/)?articles/([^?/#]+)", url)
    if not match:
        return url
    article_id = match.group(1)
    with _GOOGLE_GATE:
        page = requests.get(f"https://news.google.com/rss/articles/{article_id}",
                            headers=_HEADERS, timeout=_TIMEOUT)
        signature = re.search(r'data-n-a-sg="([^"]+)"', page.text)
        stamp = re.search(r'data-n-a-ts="([^"]+)"', page.text)
        if not (signature and stamp):
            return None
        inner = ["garturlreq",
                 [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None,
                   None, None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
                 article_id, int(stamp.group(1)), signature.group(1)]
        request = [[["Fbv4je", json.dumps(inner, separators=(",", ":")), None, "generic"]]]
        answer = requests.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute",
            data={"f.req": json.dumps(request, separators=(",", ":"))},
            headers={**_HEADERS,
                     "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
            timeout=_TIMEOUT)
    body = answer.text.split("\n\n", 1)[-1]
    real = json.loads(json.loads(body)[0][2])[1]
    return real if isinstance(real, str) and real.startswith("http") else None


def read_article(url: str) -> dict:
    """기사 하나를 받아 {"status", "paragraphs", "source_url"} 로 돌려준다.

    status — ok(한글 본문) · english(본문은 뽑았는데 번역이 막힘) ·
             summary(본문이 없어 사이트 요약만 옮김) · blocked(문을 닫음) · failed(통신 실패)
    """
    real = resolve_google_news(url)
    if not real:
        return {"status": "failed", "paragraphs": []}
    response = requests.get(real, headers=_HEADERS, timeout=_TIMEOUT)
    if response.status_code in _BLOCKED_STATUS:
        return {"status": "blocked", "paragraphs": [], "source_url": real}
    if response.status_code != 200:
        return {"status": "failed", "paragraphs": [], "source_url": real}
    paragraphs, summary = extract_article(response.text[:MAX_HTML_CHARS])
    paragraphs = trim_paragraphs(paragraphs, MAX_CHARS)
    if paragraphs:
        korean = translate_paragraphs(paragraphs)
        if korean:
            return {"status": "ok", "paragraphs": korean, "source_url": real}
        return {"status": "english", "paragraphs": paragraphs, "source_url": real}
    if summary:
        korean = translate_paragraphs([summary])
        if korean:
            return {"status": "summary", "paragraphs": korean, "source_url": real}
    return {"status": "blocked", "paragraphs": [], "source_url": real}


# ── 본문 뽑기 ────────────────────────────────────────────────────────────────
# 짧은 문단에만 적용한다. 긴 문단에 이 말이 섞였다고 버리면 본문이 날아간다 —
# 마켓비트는 첫 문장마다 「(NASDAQ:TSLA - Free Report)」가 붙는다.
_JUNK = re.compile(
    r"(subscribe|sign up|newsletter|cookie|advertis|all rights reserved|click here|"
    r"read more|related:|see also|download the|terms of (use|service)|privacy policy|"
    r"copyright|©|get the app|follow us|share this)", re.I)
_TAIL_NOISE = re.compile(r"\s*-\s*Free Report\s*(?=\))", re.I)


def _clean(text: str) -> str:
    text = _TAIL_NOISE.sub("", str(text or ""))
    return re.sub(r"\s+", " ", text).strip()


def _is_junk(text: str) -> bool:
    return len(text) < 220 and bool(_JUNK.search(text))


def _ld_article_body(raw: str) -> list[str]:
    try:
        data = json.loads(raw or "")
    except Exception:
        return []
    stack = [data]
    while stack:
        current = stack.pop()
        if isinstance(current, list):
            stack.extend(current)
        elif isinstance(current, dict):
            body = current.get("articleBody")
            if isinstance(body, str) and len(body) > 300:
                parts = [_clean(part) for part in re.split(r"\n+", body)]
                parts = [part for part in parts if len(part) >= 40 and not _is_junk(part)]
                if len(parts) == 1 and len(parts[0]) > 900:
                    # 문단 구분 없이 한 덩이로 준 사이트 — 문장 네다섯 개씩 나눈다.
                    sentences = re.split(r"(?<=[.!?])\s+", parts[0])
                    parts = [" ".join(sentences[i:i + 4]) for i in range(0, len(sentences), 4)]
                return parts
            stack.extend(value for value in current.values() if isinstance(value, (dict, list)))
    return []


def extract_article(raw_html: str) -> tuple[list[str], str]:
    """(본문 문단들, 사이트 요약) — 본문이 두 문단·400자에 못 미치면 본문은 빈 목록."""
    try:
        from lxml import html as lxml_html

        document = lxml_html.fromstring(raw_html)
    except Exception:
        return [], ""
    summary = ""
    for path in ('//meta[@property="og:description"]/@content',
                 '//meta[@name="description"]/@content'):
        found = document.xpath(path)
        if found and len(_clean(found[0])) >= 60:
            summary = _clean(found[0])
            break
    for node in document.xpath('//script[@type="application/ld+json"]'):
        body = _ld_article_body(node.text_content())
        if _enough(body):
            return body, summary
    for bad in document.xpath("//script|//style|//noscript|//aside|//nav|//footer|//header|"
                              "//form|//figure|//iframe|//svg|//button|//select"):
        try:
            bad.drop_tree()
        except Exception:
            continue
    scores: dict = {}
    for paragraph in document.iter("p"):
        text = _clean(paragraph.text_content())
        if len(text) < 60 or _is_junk(text):
            continue
        parent = paragraph.getparent()
        if parent is None:
            continue
        scores[parent] = scores.get(parent, 0.0) + len(text)
        grand = parent.getparent()
        if grand is not None:
            scores[grand] = scores.get(grand, 0.0) + len(text) / 2
    if not scores:
        return [], summary
    best = max(scores, key=scores.get)
    body = [text for text in (_clean(p.text_content()) for p in best.iter("p"))
            if len(text) >= 40 and not _is_junk(text)]
    return (body if _enough(body) else []), summary


def _enough(paragraphs: list[str]) -> bool:
    return len(paragraphs) >= 2 and sum(len(p) for p in paragraphs) >= 400


def trim_paragraphs(paragraphs: list[str], limit: int) -> list[str]:
    """앞에서부터 limit 글자까지 — 문단 가운데서 자르지 않는다(첫 문단은 예외)."""
    kept, total = [], 0
    for paragraph in paragraphs:
        if kept and total + len(paragraph) > limit:
            break
        kept.append(paragraph[:limit])
        total += len(paragraph)
    return kept


# ── 번역 ────────────────────────────────────────────────────────────────────
def _has_korean(text: str) -> bool:
    return bool(re.search(r"[가-힣]", str(text or "")))


def translate_paragraphs(paragraphs: list[str]) -> list[str] | None:
    """문단들을 한글로. 번역기 둘을 차례로 써 보고 다 막히면 None."""
    paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        return None
    if all(_has_korean(p) for p in paragraphs):
        return paragraphs
    for translate in (_by_google_single, _by_chrome):
        try:
            with _TRANSLATE_GATE:
                result = translate(paragraphs)
        except Exception:
            continue
        if result and len(result) == len(paragraphs) and all(_has_korean(r) for r in result):
            return result
    return None


def _by_google_single(paragraphs: list[str]) -> list[str] | None:
    response = requests.post(
        "https://translate.googleapis.com/translate_a/single",
        params={"client": "gtx", "sl": "auto", "tl": "ko", "dt": "t"},
        data={"q": "\n".join(paragraphs)}, headers=_HEADERS, timeout=_TIMEOUT)
    if response.status_code != 200:
        return None
    payload = response.json()
    text = "".join(str(part[0]) for part in (payload[0] if payload else [])
                   if isinstance(part, list) and part and part[0])
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return lines if len(lines) == len(paragraphs) else None


def _by_chrome(paragraphs: list[str]) -> list[str] | None:
    response = requests.post(
        "https://clients5.google.com/translate_a/t",
        params={"client": "dict-chrome-ex", "sl": "auto", "tl": "ko"},
        data=[("q", p) for p in paragraphs], headers=_HEADERS, timeout=_TIMEOUT)
    if response.status_code != 200:
        return None
    rows = response.json()
    out = []
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, list) and row:
            row = row[0]
        if not isinstance(row, str):
            return None
        out.append(row.strip())
    return out

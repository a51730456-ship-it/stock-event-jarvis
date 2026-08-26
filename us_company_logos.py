"""미국 회사 로고 그림을 받아 두었다가 카드에 쓴다 (2026-08-26 상하님 지시).

상하님이 알려 주신 곳 — https://companiesmarketcap.com
그 사이트는 회사 로고를 티커 이름으로 정해진 자리에 두고 있어서, 티커만 알면
바로 받을 수 있다. `robots.txt`도 `/img/` 를 막지 않는다(2026-08-26 확인).

**왜 미리 받아 두지 않고 그때그때 받나**
상하님이 어떤 종목을 넣으실지 미리 알 수 없다. 종목을 넣으시는 그 자리에서
받아 두면 앞으로 어떤 종목이든 로고가 나온다.

**화면을 멈추지 않는다.** 받는 일은 뒤에서 하고, 아직 안 온 로고는 그 회사
글자표로 보여 준다. 다음 판에 그림이 나온다. 통신이 막혀도 예외를 밖으로
내보내지 않는다.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen


MODULE_REVISION = 2026082601

# 64px짜리는 회사에 따라 거의 빈 그림이 온다(MSFT는 104바이트였다). 256px을 쓴다.
LOGO_SIZE = 256
SOURCE = "https://companiesmarketcap.com/img/company-logos/{size}/{ticker}.webp"
CACHE_DIR = Path(__file__).resolve().parent / "cache" / "logos"
HTTP_TIMEOUT = 8
# 못 찾은 티커를 계속 다시 받으러 가지 않는다. 이만큼 지나야 한 번 더 해 본다.
MISS_RETRY_SECONDS = 21600

# 그 사이트가 쓰는 티커가 우리와 다른 것만 적는다.
TICKER_ALIASES = {
    "GOOGL": "GOOG",
    "BRK.B": "BRK-B", "BRK.A": "BRK-A",
    "BF.B": "BF-B",
}

_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="j3-logo")
_LOCK = threading.Lock()
_MEMORY: dict[str, bytes] = {}
_MISSES: dict[str, float] = {}
_WORKING: set[str] = set()


def _clean(ticker) -> str:
    value = str(ticker or "").strip().upper()
    if not value or len(value) > 16:
        return ""
    return value if all(ch.isalnum() or ch in "-._" for ch in value) else ""


def _cache_path(ticker: str) -> Path:
    return CACHE_DIR / f"{ticker}.webp"


def _download(ticker: str) -> None:
    """뒤에서 한 번 받아 공책(디스크)에 적어 둔다. 실패해도 조용히 넘어간다."""
    try:
        url = SOURCE.format(size=LOGO_SIZE, ticker=TICKER_ALIASES.get(ticker, ticker))
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; Jarvis3/1.0)"})
        with urlopen(request, timeout=HTTP_TIMEOUT) as response:  # nosec B310 - 고정 HTTPS 주소
            body = response.read()
        # 너무 작으면 로고가 아니라 빈 그림이다. 받은 셈 치지 않는다.
        if len(body) < 200 or not body.startswith(b"RIFF"):
            raise ValueError("로고 그림이 아니다")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        temporary = _cache_path(ticker).with_suffix(".webp.tmp")
        temporary.write_bytes(body)
        temporary.replace(_cache_path(ticker))
        with _LOCK:
            _MEMORY[ticker] = body
            _MISSES.pop(ticker, None)
    except Exception:
        with _LOCK:
            _MISSES[ticker] = time.time()
    finally:
        with _LOCK:
            _WORKING.discard(ticker)


def get_or_schedule(ticker) -> bytes | None:
    """있으면 로고 그림을 바로 준다. 없으면 뒤에서 받기 시작하고 None을 준다."""
    ticker = _clean(ticker)
    if not ticker:
        return None
    with _LOCK:
        found = _MEMORY.get(ticker)
        if found:
            return found
    path = _cache_path(ticker)
    try:
        if path.is_file():
            body = path.read_bytes()
            if body.startswith(b"RIFF"):
                with _LOCK:
                    _MEMORY[ticker] = body
                return body
    except OSError:
        pass
    with _LOCK:
        missed_at = _MISSES.get(ticker)
        if missed_at is not None and time.time() - missed_at < MISS_RETRY_SECONDS:
            return None
        if ticker in _WORKING:
            return None
        _WORKING.add(ticker)
    try:
        _POOL.submit(_download, ticker)
    except Exception:
        with _LOCK:
            _WORKING.discard(ticker)
    return None


def pending(ticker) -> bool:
    """지금 받고 있는 중인가. 화면이 '조금 뒤 다시 그려라'를 알아보는 데 쓴다."""
    ticker = _clean(ticker)
    with _LOCK:
        return bool(ticker) and ticker in _WORKING

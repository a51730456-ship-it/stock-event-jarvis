"""한국 「시장 현황」 — 네이버 「증시 현황」처럼 시장 전체 업종 지도 자료 (2026-11-05 상하님 「미국테마처럼 하라고 한국테마도 배치도」 ·
「이거 네이버다」 — 네이버 증시 현황 캡처).

  · 칸 크기 = 그 업종이 한국 시장에서 차지하는 몫(업종 구성 종목 시가총액 합 · data/kr_sectors.json · 깃허브가 주 1회 모음)
  · 색 = 그 업종 오늘 등락(네이버 업종 목록 한 번 · 화면이 손님끼리 같이 씀)
  · 밑 막대 = 시장 전체 오름 · 그대로 · 내림 종목 수(네이버 업종마다 센 것을 더함)
옛 자비스 파일을 부르지 않는다(CLAUDE.md 0-5). 점수 · 판정에 안 쓴다(보여 주기만). 못 받으면 None — 화면은 예전 테마 지도로 그린다.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

MODULE_REVISION = 2026111101
ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "kr_sectors.json"
LIST_API = "https://m.stock.naver.com/api/stocks/industry?page={page}&pageSize=100"
MAX_TILES = 30
REFRESH_SECONDS = 55.0       # 이만큼 지난 값이면 뒤에서 새로 받는다(화면 1분 자동 갱신보다 짧게) · 못 받았을 때 다시 받으러 가는 틈도 이만큼
FIRST_WAIT_SECONDS = 3.0     # 값이 아예 없을 때(배포 뒤 첫 손님)만 이만큼까지 기다린다
_LOCK = threading.Lock()
_MEMO: dict = {"mtime": None, "value": {}}
_LIVE_LOCK = threading.Lock()
_LIVE: dict = {"rows": None, "at": 0.0, "tried": 0.0, "busy": False}


def _num(value):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def sizes(path: Path = DATA_PATH) -> dict:
    """업종 번호 → {name, mcap(억 원)} — 파일이 바뀔 때만 다시 읽는다. 없으면 빈 dict."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    with _LOCK:
        if _MEMO["mtime"] == mtime:
            return _MEMO["value"]
    try:
        sectors = json.loads(path.read_text(encoding="utf-8")).get("sectors") or []
    except (OSError, ValueError):
        return {}
    value = {str(s.get("no")): {"name": str(s.get("name") or ""), "mcap": _num(s.get("mcap"))} for s in sectors}
    with _LOCK:
        _MEMO.update({"mtime": mtime, "value": value})
    return value


def fetch_live(session=None, timeout: float = 6.0) -> list:
    """네이버 업종 목록(오늘 등락 · 오름/그대로/내림 종목 수). 실패하면 예외 — 부르는 쪽이 옛 값을 쓴다."""
    import requests

    getter = session or requests
    rows = []
    for page in range(1, 4):
        response = getter.get(LIST_API.format(page=page), timeout=timeout,
                              headers={"User-Agent": "Mozilla/5.0 (jarvis13)", "Referer": "https://m.stock.naver.com/"})
        response.raise_for_status()
        groups = response.json().get("groups") or []
        for group in groups:
            rows.append({"no": str(group.get("no") or ""), "name": str(group.get("name") or "").strip(),
                         "change": _num(group.get("changeRate")), "rise": int(_num(group.get("riseCount")) or 0),
                         "steady": int(_num(group.get("steadyCount")) or 0), "fall": int(_num(group.get("fallCount")) or 0)})
        if len(groups) < 100:
            break
    if not rows:
        raise RuntimeError("업종 목록이 비었습니다")
    return rows


def _refresh(fetch) -> None:
    try:
        rows = fetch()
    except Exception:
        rows = None                                   # 못 받으면 있던 값을 그대로 둔다(지우지 않음)
    with _LIVE_LOCK:
        if rows:
            _LIVE.update(rows=rows, at=time.time())
        _LIVE["busy"] = False


def live_rows(fetch=None, *, first_wait: float = FIRST_WAIT_SECONDS) -> list | None:
    """업종 등락 — **화면은 받는 것을 기다리지 않는다**(CLAUDE.md 0-0 ①②).

    55초 지난 값이면 뒤에서 새로 받고, 지금은 있던 값을 그대로 준다. 못 받아도 있던 값을 두고, 다시 받으러 가는 것은 55초에 한 번뿐이다.
    값이 아예 없을 때(배포 뒤 첫 손님)만 길어야 first_wait 초 기다린다. 전(2026-11-05 판)에는 55초마다 화면 한 판이 네이버를
    기다렸고, 못 받으면 있던 값을 버리고 판마다 다시 받으러 갔다(한 번에 길어야 6초).
    """
    fetch = fetch or fetch_live
    now = time.time()
    with _LIVE_LOCK:
        rows = _LIVE["rows"]
        due = not _LIVE["busy"] and now - _LIVE["tried"] >= REFRESH_SECONDS
        if due:
            _LIVE.update(busy=True, tried=now)
    if due:
        worker = threading.Thread(target=_refresh, args=(fetch,), name="j13-industry", daemon=True)
        worker.start()
        if rows is None and first_wait > 0:
            worker.join(first_wait)
            with _LIVE_LOCK:
                rows = _LIVE["rows"]
    return rows


def snapshot(live_rows: list, size_map: dict | None = None) -> dict | None:
    """지도 칸 줄(크기 큰 순 · 많아야 30) + 시장 전체 오름 · 그대로 · 내림. 크기를 모르는 업종은 칸에서 뺀다(0 으로 채우지 않음)."""
    size_map = sizes() if size_map is None else size_map
    tiles = []
    for row in live_rows or []:
        size = (size_map.get(row.get("no")) or {}).get("mcap")
        if size and size > 0:
            tiles.append({"name": row.get("name") or (size_map.get(row.get("no")) or {}).get("name") or "",
                          "weight": float(size), "change": row.get("change")})
    if not tiles:
        return None
    tiles.sort(key=lambda tile: tile["weight"], reverse=True)
    up = sum(int(row.get("rise") or 0) for row in live_rows)
    flat = sum(int(row.get("steady") or 0) for row in live_rows)
    down = sum(int(row.get("fall") or 0) for row in live_rows)
    return {"rows": tiles[:MAX_TILES], "breadth": {"up": up, "flat": flat, "down": down, "total": up + flat + down}}

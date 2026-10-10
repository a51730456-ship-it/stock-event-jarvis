# -*- coding: utf-8 -*-
"""아침에 앱을 **미리 깨워 둔다** (2026-09-23 상하님 지시).

상하님 — *"오늘도 아침 9시에 상승장 신고가 클릭하니 첫 로딩시 시간이 너무 오래
걸린다. 왜 이거 아직도 해결 못 하냐?"* · *"장이 종료되고 새벽에, 즉 6시에 다
정리해 놓으면 안 되나?"*

**왜 아침마다 느린가.** 온라인 앱은 받아 둔 자료를 **그 판(프로세스) 안에만**
들고 있다. 그런데 아침 목록 저장(picklist_collect.yml, 08:30 KST)이 끝나며
저장소에 글을 올리면 스트림릿이 앱을 **껐다 켠다** — 들고 있던 자료가 전부
사라진다. 2026-09-23 실측(올린 직후 = 껐다 켜진 직후, 게스트) —
    관심종목 첫 화면      글자 4.2초 · 다 그리기 150초
    시장분석             1.6초
    상승장 첫 클릭        목록 4.3초 · 다 그리기 14.5초
    급락 첫 클릭          16.4초
상승장만 느린 것이 아니다. **처음 누른 것**이 느리다 — 그것이 249종목 자료를
받아 오는 몫을 혼자 떠안기 때문이다. 21개 테마가 빠른 까닭은 시장분석 화면을
그리는 길에 이미 그 자료를 받아 두기 때문이다.

**그래서 사람 대신 미리 한 번 눌러 둔다.** 이 파일은 깃허브 컴퓨터가 아침
저장이 끝난 뒤에 돌린다(.github/workflows/warm_morning.yml). 게스트로 들어가
시장분석을 열고 상승장·급락을 한 번씩 눌러 준다. 받아 둔 자료는 **앱 전체가
같이 쓰므로**, 상하님이 9시에 누르시면 이미 다 받아 둔 자료로 열린다.

**아무것도 바꾸지 않는다.** 보기만 한다 — 게스트라 저장·매수 기록에 손댈 수
없고, 값이나 점수도 건드리지 않는다. 실패해도 앱은 그대로다(그날 아침이
예전처럼 느릴 뿐이다).

**자비스12 도 연다 · 코드를 올린 뒤에도 돈다** (2026-10-10 상하님 — "깨우기 자비스12도 열고 올린 뒤에도 돌게
해라"). 상하님이 지금 쓰시는 곳은 자비스12 다. 받아 둔 시세는 두 화면이 같이 쓰지만, 화면마다 따로 담아 두는
것(그 화면 파일을 처음 읽는 일·그 화면만의 담아 두기)이 있어 자비스12 를 **먼저** 열고 자비스3 도 연다.
시장분석으로는 두 화면 다 **밑 막대 「시장분석」** 으로 간다 — 예전에는 자비스3 넘기기의 숨은 단추
「시장분석으로」를 눌렀는데, 2026-10-10 아침 넘기기를 잠깐 뺐던 동안 그 단추가 없어 관심종목만 데웠다.
코드를 올리면 앱이 껐다 켜진다 — 그 뒤 첫 시장분석 24초·첫 테마 39~44초를 사람 대신 이것이 기다린다
(.github/workflows/warm_morning.yml 의 push).
"""
from __future__ import annotations

import sys
import time

BASE = "https://stock-event-jarvis.streamlit.app/~/+"
# 여는 차례 — (이름, 주소, 관심종목 표식, 시장분석 표식). 자비스12 가 먼저다(위 설명).
PAGES = (
    ("자비스12", f"{BASE}/자비스12?guest=1", ".j12b-home", ".j12-market-top"),
    ("자비스3", f"{BASE}/자비스3?guest=1", ".j3b-home", ".j3-market-top"),
)
APP = PAGES[0][1]           # 새 판이 떴는지 볼 때 여는 곳
# 화면이 다 그려지기를 기다리는 한도. 껐다 켜진 직후에는 관심종목 화면이
# 2분 넘게 일한다(위 실측).
SETTLE_LIMIT = 300.0
CLICK_LIMIT = 600.0


def _log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def _settle(page, limit: float = SETTLE_LIMIT) -> float:
    """스트림릿이 '돌고 있음' 표시를 내릴 때까지 기다린다."""
    start = time.time()
    while time.time() - start < limit:
        try:
            busy = page.evaluate(
                "!!document.querySelector('[data-testid=\"stStatusWidget\"]')")
        except Exception:
            busy = False
        if not busy:
            break
        page.wait_for_timeout(300)
    return time.time() - start


def _click(page, text: str) -> bool:
    return bool(page.evaluate(
        "(t) => { const b = [...document.querySelectorAll('button')]"
        ".find(x => (x.innerText || '').includes(t)); if (b) { b.click(); } return !!b; }",
        text))


def _click_key(page, key: str) -> bool:
    """스트림릿 단추를 그 열쇠(key)로 누른다 — 밑 막대 단추는 글자가 투명이라 글자로는 못 찾는다."""
    return bool(page.evaluate(
        "(k) => { const b = [...document.querySelectorAll(`div.st-key-${k} button`)]"
        ".find(x => !x.closest('[data-stale=\"true\"]')); if (b) { b.click(); } return !!b; }",
        key))


def _wait_for(page, js: str, limit: float = CLICK_LIMIT) -> float | None:
    start = time.time()
    while time.time() - start < limit:
        try:
            if page.evaluate(js):
                return time.time() - start
        except Exception:
            pass
        page.wait_for_timeout(300)
    return None


def _wait_for_version(page, short_sha: str, limit: float = 900.0) -> bool:
    """앱 맨 밑 「판 … · 커밋」에 새 커밋이 뜰 때까지 기다린다 (2026-09-24).

    목록 저장이 글을 올린 **바로 뒤에** 이 파일이 돌면, 앱은 아직 옛 판이라 데워 둔 것이
    곧 껐다 켜지며 사라진다. 그래서 새 판이 뜬 것을 본 뒤에 데운다. 30초마다 다시 연다.
    """
    start = time.time()
    while time.time() - start < limit:
        try:
            page.goto(APP, wait_until="domcontentloaded", timeout=180_000)
            if _wait_for(page, "!!document.querySelector('.jarvis-build')", limit=240) is not None:
                stamp = page.evaluate(
                    "(document.querySelector('.jarvis-build') || {}).textContent || ''")
                if short_sha in stamp:
                    _log(f"새 판 확인 — {stamp.strip()}")
                    return True
                _log(f"아직 옛 판 — {stamp.strip()}")
        except Exception as exc:
            _log(f"판 확인 실패 — {exc}")
        page.wait_for_timeout(30_000)
    return False


def _warm_page(page, name: str, url: str, home: str, market: str) -> None:
    """한 화면을 데운다 — 관심종목 → 밑 막대 「시장분석」 → 상승장·급락을 한 번씩 열고 닫는다.

    한 화면이 안 떠도 다음 화면은 데운다(그만두지 않고 넘어간다).
    """
    started = time.time()
    _log(f"{name} 열기")
    page.goto(url, wait_until="domcontentloaded", timeout=180_000)
    if _wait_for(page, f"!!document.querySelector({home!r})") is None:
        _log(f"{name} 관심종목 화면이 안 떴다 — 다음으로")
        return
    _settle(page)
    _log(f"{name} 관심종목 준비됨 {time.time() - started:.0f}초")

    _click_key(page, "j3b_nav_market")
    if _wait_for(page, f"!!document.querySelector({market!r})") is None:
        _log(f"{name} 시장분석이 안 떴다 — 다음으로")
        return
    _settle(page)
    _log(f"{name} 시장분석 준비됨")

    for open_label, close_label in (
        ("상승장 (신고가 눌림매수)", "✕ 상승장 (신고가 눌림매수) 닫기"),
        ("급락 후 반등장 (낙폭종목)", "✕ 급락 후 반등장 (낙폭종목) 닫기"),
    ):
        at = time.time()
        if not _click(page, open_label):
            _log(f"{name} {open_label} 단추를 못 찾았다")
            continue
        shown = _wait_for(
            page,
            "[...document.querySelectorAll('button')].some(b => (b.innerText||'')"
            f".includes({close_label!r}))")
        _settle(page)
        _log(f"{name} {open_label} — 목록 {shown and round(shown, 1)}초 · "
             f"다 그리기 {time.time() - at:.0f}초")
        _click(page, close_label)
        _settle(page)


def main() -> int:
    import os

    from playwright.sync_api import sync_playwright

    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_page(viewport={"width": 420, "height": 900})
        try:
            # 목록 저장·코드 올리기 뒤에 불렸으면(WAIT_FOR_SHA) 새 판이 뜰 때까지 먼저 기다린다.
            short_sha = (os.environ.get("WAIT_FOR_SHA") or "").strip()[:7]
            if short_sha and not _wait_for_version(page, short_sha):
                _log("새 판이 안 떴다 — 그래도 지금 판을 데운다")
            for name, url, home, market in PAGES:
                _warm_page(page, name, url, home, market)
            _log("아침 준비 끝")
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

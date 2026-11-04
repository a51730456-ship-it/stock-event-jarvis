# -*- coding: utf-8 -*-
"""온라인 앱(stock-event-jarvis.streamlit.app) 자비스13 맨 위 「시장 현황」을 손님으로 열어 사진을 찍는다 (2026-11-04 상하님 「다해라」).

클라우드 작업 칸은 온라인 앱 주소로 나가는 것이 막혀 있어(접속 거부 403) 깃허브 컴퓨터가 대신 연다.
**보기만 한다** — 손님(guest=1)이라 저장 · 기록에 손대지 못하고, 값 · 점수도 건드리지 않는다.
폰(412px) · PC(1400px) 두 번 연다. 지도 칸에 테마 칸(.j13-sector-tile)이 뜰 때까지 기다린다 — 처음 들어온 판에는
「받는 중」이고 1분 자동 갱신 때 채워지는 구조라 최대 3분 기다린다. 사진 · 기록은 J13_OUT 폴더에 쓴다.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("J13_ONLINE_BASE") or "https://stock-event-jarvis.streamlit.app/~/+"
URL = f"{BASE}/자비스13?guest=1"
OUT = Path(os.environ.get("J13_OUT") or "j13online")
VIEWS = (("phone", {"width": 412, "height": 915}), ("pc", {"width": 1400, "height": 900}))


def _wait(page, js: str, limit: float) -> float | None:
    start = time.time()
    while time.time() - start < limit:
        try:
            if page.evaluate(js):
                return time.time() - start
        except Exception:
            pass
        page.wait_for_timeout(500)
    return None


def _click(page, key: str) -> bool:
    return bool(page.evaluate("""(key) => {
        const b = document.querySelector(`div[class*="st-key-${key}"] button`);
        if (b) { b.scrollIntoView({block: 'center'}); b.click(); return true; }
        return false;
    }""", key))


def _detail(browser) -> list[str]:
    """급락 표 첫 종목 세부사항을 손님으로 열어 상자 셋 · 화면 깨짐을 잰다(2026-11-05 상하님 「너 사기쳤네」 — 온라인에서 확인).
    손님도 종목 개요 · 상자 셋 · 재무 · 가격 · 차트 · 뉴스는 본다(점수판만 안 봄)."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from j13_screens import AUDIT_JS

    out = []
    page = browser.new_page(viewport={"width": 412, "height": 915}, device_scale_factor=2)
    try:
        page.goto(URL, wait_until="domcontentloaded", timeout=180_000)
        _wait(page, "!!document.querySelector('div[class*=\"st-key-j13_pullback_crash\"] button')", 240)
        stamp = page.evaluate("(document.querySelector('.jarvis-build') || {}).textContent || ''").strip()
        pressed = _click(page, "j13_pullback_crash")
        table = _wait(page, "!!document.querySelector('div[class*=\"st-key-j13rbf_00\"] button')", 300)
        first = page.evaluate("(document.querySelector('div[class*=\"st-key-j13rbf_00\"] button') || {}).innerText || ''").strip()
        opened = _click(page, "j13rbf_00") if table else False
        boxes = _wait(page, "document.querySelectorAll('.j13st-box').length > 0 || document.querySelectorAll('.j13ov').length > 0", 240)
        page.wait_for_timeout(2500)
        try:
            page.evaluate("document.querySelector('.j13ov').scrollIntoView({block: 'start'})")
            page.wait_for_timeout(1000)
        except Exception:
            pass
        page.screenshot(path=str(OUT / "phone_detail_1.jpg"), type="jpeg", quality=80)
        page.evaluate("""() => { const box = document.querySelector('[data-testid="stMain"]') || document.scrollingElement;
            box.scrollBy(0, 820); }""")
        page.wait_for_timeout(900)
        page.screenshot(path=str(OUT / "phone_detail_2.jpg"), type="jpeg", quality=80)
        audit = page.evaluate(AUDIT_JS)
        titles = page.evaluate("[...document.querySelectorAll('.j13st-h')].map(e => e.innerText.trim())")
        out.append(f"[phone 세부사항] 판 {stamp} · 급락 단추 {pressed} · 표 {table and round(table, 1)}초 · 첫 종목 「{first}」 · 열림 {opened} · "
                   f"상자 {audit.get('boxes')}개 · 개요 {audit.get('overview')}개")
        out.append("   상자 제목: " + " | ".join(titles))
        bad = {k: audit.get(k) for k in ("css", "tags", "empty", "del", "code") if audit.get(k)}
        out.append("   화면 검사: " + ("이상 없음" if not bad and not audit.get("wide") else str(bad) + (" · 옆으로 넘침" if audit.get("wide") else "")))
    except Exception as exc:
        out.append(f"[phone 세부사항] 실패 {type(exc).__name__}: {exc}"[:300])
    finally:
        page.close()
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    lines = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name, viewport in VIEWS:
            page = browser.new_page(viewport=viewport, device_scale_factor=2)
            started = time.time()
            page.goto(URL, wait_until="domcontentloaded", timeout=180_000)
            cell = _wait(page, "!!document.querySelector('.j13-sector-map')", 240)
            tiles = _wait(page, "document.querySelectorAll('.j13-sector-tile').length > 0", 200)
            stamp = page.evaluate("(document.querySelector('.jarvis-build') || {}).textContent || ''")
            text = page.evaluate("(document.querySelector('.j13-sector-map') || {}).innerText || ''")
            count = page.evaluate("document.querySelectorAll('.j13-sector-tile').length")
            lines.append(f"[{name}] 칸 보임 {cell and round(cell, 1)}초 · 테마 칸 {count}개 "
                         f"(채워지기까지 {tiles and round(time.time() - started, 1)}초) · 판 {stamp.strip()}")
            lines.append("   " + " | ".join(t.strip() for t in text.splitlines() if t.strip())[:400])
            page.screenshot(path=str(OUT / f"{name}_top.jpg"), type="jpeg", quality=80)
            try:
                page.evaluate("document.querySelector('.j13-sector-map').scrollIntoView({block: 'start'})")
                page.wait_for_timeout(800)
            except Exception:
                pass
            page.screenshot(path=str(OUT / f"{name}_map.jpg"), type="jpeg", quality=80)
            page.close()
        lines.extend(_detail(browser))
        browser.close()
    (OUT / "result.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

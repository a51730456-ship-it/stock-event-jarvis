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
        browser.close()
    (OUT / "result.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

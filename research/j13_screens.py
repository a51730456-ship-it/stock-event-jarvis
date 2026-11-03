"""자비스12 와 자비스13 화면 사진을 나란히 찍는다 (2026-11-03 상하님 「자비스12 형식을 따라라」 · 디자인 옮기기 전 비교).

클라우드 작업 칸은 네이버·야후가 막혀 화면을 못 띄우고, 깃허브 첨부 파일도 못 받는다 — 그래서 깃허브 컴퓨터에서 앱을 띄워
사진을 찍고, 워크플로가 그 사진만 **따로 갈래(j13-screens)** 에 올린다. master 가 아니라 온라인 앱은 안 바뀐다.
사진은 주인으로 로그인해 찍는다(깃허브 실행 안에서만 쓰는 임시 비밀번호). 화면 셋씩(위에서부터 한 화면 높이씩 내려가며).
"""
from __future__ import annotations

import json
import os
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("J13_BASE", "http://localhost:8501")
OUT = Path(os.environ.get("J13_OUT") or "/tmp/j13screens")
CHUNKS = int(os.environ.get("J13_CHUNKS") or 3)
# (화면, 로그인 단추 앞이름, 주소 뒤, 다 그렸다고 볼 표시, 이름표)
VIEWS = (
    ("자비스12", "j12", "?s=home", ".j3b-card", "j12_home"),
    ("자비스12", "j12", "?s=market", "div[class*='st-key-j12_theme_table'], .j3-ndd", "j12_market"),
    ("자비스13", "j13", "", "div[class*='st-key-j13_theme_table']", "j13_market"),
    ("자비스13", "j13", "?s=watch", ".j13w-card, .j13w-empty", "j13_watch"),
)
SIZES = (("pc", 1400, 900), ("phone", 412, 915))


def _quiet(page, seconds: float = 4.0, limit: float = 120.0) -> None:
    start, calm = time.time(), None
    while time.time() - start < limit:
        busy = page.evaluate("""() => {
            const w = document.querySelector('[data-testid="stStatusWidget"]');
            return !!(w && w.innerText && /Running|Stop|실행/.test(w.innerText));
        }""")
        if busy:
            calm = None
        elif calm is None:
            calm = time.time()
        elif time.time() - calm >= seconds:
            return
        page.wait_for_timeout(500)


def shoot(browser, password: str, view, size) -> dict:
    name, p, tail, ready, tag = view
    label, width, height = size
    page = browser.new_page(viewport={"width": width, "height": height})
    out = {"view": tag, "size": label, "shots": []}
    started = time.time()
    try:
        page.goto(f"{BASE}/{name}{tail}", timeout=180_000)
        page.wait_for_selector('input[type="password"]', timeout=180_000)
        page.locator('input[type="password"]').fill(password)
        page.locator(f'div[class*="st-key-{p}_login_submit"] button').click()
        try:
            page.wait_for_selector(ready, timeout=300_000)
        except Exception as exc:
            out["ready_error"] = f"{type(exc).__name__}"[:80]
        _quiet(page)
        out["seconds"] = round(time.time() - started, 1)
        # 스트림릿은 안쪽 칸이 굴러간다 — 그 칸을 한 화면씩 내리며 찍는다
        for index in range(CHUNKS):
            page.evaluate("""(y) => {
                const box = document.querySelector('[data-testid="stMain"]') || document.scrollingElement;
                box.scrollTo(0, y); window.scrollTo(0, y);
            }""", index * (height - 60))
            page.wait_for_timeout(900)
            path = OUT / f"{tag}_{label}_{index + 1}.jpg"
            page.screenshot(path=str(path), type="jpeg", quality=62)
            out["shots"].append(path.name)
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"[:300]
    finally:
        page.close()
    return out


def main() -> int:
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    password = tomllib.loads((ROOT / ".streamlit" / "secrets.toml").read_text(encoding="utf-8"))["APP_PASSWORD"]
    runs = []
    with sync_playwright() as play:
        browser = play.chromium.launch()
        for view in VIEWS:
            for size in SIZES:
                run = shoot(browser, password, view, size)
                runs.append(run)
                print(json.dumps(run, ensure_ascii=False), flush=True)
        browser.close()
    (OUT / "screens.json").write_text(json.dumps(runs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n끝 · 사진 {sum(len(run['shots']) for run in runs)}장", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

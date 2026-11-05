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
    ("자비스13", "j13", "", "div[class*='st-key-btn_j13_theme_rank_open'], div[class*='st-key-j13_theme_table']", "j13_market"),
    ("자비스13", "j13", "?s=watch", ".j13h-card, .j13h-empty", "j13_watch"),
    # 2026-11-04 순위표를 연 판도 나란히(상하님 「강한 테마 20개는 미국테마 디자인을 따라 해라」) — 단추를 눌러 연 뒤 찍는다
    ("자비스12", "j12", "?s=market", "div[class*='st-key-btn_j12_theme_rank_open']", "j12_rank", "btn_j12_theme_rank_open"),
    ("자비스13", "j13", "", "div[class*='st-key-btn_j13_theme_rank_open']", "j13_rank", "btn_j13_theme_rank_open"),
    # 2026-11-04 상하님 「파트별 성적표 미국테마대로」 — 성적표를 연 판도 나란히
    ("자비스12", "j12", "?s=market", "div[class*='st-key-picklist_scorecard_US']", "j12_score", "picklist_scorecard_US"),
    ("자비스13", "j13", "", "div[class*='st-key-btn_j13sc_open']", "j13_score", "btn_j13sc_open"),
)
# 2026-11-05 상하님 「너 사기쳤네」 · 「다른 부분도 검토하고 똑똑하게」 — 세부사항까지 실제 자료로 찍는다(폰만 · 시간 아끼기).
# (화면, 로그인 앞이름, 주소 뒤, 다 그렸다고 볼 표시, 이름표, [(누를 열쇠, 기다릴 표시, 굴려 갈 표시)…])
DEEP_VIEWS = (
    # 관심종목 세부사항은 2026-11-05 부터 판 위를 덮는 창(자비스12 처럼) — 창 안 상자를 기다린다
    ("자비스13", "j13", "?s=watch", ".j13h-card, .j13h-empty", "j13_watchdetail",
     [("j13h_wdgo_005930", "div.st-key-j13w_pane .j13st-box", "div.st-key-j13w_pane .j13ov")]),
    # 날짜별 목록 → 급락 줄 첫 종목 이름(2026-11-05 상하님 「1」 — 전에는 종목명이 그냥 글자였다)
    ("자비스13", "j13", "", "div[class*='st-key-btn_j13_picklist_archive_open_KR']", "j13_picklist",
     [("btn_j13_picklist_archive_open_KR", "div[class*='st-key-plpick_KR_']", ".pl-kind"),
      ("plpick_KR_crash_00", ".j13st-box", ".j13ov")]),
    ("자비스13", "j13", "", "div[class*='st-key-j13_pullback_crash']", "j13_crash",
     # 표가 다 그려진 판에만 생기는 맨 아래 「닫기」 단추를 기다린다(위쪽에 원래 있는 알림 상자에 걸리지 않게)
     [("j13_pullback_crash", "div[class*='st-key-close_j13_pullback_open']",
       "div[class*='st-key-j13_rulebook_table']"),
      ("j13rbf_00", ".j13ov, .j13st-box", ".j13ov")]),
)
# 화면 안 깨짐 검사 — 꾸밈 글이 글자로 샘 · 취소선 · 코드 상자 · 글자로 보이는 태그 · 빈 값 글자 · 옆으로 넘침 · 상자 셋 수
AUDIT_JS = """() => {
  const root = document.querySelector('[data-testid="stMain"]') || document.body;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const css = [], tags = [], empty = [];
  let node;
  while ((node = walker.nextNode())) {
    const el = node.parentElement;
    if (!el || ['STYLE', 'SCRIPT', 'NOSCRIPT'].includes(el.tagName) || !el.getClientRects().length) continue;
    const t = node.textContent.trim();
    if (!t) continue;
    if (/[.#]?[A-Za-z_][\\w-]*\\s*\\{[^{}]*:[^{}]*\\}|!important/.test(t)) css.push(t.slice(0, 90));
    if (/<\\/?(div|span|style|b|br|table|td|tr|details|summary|a|p|u|small)\\b[^>]*>/i.test(t)) tags.push(t.slice(0, 90));
    if (/(^|[^A-Za-z])(None|NaN|nan|undefined|null)([^A-Za-z]|$)/.test(t)) empty.push(t.slice(0, 90));
  }
  const vis = (e) => e.getClientRects().length > 0;
  const del = [...root.querySelectorAll('del, s')].filter(vis).map(e => e.textContent.slice(0, 60));
  const code = [...root.querySelectorAll('pre, code')].filter(vis).map(e => e.textContent.slice(0, 60));
  const wide = document.documentElement.scrollWidth > window.innerWidth + 2;
  return {css: css.slice(0, 8), tags: tags.slice(0, 8), empty: empty.slice(0, 8), del: del.slice(0, 8), code: code.slice(0, 8),
          wide: wide, width: document.documentElement.scrollWidth,
          boxes: root.querySelectorAll('.j13st-box').length, overview: root.querySelectorAll('.j13ov').length};
}"""
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
    name, p, tail, ready, tag = view[:5]
    press = view[5] if len(view) > 5 else ""
    pressed_chunks = view[6] if len(view) > 6 else 3
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
        if press:
            button = page.locator(f'div[class*="st-key-{press}"] button').first
            button.scroll_into_view_if_needed()
            button.click()
            page.wait_for_timeout(2500)
            _quiet(page)
            # 연 자리(단추)부터 찍는다 — 안쪽 칸을 그 단추 위치로 굴린다
            page.evaluate("""(key) => {
                const el = document.querySelector(`div[class*="st-key-${key}"]`);
                const box = document.querySelector('[data-testid="stMain"]') || document.scrollingElement;
                if (el && box) { box.scrollTo(0, el.getBoundingClientRect().top + box.scrollTop - 80); }
            }""", press)
            page.wait_for_timeout(900)
        for key, wait_for, scroll_to in (view[7] if len(view) > 7 else []):
            # 숨은 단추(관심종목 「🔎 세부사항」)도 누를 수 있게 브라우저 안에서 누른다
            page.evaluate("""(key) => {
                const b = document.querySelector(`div[class*="st-key-${key}"] button`);
                if (b) { b.click(); }
            }""", key)
            try:
                page.wait_for_selector(wait_for, timeout=300_000, state="attached")
            except Exception as exc:
                out.setdefault("step_errors", []).append(f"{key}: {type(exc).__name__}"[:80])
            page.wait_for_timeout(1500)
            _quiet(page)
            page.evaluate("""(sel) => {
                const el = document.querySelector(sel);
                const box = document.querySelector('[data-testid="stMain"]') || document.scrollingElement;
                if (el && box) { box.scrollTo(0, el.getBoundingClientRect().top + box.scrollTop - 70); }
            }""", scroll_to)
            page.wait_for_timeout(900)
        try:
            out["audit"] = page.evaluate(AUDIT_JS)
        except Exception as exc:
            out["audit_error"] = f"{type(exc).__name__}"[:80]
        out["seconds"] = round(time.time() - started, 1)
        # 스트림릿은 안쪽 칸이 굴러간다 — 그 칸을 한 화면씩 내리며 찍는다
        start_y = page.evaluate("""() => {
            const box = document.querySelector('[data-testid="stMain"]') || document.scrollingElement;
            return box.scrollTop || 0;
        }""") if (press or len(view) > 7) else 0
        for index in range(CHUNKS if not press else pressed_chunks):
            page.evaluate("""(y) => {
                const box = document.querySelector('[data-testid="stMain"]') || document.scrollingElement;
                box.scrollTo(0, y); window.scrollTo(0, y);
            }""", start_y + index * (height - 60))
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
        for name, p, tail, ready, tag, steps in DEEP_VIEWS:
            run = shoot(browser, password, (name, p, tail, ready, tag, "", 4, steps), SIZES[1])
            runs.append(run)
            print(json.dumps(run, ensure_ascii=False), flush=True)
        browser.close()
    (OUT / "screens.json").write_text(json.dumps(runs, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = []
    for run in runs:
        audit = run.get("audit") or {}
        bad = {k: audit.get(k) for k in ("css", "tags", "empty", "del", "code") if audit.get(k)}
        if audit.get("wide"):
            bad["wide"] = audit.get("width")
        head = f"{run['view']} · {run['size']} · 상자 {audit.get('boxes', '-')} · 개요 {audit.get('overview', '-')}"
        lines.append(head + (" · 이상 없음" if not bad else " · " + json.dumps(bad, ensure_ascii=False)))
        for key in ("error", "ready_error", "step_errors", "audit_error"):
            if run.get(key):
                lines.append(f"    {key}: {run[key]}")
    (OUT / "audit.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    print(f"\n끝 · 사진 {sum(len(run['shots']) for run in runs)}장", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

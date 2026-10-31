"""자비스12 관심종목 「넣은 날부터 성적」을 실제 미국 시세로 확인한다 (2026-10-31 상하님 「자비스12에도 넣어라」 · 「만들어라」).

클라우드 작업 칸은 야후가 막혀 시세가 안 들어온다 — 깃허브 컴퓨터에서 앱을 띄워 본다.
`seed` — 앱을 띄우기 **전에** 깃허브 컴퓨터의 빈 기록 DB 에 관심종목 셋을 지난 날짜로 넣는다
(깃허브 실행 안에서만 생기는 임시 DB 다 — 상하님 DB 가 아니다. 저장소에 안 올린다).
그 뒤 그냥 부르면 PC(1400px)·폰(412px)으로 관심종목 화면을 열어 표·오류·옆 넘침을 본다.
"""
from __future__ import annotations

import json
import os
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASE = os.environ.get("J12_BASE", "http://localhost:8501")
OUT = Path(os.environ.get("J12_OUT") or "/tmp/j12shots")
# (무리, 자리, 티커, 이름, 넣은 날) — 셋째는 6개월보다 앞이라 「셈 안 함」이 나와야 한다.
SEED = (("selected", 1, "NVDA", "엔비디아", "2026-10-20T12:00:00"),
        ("extra", 1, "PLTR", "팔란티어", "2026-09-01T12:00:00"),
        ("extra", 2, "AAPL", "애플", "2026-01-05T12:00:00"))


def seed() -> int:
    import jarvis3_briefing_store as store
    store.ensure_tables()
    conn = store._connection()
    try:
        for group, position, ticker, name, when in SEED:
            conn.execute("INSERT INTO jarvis3_briefing_stocks (group_name,position,ticker,stock_name,created_at,updated_at)"
                         " VALUES (?,?,?,?,?,?)", (group, position, ticker, name, when, when))
        conn.commit()
    finally:
        conn.close()
    print("임시 DB 에 넣음:", ", ".join(f"{t} {w[:10]}" for _g, _p, t, _n, w in SEED), flush=True)
    return 0


def _problems(page) -> dict:
    return page.evaluate("""() => ({
        exceptions: [...document.querySelectorAll('[data-testid="stException"]')].map(e => e.innerText.slice(0, 600)),
        overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth,
    })""")


def visit(browser, password: str, width: int) -> dict:
    page = browser.new_page(viewport={"width": width, "height": 900})
    started = time.time()
    out = {"width": width}
    try:
        page.goto(f"{BASE}/자비스12?s=home", timeout=180_000)
        page.wait_for_selector('input[type="password"]', timeout=180_000)
        page.locator('input[type="password"]').fill(password)
        page.locator('div[class*="st-key-j12_login_submit"] button').click()
        page.wait_for_selector(".j12ws-table", timeout=240_000)
        page.wait_for_timeout(4000)
        out["seconds"] = round(time.time() - started, 1)
        out["rows"] = page.evaluate("""() => [...document.querySelectorAll('.j12ws-table tbody tr')]
            .map(r => r.innerText.replace(/\\s+/g, ' ').trim())""")
        out["cards"] = page.evaluate("() => document.querySelectorAll('.j3b-card').length")
        out["table_after_cards"] = page.evaluate("""() => {
            const cards = [...document.querySelectorAll('.j3b-card')];
            const table = document.querySelector('.j12ws-table');
            return !!(cards.length && table && (cards[cards.length - 1].compareDocumentPosition(table) & 4));
        }""")
        out["problems"] = _problems(page)
        page.locator(".j12ws-box").scroll_into_view_if_needed()
        page.screenshot(path=str(OUT / f"j12_watch_{width}.png"), full_page=width > 600)
        # 「오늘 움직인 까닭」(②) — 누르기 전에는 안 받고, 누르면 그 장 시간대 제목이나 「움직인 종목이 없습니다」가 나온다.
        button = page.locator('div[class*="st-key-btn_j12_movers_watch"] button')
        out["movers_button"] = button.count() == 1
        if out["movers_button"]:
            button.click()
            page.wait_for_function("() => /원인 확인은 아닙니다|움직인 종목이 없습니다/.test(document.body.innerText)",
                                   timeout=60_000)
            page.wait_for_timeout(1500)
            out["movers"] = page.evaluate("""() => {
                const t = document.body.innerText;
                const i = t.indexOf('움직인 까닭 닫기');   // 열면 단추 글이 「✕ 움직인 까닭 닫기」로 바뀐다 — 그 밑이 까닭 줄
                return i < 0 ? '' : t.slice(i, i + 700).replace(/\\s+/g, ' ');
            }""")
            out["movers_problems"] = _problems(page)
            page.screenshot(path=str(OUT / f"j12_movers_{width}.png"), full_page=width > 600)
        # ③ 시장분석 「🧮 분산일」 — 밑 막대 「시장분석」으로 가서 나스닥 막대 밑 줄을 본다.
        page.locator('div[class*="st-key-j3b_nav_market"] button').click()
        page.wait_for_function("() => document.body.innerText.includes('🧮 분산일')", timeout=180_000)
        page.wait_for_timeout(1500)
        out["dist"] = page.evaluate("""() => {
            const t = document.body.innerText; const i = t.indexOf('🧮 분산일');
            return i < 0 ? '' : t.slice(i, i + 260).replace(/\\s+/g, ' ');
        }""")
        out["dist_problems"] = _problems(page)
        page.screenshot(path=str(OUT / f"j12_market_{width}.png"), full_page=width > 600)
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"[:300]
        try:
            out["problems"] = _problems(page)
            page.screenshot(path=str(OUT / f"j12_watch_{width}_error.png"))
        except Exception:
            pass
    finally:
        page.close()
    return out


def main() -> int:
    if sys.argv[1:] == ["seed"]:
        return seed()
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    password = tomllib.loads((ROOT / ".streamlit" / "secrets.toml").read_text(encoding="utf-8"))["APP_PASSWORD"]
    with sync_playwright() as play:
        browser = play.chromium.launch()
        runs = [visit(browser, password, width) for width in (1400, 412)]
        browser.close()
    for run in runs:
        print(json.dumps(run, ensure_ascii=False), flush=True)
    rows = runs[0].get("rows") or []
    nvda = next((r for r in rows if r.startswith("NVDA")), "")
    checks = {
        "표가 PC·폰 둘 다 보임": all(run.get("rows") for run in runs),
        "카드가 먼저, 표는 그 밑": all(run.get("table_after_cards") for run in runs),
        "넣은 종목 셋이 다 표에": all(any(r.startswith(t) for r in rows) for t in ("NVDA", "PLTR", "AAPL")),
        "6개월보다 앞(AAPL)은 셈 안 함": any(r.startswith("AAPL") and "셈 안 함" in r for r in rows),
        "NVDA 는 숫자로 셈": "%p" in nvda and "—" not in nvda,
        "오류 상자 0": all(not (run.get("problems") or {}).get("exceptions") for run in runs),
        "폰 옆 넘침 0": all((run.get("problems") or {}).get("overflow", 1) <= 0 for run in runs if run["width"] < 600),
        "② 움직인 까닭 — 눌러서 열림": all(run.get("movers_button") and run.get("movers") for run in runs),
        "③ 분산일 줄 보임(숫자)": all("일" in (run.get("dist") or "") and "경고로 쓰지 않고" in (run.get("dist") or "")
                                    for run in runs),
        "③ 시장분석 오류 0 · 폰 넘침 0": all(not (run.get("dist_problems") or {}).get("exceptions")
                                       and ((run.get("dist_problems") or {}).get("overflow", 1) <= 0 or run["width"] >= 600)
                                       for run in runs),
        "② 연 뒤 오류 0 · 폰 넘침 0": all(not (run.get("movers_problems") or {}).get("exceptions")
                                     and ((run.get("movers_problems") or {}).get("overflow", 1) <= 0 or run["width"] >= 600)
                                     for run in runs),
    }
    print("\n### 자비스12 관심종목 「넣은 날부터 성적」 · 「오늘 움직인 까닭」", flush=True)
    for name, ok in checks.items():
        print(f"  {'됨' if ok else '안 됨'} · {name}", flush=True)
    print(f"\n끝 · {'모두 됨' if all(checks.values()) else '안 된 것 있음'}", flush=True)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())

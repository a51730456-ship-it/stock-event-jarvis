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
        # 기능 ⑥ 해마다 연중 최대 하락(누를 때만 · 2026-11-13)
        years_btn = page.locator('div[class*="st-key-btn_j12_years_open"] button').first
        if years_btn.count():
            years_btn.scroll_into_view_if_needed()
            years_btn.click()
            try:
                page.wait_for_function("() => /해마다 평균/.test(document.body.innerText) || /그리지 못했습니다/.test(document.body.innerText)",
                                       timeout=120_000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            out["years"] = page.evaluate("""() => { const b = [...document.querySelectorAll('.j12hs-box')].pop();
                return b ? {text: b.innerText.replace(/\\s+/g, ' ').slice(0, 260), bars: b.querySelectorAll('rect').length} : null; }""")
            out["years_problems"] = _problems(page)
            page.screenshot(path=str(OUT / f"j12_years_{width}.png"), full_page=width > 600)
        page.screenshot(path=str(OUT / f"j12_market_{width}.png"), full_page=width > 600)
        # ④ 급락 후 반등장 — 「주의 · 2배」·「⚠ 수상하게 빠짐」 딱지(2026-11-12 규칙 고침 ① · jarvis12_rules).
        # 단추는 테마 순위가 다 실린 뒤에 그려진다 — 단추가 붙을 때까지 기다린다. 표는 <table> 이 아니라 칸 묶음
        # (.st-key-j12_rulebook_table · 접힌 나머지는 .st-key-j12_rulebook_rest)이다.
        crash_button = page.locator('div[class*="st-key-j12_pullback_crash"] button').first
        crash_button.wait_for(state="attached", timeout=240_000)
        crash_button.scroll_into_view_if_needed()
        crash_button.click()
        page.wait_for_function(
            "() => { const b = document.querySelector('[class*=\"st-key-j12_rulebook_table\"]');"
            " return b && b.textContent.length > 200; }", timeout=240_000)
        page.wait_for_timeout(2500)
        out["crash"] = page.evaluate("""() => {
            // 접힌 나머지 줄도 세려고 innerText 가 아니라 textContent 로 읽는다.
            const text = [...document.querySelectorAll(
                '[class*="st-key-j12_rulebook_table"], [class*="st-key-j12_rulebook_rest"]')]
                .map(b => b.textContent).join(' ');
            return {rows: (text.match(/-\\d+~-\\d+%/g) || []).length,
                    warn: (text.match(/수상하게 빠짐/g) || []).length,
                    caution: (text.match(/주의 · 2배/g) || []).length,
                    guide: /2배를 넘으면/.test(document.body.innerText)};
        }""")
        # 기능 ④ 목록 쏠림 덩이(2026-11-13)
        out["crash_risk"] = page.evaluate("""() => [...document.querySelectorAll('.j12rk-box')]
            .map(b => b.innerText.replace(/\\s+/g, ' ').slice(0, 220))""")
        out["crash_problems"] = _problems(page)
        # ② 「🛡 자주 이기는 쪽」 — 눌러서 표가 다시 그려지는지 · 줄 수(2026-11-12 규칙 고침 ②).
        steady = page.get_by_text("🛡 자주 이기는 쪽", exact=False).first
        if steady.count():
            steady.click()
            page.wait_for_function("() => /경고 없는 종목 중 평소 덜 움직이는 순/.test(document.body.innerText)", timeout=120_000)
            page.wait_for_timeout(2500)
            out["steady_rows"] = page.evaluate("""() => [...document.querySelectorAll(
                '[class*="st-key-j12_rulebook_table"], [class*="st-key-j12_rulebook_rest"]')]
                .map(b => b.textContent).join(' ').match(/-\\d+~-\\d+%/g)?.length || 0""")
            out["steady_problems"] = _problems(page)
        # 기능 ② 종목 성적표 — 표의 첫 종목을 눌러 세부사항을 연다(세부사항은 눌러야 열림 · 2026-11-13 확인 도구 바로잡음)
        first_stock = page.locator('div[class*="st-key-j12rbf_00"] button').first
        if first_stock.count():
            first_stock.scroll_into_view_if_needed()
            first_stock.click()
            try:
                page.wait_for_selector(".j12gr-box", timeout=180_000)
                page.wait_for_timeout(1500)
            except Exception as exc:
                out["grades_error"] = f"{type(exc).__name__}: {exc}"[:200]
        out["grades"] = page.evaluate("""() => [...document.querySelectorAll('.j12gr-box')]
            .map(b => b.innerText.replace(/\\s+/g, ' ').slice(0, 160))""")
        out["implied"] = page.evaluate("""() => [...document.querySelectorAll('.j12im-box')]
            .map(b => b.innerText.replace(/\\s+/g, ' ').slice(0, 160))""")
        out["detail_problems"] = _problems(page)
        page.screenshot(path=str(OUT / f"j12_detail_{width}.png"), full_page=width > 600)
        # 기능 ③ 내 계획 한 장 — 첫 종목 세부사항에서 열어 값을 적고 저장(이 실행의 임시 DB 에만)
        plan_btn = page.locator('div[class*="st-key-btn_j12_plan_open_"] button').first
        if plan_btn.count():
            plan_btn.scroll_into_view_if_needed()
            plan_btn.click()
            try:
                page.locator('div[class*="st-key-j12_plan_buy_"] input').first.wait_for(timeout=60_000)
                for name, value in (("buy", "100"), ("stop", "92"), ("target", "120"), ("qty", "10")):
                    box = page.locator(f'div[class*="st-key-j12_plan_{name}_"] input').first
                    box.fill(value)
                    box.press("Tab")
                page.get_by_role("button", name="계획 저장").first.click()
                page.wait_for_selector(".j12pl-box", timeout=60_000)
                page.wait_for_timeout(1200)
                out["plan"] = page.evaluate("""() => document.querySelector('.j12pl-box').innerText.replace(/\\s+/g, ' ').slice(0, 260)""")
            except Exception as exc:
                out["plan_error"] = f"{type(exc).__name__}: {exc}"[:200]
            out["plan_problems"] = _problems(page)
            page.screenshot(path=str(OUT / f"j12_plan_{width}.png"), full_page=width > 600)
        # 기능 ⑤ 지난 급락 기록표(누를 때만 · 2026-11-13)
        hist_btn = page.locator('div[class*="st-key-btn_j12_crash_hist_open"] button').first
        if hist_btn.count():
            hist_btn.scroll_into_view_if_needed()
            hist_btn.click()
            try:
                page.wait_for_function("() => document.querySelector('.j12hs-tbl') || /그리지 못했습니다/.test(document.body.innerText)",
                                       timeout=120_000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            out["crash_hist"] = page.evaluate("""() => { const b = document.querySelector('.j12hs-tbl');
                const box = b && b.closest('.j12hs-box');
                return box ? {text: box.innerText.replace(/\\s+/g, ' ').slice(0, 400), rows: box.querySelectorAll('tr').length} : null; }""")
            out["crash_hist_problems"] = _problems(page)
            page.screenshot(path=str(OUT / f"j12_crash_hist_{width}.png"), full_page=width > 600)
        page.locator('[class*="st-key-j12_rulebook_table"]').first.scroll_into_view_if_needed()
        page.screenshot(path=str(OUT / f"j12_crash_{width}.png"), full_page=width > 600)
        # ⑤ 상승장 — 시장 문이 「200일선 위/아래」로 말하는지 · 눌림 「주의」 딱지 수(2026-11-12 규칙 고침 ④ · ⑤).
        up_button = page.locator('div[class*="st-key-j12_pullback_breakout"] button').first
        up_button.scroll_into_view_if_needed()
        up_button.click()
        page.wait_for_function("() => /나스닥 지수 — /.test(document.body.innerText)", timeout=240_000)
        page.wait_for_timeout(2500)
        out["swing"] = page.evaluate("""() => {
            const t = document.body.innerText; const i = t.indexOf('나스닥 지수 — ');
            return {line: i < 0 ? '' : t.slice(i, i + 160).replace(/\\s+/g, ' '),
                    grades: (t.match(/[SABCD]등급/g) || []).length,
                    caution: [...document.querySelectorAll('span[title^="8% 넘게"]')].length};
        }""")
        out["swing_risk"] = page.evaluate("""() => [...document.querySelectorAll('.j12rk-box')]
            .map(b => b.innerText.replace(/\\s+/g, ' ').slice(0, 220))""")
        out["swing_problems"] = _problems(page)
        page.screenshot(path=str(OUT / f"j12_swing_{width}.png"), full_page=width > 600)
        # 「매수심사결과 높은 순위 9」 — 손님에게는 그리지 않아 온라인 손님 확인에서는 못 본다(2026-11-13). 로그인한 이 판에서 본다.
        top9 = page.locator('div[class*="st-key-j12_top7_find"] button').first
        top9.wait_for(state="attached", timeout=300_000)       # 22개 테마를 연 뒤 판 전체가 다시 그려질 때까지
        top9.scroll_into_view_if_needed()
        top9.click()
        page.wait_for_function(
            "() => { const b = document.querySelector('[class*=\"st-key-j12_top7_table\"]');"
            " return b && b.textContent.length > 200; }", timeout=300_000)
        page.wait_for_timeout(2500)
        out["top9_text"] = page.evaluate("""() => document.querySelector('[class*="st-key-j12_top7_table"]')
            .innerText.replace(/\\s+/g, ' ').slice(0, 1500)""")
        out["top9_notes"] = page.evaluate("""() => { const t = document.body.innerText;
            const i = t.indexOf('매수심사결과 높은 순위 9'); return i < 0 ? '' : t.slice(i, i + 500).replace(/\\s+/g, ' '); }""")
        page.locator('[class*="st-key-j12_top7_table"]').first.scroll_into_view_if_needed()
        page.screenshot(path=str(OUT / f"j12_top9_{width}.png"), full_page=width > 600)
        out["top9_problems"] = _problems(page)
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


def online() -> int:
    """온라인 앱을 손님(guest=1)으로 열어 급락(② 두 목록 · ① 딱지)과 상승장(④ 200일선 줄)만 본다 — 보기만 한다(2026-11-12).

    클라우드 작업 칸은 온라인 주소로 나가는 것이 막혀 있어 깃허브 컴퓨터가 대신 연다. 저장 · 기록에 손대지 않는다.
    """
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    base = os.environ.get("J12_ONLINE_BASE") or "https://stock-event-jarvis.streamlit.app/~/+"
    runs = []
    with sync_playwright() as play:
        browser = play.chromium.launch()
        for width in (1400, 412):
            page = browser.new_page(viewport={"width": width, "height": 900})
            out = {"width": width}
            try:
                page.goto(f"{base}/자비스12?guest=1", timeout=240_000)
                button = page.locator('div[class*="st-key-j12_pullback_crash"] button').first
                button.wait_for(state="attached", timeout=300_000)
                button.scroll_into_view_if_needed()
                button.click()
                page.wait_for_function(
                    "() => { const b = document.querySelector('[class*=\"st-key-j12_rulebook_table\"]');"
                    " return b && b.textContent.length > 200; }", timeout=240_000)
                page.wait_for_timeout(2500)
                out["crash"] = page.evaluate("""() => {
                    const text = [...document.querySelectorAll(
                        '[class*="st-key-j12_rulebook_table"], [class*="st-key-j12_rulebook_rest"]')]
                        .map(b => b.textContent).join(' ');
                    return {rows: (text.match(/-\\d+~-\\d+%/g) || []).length,
                            warn: (text.match(/수상하게 빠짐/g) || []).length,
                            caution: (text.match(/주의 · 2배/g) || []).length,
                            two: /자주 이기는 쪽/.test(document.body.innerText)};
                }""")
                page.screenshot(path=str(OUT / f"online_crash_{width}.png"), full_page=width > 600)
                out["crash_text"] = page.evaluate("""() => [...document.querySelectorAll('[class*="st-key-j12_rulebook_table"]')]
                    .map(b => b.innerText).join(' ').replace(/\\s+/g, ' ').slice(0, 900)""")
                steady = page.get_by_text("🛡 자주 이기는 쪽", exact=False).first
                if steady.count():
                    steady.click()
                    page.wait_for_function("() => /경고 없는 종목 중 평소 덜 움직이는 순/.test(document.body.innerText)",
                                           timeout=120_000)
                    page.wait_for_timeout(2000)
                    out["steady_ok"] = True
                # 2026-11-13 기능 여섯 — 온라인에서도 보이나(손님 화면 · ③ 내 계획은 손님에게 안 보임)
                out["crash_risk"] = page.evaluate("""() => [...document.querySelectorAll('.j12rk-box')]
                    .map(b => b.innerText.replace(/\\s+/g, ' ').slice(0, 160))""")
                try:
                    hist_btn = page.locator('div[class*="st-key-btn_j12_crash_hist_open"] button').first
                    hist_btn.scroll_into_view_if_needed()
                    hist_btn.click()
                    page.wait_for_selector(".j12hs-tbl", timeout=180_000)
                    page.wait_for_timeout(1500)
                    out["crash_hist"] = page.evaluate("""() => document.querySelector('.j12hs-tbl').closest('.j12hs-box')
                        .innerText.replace(/\\s+/g, ' ').slice(0, 220)""")
                except Exception as exc:
                    out["crash_hist_error"] = f"{type(exc).__name__}: {exc}"[:160]
                try:
                    first_stock = page.locator('div[class*="st-key-j12rbf_00"] button').first
                    first_stock.scroll_into_view_if_needed()
                    first_stock.click()
                    page.wait_for_selector(".j12gr-box", timeout=180_000)
                    page.wait_for_timeout(1500)
                    out["grades"] = page.evaluate("""() => document.querySelector('.j12gr-box').innerText.replace(/\\s+/g, ' ').slice(0, 160)""")
                    out["plan_hidden"] = page.locator('div[class*="st-key-btn_j12_plan_open_"]').count() == 0
                    page.screenshot(path=str(OUT / f"online_detail_{width}.png"), full_page=width > 600)
                except Exception as exc:
                    out["grades_error"] = f"{type(exc).__name__}: {exc}"[:160]
                up = page.locator('div[class*="st-key-j12_pullback_breakout"] button').first
                up.scroll_into_view_if_needed()
                up.click()
                page.wait_for_function("() => /나스닥 지수 — /.test(document.body.innerText)", timeout=240_000)
                page.wait_for_timeout(2000)
                out["swing_line"] = page.evaluate("""() => { const t = document.body.innerText;
                    const i = t.indexOf('나스닥 지수 — '); return i < 0 ? '' : t.slice(i, i + 140).replace(/\\s+/g, ' '); }""")
                page.screenshot(path=str(OUT / f"online_swing_{width}.png"), full_page=width > 600)
                out["swing_rows"] = page.evaluate("""() => document.body.innerText.match(/[SABCD]등급/g)?.length || 0""")
                out["swing_risk"] = page.evaluate("""() => [...document.querySelectorAll('.j12rk-box')]
                    .map(b => b.innerText.replace(/\\s+/g, ' ').slice(0, 160))""")
                out["swing_text"] = page.evaluate("""() => { const t = document.body.innerText;
                    const i = t.indexOf('분기 실적'); return i < 0 ? '' : t.slice(i, i + 700).replace(/\\s+/g, ' '); }""")
                # 「22개 테마」 · 「매수심사결과 높은 순위 9」(2026-11-13 상하님 「4개 파트 다 봤냐?」) — 열어서 표가 뜨는지 · 무엇이 실렸는지.
                theme = page.locator('div[class*="st-key-btn_j12_theme_rank_open"] button').first
                theme.scroll_into_view_if_needed()
                theme.click()
                page.wait_for_function(
                    "() => { const b = document.querySelector('[class*=\"st-key-j12_theme_table\"]');"
                    " return b && b.textContent.length > 200; }", timeout=240_000)
                page.wait_for_timeout(2000)
                out["theme_text"] = page.evaluate("""() => document.querySelector('[class*="st-key-j12_theme_table"]')
                    .innerText.replace(/\\s+/g, ' ').slice(0, 500)""")
                page.screenshot(path=str(OUT / f"online_theme_{width}.png"), full_page=width > 600)
                out["version"] = page.evaluate("""() => (document.body.innerText.match(/판 \\d{4}-\\d\\d-\\d\\d \\d\\d:\\d\\d · [0-9a-f]{6,}/) || [''])[0]""")
                try:
                    page.locator('div[class*="st-key-j3b_nav_market"] button').first.click()
                    # 시장분석이 다 그려진 뒤에 누른다 — 그리는 도중에 누르면 눌림이 사라진다(2026-11-13 온라인 확인에서 겪음)
                    page.wait_for_function("() => document.body.innerText.includes('🧮 분산일')", timeout=180_000)
                    page.wait_for_timeout(2500)
                    years_btn = page.locator('div[class*="st-key-btn_j12_years_open"] button').first
                    years_btn.scroll_into_view_if_needed()
                    years_btn.click()
                    try:
                        page.wait_for_function("() => /연중 최대 하락 닫기/.test(document.body.innerText)", timeout=20_000)
                    except Exception:
                        out["years_reclick"] = True              # 눌림이 안 먹었으면 한 번만 다시 누른다
                        years_btn.click()
                    page.wait_for_function("() => /해마다 평균/.test(document.body.innerText)", timeout=180_000)
                    page.wait_for_timeout(1500)
                    out["years"] = page.evaluate("""() => { const b = [...document.querySelectorAll('.j12hs-box')].pop();
                        return b ? b.innerText.replace(/\\s+/g, ' ').slice(0, 160) : ''; }""")
                    page.screenshot(path=str(OUT / f"online_years_{width}.png"), full_page=width > 600)
                except Exception as exc:
                    out["years_error"] = f"{type(exc).__name__}: {exc}"[:160]
                    # 무엇이 보였나 남긴다 — 닫기 단추로 바뀌었는지(눌림이 먹었는지) · 그 근처 글 · 사진
                    out["years_seen"] = page.evaluate("""() => { const t = document.body.innerText;
                        const i = t.indexOf('연중 최대 하락'); return {closed: /연중 최대 하락 닫기/.test(t),
                        caption: /그리지 못했습니다/.test(t), near: i < 0 ? '' : t.slice(Math.max(0, i - 80), i + 220).replace(/\\s+/g, ' ')}; }""")
                    try:
                        page.screenshot(path=str(OUT / f"online_years_error_{width}.png"), full_page=width > 600)
                    except Exception:
                        pass
                out["problems"] = _problems(page)
            except Exception as exc:
                out["error"] = f"{type(exc).__name__}: {exc}"[:300]
                try:
                    page.screenshot(path=str(OUT / f"online_error_{width}.png"))
                except Exception:
                    pass
            finally:
                page.close()
            runs.append(out)
        browser.close()
    for run in runs:
        print(json.dumps(run, ensure_ascii=False), flush=True)
    checks = {
        "급락 표 보임": all((run.get("crash") or {}).get("rows", 0) > 0 for run in runs),
        "② 두 목록 고르는 칸 · 자주 이기는 쪽 열림": all((run.get("crash") or {}).get("two") and run.get("steady_ok") for run in runs),
        "④ 상승장 시장 줄이 200일선으로 말함": all("200일선" in (run.get("swing_line") or "") for run in runs),
        "22개 테마 표 보임": all(len(run.get("theme_text") or "") > 100 for run in runs),
        "기능 ④ 쏠림 — 급락 · 상승장 표 위": all(any("흔들림" in b for b in (run.get("crash_risk") or []))
                                          and run.get("swing_risk") for run in runs),
        "기능 ⑤ 지난 급락 기록표": all("처음 −5% 다음 날" in (run.get("crash_hist") or "") for run in runs),
        "기능 ② 종목 성적표(세부사항)": all("성장" in (run.get("grades") or "") for run in runs),
        "기능 ③ 손님에게 내 계획 안 보임": all(run.get("plan_hidden") for run in runs),
        "기능 ⑥ 연중 최대 하락(시장분석)": all("해마다 평균" in (run.get("years") or "") for run in runs),
        "오류 0 · 폰 넘침 0": all(not (run.get("problems") or {}).get("exceptions")
                             and ((run.get("problems") or {}).get("overflow", 1) <= 0 or run["width"] >= 600) for run in runs),
    }
    print("\n### 온라인 자비스12 (손님 · 보기만)", flush=True)
    for name, ok in checks.items():
        print(f"  {'됨' if ok else '안 됨'} · {name}", flush=True)
    print(f"\n끝 · {'모두 됨' if all(checks.values()) else '안 된 것 있음'}", flush=True)
    return 0 if all(checks.values()) else 1


def main() -> int:
    if sys.argv[1:] == ["seed"]:
        return seed()
    if sys.argv[1:] == ["online"]:
        return online()
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
        "④ 급락 표 보임": all((run.get("crash") or {}).get("rows", 0) > 0 for run in runs),
        "④ 급락 오류 0 · 폰 넘침 0": all(not (run.get("crash_problems") or {}).get("exceptions")
                                     and ((run.get("crash_problems") or {}).get("overflow", 1) <= 0 or run["width"] >= 600)
                                     for run in runs),
        "② 자주 이기는 쪽 표 보임": all((run.get("steady_rows") or 0) > 0 for run in runs),
        "② 자주 이기는 쪽 오류 0 · 폰 넘침 0": all(not (run.get("steady_problems") or {}).get("exceptions")
                                          and ((run.get("steady_problems") or {}).get("overflow", 1) <= 0 or run["width"] >= 600)
                                          for run in runs),
        "④ 쏠림 덩이 — 급락 표 위": all(any("흔들림" in b for b in (run.get("crash_risk") or [])) for run in runs),
        "④ 쏠림 덩이 — 상승장 표 위": all(len(run.get("swing_risk") or []) >= 1 for run in runs),
        "② 종목 성적표 다섯 칸": all(any("성장" in b and "흔들림" in b for b in (run.get("grades") or [])) for run in runs),
        "② 세부사항 오류 0 · 폰 넘침 0": all(not (run.get("detail_problems") or {}).get("exceptions")
                                       and ((run.get("detail_problems") or {}).get("overflow", 1) <= 0 or run["width"] >= 600)
                                       for run in runs),
        "③ 내 계획 — 적고 저장하면 그림 · 금액": all("목표에 닿으면 +20.0%" in (run.get("plan") or "") for run in runs),
        "③ 오류 0 · 폰 넘침 0": all(not (run.get("plan_problems") or {}).get("exceptions")
                                  and ((run.get("plan_problems") or {}).get("overflow", 1) <= 0 or run["width"] >= 600)
                                  for run in runs),
        "⑤ 지난 급락 기록표 열림": all((run.get("crash_hist") or {}).get("rows", 0) >= 3 for run in runs),
        "⑥ 연중 최대 하락 그림": all((run.get("years") or {}).get("bars", 0) >= 10 for run in runs),
        "⑤ ⑥ 오류 0 · 폰 넘침 0": all(not (run.get(k) or {}).get("exceptions")
                                    and ((run.get(k) or {}).get("overflow", 1) <= 0 or run["width"] >= 600)
                                    for run in runs for k in ("years_problems", "crash_hist_problems")),
        "순위 9 표 보임": all(len(run.get("top9_text") or "") > 100 for run in runs),
        "순위 9 오류 0 · 폰 넘침 0": all(not (run.get("top9_problems") or {}).get("exceptions")
                                     and ((run.get("top9_problems") or {}).get("overflow", 1) <= 0 or run["width"] >= 600)
                                     for run in runs),
        "⑤ 상승장 시장 줄이 200일선으로 말함": all("200일선" in ((run.get("swing") or {}).get("line") or "") for run in runs),
        "⑤ 상승장 오류 0 · 폰 넘침 0": all(not (run.get("swing_problems") or {}).get("exceptions")
                                      and ((run.get("swing_problems") or {}).get("overflow", 1) <= 0 or run["width"] >= 600)
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

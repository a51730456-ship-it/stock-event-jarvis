"""자비스13 화면 확인 — 깃허브 컴퓨터에서 앱을 띄우고 자비스4 와 자비스13 을 **실제 한국 자료로** 나란히 연다
(2026-10-30 상하님 「한국테마를 꼼꼼히 잘해야 한다 · 검증 오류 이런 것 다 확인까지 해라」).

클라우드 작업 칸은 네이버가 막혀 한국 자료가 안 들어온다 — 깃허브(.github/workflows/j13_screen_check.yml)에서 돈다.
저장소에는 아무것도 쓰지 않는다. 결과는 실행 기록(아래 표)과 첨부 파일(사진 · 글)에 남는다.

보는 것
  ① 오류 — 스트림릿 빨간 오류 상자(stException) · 오류·경고 알림(stAlert) 글
  ② 같은가 — 자비스13 은 자비스4 를 베낀 화면이라 같은 자료면 같은 글이 나와야 한다.
     테마 순위표 · 수급 카드 · 눌림목 찾기 · 상승장 · 급락 후 반등장 · 순위 7(주인) · 날짜별 목록 글을 견준다(시각은 빼고).
  ③ 폰 — 412px 에서 화면이 옆으로 넘치지 않나(표는 원래 옆으로 민다 — 화면 전체만 본다)
  ④ 첫 화면 — PC 「어디로 갈까요」에 자비스13 이 보이고, 폰은 그대로 바로 자비스12 로 가나

2026-10-30 자비스4 를 닫은 뒤(상하님 「그전 한국테마는 중지시켜야지」)에는 ②를 못 한다 — 그때는 저절로 「닫은 뒤」 확인을 한다.
  ⑤ 자비스4 — 주소로 바로 들어와도 「닫혀 있습니다」만 나오고 테마표가 없나
  ⑥ 한국테마로 가는 길 — 첫 화면 PC 오른쪽 판 · 자비스12 맨 위 「🌏 한국테마 →」(눌러서 실제로 어디 닿는지까지)이 자비스13 으로 가나
  ⑦ 자비스13 — 게스트(PC·폰) · 주인 PC 로 열어 ①③ 을 본다
  ⑧ 5단계(2026-10-30) — 밑 막대(홈 · 시장분석 · 관심종목) · 한국 관심종목. 주인 폰으로 찾아 넣기 → 카드 → 세부사항 → 빼기,
     그사이 게스트 PC 로 보기만 되나(찾기 칸·빼기 단추가 없어야). 깃허브 컴퓨터의 앱은 이 실행에서만 쓰는 빈 DB 라
     넣고 빼도 진짜 기록(온라인 원격 DB)은 안 건드린다.

온라인 주소를 주면(합친 뒤 확인) 스트림릿 클라우드의 겉 화면부터 본다 — 앱을 안쪽 틀(iframe · /~/+/)에 담거나,
잠들어 「깨우기」 단추만 있을 수 있다. 무엇이 보였는지 기록에 적고 안쪽 틀 주소로 바로 연다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import tomllib
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import page_access  # noqa: E402  — 자비스4 를 닫았나(아래 J4_CLOSED)

# 자비스4 를 닫았나 — 맨 앞에 「자비스4」 이름표로 막는 줄이 있고 그 이름표가 닫혀 있으면 닫은 것이다(2026-10-30).
J4_CLOSED = ('page_access.guard(st, "자비스4")' in (ROOT / "pages" / "3_자비스4.py").read_text(encoding="utf-8")
             and not page_access.is_open("자비스4"))
BASE = os.environ.get("J13_BASE", "http://localhost:8501")
# 온라인 앱을 볼 때(깃허브 「온라인 주소」 칸)는 비밀번호가 없으니 게스트로 볼 수 있는 것만 본다(2026-10-30 합친 뒤 확인).
GUEST_ONLY = os.environ.get("J13_GUEST_ONLY") == "1"
OUT = Path(os.environ.get("J13_OUT") or "/tmp/j13shots")
# 비밀번호 — 깃허브는 이 실행에서만 만든 .streamlit/secrets.toml 에서 읽는다(시험할 때는 J13_PASSWORD 로 줄 수 있다)
PASSWORD = os.environ.get("J13_PASSWORD") or tomllib.loads(
    (ROOT / ".streamlit" / "secrets.toml").read_text(encoding="utf-8"))["APP_PASSWORD"]
# 여는 차례 — 2026-10-30 3차부터 **자비스13 을 먼저** 연다. 2차(자비스4 먼저)에서 뒤에 연 자비스13 의 눌림목이
# 22.7초로 자비스4(12.2초)보다 길었다 — 화면 탓인지 차례(시세 보관 90초가 지남) 탓인지 가르려고 바꿔 연다.
PAGES = (("자비스13", "j13"), ("자비스4", "j4"))
WAIT_MS = int(os.environ.get("J13_WAIT_MS") or 300_000)   # 처음 테마 전수 훑기는 몇 분 걸린다
_TIME = re.compile(r"\d{1,2}:\d{2}(:\d{2})?|\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?|\(\d+(\.\d+)?초\)|\d+(\.\d+)?초")
# 자비스13 에서 더한 코스피 두 줄 — 견줄 때 뺀다(자비스4 에는 없다)
_J13_LINES = re.compile(r"📉 이번 하락\(코스피 종가\):[^\n]*\n?|참고 · 코스닥 1년 최고 종가 대비[^\n]*\n?")
_NUMBER = re.compile(r"[-+−]?\d[\d,]*(\.\d+)?")


def _log(text: str) -> None:
    print(text, flush=True)


def _quiet(page, seconds: float = 3.0, limit: float = 90.0) -> None:
    """스트림릿이 다 그릴 때까지(「실행 중」 표시가 seconds 초 동안 안 보일 때까지) 기다린다 — 길어야 limit 초.

    시장판단 칸은 1분마다 혼자 다시 그려져 「실행 중」이 자주 뜬다 — 그래서 한도를 짧게 두고, 표마다는
    _settled(그 표 글이 몇 초 동안 안 바뀌면 다 그린 것)로 따로 기다린다(2026-10-30 첫 실행이 60분을 넘긴 까닭).
    """
    start = time.time()
    calm_since = None
    while time.time() - start < limit:
        busy = page.evaluate("""() => {
            const w = document.querySelector('[data-testid="stStatusWidget"]');
            // 그리는 동안은 오른쪽 위에 「Running…」 또는 「Stop」 단추가 뜬다(스트림릿 1.59)
            if (w && w.innerText && /Running|Stop|실행/.test(w.innerText)) return true;
            return [...document.querySelectorAll('header button, [data-testid="stToolbar"] button')]
                .some(b => /^\\s*Stop\\s*$/.test(b.innerText || ''));
        }""")
        if busy:
            calm_since = None
        elif calm_since is None:
            calm_since = time.time()
        elif time.time() - calm_since >= seconds:
            return
        page.wait_for_timeout(500)


def _problems(page) -> dict:
    return page.evaluate("""() => ({
        exceptions: [...document.querySelectorAll('[data-testid="stException"]')].map(e => e.innerText.slice(0, 600)),
        alerts: [...document.querySelectorAll('[data-testid="stAlert"]')].map(e => e.innerText.slice(0, 300)),
        overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth,
    })""")


def _text(page, key: str) -> str:
    return page.evaluate("""(key) => {
        const box = document.querySelector(`div[class*="st-key-${key}"]`);
        return box ? box.innerText : null;
    }""", key)


def _norm(text):
    if text is None:
        return None
    text = re.sub(r"판 [^·]*· [0-9a-f]{7}", "판 〈판 표시〉", text)     # 맨 밑 판 표시(커밋 번호)는 견주지 않는다
    return re.sub(r"\s+", " ", _TIME.sub("〈시각〉", text)).strip()


def _lines(text):
    """줄마다 나눈 글(시각은 가림) — 줄 차례만 바뀐 것(장중에 순위가 바뀜)을 가려내려고."""
    if text is None:
        return None
    return [line for line in (_norm(part) for part in text.split("\n")) if line]


def _shape(text):
    """숫자를 # 로 가린 글 — 장중 시세로 숫자만 바뀐 것과 글·칸이 바뀐 것을 가른다."""
    return None if text is None else _NUMBER.sub("#", text)


def _settled(page, key: str, seconds: float = 3.0, limit: float = 180.0) -> str | None:
    """그 칸 글이 seconds 초 동안 안 바뀔 때까지 기다리고 그 글을 돌려준다(길어야 limit 초)."""
    start, last, same_since = time.time(), None, None
    while time.time() - start < limit:
        now = _text(page, key)
        if now is not None and now == last:
            same_since = same_since or time.time()
            if time.time() - same_since >= seconds:
                return now
        else:
            same_since = None
        last = now
        page.wait_for_timeout(500)
    return last


def _click(page, key: str) -> bool:
    button = page.locator(f'div[class*="st-key-{key}"] button').first
    if not button.count():
        return False
    button.scroll_into_view_if_needed()
    button.click()
    return True


# 표 대신 뜨는 「오늘은 자리가 없습니다」 글 — 이것도 다 그린 것이다(빈자리를 채우지 않는 화면 · CLAUDE.md 0-1 바)
_EMPTY_TEXTS = ("지금은 이 기준에 맞는 종목이 없습니다", "통과한 종목이 없습니다", "조건에 맞는 종목이 없습니다")


def _wait_box(page, key: str, limit: int = WAIT_MS, *, empty_ok: bool = False):
    """그 칸이 생길 때까지 기다린다. empty_ok 면 「종목이 없습니다」 글도 받아들인다 → "table" · "empty" · False."""
    start = time.time()
    while (time.time() - start) * 1000 < limit:
        found = page.evaluate("""([key, texts]) => {
            if (document.querySelector(`div[class*="st-key-${key}"]`)) return "table";
            const alerts = [...document.querySelectorAll('[data-testid="stAlert"]')].map(a => a.innerText || "");
            return texts.some(t => alerts.some(a => a.includes(t))) ? "empty" : "";
        }""", [key, list(_EMPTY_TEXTS) if empty_ok else []])
        if found:
            return found
        page.wait_for_timeout(500)
    return False


def visit(browser, name: str, p: str, *, owner: bool, width: int, height: int, tag: str) -> dict:
    page = browser.new_page(viewport={"width": width, "height": height})
    started = time.time()
    result = {"page": name, "owner": owner, "width": width, "texts": {}, "raw": {}, "steps": []}
    try:
        page.goto(f"{BASE}/{name}" + ("" if owner else "?guest=1"), timeout=180_000)
        if owner:
            page.wait_for_selector('input[type="password"]', timeout=180_000)
            page.locator('input[type="password"]').fill(PASSWORD)
            page.locator(f'div[class*="st-key-{p}_login_submit"] button').click()
        result["theme_table"] = _wait_box(page, f"{p}_theme_table")
        if result["theme_table"]:
            _settled(page, f"{p}_theme_table")
        _quiet(page)
        result["first_screen_s"] = round(time.time() - started, 1)
        theme_raw = _text(page, f"{p}_theme_table")
        result["texts"]["theme_table"] = _norm(theme_raw)
        result["raw"]["theme_table"] = theme_raw
        body = page.evaluate("() => document.body.innerText") or ""
        if p == "j13":
            lines = re.findall(r"📉 이번 하락[^\n]*|참고 · 코스닥[^\n]*", body)
            result["kospi_line"] = " / ".join(lines) if lines else None
            # 더한 두 줄은 **자르기 전에** 뺀다 — 2차는 2,500자로 자른 뒤에 빼서 자비스13 글이 그만큼(약 110자) 짧았다
            body = _J13_LINES.sub("", body)
        top = body[:2500]
        top = top[:top.rfind("\n")] if "\n" in top else top      # 잘린 끝 줄은 버린다(숫자 길이에 따라 자른 자리가 달라진다)
        result["texts"]["page_top"] = _norm(top)
        result["raw"]["page_top"] = top
        page.screenshot(path=str(OUT / f"{tag}_{name}_1_first.png"), full_page=width > 600)
        steps = [("pullback", f"{p}_pullback_find", f"{p}_pullback_table"),
                 ("breakout", f"{p}_pullback_breakout", f"{p}_rulebook_table"),
                 ("crash", f"{p}_pullback_crash", f"{p}_rulebook_table")]
        if owner:
            steps.append(("top7", f"{p}_top7_find", f"{p}_top7_table"))
        if p == "j13":
            # 자비스12 에서 옮겨 온 것 — 파트별 성적표 + 코스피와 견줘 보기(자비스13 에만 있다)
            steps.append(("scorecard", "btn_j13sc_open", "j13sc_box"))
        for label, button, box in steps:
            at = time.time()
            before = _text(page, box)
            pressed = _click(page, button)
            if pressed:
                page.wait_for_timeout(1500)            # 누른 판이 시작되게
            shown = _wait_box(page, box, empty_ok=True) if pressed else False
            if shown == "table" and before is not None:   # 같은 칸을 다시 쓰는 단추(상승장 → 급락) — 글이 바뀔 때까지
                waited = time.time()
                while time.time() - waited < 120 and _text(page, box) == before:
                    page.wait_for_timeout(500)
            if shown == "table":
                raw = _settled(page, box)
                text = _norm(raw)
                result["raw"][label] = raw
            elif shown == "empty":
                text = "〈오늘은 이 기준에 맞는 종목이 없습니다〉"
            else:
                text = None
            result["texts"][label] = text
            result["steps"].append({"step": label, "pressed": pressed, "shown": shown, "seconds": round(time.time() - at, 1),
                                    "chars": None if text is None else len(text)})
            page.screenshot(path=str(OUT / f"{tag}_{name}_2_{label}.png"), full_page=width > 600)
        result["problems"] = _problems(page)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"[:500]
        try:
            page.screenshot(path=str(OUT / f"{tag}_{name}_9_error.png"), full_page=True)
            result["problems"] = _problems(page)
        except Exception:
            pass
    finally:
        result["total_s"] = round(time.time() - started, 1)
        page.close()
    return result


def entry_check(browser) -> dict:
    """첫 화면 — PC 는 목록에 자비스13 · 폰은 바로 자비스12."""
    out = {}
    for tag, width in (("pc", 1400), ("phone", 412)):
        page = browser.new_page(viewport={"width": width, "height": 900})
        try:
            page.goto(BASE + "/", timeout=180_000)
            page.wait_for_selector('input[type="password"]', timeout=180_000)
            page.locator('input[type="password"]').fill(PASSWORD)
            page.get_by_role("button", name=re.compile(r"^로그인$")).first.click()
            page.wait_for_timeout(8000)
            out[tag] = {
                "path": page.evaluate("() => decodeURIComponent(location.pathname)"),
                "links": page.evaluate("""() => [...document.querySelectorAll('[class*="st-key-entry_dest"] a')]
                    .map(a => a.innerText.trim() + (a.getClientRects().length ? '' : ' (숨김)'))"""),
            }
        except Exception as exc:
            out[tag] = {"error": str(exc)[:300]}
        finally:
            page.close()
    return out


def closed_check(browser) -> dict:
    """⑤ 옛 한국테마(자비스4) — 주소로 바로 들어와도 「닫혀 있습니다」만 나오고 테마표가 없어야 한다."""
    out = {}
    for who, suffix in (("게스트 주소", "?guest=1"), ("그냥 주소", "")):
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        try:
            page.goto(f"{BASE}/자비스4{suffix}", timeout=180_000)
            page.wait_for_function("() => document.body.innerText.includes('닫혀 있습니다')", timeout=120_000)
            page.wait_for_timeout(3000)                 # 막은 뒤에 더 그려지는 것이 없나 잠깐 더 본다
            body = page.evaluate("() => document.body.innerText") or ""
            out[who] = {
                "closed": "이 화면은 지금 닫혀 있습니다" in body,
                "theme_table": page.evaluate("() => !!document.querySelector('div[class*=\"st-key-j4_theme_table\"]')"),
                "links": page.evaluate("() => [...document.querySelectorAll('a')].map(a => a.innerText.trim()).filter(Boolean)"),
                "problems": _problems(page),
            }
            page.screenshot(path=str(OUT / f"closed_{'guest' if suffix else 'plain'}_자비스4.png"), full_page=True)
        except Exception as exc:
            out[who] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
        finally:
            page.close()
    return out


def roads_check(browser) -> dict:
    """⑥ 한국테마로 가는 길 — 첫 화면 PC 오른쪽 판 · 자비스12 맨 위 「🌏 한국테마 →」(눌러서 닿는 곳까지)."""
    out = {}
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    try:
        page.goto(BASE + "/", timeout=180_000)
        link = page.locator('div[class*="st-key-jp_panel_KR"] a').first
        link.wait_for(timeout=180_000)
        out["첫 화면 오른쪽 판"] = {
            "label": link.inner_text().strip(),
            "href": page.evaluate("(a) => decodeURIComponent(a.getAttribute('href') || '')", link.element_handle()),
        }
    except Exception as exc:
        out["첫 화면 오른쪽 판"] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
    finally:
        page.close()
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    try:
        page.goto(f"{BASE}/자비스12?guest=1", timeout=180_000)
        link = page.locator('div[class*="st-key-jarvis_cross_market"] a').first
        link.wait_for(timeout=240_000)
        row = {"label": link.inner_text().strip(),
               "href": page.evaluate("(a) => decodeURIComponent(a.getAttribute('href') || '')", link.element_handle())}
        link.click()
        page.wait_for_function("() => decodeURIComponent(location.pathname).endsWith('/자비스13')", timeout=60_000)
        page.wait_for_timeout(8000)
        row["landed"] = page.evaluate("() => decodeURIComponent(location.pathname)")
        row["problems"] = _problems(page)
        page.screenshot(path=str(OUT / "road_자비스12_to_자비스13.png"), full_page=True)
        out["자비스12 「🌏 한국테마 →」"] = row
    except Exception as exc:
        out["자비스12 「🌏 한국테마 →」"] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
    finally:
        page.close()
    return out


def _login(page, p: str) -> None:
    page.wait_for_selector('input[type="password"]', timeout=180_000)
    page.locator('input[type="password"]').fill(PASSWORD)
    page.locator(f'div[class*="st-key-{p}_login_submit"] button').click()


def _body_has(page, text: str, timeout: int = 180_000) -> bool:
    try:
        page.wait_for_function("(t) => document.body.innerText.includes(t)", arg=text, timeout=timeout)
        return True
    except Exception:
        return False


def _watch_view(page) -> dict:
    return page.evaluate("""() => ({
        cards: [...document.querySelectorAll('.j13w-card')].map(c => c.innerText.replace(/\\s+/g, ' ').slice(0, 220)),
        search: !!document.querySelector('div[class*="st-key-j13w_query"] input'),
        remove: document.querySelectorAll('div[class*="st-key-j13w_remove_"] button').length,
        bar: [...document.querySelectorAll('nav.j13b-bottom-nav .j13b-nav-item')].map(e => e.innerText.replace(/\\s+/g, ' ').trim()),
        active: ((document.querySelector('nav.j13b-bottom-nav .j13b-nav-item.active') || {}).innerText || '').trim(),
        path: decodeURIComponent(location.pathname + location.search),
    })""")


def watch_check(browser, *, owner_flow: bool) -> dict:
    """⑧ 5단계 — 밑 막대와 한국 관심종목. owner_flow=False(온라인)면 게스트 PC 로 보기만 한다."""
    out = {}
    owner = browser.new_page(viewport={"width": 412, "height": 915}) if owner_flow else None
    guest = browser.new_page(viewport={"width": 1400, "height": 900})
    try:
        if owner is not None:
            owner.goto(f"{BASE}/자비스13", timeout=180_000)
            _login(owner, "j13")
            owner.locator("nav.j13b-bottom-nav").wait_for(timeout=WAIT_MS)
            _quiet(owner)
            out["주인 처음"] = _watch_view(owner)            # 시장분석이 먼저 켜져 있어야 한다
            _click(owner, "j13b_nav_watch")
            out["주인 관심종목 열림"] = _body_has(owner, "★ 관심종목")
            _quiet(owner)
            box = owner.locator('div[class*="st-key-j13w_query"] input')
            box.fill("삼성전자")
            box.press("Enter")
            owner.locator('div[class*="st-key-j13w_add_found"] button').wait_for(timeout=120_000)
            _click(owner, "j13w_add_found")
            out["넣음 알림"] = _body_has(owner, "관심종목에 넣었습니다", 120_000)
            owner.wait_for_selector(".j13w-card", timeout=180_000)
            _quiet(owner)
            out["주인 카드"] = _watch_view(owner)["cards"]
            out["코드"] = owner.evaluate("() => ((document.querySelector('.j13w-code') || {}).innerText || '').trim()")
            owner.screenshot(path=str(OUT / "watch_owner_phone_1_card.png"), full_page=True)
            _click(owner, f"j13w_open_{out['코드']}")
            out["세부사항 열림"] = _body_has(owner, "관심종목에 있음", 180_000)
            _quiet(owner)
            owner.screenshot(path=str(OUT / "watch_owner_phone_2_detail.png"), full_page=False)
            out["주인 문제"] = _problems(owner)
        # 게스트(PC) — 보기만. 주인이 넣은 카드는 보이고 찾기 칸 · 빼기 단추는 없어야 한다
        guest.goto(f"{BASE}/자비스13?guest=1", timeout=180_000)
        guest.locator("nav.j13b-bottom-nav").wait_for(timeout=WAIT_MS)
        _quiet(guest)
        _click(guest, "j13b_nav_watch")
        out["게스트 관심종목 열림"] = _body_has(guest, "★ 관심종목")
        _quiet(guest)
        out["게스트"] = _watch_view(guest)
        out["게스트 문제"] = _problems(guest)
        guest.screenshot(path=str(OUT / "watch_guest_pc.png"), full_page=True)
        _click(guest, "j13b_nav_home")
        guest.wait_for_timeout(8000)
        out["게스트 홈 →"] = guest.evaluate("() => decodeURIComponent(location.pathname)")
        if owner is not None:
            _click(owner, f"j13w_remove_{out['코드']}")
            out["뺌 알림"] = _body_has(owner, "관심종목에서 뺐습니다", 120_000)
            _quiet(owner)
            out["뺀 뒤 카드"] = len(_watch_view(owner)["cards"])
            _click(owner, "j13b_nav_market")
            out["시장분석으로"] = _body_has(owner, "한국 전체시장 판단", WAIT_MS)
            _quiet(owner)
            _click(owner, "j13b_nav_home")
            owner.wait_for_timeout(10_000)                     # 폰은 첫 화면이 하나 남은 자비스12 로 바로 넘긴다
            out["주인 폰 홈 →"] = owner.evaluate("() => decodeURIComponent(location.pathname)")
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"[:400]
        for pg, name in ((owner, "owner"), (guest, "guest")):
            if pg is not None:
                try:
                    pg.screenshot(path=str(OUT / f"watch_{name}_9_error.png"), full_page=True)
                except Exception:
                    pass
    finally:
        for pg in (owner, guest):
            if pg is not None:
                pg.close()
    return out


def watch_checks(watch: dict, *, owner_flow: bool) -> dict:
    """⑧ 의 됐나/안 됐나."""
    guest = watch.get("게스트") or {}
    checks = {
        "관심종목 화면 — 게스트는 보기만(찾기 칸·빼기 없음)": bool(watch.get("게스트 관심종목 열림")) and not guest.get("search")
        and not guest.get("remove") and not (watch.get("게스트 문제") or {}).get("exceptions"),
        "밑 막대 「홈」 → 첫 화면(PC)": str(watch.get("게스트 홈 →", "")).endswith("/"),
    }
    if owner_flow:
        first = watch.get("주인 처음") or {}
        cards = watch.get("주인 카드") or []
        checks.update({
            "밑 막대 차례 홈 · 시장분석 · 관심종목 · 처음은 시장분석":
                [item.split()[-1] for item in first.get("bar", []) if item] == ["홈", "시장분석", "관심종목"]
                and "시장분석" in first.get("active", ""),
            "찾아 넣기 → 카드(원화 · 넣은 날 · 코스피와 견줌)": bool(watch.get("넣음 알림")) and bool(cards)
                and "원" in cards[0] and "넣은 날" in cards[0] and "코스피" in cards[0],
            "카드 「세부사항」 열림": bool(watch.get("세부사항 열림")) and not (watch.get("주인 문제") or {}).get("exceptions"),
            "게스트에게 주인이 넣은 카드 보임": len(guest.get("cards") or []) >= 1,
            "빼기 → 알림 · 카드 없어짐": bool(watch.get("뺌 알림")) and watch.get("뺀 뒤 카드") == 0,
            "밑 막대 「시장분석」으로 돌아감": bool(watch.get("시장분석으로")),
            "폰 「홈」 → 자비스12(폰 첫 화면이 바로 넘김)": str(watch.get("주인 폰 홈 →", "")).endswith("/자비스12"),
        })
    return checks


def after_close(browser, report: dict) -> None:
    """자비스4 를 닫은 뒤의 확인(⑤⑥⑦) — 맨 끝에 한 줄로 됐나/안 됐나를 적는다."""
    entry = report["entry"]
    report["closed"] = closed_check(browser)
    report["roads"] = roads_check(browser)
    _log(f"자비스4: {json.dumps(report['closed'], ensure_ascii=False)}")
    _log(f"가는 길: {json.dumps(report['roads'], ensure_ascii=False)}")
    for owner in (False, True):
        sizes = (("pc", 1400, 900),) if owner else (("pc", 1400, 900), ("phone", 412, 915))
        for tag, width, height in sizes:
            run = visit(browser, "자비스13", "j13", owner=owner, width=width, height=height,
                        tag=f"{'owner' if owner else 'guest'}_{tag}")
            report["runs"].append(run)
            _report_run(run)
    report["watch"] = watch_check(browser, owner_flow=True)
    _log(f"\n관심종목(5단계): {json.dumps(report['watch'], ensure_ascii=False)}")
    checks = {
        "PC 목록이 자비스12 · 자비스13 둘": (entry.get("pc") or {}).get("links") == ["미국테마 (자비스12)", "한국테마 (자비스13)"],
        "폰은 바로 자비스12": (entry.get("phone") or {}).get("path") == "/자비스12",
        "자비스4 닫힘(테마표 없음)": all(v.get("closed") and not v.get("theme_table") for v in report["closed"].values()),
        "첫 화면 오른쪽 판 → 자비스13": "자비스13" in str((report["roads"].get("첫 화면 오른쪽 판") or {}).get("href")),
        "「🌏 한국테마 →」 → 자비스13": str((report["roads"].get("자비스12 「🌏 한국테마 →」") or {}).get("landed", "")).endswith("/자비스13"),
        "자비스13 오류 상자 0": all(not (r.get("problems") or {}).get("exceptions") and not r.get("error") for r in report["runs"]),
        "자비스13 테마표 보임": all(r.get("theme_table") for r in report["runs"]),
        "폰 옆 넘침 0": all((r.get("problems") or {}).get("overflow", 1) <= 0 for r in report["runs"] if r["width"] < 600),
        **watch_checks(report["watch"], owner_flow=True),
    }
    report["checks"] = checks
    _log("\n### 자비스4 를 닫은 뒤")
    for name, ok in checks.items():
        _log(f"  {'됨' if ok else '⚠ 안 됨'} · {name}")
    _log(f"\n끝(닫은 뒤) · {'모두 됨' if all(checks.values()) else '⚠ 안 된 것 있음'}")


def _has_app(frame) -> bool:
    try:
        return bool(frame.evaluate("() => !!document.querySelector('[data-testid=\"stApp\"]')"))
    except Exception:
        return False


def online_root(browser) -> str:
    """온라인 겉 화면을 먼저 본다 — 잠들었으면 깨우고, 앱이 안쪽 틀(/~/+/)에 있으면 그 주소를 돌려준다.

    2026-10-30 첫 온라인 확인(실행 41012410955)은 모든 칸이 시간 초과였다(첫 화면 305초 · 테마표 없음). 작업 칸에서는
    사진 첨부를 못 받으니, 겉 화면의 제목 · 글 · 틀 주소를 기록에 적어 까닭을 가린다.
    """
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    root = BASE
    try:
        page.goto(BASE + "/", timeout=180_000)
        deadline, woke, here, inner = time.time() + 420, 0, False, None
        while time.time() < deadline:
            page.wait_for_timeout(5000)
            wake = page.get_by_role("button", name=re.compile(r"back up|wake", re.I))
            if wake.count() and woke < 3:              # 잠든 앱 — 「Yes, get this app back up!」
                wake.first.click()
                woke += 1
                continue
            here = _has_app(page.main_frame)
            inner = next((f for f in page.frames if f is not page.main_frame and _has_app(f)), None)
            if here or inner is not None:
                break
        info = {"title": page.title(), "url": page.url, "woke": woke, "app_here": here,
                "app_frame": inner.url if inner is not None else None,
                "frames": [f.url for f in page.frames][:6],
                "text": (page.evaluate("() => document.body.innerText") or "")[:300]}
        _log(f"온라인 겉 화면: {json.dumps(info, ensure_ascii=False)}")
        page.screenshot(path=str(OUT / "online_0_outer.png"), full_page=True)
        found = re.match(r"^(https?://[^/]+/~/\+)", inner.url) if (not here and inner is not None) else None
        if found:
            root = found.group(1)
    except Exception as exc:
        _log(f"온라인 겉 화면을 못 봄: {type(exc).__name__}: {exc}"[:300])
    finally:
        page.close()
    _log(f"온라인 앱을 여는 주소: {root}")
    return root


def online_guest(browser, report: dict) -> None:
    """온라인 앱 — 게스트로 볼 수 있는 것만: 자비스4 닫힘 · 첫 화면 판 · 「🌏 한국테마 →」(눌러서) · 자비스13 PC·폰 · 관심종목."""
    global BASE
    BASE = online_root(browser)
    report["closed"] = closed_check(browser)
    report["roads"] = roads_check(browser)
    _log(f"자비스4: {json.dumps(report['closed'], ensure_ascii=False)}")
    _log(f"가는 길: {json.dumps(report['roads'], ensure_ascii=False)}")
    for tag, width, height in (("pc", 1400, 900), ("phone", 412, 915)):
        run = visit(browser, "자비스13", "j13", owner=False, width=width, height=height, tag=f"online_{tag}")
        report["runs"].append(run)
        _report_run(run)
    report["watch"] = watch_check(browser, owner_flow=False)
    _log(f"\n관심종목(5단계 · 게스트): {json.dumps(report['watch'], ensure_ascii=False)}")
    checks = {
        "자비스4 닫힘(테마표 없음)": all(v.get("closed") and not v.get("theme_table") for v in report["closed"].values()),
        "첫 화면 오른쪽 판 → 자비스13": "자비스13" in str((report["roads"].get("첫 화면 오른쪽 판") or {}).get("href")),
        "「🌏 한국테마 →」 → 자비스13": str((report["roads"].get("자비스12 「🌏 한국테마 →」") or {}).get("landed", "")).endswith("/자비스13"),
        "자비스13 오류 상자 0": all(not (r.get("problems") or {}).get("exceptions") and not r.get("error") for r in report["runs"]),
        "자비스13 테마표 보임": all(r.get("theme_table") for r in report["runs"]),
        "폰 옆 넘침 0": all((r.get("problems") or {}).get("overflow", 1) <= 0 for r in report["runs"] if r["width"] < 600),
        **watch_checks(report["watch"], owner_flow=False),
    }
    report["checks"] = checks
    _log(f"\n### 온라인({BASE}) 게스트로 본 것")
    for name, ok in checks.items():
        _log(f"  {'됨' if ok else '⚠ 안 됨'} · {name}")
    _log(f"\n끝(온라인) · {'모두 됨' if all(checks.values()) else '⚠ 안 된 것 있음'}")


def _report_run(run: dict) -> None:
    probs = run.get("problems") or {}
    _log(f"\n[{run['page']} · {'주인' if run['owner'] else '게스트'} · {run['width']}px"
         + (" · 한 번 더" if run.get("again") else "") + f"] 첫 화면 {run.get('first_screen_s')}초 · "
         f"전체 {run.get('total_s')}초 · 테마표 {'보임' if run.get('theme_table') else '없음'} · "
         f"오류 상자 {len(probs.get('exceptions') or [])} · 알림 {len(probs.get('alerts') or [])} · "
         f"옆 넘침 {probs.get('overflow')}px" + (f" · ⚠ {run['error']}" if run.get("error") else ""))
    for step in run["steps"]:
        _log(f"   {step['step']}: 눌림 {step['pressed']} · 표 {step['shown']} · {step['seconds']}초")
    for item in (probs.get("exceptions") or []):
        _log(f"   ⚠ 오류 상자: {item[:300]}")
    for item in (probs.get("alerts") or []):
        _log(f"   · 알림: {item[:200]}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"runs": [], "same": {}}
    with sync_playwright() as play:
        browser = play.chromium.launch()
        if GUEST_ONLY:
            online_guest(browser, report)
            browser.close()
            (OUT / "j13_screen_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
            return 0
        report["entry"] = entry_check(browser)
        _log(f"첫 화면: {json.dumps(report['entry'], ensure_ascii=False)}")
        if J4_CLOSED:
            after_close(browser, report)
            browser.close()
            (OUT / "j13_screen_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
            return 0
        _log(f"여는 차례: {' → '.join(name for name, _p in PAGES)} (주인은 끝에 자비스13 을 한 번 더)")
        for owner in (False, True):
            for name, p in PAGES:
                phone = (("phone", 412, 915),) if (not owner and p == "j13") else ()
                for tag, width, height in (("pc", 1400, 900),) + phone:
                    run = visit(browser, name, p, owner=owner, width=width, height=height,
                                tag=f"{'owner' if owner else 'guest'}_{tag}")
                    report["runs"].append(run)
                    _report_run(run)
            if owner:
                # 주인으로 자비스13 을 한 번 더 — 앞에서 받은 시세가 남아 있을 때 걸리는 시간(견주기에는 안 쓴다)
                run = visit(browser, "자비스13", "j13", owner=True, width=1400, height=900, tag="owner_pc_again")
                run["again"] = True
                report["runs"].append(run)
                _report_run(run)
        browser.close()
    # 같은가 — 같은 조건(주인/게스트 · 폭)끼리 자비스4 와 자비스13 을 견준다
    # 장중에는 두 화면을 여는 사이(30~60초)에 시세가 바뀐다 — 그래서 셋으로 가른다:
    #   같음 · 숫자만 다름(글·칸·이름은 같고 숫자만) · 숫자·줄 차례만 다름(순위가 바뀜) · ⚠ 다름(글이나 칸이 다름)
    _log("\n### 자비스4 와 자비스13 이 같은 글을 보이나 (시각은 빼고)")
    by = {}
    for run in report["runs"]:
        if run.get("again"):
            continue
        by.setdefault((run["owner"], run["width"]), {})[run["page"]] = run
    all_same = True
    for (owner, width), pair in sorted(by.items()):
        a, b = pair.get("자비스4"), pair.get("자비스13")
        if not a or not b:
            continue
        for key in sorted(set(a["texts"]) | set(b["texts"])):
            ta, tb = a["texts"].get(key), b["texts"].get(key)
            ra, rb = a["raw"].get(key), b["raw"].get(key)
            if key == "scorecard":        # 자비스13 에만 있다 — 견주지 않고 따로 적는다
                continue
            if key == "page_top":         # 맨 위 글에는 화면 이름(자비스4/13)이 들어 있어 이름을 같게 친 뒤 견준다
                ta, ra = (ta and ta.replace("자비스4", "자비스N")), (ra and ra.replace("자비스4", "자비스N"))
                tb, rb = (tb and tb.replace("자비스13", "자비스N")), (rb and rb.replace("자비스13", "자비스N"))
            same = ta == tb
            shape_same = ta is not None and _shape(ta) == _shape(tb)
            la, lb = _lines(ra), _lines(rb)
            lines_same = bool(la) and bool(lb) and sorted(map(_shape, la)) == sorted(map(_shape, lb))
            ok = same or shape_same or lines_same or (ta is None and tb is None)
            all_same &= ok
            mark = ("같음" if same else "숫자만 다름(장중 시세)" if shape_same
                    else "숫자·줄 차례만 다름(장중 순위)" if lines_same else "⚠ 다름")
            report["same"][f"{'주인' if owner else '게스트'}_{width}_{key}"] = mark
            _log(f"  {'주인' if owner else '게스트'} {width}px · {key}: {mark} "
                 f"(글자 {len(ta or '')} · {len(tb or '')})")
            if not same and ta and tb:
                i = next((i for i, (x, y) in enumerate(zip(ta, tb)) if x != y), min(len(ta), len(tb)))
                _log(f"      자비스4 : …{ta[max(0, i - 80):i + 120]}…\n      자비스13: …{tb[max(0, i - 80):i + 120]}…")
            if not ok and la and lb:      # 글이 다른 줄만 따로 적는다(숫자는 가린 채)
                only_a = sorted(set(map(_shape, la)) - set(map(_shape, lb)))[:6]
                only_b = sorted(set(map(_shape, lb)) - set(map(_shape, la)))[:6]
                _log(f"      자비스4 에만: {only_a}\n      자비스13 에만: {only_b}")
    _log("\n### 자비스13 에만 있는 것")
    for run in report["runs"]:
        if run["page"] != "자비스13" or run.get("again"):
            continue
        who = f"{'주인' if run['owner'] else '게스트'} {run['width']}px"
        _log(f"  {who} · 코스피 줄: {run.get('kospi_line')}")
        card = run["texts"].get("scorecard")
        _log(f"  {who} · 성적표: {'없음' if not card else card[:600]}")
    errors = sum(len((r.get("problems") or {}).get("exceptions") or []) for r in report["runs"])
    crashed = [r["page"] for r in report["runs"] if r.get("error")]
    _log(f"\n끝 · 오류 상자 모두 {errors}개 · 멈춘 판 {crashed or '없음'} · 둘이 모두 같음 {all_same}")
    (OUT / "j13_screen_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
BASE = os.environ.get("J13_BASE", "http://localhost:8501")
OUT = Path(os.environ.get("J13_OUT") or "/tmp/j13shots")
# 비밀번호 — 깃허브는 이 실행에서만 만든 .streamlit/secrets.toml 에서 읽는다(시험할 때는 J13_PASSWORD 로 줄 수 있다)
PASSWORD = os.environ.get("J13_PASSWORD") or tomllib.loads(
    (ROOT / ".streamlit" / "secrets.toml").read_text(encoding="utf-8"))["APP_PASSWORD"]
PAGES = (("자비스4", "j4"), ("자비스13", "j13"))
WAIT_MS = int(os.environ.get("J13_WAIT_MS") or 300_000)   # 처음 테마 전수 훑기는 몇 분 걸린다
_TIME = re.compile(r"\d{1,2}:\d{2}(:\d{2})?|\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?|\(\d+(\.\d+)?초\)|\d+(\.\d+)?초")


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
    result = {"page": name, "owner": owner, "width": width, "texts": {}, "steps": []}
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
        result["texts"]["theme_table"] = _norm(_text(page, f"{p}_theme_table"))
        result["texts"]["page_top"] = _norm(page.evaluate("() => document.body.innerText.slice(0, 2500)"))
        if p == "j13":
            lines = re.findall(r"📉 이번 하락[^\n]*|참고 · 코스닥[^\n]*", page.evaluate("() => document.body.innerText") or "")
            result["kospi_line"] = " / ".join(lines) if lines else None
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
                text = _norm(_settled(page, box))
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


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"runs": [], "same": {}}
    with sync_playwright() as play:
        browser = play.chromium.launch()
        report["entry"] = entry_check(browser)
        _log(f"첫 화면: {json.dumps(report['entry'], ensure_ascii=False)}")
        for owner in (False, True):
            for name, p in PAGES:
                phone = (("phone", 412, 915),) if (not owner and p == "j13") else ()
                for tag, width, height in (("pc", 1400, 900),) + phone:
                    run = visit(browser, name, p, owner=owner, width=width, height=height,
                                tag=f"{'owner' if owner else 'guest'}_{tag}")
                    report["runs"].append(run)
                    probs = run.get("problems") or {}
                    _log(f"\n[{name} · {'주인' if owner else '게스트'} · {width}px] 첫 화면 {run.get('first_screen_s')}초 · "
                         f"전체 {run.get('total_s')}초 · 테마표 {'보임' if run.get('theme_table') else '없음'} · "
                         f"오류 상자 {len(probs.get('exceptions') or [])} · 알림 {len(probs.get('alerts') or [])} · "
                         f"옆 넘침 {probs.get('overflow')}px" + (f" · ⚠ {run['error']}" if run.get("error") else ""))
                    for step in run["steps"]:
                        _log(f"   {step['step']}: 눌림 {step['pressed']} · 표 {step['shown']} · {step['seconds']}초")
                    for item in (probs.get("exceptions") or []):
                        _log(f"   ⚠ 오류 상자: {item[:300]}")
                    for item in (probs.get("alerts") or []):
                        _log(f"   · 알림: {item[:200]}")
        browser.close()
    # 같은가 — 같은 조건(주인/게스트 · 폭)끼리 자비스4 와 자비스13 을 견준다
    _log("\n### 자비스4 와 자비스13 이 같은 글을 보이나 (시각은 빼고)")
    by = {}
    for run in report["runs"]:
        by.setdefault((run["owner"], run["width"]), {})[run["page"]] = run
    all_same = True
    for (owner, width), pair in sorted(by.items()):
        a, b = pair.get("자비스4"), pair.get("자비스13")
        if not a or not b:
            continue
        for key in sorted(set(a["texts"]) | set(b["texts"])):
            ta, tb = a["texts"].get(key), b["texts"].get(key)
            if key == "scorecard":        # 자비스13 에만 있다 — 견주지 않고 따로 적는다
                continue
            if key == "page_top":         # 맨 위 글에는 화면 이름(자비스4/13)이 들어 있어 이름을 같게 친 뒤 견준다
                ta = ta and ta.replace("자비스4", "자비스N")
                tb = tb and tb.replace("자비스13", "자비스N")
                # 자비스13 에서 더한 코스피 두 줄(「이번 하락」 · 코스닥 참고)은 빼고 견준다
                tb = tb and re.sub(r"📉 이번 하락\(코스피 종가\):.*?지금 [-+]?\d+\.\d%( · 급락 후 반등장 기준일 \d+월 \d+일)? ?", "", tb)
                tb = tb and re.sub(r"참고 · 코스닥 1년 최고 종가 대비 [-+]?\d+\.\d% \(고점 \d+월 \d+일\) ?", "", tb)
            same = ta == tb
            all_same &= same or (ta is None and tb is None)
            report["same"][f"{'주인' if owner else '게스트'}_{width}_{key}"] = same
            mark = "같음" if same else "⚠ 다름"
            _log(f"  {'주인' if owner else '게스트'} {width}px · {key}: {mark} "
                 f"(글자 {len(ta or '')} · {len(tb or '')})")
            if not same and ta and tb:
                i = next((i for i, (x, y) in enumerate(zip(ta, tb)) if x != y), min(len(ta), len(tb)))
                _log(f"      자비스4 : …{ta[max(0, i - 80):i + 120]}…\n      자비스13: …{tb[max(0, i - 80):i + 120]}…")
    _log("\n### 자비스13 에만 있는 것")
    for run in report["runs"]:
        if run["page"] != "자비스13":
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

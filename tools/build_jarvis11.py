"""자비스3 화면 파일을 베껴 안 쓰는 것만 뺀 자비스11을 만든다.

python tools/build_jarvis11.py            (pages/2_자비스3.py → pages/10_자비스11.py)
python tools/build_jarvis11.py <원본> <만들 파일> [--no-rename]

**자비스11 만 따로 고친 것이 생기면 이 스크립트로 다시 만들지 않는다** — 다시 만들면 그 고친 것이
사라진다. 그때는 자비스11 파일을 손으로 고친다.
**2026-10-01 오후부터 자비스11 만의 고침이 있다** — 22개 테마 자료를 새로 받아야 할 때 뒤로 미루기
(_theme_batch_ready · _start_theme_fetch · _ranking_ready · _render_theme_pending). 이 도구로 다시 만들면 사라진다.
화면에 보이는 것은 바꾸지 않는다 — 뺀 것은 ① 아무 데서도 부르지 않는 위층 이름 ② 어디에도
걸리지 않는 꾸밈 규칙 ③ 폰으로 보내는 꾸밈·움직임 코드 안의 설명 글뿐이다.
"""
from __future__ import annotations

import ast
import io
import json
import re
import subprocess
import sys
import tokenize
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jarvis11_css_dead as css_dead  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]
_ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
SRC = Path(_ARGS[0]) if _ARGS else _ROOT / "pages" / "2_자비스3.py"
OUT = Path(_ARGS[1]) if len(_ARGS) > 1 else _ROOT / "pages" / "10_자비스11.py"
RENAME = "--no-rename" not in sys.argv
src = SRC.read_text(encoding="utf-8")
log = []


# ── 1. 이름 바꾸기(자비스3 과 한 탭에서 섞이지 않게) · 제목 ─────────────────────────────
def must_replace(text, old, new, count=None):
    n = text.count(old)
    assert n > 0, f"없음: {old!r}"
    if count is not None:
        assert n == count, f"{old!r} {n}번(기대 {count})"
    log.append(f"바꿈 {n}번: {old[:50]!r} → {new[:50]!r}")
    return text.replace(old, new)


src = must_replace(src, '"""자비스3 — 미국 테마 레이더와 실제 매수 기록 페이지."""',
                   '"""자비스11 — 자비스3 미국테마를 그대로 베끼고 안 쓰는 코드만 뺀 화면 (2026-10-01 상하님 지시).\n\n'
                   '상하님 — *"자비스3 미국테마는 그대로 두고 중요부분을 그대로 복사해서 자비스11 미국테마\n'
                   '하나를 더 만든다 … 필요없는 코드는 다 버리고 지금 있는 것 그대로 다 가져간다."*\n\n'
                   '화면에 보이는 것·점수·목록은 자비스3 과 같다(같은 jarvis3_data 를 부른다).\n'
                   '뺀 것 — 아무 데서도 부르지 않던 함수, 어디에도 걸리지 않던 꾸밈 규칙, 폰으로 보내던\n'
                   '꾸밈·움직임 코드 안의 설명 글. 그 설명과 내력은 pages/2_자비스3.py 에 그대로 있다.\n'
                   '자비스3 과 한 탭에서 오가도 손가락 넘기기가 섞이지 않게 화면 표식·사진 저장 이름을 j11 로 바꿨다.\n"""', 1)
src = must_replace(src, 'st.set_page_config(page_title="자비스3 — 종목 브리핑", layout="wide")',
                   'st.set_page_config(page_title="자비스11 — 미국테마", layout="wide")\n\n'
                   'import page_access  # noqa: E402\n\n'
                   'if int(getattr(page_access, "MODULE_REVISION", 0)) < 2026100101:\n'
                   '    import importlib as _importlib\n\n'
                   '    page_access = _importlib.reload(page_access)\n'
                   'page_access.guard(st, "자비스11")', 1)
src = must_replace(src, 'st.markdown("## 자비스3 — 미국 테마 레이더")', 'st.markdown("## 자비스11 — 미국테마")', 1)
src = must_replace(src, 'st.button("자비스3 로그인", key="j3_login_submit"', 'st.button("자비스11 로그인", key="j3_login_submit"', 1)
src = must_replace(src, '<div class="j3b-title">JARVIS <b>3</b></div>', '<div class="j3b-title">JARVIS <b>11</b></div>', 1)
src = must_replace(src, 'hero_banner.render(st, refresh_key="j3hero_refresh")',
                   'hero_banner.render(st, refresh_key="j3hero_refresh", mark="11")', 1)
if RENAME:
    # 화면 표식 — 자비스3 의 넘기기 코드가 이 화면을 제 화면으로 알아보지 않게 한다.
    src = must_replace(src, "j3b-home", "j11b-home")
    src = must_replace(src, "j3-market-top", "j11-market-top")
    # 넘기기 코드의 이름표·사진 칸·폰 저장소 이름
    src = must_replace(src, "j3b-swipe-script", "j11b-swipe-script")
    src = must_replace(src, "'j3snap-host'", "'j11snap-host'")
    src = must_replace(src, "copyHolder('j3page-host'), EDGE = copyHolder('j3curl-host')",
                       "copyHolder('j11page-host'), EDGE = copyHolder('j11curl-host')", 1)
    src = must_replace(src, "var STORE = 'j3snap:v1:';", "var STORE = 'j11snap:v1:';", 1)
    # 손가락 움직임 한 번을 두 번 세지 않으려고 붙이는 「봤다」 표시. 이름이 같으면 자비스3 코드가 먼저
    # 표시를 붙여 자비스11 코드가 그 움직임을 버린다(2026-10-01 실측 — 자비스3 을 먼저 연 탭에서 안 넘어감).
    src = must_replace(src, "ev.__j3seen", "ev.__j11seen", 2)
    # 홈에서 넘기면 자비스11 로 — 다만 자비스3 넘기기 코드가 이 탭에 이미 있으면 홈은 그쪽에 맡긴다
    # (둘이 함께 받으면 한 번 밀어 두 곳으로 간다).
    src = must_replace(src, "if (now === 'home') { return { link: '자비스3', from: 'home', to: 'watch' }; }",
                       "if (now === 'home') { return { link: '자비스11', from: 'home', to: 'watch' }; }", 1)
    src = must_replace(src, "  function screenNow() {\n", "  function screenNow() {\n"
                       "    var s = screenNow0();\n"
                       "    if (s === 'home' && d.getElementById('j3b-swipe-script')) { return ''; }\n"
                       "    return s;\n"
                       "  }\n"
                       "  function screenNow0() {\n", 1)


# ── 2. 아무 데서도 부르지 않는 위층 이름 빼기 ───────────────────────────────────────────
def dead_top_level(text):
    tree = ast.parse(text)
    defs = {}
    for node in tree.body:
        names = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        for n in names:
            start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
            defs[n] = (start, node.end_lineno)
    loads = [(n.id, n.lineno) for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)]
    dead = set()
    for _ in range(10):
        changed = False
        for name, (a, b) in defs.items():
            if name in dead or name.startswith("__") or name == "main":
                continue
            used = False
            for lid, ln in loads:
                if lid != name or a <= ln <= b:
                    continue
                owner = [o for o, (oa, ob) in defs.items() if oa <= ln <= ob]
                if owner and all(o in dead for o in owner):
                    continue
                used = True
                break
            if not used and re.search(r"""['"]%s['"]""" % re.escape(name), text):
                used = True
            if not used:
                dead.add(name)
                changed = True
        if not changed:
            break
    return dead, defs


dead, defs = dead_top_level(src)
lines = src.splitlines(keepends=True)
drop = set()
for name in dead:
    a, b = defs[name]
    # 바로 위에 붙은 주석 덩어리(빈 줄 없이 이어진 것)도 그 이름의 설명이다
    k = a - 2
    while k >= 0 and lines[k].lstrip().startswith("#"):
        k -= 1
    for i in range(k + 1, b):
        drop.add(i)
    log.append(f"뺀 이름: {name} ({b - a + 1}줄, 설명 {a - 1 - (k + 1)}줄)")
src = "".join(line for i, line in enumerate(lines) if i not in drop)
src = re.sub(r"\n{4,}", "\n\n\n", src)
again, _ = dead_top_level(src)
assert not again, f"아직 남은 안 쓰는 이름: {again}"


# ── 3. 꾸밈 규칙 · 꾸밈 설명 글 ──────────────────────────────────────────────────────
root = css_dead.ROOT
corpus_files = [p for p in root.glob("*.py") if not p.name.startswith(("test_", "conftest"))]
corpus_files += [p for p in (root / "pages").glob("*.py") if p.name not in ("2_자비스3.py", "6_자비스6_미국테마.py", OUT.name)]
parts = []
for p in corpus_files:
    t = css_dead.strip_py_comments(p.read_text(encoding="utf-8"))
    parts.append(re.sub(r"/\*.*?\*/", " ", t, flags=re.S))
parts.append(re.sub(r"/\*.*?\*/", " ", css_dead.strip_py_comments(src), flags=re.S))
prod = css_dead.Produced("\n".join(parts))
report = []
before = len(src)
src, n_css = css_dead.process_source(src, prod, report)
kinds = {}
for r in report:
    kinds.setdefault(r[0], [0, 0])
    kinds[r[0]][0] += 1
    kinds[r[0]][1] += r[2]
log.append(f"꾸밈 글자 덩어리 {n_css}개 고침 · {before}→{len(src)}자 · " +
           " · ".join(f"{k} {c}개 {s}자" for k, (c, s) in kinds.items()))
for r in report:
    if r[0] in ("rule", "sel", "at-empty"):
        log.append(f"   꾸밈 뺌 [{r[0]}] {r[1]} {r[3]!r}")


# ── 4. 움직임 코드(자바스크립트) 안의 설명 글 ───────────────────────────────────────────
JS_NAMES = ("_SWIPE_OUTER_JS", "_ZOOM_CLONE_JS", "_ST5_WATCH", "_J3B_POP_CLOSE")


def strip_js_comments(js: str) -> str:
    out = []
    for line in js.split("\n"):
        s = line.strip()
        if s.startswith("//"):
            continue
        m = re.match(r"^(.*?\S)\s+//\s.*$", line)
        if m and m.group(1).count("'") % 2 == 0 and m.group(1).count('"') % 2 == 0 and "/" not in m.group(1).replace("//", ""):
            line = m.group(1)
        line = re.sub(r"\s*/\*[^*]*\*/\s*", " ", line) if "/*" in line and "*/" in line else line
        out.append(line.rstrip())
    return "\n".join(l for l in out if l.strip())


def js_ok(js: str) -> bool:
    r = subprocess.run(["node", "-e", "new Function(require('fs').readFileSync(0,'utf8'))"],
                       input=js.encode("utf-8"), capture_output=True)
    return r.returncode == 0


tree = ast.parse(src)
edits = []
for node in tree.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
            and node.targets[0].id in JS_NAMES and isinstance(node.value, ast.Constant):
        js = node.value.value
        new = strip_js_comments(js)
        assert js_ok(js), node.targets[0].id + " 원본이 안 읽힌다"
        assert js_ok(new), node.targets[0].id + " 고친 것이 안 읽힌다"
        seg_lines = src.splitlines(keepends=True)
        edits.append((node.value.lineno, node.value.end_lineno, node.targets[0].id, js, new))
for a, b, name, js, new in sorted(edits, reverse=True):
    seg = src.splitlines(keepends=True)
    old_text = "".join(seg[a - 1:b])
    head = old_text[:old_text.index('"""') + 3]
    tail = old_text[old_text.rindex('"""'):]
    body = new.replace("\\", "\\\\")
    assert '"""' not in body
    literal_check = ast.literal_eval('"""' + body + '"""')
    assert literal_check == new
    seg[a - 1:b] = [head + body + tail]
    src = "".join(seg)
    log.append(f"움직임 코드 {name}: {len(js)}→{len(new)}자")


# ── 5. 안 쓰는 가져오기(import) ───────────────────────────────────────────────────────
tree = ast.parse(src)
used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
    n.value.id for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
unused = []
for node in tree.body:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        for alias in node.names:
            nm = (alias.asname or alias.name).split(".")[0]
            if nm not in used and nm not in ("annotations",):
                unused.append((node.lineno, nm))
log.append(f"안 쓰는 가져오기: {unused}")
# altair 는 이 화면에서 한 번도 안 쓴다(그림은 모두 svg 글자로 그린다) — 가져오기만 뺀다.
if [nm for _ln, nm in unused] == ["alt"]:
    src = must_replace(src, "import altair as alt\n", "", 1)
else:
    assert not unused, unused

compile(src, str(OUT), "exec")
OUT.write_text(src, encoding="utf-8")
print("\n".join(log))
print(f"원본 {len(SRC.read_text(encoding='utf-8'))}자 · {SRC.read_text(encoding='utf-8').count(chr(10))}줄 → "
      f"자비스11 {len(src)}자 · {src.count(chr(10))}줄")

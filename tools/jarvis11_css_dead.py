"""화면 어디에도 걸릴 수 없는 꾸밈 규칙을 찾는다(그리고 원하면 지운다) — tools/build_jarvis11.py 가 쓴다.

걸릴 수 없다 = 그 규칙이 가리키는 이름(.이름 · #이름 · st-key-이름)을 **코드 어디서도 만들지
않는다**. 만드는 곳은 HTML 의 class='…' · 스트림릿 key='…' · 자바스크립트 classList.add('…') 따위다.
아주 조심스럽게 센다 — 조금이라도 만들 수 있으면 살린다.
"""
from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STREAMLIT_CLASS = re.compile(
    r"^(st[A-Z]\w*|st-emotion-cache-\w+|e[a-z0-9]{4,}\d+|block-container|element-container|"
    r"appview-container|main|streamlit-\w+|react-aria-\w+|withScreencast|stApp\w*)$")


def strip_py_comments(text: str) -> str:
    """주석 자리만 빈칸으로 바꾼다(글자 모양은 그대로 — f글자의 앞부분이 붙어 있어야 한다)."""
    try:
        lines = text.splitlines(keepends=True)
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                r, c = tok.start
                line = lines[r - 1]
                lines[r - 1] = line[:c] + " " * (len(tok.string)) + line[c + len(tok.string):]
        return "".join(lines)
    except Exception:
        return text


def corpus_text(extra_files=()) -> str:
    parts = []
    files = [p for p in ROOT.glob("*.py") if not p.name.startswith(("test_", "conftest"))]
    files += list((ROOT / "pages").glob("*.py"))
    files += [Path(p) for p in extra_files]
    for p in files:
        try:
            t = p.read_text(encoding="utf-8")
        except Exception:
            continue
        t = strip_py_comments(t)
        t = re.sub(r"/\*.*?\*/", " ", t, flags=re.S)
        parts.append(t)
    return "\n".join(parts)


class Produced:
    def __init__(self, corpus: str):
        self.corpus = corpus
        self.cache: dict[str, bool] = {}
        # 이어 붙여 만드는 이름의 앞부분 — 'j3-band-' + x · f"j3-band-{x}" · "st-key-" 꼴
        self.prefixes = set(m.group(1) for m in re.finditer(r"([A-Za-z][\w-]{2,}[-_])(?=\{|['\"]\s*\+|['\"]\s*%)", corpus))
        # "jarvis-anchor-" 처럼 이음표로 끝나는 글자 하나 — 뒤에 무엇을 붙여 쓰는 앞부분이다
        self.prefixes |= set(m.group(1) for m in re.finditer(r"['\"]([A-Za-z][\w-]{2,}[-_])['\"]", corpus))

    def cls(self, name: str) -> bool:
        if STREAMLIT_CLASS.match(name):
            return True
        # 자료에서 만드는 이름(종목 기호 tsla 따위) — 짧고 이음표 없는 이름은 살린다
        if re.fullmatch(r"[a-z0-9]{1,6}", name):
            return True
        if name in self.cache:
            return self.cache[name]
        ok = re.search(r"(?<![.#\w-])" + re.escape(name) + r"(?![\w-])", self.corpus) is not None
        if not ok:
            ok = any(name.startswith(p) and len(p) >= 4 for p in self.prefixes)
        self.cache[name] = ok
        return ok

    def key(self, name: str, prefix_only: bool) -> bool:
        """st-key-<name> — 스트림릿 key 로 만든다. key 글자가 name 으로 시작하면 산다."""
        ck = ("key", name, prefix_only)
        if ck in self.cache:
            return self.cache[ck]
        if not name:
            ok = True
        else:
            ok = re.search(r"['\"]" + re.escape(name), self.corpus) is not None
            if not ok:
                # f"j3_stock_choice_{x}" 꼴: name 이 그 앞부분으로 시작하면 산다
                ok = any(name.startswith(p) and len(p) >= 4 for p in self.prefixes)
            if not ok:
                # key 를 이어 붙여 만드는 곳(f"close_{key}") — name 의 뒷부분이 key 로 있으면 산다
                for cut in ("close_", "btn_", "open_"):
                    if name.startswith(cut) and re.search(r"['\"]" + re.escape(name[len(cut):]), self.corpus):
                        ok = True
        self.cache[ck] = ok
        return ok


# ── 꾸밈 글자 나누기 ─────────────────────────────────────────────────────────
def split_css(text: str):
    """[(kind, start, end, extra)] — kind: comment | rule(sel_start, sel_end, body_start) | at(...) | other."""
    items = []
    i, n = 0, len(text)
    while i < n:
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            items.append(("comment", i, j, None))
            i = j
            continue
        if text[i].isspace():
            i += 1
            continue
        # 규칙 하나: 선택자 { … } — 문자열·괄호 안의 { 는 건너뛴다
        j = i
        depth_par = 0
        quote = None
        while j < n:
            c = text[j]
            if quote:
                if c == quote:
                    quote = None
            elif c in "'\"":
                quote = c
            elif c == "(":
                depth_par += 1
            elif c == ")":
                depth_par -= 1
            elif c == "{" and depth_par == 0:
                break
            elif c == "}" and depth_par == 0:
                break
            elif c == ";" and depth_par == 0 and text[i] == "@":
                break
            j += 1
        if j >= n or text[j] == "}":
            items.append(("other", i, min(j + 1, n), None))
            i = j + 1
            continue
        if text[j] == ";":
            items.append(("other", i, j + 1, None))
            i = j + 1
            continue
        # 짝 맞는 } 찾기
        k = j + 1
        depth = 1
        quote = None
        while k < n and depth:
            c = text[k]
            if quote:
                if c == quote:
                    quote = None
            elif text.startswith("/*", k):
                e = text.find("*/", k + 2)
                k = n if e < 0 else e + 2
                continue
            elif c in "'\"":
                quote = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            k += 1
        head = text[i:j]
        kind = "at" if head.lstrip().startswith("@") else "rule"
        items.append((kind, i, k, (i, j, j + 1)))
        i = k
    return items


def split_selectors(sel: str):
    out, depth, cur, quote = [], 0, "", None
    for c in sel:
        if quote:
            cur += c
            if c == quote:
                quote = None
            continue
        if c in "'\"":
            quote = c
        elif c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        if c == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += c
    out.append(cur)
    return out


def remove_not_groups(sel: str) -> str:
    # :not( … ) 안의 이름은 없어도 규칙이 걸린다 → 따지지 않는다
    out, i = "", 0
    while i < len(sel):
        m = re.compile(r":not\(").match(sel, i)
        if m:
            depth, j = 1, m.end()
            while j < len(sel) and depth:
                if sel[j] == "(":
                    depth += 1
                elif sel[j] == ")":
                    depth -= 1
                j += 1
            i = j
            continue
        out += sel[i]
        i += 1
    return out


def selector_dead(sel: str, prod: Produced):
    s = remove_not_groups(sel)
    s = re.sub(r"(['\"]).*?\1", lambda m: m.group(0), s)
    reasons = []
    # [class*='st-key-…'] · [class^=…] · [class~=…]
    for m in re.finditer(r"\[class([*^~|$]?)=\s*(['\"]?)([^'\"\]]+)\2\s*\]", s):
        op, val = m.group(1), m.group(3).strip()
        if val.startswith("st-key-"):
            if not prod.key(val[len("st-key-"):], prefix_only=op in "*^"):
                reasons.append("key:" + val)
        elif op == "" or op == "~":
            if not prod.cls(val):
                reasons.append("cls:" + val)
    s2 = re.sub(r"\[[^\]]*\]", " ", s)
    for m in re.finditer(r"\.(-?[A-Za-z_][\w-]*)", s2):
        name = m.group(1)
        if name.startswith("st-key-"):
            if not prod.key(name[len("st-key-"):], prefix_only=False):
                reasons.append("key:" + name)
        elif not prod.cls(name):
            reasons.append("cls:" + name)
    for m in re.finditer(r"#([A-Za-z_][\w-]*)", s2):
        name = m.group(1)
        if re.fullmatch(r"[0-9a-fA-F]{3,8}", name):
            continue
        if not prod.cls(name):
            reasons.append("id:" + name)
    return reasons


def clean_css(text: str, prod: Produced, report: list, where: str):
    """주석·걸릴 수 없는 선택자를 뺀 새 글자를 돌려준다."""
    items = split_css(text)
    out = []
    last = 0
    for kind, a, b, extra in items:
        out.append(text[last:a])
        last = b
        piece = text[a:b]
        if kind == "comment":
            report.append(("comment", where, len(piece), piece[:50]))
            continue
        if kind == "rule":
            i, j, body = extra
            sels = split_selectors(text[i:j])
            keep, dead = [], []
            for sel in sels:
                r = selector_dead(sel, prod)
                (dead if r else keep).append((sel, r))
            if not keep:
                report.append(("rule", where, len(piece), text[i:j].strip()[:80], [r for _s, r in dead]))
                continue
            if dead:
                for sel, r in dead:
                    report.append(("sel", where, len(sel) + 1, sel.strip()[:80], r))
                new_sel = ",".join(s for s, _r in keep)
                # 선택자 앞 줄바꿈 모양은 첫 선택자 것을 둔다
                piece = new_sel + text[j:b]
            # 몸통 안 주석도 뺀다
            piece = re.sub(r"/\*.*?\*/", "", piece, flags=re.S)
            out.append(piece)
            continue
        if kind == "at":
            i, j, body = extra
            head = text[i:j]
            if head.strip().startswith(("@media", "@supports", "@container", "@layer")):
                inner = text[body:b - 1]
                new_inner = clean_css(inner, prod, report, where + " " + head.strip()[:30])
                if not new_inner.strip():
                    report.append(("at-empty", where, len(piece), head.strip()[:60]))
                    continue
                out.append(head + "{" + new_inner + "}")
                continue
            out.append(re.sub(r"/\*.*?\*/", "", piece, flags=re.S))
            continue
        out.append(piece)
    out.append(text[last:])
    return "".join(out)


def css_regions(value: str):
    """글자 안에서 꾸밈 부분의 [시작, 끝) — <style>…</style> 이 있으면 그 안, 없고 꾸밈만이면 통째로."""
    regs = []
    for m in re.finditer(r"<style[^>]*>(.*?)</style>", value, flags=re.S):
        regs.append((m.start(1), m.end(1)))
    if regs:
        return regs
    if "{" in value and re.search(r"[\w\]\)*-]\s*\{[^{}]*:[^{}]*\}", value) and "<" not in value and "function" not in value:
        return [(0, len(value))]
    return []


def drop_blank_lines(s: str) -> str:
    return "\n".join(line for line in s.split("\n") if line.strip()) if "\n" in s else s


def process_source(src: str, prod: Produced, report: list, only_lines=None):
    """파일 글자에서 꾸밈 든 보통 글자를 찾아 고친 새 파일 글자를 돌려준다."""
    tree = ast.parse(src)
    line_starts = [0]
    for line in src.splitlines(keepends=True):
        line_starts.append(line_starts[-1] + len(line))

    def off(lineno, col):
        # col 은 UTF-8 바이트 기준
        line = src[line_starts[lineno - 1]:line_starts[lineno]]
        return line_starts[lineno - 1] + len(line.encode("utf-8")[:col].decode("utf-8", errors="ignore"))

    edits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if only_lines and node.lineno not in only_lines:
            continue
        value = node.value
        regs = css_regions(value)
        if not regs:
            continue
        new = value
        for a, b in reversed(regs):
            cleaned = clean_css(value[a:b], prod, report, f"{node.lineno}행")
            cleaned = drop_blank_lines(cleaned)
            new = new[:a] + cleaned + new[b:]
        if new == value:
            continue
        a = off(node.lineno, node.col_offset)
        b = off(node.end_lineno, node.end_col_offset)
        old_src = src[a:b]
        # 원래 글자가 r 접두인지, 따옴표 모양
        prefix = re.match(r"^[rRbBuU]*", old_src).group(0)
        if "b" in prefix.lower():
            continue
        body = new
        if "r" not in prefix.lower():
            body = body.replace("\\", "\\\\")
        if '"""' in body or body.endswith('"'):
            continue
        literal = prefix + '"""' + body + '"""'
        assert ast.literal_eval(literal) == new, node.lineno
        edits.append((a, b, literal))
    for a, b, lit in sorted(edits, reverse=True):
        src = src[:a] + lit + src[b:]
    return src, len(edits)


if __name__ == "__main__":
    import sys
    page = Path(sys.argv[1])
    src = page.read_text(encoding="utf-8")
    prod = Produced(corpus_text())
    report = []
    new_src, n = process_source(src, prod, report)
    kinds = {}
    for r in report:
        kinds.setdefault(r[0], [0, 0])
        kinds[r[0]][0] += 1
        kinds[r[0]][1] += r[2]
    print("고친 글자 덩어리", n, "· 파일", len(src), "→", len(new_src), "자")
    for k, (c, s) in kinds.items():
        print(f"  {k}: {c}개 · {s}자")
    if "-v" in sys.argv:
        for r in report:
            if r[0] in ("rule", "sel", "at-empty"):
                print("   ", r[0], r[1], r[3], r[4] if len(r) > 4 else "")
    if "-w" in sys.argv:
        out = Path(sys.argv[sys.argv.index("-w") + 1])
        out.write_text(new_src, encoding="utf-8")
        print("썼다:", out)

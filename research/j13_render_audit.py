# -*- coding: utf-8 -*-
"""자비스13 화면 글이 스트림릿에서 깨지는 곳을 도구로 찾는다 (2026-11-05 상하님 「너 사기쳤네」 · 「다른 부분도 검토하고 똑똑하게」).

사람 눈으로 하나씩 찾지 않고, 화면 글을 **스트림릿이 읽는 규칙 그대로** 읽어 본다.
  · 물결표 둘(「40~60% … 3~5일」) — 스트림릿이 그 사이 글자에 취소선을 긋는다(2026-11-05 실제로 그려 확인).
  · 꾸밈(<style>) 뒤에 붙인 글 — 한 번에 내보내면 스트림릿이 상자를 통째로 버린다(세부사항 상자 셋 0개 사건).
  · 들여 쓴 줄 — 네 칸 이상 들여 쓰면 코드 상자(회색 글)로 나온다.
  · 꾸밈 글(.이름{…}) · 태그(<b>)가 글자로 새는 것 — HTML 을 못 쓰는 자리(알림 상자 · 단추 이름 등)에 태그를 넣은 것.

markdown_problems() 는 시험(test_jarvis13_render_audit)이 같이 쓴다. 바깥 꾸러미 없이 CommonMark 의 블록 규칙만 옮겼다.
이 파일을 직접 돌리면 여러 화면 상태(시장분석 · 세부사항 · 상승장 · 급락 · 관심종목 · 매수 기록 · 판정 기준 · 성적표)를
시험 자료로 띄워 글을 모으고 찾은 것을 찍는다.
"""
from __future__ import annotations

import re
import sys
import textwrap
import unicodedata

_TYPE1_OPEN = re.compile(r"^ {0,3}<(script|pre|style|textarea)(?=[\s>]|$)", re.I)
_TYPE1_CLOSE = re.compile(r"</(script|pre|style|textarea)>", re.I)
_BLOCK_TAGS = ("address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|"
               "dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h1|h2|h3|h4|h5|h6|head|header|hr|html|iframe|"
               "legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|"
               "tbody|td|tfoot|th|thead|title|tr|track|ul")
_TYPE6 = re.compile(rf"^ {{0,3}}</?({_BLOCK_TAGS})(?=[\s/>]|$)", re.I)
_ATTR = r"""(?:\s+[A-Za-z_:][\w.:-]*(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?)"""
_TYPE7 = re.compile(rf"^ {{0,3}}(?:<[A-Za-z][A-Za-z0-9-]*{_ATTR}*\s*/?>|</[A-Za-z][A-Za-z0-9-]*\s*>)\s*$")
_TAG = re.compile(r"<[^<>]+>")
_CSS = re.compile(r"[.#]?[A-Za-z_][\w-]*\s*\{[^{}]*:[^{}]*\}|!important")
_LITERAL_TAG = re.compile(r"</?(div|span|style|b|br|table|td|tr|th|details|summary|a|p|u|i|small|strong|em|img|svg)\b[^>]*>",
                          re.I)


def _punct(ch: str) -> bool:
    return bool(ch) and unicodedata.category(ch)[0] in "PS"


def _tilde_strikes(text: str) -> list[str]:
    """GFM 취소선(물결표 하나 또는 둘)으로 묶이는 글 조각. 스트림릿은 「~」 하나로도 긋는다."""
    plain = _TAG.sub(" ", text.replace("\\~", ""))
    runs = []
    index = 0
    while index < len(plain):
        if plain[index] == "~":
            end = index
            while end < len(plain) and plain[end] == "~":
                end += 1
            prev = plain[index - 1] if index > 0 else ""
            nxt = plain[end] if end < len(plain) else ""
            left = bool(nxt) and not nxt.isspace() and (not _punct(nxt) or not prev or prev.isspace() or _punct(prev))
            right = bool(prev) and not prev.isspace() and (not _punct(prev) or not nxt or nxt.isspace() or _punct(nxt))
            runs.append((index, end - index, left, right))
            index = end
        else:
            index += 1
    found = []
    used = set()
    for i, (start, size, can_open, _close) in enumerate(runs):
        if not can_open or i in used or size > 2:
            continue
        for j in range(i + 1, len(runs)):
            other, other_size, _open, can_close = runs[j]
            if can_close and other_size == size and j not in used:
                found.append(plain[start:other + other_size].strip())
                used.update({i, j})
                break
    return found


def _dollar_math(text: str) -> str | None:
    """달러 기호 둘(「$10.75 그리고 $8.90」) — 스트림릿이 그 사이를 수식으로 바꿔 회색 상자로 낸다(2026-11-05 실제로 그려 확인)."""
    plain = _TAG.sub(" ", text.replace("\\$", ""))
    spots = [i for i, ch in enumerate(plain) if ch == "$"]
    return plain[spots[0]:spots[1] + 1] if len(spots) >= 2 else None


def _check_paragraph(chunk: str, problems: list[str]) -> None:
    for strike in _tilde_strikes(chunk):
        problems.append(f"물결표 취소선: 「{strike[:60]}」")
    math = _dollar_math(chunk)
    if math:
        problems.append(f"달러 기호 둘이 수식 상자로 바뀜: 「{math[:60]}」")
    plain = _TAG.sub(" ", chunk)
    if _CSS.search(plain):
        problems.append(f"꾸밈 글이 글자로 샘: 「{_CSS.search(plain).group(0)[:60]}」")
    if re.search(r"<style", chunk, re.I):
        problems.append("문단 속 <style> — 꾸밈이 안 먹고 뒤 글이 깨짐")


def _check_html_block(block: list[str], problems: list[str]) -> None:
    return None


_STYLE_OPEN = re.compile(r"<style\b", re.I)
_STYLE_CLOSE = re.compile(r"</style\s*>", re.I)


def _style_problems(text: str) -> list[str]:
    """꾸밈 덩이(<style>)는 **새 줄 맨 앞에서** 열고 닫혀야 한다. 줄 가운데서 열리면 그 줄로 HTML 덩이가 끝나 뒤 줄들이 문단 글로
    읽힌다 — 세부사항 상자 0개 사건(2026-11-05)이 이 꼴이었다. 꾸밈 안의 글(주석 속 「<style …>」)은 건너뛴다."""
    found, pos = [], 0
    while True:
        opened = _STYLE_OPEN.search(text, pos)
        if not opened:
            return found
        line_start = text.rfind("\n", 0, opened.start()) + 1
        closed = _STYLE_CLOSE.search(text, opened.end())
        if not closed:
            found.append("꾸밈(<style>)이 안 닫힘")
            return found
        # 줄 가운데서 열리고 **다른 줄에서** 닫히면 위험하다 — 여는 줄에서 HTML 덩이가 끝나 그 사이 줄들이 문단 글로 읽힌다.
        # (같은 줄 안에서 열고 닫으면 그 줄 전체가 HTML 이라 괜찮다.)
        if text[line_start:opened.start()].strip() and "\n" in text[opened.end():closed.start()]:
            before = " ".join(text[max(line_start, opened.start() - 40):opened.start()].split())
            found.append(f"꾸밈(<style>)이 줄 가운데서 열려 다음 줄에서 닫힘(앞 글 「…{before[-30:]}」) — 뒤 글이 문단으로 읽혀 깨질 수 있음")
        pos = closed.end()


def markdown_problems(body: str, *, allow_html: bool = True) -> list[str]:
    """스트림릿 st.markdown 이 이 글을 어떻게 읽는지 블록 규칙대로 따라가며 깨지는 곳을 적는다(없으면 빈 목록)."""
    text = textwrap.dedent(str(body)).strip()          # 스트림릿 clean_text 와 같다
    problems: list[str] = []
    if not allow_html:
        literal = _LITERAL_TAG.search(text)
        if literal:
            problems.append(f"HTML 을 못 쓰는 자리에 태그가 글자로 나옴: 「{literal.group(0)[:40]}」")
        for strike in _tilde_strikes(text):
            problems.append(f"물결표 취소선: 「{strike[:60]}」")
        math = _dollar_math(text)
        if math:
            problems.append(f"달러 기호 둘이 수식 상자로 바뀜: 「{math[:60]}」")
        return problems
    problems.extend(_style_problems(text))
    state, block, para = None, [], []

    def end_para():
        if para:
            _check_paragraph("\n".join(para), problems)
            para.clear()

    for line in text.split("\n"):
        if state == "html1":
            block.append(line)
            if _TYPE1_CLOSE.search(line):
                _check_html_block(block, problems)
                state, block = None, []
            continue
        if state == "html6":
            if not line.strip():
                _check_html_block(block, problems)
                state, block = None, []
            else:
                block.append(line)
            continue
        if not line.strip():
            if state == "para":
                end_para()
                state = None
            continue
        opened = _TYPE1_OPEN.match(line)
        if opened:
            end_para()
            block = [line]
            if _TYPE1_CLOSE.search(line[opened.end():]):
                _check_html_block(block, problems)
                state, block = None, []
            else:
                state = "html1"
            continue
        if _TYPE6.match(line) or (state != "para" and _TYPE7.match(line)):
            end_para()
            state, block = "html6", [line]
            continue
        if state != "para" and re.match(r"^(?: {4,}|\t)", line):
            problems.append(f"네 칸 들여 쓴 줄이 코드 상자로 나옴: 「{line.strip()[:60]}」")
            continue
        para.append(line)
        state = "para"
    end_para()
    if block:
        _check_html_block(block, problems)
    return problems


# ── 화면 상태를 띄워 글 모으기(직접 돌릴 때) ─────────────────────────────────────────────

def _texts(app) -> list[tuple[str, str, bool]]:
    """(종류, 글, HTML 허용) — 스트림릿이 마크다운으로 읽는 자리만."""
    out = []
    for element in app.markdown:
        proto = element.proto
        out.append(("캡션" if element.is_caption else "글", proto.body, bool(proto.allow_html)))
    for name, kind in (("info", "알림"), ("warning", "주의"), ("success", "됨"), ("error", "오류")):
        for element in getattr(app, name):
            out.append((kind, element.proto.body, False))
    for name, kind in (("button", "단추"), ("checkbox", "고르기"), ("toggle", "켜기"), ("radio", "고르기"),
                       ("text_input", "칸"), ("selectbox", "고르기"), ("metric", "숫자")):
        for element in getattr(app, name):
            label = getattr(element.proto, "label", "")
            if label:
                out.append((kind, label, False))
            if name == "radio":
                for option in element.options:
                    out.append(("고르기 항목", str(option), False))
    for element in app.expander:
        out.append(("접기", element.proto.label, False))
    for name, kind in (("subheader", "소제목"), ("header", "제목"), ("title", "제목")):
        for element in getattr(app, name):
            out.append((kind, element.proto.body, False))
    return out


def main() -> int:
    import os
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    os.chdir(root)
    import test_jarvis13_render_audit as audit

    found = 0
    for state, app in audit.run_states():
        for kind, text, allow_html in _texts(app):
            for problem in markdown_problems(text, allow_html=allow_html):
                found += 1
                snippet = " ".join(str(text).split())[:110]
                print(f"[{state}] {kind} · {problem}\n      글: {snippet}", flush=True)
    print(f"\n찾은 것 {found}건", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())


def newline_styles(text: str) -> str:
    """위험한 꾸밈(줄 가운데서 열려 다른 줄에서 닫히는 <style>) 앞에 줄바꿈을 넣은 글 — 고치기 전후 그림을 견줄 때 쓴다."""
    out, pos = [], 0
    while True:
        opened = _STYLE_OPEN.search(text, pos)
        if not opened:
            out.append(text[pos:])
            return "".join(out)
        closed = _STYLE_CLOSE.search(text, opened.end())
        end = closed.end() if closed else len(text)
        line_start = text.rfind("\n", 0, opened.start()) + 1
        out.append(text[pos:opened.start()])
        if closed and text[line_start:opened.start()].strip() and "\n" in text[opened.end():closed.start()]:
            out.append("\n")
        out.append(text[opened.start():end])
        pos = end

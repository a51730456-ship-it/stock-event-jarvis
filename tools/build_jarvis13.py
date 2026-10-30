"""자비스13(한국테마)을 자비스4 에서 한 번 베낀다 (2026-10-30 상하님 「둘 다 해라」 · 「자비스4 와 자비스12 둘 다 장점을 베낌」).

만드는 것
  pages/12_자비스13.py      ← pages/3_자비스4.py
  jarvis13_picklist_ui.py   ← jarvis12_picklist_ui.py (날짜별 목록 · 원본 picklist_ui.render + 넘겨받는 셋 · 이름만 j13)
  jarvis13_back_nav.py      ← back_nav.py (뒤로가기 · 보관함 이름만 j13)
  jarvis13_scroll_to.py     ← scroll_to.py (스크롤 · 보관함 이름만 j13)

바꾸는 것은 셋뿐이다 (값·점수·목록·꾸밈은 그대로)
  ① 화면 이름 — 탭 제목 · 로그인 글 · 몇몇 안내 글의 「자비스4」
  ② 보관함·단추 이름 j4… → j13… (j4_ · j4tbtn_ · j4lbtn_ · j4rbf_ · j4pbf_ · j4top · j4idx_ 와 그로 만든 btn_ · close_ 이름)
     — 자비스12 때(2026-10-23) 이름이 같아 두 화면의 결과가 섞인 사고를 처음부터 막는다.
     **꾸밈 이름(j4-…)은 그대로** — 같이 쓰는 폰 규칙(mobile_ui)이 그 이름을 본다(2026-10-27 j3sc_ 사고와 같은 꼴을 막는다).
     계산 파일 이름(j4data · j4store)과 판 번호(_REQUIRED_J4_…)도 그대로 — 같은 계산 파일을 부른다.
  ③ 화면 움직임을 기억하는 공용 파일 셋(날짜별 목록 그리기 · 뒤로가기 · 스크롤)을 j13 전용 사본으로.

**이 도구는 한 번만 돌린다** — 다시 돌리면 자비스13 에서 고친 것이 사라진다(자비스12 의 build_jarvis12 와 같은 규칙).
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _swap(text: str, old: str, new: str, count: int = 1) -> str:
    found = text.count(old)
    if found != count:
        raise SystemExit(f"찾는 글이 {count}번이 아니라 {found}번이다: {old[:60]!r}")
    return text.replace(old, new)


# 보관함·단추 이름 — 앞이 영문자·숫자가 아닌 자리의 j4 + 아래 꼬리
_NAME = re.compile(r"(?<![A-Za-z0-9])j4(?=(?:_|tbtn_|lbtn_|rbf_|pbf_|top|idx_))")


def build_page() -> str:
    src = (ROOT / "pages" / "3_자비스4.py").read_text(encoding="utf-8")
    text = src
    # ① 화면 이름
    text = _swap(text, '"""자비스4 — 한국 테마 레이더와 실제 매수 기록 페이지.',
                 '"""자비스13 — 한국테마. 2026-10-30 자비스4 를 그대로 베끼고(tools/build_jarvis13.py) 자비스12 의 좋은 점을 옮겨 오는 화면.\n\n'
                 '아래는 자비스4 의 설명 그대로다.\n\n자비스4 — 한국 테마 레이더와 실제 매수 기록 페이지.')
    text = _swap(text, 'st.set_page_config(page_title="자비스4 — 한국 테마 레이더", layout="wide")',
                 'st.set_page_config(page_title="자비스13 — 한국테마", layout="wide")')
    text = _swap(text, 'st.markdown("## 자비스4 — 한국 테마 레이더")', 'st.markdown("## 자비스13 — 한국테마")')
    text = _swap(text, '"자비스4 로그인"', '"자비스13 로그인"')
    text = _swap(text, '"📈 자비스4에만 있는 승률 보완 장치 9가지 (미국테마에 없는 것)"',
                 '"📈 한국테마에만 있는 승률 보완 장치 9가지 (미국테마에 없는 것)"')
    text = _swap(text, '"아직 저장된 자비스4 매수 기록이 없습니다."', '"아직 저장된 한국테마 매수 기록이 없습니다."')
    text = _swap(text, 'st.error(f"자비스4 기록 테이블 준비 실패:', 'st.error(f"한국테마 기록 테이블 준비 실패:')
    text = _swap(text, '        "자비스4 보기",', '        "자비스13 보기",')
    # ② 보관함·단추 이름
    before = len(_NAME.findall(text))
    text = _NAME.sub("j13", text)
    if before < 250:
        raise SystemExit(f"바꾼 이름이 너무 적다({before}) — 자비스4 파일이 바뀌었는지 본다")
    # ③ 공용 파일 셋을 전용 사본으로 (불러오는 이름은 그대로 두어 아래 코드를 안 건드린다)
    text = _swap(text, "\nimport picklist_ui\n",
                 "\nimport picklist_ui  # 목록 자동 저장(autosave)은 자비스4 와 같은 함수 — 같은 계산이라 같은 줄을 적는다\n"
                 "import jarvis13_picklist_ui  # 목록 그리기는 j13 이름의 사본(자비스4 와 보관함 따로)\n")
    text = _swap(text, 'picklist_ui.render(st, "KR", toggle=_section_toggle, close=_section_close)',
                 'jarvis13_picklist_ui.render(st, "KR", toggle=_section_toggle, close=_section_close)', count=2)
    text = _swap(text, "\nimport scroll_to\n", "\nimport jarvis13_scroll_to as scroll_to  # j13 이름의 사본(자비스4 와 보관함 따로)\n")
    text = _swap(text, "import back_nav  # 폰·태블릿 뒤로가기",
                 "import jarvis13_back_nav as back_nav  # j13 이름의 사본(자비스4 와 보관함 따로) · 폰·태블릿 뒤로가기")
    # 꾸밈 이름(j4-…)은 일부러 남긴다 — 「j4」 뒤에 「-」 가 오는 것은 세지 않는다
    left = sorted(set(re.findall(r"(?<![A-Za-z0-9])(j4[A-Za-z0-9_]*)(?![-A-Za-z0-9_])", text)) - {"j4data", "j4store"})
    if left:
        raise SystemExit(f"j4 이름이 남았다: {left}")
    return text


def build_picklist() -> str:
    src = (ROOT / "jarvis12_picklist_ui.py").read_text(encoding="utf-8")
    head_end = src.index('"""', 3) + 3
    doc = ('"""자비스13 전용 날짜별 목록 화면 — jarvis12_picklist_ui.py 를 2026-10-30 그대로 베끼고 이름만 j13 (tools/build_jarvis13.py).\n\n'
           '자비스13 은 넘겨받는 셋(rows_view · quick_prices · kind_note)을 아직 안 넘긴다 — 그러면 원본 picklist_ui.render 와\n'
           '똑같이 돈다(보관함 이름만 j13). 자비스4 · 자비스12 와 보관함이 섞이지 않는다.\n\n'
           '아래는 베낀 파일의 설명 그대로다.\n\n' + src[3:head_end - 3].lstrip() + '"""')
    text = doc + src[head_end:]
    text = re.sub(r"(?<![A-Za-z0-9])j12_", "j13_", text)
    text = text.replace("__jarvis12NoKeyboard", "__jarvis13NoKeyboard")
    text = text.replace("_REQUIRED_J12_PICKLIST_REVISION", "_REQUIRED_J13_PICKLIST_REVISION")
    # 설명 글 속 이름도 이 사본 것으로(하는 일은 그대로)
    for a, b in (("이름만 j12", "이름만 j13"), ("담는 자리만 j12", "담는 자리만 j13"),
                 ("이름에 j12 를 붙인다", "이름에 j13 을 붙인다"), ("날짜 칸 이름이 j12 라", "날짜 칸 이름이 j13 이라"),
                 ("j12 로 바꾼 사본", "j13 으로 바꾼 사본"),
                 ("자비스12 의 _REQUIRED_J13_PICKLIST_REVISION", "자비스13 의 _REQUIRED_J13_PICKLIST_REVISION"),
                 ("# 자비스12 — 값 담는 칸 이름을 j13_ 로 따로 둔다.", "# 자비스12·13 — 값 담는 칸 이름을 화면마다 따로 둔다(여기는 j13_).")):
        text = text.replace(a, b)
    if re.search(r"(?<![A-Za-z0-9])j12[_A-Za-z]", text.split('"""', 2)[2]):
        raise SystemExit("날짜별 목록 사본에 j12 이름이 남았다")
    return text


def build_copy(name: str, pairs: list[tuple[str, str]], note: str) -> str:
    src = (ROOT / f"{name}.py").read_text(encoding="utf-8")
    text = src
    for old, new in pairs:
        text = _swap(text, old, new)
    first = text.index('"""') + 3
    return text[:first] + f"자비스13 전용 사본 — {name}.py 를 2026-10-30 그대로 베끼고 {note} (tools/build_jarvis13.py).\n\n" + text[first:]


def main() -> int:
    targets = {
        ROOT / "pages" / "12_자비스13.py": build_page(),
        ROOT / "jarvis13_picklist_ui.py": build_picklist(),
        ROOT / "jarvis13_back_nav.py": build_copy("back_nav", [('_STACK = "_backnav_open"', '_STACK = "_j13_backnav_open"')],
                                                  "보관함 이름만 j13"),
        ROOT / "jarvis13_scroll_to.py": build_copy("scroll_to", [('REQUEST_KEY = "jarvis_scroll_target"', 'REQUEST_KEY = "j13_scroll_target"'),
                                                                  ('COUNTER_KEY = "jarvis_scroll_seq"', 'COUNTER_KEY = "j13_scroll_seq"')],
                                                   "보관함 이름만 j13"),
    }
    if any(path.exists() for path in targets) and "--force" not in sys.argv:
        raise SystemExit("이미 만든 파일이 있다 — 다시 돌리면 자비스13 에서 고친 것이 사라진다(돌리지 않는다)")
    for path, text in targets.items():
        path.write_text(text, encoding="utf-8")
        print(f"만듦 {path.relative_to(ROOT)} · {len(text.splitlines())}줄")
    return 0


if __name__ == "__main__":
    sys.exit(main())

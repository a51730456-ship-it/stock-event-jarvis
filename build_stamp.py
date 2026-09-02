"""이 화면이 **언제 판인지** 맨 밑에 작게 적는다 (2026-09-02 상하님 지시).

상하님 — *"너는 어디서 어디까지 반영을 했는지 안 했는지 몰라서 걱정된다고
했잖아."*

**왜 필요한가.** 폰(온라인)은 깃허브를 보고 저절로 새로 뜨는데, 노트북은
상하님이 받아 오셔야 바뀐다. 그래서 두 화면이 다를 때 ① 제가 안 한 것인지
② 노트북이 아직 안 받아 온 것인지 **상하님이 가릴 방법이 없었다.**
화면 맨 밑에 같은 표시가 있으면 둘을 나란히 놓고 바로 아신다.

**무엇을 적나 — 자료 저장이 아니라 「코드」가 언제 바뀌었나다.**
이 저장소에는 자비스5 수집이 **10분마다** 커밋을 쌓는다. 그 번호를 적으면
노트북과 온라인이 영영 다르게 보여 아무 쓸모가 없다. 그래서 `*.py`를 건드린
**마지막 커밋**만 본다 — 자료만 쌓인 커밋은 세지 않는다.

**시각은 커밋이 가진 시간대 그대로 적는다**(`--date=iso`). 기계마다 바꿔 적으면
(온라인은 UTC, 노트북은 한국시간) 같은 판인데 다른 시각으로 보인다.

**절대 원칙 — 실패해도 아무 일도 일어나지 않아야 한다.** git 이 없거나 막히면
파일 시각으로 물러서고, 그것도 안 되면 「판 모름」이라 적는다. 이 한 줄 때문에
화면이 죽으면 안 된다(쿠키 로그인과 같은 원칙, CLAUDE.md 13번).
"""

from __future__ import annotations

import datetime
import html
import pathlib
import subprocess

# 표시 방식을 바꾸면 이 숫자를 올린다(규칙 11).
MODULE_REVISION = 2026090210

_ROOT = pathlib.Path(__file__).resolve().parent

# 한 판에 한 번만 알아본다. 받아 오면 앱이 다시 뜨므로 그때 새로 읽는다.
_CACHE: dict[str, str] = {}

# 코드가 든 파일만 본다. 자료(data/…)만 바뀐 커밋은 판이 바뀐 것이 아니다.
_CODE_PATHS = ("*.py", "pages/*.py", "*.bat", "*.toml")


def _from_git() -> str | None:
    """`*.py`를 건드린 마지막 커밋. 가장 믿을 만한 값이다."""
    try:
        done = subprocess.run(
            ["git", "-C", str(_ROOT), "log", "-1", "--date=iso",
             "--format=%cd|%h", "--", *_CODE_PATHS],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None
    text = (done.stdout or "").strip()
    if "|" not in text:
        return None
    when, _, short = text.partition("|")
    # '2026-09-02 10:57:31 +0000' → '2026-09-02 10:57'
    stamp = " ".join(when.split()[:2])[:16]
    return f"{stamp} · {short.strip()}" if short.strip() else None


def _from_git_files() -> str | None:
    """git 명령이 안 될 때 `.git` 폴더를 직접 읽는다. 번호만 얻는다."""
    git_dir = _ROOT / ".git"
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    except Exception:
        return None
    if head.startswith("ref:"):
        ref = head.split(" ", 1)[-1].strip()
        sha = ""
        try:
            sha = (git_dir / ref).read_text(encoding="utf-8").strip()
        except Exception:
            try:
                for line in (git_dir / "packed-refs").read_text(
                        encoding="utf-8").splitlines():
                    if line.endswith(" " + ref):
                        sha = line.split(" ", 1)[0].strip()
                        break
            except Exception:
                sha = ""
    else:
        sha = head
    return f"{sha[:7]} (받아 온 판)" if sha else None


def _from_files() -> str:
    """마지막 수단 — 앱 파일이 마지막으로 바뀐 시각. **기계 시간이라 따로 적는다.**"""
    newest = 0.0
    for name in ("app.py", "picklist_ui.py", "jarvis3_data.py"):
        try:
            newest = max(newest, (_ROOT / name).stat().st_mtime)
        except Exception:
            continue
    if not newest:
        return "판 모름"
    when = datetime.datetime.fromtimestamp(newest).strftime("%Y-%m-%d %H:%M")
    return f"{when} (파일 시각)"


def stamp() -> str:
    """화면에 적을 한 마디."""
    if "text" not in _CACHE:
        try:
            _CACHE["text"] = _from_git() or _from_git_files() or _from_files()
        except Exception:
            _CACHE["text"] = "판 모름"
    return _CACHE["text"]


CSS = """
<style>
.jarvis-build { color: #6e7480; font-size: .74rem; text-align: center;
                letter-spacing: .02em; margin: 1.6rem 0 .5rem; }
</style>
"""


def render(st) -> None:
    """화면 **맨 밑**에 한 줄. 값·점수·판정은 하나도 안 건드린다."""
    try:
        st.markdown(
            CSS + f"<div class='jarvis-build'>판 {html.escape(stamp())}</div>",
            unsafe_allow_html=True,
        )
    except Exception:
        pass          # 이 한 줄 때문에 화면이 막히면 안 된다

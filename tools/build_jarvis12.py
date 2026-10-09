"""자비스3 화면 파일을 **그대로** 베껴 자비스12 를 만든다 (2026-10-09 상하님 지시).

    python tools/build_jarvis12.py            (pages/2_자비스3.py → pages/11_자비스12.py)

상하님 — *"미국테마는 예전에 수정을 하니 … 자꾸 되돌리기나 엄한 잘못을 해서 계속 나를 힘들게 해서
미국테마를 그대로 복사한 상태에서 그 복사된 것으로 수정을 해 볼려고 한다 · 손가락 넘기기 부분이 로딩을
많이 차지하는 것 같아서 우선 그것을 해결"*.

**자비스11 과 다르다 — 코드를 하나도 빼지 않는다.** 바꾸는 것은 둘뿐이다.
  ① 이름 — 맨 위 설명 · 브라우저 탭 제목 · 「JARVIS 12」 · 들어오는 문(page_access.guard "자비스12").
  ② 손가락 넘기기의 이름표 — 넘기기 코드는 바깥 문서에 한 번 심기면 화면을 옮겨도 남는다. 자비스3 과
     이름이 같으면 한 탭에서 오갈 때 자비스3 코드가 이 화면을 제 것으로 알고 손가락을 먼저 먹는다
     (2026-10-01 자비스11 때 실측). 그래서 화면 표식·사진 칸·폰 저장소·손가락 표시 이름을 j12 로 바꾼다.

**한 번만 쓰는 도구다.** 자비스12 를 고치기 시작하면 이 도구로 다시 만들지 않는다 — 다시 만들면 고친 것이
사라진다. 넘기기 말고 다른 바깥 문서 장치(관심종목 세부사항 그림 단추 등)는 이름이 자비스3 과 같다 — 같은
코드라 어느 쪽이 먼저 심겨도 똑같이 돈다. **자비스12 에서 그런 장치를 고치면 그 이름도 j12 로 바꿀 것.**
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else _ROOT / "pages" / "2_자비스3.py"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else _ROOT / "pages" / "11_자비스12.py"
PAGE_ACCESS_REVISION = 2026100901


def must_replace(text, old, new, count):
    found = text.count(old)
    assert found == count, f"{old[:60]!r} — {found}번(기대 {count}번)"
    print(f"바꿈 {found}번: {old[:56]!r}")
    return text.replace(old, new)


def build(src: str) -> str:
    # ① 이름
    src = must_replace(src, '"""자비스3 — 미국 테마 레이더와 실제 매수 기록 페이지."""',
                       '"""자비스12 — 자비스3 미국테마를 그대로 베낀 화면 (2026-10-09 상하님 지시).\n\n'
                       '상하님 — *"미국테마를 그대로 복사한 상태에서 그 복사된 것으로 수정을 해 볼려고 한다."*\n'
                       '처음 판은 자비스3 과 코드가 같다(tools/build_jarvis12.py — 이름과 손가락 넘기기 이름표만 다르다).\n'
                       '점수·목록은 자비스3 과 같은 jarvis3_data 를 부른다. **자비스3 은 손대지 않는다.**\n"""', 1)
    src = must_replace(src, 'st.set_page_config(page_title="자비스3 — 종목 브리핑", layout="wide")',
                       'st.set_page_config(page_title="자비스12 — 미국테마", layout="wide")\n\n'
                       'import page_access  # noqa: E402\n\n'
                       f'if int(getattr(page_access, "MODULE_REVISION", 0)) < {PAGE_ACCESS_REVISION}:\n'
                       '    import importlib as _importlib\n\n'
                       '    page_access = _importlib.reload(page_access)\n'
                       'page_access.guard(st, "자비스12")', 1)
    src = must_replace(src, 'st.markdown("## 자비스3 — 미국 테마 레이더")', 'st.markdown("## 자비스12 — 미국테마")', 1)
    src = must_replace(src, 'st.button("자비스3 로그인", key="j3_login_submit"',
                       'st.button("자비스12 로그인", key="j3_login_submit"', 1)
    src = must_replace(src, '<div class="j3b-title">JARVIS <b>3</b></div>',
                       '<div class="j3b-title">JARVIS <b>12</b></div>', 1)
    src = must_replace(src, 'hero_banner.render(st, refresh_key="j3hero_refresh")',
                       'hero_banner.render(st, refresh_key="j3hero_refresh", mark="12")', 1)
    # ② 손가락 넘기기 이름표(자비스11 도구와 같은 자리)
    src = must_replace(src, "j3b-home", "j12b-home", 59)
    src = must_replace(src, "j3-market-top", "j12-market-top", 55)
    src = must_replace(src, "j3b-swipe-script", "j12b-swipe-script", 2)
    src = must_replace(src, "'j3snap-host'", "'j12snap-host'", 1)
    src = must_replace(src, "copyHolder('j3page-host'), EDGE = copyHolder('j3curl-host')",
                       "copyHolder('j12page-host'), EDGE = copyHolder('j12curl-host')", 1)
    src = must_replace(src, "var STORE = 'j3snap:v1:';", "var STORE = 'j12snap:v1:';", 1)
    src = must_replace(src, "ev.__j3seen", "ev.__j12seen", 2)
    # 홈에서 넘기면 자비스12 관심종목으로 — 다만 자비스3 넘기기 코드가 이 탭에 이미 있으면 홈은 그쪽에
    # 맡긴다(둘이 함께 받으면 한 번 밀어 두 곳으로 간다 · 자비스11 과 같다).
    src = must_replace(src, "if (now === 'home') { return { link: '자비스3', from: 'home', to: 'watch' }; }",
                       "if (now === 'home') { return { link: '자비스12', from: 'home', to: 'watch' }; }", 1)
    src = must_replace(src, "  function screenNow() {\n", "  function screenNow() {\n"
                       "    var s = screenNow0();\n"
                       "    if (s === 'home' && d.getElementById('j3b-swipe-script')) { return ''; }\n"
                       "    return s;\n"
                       "  }\n"
                       "  function screenNow0() {\n", 1)
    return src


if __name__ == "__main__":
    text = build(SRC.read_text(encoding="utf-8"))
    compile(text, str(OUT), "exec")
    OUT.write_text(text, encoding="utf-8")
    print(f"{SRC.name} → {OUT.name} · {len(text.splitlines())}줄")

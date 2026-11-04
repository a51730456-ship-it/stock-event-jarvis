# -*- coding: utf-8 -*-
"""자비스13 시장분석 맨 위 머리 띠 — 한국 장면(2026-11-05 상하님 「한국 주식 배경 동영상 … 미국테마와 구분하자」).

**옛 자비스1~11 파일을 부르지 않는다**(2026-11-05 상하님 「과거 자비스 1~11까지 링크시키지 말아야 된다 · 참고해서 코딩하는 것은
괜찮다」). 처음 판은 얼린 hero_banner(자비스3 띠)를 불러 짜임 · 꾸밈을 빌렸는데, 그것을 끊고 **보고 베껴** 이 파일 안에 담았다.
  · 겉 짜임 · 꾸밈 — hero_banner.CSS 에서 쓰는 줄만 베낌(이름 j3hero → j13hero · 미국 캔들 · 화살촉 · 영상 줄은 뺌)
  · 폰 크기(600px 이하) — mobile_ui.CONTENT_CSS 의 띠 줄을 같은 경계 · 같은 값으로 베낌(이름만 j13hero)
  · 배경 — jarvis13_hero_scene(여의도 밤 · 코스피 캔들 오름 빨강/내림 파랑 · 자비스13 전용)
「✕ 자비스 닫기」(jarvis13_exit)는 .j13hero + 「13」 을 보고 붙는다.
"""
from __future__ import annotations

import jarvis13_hero_scene as scene

MODULE_REVISION = 2026110502
BOX_KEY = "j13hero_box"            # ↻ 를 보이는 동그라미 위에 겹치는 칸 이름(아래 꾸밈 · jarvis13_exit · jarvis13_skin 이 찾는다)

# hero_banner.CSS 에서 베낀 줄(값 그대로 · 이름만 j13hero). 바탕만 밤하늘 남색 · 글자 쪽 어둠은 조금 옅게(장면이 이미 어둡다).
_CSS = """<style>
.j13hero{position:relative;height:236px;overflow:hidden;border-radius:0 0 24px 24px;
  border:1px solid rgba(143,200,240,.55);border-top:none;background:#030b22;
  box-shadow:inset 0 -18px 31px rgba(0,19,45,.5),0 9px 22px rgba(0,0,0,.5);margin:0 0 1.4rem}
.j13hero-scrim{position:absolute;inset:0;
  background:linear-gradient(90deg,rgba(2,9,26,.55) 0%,rgba(2,9,26,.22) 30%,transparent 55%),
    linear-gradient(0deg,rgba(1,7,20,.42) 0%,transparent 34%)}
.j13hero-vig{position:absolute;inset:0;background:radial-gradient(130% 95% at 55% 40%,transparent 55%,rgba(1,6,18,.32) 100%)}
.j13hero-copy{position:absolute;left:18px;top:15px;z-index:3;line-height:1.15;text-shadow:0 2px 12px rgba(0,0,0,.8)}
.j13hero-mark{margin:0;font-size:26px;font-weight:800;letter-spacing:.02em;color:#eaf4ff}
.j13hero-mark b{color:#e8c07a;font-weight:900}
.j13hero-sub{margin:2px 0 0;font-size:13px;font-weight:700;color:#cfe0ff;letter-spacing:.02em}
.j13hero-actions{position:absolute;right:16px;top:14px;z-index:3;display:flex;gap:8px}
.j13hero-round,.j13hero-live{height:38px;display:flex;align-items:center;justify-content:center;
  border:1px solid #c89550;border-radius:22px;background:rgba(6,29,64,.87);color:#fff8e8;box-shadow:0 2px 8px rgba(0,0,0,.45)}
.j13hero-round{width:38px;font-size:23px}
.j13hero-live{width:86px;gap:7px;font-size:14px;font-weight:800}
.j13hero-live i{display:block;width:9px;height:9px;border-radius:50%;background:#64d84d;box-shadow:0 0 8px #4cf059}
div[class*="st-key-j13hero_box"]{position:relative!important}
div[class*="st-key-j13hero_box"] [data-testid="stElementContainer"]:has(button){
  position:absolute!important;right:110px;top:14px;z-index:6;width:auto!important;margin:0!important}
div[class*="st-key-j13hero_box"] .stButton,
div[class*="st-key-j13hero_box"] button{width:38px!important;height:38px!important;min-height:38px!important;
  padding:0!important;border:0!important;border-radius:50%!important;
  background:transparent!important;color:transparent!important;box-shadow:none!important}
div[class*="st-key-j13hero_box"] button:hover,
div[class*="st-key-j13hero_box"] button:focus{background:rgba(255,255,255,.12)!important}
</style>"""

# mobile_ui.CONTENT_CSS 의 띠 줄 — 폰(600px 이하)에서만 걸린다(CLAUDE.md 12 · 태블릿 · PC 는 그대로). 값 그대로 · 이름만 j13hero.
_PHONE_CSS = """<style>
@media (max-width:600px){
.j13hero{height:174px!important;border-radius:0 0 24px 24px!important;
  margin-left:-8px!important;margin-right:-8px!important;width:calc(100% + 16px)!important}
.j13hero-copy{left:20px!important;top:18px!important}
.j13hero-mark{font-size:29px!important;letter-spacing:-.05em!important}
.j13hero-sub{margin-top:6px!important;font-size:15px!important}
.j13hero-actions{right:15px!important;top:12px!important;gap:6px!important}
.j13hero-round,.j13hero-live{height:31px!important;border-radius:18px!important}
.j13hero-round{width:31px!important;font-size:19px!important}
.j13hero-live{width:66px!important;gap:5px!important;font-size:11px!important}
.j13hero-live i{width:8px!important;height:8px!important}
body div[class*="st-key-j13hero_box"] [data-testid="stElementContainer"]:has(button){right:79px!important;top:12px!important}
body div[class*="st-key-j13hero_box"] .stButton,
body div[class*="st-key-j13hero_box"] button{width:31px!important;height:31px!important;min-height:31px!important}
}
</style>"""


def css() -> str:
    """띠 꾸밈 · 폰 크기 · 한국 장면 움직임 — 꾸밈 덩이는 저마다 새 줄에서 연다(CLAUDE.md 0-4)."""
    return _CSS + "\n" + _PHONE_CSS + "\n" + scene.CSS + "\n"


def html(mark: str = "13") -> str:
    """띠 한 덩이 — 한국 장면 위에 어둠 두 겹 · 글자 · ↻ · 실시간."""
    return (
        '<div class="j13hero">'
        + scene.scene_html("market")
        + '<div class="j13hero-scrim"></div><div class="j13hero-vig"></div>'
        f'<div class="j13hero-copy"><p class="j13hero-mark">JARVIS <b>{mark}</b></p>'
        '<p class="j13hero-sub">시장분석</p></div>'
        '<div class="j13hero-actions"><span class="j13hero-round">↻</span>'
        '<span class="j13hero-live"><i></i>실시간</span></div>'
        "</div>"
    )


def render(st, *, refresh_key: str | None = None, mark: str = "13") -> bool:
    """시장분석 맨 위에 띠를 그린다. ↻ 를 누르셨으면 True. 실패해도 화면은 멈추지 않는다(띠는 그림일 뿐)."""
    if not refresh_key:
        try:
            st.markdown(css() + html(mark), unsafe_allow_html=True)
        except Exception:
            pass
        return False
    try:
        with st.container(key=BOX_KEY):
            st.markdown(css() + html(mark), unsafe_allow_html=True)
            return bool(st.button("↻", key=refresh_key))
    except Exception:
        return False

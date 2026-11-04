# -*- coding: utf-8 -*-
"""자비스13 시장분석 맨 위 머리 띠 — 한국 장면(2026-11-05 상하님 「한국 주식 배경 동영상 … 미국테마와 구분하자」).

얼린 hero_banner(자비스12 · 자비스3 이 같이 쓰는 띠)는 **고치지 않는다**(CLAUDE.md 0-2 ③ · 0-3 ②). 그 띠의 짜임 · 꾸밈 · ↻ 단추
겹치기는 그대로 빌려 쓰고, **배경만** 바꾼다 — 눈밭 영상(hero_snow_camp.mp4)과 미국 색 캔들 대신 jarvis13_hero_scene 의 여의도 밤 ·
코스피 캔들(오름 빨강 · 내림 파랑). 겉 짜임(.j3hero · .j3hero-mark · .j3hero-actions)이 같아야 「✕ 자비스 닫기」(jarvis13_exit)와
↻ 겹치기가 그대로 붙는다.
"""
from __future__ import annotations

import hero_banner
import jarvis13_hero_scene as scene

MODULE_REVISION = 2026110501
BOX_KEY = hero_banner.BOX_KEY          # ↻ 단추 겹치기 규칙이 이 이름으로 찾는다(얼린 꾸밈) — 같아야 한다

# 한국 장면 위에서 쓰는 덧꾸밈(이름 j13k) — 얼린 띠의 흐린 눈밭 바탕을 밤하늘 남색으로 · 글자 쪽 어둠은 조금 옅게(장면이 이미 어둡다)
_KR_CSS = """<style>
.j3hero.j13k-hero{background:#030b22!important}
.j3hero.j13k-hero .j3hero-scrim{background:linear-gradient(90deg,rgba(2,9,26,.55) 0%,rgba(2,9,26,.22) 30%,transparent 55%),
  linear-gradient(0deg,rgba(1,7,20,.42) 0%,transparent 34%)!important}
.j3hero.j13k-hero .j3hero-vig{background:radial-gradient(130% 95% at 55% 40%,transparent 55%,rgba(1,6,18,.32) 100%)!important}
.j3hero.j13k-hero .j3hero-copy,.j3hero.j13k-hero .j3hero-actions{z-index:3}
.j3hero.j13k-hero .j3hero-sub{color:#cfe0ff}
</style>"""


def css() -> str:
    """얼린 띠 꾸밈(새 줄에서 끝남) + 한국 장면 움직임 + 덧꾸밈 — 꾸밈 덩이는 저마다 새 줄에서 연다(CLAUDE.md 0-4)."""
    return hero_banner.css().rstrip() + "\n" + scene.CSS + "\n" + _KR_CSS + "\n"


def html(mark: str = "13") -> str:
    """얼린 hero_banner.html 과 같은 겉 짜임 — 영상 · 미국 캔들 자리에 한국 장면만."""
    return (
        '<div class="j3hero j13k-hero">'
        + scene.scene_html("market")
        + '<div class="j3hero-scrim"></div><div class="j3hero-vig"></div>'
        f'<div class="j3hero-copy"><p class="j3hero-mark">JARVIS <b>{mark}</b></p>'
        '<p class="j3hero-sub">시장분석</p></div>'
        '<div class="j3hero-actions"><span class="j3hero-round">↻</span>'
        '<span class="j3hero-live"><i></i>실시간</span></div>'
        "</div>"
    )


def render(st, *, refresh_key: str | None = None, mark: str = "13") -> bool:
    """hero_banner.render 와 같은 일 — 배경만 한국 장면. ↻ 를 누르셨으면 True. 실패해도 화면은 멈추지 않는다."""
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

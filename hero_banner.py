"""시장분석 맨 위의 눈밭 캠프 배너 (2026-08-28 상하님 지시).

상하님 — "시장분석 맨 위에 넣어라. 봉 조금 더 진하게 길게, 띠는 좀 더 위로 각도로."

무엇이 들어 있나
  · 배경 — 상하님이 그록·제미나이로 만드신 **영상 그대로**(1280x720 · 8초 · 2.71MB).
    `static/hero_snow_camp.mp4` 에 두고 주소로 부른다. 글자(base64)로 박아 넣으면
    화면을 다시 그릴 때마다 3.6MB 가 오간다. 주소로 부르면 브라우저가 **처음 한 번만**
    받고 그다음부터는 제 창고에서 꺼내 쓴다.
  · 영상이 안 뜰 때 — 대신 보일 한 장면(`static/hero_snow_camp.webp`)도 주소로
    부른다. 주소가 아예 막힌 때를 위해 40픽셀짜리 흐린 그림만 글자로 박아 둔다
    (256바이트). 어느 쪽이 실패해도 검은 칸이 남지 않는다.
  · 봉차트 — **6개월 일봉 125봉**(관심종목 카드의 「일봉 6개월」과 같은 밀도).
    지어낸 값이지 시세가 아니다. 그래서 **숫자를 한 개도 안 적는다** —
    지어낸 값에 퍼센트를 붙이면 화면이 거짓말을 한다(2026-08-28 상하님 물음 —
    "화살표 위에 글자는 뭐냐?").

**값·점수·판정은 하나도 안 건드린다.** 이 파일은 그림만 그린다.

속도 — 화면을 다시 그릴 때마다 오가는 글은 **35.5KB**다(그림 31.5 + 규칙 4.1).
처음 만든 것은 105KB 였고, 세 가지를 고쳐 줄였다.
  · 봉 하나마다 선·네모를 따로 두던 것을 조각 넷으로 묶었다 (67 → 31.5KB)
  · 장면 그림을 글자에서 빼고 주소로 불렀다 (64 → 0KB)
  · 화살촉이 탈 길을 성기게 만들었다 (8 → 2KB)
만드는 데 걸리는 시간은 0.1ms 다(그림은 파일을 읽을 때 한 번만 만든다).
영상 2.71MB 는 **첫 한 번**만 오간다.
"""

from __future__ import annotations

import math

# 그림·글귀를 바꾸면 이 숫자를 올리고 페이지의 `_REQUIRED_HERO_REVISION`도 같이
# 올린다(CLAUDE.md 11번). 안 올리면 온라인에 옛 배너가 그대로 남는다.
MODULE_REVISION = 2026082812

UP, DOWN = "#4da6ff", "#ff6b6b"          # 미국 화면 규칙 — 오르면 파랑, 내리면 빨강

# ── 봉과 띠의 성질을 정하는 값 여섯 ────────────────────────────────────────────
# 2026-08-28 상하님 지시 — "봉 조금 더 진하게 길게, 띠는 좀 더 위로 각도로".
# 여기 여섯만 만지면 모양이 바뀐다. 괄호 안은 그 지시 **전**의 값이다.
DRIFT = .55       # 한 봉에 오르는 값 — 클수록 띠가 선다 (앞 판 .34)
LONG_W = 5.0      # 긴 파도 — 눌림 깊이 (앞 판 6.0)
SHORT_W = 1.5     # 짧은 파도 — 봉 몸통 길이 (앞 판 .8)
WICK = 1.7        # 꼬리 길이 (앞 판 .9)
BODY_A = .86      # 몸통 진하기 (앞 판 .66)
WICK_A = .72      # 꼬리 진하기 (앞 판 .5)

BARS_6M = 125     # 6개월 일봉 — 관심종목 카드의 「일봉 6개월」과 같은 밀도

_VIDEO_URLS = (
    # 스트림릿이 `static/` 폴더를 이 주소로 내준다(.streamlit/config.toml 의
    # enableStaticServing). 노트북에서 재 봤다 — 200, 2,845,262바이트, video/mp4.
    # 앞의 것이 안 되면 브라우저가 다음 것을 시도한다. 주소 앞에 무엇이 붙느냐가
    # 온라인과 노트북에서 다를 수 있어 둘을 다 적는다.
    "app/static/hero_snow_camp.mp4",
    "/app/static/hero_snow_camp.mp4",
)

# 영상이 뜨기 전·못 뜰 때 대신 보일 한 장면도 같은 창고에서 주소로 부른다.
_POSTER_URL = "app/static/hero_snow_camp.webp"

# 주소가 아예 막혔을 때의 마지막 자리 — 40픽셀짜리 흐린 그림이다. 이것만 글자로
# 박는다(256바이트). 검은 칸이 남는 것보다 흐린 눈밭이 낫다.
_BLUR = (
    "data:image/webp;base64,UklGRrgAAABXRUJQVlA4IKwAAACwBgCdASooABYAPulgqlApJSOiqrgM"
    "ASAdCUAXBgFm7ZEzXcYJE48Clnf/RfoRlPdsXGdVgzBYsEhZO3WgwADhpQeP9TL7Z8j5OSdP0aZF5M"
    "N5OIXEKF+ZRVrjIvzgzxmeGyCOU1IU9xmUYQ1YSz6uf09W6gTnsaOYVhUi4TMHBz6V5bVLx68NkjTM"
    "JFNILivg7RsadvAD+h67MnKQ87c5Bc8NpTs0B9xYPAAA"
)


def _series(bars: int, seed: float = 12.0) -> list[tuple[float, float, float, float]]:
    """6개월 일봉처럼 흐르는 자료. 값 = 곧게 오르는 선 + 파도 셋.

      · 곧게 오르는 선 — 한 봉에 `DRIFT`씩. 클수록 **띠의 각도가 선다.**
      · 긴 파도(26봉) — **눌림 자리**를 만든다.
      · 중간 파도(9봉)와 짧은 파도(3봉) — 하루하루 흔들림.
        짧은 파도가 클수록 **봉 몸통이 길어진다.**

    무작위를 안 쓰므로 몇 번을 다시 그려도 같은 그림이 나온다. 그래야 화면을
    다시 그릴 때마다 배너가 달라 보이지 않는다.

    `seed=12.0` 은 고른 값이다. 파도의 시작점을 옮겨 가며 재 보고 **끝에서
    추세선이 오르면서 끝나는** 자리를 골랐다. 배너는 마지막 모습이 남으므로
    끝이 내려가면 우상향으로 안 보인다.
    """
    def wave(t: float) -> float:
        return (LONG_W * math.sin(t * .241 + .4)
                + 1.7 * math.sin(t * .68 + 1.1)
                + SHORT_W * math.sin(t * 2.05 + .35))

    out: list[tuple[float, float, float, float]] = []
    price = 100.0
    for i in range(bars):
        t = i + seed
        op = price
        cl = op + DRIFT + (wave(t) - wave(t - 1)) * .8
        hi = max(op, cl) + abs(math.sin(t * 1.9 + .7)) * WICK + .3
        lo = min(op, cl) - abs(math.cos(t * 1.4 + .3)) * WICK - .3
        out.append((op, hi, lo, cl))
        price = cl
    return out


def _smooth(points: list[tuple[float, float]]) -> str:
    """점들을 부드러운 곡선으로 잇는다(캣멀-롬). 꺾인 선은 배너에 안 어울린다."""
    d = [f"M{points[0][0]:.1f} {points[0][1]:.1f}"]
    for i in range(len(points) - 1):
        p0 = points[i - 1] if i > 0 else points[i]
        p1, p2 = points[i], points[i + 1]
        p3 = points[i + 2] if i + 2 < len(points) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}")
    return " ".join(d)


def _chart(name: str, vw: int, vh: int, pad_l: int, pad_r: int,
           top: int, bottom: int, wick_w: float,
           widths: tuple[float, float, float, float]) -> tuple[str, str]:
    """한 벌의 봉차트. 폰용과 노트북용을 따로 그려 봉 굵기를 칸에 맞춘다.

    **봉은 그림 조각 넷으로 그린다** — 오른 꼬리·내린 꼬리·오른 몸통·내린 몸통.
    한 봉마다 선과 네모를 따로 두면 조각이 250개가 되어 글이 33KB 가 된다.
    넷으로 묶으면 16KB 다(2026-08-28 실측). 스트림릿은 화면을 다시 그릴 때마다
    이 글을 통째로 보내므로, 줄인 만큼이 다시 그릴 때마다 아낀 양이다.

    돌려주는 것은 (그림, 띠의 길) 둘이다. 띠의 길은 화살촉이 타고 가는 데 쓴다.
    """
    data = _series(BARS_6M)
    lo = min(b[2] for b in data)
    hi = max(b[1] for b in data)
    slot = (vw - pad_l - pad_r) / BARS_6M
    body_w = slot * .56

    def y(v: float) -> float:
        return bottom - (v - lo) / (hi - lo) * (bottom - top)

    def x(i: int) -> float:
        return pad_l + slot * (i + .5)

    wk_up: list[str] = []
    wk_dn: list[str] = []
    bd_up: list[str] = []
    bd_dn: list[str] = []
    for i, (op, h, l, cl) in enumerate(data):
        cx = x(i)
        rose = cl >= op
        (wk_up if rose else wk_dn).append(f"M{cx:.1f} {y(h):.1f}V{y(l):.1f}")
        t, b = y(max(op, cl)), y(min(op, cl))
        (bd_up if rose else bd_dn).append(
            f"M{cx - body_w / 2:.1f} {t:.1f}h{body_w:.1f}v{max(b - t, 1.6):.1f}h-{body_w:.1f}z")

    trend = []
    for i in range(BARS_6M):
        chunk = [data[j][3] for j in range(max(0, i - 11), i + 1)]
        trend.append((x(i), y(sum(chunk) / len(chunk))))
    d = _smooth(trend)
    # 화살촉이 타고 갈 길은 **성기게** 만든다. 띠와 똑같은 길을 규칙(CSS)에 한 번 더
    # 적으면 4KB 가 두 번 오간다. 넷에 하나만 남겨도 화살촉이 가는 자리는 눈으로
    # 구별이 안 된다(1KB).
    coarse = _smooth(trend[::4] + [trend[-1]])

    # 칠은 그림의 **오른쪽 끝까지** 이어야 한다. 마지막 봉에서 끊으면 거기에 밝은
    # 세로줄이 생기고, 수평으로 이으면 선 위에 밝은 턱이 생긴다(둘 다 2026-08-28
    # 실물에서 보였다). 그래서 **마지막 기울기 그대로** 뻗는다.
    run = trend[-1][0] - trend[-2][0]
    rise = (trend[-1][1] - trend[-2][1]) / run if run else 0
    edge_x = vw + 6
    edge_y = max(top * .35, trend[-1][1] + rise * (edge_x - trend[-1][0]))
    fill_d = (f"{d} L{edge_x} {edge_y:.1f} L{edge_x} {vh + 4}"
              f" L{trend[0][0]:.1f} {vh + 4} Z")
    w_wide, w_near, w_line, head = widths
    j = "".join

    svg = (
        f'<svg class="j3hero-chart j3hero-{name}" viewBox="0 0 {vw} {vh}"'
        ' preserveAspectRatio="none" aria-hidden="true">'
        "<defs>"
        f'<linearGradient id="j3hf{name}" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#4da6ff" stop-opacity=".38"/>'
        '<stop offset=".55" stop-color="#2f7fd6" stop-opacity=".12"/>'
        '<stop offset="1" stop-color="#1b4f8a" stop-opacity="0"/></linearGradient>'
        # 가리개는 **흰색**이어야 한다. 그림 가리개는 밝기로 가리므로 검은색을 쓰면
        # 투명도와 상관없이 통째로 사라진다(2026-08-28 봉이 하나도 안 나왔다).
        f'<linearGradient id="j3hd{name}" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset=".2" stop-color="#fff" stop-opacity=".45"/>'
        '<stop offset=".42" stop-color="#fff" stop-opacity="1"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="1"/></linearGradient>'
        f'<mask id="j3hm{name}"><rect width="{vw}" height="{vh}" fill="url(#j3hd{name})"/></mask>'
        f'<filter id="j3hbw{name}" x="-30%" y="-60%" width="160%" height="220%">'
        f'<feGaussianBlur stdDeviation="{w_wide * .6:.1f}"/></filter>'
        f'<filter id="j3hbn{name}" x="-20%" y="-40%" width="140%" height="180%">'
        f'<feGaussianBlur stdDeviation="{w_near * .5:.1f}"/></filter>'
        f'<path id="j3hp{name}" d="{d}"/>'
        "</defs>"
        f'<g mask="url(#j3hm{name})">'
        f'<path d="{j(wk_up)}" fill="none" stroke="{UP}" stroke-width="{wick_w}" opacity="{WICK_A}"/>'
        f'<path d="{j(wk_dn)}" fill="none" stroke="{DOWN}" stroke-width="{wick_w}" opacity="{WICK_A}"/>'
        f'<path d="{j(bd_up)}" fill="{UP}" opacity="{BODY_A}"/>'
        f'<path d="{j(bd_dn)}" fill="{DOWN}" opacity="{BODY_A}"/></g>'
        f'<path d="{fill_d}" fill="url(#j3hf{name})" mask="url(#j3hm{name})"/>'
        # 띠는 세 겹이다 — 넓게 번지는 빛·가까운 빛·얇고 밝은 선. 굵은 흰 선 하나로
        # 그리면 페인트칠처럼 보인다.
        f'<use href="#j3hp{name}" fill="none" stroke="#2f8ce0" stroke-width="{w_wide}"'
        f' stroke-linecap="round" stroke-linejoin="round" opacity=".36" filter="url(#j3hbw{name})"/>'
        f'<use href="#j3hp{name}" fill="none" stroke="#7cc4ff" stroke-width="{w_near}"'
        f' stroke-linecap="round" stroke-linejoin="round" opacity=".6" filter="url(#j3hbn{name})"/>'
        f'<use href="#j3hp{name}" fill="none" stroke="#f2faff" stroke-width="{w_line}"'
        ' stroke-linecap="round" stroke-linejoin="round"/>'
        f'<g class="j3hero-tip j3hero-tip-{name}">'
        f'<circle r="{head * 1.7:.1f}" fill="#8fd0ff" opacity=".26" filter="url(#j3hbn{name})"/>'
        f'<path d="M{-head:.1f},{-head * .8:.1f} L{head * 1.35:.1f},0'
        f' L{-head:.1f},{head * .8:.1f} L{-head * .55:.1f},0 Z" fill="#f4fbff"/></g>'
        "</svg>"
    )
    return svg, coarse


# 위(top)와 아래(bottom)를 벌릴수록 띠가 세로를 더 써서 **각도가 선다.**
# 잰 값 — 폰 16.8도, 노트북 11.2도 (앞 판은 노트북 8.5도).
_SM, _SM_D = _chart("sm", 375, 150, 8, 10, 16, 142, .75, (7, 3.2, 1.6, 5))
_LG, _LG_D = _chart("lg", 900, 236, 16, 22, 24, 224, 1.15, (13, 5.2, 2.3, 7.5))


CSS = """
<style>
.j3hero{position:relative;height:220px;overflow:hidden;border-radius:20px;
  border:1px solid rgba(143,200,240,.55);background:#01091f center 55%/cover no-repeat url("__BLUR__");
  box-shadow:inset 0 -18px 31px rgba(0,19,45,.5),0 9px 22px rgba(0,0,0,.5);
  /* 아래 여백이 1.4rem 인 까닭 — 바로 밑의 두 단추 줄(「🌏 한국테마 →」·
     「📘 이 테마 설명」)이 페이지 규칙에서 위로 1rem 당겨져 있다. 여백을 .55rem
     으로 두면 단추가 배너 아래 테두리를 밟는다(2026-08-28 실물에서 5px 겹쳤다). */
  margin:0 0 1.4rem}
.j3hero video{position:absolute;inset:0;width:100%;height:100%;
  object-fit:cover;object-position:center 48%}
/* 영상 위에 어둠을 깔아야 봉과 글자가 읽힌다. 두 겹이다.
   ① 왼쪽이 더 어둡다 — 거기 「JARVIS 3 · 시장분석」 글자가 있다.
   ② **아래쪽**이 더 어둡다 — 거기 봉차트가 있다. 눈밭이 하얘서 이것이 없으면
      파란 봉이 묻힌다(2026-08-28 실물에서 안 보였다). 로봇과 캠핑카가 있는
      위쪽은 밝게 둔다 — 상하님이 그 영상을 보시려고 넣으신 것이다. */
.j3hero-scrim{position:absolute;inset:0;
  background:linear-gradient(90deg,rgba(2,9,26,.9) 0%,rgba(2,9,26,.6) 34%,
      rgba(2,9,26,.26) 62%,rgba(2,9,26,.38) 100%),
    linear-gradient(0deg,rgba(1,7,20,.86) 0%,rgba(1,7,20,.5) 34%,transparent 62%)}
.j3hero-vig{position:absolute;inset:0;
  background:radial-gradient(120% 90% at 50% 40%,transparent 38%,rgba(1,6,18,.68) 100%)}
/* 차트는 **아래 3분의 2**에만 둔다. 위까지 채우면 띠가 로봇 얼굴을 가로지른다. */
.j3hero-chart{position:absolute;left:0;right:0;bottom:0;width:100%;height:68%}
.j3hero-lg{display:block}
.j3hero-sm{display:none}
.j3hero-copy{position:absolute;left:18px;top:50%;transform:translateY(-50%);
  line-height:1.15;text-shadow:0 2px 12px rgba(0,0,0,.8)}
.j3hero-mark{margin:0;font-size:26px;font-weight:800;letter-spacing:.02em;color:#eaf4ff}
.j3hero-mark b{color:#e8c07a;font-weight:900}
.j3hero-sub{margin:2px 0 0;font-size:13px;font-weight:700;color:#9fc6ea;letter-spacing:.02em}
/* 화살촉이 띠를 타고 간다. 6초에 한 바퀴. */
.j3hero-tip{offset-rotate:auto;animation:j3heroRun 6s linear infinite}
.j3hero-tip-lg{offset-path:path("__LG__")}
.j3hero-tip-sm{offset-path:path("__SM__")}
@keyframes j3heroRun{
  0%{offset-distance:8%;opacity:0}
  8%{opacity:1}
  88%{opacity:1}
  100%{offset-distance:100%;opacity:0}
}
@media (prefers-reduced-motion:reduce){
  .j3hero-tip{animation:none;offset-distance:100%}
}
</style>
"""


def css() -> str:
    """배너 규칙 한 덩어리. 화살촉이 탈 길 두 개와 흐린 그림을 끼워 넣는다."""
    return (CSS.replace("__LG__", _LG_D).replace("__SM__", _SM_D)
               .replace("__BLUR__", _BLUR))


def html() -> str:
    """배너 그림 한 덩어리."""
    sources = "".join(f'<source src="{u}" type="video/mp4">' for u in _VIDEO_URLS)
    return (
        '<div class="j3hero">'
        f'<video autoplay muted loop playsinline preload="auto" poster="{_POSTER_URL}">'
        f"{sources}</video>"
        '<div class="j3hero-scrim"></div><div class="j3hero-vig"></div>'
        f"{_SM}{_LG}"
        '<div class="j3hero-copy"><p class="j3hero-mark">JARVIS <b>3</b></p>'
        '<p class="j3hero-sub">시장분석</p></div>'
        "</div>"
    )


def render(st) -> None:
    """시장분석 맨 위에 배너를 그린다. 실패해도 화면이 멈추면 안 된다."""
    try:
        st.markdown(css() + html(), unsafe_allow_html=True)
    except Exception:
        # 배너는 그림일 뿐이다. 못 그려도 아래 화면은 그대로 나와야 한다.
        pass

"""자비스10 · 한국증시 — 화면 조각(꾸밈 · 카드 · 설명 창 · 이동막대 · 손가락 넘기기) (2026-09-30).

화면 설명서: docs/JARVIS10_SPEC.md. 모양은 자비스3 을 따른다(남색 바탕 · 금테 카드 · 아래 이동막대).

말은 정확히 쓴다(설명서 1장) — **코스피 지수** · **코스피200 상품** · **개별 종목**.
한국 칸 색: 오르면 빨강 · 내리면 파랑. 미국 칸 색: 자비스3 그대로(오르면 파랑 · 내리면 빨강).

HTML 은 **줄바꿈 없이** 이어 붙인다 — 스트림릿 글 칸(markdown)은 빈 줄이나 네 칸 들여쓰기를
글자로 흘려 버린다.
"""
from __future__ import annotations

import html as _html
import json
import math

MODULE_REVISION = 2026100101

# ── 색 ───────────────────────────────────────────────────────────────────────
KR_UP, KR_DOWN = "#ff5b5b", "#4da6ff"
US_UP, US_DOWN = "#4da6ff", "#ff5b5b"


def _kr(v) -> str:
    return KR_UP if v and v > 0 else KR_DOWN if v and v < 0 else "#9aa0aa"


def _us(v) -> str:
    return US_UP if v and v > 0 else US_DOWN if v and v < 0 else "#9aa0aa"


def _pct(v, digits: int = 1, sign: bool = True) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    s = f"{v:+.{digits}f}" if sign else f"{v:.{digits}f}"
    return s.replace("-", "−") + "%"


def _num(v, digits: int = 2) -> str:
    if v is None:
        return "—"
    return f"{v:,.{digits}f}"


def _md(date_str: str) -> str:
    """'2026-09-30' → '9월 30일'."""
    try:
        y, m, d = date_str.split("-")
        return f"{int(m)}월 {int(d)}일"
    except Exception:
        return date_str or ""


def _esc(s) -> str:
    return _html.escape(str(s), quote=True)


# ── 작은 그림 ────────────────────────────────────────────────────────────────
def line_svg(points, base, up: str, down: str, *, w: int = 150, h: int = 46) -> str:
    """자비스3 지수 칸과 같은 선 그림 — 점선(기준선) 위는 오른 색, 아래는 내린 색으로 긋는다.

    「당일」은 전날 종가가, 「6개월」은 여섯 달 전 첫 종가가 기준선이다(자비스3 과 같다).
    좌표는 10배로 잡아 정수로 적는다 — 소수점이 없어 칸마다 글자가 줄어든다(폰은 이 글자를 다 읽는다).
    """
    vals = [float(v) for v in (points or []) if v is not None]
    if len(vals) < 2 or not base:
        return ""
    base = float(base)
    lo, hi = min(vals + [base]), max(vals + [base])
    span = (hi - lo) or 1.0
    width, height, pad = w * 10, h * 10, 60
    inner = height - pad * 2
    step = width / (len(vals) - 1)

    def y(v: float) -> int:
        return round(pad + inner - (v - lo) / span * inner)

    runs: list = []
    for i in range(len(vals) - 1):
        col = up if (vals[i] + vals[i + 1]) / 2 >= base else down
        if runs and runs[-1][0] == col:
            runs[-1][1].append(i + 1)
        else:
            runs.append((col, [i, i + 1]))
    by = y(base)
    area = f"0,{by} " + " ".join(f"{round(i * step)},{y(v)}" for i, v in enumerate(vals)) + f" {width},{by}"
    lines = "".join("<polyline points='" + " ".join(f"{round(i * step)},{y(vals[i])}" for i in idx)
                    + f"' stroke='{col}'/>" for col, idx in runs)
    return (f"<svg viewBox='0 0 {width} {height}' preserveAspectRatio='none' class='j10-spark' aria-hidden='true'>"
            f"<polygon points='{area}' fill='{up if vals[-1] >= base else down}' fill-opacity='.14'/>"
            f"<line x1='0' x2='{width}' y1='{by}' y2='{by}'/><g>{lines}</g></svg>")


def _chart_swap(c: dict, *, kr: bool, w: int, h: int) -> tuple[str, bool]:
    """「당일」 그림과 「6개월」 그림을 같은 자리에 겹쳐 둔다(자비스3 지수 칸과 같은 장치).

    누르면 같은 자리에서 바뀐다 — 자리를 새로 만들지 않아 아래 화면이 밀리지 않는다.
    당일 자료를 못 받았으면 6개월 그림 하나만 두고, 누를 것도 두지 않는다(누르면 빈칸이 되지 않게).
    """
    up, down = (KR_UP, KR_DOWN) if kr else (US_UP, US_DOWN)
    daily = [v for v in (c.get("spark") or []) if v is not None]
    if len(daily) > 70:                     # 여섯 달 125일 → 이틀에 한 점(끝 값은 남긴다) — 폭 150px 이라 모양은 같다
        daily = daily[::2] + ([daily[-1]] if (len(daily) - 1) % 2 else [])
    six = line_svg(daily, daily[0] if daily else None, up, down, w=w, h=h)
    intra = c.get("intraday") or {}
    today = line_svg(intra.get("points"), intra.get("base"), up, down, w=w, h=h)
    if not today:
        return (f"<div class='j10-swap'><div class='j10-now'>{six}<div class='j10-cap'>6개월</div></div></div>"
                if six else ""), False
    return ("<div class='j10-swap'>"
            f"<div class='j10-now'>{today}<div class='j10-cap'>당일</div></div>"
            f"<div class='j10-more'>{six}<div class='j10-cap'>6개월</div></div></div>"), bool(six)


def _tap(nonce: str, key: str) -> str:
    """칸 전체를 덮는 누르는 자리 — 숨긴 체크칸을 켰다 껐다 한다(서버에 안 묻는다 · 자바스크립트 없이 된다)."""
    tap_id = f"j10t-{_esc(nonce)}-{key}"
    return (f"<input type='checkbox' id='{tap_id}' class='j10-tap'>"
            f"<label for='{tap_id}' class='j10-tapzone' aria-label='당일·6개월 그림 바꾸기'></label>")


def _banner_line(monthly) -> str:
    vals = [math.log(v) for v in (monthly or []) if v and v > 0]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    w, h = 390, 150
    return " ".join(f"{i * w / (len(vals) - 1):.1f},{h - 10 - (v - lo) / ((hi - lo) or 1) * (h - 40):.1f}"
                    for i, v in enumerate(vals))


# ── 꾸밈 ─────────────────────────────────────────────────────────────────────
# 화면 상태 규칙(어느 판이 보이나)은 **이번 판 표시(nonce)** 를 붙인 이름에만 걸린다.
# 다른 화면에 갔다가 돌아오면 표시가 바뀌어 늘 코스피 판부터 보인다(↻ 로 다시 받을 때는 그대로).
_BASE_CSS = """
:root{--j10-bg:#031023;--j10-card:linear-gradient(145deg,#06345f 0%,#03264a 58%,#001d3c 100%);
--j10-gold:#bf9254a8;--j10-gold-s:#e2b25e;--j10-gold-t:#f4c66b;--j10-violet:#c084fc;--j10-green:#44f0a1;
--j10-sky:#4da6ff;--j10-muted:#9aa0aa;--j10-note:#aeb6c2;--j10-text:#e9eff6}
[data-testid="stSidebar"],[data-testid="stSidebarNav"],[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"]{display:none!important}
[data-testid="stAppViewContainer"],.stApp{background:linear-gradient(180deg,#041229 0%,#031023 40%,#020c1d 100%)!important}
.stAppHeader,[data-testid="stHeader"],[data-testid="stStatusWidget"],[data-testid="stAppDeployButton"]{display:none!important}
[data-testid="stMainBlockContainer"]{max-width:720px!important;padding:.7rem 1rem 7.5rem!important}
.j10 *{box-sizing:border-box}
.j10{color:var(--j10-text);font-family:inherit;-webkit-font-smoothing:antialiased}
.j10-banner{position:relative;height:178px;border-radius:22px;overflow:hidden;border:1px solid #2c4d7a;
background:radial-gradient(120% 90% at 80% 10%,#16427a 0%,#0a2650 45%,#06173a 100%)}
.j10-stars i{position:absolute;width:2px;height:2px;border-radius:50%;background:#fff}
.j10-banner-line{position:absolute;left:0;right:0;bottom:0;width:100%;height:150px;filter:drop-shadow(0 0 5px #9fd0ff)}
.j10-banner-cap{position:absolute;right:12px;bottom:8px;font-size:10px;color:#b9d4f5aa}
.j10-brand{position:absolute;left:18px;top:18px;line-height:1}
.j10-brand b{font-size:34px;font-weight:900;letter-spacing:-1.5px;color:#fff;text-shadow:0 2px 8px #0008}
.j10-brand em{font-style:normal;font-size:34px;font-weight:900;color:var(--j10-gold-t);margin-left:6px}
.j10-brand span{display:block;margin-top:8px;font-size:19px;font-weight:800;color:#9ecbff}
.j10-top-btns{position:absolute;right:12px;top:14px;display:flex;gap:6px}
.j10-circle{width:38px;height:38px;border-radius:50%;border:1.5px solid var(--j10-gold-s);display:grid;place-items:center;
background:#06224899;font-size:18px;color:#fff;cursor:pointer;user-select:none}
.j10-phase{height:38px;padding:0 13px;border-radius:19px;border:1.5px solid var(--j10-gold-s);display:flex;align-items:center;
gap:6px;background:#06224899;font-weight:800;font-size:13.5px;color:#fff;white-space:nowrap}
.j10-phase i{width:9px;height:9px;border-radius:50%;background:#8a96a8}
.j10-phase.open i{background:#39d353;box-shadow:0 0 6px #39d353}
.j10-row{display:flex;justify-content:flex-end;align-items:center;gap:8px;margin:10px 2px 0}
.j10-help-btn{background:#d8ecff;color:#b4532a;font-weight:800;font-size:14px;padding:8px 14px;border-radius:12px;
border:1px solid #9cc9f5;cursor:pointer;user-select:none;white-space:nowrap}
.j10-sec{color:var(--j10-violet);font-weight:850;font-size:18px;margin:6px 4px 8px}
.j10-sec small{color:var(--j10-muted);font-size:12px;font-weight:700;margin-left:6px}
.j10-card{background:var(--j10-card);border:1px solid var(--j10-gold);border-radius:17px;padding:12px 13px;margin-bottom:10px;
box-shadow:inset 0 1px #7bc9ff35,0 6px 16px #0006}
.j10-lbl{color:var(--j10-green);font-weight:800;font-size:15px}
.j10-lbl small{color:var(--j10-muted);font-weight:700;margin-left:6px;font-size:11.5px}
.j10-hero-row{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;margin-top:4px}
.j10-big{font-size:34px;font-weight:900;letter-spacing:-1px;line-height:1.05}
.j10-chg{font-size:19px;font-weight:850;margin-top:2px}
.j10-hero-spark{width:150px;flex:0 0 150px}
.j10-spark{width:100%;height:46px;display:block}
.j10-spark line{stroke:#ffffff61;stroke-width:1;stroke-dasharray:4 4;vector-effect:non-scaling-stroke}
.j10-spark g{fill:none;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.j10-spark polyline{vector-effect:non-scaling-stroke}
.j10-tapcard{position:relative;cursor:pointer;transition:filter .12s ease-out}.j10-tapcard:active{filter:brightness(1.12)}
.j10-tap{position:absolute;opacity:0;width:0;height:0;margin:0;pointer-events:none}
.j10-tapzone{position:absolute;inset:0;z-index:3;border-radius:inherit;cursor:pointer;-webkit-tap-highlight-color:transparent}
.j10-swap{position:relative;overflow:hidden;border-radius:7px}
.j10-swap>div{position:relative;opacity:1;transform:translateX(0);transition:opacity .5s ease,transform .5s ease}
.j10-swap .j10-more{position:absolute;inset:0;opacity:0;transform:translateX(26px);pointer-events:none}
.j10-tap:checked~* .j10-now{opacity:0;transform:translateX(-26px);transition:opacity .24s ease-out,transform .24s ease-out}
.j10-tap:checked~* .j10-more{opacity:1;transform:translateX(0);transition:opacity .24s ease-out,transform .24s ease-out}
@media (hover:hover) and (pointer:fine){.j10-tapcard:hover{filter:brightness(1.1)}
.j10-tapcard:hover .j10-now{opacity:0;transform:translateX(-26px);transition:opacity .24s ease-out,transform .24s ease-out}
.j10-tapcard:hover .j10-more{opacity:1;transform:translateX(0);transition:opacity .24s ease-out,transform .24s ease-out}}
.j10-cap{position:absolute;left:0;right:0;top:50%;transform:translateY(-54%);color:#ffd1668c;font-size:.7rem;font-weight:800;
letter-spacing:-.02em;text-align:center;pointer-events:none;z-index:0;text-shadow:0 1px 3px #000b}
.j10-swap svg{position:relative;z-index:1}
.j10-chips{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:10px}
.j10-chip{background:#ffffff0d;border:1px solid #ffffff1c;border-radius:11px;padding:6px 7px;display:flex;flex-direction:column;gap:2px}
.j10-chip small{color:var(--j10-muted);font-size:11px;font-weight:700}.j10-chip b{font-size:14.5px;font-weight:900}
.j10-ndd-head{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.j10-ndd-head b{color:var(--j10-violet);font-weight:850;font-size:15px}.j10-ndd-val{font-size:23px;font-weight:900}
.j10-ndd-bar{position:relative;height:10px;border-radius:5px;background:#ffffff1a;margin:8px 0 4px}
.j10-ndd-fill{position:absolute;left:0;top:0;bottom:0;border-radius:5px;background:linear-gradient(90deg,#ffd166,#44f0a1)}
.j10-ndd-center{position:absolute;left:50%;top:-4px;bottom:-4px;width:3px;margin-left:-1.5px;background:var(--j10-violet);
border-radius:2px;box-shadow:0 0 6px #c084fcb3}
.j10-ndd-scale{display:flex;justify-content:space-between;color:#8a9099;font-size:11.5px;font-weight:700}
.j10-ndd-scale span:nth-child(2){color:var(--j10-violet)}
.j10-note{color:var(--j10-note);font-size:13px;line-height:1.6;margin-top:6px}.j10-key{color:var(--j10-sky);font-weight:850}
.j10-up{color:#ff5b5b}.j10-down{color:#4da6ff}.j10-muted{color:var(--j10-muted)}
.j10-cap{color:var(--j10-note);font-size:12.5px;line-height:1.55;margin-bottom:8px}.j10-cap b{color:#fff}
.j10-foot{color:#7f8a99;font-size:11px;line-height:1.5;margin-top:7px}.j10-foot.center{text-align:center;margin:6px 8px 10px}
.j10-ht{border:1px solid #ffffff1c;border-radius:10px;overflow:hidden}
.j10-hr{display:grid;grid-template-columns:.7fr 2.3fr .95fr .95fr;align-items:center;gap:6px;padding:8px;border-top:1px solid #ffffff12;font-size:12.5px}
.j10-hr.hh{background:#f0b58a2e;color:#ffd7b5;font-weight:800;border-top:0;font-size:11.5px}.j10-hr.hh span{text-align:center}
.j10-hy{font-weight:900;color:#fff;text-align:center;font-size:14px}.j10-hm,.j10-hw{text-align:center;font-weight:900;font-size:13.5px}
.j10-hbar{position:relative;height:22px;border-radius:6px;background:#ffffff10;overflow:hidden;display:block}
.j10-hbar i{position:absolute;left:0;top:0;bottom:0;border-radius:6px;background:linear-gradient(90deg,#b8322f,#ff5b5b)}
.j10-hbar em{position:absolute;left:8px;top:50%;transform:translateY(-50%);font-style:normal;font-size:11.5px;font-weight:900;
color:#fff;text-shadow:0 1px 2px #000a;white-space:nowrap}
.j10-split{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}
.j10-split>div{background:#ffffff0b;border:1px solid #ffffff17;border-radius:12px;padding:9px}
.j10-split small{display:block;color:var(--j10-muted);font-size:11px;font-weight:700}
.j10-split b{display:block;font-size:14px;margin:3px 0;font-weight:900}.j10-split em{font-style:normal;font-size:11px;color:var(--j10-note)}
.j10-rb{display:grid;grid-template-columns:150px 1fr 54px;align-items:center;gap:8px;margin:7px 0;font-size:12.5px}
.j10-rb>div{height:12px;border-radius:6px;background:#ffffff12;overflow:hidden}.j10-rb i{display:block;height:100%;border-radius:6px;background:#8b9bb4}
.j10-rb b{text-align:right;font-size:13.5px;color:#cfd8e3}.j10-rb.best span{color:#fff;font-weight:900}
.j10-rb.best i{background:linear-gradient(90deg,#f4c66b,#ffd98f)}.j10-rb.best b{color:var(--j10-gold-t)}
.j10-rb small{display:block;color:#7f8a99;font-size:10.5px;font-weight:700}
.j10-easy{margin-top:9px;font-size:13px;line-height:1.6;color:#dfe7f0}.j10-easy>b:first-child{color:var(--j10-gold-t)}
.j10-decide{text-align:center;color:#cfd8e3;font-size:12.5px;margin:12px 6px 4px;padding:9px;border:1px solid #c1975b99;border-radius:13px;background:#06264ad9}
.j10-words{font-size:12px;color:#aebdd0;line-height:1.6;margin:8px 2px 0}.j10-words b{color:#fff}
.j10-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px;margin-bottom:10px}.j10-grid .j10-card{margin:0;min-width:0}
.j10-wide{grid-column:span 2}
.j10-idx .j10-val{font-size:21px;font-weight:900;margin-top:3px}.j10-idx .j10-sub{font-size:12.5px;color:var(--j10-muted);margin-top:2px}
.j10-idx .j10-mini{margin-top:6px;border:1px solid #ffffff14;border-radius:9px;padding:3px;background:#00112455}
.j10-idx .j10-mini .j10-spark{height:40px}
.j10-pos{display:flex;justify-content:space-between;font-size:11px;color:var(--j10-muted);margin-top:6px}.j10-pos b{font-size:12px}
.j10-flow-amt{font-size:21px;font-weight:900;margin-top:3px}
.j10-flow-sub{font-size:11.5px;color:var(--j10-note);line-height:1.5;margin-top:4px}
.j10-fail{color:#ffb4a8;font-size:13px;line-height:1.5}.j10-cap-plain{color:var(--j10-note);font-size:13px;padding:6px 2px}
.j10-gauge-cell{grid-column:span 2;min-width:0;overflow:hidden}
/* 게이지는 한국테마·미국테마의 상자를 그대로 쓴다. 한국증시는 "사라·쉬어라"를 적지 않으므로 상자 맨 밑 행동 문구
   (「신규 매수 보류」·「조건 충족 종목만 매수 심사」)만 감춘다 — 점수·구간은 그대로 보인다(2026-09-30). */
.j10-regime .fg-box-foot{display:none!important}
.j10-gauge-cell .fg-box-body{gap:6px!important}
.j10-gauge-cell .fg-box-gauge{flex:0 0 112px!important;width:112px!important}
.j10-gauge-cell .fg-box-hist{flex:1 1 auto!important;min-width:0!important;width:auto!important}
.j10-gauge-cell .fg-hist-label{white-space:nowrap!important}
.j10-gauge-cell .fg-box,.j10-gauge-cell .gauge-box{width:100%!important;max-width:none!important;min-width:0!important;margin:0!important}
/* 아래 이동막대 자리 — **미국테마와 같다** (2026-10-01 상하님 — "맨밑에 홈화면과 시장분석이 겹쳐진다 미국테마 확인해봐라").
   온라인 앱은 화면 오른쪽 아래에 스트림릿 표시(얼굴 그림 · 붉은 왕관, 오른쪽 끝에서 약 137px · 높이 46px)를 띄운다.
   그것은 바깥 문서에 있어 이 화면이 덮을 수 없다 — 피해서 놓아야 한다. 미국테마가 그렇게 했다(온라인 실측):
   폰(600px 이하) = 왼쪽 8px 에서 시작 · 폭 화면의 3분의 2(최대 286.667px) · 높이 50 · 바닥에서 4px
   태블릿(601~1200px) = 폭 min(430px, 62vw) · 가운데에서 60px 왼쪽 · 높이 48 · 바닥에서 12px
   PC 는 막대가 가운데 430px 라 표시와 멀다 — 그대로 둔다. 홈을 누르는 자리(.st-key-j10_home_link a)도 같은 숫자를 쓴다. */
:root{--j10-nw:min(430px,calc(100vw - 24px));--j10-nl:calc(50% - var(--j10-nw) / 2);--j10-nb:12px;--j10-nh:64px}
@media (max-width:600px){:root{--j10-nw:min(286.667px,66.667vw);--j10-nl:8px;--j10-nb:4px;--j10-nh:50px}}
@media (min-width:601px) and (max-width:1200px){:root{--j10-nw:min(430px,62vw);--j10-nl:calc(50% - var(--j10-nw) / 2 - 60px);--j10-nb:12px;--j10-nh:48px}}
.j10-nav{position:fixed;z-index:1000;bottom:var(--j10-nb);left:var(--j10-nl);width:var(--j10-nw);height:var(--j10-nh);
display:flex;justify-content:space-around;align-items:center;background:linear-gradient(180deg,#0a2f5cf2,#03162eee);
border:1.6px solid #e2b25ecc;border-radius:20px;box-shadow:0 6px 18px #000a,inset 0 1px #ffd88a44;backdrop-filter:blur(10px)}
.j10-nav-item{display:grid;place-items:center;gap:2px;color:#d6e2f0;font-size:12.5px;font-weight:800;width:33.3%;height:100%;
cursor:pointer;user-select:none;-webkit-tap-highlight-color:transparent}
.j10-nav-item svg{width:26px;height:26px}
@media (max-width:600px){.j10-nav{border-radius:17px}.j10-nav-item{font-size:12px;gap:1px}.j10-nav-item svg{width:23px;height:23px}}
@media (min-width:601px) and (max-width:1200px){.j10-nav{border-radius:19px}.j10-nav-item{font-size:11px;gap:1px}.j10-nav-item svg{width:21px;height:21px}}
.st-key-j10_home_link{position:absolute!important;width:1px!important;height:1px!important;margin:0!important;padding:0!important;gap:0!important}
.st-key-j10_home_link a{position:fixed!important;z-index:1001!important;bottom:var(--j10-nb)!important;left:var(--j10-nl)!important;
width:calc(var(--j10-nw) / 3)!important;height:var(--j10-nh)!important;opacity:0!important;min-height:0!important;margin:0!important}
.st-key-j10_hidden{position:fixed!important;left:-9999px!important;top:-9999px!important;width:1px!important;height:1px!important;overflow:hidden!important}
.st-key-j10_js,[data-testid="stLayoutWrapper"]:has(> .st-key-j10_js){position:absolute!important;width:0!important;height:0!important;overflow:hidden!important;margin:0!important;padding:0!important}
.st-key-j10_row_links{margin-top:-2px}
.st-key-j10_row_links [data-testid="stPageLink"] a{background:#efe3ff!important;border-radius:12px!important;padding:6px 13px!important;
box-shadow:0 2px 8px #0006!important}
.st-key-j10_row_links [data-testid="stPageLink"] a p,.st-key-j10_row_links [data-testid="stPageLink"] a span{color:#4b2a86!important;
font-weight:800!important;font-size:14px!important}
.st-key-j10_row_links{justify-content:space-between!important;align-items:center!important;flex-wrap:nowrap!important;margin-top:10px!important}
.st-key-j10_row_links .j10-row{margin:0!important}
.st-key-j10_row_links [data-testid="stElementContainer"],.st-key-j10_row_links [data-testid="stMarkdownContainer"],
.st-key-j10_row_links [data-testid="stMarkdown"],.st-key-j10_row_links [data-testid="stPageLink"]{margin:0!important;padding:0!important}
.j10-sheet-toggle{position:absolute;opacity:0;pointer-events:none;width:0;height:0}
.j10-sheet-wrap{display:none;position:fixed;inset:0;z-index:1100;background:#010610cc;overflow-y:auto;-webkit-overflow-scrolling:touch;padding:14px 10px 40px}
.j10-sheet-toggle:checked + .j10-sheet-wrap{display:block}
.j10-sheet{max-width:560px;margin:0 auto;background:linear-gradient(180deg,#07203f,#041229);border:1.5px solid #e2b25ecc;border-radius:22px;padding:12px 10px 14px}
.j10-sheet-head{display:flex;justify-content:space-between;align-items:center;padding:4px 6px 10px;position:sticky;top:-14px;z-index:2;
background:linear-gradient(180deg,#07203f,#07203ff0)}
.j10-sheet-head b{font-size:19px;font-weight:900;color:#d8ecff}
.j10-x{width:36px;height:36px;border-radius:50%;border:1px solid #a9c7df;display:grid;place-items:center;background:#062448;color:#fff;cursor:pointer;font-size:17px}
.j10-glance{background:linear-gradient(145deg,#1b2f6b,#0b1e47);border-color:#c084fc88}
.j10-glance-t{color:var(--j10-violet);font-weight:900;font-size:15px;margin-bottom:4px}
.j10-glance ol{margin:0;padding-left:20px;font-size:13.5px;line-height:1.75}.j10-glance b{color:#fff}
.j10-h{font-weight:900;font-size:15px;color:#fff;margin-bottom:6px}.j10-h small{display:inline-block;margin-right:6px;padding:1px 7px;border-radius:7px;
font-size:11px;font-weight:900;vertical-align:1px}
.j10-tag-i{background:#f4c66b33;color:#ffd98f}.j10-tag-s{background:#4da6ff33;color:#9fd0ff}.j10-tag-f{background:#44f0a133;color:#8af5c4}
.j10-vs2{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.j10-vs2>div{background:#ffffff0b;border:1px solid #ffffff17;border-radius:12px;padding:9px 10px}
.j10-vs2 small{display:block;color:var(--j10-muted);font-size:11.5px;font-weight:700}.j10-vs2 b{font-size:27px;font-weight:900;letter-spacing:-.5px}
.j10-vs2 em{display:block;font-style:normal;font-size:11px;color:var(--j10-note);margin-top:2px}
.j10-dots{display:flex;gap:6px;margin:11px 0 4px}.j10-dots i{flex:1;aspect-ratio:1;border-radius:50%;border:2px solid #4da6ff66}
.j10-dots i.hit{background:#ff5b5b;border-color:#ff5b5b;box-shadow:0 0 8px #ff5b5b88}
.j10-dots-cap{font-size:12.5px;color:#dfe7f0}
.j10-hb{display:grid;grid-template-columns:132px 1fr 46px;align-items:center;gap:8px;margin:7px 0;font-size:12.5px}
.j10-hb>div{height:12px;border-radius:6px;background:#ffffff12;overflow:hidden}.j10-hb i{display:block;height:100%;border-radius:6px}
.j10-hb b{text-align:right;font-size:14px}.j10-hb i.kr{background:linear-gradient(90deg,#4da6ff,#7cc0ff)}
.j10-hb i.ix{background:linear-gradient(90deg,#f4c66b,#ffd98f)}.j10-hb i.us{background:linear-gradient(90deg,#44f0a1,#8af5c4)}
.j10-hb i.kr2{background:linear-gradient(90deg,#8b9bb4,#b6c3d6)}
.j10-legend{display:flex;gap:14px;font-size:11.5px;color:var(--j10-muted);margin-bottom:4px}
.j10-legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:4px;vertical-align:-1px}
.j10-legend i.bad,.j10-bar.bad{background:linear-gradient(90deg,#2f7fd6,#4da6ff)}.j10-legend i.mid,.j10-bar.mid{background:#8b9bb4}
.j10-pb{margin:8px 0 10px}.j10-pb-l{font-size:12.5px;font-weight:800;margin-bottom:3px}
.j10-pb-r{display:flex;align-items:center;gap:7px;margin:2px 0}.j10-pb-r .j10-bar{height:9px;border-radius:5px;display:block}
.j10-pb-r b{font-size:12.5px;min-width:46px}
.j10-steps{display:flex;align-items:center;gap:5px}.j10-steps>div{flex:1;background:#ffffff0b;border:1px solid #ffffff17;border-radius:12px;padding:8px 6px;text-align:center}
.j10-steps small{display:block;color:var(--j10-muted);font-size:10.5px;font-weight:700}.j10-steps b{font-size:19px;font-weight:900}
.j10-steps>span{color:var(--j10-muted);font-weight:900}
.j10-papers{margin:0;padding-left:17px;font-size:12.8px;line-height:1.6}.j10-papers li{margin-bottom:7px}.j10-papers b{color:#fff}
.j10-papers small{display:block;color:#7f8a99;font-size:10.5px}
.j10-dont{border-color:#c1975b99;font-size:13px;line-height:1.6;color:#dfe7f0}
.j10-page{touch-action:pan-y pinch-zoom}
@media (max-width:420px){.j10-rb{grid-template-columns:132px 1fr 50px}.j10-big{font-size:31px}}
@media (prefers-reduced-motion:reduce){.j10 *{transition:none!important;animation:none!important}}
"""


def page_css(nonce: str, extra: str = "") -> str:
    """꾸밈 전부. 어느 판이 보이는지는 html 의 data-j10p 가 이번 판 표시와 같을 때만 따른다."""
    m = f'html[data-j10p="market-{nonce}"]'
    nm = f'html:not([data-j10p="market-{nonce}"])'
    warm, cold = f'[data-j10warm="{nonce}"]', f':not([data-j10warm="{nonce}"])'
    # 안 보이는 판은 **자리를 잡아 둔 채 숨긴다** (2026-10-01). 아예 빼 두면(display:none) 처음 넘길 때 그 판
    # 전체의 자리를 그제야 재느라 느린 폰이 0.24~0.37초 멈췄다(온라인 실측 · 칸 637개). 숨긴 판은 흐름 밖
    # (맨 위 0px · 높이 0 · 넘친 것 잘라 냄)에 같은 폭으로 놓여 자리만 재 둔다.
    # 다만 **첫 화면이 그려지기 전에는 빼 둔다** — 두 판이 한꺼번에 오면 숨긴 판의 자리 재기가 첫 화면
    # 그리기에 얹혔다(노트북 느린 폰 1.7초). 첫 화면을 그린 뒤 넘기기 코드가 html 에 data-j10warm 을 단다.
    # 스트림릿 1.59 는 이름 붙인 상자를 겉싸개(stLayoutWrapper)로 한 겹 더 싼다 — 겉싸개를 숨겨야 판 사이
    # 틈(16px)이 하나 더 생기지 않는다. 겉싸개가 없는 판(옛 스트림릿)은 상자를 숨긴다.
    wk = '[data-testid="stLayoutWrapper"]:has(> .st-key-j10_page_kospi)'
    wm = '[data-testid="stLayoutWrapper"]:has(> .st-key-j10_page_market)'
    bk = ':not([data-testid="stLayoutWrapper"]) > .st-key-j10_page_kospi'
    bm = ':not([data-testid="stLayoutWrapper"]) > .st-key-j10_page_market'
    parked = ("position:absolute!important;left:0!important;right:0!important;top:0!important;height:0!important;"
              "min-height:0!important;overflow:hidden!important;visibility:hidden!important;pointer-events:none!important;"
              "margin:0!important;padding:0!important")
    nmc, nmw = f'html{cold}:not([data-j10p="market-{nonce}"])', f'html{warm}:not([data-j10p="market-{nonce}"])'
    mc, mw = f'html{cold}[data-j10p="market-{nonce}"]', f'html{warm}[data-j10p="market-{nonce}"]'
    state = (
        f'{nmc} {wm},{nmc} {bm},{mc} {wk},{mc} {bk}{{display:none!important}}'
        f'{nmw} {wm},{nmw} {bm},{mw} {wk},{mw} {bk}{{{parked}}}'
        '[data-testid="stVerticalBlock"]:has(> [data-testid="stLayoutWrapper"] > .st-key-j10_page_kospi),'
        '[data-testid="stVerticalBlock"]:has(> .st-key-j10_page_kospi){position:relative}'
        f'html:not([data-j10p="market-{nonce}"]) .j10-nav-item[data-go="kospi"],'
        f'{m} .j10-nav-item[data-go="market"]{{color:#b6ff3b;text-shadow:0 0 8px #b6ff3b88}}'
        f'html:not([data-j10p="market-{nonce}"]) .j10-nav-item[data-go="kospi"] svg,'
        f'{m} .j10-nav-item[data-go="market"] svg{{filter:drop-shadow(0 0 5px #b6ff3b)}}'
    )
    return "<style>" + _BASE_CSS.replace("\n", "") + state + extra + "</style>"


# ── 맨 위 그림 ───────────────────────────────────────────────────────────────
def banner_html(monthly, phase: str) -> str:
    stars = "".join(f"<i style='left:{(i * 37) % 97}%;top:{(i * 23) % 61 + 4}%;opacity:{.35 + (i % 5) * .12:.2f}'></i>"
                    for i in range(26))
    line = _banner_line(monthly)
    open_ = phase in ("정규장", "장전 동시호가", "장 마감 동시호가")
    return (
        "<div class='j10'><div class='j10-banner'>"
        f"<div class='j10-stars'>{stars}</div>"
        + (f"<svg class='j10-banner-line' viewBox='0 0 390 150' preserveAspectRatio='none' aria-hidden='true'>"
           f"<polyline points='{line}' fill='none' stroke='#fff' stroke-width='2.2' vector-effect='non-scaling-stroke'/></svg>"
           "<div class='j10-banner-cap'>코스피 지수 30년 (1996~ · 눈금은 곱하기 비율)</div>" if line else "")
        + "<div class='j10-brand'><b>JARVIS</b><em>10</em><span>한국증시</span></div>"
        "<div class='j10-top-btns'><span class='j10-circle' data-j10='refresh' role='button' aria-label='다시 받기'>↻</span>"
        f"<span class='j10-phase{' open' if open_ else ''}'><i></i>{_esc(phase)}</span></div>"
        "</div></div>"
    )


def help_button_html() -> str:
    return ("<div class='j10'><div class='j10-row'>"
            "<label class='j10-help-btn' for='j10-help-toggle' role='button'>📘 한국증시 설명</label></div></div>")


# ── ① 코스피 판 ──────────────────────────────────────────────────────────────
def _fill_pct(pct, span: float = 40.0) -> float:
    return max(2.0, min(100.0, 50 + pct / span * 50))


def _up_text(share: float) -> str:
    if share >= 0.995:
        return f"1,000번 중 {round(share * 1000):,}번"
    return f"100번 중 {round(share * 100)}번"


def kospi_panel_html(data: dict, nonce: str, phase: str) -> str:
    parts = [f"<div class='j10 j10-page' data-page='kospi' data-run='{_esc(nonce)}'>"]
    parts.append("<div class='j10-sec'>코스피 지수 지금</div>")
    card = (data or {}).get("card") or {}
    if card.get("ok"):
        when = f"{_md(card['date'])} · {_esc(phase)}"
        chart, swaps = _chart_swap(card, kr=True, w=150, h=46)
        parts.append(
            f"<div class='j10-card{' j10-tapcard' if swaps else ''}'>" + (_tap(nonce, "hero") if swaps else "")
            + f"<div class='j10-lbl'>코스피 지수 <small>{when}</small></div>"
            "<div class='j10-hero-row'><div>"
            f"<div class='j10-big'>{_num(card['close'])}</div>"
            f"<div class='j10-chg' style='color:{_kr(card['change_pct'])}'>{_pct(card['change_pct'], 2)}</div></div>"
            f"<div class='j10-hero-spark'>{chart}</div></div>"
            "<div class='j10-chips'>"
            f"<span class='j10-chip'><small>고점 대비</small><b style='color:{_kr(card.get('dd_pct'))}'>{_pct(card.get('dd_pct'))}</b></span>"
            f"<span class='j10-chip'><small>200일선보다</small><b style='color:{_kr(card.get('ma_pct'))}'>"
            f"{_pct(card.get('ma_pct'))} {'위' if (card.get('ma_pct') or 0) >= 0 else '아래'}</b></span>"
            f"<span class='j10-chip'><small>고점 ({_md(card.get('high_date', ''))})</small><b>{_num(card.get('high'), 0)}</b></span>"
            "</div></div>")
        dd = card.get("dd_pct") or 0.0
        low_note = ""
        if card.get("low_after_high") and card.get("low_after_high_date") != card.get("high_date"):
            low_note = (f"고점 <b class='j10-key'>{_num(card['high'])}</b>({_md(card['high_date'])}) 뒤 가장 깊었던 날은 "
                        f"{_md(card['low_after_high_date'])}({_pct(card['low_after_high_pct'])})입니다.")
        parts.append(
            "<div class='j10-card'>"
            f"<div class='j10-ndd-head'><b>코스피 지수 고점 대비</b><span class='j10-ndd-val' style='color:{_kr(dd)}'>{_pct(dd)}</span></div>"
            f"<div class='j10-ndd-bar'><span class='j10-ndd-fill' style='width:{_fill_pct(dd):.1f}%'></span><span class='j10-ndd-center'></span></div>"
            "<div class='j10-ndd-scale'><span>고점 −40%</span><span>전고점</span><span>고점 +40%</span></div>"
            + (f"<div class='j10-note'>{low_note}</div>" if low_note else "")
            + "</div>")
    else:
        parts.append("<div class='j10-card'><div class='j10-fail'>코스피 지수 자료를 못 받았습니다. ↻ 를 눌러 다시 받아 주십시오.</div></div>")

    hold = (data or {}).get("hold") or {}
    if hold.get("rows"):
        rows = "".join(
            f"<div class='j10-hr'><span class='j10-hy'>{r['years']}년</span>"
            f"<span class='j10-hbar'><i style='width:{min(r['up'] * 100, 100):.0f}%'></i><em>{_up_text(r['up'])}</em></span>"
            f"<span class='j10-hm' style='color:{_kr(r['median'])}'>{_pct(r['median'])}</span>"
            f"<span class='j10-hw' style='color:{_kr(r['worst'])}'>{_pct(r['worst'], 0)}</span></div>"
            for r in hold["rows"])
        dca = "".join(
            f"<div><small>매달 같은 돈을 {x['years']}년 넣었다면</small>"
            f"<b>100번 중 <span class='j10-up'>{round(x['win'] * 100)}번</span> 벌었다</b>"
            f"<em>가운데 {_pct(x['median'], 0)} · 가장 나쁠 때 {_pct(x['worst'], 0)}</em></div>"
            for x in hold.get("dca", []))
        parts.append(
            f"<div class='j10-sec'>코스피 지수를 오래 들고 있었다면 <small>{_esc(data.get('source', ''))}</small></div>"
            "<div class='j10-card'>"
            "<div class='j10-cap'><b>코스피 지수</b>를 <b>아무 날이나</b> 사서 그 기간 들고 있었을 때 — 수천 날이 쌓인 숫자라 흔들리지 않습니다</div>"
            "<div class='j10-ht'><div class='j10-hr hh'><span>기간</span><span>오른 횟수</span><span>가운데</span><span>가장 나빴을 때</span></div>"
            + rows + "</div>"
            + (f"<div class='j10-split'>{dca}</div>" if dca else "")
            + f"<div class='j10-foot'>{hold.get('start', '')[:4]}년 ~ {hold.get('end', '')[:4]}년 {_md(hold.get('end', ''))} · "
            "배당은 뺐습니다(코스피200 상품으로 들면 해마다 약 1.5%가 더 붙었습니다) · 날마다 새로 셉니다</div></div>")

    rules = (data or {}).get("rules") or {}
    if rules.get("rules"):
        best = max(r["cagr"] for r in rules["rules"])
        top = max(best, 1.0) * 1.08
        bars = "".join(
            f"<div class='j10-rb{' best' if r['name'] == '그냥 들고 있기' else ''}'>"
            f"<span>{_esc(r['name'])}<small>가장 크게 빠짐 {_pct(r['mdd'], 0)}</small></span>"
            f"<div><i style='width:{max(r['cagr'], 0) / top * 100:.0f}%'></i></div><b>{_pct(r['cagr'])}</b></div>"
            for r in rules["rules"])
        held = next((r for r in rules["rules"] if r["name"] == "그냥 들고 있기"), None)
        beaten = held and all(r["cagr"] <= held["cagr"] + 1e-9 for r in rules["rules"])
        verdict = ("사고파는 때를 맞히려는 규칙은 다섯 가지 모두 <b class='j10-up'>그냥 들고 있기</b>를 못 이겼습니다."
                   if beaten else "그냥 들고 있기보다 나은 규칙이 생겼습니다 — 설명서를 다시 봐야 합니다.")
        parts.append(
            "<div class='j10-sec'>코스피200 상품 — 때 맞히기 규칙은 어땠나</div>"
            "<div class='j10-card'>"
            f"<div class='j10-cap'>규칙을 {rules['start'][:4]}년부터 그대로 따랐다면 — <b>해마다 번 돈</b> "
            "(코스피200 상품 KODEX 200 · 배당 넣음 · 바꿀 때 0.1% · 현금 이자 0)</div>"
            + bars
            + f"<div class='j10-easy'><b>쉽게 말해</b> — {verdict} 그래서 이 화면은 \"사라·쉬어라\"를 적지 않습니다.</div>"
            "</div>")
    elif (data or {}).get("rules_error"):
        parts.append("<div class='j10-card'><div class='j10-fail'>코스피200 상품 자료를 못 받았습니다. 잠시 뒤 ↻ 를 눌러 주십시오.</div></div>")

    parts.append(
        "<div class='j10-words'><b>말 뜻</b> — <b>코스피 지수</b>: 한국 종합주가지수 하나(직접은 못 사고 지수를 따라가는 상품으로 삽니다) · "
        "<b>코스피200 상품</b>: KODEX 200 같은 상품(배당이 들어갑니다) · <b>개별 종목</b>: 삼성전자 같은 회사 하나하나의 주식</div>"
        "<div class='j10-decide'>판단은 상하님이 하십니다. 이 화면은 자료만 보여 드립니다.</div>")
    parts.append("</div>")
    return "".join(parts)


# ── ② 시장분석 판 ────────────────────────────────────────────────────────────
def _idx_card(label: str, c: dict, *, kr: bool, sub: str, show_dd: bool = True, nonce: str = "", key: str = "") -> str:
    """지수 한 칸 — **누르면 「당일」↔「6개월」 그림이 같은 자리에서 바뀐다** (2026-10-01 상하님 — "각 지수들 클릭해도
    미국테마처럼 클릭이 안된다"). 미국테마 지수 칸과 같은 장치다(pages/2_자비스3.py _index_chart_swap)."""
    if not c or not c.get("ok"):
        return f"<div class='j10-card j10-idx'><div class='j10-lbl'>{label}</div><div class='j10-fail'>자료를 못 받았습니다</div></div>"
    col = _kr if kr else _us
    chart, swaps = _chart_swap(c, kr=kr, w=140, h=40)
    pos = []
    if show_dd and c.get("dd_pct") is not None:
        pos.append(f"<span>고점 대비 <b style='color:{col(c['dd_pct'])}'>{_pct(c['dd_pct'])}</b></span>")
    if c.get("ma_pct") is not None:
        pos.append(f"<span>200일선 <b style='color:{col(c['ma_pct'])}'>{_pct(c['ma_pct'])}</b></span>")
    return (f"<div class='j10-card j10-idx{' j10-tapcard' if swaps else ''}'>" + (_tap(nonce, key) if swaps else "")
            + f"<div class='j10-lbl'>{label}</div><div class='j10-val'>{_num(c['close'])}</div>"
            f"<div class='j10-sub'><b style='color:{col(c['change_pct'])}'>{_pct(c['change_pct'], 2)}</b> · {sub}</div>"
            f"<div class='j10-mini'>{chart}</div>"
            + (f"<div class='j10-pos'>{''.join(pos)}</div>" if pos else "")
            + "</div>")


def _flow_card(flow: dict | None) -> str:
    """외국인·기관 5일 — 대표 **개별 종목** 둘의 합(시장 전체가 아니다). jarvis10_data.flow_5d."""
    flow = flow or {}
    head = "<div class='j10-lbl'>외국인·기관 5일</div>"
    if not flow.get("ok"):
        return f"<div class='j10-card j10-idx'>{head}<div class='j10-fail'>자료를 못 받았습니다</div></div>"
    def won(eok: float) -> str:        # 1조 넘으면 조로 적어 칸을 짧게
        return f"{eok / 10000:+.1f}조".replace("-", "−") if abs(eok) >= 10000 else f"{eok:+,.0f}억".replace("-", "−")

    f_amt, o_amt = flow["foreign"] / 1e8, flow["organ"] / 1e8
    per = " · ".join(f"{_esc(s['label'])} {won((s['foreign'] + s['organ']) / 1e8)}" for s in flow["stocks"])
    return (f"<div class='j10-card j10-idx'>{head}"
            f"<div class='j10-flow-amt' style='color:{_kr(f_amt + o_amt)}'>{won(f_amt + o_amt)}</div>"
            f"<div class='j10-flow-sub'>외국인 <b style='color:{_kr(f_amt)}'>{won(f_amt)}</b> · "
            f"기관 <b style='color:{_kr(o_amt)}'>{won(o_amt)}</b><br>{per}</div>"
            f"<div class='j10-foot'>{_md(flow['latest'])}까지 5거래일 · 그날 종가로 셈 · "
            "시장 전체가 아니라 대표 개별 종목 둘의 합</div></div>")


def market_panel_html(cards: dict, overview: dict | None, kospi_card: dict | None, nonce: str) -> str:
    import fear_greed_ui
    import regime_gauge_ui

    k = kospi_card or {}
    us_prev = (overview or {}).get("us_prev") or {}
    parts = [f"<div class='j10 j10-page' data-page='market' data-run='{_esc(nonce)}'>",
             "<div class='j10-sec'>한국 <small>코스피 지수 · 코스닥 지수 · 환율 · 수급</small></div><div class='j10-grid'>",
             _idx_card("코스피 지수", k, kr=True, sub=_md(k.get("date", "")) if k else "", nonce=nonce, key="kospi"),
             _idx_card("코스닥 지수", cards.get("KOSDAQ") or {}, kr=True, sub=_md((cards.get("KOSDAQ") or {}).get("date", "")),
                       nonce=nonce, key="kosdaq"),
             _idx_card("원/달러 환율", cards.get("USDKRW") or {}, kr=True, sub=_md((cards.get("USDKRW") or {}).get("date", "")),
                       show_dd=False, nonce=nonce, key="usdkrw"),
             _flow_card(cards.get("FLOW"))]
    if overview and overview.get("ok"):
        parts.append("<div class='j10-gauge-cell j10-regime'>"
                     + regime_gauge_ui.regime_box_html(overview, title="시장 국면 (한국)") + "</div>")
    else:
        parts.append("<div class='j10-card j10-wide'><div class='j10-lbl'>시장 국면 (한국)</div>"
                     "<div class='j10-fail'>자료를 못 받았습니다</div></div>")
    parts.append("</div><div class='j10-sec'>미국 <small>한국장보다 먼저 움직입니다</small></div><div class='j10-grid'>")
    for symbol, label in (("NQ=F", "나스닥100 선물"), ("^IXIC", "나스닥 종합"), ("^GSPC", "S&amp;P 500"), ("^DJI", "다우존스")):
        c = cards.get(symbol) or {}
        sub = ("선물 · " if symbol == "NQ=F" else "") + _md(c.get("date", "")) + (" 장 마감" if symbol != "NQ=F" else "")
        parts.append(_idx_card(label, c, kr=False, sub=sub, nonce=nonce, key="".join(ch for ch in symbol if ch.isalnum()).lower()))
    parts.append("<div class='j10-gauge-cell j10-regime'>"
                 + regime_gauge_ui.regime_box_html(us_prev.get("market_overview"), title="(미국) 시장 국면", note_prefix=" : ")
                 + "</div>")
    parts.append("<div class='j10-gauge-cell'>"
                 + fear_greed_ui.box_html(us_prev.get("fear_greed_detail"), title="(미국) 공포·탐욕 지수") + "</div>")
    parts.append("</div><div class='j10-foot center'>미국 두 게이지와 한국 시장 국면은 미국테마·한국테마와 같은 계산입니다</div></div>")
    # 게이지 조각에 줄바꿈이 섞여 오면 글 칸(markdown)이 빈 줄에서 HTML 을 끊는다 — 한 줄로 만든다.
    return "".join(parts).replace(chr(10), " ")


def market_loading_html(nonce: str) -> str:
    """시장분석 판 자리 — 자료를 받는 동안 넘겨도 빈 화면이 아니게 한다(받으면 이 자리에 진짜 판이 들어간다)."""
    return (f"<div class='j10 j10-page' data-page='market' data-run='{_esc(nonce)}'>"
            "<div class='j10-sec'>한국 <small>코스피 지수 · 코스닥 지수 · 환율 · 수급</small></div>"
            "<div class='j10-card'><div class='j10-cap-plain'>시장분석 자료를 받는 중입니다…</div></div></div>")


def gauge_css() -> str:
    import fear_greed_ui
    import gauge_ui

    return gauge_ui.CSS + fear_greed_ui.CSS


# ── ③ 한국증시 설명 창 (2026-09-30 에 잰 값 — 상장폐지 포함 연구라 화면에서 다시 셀 수 없다) ──
def _pair_bar(label: str, bad: float, mid: float) -> str:
    w = lambda v: min(100, abs(v) / 11 * 100)   # noqa: E731
    return (f"<div class='j10-pb'><div class='j10-pb-l'>{label}</div>"
            f"<div class='j10-pb-r'><span class='j10-bar bad' style='width:{w(bad):.0f}%'></span><b class='j10-down'>{_pct(bad)}</b></div>"
            f"<div class='j10-pb-r'><span class='j10-bar mid' style='width:{w(mid):.0f}%'></span><b class='j10-muted'>{_pct(mid)}</b></div></div>")


TAG_I = "<small class='j10-tag-i'>코스피 지수</small>"
TAG_S = "<small class='j10-tag-s'>개별 종목</small>"
TAG_F = "<small class='j10-tag-f'>코스피200 상품</small>"


def help_sheet_html() -> str:
    dots = "".join(f"<i class='{'hit' if i == 0 else ''}'></i>" for i in range(10))
    body = (
        "<div class='j10-card j10-glance'><div class='j10-glance-t'>한눈에</div><ol>"
        "<li><b>한국 개별 종목은 대부분 빠졌습니다</b> — 코스피 지수가 오를 때도.</li>"
        "<li><b>개별 종목을 어떻게 골라도 코스피 지수를 못 이겼습니다</b> — 신고가 눌림·급락 종목·싼 종목 모두.</li>"
        "<li><b>코스피 지수는 '언제'보다 '얼마나 오래'</b> — 사고파는 때를 맞히는 규칙은 그냥 들고 있기를 못 이겼습니다.</li></ol></div>"

        f"<div class='j10-card'><div class='j10-h'>{TAG_S}① 12년 동안 한 번 사서 들고 있었다면</div>"
        "<div class='j10-cap'>2014년 7월에 거래되던 개별 종목 1,743개 · 그 뒤 상장폐지된 266개 포함 · 2026년 9월까지</div>"
        "<div class='j10-vs2'><div><small>코스피 지수</small><b class='j10-up'>+243%</b></div>"
        "<div><small>개별 종목 가운데</small><b class='j10-down'>−23%</b></div></div>"
        f"<div class='j10-dots'>{dots}</div>"
        "<div class='j10-dots-cap'>코스피 지수를 이긴 개별 종목 <b class='j10-up'>10개 중 1개</b> · 반토막 넘게 난 개별 종목 "
        "<b class='j10-down'>10개 중 3.6개</b></div>"
        "<div class='j10-foot'>2024년 말에서 끊어도 코스피 지수 +20% · 개별 종목 가운데 −21%</div></div>"

        f"<div class='j10-card'><div class='j10-h'>② 아무거나 사서 1년 들면 — 오른 횟수 (100번 중)</div>"
        "<div class='j10-hb'><span>한국 개별 종목</span><div><i style='width:38%' class='kr'></i></div><b>38번</b></div>"
        "<div class='j10-hb'><span>코스피 지수</span><div><i style='width:63%' class='ix'></i></div><b>63번</b></div>"
        "<div class='j10-hb'><span>미국 대형 개별 종목*</span><div><i style='width:71%' class='us'></i></div><b>71번</b></div>"
        "<div class='j10-foot'>* 미국은 지금 살아 있는 대형 개별 종목 198개로 잰 것이라 실제보다 좋게 나옵니다</div></div>"

        f"<div class='j10-card'><div class='j10-h'>{TAG_S}③ 많이 오른 개별 종목을 따라 사면</div>"
        "<div class='j10-vs2'><div><small>6개월 많이 오른 20% · 1년 뒤</small><b class='j10-down'>−17.1%</b></div>"
        "<div><small>나머지 · 1년 뒤</small><b class='j10-muted'>−10.6%</b></div></div>"
        "<div class='j10-note'>한국은 오른 개별 종목이 계속 오르지 않고 <b class='j10-key'>되돌아왔습니다.</b> 미국 나스닥은 반대로 많이 오른 종목이 더 나았습니다.</div></div>"

        f"<div class='j10-card'><div class='j10-h'>{TAG_S}④ 사면 안 되는 개별 종목 다섯 가지 — 두세 달 뒤 가운데</div>"
        "<div class='j10-legend'><span><i class='bad'></i>가장 심한 20%</span><span><i class='mid'></i>보통 개별 종목</span></div>"
        + _pair_bar("하루 오르내림이 심한 개별 종목", -10.7, -3.4)
        + _pair_bar("한 달 안에 하루 확 튄 개별 종목", -9.1, -3.6)
        + _pair_bar("한 달 새 많이 오른 개별 종목", -7.5, -2.9)
        + _pair_bar("회사 실력에 비해 비싼 개별 종목", -7.5, -4.3)
        + _pair_bar("거래가 갑자기 몰린 개별 종목", -6.5, -2.6)
        + "<div class='j10-foot'>상장폐지 포함 3,011개 · 2014~2026 · 비싼 종목은 시가총액 대비 영업이익·장부가·매출로 셈(2015~ 사업보고서)</div></div>"

        f"<div class='j10-card'><div class='j10-h'>{TAG_S}⑤ 싼 개별 종목을 골라도 — 두세 달 뒤 평균</div>"
        "<div class='j10-vs2'><div><small>싼 20% + 큰 회사</small><b class='j10-up'>+2.2%</b></div>"
        "<div><small>같은 날 코스피 지수</small><b class='j10-up'>+3.6%</b></div></div>"
        "<div class='j10-note'>논문에서 가장 강했던 기준입니다. 싼 개별 종목이 비싼 개별 종목보다는 뚜렷이 나았지만(1년 뒤 −8% vs −23%) "
        "<b class='j10-key'>코스피 지수는 못 이겼습니다.</b></div></div>"

        f"<div class='j10-card'><div class='j10-h'>{TAG_I}⑥ 코스피 지수가 오른 몫은 몇 달에 몰렸다</div>"
        "<div class='j10-steps'><div><small>12년 그대로</small><b class='j10-up'>+243%</b></div><span>→</span>"
        "<div><small>좋은 5달 빼면</small><b class='j10-up'>+15%</b></div><span>→</span>"
        "<div><small>좋은 10달 빼면</small><b class='j10-down'>−35%</b></div></div>"
        "<div class='j10-note'>30년(357달)으로 봐도 +954%가 좋은 10달을 빼면 +3%. <b class='j10-key'>그 몇 달은 미리 알 수 없었습니다.</b></div></div>"

        f"<div class='j10-card'><div class='j10-h'>{TAG_I}⑦ 빠질 때 기다렸다 사기 vs 매달 사기 — 10년</div>"
        "<div class='j10-cap'>코스피 지수에 매달 같은 돈을 넣어 10년에 120을 넣었다면 (238가지 시작 달의 가운데)</div>"
        f"<div class='j10-hb'><span>매달 사기</span><div><i style='width:{160 / 180 * 100:.0f}%' class='ix'></i></div><b>160</b></div>"
        f"<div class='j10-hb'><span>−15% 기다리기</span><div><i style='width:{159 / 180 * 100:.0f}%' class='kr2'></i></div><b>159</b></div>"
        f"<div class='j10-hb'><span>−20% 기다리기</span><div><i style='width:{155 / 180 * 100:.0f}%' class='kr2'></i></div><b>155</b></div>"
        f"<div class='j10-hb'><span>−30% 기다리기</span><div><i style='width:{162 / 180 * 100:.0f}%' class='kr2'></i></div><b>162</b></div>"
        "<div class='j10-note'>결과가 거의 같았습니다. 싸게 산 덕을, 기다리는 동안 놓친 오름이 지웠습니다.</div></div>"

        f"<div class='j10-card'><div class='j10-h'>{TAG_F}⑧ 200일선으로 사고팔면 — 배당 넣고 19년</div>"
        "<div class='j10-vs2'><div><small>그냥 들고 있기</small><b class='j10-up'>+12.1%</b><em>해마다 · 가장 크게 빠짐 −41%</em></div>"
        "<div><small>200일선 위일 때만</small><b class='j10-up'>+10.2%</b><em>해마다 · 가장 크게 빠짐 −41%</em></div></div>"
        "<div class='j10-note'>덜 벌었고 크게 빠진 폭도 같았습니다. 2026년 7월처럼 <b class='j10-key'>선 위에서 갑자기 터지는 폭락은 못 막았습니다.</b></div></div>"

        "<div class='j10-card'><div class='j10-h'>⑨ 논문도 같은 말을 합니다</div><ul class='j10-papers'>"
        "<li>한국 개별 종목은 오른 종목이 이어 오르기보다 <b>되돌아오는 쪽이 우세</b> (1983~2023)<small>Investment Analysts Journal, 2024</small></li>"
        "<li>하루 크게 튄 <b>복권 같은 개별 종목은 뒤에 빠진다</b> — 개인 거래가 70~87%인 한국에서 뚜렷<small>Applied Economics, 2022 외</small></li>"
        "<li><b>많이 흔들리는 개별 종목은 뒤 수익이 낮다</b> — 개인 비중이 높을수록 심함<small>한국증권학회지, 2018</small></li>"
        "<li>코스닥 전환사채 발행 기업 204곳은 <b>2~3년 뒤 크게 부진</b> (2016~2020)<small>China Finance Review International</small></li>"
        "<li>52주 신고가 전략 — <b>미국(나스닥 포함)에선 통했고</b>, 20개 나라 중 뚜렷했던 곳은 10곳 · <b>한국은 아니었다</b>"
        "<small>Journal of Finance, 2004 · J. of International Money and Finance, 2011</small></li></ul></div>"

        "<div class='j10-card j10-dont'><div class='j10-h'>이 화면이 하지 않는 일</div>"
        "<div>사라·팔아라를 말하지 않습니다 · 얼마를 살지 정하지 않습니다 · 개별 종목을 추천하지 않습니다 · 판단은 상하님이 하십니다.</div></div>"
        "<div class='j10-foot center'>①~⑧ 은 2026년 9월 30일에 잰 값입니다 · 자료 — 네이버 일봉(수정주가) · 한국거래소 상장폐지 목록 · "
        "FinanceData/marcap 시가총액 · DART 사업보고서 · 야후 코스피 지수(1996~) · KODEX 200(2007~, 배당 넣음)</div>"
    )
    return ("<div class='j10'><input type='checkbox' id='j10-help-toggle' class='j10-sheet-toggle'>"
            "<div class='j10-sheet-wrap'><div class='j10-sheet'>"
            "<div class='j10-sheet-head'><b>📘 한국증시 설명</b><label class='j10-x' for='j10-help-toggle' role='button' aria-label='닫기'>✕</label></div>"
            + body + "</div></div></div>")


# ── 아래 이동막대 ────────────────────────────────────────────────────────────
_NAV_ICONS = (
    ("home", "홈", "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M4 11 12 4l8 7v9h-5v-6H9v6H4z' fill='none' "
                   "stroke='currentColor' stroke-width='2' stroke-linejoin='round'/></svg>"),
    ("kospi", "코스피", "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M3 18l5-6 4 3 6-8 3 3' fill='none' "
                       "stroke='currentColor' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'/></svg>"),
    ("market", "시장분석", "<svg viewBox='0 0 24 24' aria-hidden='true'><circle cx='12' cy='12' r='8.5' fill='none' "
                         "stroke='currentColor' stroke-width='2'/><path d='M12 3.5V12h8.5A8.5 8.5 0 0 0 12 3.5z' fill='currentColor'/></svg>"),
)


def nav_html() -> str:
    items = "".join(f"<div class='j10-nav-item' data-go='{k}' role='button'>{icon}<span>{label}</span></div>"
                    for k, label, icon in _NAV_ICONS)
    return f"<div class='j10'><nav class='j10-nav'>{items}</nav></div>"


# ── 손가락 넘기기 (바깥 문서에서 돈다) ──────────────────────────────────────────
# 자비스3 의 「앞으로 넘어오며 말리는 종이」와 같은 모양·같은 숫자(원근 1500 · 끝 0.3 · 더 말림 1.25 · 그늘 56).
# 다른 점 — 다음 판이 **이미 폰에 그려져 있다.** 그래서 사진을 떠 두지 않는다. 지금 판(진짜 화면)을 돌리고,
# 말리는 끝만 한 벌 베껴 얹는다. 서버에는 한 번도 안 묻는다(홈으로 갈 때만 링크를 누른다).
SWIPE_JS = r"""
(function () {
  var VER = 'j10-2';
  var w = window, d = document;
  if (w.__j10 && w.__j10.ver === VER) { return; }
  if (w.__j10 && w.__j10.off) { try { w.__j10.off(); } catch (e) {} }
  var api = { ver: VER, alive: true };
  w.__j10 = api;
  var DEPTH = 1500, CURL = 0.3, BEND = 1.25, CAST = 56;
  var still = false;
  try { still = w.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}

  function live(sel) {
    var all = d.querySelectorAll(sel);
    for (var i = 0; i < all.length; i++) {
      if (!all[i].closest('[data-stale="true"]') && !all[i].closest('.j10-clone')) { return all[i]; }
    }
    return null;
  }
  function box(p) { return live('.st-key-j10_page_' + p); }
  function nonce() {
    var pg = live('.j10-page[data-run]');
    return pg ? pg.getAttribute('data-run') : '';
  }
  function onPage() { return !!box('kospi'); }
  function current() {
    return d.documentElement.getAttribute('data-j10p') === 'market-' + nonce() ? 'market' : 'kospi';
  }
  function show(p) {
    d.documentElement.setAttribute('data-j10p', p + '-' + nonce());
  }
  function scroller(from) {
    for (var n = from && from.parentElement; n && n !== d.body; n = n.parentElement) {
      var how = '';
      try { how = getComputedStyle(n).overflowY; } catch (e) {}
      if ((how === 'auto' || how === 'scroll') && n.scrollHeight > n.clientHeight + 4) { return n; }
    }
    return null;
  }
  function toTopOf(el) {
    try {
      var r = el.getBoundingClientRect();
      if (r.top >= 0) { return; }
      var sc = scroller(el);
      // 넘기는 동안 다음 판을 화면 맨 위(0px)에 깔았으므로 끝나도 그 자리에 둔다 — 튀지 않게.
      if (sc) { sc.scrollTop += r.top; } else { w.scrollBy(0, r.top); }
    } catch (e) {}
  }
  function clickHome() {
    var a = live('.st-key-j10_home_link a');
    if (a) { a.click(); }
  }

  // ── 종이 모양 계산 (자비스3 과 같은 식) ──
  function outerX(W, c, th) {
    var xb = W - c, dl = th * BEND;
    function proj(x, z) { return W + (x - W) * DEPTH / (DEPTH - z); }
    var bend = proj(xb * Math.cos(th), xb * Math.sin(th));
    if (c <= 0) { return bend; }
    var ex = xb * Math.cos(th) + c * Math.cos(th + dl);
    var ez = xb * Math.sin(th) + c * Math.sin(th + dl);
    return Math.max(bend, proj(ex, ez));
  }
  function angleFor(W, c, dist) {
    var target = W - dist, lo = 0, hi = Math.PI / 2;
    for (var i = 0; i < 16; i++) {
      var mid = (lo + hi) / 2;
      if (outerX(W, c, mid) > target) { lo = mid; } else { hi = mid; }
    }
    return (lo + hi) / 2;
  }
  function pageTf(s, W, th) {
    return 'translateX(' + (-s * W) + 'px) perspective(' + DEPTH + 'px) translateX(' + (s * W) + 'px) '
      + 'rotateY(' + (s * th).toFixed(4) + 'rad)';
  }
  function edgeTf(s, W, c, th) {
    var xb = W - c;
    return pageTf(s, W, th) + ' translateX(' + (-s * xb) + 'px) rotateY(' + (s * th * BEND).toFixed(4)
      + 'rad) translateX(' + (s * xb) + 'px)';
  }

  // ── 한 번의 넘김 ──
  var g = null;          // 지금 넘기는 중인 것
  var UNDER_KEYS = ['display', 'position', 'left', 'right', 'top', 'width', 'height', 'overflow', 'visibility', 'z-index',
    'background', 'pointer-events'];
  function imp(el, props) {
    for (var k in props) { if (props.hasOwnProperty(k)) { el.style.setProperty(k, props[k], 'important'); } }
  }
  function edgeCopy(face, rect, vh) {
    var page = face.querySelector('.j10-page');
    if (!page) { return null; }
    var shell = page.cloneNode(false);           // .j10 .j10-page — 꾸밈 이름은 그대로 두고 속은 비운다
    var cs = getComputedStyle(page);
    shell.style.cssText = 'font-size:' + cs.fontSize + ';line-height:' + cs.lineHeight + ';font-family:'
      + cs.fontFamily + ';color:' + cs.color + ';';
    var kids = page.children;
    for (var i = 0; i < kids.length; i++) {
      var r = kids[i].getBoundingClientRect();
      if (!r.height || r.bottom < -40 || r.top > vh + 40) { continue; }
      var c = kids[i].cloneNode(true);
      c.style.position = 'absolute'; c.style.left = (r.left - rect.left) + 'px'; c.style.top = (r.top - rect.top) + 'px';
      c.style.width = r.width + 'px'; c.style.margin = '0'; c.style.boxSizing = 'border-box';
      shell.appendChild(c);
    }
    return shell;
  }
  function fixedBox(rect, z) {
    var el = d.createElement('div');
    el.setAttribute('aria-hidden', 'true');
    el.className = 'j10-fx';
    el.style.cssText = 'position:fixed;left:' + rect.left + 'px;top:' + rect.top + 'px;width:' + rect.width
      + 'px;height:' + rect.height + 'px;pointer-events:none;z-index:' + z + ';';
    return el;
  }
  function begin(sign, to) {
    var face = box(current());
    if (!face) { return null; }
    var rect = face.getBoundingClientRect();
    var W = rect.width, c = Math.round(W * CURL);
    var vh = w.innerHeight || d.documentElement.clientHeight || 800;
    var oy = Math.max(0, Math.min(rect.height, vh / 2 - rect.top));
    var origin = (sign < 0 ? '0px ' : W + 'px ') + oy + 'px';
    var st = { sign: sign, to: to, W: W, c: c, rect: rect, face: face, origin: origin, parts: [] };
    // 밑에 다음 판 — 이미 그려져 있다. 화면 위쪽에 맞춰 잠깐 띄워 둔다(맨 위부터 보인다).
    var top = Math.max(rect.top, 0);
    var under;
    if (to === 'home') {
      under = fixedBox({ left: rect.left, top: top, width: W, height: vh - top }, 3);
      under.style.background = '#031023';
      face.parentElement.insertBefore(under, face);
      st.parts.push(under);
    } else {
      var inner = box(to);
      if (!inner || !inner.querySelector('.j10-page')) { return null; }
      // 다음 판은 자리를 잡아 둔 채 숨어 있다(겉싸개째) — 넘기는 동안만 같은 폭으로 화면 위에 띄운다.
      var pw = inner.parentElement;
      under = (pw && pw.getAttribute('data-testid') === 'stLayoutWrapper') ? pw : inner;
      imp(under, { display: 'flex', position: 'fixed', left: rect.left + 'px', right: 'auto', top: top + 'px', width: W + 'px',
        height: (vh - top) + 'px', overflow: 'hidden', visibility: 'visible', 'z-index': '3',
        background: '#031023', 'pointer-events': 'none' });
    }
    st.under = under;
    // 지금 판(진짜 화면)을 들어 올린다 — 말리는 끝(폭의 3할)은 잘라 내고 따로 얹는다.
    var fs = face.style;
    fs.position = 'relative'; fs.zIndex = '5'; fs.transformOrigin = origin; fs.willChange = 'transform';
    fs.backfaceVisibility = 'hidden'; fs.transition = 'none';
    // 넘어오는 종이는 **비치지 않는다** — 카드 사이 빈 곳이 투명하면 밑의 다음 판 글자가 겹쳐 보였다(2026-09-30 실측).
    fs.background = '#031023';
    fs.clipPath = sign < 0 ? 'inset(0 ' + c + 'px 0 0)' : 'inset(0 0 0 ' + c + 'px)';
    // 말리는 끝 — 지금 판에서 **화면에 보이는 칸만** 베껴 같은 자리에 얹는다(판 전체를 베끼면 느린 폰이
    // 그 칸들의 자리를 다 새로 쟀다). 못 베끼면 예전처럼 통째로 베낀다.
    var edge = edgeCopy(face, rect, vh);
    if (!edge) {
      edge = face.cloneNode(true);
      edge.className = edge.className.replace(/st-key-\S+/g, '');
    }
    edge.classList.add('j10-clone');
    edge.setAttribute('aria-hidden', 'true');
    var es = edge.style;
    es.position = 'fixed'; es.left = rect.left + 'px'; es.top = rect.top + 'px'; es.width = W + 'px';
    es.height = rect.height + 'px'; es.margin = '0'; es.zIndex = '6'; es.pointerEvents = 'none';
    es.transformOrigin = origin; es.transition = 'none'; es.willChange = 'transform';
    es.clipPath = sign < 0 ? 'inset(0 0 0 ' + (W - c) + 'px)' : 'inset(0 ' + (W - c) + 'px 0 0)';
    es.background = '#041a36';
    face.parentElement.insertBefore(edge, face.nextSibling);
    st.edge = edge; st.parts.push(edge);
    // 빛과 그늘 — 종이 면의 어둠, 접힌 자리의 빛, 종이 끝 밖의 그늘.
    var toEdge = sign < 0 ? 'to right' : 'to left';
    var shade = fixedBox(rect, 7);
    shade.style.transformOrigin = origin;
    shade.style.clipPath = fs.clipPath;
    shade.style.backgroundImage = 'linear-gradient(' + toEdge + ',rgba(0,0,0,0) 0%,rgba(0,0,0,.30) 100%)';
    shade.style.backgroundSize = (W - c) + 'px 100%';
    shade.style.backgroundRepeat = 'no-repeat';
    shade.style.backgroundPosition = sign < 0 ? '0 0' : c + 'px 0';
    shade.style.opacity = '0';
    var gloss = fixedBox(rect, 8);
    gloss.style.transformOrigin = origin;
    gloss.style.clipPath = es.clipPath;
    gloss.style.backgroundImage = 'linear-gradient(' + toEdge + ',rgba(0,0,0,.32) 0%,rgba(255,255,255,.26) 12%,'
      + 'rgba(255,255,255,.08) 32%,rgba(0,0,0,.14) 64%,rgba(0,0,0,.46) 100%)';
    gloss.style.backgroundSize = c + 'px 100%';
    gloss.style.backgroundRepeat = 'no-repeat';
    gloss.style.backgroundPosition = sign < 0 ? (W - c) + 'px 0' : '0 0';
    gloss.style.opacity = '0';
    var cast = fixedBox({ left: rect.left, top: Math.max(rect.top, 0), width: CAST, height: vh }, 4);
    cast.style.backgroundImage = 'linear-gradient(' + toEdge + ',rgba(0,0,0,.5),rgba(0,0,0,0))';
    cast.style.opacity = '0';
    face.parentElement.insertBefore(shade, edge.nextSibling);
    face.parentElement.insertBefore(gloss, shade.nextSibling);
    face.parentElement.insertBefore(cast, gloss.nextSibling);
    st.shade = shade; st.gloss = gloss; st.cast = cast;
    st.parts.push(shade, gloss, cast);
    return st;
  }
  function place(st, th, ms) {
    var s = st.sign, W = st.W, c = st.c;
    var tr = ms ? 'transform ' + ms + 'ms cubic-bezier(.3,.55,.3,1),opacity ' + ms + 'ms ease' : 'none';
    var p = Math.min(1, th / (Math.PI / 2));
    var tf = pageTf(s, W, th), etf = edgeTf(s, W, c, th);
    st.face.style.transition = tr; st.face.style.transform = tf;
    st.shade.style.transition = tr; st.shade.style.transform = tf; st.shade.style.opacity = String(p);
    st.edge.style.transition = tr; st.edge.style.transform = etf;
    st.gloss.style.transition = tr; st.gloss.style.transform = etf; st.gloss.style.opacity = String(Math.min(1, p * 1.8));
    var out = outerX(W, c, th);
    var x = s < 0 ? st.rect.left + out : st.rect.left + W - out - CAST;
    st.cast.style.transition = ms ? 'opacity ' + ms + 'ms ease' : 'none';
    if (!ms) { st.cast.style.left = x.toFixed(1) + 'px'; }
    st.cast.style.opacity = ms ? '0' : String(Math.min(1, p * 2.5));
  }
  function cleanup(st) {
    if (!st) { return; }
    var fs = st.face.style;
    fs.transform = ''; fs.transition = ''; fs.clipPath = ''; fs.transformOrigin = ''; fs.willChange = '';
    fs.position = ''; fs.zIndex = ''; fs.backfaceVisibility = ''; fs.background = '';
    for (var i = 0; i < st.parts.length; i++) {
      try { st.parts[i].remove(); } catch (e) {}
    }
    if (st.under && st.to !== 'home') {
      var us = st.under.style;
      UNDER_KEYS.forEach(function (k) { us.removeProperty(k); });
    }
  }
  function finish(st) {
    var MS = still ? 0 : 300;
    if (MS) { place(st, Math.PI / 2, MS); }
    setTimeout(function () {
      if (st.to === 'home') { cleanup(st); clickHome(); return; }
      var wasAbove = st.rect.top < 0;
      show(st.to);
      cleanup(st);
      if (wasAbove) { toTopOf(box(st.to)); }
      g = null;
    }, MS + 20);
  }
  function settle(st) {
    if (still) { cleanup(st); g = null; return; }
    place(st, 0, 260);
    setTimeout(function () { cleanup(st); g = null; }, 290);
  }
  // 이동막대에서 누르면 — 같은 모양으로 저절로 넘어간다.
  function go(to) {
    if (g || !onPage()) { return; }
    var now = current();
    if (to === now) { toTopOf(box(now)); return; }
    // 서버를 막 켠 직후에는 시장분석 판이 아직 안 왔을 수 있다 — 그때는 아무것도 안 한다(빈 화면 방지).
    if (!box(to) || !box(to).querySelector('.j10-page')) { return; }
    var sign = (to === 'market') ? -1 : 1;
    if (still) { show(to); toTopOf(box(to)); return; }
    var st = begin(sign, to);
    if (!st) { show(to); return; }
    g = st;
    place(st, 0, 0);
    requestAnimationFrame(function () { requestAnimationFrame(function () {
      place(st, Math.PI / 2, 460);
      setTimeout(function () {
        var wasAbove = st.rect.top < 0;
        show(to); cleanup(st); if (wasAbove) { toTopOf(box(to)); } g = null;
      }, 480);
    }); });
  }
  function target(dx) {
    var now = current();
    if (dx < 0) { return now === 'kospi' ? 'market' : 'home'; }
    return now === 'market' ? 'kospi' : 'home';
  }
  function sideways(node) {
    while (node && node !== d.documentElement) {
      try {
        if (node.scrollWidth > node.clientWidth + 4) {
          var how = getComputedStyle(node).overflowX;
          if (how === 'auto' || how === 'scroll') { return true; }
        }
      } catch (e) { return false; }
      node = node.parentElement;
    }
    return false;
  }

  // ── 손가락 ──
  var t = null;          // 닿은 손가락
  var quietUntil = 0;    // 넘기다 손을 뗀 직후의 누름은 지수 칸 누름으로 치지 않는다
  function onStart(ev) {
    if (!api.alive || g || !ev.touches || ev.touches.length !== 1 || !onPage()) { t = null; return; }
    var el = ev.target;
    if (!el || !el.closest || !el.closest('.st-key-j10_page_kospi,.st-key-j10_page_market')) { t = null; return; }
    if (el.closest('.j10-sheet-wrap') || sideways(el)) { t = null; return; }
    var p = ev.touches[0];
    t = { x0: p.clientX, y0: p.clientY, t0: Date.now(), mode: '', st: null, lastX: p.clientX, lastT: Date.now(), v: 0 };
  }
  function onMove(ev) {
    if (!t || !ev.touches || !ev.touches.length) { return; }
    var p = ev.touches[0], dx = p.clientX - t.x0, dy = p.clientY - t.y0;
    if (!t.mode) {
      if (Math.abs(dx) < 12 && Math.abs(dy) < 12) { return; }
      if (Math.abs(dx) < Math.abs(dy) * 1.2) { t.mode = 'scroll'; return; }
      t.mode = 'turn';
      var st = begin(dx < 0 ? -1 : 1, target(dx));
      if (!st) { t = null; return; }
      g = t.st = st;
    }
    if (t.mode !== 'turn' || !t.st) { return; }
    var now = Date.now();
    t.v = (p.clientX - t.lastX) / Math.max(1, now - t.lastT);
    t.lastX = p.clientX; t.lastT = now;
    var dist = Math.max(0, t.st.sign < 0 ? -dx : dx);
    place(t.st, angleFor(t.st.W, t.st.c, Math.min(dist, t.st.W)), 0);
  }
  function onEnd() {
    if (!t) { return; }
    var tt = t; t = null;
    if (tt.mode === 'turn') { quietUntil = Date.now() + 450; }
    if (tt.mode !== 'turn' || !tt.st) { return; }
    var dist = Math.max(0, tt.st.sign < 0 ? tt.x0 - tt.lastX : tt.lastX - tt.x0);
    var fling = (tt.st.sign < 0 ? -tt.v : tt.v) > 0.45;
    if (dist > tt.st.W * 0.3 || (fling && dist > 30)) { finish(tt.st); } else { settle(tt.st); }
  }
  function onClick(ev) {
    // 손이 한 누름만 막는다 — 넘기기 코드가 스스로 누르는 홈·↻ 는 그대로 간다.
    if (ev.isTrusted && Date.now() < quietUntil) { ev.preventDefault(); ev.stopPropagation(); return; }
    var el = ev.target && ev.target.closest ? ev.target.closest('[data-go],[data-j10="refresh"]') : null;
    if (!el || !onPage()) { return; }
    if (el.getAttribute('data-j10') === 'refresh') {
      var b = live('.st-key-j10_refresh button');
      if (b) { b.click(); }
      return;
    }
    var to = el.getAttribute('data-go');
    if (to === 'kospi' || to === 'market') { ev.preventDefault(); go(to); }
  }
  d.addEventListener('touchstart', onStart, { passive: true, capture: true });
  d.addEventListener('touchmove', onMove, { passive: true, capture: true });
  d.addEventListener('touchend', onEnd, { passive: true, capture: true });
  d.addEventListener('touchcancel', onEnd, { passive: true, capture: true });
  d.addEventListener('click', onClick, true);
  api.off = function () {
    api.alive = false;
    d.removeEventListener('touchstart', onStart, { capture: true });
    d.removeEventListener('touchmove', onMove, { capture: true });
    d.removeEventListener('touchend', onEnd, { capture: true });
    d.removeEventListener('touchcancel', onEnd, { capture: true });
    d.removeEventListener('click', onClick, true);
  };
  // 숨긴 판의 자리 재기는 **첫 화면을 그린 뒤**에 켠다 — 시장분석 판이 다 온 것을 보고, 두 장을 그린 다음,
  // 손가락이 닿아 있지 않을 때. 화면을 새로 열 때마다(이번 판 표시가 바뀔 때마다) 한 번씩 한다.
  var warmTimer = 0, warmTries = 0;
  function warm() {
    clearTimeout(warmTimer);
    if (!api.alive) { return; }
    // 화면을 여는 도중 스트림릿이 한 번 다시 그리면 그 순간 판이 「옛것」으로 표시된다 — 그때도 그만두지 않고
    // 기다린다(그만두면 이번 판은 끝까지 자리를 안 재 두었다 · 2026-10-01 노트북). 24초 뒤에는 그만둔다.
    var n = onPage() ? nonce() : '';
    if (n && d.documentElement.getAttribute('data-j10warm') === n) { return; }
    var mk = n ? box('market') : null;
    if (!mk || !mk.querySelector('.j10-grid') || t || g) {
      if (warmTries++ < 80) { warmTimer = setTimeout(warm, 300); }
      return;
    }
    requestAnimationFrame(function () { requestAnimationFrame(function () {
      if (t || g) { warmTimer = setTimeout(warm, 300); return; }
      d.documentElement.setAttribute('data-j10warm', n);
    }); });
  }
  api.warm = function () { warmTries = 0; warm(); };
  api.go = go; api.current = current;
  warm();
})();
"""


def inject_js(st) -> None:
    """넘기기 코드를 **바깥 문서**에 한 번 심는다(자비스3 과 같은 방식 — 작은 창은 심부름만 한다)."""
    try:
        import streamlit.components.v1 as components

        # 자리를 차지하지 않는 상자에 담는다(.st-key-j10_js) — 판과 판 사이에 틈이 하나 더 생기지 않게.
        with st.container(key="j10_js"):
            _inject_frame(components)
    except Exception:
        pass   # 안 되면 넘기기만 안 된다 — 아래 이동막대의 홈은 그대로 된다


def _inject_frame(components) -> None:
    """작은 창은 심부름만 한다 — 바깥 문서에 <script> 를 붙이고 끝낸다(자비스3 과 같은 방식)."""
    components.html(
        "<script>(function(){var d;try{d=window.parent&&window.parent.document;}catch(e){return;}"
        "if(!d||!d.body){return;}"
        "var j=window.parent.__j10;if(j&&j.ver==='j10-2'){try{j.warm();}catch(e){}return;}"
        "var t=d.createElement('script');t.id='j10-swipe-script';"
        "t.textContent=" + json.dumps(SWIPE_JS) + ";d.body.appendChild(t);})();</script>",
        height=0,
    )

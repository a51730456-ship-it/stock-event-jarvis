"""자비스13 「📘 이 테마 설명」 — 짧은 설명서 (2026-11-04 상하님 「한국테마 설명이 너무 길다 · 내용 이해하기 쉽게 간단히 만들어라 ·
그리고 현실과 맞냐?」).

얼린 method_help.KR_TEXT(2026-08 글 · 6절)를 **손대지 않고**, 자비스13 창(pages/12 _j13_method_help)에서만 이 짧은 글을 먼저 보인다.
예전 긴 글은 맨 밑 「예전 긴 설명 그대로 ▾」에 접어 둔다(지우지 않는다 · 급락 숫자 바로잡음 jarvis13_crash_record.help_text 그대로).

숫자는 **지금 앱이 실제로 쓰는 값**만 적는다(2026-11-04 대조 — jarvis4_data · docs/KR_THEME_SPEC.md · jarvis13_flow).
  · 상승장 그물 · 보유 — KR_THEME_SPEC 3-3(50억 · 신고가 뒤 3~10일 · −4~−6% · 250거래일) · 성적 43.4%/−6.6%(2026-08-07 재기).
  · 급락 — 성적은 jarvis13_crash_record 한 곳에서 읽는다(holds_line).
  · 눌림목 · 순위 7 문턱 — jarvis4_data.recommend 의 시장 50 · 테마 60 · 종목 70 · 면제 85(STRONG_STOCK_OVERRIDE).
  · **바로잡은 줄** — 옛 글 「외국인·기관 수급을 종목 점수 100점 중 20점으로 넣었습니다」는 지금 틀리다. 자비스13 은 수급을
    **값만 보여 주고 점수는 0**이다(jarvis13_flow · KR_THEME_SPEC 3-5). 접어 둔 옛 글에서도 그 줄을 바꿔 보인다.
값 · 점수 · 판정은 하나도 안 바꾼다 — 보여 주는 글만이다.
"""

from __future__ import annotations

import jarvis13_crash_record

MODULE_REVISION = 2026110401

CSS = """<style>
.j13hp-chips{display:flex;flex-wrap:wrap;gap:.3rem;margin:.25rem 0 .35rem}
.j13hp-chip{display:inline-block;padding:.12rem .5rem;border-radius:999px;font-size:.84rem;font-weight:800;
  border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.05)}
.j13hp-good{color:#3ddc97;border-color:rgba(61,220,151,.45)}
.j13hp-bad{color:#ff7b7b;border-color:rgba(255,123,123,.45)}
.j13hp-key{color:#ffd166;border-color:rgba(255,209,102,.45)}
.j13hp-info{color:#7cc4ff;border-color:rgba(124,196,255,.45)}
.j13hp-flow{font-weight:800;line-height:1.7}
.j13hp-flow b{color:#ffd166}
details.j13hp-old{margin-top:.8rem;border-top:1px dashed rgba(255,255,255,.18);padding-top:.5rem}
details.j13hp-old>summary{cursor:pointer;font-weight:800;color:#9fb3d1}
</style>"""

OLD_FLOW_LINE = ('<div class="mh-step"><b>외국인·기관 수급</b>을 종목 점수 100점 중 <b>20점</b>으로 넣었습니다</div>\n'
                 '<div class="mh-step mh-go">→ 시장 점수는 <u>참고로만</u>, 수급과 종목 점수를 무겁게</div>')
NEW_FLOW_LINE = ('<div class="mh-step"><b>외국인·기관 수급</b>은 <b>값만 보여 주고 점수는 0점</b>입니다'
                 ' (과거 자료가 없어 한 번도 재 보지 못했습니다 · 2026-11-04 바로잡음)</div>\n'
                 '<div class="mh-step mh-go">→ 시장 점수는 <u>참고로만</u>, 종목 점수를 무겁게</div>')


def _chips(*items) -> str:
    return "<div class='j13hp-chips'>" + "".join(
        f"<span class='j13hp-chip j13hp-{tone}'>{text}</span>" for tone, text in items) + "</div>"


def short_html() -> str:
    """짧은 설명서 — 갈래마다 「사는 법 한 줄 · 파는 때 · 성적 칩」."""
    crash = jarvis13_crash_record.holds_line()
    return f"""
<div class="mh-doc">
<div class="mh-h1">한국테마 한눈에</div>
<div class="mh-key"><div class="mh-key-h">세 줄 요약</div>
<div>① 사는 때는 늘 <b>종가 확인 → 다음 날 시가</b>.</div>
<div>② 점수는 <b>「얼마나 위험한가」</b>이지 「오른다」가 아닙니다.</div>
<div>③ <b>얼마를 살지 · 언제 팔지</b>는 상하님이 정하십니다.</div></div>

<div class="mh-h2"><span class="mh-no">1</span><span>상승장 (신고가 눌림매수)</span></div>
<div class="mh-box mh-buy-box">
<div class="j13hp-flow">거래대금 <b>50억↑</b> → 52주 <b>신고가</b> → <b>3~10일</b> 뒤 고점보다 <b>−4~−6%</b> → 다음 날 시가</div>
<div class="mh-sub">보유 <b>250거래일(약 1년)</b> · 손절 없음</div>
{_chips(("good", "승률 43.4% (아무 종목 35.1%)"), ("bad", "가운데 −6.6% (아무 종목 −14.0%)"))}
<div class="mh-sub">⚠ <b>덜 잃는</b> 규칙이지 <b>버는</b> 규칙이 아닙니다 — 절반 넘게는 잃었습니다(12년 · 7,410번).</div>
</div>

<div class="mh-h2"><span class="mh-no">2</span><span>급락 후 반등장 (낙폭종목)</span></div>
<div class="mh-box mh-buy-box">
<div class="j13hp-flow">코스피 종가가 1년 최고보다 <b>15%↓</b> → 그때까지 가장 깊은 날 고점보다 <b>−40~−60%</b> 종목(50억↑) → 다음 날 시가</div>
<div class="mh-sub">보유 <b>20거래일</b> 뒤 종가 · 손절 없음</div>
<div class="mh-sub">{crash}</div>
<div class="mh-sub">⚠ 12년에 국면 <b>{jarvis13_crash_record.EPISODE_COUNT}번</b>뿐 — 앞으로의 확률로 읽으면 안 됩니다. 거래 비용은 안 넣었습니다.</div>
</div>

<div class="mh-h2"><span class="mh-no">3</span><span>눌림목 찾기 · 순위 7 (조건점수)</span></div>
<div class="mh-box mh-data-box">
{_chips(("info", "시장 50↑"), ("info", "테마 60↑"), ("info", "종목 70↑"), ("key", "종목 85↑면 테마 안 봄"))}
<div class="mh-sub">외국인·기관 수급은 <b>값만 보여 주고 점수 0점</b> — 과거 자료가 없어 재 보지 못했습니다.</div>
<div class="mh-sub">⚠ 이 두 갈래는 <b>과거 성적을 재 보지 않았습니다.</b> 사는 때 · 손절 · 목표는 상자에 적힌 대로입니다.</div>
</div>

<div class="mh-h2"><span class="mh-no">4</span><span>상자 색 = 지금 할 일</span></div>
<div class="mh-box mh-data-box">
{_chips(("good", "🟩 진입 자리"), ("key", "🟨 기다림"), ("bad", "🟥 손대지 않음"))}
</div>

<div class="mh-h2"><span class="mh-no">5</span><span>실제로는? (현실 성적)</span></div>
<div class="mh-box mh-warn-box">
<div class="mh-step">위 숫자는 <b>과거 12년 재기</b>입니다. 2026-08-09부터 <b>실제로 고른 목록</b>의 성적은
화면 아래 <b>「📊 파트별 성적표」</b>에서 같은 날 코스피와 나란히 봅니다(날마다 바뀌어 여기에는 적지 않습니다).</div>
</div>
</div>
"""


def old_html(kr_text: str) -> str:
    """예전 긴 글 — 급락 숫자 바로잡음(jarvis13_crash_record) + 틀린 수급 20점 줄 바로잡음."""
    text = jarvis13_crash_record.help_text(kr_text)
    return text.replace(OLD_FLOW_LINE, NEW_FLOW_LINE)


def help_html(kr_text: str) -> str:
    return (CSS + short_html()
            + "<details class='j13hp-old'><summary>예전 긴 설명 그대로 보기 ▾</summary>" + old_html(kr_text) + "</details>")

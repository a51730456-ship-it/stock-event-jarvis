"""자비스13 급락 후 반등장 — 화면 방식으로 다시 잰 성적 · 국면별 표 · 동전주 딱지 · 그림자 목록 (2026-10-31 상하님 「라」).

설명서 docs/KR_THEME_SPEC.md 3-4(바로잡음) · 3-4-1(그림자 목록)을 화면에 옮긴 것이다. 그물·배점·매매는 그대로다.
옛 화면은 얼린 jarvis4_data 의 「12년에 29번 · 100번 중 66.6번」을 적었다 — 국면이 **끝나야** 아는 「가장 깊은 날」로 잰 값이라
화면 방식(국면 안 날마다 · 그때까지 가장 깊은 날 기준)의 성적이 아니다. 숫자는 깃허브 「자비스13 한국 급락 다시 재기」가 잰 그대로 옮긴다
(이 파일에서 셈하지 않는다 · 다시 재면 같이 고친다).
"""

from __future__ import annotations

import html
import pathlib

MODULE_REVISION = 2026103101

ROOT = pathlib.Path(__file__).resolve().parent
RUN = 41017206848                        # 국면 12번 · 세 기간 숫자를 잰 실행
SPAN = "2014-08 ~ 2026-10"
HOW = ("상장폐지 종목 포함(일봉 527/532) · 다음 거래일 시가에 산 것으로 · 그 시가가 상한가거나 거래가 없으면 못 산 것 · "
       "거래 비용 없음 · 보통주 전체")
EPISODE_COUNT = 12
# (보유 거래일, 국면마다 코스피보다 %p, 코스피를 이긴 국면 %, 번 국면 %)
HOLDS = ((20, 2.5, 75, 83), (40, -0.9, 67, 83), (60, -4.4, 50, 75))
# 국면별 — 깃허브 실행의 「### 국면별 — 지금 화면 규칙」 표를 그대로 옮긴다(시작 · 끝 · 가장 깊은 날 · 깊이 % · 보유별 코스피보다 %p).
EPISODES: tuple = (
    {"start": "2015-08-24", "end": "2015-08-25", "deepest": "2015-08-24", "depth": -15.8, "ex": {20: 11.3, 40: 13.7, 60: 13.6}},
    {"start": "2016-01-20", "end": "2016-02-12", "deepest": "2016-02-12", "depth": -15.6, "ex": {20: 1.8, 40: 4.4, 60: 6.1}},
    {"start": "2018-10-11", "end": "2019-03-28", "deepest": "2019-01-03", "depth": -23.3, "ex": {20: 2.0, 40: 3.3, 60: 3.6}},
    {"start": "2019-05-09", "end": "2019-06-18", "deepest": "2019-05-29", "depth": -18.4, "ex": {20: -1.9, 40: -8.1, 60: -10.9}},
    {"start": "2019-08-02", "end": "2019-09-04", "deepest": "2019-08-07", "depth": -18.9, "ex": {20: 2.5, 40: 0.3, 60: -2.5}},
    {"start": "2020-03-11", "end": "2020-05-14", "deepest": "2020-03-19", "depth": -35.7, "ex": {20: 6.6, 40: 7.0, 60: 5.8}},
    {"start": "2022-01-24", "end": "2023-01-25", "deepest": "2022-09-30", "depth": -31.2, "ex": {20: -0.8, 40: -1.8, 60: -2.6}},
    {"start": "2024-08-05", "end": "2024-08-05", "deepest": "2024-08-05", "depth": -15.6, "ex": {20: 3.9, 40: 6.6, 60: 3.0}},
    {"start": "2024-11-13", "end": "2025-02-03", "deepest": "2024-12-09", "depth": -18.4, "ex": {20: 3.4, 40: 3.6, 60: -1.0}},
    {"start": "2025-04-07", "end": "2025-04-16", "deepest": "2025-04-09", "depth": -20.7, "ex": {20: 4.3, 40: -2.1, 60: -9.8}},
    {"start": "2026-03-04", "end": "2026-04-02", "deepest": "2026-03-31", "depth": -19.9, "ex": {20: -7.2, 40: -42.8, 60: -74.4}},
    {"start": "2026-07-02", "end": "진행 중", "deepest": "2026-10-26", "depth": -40.0, "ex": {20: 3.6, 40: 5.6, 60: 16.8}},
)
EPISODE_RUN = 41125696240
# 40·60일 평균을 끌어내린 것은 거의 2026년 3~4월 국면 하나다(코스피가 60일에 +58.1% 오를 때 목록은 −16.3%).
# 그 국면을 빼면(위 표로 셈) — 20일 +3.3%p · 40일 +3.0%p · 60일 +2.0%p.
WITHOUT_2026_03 = {20: 3.3, 40: 3.0, 60: 2.0}
COST = "2026년 증권거래세 0.20%(코스피 0.05%+농어촌특별세 0.15% · 코스닥 0.20%) · 증권사 수수료 별도"
PENNY_PRICE = 1_000                      # 2026-07부터 1,000원 미만이 상장폐지 요건(검색 요약 · 원문 미확인)
SHADOW_RULE = "j13-shadow-v1"
SHADOW_DIR = ROOT / "data" / "picklist_shadow"


def _pp(value: float) -> str:
    return f"{value:+.1f}%p"


def holds_line() -> str:
    """카드 한 줄 — 국면마다 코스피보다 20 · 40 · 60거래일."""
    cells = " · ".join(
        f"{days}일 <b class='{'j4-up' if value > 0 else 'j4-down'}'>{_pp(value)}</b>" for days, value, _beat, _pos in HOLDS)
    return f"지금 화면 방식으로 다시 잰 성적(국면 {EPISODE_COUNT}번) — 코스피보다 {cells}"


def shadow_saved(folder: pathlib.Path | None = None) -> list[str]:
    """그림자 목록이 저장된 날(신호 난 날) — 파일 이름의 날짜. 못 읽으면 빈 목록."""
    folder = folder or SHADOW_DIR
    try:
        return sorted(path.name[:10] for path in folder.glob("*.KR.json"))
    except OSError:
        return []


def _episode_table() -> str:
    if not EPISODES:
        return ""
    head = "".join(f"<th>{days}일</th>" for days, *_rest in HOLDS)
    rows = []
    for item in EPISODES:
        cells = "".join(
            "<td>—</td>" if item["ex"].get(days) is None else
            f"<td class='{'j4-up' if item['ex'][days] > 0 else 'j4-down'}'>{_pp(item['ex'][days])}</td>"
            for days, *_rest in HOLDS)
        rows.append(f"<tr><td>{html.escape(item['start'])} ~ {html.escape(item['end'])}</td>"
                    f"<td>{html.escape(item['deepest'])} {item['depth']:.1f}%</td>{cells}</tr>")
    # 폰에서는 표가 화면보다 넓다 — 표만 옆으로 밀게 감싼다(화면 전체가 넘치지 않게 · CLAUDE.md 12)
    return ("<div style='overflow-x:auto;max-width:100%'><table class='j13-crash-eps'><thead><tr>"
            "<th>국면(코스피 종가 −15% 아래)</th><th>가장 깊은 날</th>"
            f"{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
            f"<div class='j4-muted' style='font-size:.78rem'>국면마다 그 안에서 고른 목록을 코스피와 견준 값(%p) · "
            f"깃허브 실행 {EPISODE_RUN}</div>")


def record_html() -> str:
    """설명 안 「한국 자료로 잰 성적」 자리 — 다시 잰 성적 · 국면별 표 · 비용 · 그림자 목록."""
    beat = " · ".join(f"{days}일 {beat_pct}% · {pos_pct}%" for days, _value, beat_pct, pos_pct in HOLDS)
    saved = shadow_saved()
    shadow = (f"지금까지 {len(saved)}번 저장(마지막 {saved[-1]})" if saved
              else "아직 저장된 날이 없습니다 — 국면 안에서 코스피가 새 바닥을 찍는 날부터 쌓입니다")
    return (
        CSS +
        f"<b>한국 자료로 다시 잰 성적</b>({SPAN} · {HOW}) — {holds_line()}.<br>"
        f"코스피를 이긴 국면 · 번 국면: {beat}. "
        "<b class='j4-down'>한 달 안팎은 코스피보다 나았지만, 길게 들면 코스피보다 못했습니다.</b> "
        "다만 40·60일을 끌어내린 것은 거의 <b>2026년 3~4월 국면 하나</b>입니다(코스피가 60일에 +58.1% 오를 때 목록은 −16.3%) — "
        f"그 국면을 빼면 20일 {_pp(WITHOUT_2026_03[20])} · 40일 {_pp(WITHOUT_2026_03[40])} · 60일 {_pp(WITHOUT_2026_03[60])}입니다(표로 셈). "
        f"국면이 {EPISODE_COUNT}번뿐이라 이 숫자를 앞으로의 확률로 읽으면 안 됩니다.<br>"
        "예전에 적던 「12년에 29번 · 100번 중 66.6번」은 국면이 <u>끝나야</u> 아는 「가장 깊은 날」로 잰 값이라 뺐습니다"
        "(2026-10-31 · 설명서 3-4).<br>"
        + _episode_table() +
        f"성적에는 거래 비용이 없습니다 — {COST}. 코스피 국면은 <b>종가</b>로 잽니다"
        "(뉴스가 쓰는 장중 최고와 다를 수 있습니다).<br>"
        f"<b>그림자 목록</b>({SHADOW_RULE}) — 재기에서 가장 나았던 자비스12 식 규칙(코스피 고점일 대비 −50~−80% · "
        f"새 바닥마다 · 빼기)을 화면 추천에는 쓰지 않고 날짜와 함께 따로 쌓아, 이번 국면이 끝나면 이 목록과 견줍니다. {shadow}.<br>"
    )


CSS = """<style>
table.j13-crash-eps{border-collapse:collapse;margin:.35rem 0 .2rem;font-size:.82rem;font-variant-numeric:tabular-nums}
table.j13-crash-eps th,table.j13-crash-eps td{border:1px solid rgba(255,255,255,.12);padding:.2rem .45rem;text-align:center;
  white-space:nowrap}
table.j13-crash-eps th{color:#9aa0aa;font-weight:700}
</style>"""


# ── 「📘 이 테마 설명」 — 얼린 method_help.KR_TEXT 의 급락 부분만 바로잡은 글 (자비스13 만 · method_help 는 그대로) ──
_OLD_DATA_BOX = (
    '<div class="mh-box-h">▸ 한국에서 재 본 성적</div>\n'
    '<div class="mh-kv"><span class="mh-k">이 규칙</span><span class="mh-v mh-pos">승률 66.6%(3,739건) · 가운데 값 +6.1%</span></div>\n'
    '<div class="mh-kv"><span class="mh-k">그날 아무 종목이나 샀으면</span><span class="mh-v">승률 62.1% · 가운데 값 +4.1%</span></div>\n'
    '<div class="mh-kv"><span class="mh-k">기준선보다 나았던 해</span><span class="mh-v mh-pos">8년 중 7년</span></div>\n'
    '<div class="mh-kv"><span class="mh-k">기준선보다 나았던 창</span><span class="mh-v mh-pos">306개 중 306개</span></div>')


def _new_data_box() -> str:
    holds = " · ".join(f"{days}일 {_pp(value)}" for days, value, _beat, _pos in HOLDS)
    beats = " · ".join(f"{days}일 {beat}%" for days, _value, beat, _pos in HOLDS)
    without = " · ".join(f"{days}일 {_pp(value)}" for days, value in WITHOUT_2026_03.items())
    return (f'<div class="mh-box-h">▸ 한국에서 다시 잰 성적 (화면 방식 · {SPAN} · 국면 {EPISODE_COUNT}번)</div>\n'
            f'<div class="mh-kv"><span class="mh-k">국면마다 코스피보다</span><span class="mh-v">{holds}</span></div>\n'
            f'<div class="mh-kv"><span class="mh-k">코스피를 이긴 국면</span><span class="mh-v">{beats}</span></div>\n'
            f'<div class="mh-kv"><span class="mh-k">2026년 3~4월 국면을 빼면</span><span class="mh-v">{without}</span></div>\n'
            '<div class="mh-kv"><span class="mh-k">예전 숫자 66.6%</span>'
            '<span class="mh-v">국면이 끝나야 아는 날로 잰 값이라 뺐습니다(2026-10-31)</span></div>')


HELP_FIXES = (
    ('<div class="mh-step">코스피가 고점 대비 <b>15% 넘게</b> 빠진 국면</div>',
     '<div class="mh-step">코스피 <b>종가</b>가 1년 최고 종가보다 <b>15% 넘게</b> 빠진 국면</div>'),
    ('<div class="mh-step">그 국면에서 <b>가장 깊었던 날</b></div>',
     '<div class="mh-step">그때까지 <b>가장 깊었던 날</b>을 기준일로 <b>날마다</b> 다시 고름</div>'),
    (_OLD_DATA_BOX, None),                    # None — _new_data_box() 로 바꾼다(숫자를 한 곳에서만 가져오게)
    ('<li>이 신호는 12년 동안 <b>스물아홉 번</b> 났습니다. 사실상 스물아홉 번의 사건이라, 승률을 앞으로의 확률로 읽으면 안 됩니다.</li>',
     f'<li>국면은 12년에 <b>{EPISODE_COUNT}번</b>뿐입니다. 이 숫자를 앞으로의 확률로 읽으면 안 됩니다. '
     f'성적에는 거래 비용이 없습니다({COST}).</li>'),
)


def help_text(kr_text: str) -> str:
    """얼린 설명 글에서 급락 부분만 바꾼다. 못 찾은 곳이 있으면 옛 숫자를 그대로 두지 않고 맨 위에 바로잡은 글을 붙인다."""
    text, missing = str(kr_text or ""), 0
    for old, new in HELP_FIXES:
        if old in text:
            text = text.replace(old, _new_data_box() if new is None else new)
        else:
            missing += 1
    if missing:
        text = ("<div class='mh-box mh-warn-box'><div class='mh-box-h'>⚠ 급락 후 반등장 성적 바로잡음(2026-10-31)</div>"
                f"{holds_line()} · 아래 설명의 예전 숫자(66.6% 등)는 국면이 끝나야 아는 날로 잰 값입니다.</div>" + text)
    return text

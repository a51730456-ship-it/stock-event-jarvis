"""자비스5 — 한국테마 선행감지 실험 화면."""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

import streamlit as st

import auth  # 로그인 유지(쿠키). 쿠키가 안 되면 조용히 세션 기반 동작으로 남는다.

# 배포 갱신 중 옛 auth가 프로세스에 남으면 함수 모양이 안 맞아 화면이 죽는다
# (2026-07-25 온라인 실발생). 리비전이 낮으면 다시 읽는다.
_REQUIRED_AUTH_REVISION = 2026072503
if int(getattr(auth, "MODULE_REVISION", 0)) < _REQUIRED_AUTH_REVISION:
    import importlib as _importlib

    auth = _importlib.reload(auth)


st.set_page_config(page_title="자비스5 — 한국테마 선행감지", layout="wide")
st.markdown(
    """
    <style>
    /* 왼쪽 메뉴는 좁게, 오른쪽 본문은 넓게 (2026-07-24 사용자 지시). j-narrow-sidebar */
    [data-testid="stSidebar"],
    section[data-testid="stSidebar"] {
        width: 10rem !important; min-width: 10rem !important; max-width: 10rem !important;
    }
    [data-testid="stSidebar"] > div,
    [data-testid="stSidebarContent"],
    section[data-testid="stSidebar"] > div {
        width: 10rem !important; min-width: 10rem !important;
    }
    /* 메뉴 글자가 만드는 자동 최소폭 때문에 사이드바가 안 좁아지는 것을 막는다 */
    [data-testid="stSidebarNav"],
    [data-testid="stSidebarNav"] ul,
    [data-testid="stSidebarNav"] li,
    [data-testid="stSidebarNav"] a { min-width: 0 !important; max-width: 100% !important; }
    [data-testid="stSidebarNav"] a p { overflow-wrap: anywhere; }
    [data-testid="stSidebarNav"] li { margin: 0 !important; }
    [data-testid="stSidebarNav"] a { padding: .45rem .6rem !important; }
    [data-testid="stSidebarNav"] a, [data-testid="stSidebarNav"] a * {
        font-size: 1.15rem !important; font-weight: 800 !important; color: #ffb020 !important;
    }
    [data-testid="stSidebarNav"] li:first-child a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:first-child a p::before { content: "자비스1"; font-size: 1.15rem; }
    [data-testid="stSidebarNav"] ul { display: flex; flex-direction: column; }
    [data-testid="stSidebarNav"] li:nth-child(1) { order: 2; }
    [data-testid="stSidebarNav"] li:nth-child(2) { order: 1; }
    [data-testid="stSidebarNav"] li:nth-child(3) { order: 3; }
    [data-testid="stSidebarNav"] li:nth-child(4) { order: 4; }
    [data-testid="stSidebarNav"] li:nth-child(5) { order: 5; }
    [data-testid="stSidebarNav"] li:nth-child(6) { order: 6; }
    [data-testid="stSidebarNav"] li:nth-child(7) { order: 7; }
    [data-testid="stSidebarNav"] li:nth-child(7) a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:nth-child(7) a p::before {
        content: "종가관찰\\A(자비스6)"; white-space: pre; line-height: 1.2;
        font-size: 1.15rem; font-weight: 800; color: #ffb020;
    }
    [data-testid="stSidebarNav"] li:nth-child(4) a p,
    [data-testid="stSidebarNav"] li:nth-child(5) a p,
    [data-testid="stSidebarNav"] li:nth-child(6) a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:nth-child(4) a p::before { content: "미국테마\\A(자비스3)"; white-space: pre; line-height: 1.2; font-size: 1.15rem; }
    [data-testid="stSidebarNav"] li:nth-child(5) a p::before { content: "한국테마\\A(자비스4)"; white-space: pre; line-height: 1.2; font-size: 1.15rem; }
    [data-testid="stSidebarNav"] li:nth-child(6) a p::before { content: "한국테마\\A(선행감지)"; white-space: pre; line-height: 1.2; font-size: 1.15rem; }
    .j5-note { border: 1px solid rgba(77,166,255,.45); background: rgba(37,99,235,.10);
        border-radius: .6rem; padding: .8rem 1rem; color: #9dccff; line-height: 1.65; }
    .j5-warn { color: #ffb020; font-weight: 800; }
    .j5-section-title { color: #4da6ff; font-size: 1.28rem; font-weight: 800;
        margin: 1.4rem 0 .45rem; text-align: left; }
    .j5-kpi-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: .75rem; margin: 1rem 0 .8rem; }
    .j5-kpi { border: 1px solid rgba(255,255,255,.11); background: rgba(255,255,255,.025);
        border-radius: .65rem; padding: .72rem .9rem; text-align: center; }
    .j5-kpi-label { color: #4da6ff; font-size: .88rem; font-weight: 800; }
    .j5-kpi-value { color: #44f0a1; font-size: 1.45rem; font-weight: 800; line-height: 1.35; }
    .j5-guide-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: .7rem; margin: .55rem 0 .8rem; }
    .j5-guide-card { border: 1px solid rgba(255,255,255,.10); background: rgba(255,255,255,.025);
        border-radius: .6rem; padding: .68rem .8rem; color: #b7c0ce; line-height: 1.5; }
    .j5-guide-title { color: #44f0a1; font-weight: 800; margin-bottom: .15rem; }
    .j5-guide-key { color: #ffb020; font-weight: 800; }
    .j5-table-wrap { overflow-x: auto; border: 1px solid rgba(255,255,255,.08);
        border-radius: .55rem; margin: .25rem 0 .7rem; }
    .j5-table { width: 100%; min-width: 920px; border-collapse: collapse; table-layout: fixed;
        font-size: .9rem; }
    .j5-table th { color: #7cc8ff; font-weight: 800; text-align: center; padding: .58rem .45rem;
        background: rgba(77,166,255,.07); border-bottom: 1px solid rgba(77,166,255,.32); }
    .j5-table td { color: #e6e6e6; text-align: center; padding: .52rem .45rem;
        border-bottom: 1px solid rgba(255,255,255,.06); vertical-align: middle; }
    .j5-table tr:last-child td { border-bottom: none; }
    .j5-table td.j5-left, .j5-table th.j5-left { text-align: left; }
    .j5-name { color: #c084fc !important; font-weight: 800; }
    /* 한국시장 색 규칙: 상승(+) 빨강, 하락(-) 파랑 */
    .j5-pos { color: #ff5b5b !important; font-weight: 800; }
    .j5-neg { color: #4da6ff !important; font-weight: 800; }
    .j5-good { color: #44f0a1 !important; font-weight: 800; }
    .j5-amber { color: #ffb020 !important; font-weight: 800; }
    .j5-muted { color: #9aa0aa !important; }
    .j5-badge { display: inline-block; min-width: 1.7rem; padding: .1rem .42rem;
        border-radius: .45rem; font-weight: 800; line-height: 1.35; }
    .j5-model-a { color: #69bff8; border: 1px solid rgba(105,191,248,.65);
        background: rgba(105,191,248,.10); }
    .j5-model-b { color: #c084fc; border: 1px solid rgba(192,132,252,.65);
        background: rgba(192,132,252,.10); }
    .j5-model-c { color: #ffb020; border: 1px solid rgba(255,176,32,.65);
        background: rgba(255,176,32,.10); }
    .j5-stage { color: #44f0a1; font-weight: 800; }
    .j5-score-wrap { display: flex; align-items: center; gap: .4rem; }
    .j5-score-bar { flex: 1; min-width: 55px; height: 8px; overflow: hidden;
        border-radius: 5px; background: rgba(255,255,255,.10); }
    .j5-score-fill { height: 8px; background: #44f0a1; }
    .j5-score-num { min-width: 28px; color: #e6e6e6; font-weight: 800; text-align: right; }
    .j5-lead-score { font-size: 1.02rem; font-weight: 800; color: #44f0a1; }
    .j5-lead-stage { display: block; margin-top: .1rem; font-size: .72rem; font-weight: 800; }
    .j5-spark { width: 104px; height: 28px; vertical-align: middle; overflow: visible; }
    .j5-spark-base { stroke: rgba(255,255,255,.12); stroke-width: 1; }
    .j5-spark-line { fill: none; stroke-width: 2.4; stroke-linecap: round; stroke-linejoin: round; }
    .j5-formula { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: .45rem;
        margin: .45rem 0 .7rem; }
    .j5-formula-cell { text-align: center; border: 1px solid rgba(255,255,255,.10);
        border-radius: .5rem; padding: .45rem .35rem; color: #b7c0ce; font-size: .82rem; }
    .j5-formula-cell b { display: block; color: #44f0a1; font-size: 1rem; }
    .j5-explain { color: #b7c0ce; font-size: .92rem; line-height: 1.6; margin: 0 0 .55rem; }
    .j5-explain b { color: #44f0a1; }
    .j5-legend { border-left: 4px solid #4da6ff; background: rgba(77,166,255,.07);
        border-radius: .4rem; padding: .62rem .8rem; color: #b7c0ce; line-height: 1.55;
        margin-bottom: .7rem; }
    @media (max-width: 900px) {
        .j5-kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .j5-guide-grid { grid-template-columns: 1fr; }
        .j5-formula { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _login_gate() -> None:
    auth.sync_auth()  # 쿠키에 로그인이 남아 있으면 되살린다(폰 복귀 시 재로그인 방지).
    if st.session_state.get("authenticated"):
        return
    st.markdown("## 자비스5 — 한국테마 선행감지")
    try:
        password = st.secrets.get("APP_PASSWORD")
    except Exception:
        password = None
    if not password:
        st.warning(".streamlit/secrets.toml에 APP_PASSWORD 설정이 필요합니다.")
        st.stop()
    entered = st.text_input("비밀번호", type="password", key="j5_login_password")
    if st.button("자비스5 로그인", width="stretch"):
        if entered == password:
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("비밀번호가 올바르지 않습니다.")
    st.stop()


_login_gate()

import importlib

import mobile_ui

# 옛 mobile_ui가 프로세스에 남으면 폰 수정이 온라인에 하나도 반영되지 않는다
# (2026-07-25 실발생). CLAUDE.md 11번 규칙에 따라 리비전이 낮으면 다시 읽는다.
_REQUIRED_MOBILE_REVISION = 2026073012
if int(getattr(mobile_ui, "MODULE_REVISION", 0)) < _REQUIRED_MOBILE_REVISION:
    mobile_ui = importlib.reload(mobile_ui)
import jarvis5_collector as collector
import jarvis5_data as engine
import jarvis5_store as store
import jarvis5_sync as sync


def _eok(value) -> str:
    return "—" if value is None else f"{float(value) / 1e8:,.1f}억"


def _pct(value, digits=2) -> str:
    return "—" if value is None else f"{float(value):+.{digits}f}%"


def _esc(value) -> str:
    return html.escape(str(value or "—"))


def _sign_class(value) -> str:
    if value is None:
        return "j5-muted"
    number = float(value)
    if number > 0:
        return "j5-pos"
    if number < 0:
        return "j5-neg"
    return "j5-muted"


def _day_price_note(latest: dict | None) -> str:
    """당일 고가·저가가 몇 %나 찍혔는지 (2026-07-26 추가).

    이 값은 지나가면 소급이 안 된다. 클라우드 작업이 초록불로 끝나도 시세
    조회만 조용히 실패할 수 있어서, 그때 알아채는 유일한 표시다.
    거래정지 종목은 저장하지 않으므로 100%가 나오지는 않는다.
    """
    if not latest:
        return ""
    try:
        coverage = store.day_price_coverage(latest.get("id"))
    except Exception:
        return ""
    ratio = coverage.get("ratio")
    return "" if ratio is None else f" · 고저 {ratio * 100:.0f}%"


def _summary_cards(latest: dict | None) -> str:
    values = [
        ("최근 수집", str(latest.get("captured_at") or "—")[5:16] if latest else "없음"),
        ("테마", f"{int(latest.get('theme_count') or 0):,}개" if latest else "0개"),
        ("종목행",
         f"{int(latest.get('stock_row_count') or 0):,}개{_day_price_note(latest)}"
         if latest else "0개"),
        ("수집시간", f"{float(latest.get('elapsed_seconds') or 0):.1f}초" if latest else "—"),
    ]
    cards = "".join(
        f"<div class='j5-kpi'><div class='j5-kpi-label'>{_esc(label)}</div>"
        f"<div class='j5-kpi-value'>{_esc(value)}</div></div>"
        for label, value in values
    )
    return f"<div class='j5-kpi-grid'>{cards}</div>"


# 수집 간격이 이보다 짧으면 분당 환산값을 믿지 않는다. 네이버 누적 거래대금은
# 실시간이 아니라 몇십 초 늦게 갱신되므로, 32초 간격 수집은 "아직 안 오른 누적값"을
# 0.53분으로 나눠 엉뚱하게 작은 값을 만든다(2026-07-24 실측: 같은 테마가 32초 수집
# 166만 → 78분 수집 2억5천만으로 153배 차이. 이 가짜 저점 때문에 거의 모든 테마의
# 미니차트가 '올라가는 선'으로 보였다).
SPARK_MIN_INTERVAL_SECONDS = 60.0


def _parse_captured_at(value):
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _history_points(history: list[dict]) -> list[dict]:
    """미니차트·직전 대비에 쓸 수 있는 점만 시간과 함께 남긴다."""
    points = []
    for row in history:
        value = row.get("activity_intensity")
        if value is None:
            continue
        interval = row.get("interval_seconds")
        if interval is not None and float(interval) < SPARK_MIN_INTERVAL_SECONDS:
            continue
        points.append({
            "value": float(value),
            "at": _parse_captured_at(row.get("captured_at")),
        })
    return points


def _span_text(points: list[dict]) -> str:
    """미니차트가 실제로 담고 있는 시간 범위를 문장으로 만든다."""
    times = [p["at"] for p in points if p["at"] is not None]
    if len(times) < 2:
        return f"수집 {len(points)}회"
    minutes = (times[-1] - times[0]).total_seconds() / 60
    span = f"{minutes / 60:.1f}시간" if minutes >= 90 else f"{minutes:.0f}분"
    return f"{times[0].strftime('%H:%M')}~{times[-1].strftime('%H:%M')} · {span} · 수집 {len(points)}회"


def _sparkline_svg(history: list[dict]) -> str:
    """최근 분당 거래활동 미니차트.

    가로축은 '몇 번째 수집'이 아니라 실제 시각이다. 수집이 78분·271분처럼 들쭉날쭉
    벌어진 날 균등 간격으로 그리면 기울기가 거짓말을 한다(2026-07-24 사용자 지적).
    가로 점선은 이 구간이 시작된 수준이라, 선이 그 위면 활동이 늘어난 것이다.
    """
    points = _history_points(history)
    if len(points) < 2:
        return "<span class='j5-muted'>자료 축적중</span>"
    values = [p["value"] for p in points]
    width, height, pad = 104, 28, 3
    low, high = min(values), max(values)
    spread = high - low

    def _y(value):
        if spread == 0:
            return height / 2
        return pad + (high - value) / spread * (height - 2 * pad)

    times = [p["at"] for p in points]
    total = None
    if all(t is not None for t in times):
        total = (times[-1] - times[0]).total_seconds()
    coords = []
    for index, point in enumerate(points):
        if total and total > 0:
            ratio = (point["at"] - times[0]).total_seconds() / total
        else:
            ratio = index / max(1, len(points) - 1)
        coords.append((pad + ratio * (width - 2 * pad), _y(point["value"])))

    change = (values[-1] / values[0] - 1) * 100 if values[0] > 0 else None
    if values[-1] > values[0]:
        color = "#ff5b5b"
    elif values[-1] < values[0]:
        color = "#4da6ff"
    else:
        color = "#9aa0aa"
    start_y = _y(values[0])
    change_text = f"구간 변화 {change:+.1f}%" if change is not None else "구간 변화 계산 불가"
    tooltip = _esc(f"{_span_text(points)} · {change_text}")
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    return (
        f"<svg class='j5-spark' viewBox='0 0 {width} {height}' role='img' "
        f"aria-label='{tooltip}'><title>{tooltip}</title>"
        f"<line class='j5-spark-base' x1='{pad}' y1='{start_y:.1f}' "
        f"x2='{width - pad}' y2='{start_y:.1f}'></line>"
        f"<polyline class='j5-spark-line' stroke='{color}' points='{path}'></polyline>"
        + "".join(
            f"<circle cx='{x:.1f}' cy='{y:.1f}' r='1.6' fill='{color}' opacity='.55'></circle>"
            for x, y in coords[:-1]
        )
        + f"<circle cx='{coords[-1][0]:.1f}' cy='{coords[-1][1]:.1f}' "
        f"r='2.5' fill='{color}'></circle></svg>"
    )


def _history_delta(history: list[dict]) -> float | None:
    values = [point["value"] for point in _history_points(history)]
    if len(values) < 2 or values[-2] <= 0:
        return None
    return (values[-1] / values[-2] - 1) * 100


def _latest_table_html(rows: list[dict], histories: dict[int, list[dict]]) -> str:
    body = []
    for rank, row in enumerate(rows, 1):
        members = int(row.get("member_count") or 0)
        history = histories.get(int(row.get("theme_no") or 0), [])
        delta = _history_delta(history)
        ratio = row.get("baseline_ratio")
        ratio_html = (
            f"<span class='j5-good'>{float(ratio):.2f}배</span>"
            if ratio is not None else "<span class='j5-amber'>학습중</span>"
        )
        share = row.get("top_contributor_share")
        share_pct = float(share) * 100 if share is not None else None
        share_class = (
            "j5-muted" if share_pct is None else ("j5-good" if share_pct <= 55 else "j5-amber")
        )
        share_text = f"{share_pct:.0f}%" if share_pct is not None else "—"
        relative = row.get("relative_change_pct")
        lead_score = float(row.get("lead_score") or 0)
        lead_stage = str(row.get("lead_stage") or "학습점수")
        lead_class = "j5-good" if lead_stage == "선행점수" else "j5-amber"
        flags = " · ".join(row.get("lead_flags") or []) or "품질 감점 없음"
        body.append(
            "<tr>"
            f"<td class='j5-muted'>{int(row.get('lead_rank') or rank)}</td>"
            f"<td class='j5-left j5-name'>{_esc(row.get('theme_name'))}</td>"
            f"<td title='{_esc(flags)}'><span class='j5-lead-score'>{lead_score:.1f}</span>"
            f"<span class='j5-lead-stage {lead_class}'>{_esc(lead_stage)}</span></td>"
            f"<td>{_sparkline_svg(history)}</td>"
            f"<td class='{_sign_class(delta)}'>{_pct(delta, 1)}</td>"
            f"<td class='j5-good'>{_eok(row.get('activity_intensity'))}</td>"
            f"<td>{ratio_html}</td>"
            f"<td>{int(row.get('advancers') or 0)}/{members}</td>"
            f"<td>{int(row.get('active_count') or 0)}/{members}</td>"
            f"<td class='{share_class}'>{share_text}</td>"
            f"<td class='{_sign_class(relative)}'>{_pct(relative)}</td>"
            "</tr>"
        )
    return (
        "<div class='j5-table-wrap'><table class='j5-table' style='min-width:1280px'>"
        "<colgroup><col style='width:4%'><col style='width:15%'><col style='width:9%'>"
        "<col style='width:11%'><col style='width:9%'><col style='width:13%'>"
        "<col style='width:10%'><col style='width:8%'><col style='width:8%'>"
        "<col style='width:7%'><col style='width:8%'></colgroup>"
        "<thead><tr><th>순위</th><th class='j5-left'>테마</th><th>선행 후보점수</th>"
        "<th>최근 흐름 (시각 기준)</th><th>직전 대비</th><th>분당 거래활동</th>"
        "<th>동일시각 배수</th><th>상승확산</th><th>거래참여</th>"
        "<th>최대종목 기여</th><th>시장대비</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


def _session_progress(captured_at) -> float:
    """장 시작(09:00)부터 이 수집 시각까지 정규장 6시간30분 중 얼마나 지났는지.

    오늘 거래량을 전일 '하루치'와 그냥 나누면 장중에는 무조건 1배 미만으로 나온다.
    경과율로 나눠야 '평소 이맘때 대비 몇 배 페이스인가'가 된다.
    """
    try:
        moment = datetime.fromisoformat(str(captured_at))
    except (TypeError, ValueError):
        return 1.0
    opened = moment.replace(hour=9, minute=0, second=0, microsecond=0)
    ratio = (moment - opened).total_seconds() / (6.5 * 3600)
    return min(1.0, max(0.02, ratio))


def _pace_cell(volume, previous_volume, progress: float) -> str:
    """전일 대비 거래 페이스 칸."""
    volume = float(volume or 0)
    previous_volume = float(previous_volume or 0)
    if previous_volume <= 0 or volume <= 0:
        return "<td class='j5-muted'>—</td>"
    pace = (volume / previous_volume) / progress
    if pace >= 2.0:
        cls = "j5-warn"
    elif pace >= 1.3:
        cls = "j5-good"
    elif pace >= 0.7:
        cls = "j5-muted"
    else:
        cls = "j5-neg"
    return f"<td class='{cls}'>{pace:.2f}배</td>"


def _stock_table_html(stocks: list[dict], theme_row: dict, progress: float = 1.0) -> str:
    """테마를 펼쳤을 때 보이는 구성종목 표.

    구간 거래대금이 큰 순서로 준다 — 맨 위 종목이 그 테마 점수를 끌어올린 종목이다.
    기여 비중을 같이 보여줘 한 종목이 테마를 혼자 들어올린 것인지 바로 보이게 한다.
    """
    if not stocks:
        return "<div class='j5-note'>이 테마의 종목 자료가 아직 없습니다.</div>"

    interval_total = sum(float(s.get("interval_trading_value") or 0) for s in stocks)
    body = []
    for index, stock in enumerate(stocks, 1):
        interval = float(stock.get("interval_trading_value") or 0)
        share = (interval / interval_total) if interval_total > 0 else 0.0
        theme_count = int(stock.get("theme_count") or 0)
        # 여러 테마에 겹친 종목은 이 테마만의 신호로 보기 어렵다 — 그대로 보여준다.
        overlap_class = "j5-amber" if theme_count >= 10 else "j5-muted"
        share_class = "j5-warn" if share >= 0.55 else ("j5-amber" if share >= 0.35 else "j5-good")
        price = stock.get("price")
        body.append(
            "<tr>"
            f"<td class='j5-muted'>{index}</td>"
            f"<td class='j5-left j5-name'>{_esc(stock.get('stock_name'))}</td>"
            f"<td class='j5-muted'>{_esc(stock.get('stock_code'))}</td>"
            f"<td>{'—' if price is None else f'{int(float(price)):,}'}</td>"
            f"<td class='{_sign_class(stock.get('change_pct'))}'>{_pct(stock.get('change_pct'))}</td>"
            f"<td class='j5-good'>{_eok(interval)}</td>"
            f"<td class='{share_class}'>{share * 100:.0f}%</td>"
            f"<td class='j5-muted'>{_eok(stock.get('trading_value'))}</td>"
            + _pace_cell(stock.get("volume"), stock.get("previous_volume"), progress)
            + f"<td class='{overlap_class}'>{theme_count or '—'}</td>"
            "</tr>"
        )

    advancers = int(theme_row.get("advancers") or 0)
    members = int(theme_row.get("member_count") or len(stocks))
    active = int(theme_row.get("active_count") or 0)
    top_share = float(theme_row.get("top_contributor_share") or 0)
    top_raw = max((float(s.get("interval_trading_value") or 0) for s in stocks), default=0.0)
    top_raw_share = (top_raw / interval_total) if interval_total > 0 else 0.0
    today_volume = sum(float(s.get("volume") or 0) for s in stocks)
    prev_volume = sum(float(s.get("previous_volume") or 0) for s in stocks)
    theme_pace = (
        f"{(today_volume / prev_volume) / progress:.2f}배"
        if prev_volume > 0 and today_volume > 0 else "—"
    )
    head = (
        f"<div class='j5-note'>구성종목 {members}개 · 오른 종목 {advancers}개 · "
        f"거래가 늘어난 종목 {active}개<br>"
        f"<b>최대종목 기여 {top_share * 100:.0f}%</b>(중복소속 보정 후 — 점수·경보 판정에 쓰는 값) · "
        f"실제 돈 기준으로는 {top_raw_share * 100:.0f}%"
        + ("  <b class='j5-warn'>— 한 종목이 절반 넘게 만들었습니다</b>" if top_raw_share >= 0.55 else "")
        + f"<br>테마 전체 거래 페이스 <b>{theme_pace}</b>"
        + " · <span class='j5-muted'>전일 대비는 <b>매수+매도 합계 거래량</b>이 평소 이맘때보다 "
        "몇 배인지입니다. 순매수(들어온 돈)가 아닙니다 — 팔자가 쏟아져도 올라갑니다.</span>"
        + "</div>"
    )
    return (
        head
        + "<div class='j5-table-wrap'><table class='j5-table' style='min-width:860px'>"
        "<thead><tr><th>#</th><th class='j5-left'>종목</th><th>코드</th><th>현재가</th>"
        "<th>등락</th><th>구간 거래대금</th><th>테마 내 비중</th><th>오늘 누적</th>"
        "<th>전일 대비</th><th>소속테마</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


def _signal_table_html(rows: list[dict]) -> str:
    body = []
    for row in rows:
        try:
            features = json.loads(row.get("feature_json") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            features = {}
        model = str(row.get("model") or "?").upper()
        model_class = f"j5-model-{model.lower()}" if model in {"A", "B", "C"} else "j5-muted"
        score = float(row.get("score") or 0)
        body.append(
            "<tr>"
            f"<td class='j5-muted'>{_esc(str(row.get('captured_at') or '')[5:16])}</td>"
            f"<td class='j5-left j5-name'>{_esc(row.get('theme_name'))}</td>"
            f"<td><span class='j5-badge {model_class}'>{_esc(model)}</span> "
            f"<span class='j5-muted'>v{int(row.get('model_version') or 1)}</span></td>"
            f"<td class='j5-stage'>{_esc(row.get('stage'))}</td>"
            "<td><div class='j5-score-wrap'><div class='j5-score-bar'>"
            f"<div class='j5-score-fill' style='width:{max(0, min(score, 100)):.0f}%'></div></div>"
            f"<span class='j5-score-num'>{score:.0f}</span></div></td>"
            f"<td class='j5-good'>{_eok(features.get('interval_value'))}</td>"
            f"<td class='j5-left'>{_esc(row.get('reason'))}</td>"
            "</tr>"
        )
    return (
        "<div class='j5-table-wrap'><table class='j5-table'>"
        "<colgroup><col style='width:10%'><col style='width:17%'><col style='width:10%'>"
        "<col style='width:11%'><col style='width:12%'><col style='width:13%'>"
        "<col style='width:27%'></colgroup>"
        "<thead><tr><th>시각</th><th class='j5-left'>테마</th><th>모델</th>"
        "<th>단계</th><th>점수</th><th>거래활동</th><th class='j5-left'>감지 근거</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


def _outcome_table_html(rows: list[dict]) -> str:
    body = []
    for row in rows:
        forward = row.get("avg_forward_return_pct")
        relative = row.get("avg_relative_forward_return_pct")
        enough = bool(row.get("enough_samples"))
        hit_text = f"{float(row['hit_rate']) * 100:.1f}%" if enough else "20건 미만"
        model = str(row.get("model") or "?").upper()
        model_class = f"j5-model-{model.lower()}" if model in {"A", "B", "C"} else "j5-muted"
        body.append(
            "<tr>"
            f"<td><span class='j5-badge {model_class}'>{_esc(model)}</span> "
            f"<span class='j5-muted'>v{int(row.get('model_version') or 1)}</span></td>"
            f"<td>{int(row.get('horizon_minutes') or 0)}분</td>"
            f"<td>{int(row.get('sample_count') or 0):,}건</td>"
            f"<td class='{_sign_class(forward)}'>{_pct(forward, 3)}</td>"
            f"<td class='{_sign_class(relative)}'>{_pct(relative, 3)}</td>"
            f"<td class='{'j5-good' if enough else 'j5-amber'}'>{hit_text}</td>"
            "</tr>"
        )
    return (
        "<div class='j5-table-wrap'><table class='j5-table' style='min-width:720px'>"
        "<thead><tr><th>모델</th><th>확인구간</th><th>표본수</th>"
        "<th>평균 수익</th><th>시장대비 평균</th><th>적중률</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


def main() -> None:
    store.ensure_schema()
    # 폰에서만 글자·표를 줄인다(자비스5 표는 HTML이라 칸을 숨기지 않고 글자만 줄인다).
    st.markdown(mobile_ui.page_css(), unsafe_allow_html=True)
    st.title("자비스5 — 한국테마 선행감지 (실험)")
    st.markdown(
        "<div class='j5-note'><span class='j5-warn'>테스트용 관찰 도구입니다.</span> "
        "거래대금은 매수·매도 합계이므로 ‘자금 순유입’으로 표시하지 않습니다. "
        "A/B/C 모델이 여러 종목으로 거래활동과 가격이 퍼지는 순간을 따로 기록하고, "
        "5·10·20·30분 뒤 실제 성과가 쌓여야 의미를 판단합니다.</div>",
        unsafe_allow_html=True,
    )

    latest = store.latest_run()
    st.markdown(_summary_cards(latest), unsafe_allow_html=True)

    left, middle, right = st.columns([1.2, 1.2, 1.4])
    with left:
        if st.button("전체 테마 스냅샷 1회 수집", type="primary", width="stretch"):
            with st.spinner("네이버 전체 테마 원자료를 수집하는 중입니다…"):
                result = collector.collect_once()
            st.session_state["j5_last_collection"] = result
            if result.get("ok"):
                st.success(
                    f"{result['theme_count']}개 테마 · {result['stock_row_count']}개 종목행 저장 "
                    f"({result['elapsed_seconds']:.1f}초)"
                )
                st.rerun()
            else:
                st.error(f"수집 실패: {result.get('error')}")
    with middle:
        # 노트북이 꺼져 있던 날 클라우드가 대신 모아 둔 자료를 합친다(2026-07-24).
        if st.button("클라우드에 쌓인 자료 가져오기", width="stretch"):
            with st.spinner("내려받아 둔 파일을 로컬 DB에 합치는 중입니다…"):
                merged = sync.import_dir()
            if not merged.get("ok"):
                st.warning(merged.get("error") or "가져올 자료가 없습니다")
            elif merged.get("added_runs"):
                st.success(
                    f"{merged['day_count']}일치 중 새로 들어온 수집 {merged['added_runs']}회 · "
                    f"테마 {merged['added_theme_rows']:,}행"
                )
                st.rerun()
            else:
                st.info("이미 다 들어와 있습니다. 새로 합칠 자료가 없습니다.")
    with right:
        _dates = sync.available_dates()
        _have = f"내려받은 자료: {len(_dates)}일치({_dates[0]}~{_dates[-1]})" if _dates else "내려받은 자료 없음"
        st.caption(
            f"{_have}. 자료는 GitHub이 장중에 대신 모으므로 노트북을 꺼 둬도 쌓입니다. "
            "`자비스5_자료받기.bat`을 실행하면 최신 자료를 내려받아 자동으로 합칩니다. "
            "이 컴퓨터에서 직접 3분마다 모으려면 `run_jarvis5_collector.bat`을 켜세요."
        )

    st.markdown(
        "<div class='j5-section-title'>선행 후보 종합순위 · 거래금액순 아님</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='j5-legend'><b class='j5-good'>표 읽는 법</b> — "
        "<b>순위는 분당 거래금액이 큰 순서가 아닙니다.</b> 과거 같은 시각 대비 증가, 실제 거래에 "
        "참여한 종목 비율, 상승 종목 확산, 한 종목 독점 여부를 합친 점수입니다. "
        "<b>분당 거래활동</b>은 매수·매도 합계 거래대금을 테마 크기와 중복 소속으로 보정한 참고값입니다. "
        "<b>최근 흐름</b> 미니차트는 가장 최근 수집 12회를 <b>실제 시각 기준</b>으로 이은 선입니다. "
        "가로 점선은 그 구간이 시작된 수준이라 선이 점선 위면 활동이 늘어난 것입니다. 마우스를 "
        "올리면 실제 시간대와 변화율이 나옵니다. 수집 간격이 1분보다 짧은 시점은 누적 거래대금이 "
        "아직 갱신되기 전이라 값이 크게 튀므로 차트에서 뺍니다. 각 테마 자체 흐름이라 "
        "삼성전자와 작은 종목의 절대금액을 "
        "서로 직접 비교하지 않습니다. <b>동일시각 배수</b>는 과거 같은 시각 대비이며, "
        "3거래일 전까지는 ‘학습중’으로 표시합니다. "
        "<b>상승확산</b>은 오른 종목 수, <b>거래참여</b>는 실제 거래가 늘어난 종목 수입니다. "
        "<b>최대종목 기여</b>가 55%를 넘으면 한 종목이 테마를 끌어올린 것으로 보고 경보에서 제외합니다.<br>"
        "<span class='j5-pos'>+ 상승은 빨강</span> · "
        "<span class='j5-neg'>− 하락은 파랑</span> (한국시장 색 규칙)</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='j5-formula'>"
        "<div class='j5-formula-cell'><b>35점</b>과거 동일시각 대비 증가</div>"
        "<div class='j5-formula-cell'><b>15점</b>전체 테마 중 활동 순위</div>"
        "<div class='j5-formula-cell'><b>20점</b>거래 참여 종목 비율</div>"
        "<div class='j5-formula-cell'><b>20점</b>상승 종목 확산</div>"
        "<div class='j5-formula-cell'><b>10점</b>단일종목 독점 방지</div>"
        "</div>"
        "<div class='j5-explain'><span class='j5-guide-key'>학습기간 점수:</span> "
        "동일시각 자료가 쌓이기 전에는 활동순위 20점·거래참여 30점·상승확산 30점·독점방지 20점으로 "
        "임시 계산합니다. 시가총액으로 단순 나누면 작은 저유동성 종목이 과대평가되므로 사용하지 않습니다. "
        "삼성전자·SK하이닉스처럼 평소 거래가 큰 종목은 동일시각 자기 기준선에서 상쇄되고, "
        "여러 테마에 겹친 영향과 단일종목 집중은 별도로 감점합니다.</div>",
        unsafe_allow_html=True,
    )
    # 순위는 '구간 거래활동이 살아 있던 마지막 수집'으로 매긴다. 마감 뒤나 마감
    # 동시호가에는 늘어난 거래가 없어 구간 지표가 전부 0이 되고, 그대로 줄을 세우면
    # 266개가 모두 0점인 채 뜻 없는 1위가 남는다(2026-07-23 실측).
    active_run = store.latest_active_run()
    rank_run_id = (active_run or {}).get("id")
    latest_run_id = (latest or {}).get("id")
    # 두 수집을 식별할 수 있을 때만 비교한다 — 최신 수집 정보에 id가 없을 수도 있다.
    if rank_run_id is not None and latest_run_id is not None and int(rank_run_id) != int(latest_run_id):
        st.warning(
            f"장중 거래가 멈춘 뒤라 최신 수집({str(latest.get('captured_at'))[11:16]})에는 "
            f"구간 지표가 없습니다. 아래 순위는 값이 살아 있던 마지막 시점 "
            f"**{str(active_run.get('captured_at'))[11:16]}** 기준입니다."
        )
    all_latest_rows = store.latest_theme_rows(limit=400, run_id=rank_run_id)
    latest_rows = engine.rank_lead_themes(all_latest_rows)[:20]
    if latest_rows:
        histories = store.theme_activity_history(
            [row.get("theme_no") for row in latest_rows],
            limit_runs=12,
        )
        # 미니차트가 담고 있는 실제 시간대와 점 개수를 알려준다 — '약 30분'처럼
        # 고정 문구를 쓰면 수집이 띄엄띄엄한 날 거짓말이 된다(2026-07-24 사용자 지적).
        _sample = max(
            (_history_points(rows) for rows in histories.values()),
            key=len,
            default=[],
        )
        if len(_sample) < 2:
            st.warning(
                f"미니차트를 그릴 수집 시점이 오늘 **{len(_sample)}개**뿐이라 선을 그릴 수 없습니다. "
                "장중 3분마다 자동 수집되도록 `run_jarvis5_collector.bat`을 켜 주세요."
            )
        else:
            _times = [p["at"] for p in _sample if p["at"] is not None]
            _gap = (
                (_times[-1] - _times[0]).total_seconds() / 60 / max(1, len(_times) - 1)
                if len(_times) >= 2 else 0
            )
            st.caption(
                f"미니차트 구간: **{_span_text(_sample)}** · 평균 수집 간격 {_gap:.0f}분. "
                "가로축은 실제 시각이라 오래 비어 있던 구간은 선이 길게 늘어납니다."
                + (
                    " 3분 간격 자동 수집(`run_jarvis5_collector.bat`)이 꺼져 있어 점이 드뭅니다."
                    if _gap > 10 else ""
                )
            )
        st.markdown(_latest_table_html(latest_rows, histories), unsafe_allow_html=True)
        # 위 표는 그대로 두고, 아래에 테마별 구성종목을 펼쳐 볼 수 있게 덧붙인다.
        # 어떤 종목이 그 테마를 끌어올렸는지 눈으로 확인하기 위한 것이다.
        stock_groups = store.latest_theme_stock_rows(
            [row.get("theme_no") for row in latest_rows],
            run_id=rank_run_id,
        )
        st.markdown(
            "<div class='j5-section-title'>테마별 구성종목 · 누르면 펼쳐집니다</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "구간 거래대금이 큰 순서입니다. 맨 위 종목이 그 테마 점수를 끌어올린 종목입니다. "
            "‘테마 내 비중’이 한 종목에 쏠려 있으면 테마가 퍼진 것이 아니라 그 종목 혼자 움직인 것입니다. "
            "‘전일 대비’는 오늘 거래량이 전일 하루치 대비 몇 배 페이스인지로, 장 경과 시간을 보정한 값입니다 "
            "(1.00배 = 평소와 같은 속도)."
        )
        progress = _session_progress(
            (active_run or latest or {}).get("captured_at")
        )
        for rank, row in enumerate(latest_rows, 1):
            theme_no = row.get("theme_no")
            stocks = stock_groups.get(int(theme_no)) if theme_no is not None else None
            flags = row.get("lead_flags") or []
            label = (
                f"{rank}위  {row.get('theme_name')}"
                f"   ·  선행 후보점수 {float(row.get('lead_score') or 0):.1f}"
                f"  ·  종목 {int(row.get('member_count') or 0)}개"
                + (f"   ⚠ {' / '.join(flags)}" if flags else "")
            )
            with st.expander(label):
                if flags:
                    st.markdown(
                        "<div class='j5-note'><b class='j5-warn'>감점 사유</b> — "
                        + _esc(" / ".join(flags))
                        + f" (합계 −{float(row.get('lead_penalty') or 0):.0f}점)</div>",
                        unsafe_allow_html=True,
                    )
                st.markdown(
                    _stock_table_html(stocks or [], row, progress),
                    unsafe_allow_html=True,
                )
    else:
        st.info("아직 원자료가 없습니다. 1회 수집하거나 별도 수집기를 실행하십시오.")

    st.markdown("<div class='j5-section-title'>실험 감지 기록</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='j5-guide-grid'>"
        "<div class='j5-guide-card'><div class='j5-guide-title'>A 거래활동 급증</div>"
        "과거 동일시각보다 활동이 튀고, 3종목 이상이 참여하며 한 종목 독점이 아닐 때 기록합니다.</div>"
        "<div class='j5-guide-card'><div class='j5-guide-title'>B 다종목 확산</div>"
        "테마 안에서 오른 종목 비율과 거래 참여 종목 수가 함께 넓어질 때 기록합니다.</div>"
        "<div class='j5-guide-card'><div class='j5-guide-title'>C 급증 + 가격확산</div>"
        "A와 B가 동시에 나타난 강한 조합입니다. 이미 4% 이상 오른 테마는 추격 방지를 위해 제외합니다.</div>"
        "</div>"
        "<div class='j5-explain'><span class='j5-guide-key'>중요:</span> 이 기록은 "
        "<b>매수 신호가 아니라 검증 전 후보</b>입니다. 같은 테마가 여러 번 잡혀도 각각의 시점부터 "
        "5·10·20·30분 뒤 결과를 따로 측정합니다.</div>",
        unsafe_allow_html=True,
    )
    signals = store.recent_signals(limit=50)
    if signals:
        st.markdown(_signal_table_html(signals), unsafe_allow_html=True)
    else:
        st.info("첫 스냅샷은 기준점만 저장합니다. 두 번째 이후부터 조건 충족 시 실험 기록이 생깁니다.")

    st.markdown("<div class='j5-section-title'>사후 검증</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='j5-explain'><b>평균 수익</b>은 감지 시점 이후 실제 테마 수익률, "
        "<b>시장대비 평균</b>은 같은 구간의 시장 움직임을 뺀 값입니다. "
        "<b>적중</b>은 ‘수익률 &gt; 0’이면서 ‘시장대비 &gt; 0’인 경우만 셉니다. "
        "표본 20건 전에는 숫자가 우연에 흔들리므로 적중률을 숨깁니다.</div>",
        unsafe_allow_html=True,
    )
    summary = store.outcome_summary(minimum_samples=20)
    if summary:
        st.markdown(_outcome_table_html(summary), unsafe_allow_html=True)
    else:
        st.caption("신호 뒤 5·10·20·30분 스냅샷이 쌓이면 자동으로 채워집니다.")

    with st.expander("저장 위치와 기술 기준"):
        st.markdown(
            "- 전체 266개 안에서 횡단면 순위를 비교하되, 최소 활동량·참여종목 수 같은 절대 품질 관문도 함께 적용\n"
            "- 한 종목이 여러 테마에 속하면 `1/√소속테마수`로 영향 축소\n"
            "- 기여 종목이 60% 이상 겹치는 당일 신호는 대표 테마 하나만 남김\n\n"
            f"전용 DB: `{Path(store.DB_PATH)}` — 기존 `db/jarvis.sqlite3`과 완전히 분리"
        )


main()

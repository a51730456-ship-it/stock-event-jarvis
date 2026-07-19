"""자비스3 — 미국 테마 레이더와 실제 매수 기록 페이지."""

from __future__ import annotations

from datetime import date

import streamlit as st

st.set_page_config(page_title="자비스3 — 미국 테마 레이더", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stSidebarNav"] a { padding: 0.7rem 1rem !important; }
    [data-testid="stSidebarNav"] a,
    [data-testid="stSidebarNav"] a * {
        font-size: 1.8rem !important;
        font-weight: 800 !important;
        color: #ffb020 !important;
        line-height: 1.4 !important;
    }
    [data-testid="stSidebarNav"] li:first-child a p { font-size: 0 !important; }
    [data-testid="stSidebarNav"] li:first-child a p::before {
        content: "자비스1";
        font-size: 1.8rem;
        font-weight: 800;
        color: #ffb020;
    }
    div[class*="st-key-j3_theme_choice"] [data-baseweb="button-group"] {
        gap: 0.35rem;
    }
    .j3-score-guide, .j3-market-flow {
        color: #44f0a1;
        font-size: 1rem;
        font-weight: 800;
        line-height: 1.65;
    }
    .j3-score-guide { margin-top: 0.35rem; }
    .j3-market-flow {
        margin: 1.9rem 0 0.8rem 0;
        padding: 0.75rem 1rem;
        border-left: 4px solid #44f0a1;
        background: rgba(34, 197, 94, 0.08);
        border-radius: 0.4rem;
    }
    .j3-action-box {
        color: #4da6ff;
        font-size: 1rem;
        font-weight: 800;
        line-height: 1.65;
        margin-top: 1.9rem;
        margin-bottom: 0.8rem;
        padding: 0.8rem 1rem;
        border: 1px solid rgba(77, 166, 255, 0.45);
        background: rgba(37, 99, 235, 0.13);
        border-radius: 0.55rem;
    }
    h1 { font-size: 2.05rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.65rem !important; }
    /* 종목 상세 색 규칙: 종목명 밝은 보라, 라벨 코발트, +파랑/−빨강, 내용 초록 */
    .j3-stock-name { color: #c084fc; font-size: 1.7rem; font-weight: 800; line-height: 1.2; margin-top: 0.3rem; }
    .j3-stock-sub { color: #9aa0aa; font-size: 0.95rem; margin: 0.1rem 0 0.7rem; }
    .j3-metric-row { display: flex; flex-wrap: wrap; gap: 1.6rem; margin: 0.2rem 0 0.4rem; }
    .j3-mc { min-width: 120px; }
    .j3-mc-label { color: #4da6ff; font-size: 0.92rem; font-weight: 800; }
    .j3-mc-val { font-size: 1.5rem; font-weight: 800; color: #e6e6e6; line-height: 1.25; }
    .j3-mc-sub { font-size: 0.95rem; font-weight: 800; }
    .j3-up { color: #4da6ff; }
    .j3-down { color: #ff5b5b; }
    .j3-muted { color: #9aa0aa; }
    .j3-section-title { color: #4da6ff; font-size: 1.2rem; font-weight: 800; margin: 1rem 0 0.5rem; }
    .j3-factor-table { width: 100%; border-collapse: collapse; margin-bottom: 0.5rem; font-size: 0.95rem; }
    .j3-factor-table th { text-align: center; color: #4da6ff; font-weight: 800; padding: 0.45rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.18); }
    .j3-factor-table td { color: #44f0a1; font-weight: 700; padding: 0.4rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.06); }
    .j3-factor-table td.j3-fac-name { text-align: left; }
    .j3-factor-table td.j3-fac-val { text-align: center; }
    .j3-reason-card { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.09); border-radius: 0.55rem; padding: 0.6rem 0.75rem; height: 100%; }
    .j3-reason-title { color: #4da6ff; font-weight: 800; font-size: 0.95rem; margin-bottom: 0.25rem; }
    .j3-reason-body { color: #44f0a1; font-weight: 700; font-size: 0.9rem; line-height: 1.45; }
    .j3-chart-title { color: #e6e6e6; font-weight: 800; font-size: 1rem; margin-bottom: 0.1rem; }
    .j3-leader-name { font-size: 1.2rem; font-weight: 800; color: #e6e6e6; line-height: 1.25; }
    .j3-leader-name .j3-medal { font-size: 1.6rem; vertical-align: -2px; }
    .j3-leader-score-label { color: #4da6ff; font-size: 0.85rem; font-weight: 800; margin-top: 0.35rem; }
    .j3-leader-score { color: #ff5b5b; font-size: 1.9rem; font-weight: 800; line-height: 1.1; }
    .j3-leader-state { color: #9aa0aa; font-size: 0.9rem; }
    .j3-green { color: #44f0a1; }
    .j3-green-strong { color: #22c55e; font-weight: 800; }
    .j3-theme-box { background: rgba(77,166,255,0.08); border: 1px solid rgba(77,166,255,0.3); border-radius: 0.55rem; padding: 0.7rem 0.9rem; font-size: 0.95rem; line-height: 1.7; margin-bottom: 0.6rem; }
    .j3-reason-mustard { background: rgba(234,179,8,0.12); border: 1px solid rgba(234,179,8,0.42); color: #e6c34a; border-radius: 0.5rem; padding: 0.6rem 0.8rem; font-weight: 700; }
    .j3-chart-heading { margin-top: 1.6rem; font-size: 1.15rem; font-weight: 800; color: #e6e6e6; }
    .j3-theme-badge { display: inline-block; background: rgba(255,176,32,0.16); color: #ffb020; border: 1px solid #ffb020; border-radius: 0.5rem; padding: 0.15rem 0.7rem; font-weight: 800; font-size: 1.05rem; margin-right: 0.4rem; }
    .j3-flow-label { color: #44f0a1; font-weight: 800; }
    .j3-flow-body { color: #4da6ff; font-weight: 800; }
    .j3-action-label { color: #4da6ff; font-weight: 800; }
    .j3-action-posture { color: #ff5b5b; font-weight: 800; }
    .j3-action-detail { color: #ff9d3b; font-weight: 800; }
    .j3-top-row { display: flex; gap: 2rem; flex-wrap: wrap; margin-bottom: 0.3rem; }
    .j3-top-cell { min-width: 150px; }
    .j3-top-label { color: #9aa0aa; font-size: 0.9rem; }
    .j3-top-val { font-size: 1.7rem; font-weight: 800; line-height: 1.2; }
    .j3-top-sub { font-size: 0.95rem; font-weight: 700; }
    .j3-theme-table { width: 100%; border-collapse: collapse; font-size: 0.92rem; table-layout: fixed; }
    .j3-theme-table th { text-align: center; color: #9aa0aa; font-weight: 800; padding: 0.5rem 0.4rem; border-bottom: 1px solid rgba(255,255,255,0.18); }
    .j3-theme-table td { text-align: center; padding: 0.45rem 0.4rem; border-bottom: 1px solid rgba(255,255,255,0.06); color: #e6e6e6; overflow: hidden; text-overflow: ellipsis; }
    .j3-theme-table td.j3-th-name { font-weight: 800; }
    .j3-th-selected { background: rgba(255,176,32,0.13); }
    .j3-th-muted { color: #9aa0aa; }
    .j3-barwrap { display: flex; align-items: center; gap: 6px; }
    .j3-bar { position: relative; flex: 1; background: rgba(255,255,255,0.10); border-radius: 4px; height: 14px; overflow: hidden; }
    .j3-bar-fill { height: 14px; background: #44f0a1; }
    .j3-bar-blue { background: #4da6ff; }
    .j3-bar-num { font-size: 0.82rem; font-weight: 700; color: #e6e6e6; min-width: 32px; text-align: right; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _login_gate() -> None:
    if st.session_state.get("authenticated"):
        return
    st.markdown("## 자비스3 — 미국 테마 레이더")
    st.caption("승인된 사용자만 접근할 수 있습니다. 여기서 바로 로그인할 수 있습니다.")
    try:
        password = st.secrets.get("APP_PASSWORD")
    except Exception:
        password = None
    if not password:
        st.warning(".streamlit/secrets.toml에 APP_PASSWORD 설정이 필요합니다.")
        st.stop()
    entered = st.text_input("비밀번호", type="password", key="j3_login_password")
    if st.button("자비스3 로그인", key="j3_login_submit", width="stretch"):
        if entered == password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()


_login_gate()

import altair as alt
import pandas as pd

import jarvis3_data as j3data
import jarvis3_store as j3store


def _pct(value) -> str:
    return "—" if value is None else f"{float(value):+.2f}%"


def _price(value) -> str:
    return "—" if value is None else f"${float(value):,.2f}"


def _number(value, digits=1) -> str:
    return "—" if value is None else f"{float(value):,.{digits}f}"


def _sign_class(value) -> str:
    """미국장 색: 상승(+)은 푸른색, 하락(−)은 붉은색."""
    if value is None:
        return "j3-muted"
    try:
        return "j3-up" if float(value) >= 0 else "j3-down"
    except (TypeError, ValueError):
        return "j3-muted"


def _signed_pct_html(value) -> str:
    return f"<span class='{_sign_class(value)}'>{_pct(value)}</span>"


def _top_metric(label, value, value_color, sub, *, sub_color=None, sub_signed=False) -> str:
    if sub_signed:
        sub_html = f"<div class='j3-top-sub {_sign_class(sub)}'>{_pct(sub)}</div>"
    else:
        sub_html = f"<div class='j3-top-sub' style='color:{sub_color or '#9aa0aa'}'>{sub}</div>"
    return (
        f"<div class='j3-top-cell'><div class='j3-top-label'>{label}</div>"
        f"<div class='j3-top-val' style='color:{value_color}'>{value}</div>{sub_html}</div>"
    )


def _theme_table_html(ranking: dict, selected: str | None) -> str:
    """20개 테마 순위를 가운데 정렬·좁은 칸으로 HTML 표에 그린다(상태는 색 구분)."""
    status_color = {"주도": "#44f0a1", "관찰": "#ff9d3b", "약함": "#9aa0aa"}
    body = []
    for row in ranking.get("rows", []):
        name = row.get("name", "")
        highlight = " j3-th-selected" if name == selected else ""
        if not row.get("ok"):
            body.append(
                f"<tr class='j3-th-row{highlight}'><td>{row.get('rank', '')}</td>"
                f"<td class='j3-th-name'>{name}</td><td>{row.get('etf', '')}</td>"
                "<td colspan='5' class='j3-th-muted'>자료 부족</td></tr>"
            )
            continue
        score = float(row.get("score") or 0)
        breadth = row.get("breadth")
        change, rs20 = row.get("change_pct"), row.get("rs20")
        status = row.get("status", "")
        sc = status_color.get(status, "#9aa0aa")
        score_bar = (
            "<div class='j3-barwrap'><div class='j3-bar'>"
            f"<div class='j3-bar-fill' style='width:{min(score, 100):.0f}%'></div></div>"
            f"<span class='j3-bar-num'>{score:.1f}</span></div>"
        )
        breadth_bar = "—" if breadth is None else (
            "<div class='j3-barwrap'><div class='j3-bar'>"
            f"<div class='j3-bar-fill j3-bar-blue' style='width:{min(float(breadth), 100):.0f}%'></div></div>"
            f"<span class='j3-bar-num'>{float(breadth):.0f}%</span></div>"
        )
        rs_text = "—" if rs20 is None else f"{float(rs20):+.1f}%p"
        body.append(
            f"<tr class='j3-th-row{highlight}'>"
            f"<td>{row.get('rank', '')}</td>"
            f"<td class='j3-th-name'>{name}</td>"
            f"<td>{row.get('etf', '')}</td>"
            f"<td>{score_bar}</td>"
            f"<td style='color:{sc}; font-weight:800'>{status}</td>"
            f"<td class='{_sign_class(change)}'>{_pct(change)}</td>"
            f"<td class='{_sign_class(rs20)}'>{rs_text}</td>"
            f"<td>{breadth_bar}</td></tr>"
        )
    return (
        "<table class='j3-theme-table'><colgroup>"
        "<col style='width:6%'><col style='width:20%'><col style='width:8%'>"
        "<col style='width:20%'><col style='width:8%'><col style='width:10%'>"
        "<col style='width:14%'><col style='width:14%'></colgroup>"
        "<thead><tr><th>순위</th><th>테마</th><th>ETF</th><th>조건점수</th>"
        "<th>상태</th><th>당일</th><th>20일 상대강도</th><th>구성종목 확산</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
    )


def _safe_error_text(error) -> str:
    text = str(error or "일시적인 온라인 조회 오류")
    return text[:220]


def _selected_rows(event) -> list[int]:
    try:
        rows = [int(value) for value in event.selection.rows]
        if rows:
            return rows
        cells = list(event.selection.cells)
        return [int(cells[0][0])] if cells else []
    except (AttributeError, KeyError, TypeError, ValueError):
        try:
            selection = event.get("selection", {})
            rows = [int(value) for value in selection.get("rows", [])]
            if rows:
                return rows
            cells = selection.get("cells", [])
            return [int(cells[0][0])] if cells else []
        except (AttributeError, TypeError, ValueError):
            return []


def _trend_position(row: dict, label: str) -> str:
    current = row.get("current")
    sma20, sma50 = row.get("sma20"), row.get("sma50")
    if current is None or sma20 is None or sma50 is None:
        return f"{label} 추세 자료가 부족합니다"
    above20, above50 = current > sma20, current > sma50
    if above20 and above50:
        return f"{label}은 20·50일선 위로 단기·중기 추세가 모두 살아 있습니다"
    if above50:
        return f"{label}은 50일선 위지만 20일선 아래여서 중기 추세 속 단기 조정입니다"
    if above20:
        return f"{label}은 20일선은 회복했지만 50일선 아래라 추세 전환 확인이 필요합니다"
    return f"{label}은 20·50일선 아래로 단기·중기 흐름이 모두 약합니다"


def _market_flow_text(overview: dict) -> str:
    rows = overview.get("rows", {})
    sections = [
        _trend_position(rows.get("SPY", {}), "S&P500"),
        _trend_position(rows.get("QQQ", {}), "나스닥100"),
    ]
    iwm = rows.get("IWM", {})
    if iwm.get("current") is not None and iwm.get("sma50") is not None:
        if iwm["current"] > iwm["sma50"]:
            sections.append("IWM이 50일선 위여서 중소형주도 중기 추세를 지킨다는 ‘중소형주 동행’ 조건은 충족했습니다")
        else:
            sections.append("IWM이 50일선 아래라 중소형주는 대형주 상승에 충분히 동참하지 못하고 있습니다")
    vix_value = rows.get("^VIX", {}).get("current")
    if vix_value is not None:
        if vix_value < 25:
            sections.append(f"VIX {vix_value:.1f}은 25 미만으로 공포·변동성은 과열 구간이 아닙니다")
        elif vix_value < 35:
            sections.append(f"VIX {vix_value:.1f}은 25~35 경계 구간이라 변동성 확대에 주의해야 합니다")
        else:
            sections.append(f"VIX {vix_value:.1f}은 35 이상으로 시장 공포와 급변 위험이 매우 높습니다")
    return ". ".join(sections) + "."


def _market_score_detail(overview: dict) -> str:
    breakdown = overview.get("score_breakdown") or []
    if not breakdown:
        return "세부 점수는 다음 온라인 갱신에서 표시됩니다."
    earned = [f"{item['label']} {item['earned']}/{item['max']}점" for item in breakdown if item.get("earned")]
    missed = [item["label"] for item in breakdown if not item.get("earned")]
    earned_text = ", ".join(earned) if earned else "충족 신호 없음"
    missed_text = ", ".join(missed) if missed else "없음"
    return f"현재 획득: {earned_text} · 미충족: {missed_text}"


def _market_action_detail(overview: dict) -> str:
    score = float(overview.get("score") or 0)
    if score >= 75:
        return (
            "시장 추세와 위험선호가 충분히 확인된 구간입니다. 그래도 아무 종목이나 매수하지 않고, "
            "주도 테마이면서 종목점수 75점 이상인 대장주가 기준가격을 통과할 때만 분할 진입합니다."
        )
    if score >= 50:
        return (
            "시장 일부만 강한 선별 구간입니다. 매수 비중을 평소보다 줄이고, 주도 테마의 1~3위 종목 중 "
            "돌파 또는 20일선 눌림 조건이 확인된 종목만 심사합니다."
        )
    return (
        "상승장 확인 조건이 부족하므로 신규 매수를 보류합니다. 보유 종목의 손절 기준과 비중을 먼저 관리하고, "
        "SPY·QQQ의 20·50일선 회복과 시장점수 50점 이상을 확인한 뒤 다시 매수 심사를 시작합니다."
    )


def _relative_strength_guide(value) -> tuple[str, str]:
    if value is None:
        return "판단 불가", "상대강도 자료가 부족합니다."
    value = float(value)
    if value >= 10:
        level = "매우 강함"
    elif value >= 5:
        level = "강함"
    elif value >= 0:
        level = "시장 대비 우위"
    elif value >= -5:
        level = "시장 대비 약세"
    else:
        level = "매우 약함"
    meaning = f"최근 20거래일 동안 해당 테마 ETF가 SPY보다 {abs(value):.1f}%p {'더 올랐거나 덜 내렸습니다' if value >= 0 else '뒤처졌습니다'}."
    return level, meaning


def _leader_table(leaders: list[dict]) -> pd.DataFrame:
    rank_labels = {1: "🟡 1위", 2: "⚪ 2위", 3: "🟠 3위"}
    rows = []
    for leader in leaders[:6]:
        metrics, plan = leader["metrics"], leader["plan"]
        rank = int(leader["rank"])
        rows.append({
            "순위": rank_labels.get(rank, f"{rank}위"),
            "종목": leader["name"],
            "티커": leader["ticker"],
            "조건점수": leader["score"],
            "52주 고가 대비": metrics.get("from_high_pct"),
            "20일 수익률": metrics.get("ret20"),
            "매수 상태": plan.get("state"),
            "상세 연결": "클릭하면 상세 선택" if rank <= 3 else "예비 관찰",
        })
    return pd.DataFrame(rows)


def _price_chart(payload: dict, timeframe: str, include_volume: bool = False, height: int | None = None):
    price = payload["price"].reset_index()
    date_column = price.columns[0]
    price = price.rename(columns={date_column: "날짜", "Close": "주가", "MA20": "20일선", "MA50": "50일선"})
    available = [column for column in ("주가", "20일선", "50일선") if column in price.columns]
    long_price = price.melt(id_vars=["날짜"], value_vars=available, var_name="구분", value_name="가격").dropna()
    line_height = height if height is not None else (220 if include_volume else 315)
    line = (
        alt.Chart(long_price)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("날짜:T", title=None, axis=alt.Axis(format="%y-%m", labelAngle=0, tickCount=5)),
            y=alt.Y("가격:Q", title=None, scale=alt.Scale(zero=False), axis=alt.Axis(tickCount=5)),
            color=alt.Color(
                "구분:N",
                title=None,
                scale=alt.Scale(
                    domain=["주가", "20일선", "50일선"],
                    range=["#69bff8", "#ff4d4f", "#a855f7"],
                ),
                legend=alt.Legend(orient="top", direction="horizontal"),
            ),
            tooltip=[alt.Tooltip("날짜:T", title="날짜"), alt.Tooltip("구분:N"), alt.Tooltip("가격:Q", format=",.2f")],
        )
        .properties(height=line_height)
    )
    volume = payload.get("volume")
    if not include_volume or volume is None or volume.empty:
        return line
    volume_frame = volume.reset_index()
    volume_date_column = volume_frame.columns[0]
    volume_frame = volume_frame.rename(columns={volume_date_column: "날짜", "Volume": "거래량"})
    bars = (
        alt.Chart(volume_frame)
        .mark_bar(color="#3b82f6", opacity=0.65)
        .encode(
            x=alt.X("날짜:T", title=None, axis=alt.Axis(format="%y-%m", labelAngle=0, tickCount=5)),
            y=alt.Y("거래량:Q", title="거래량", axis=alt.Axis(format="~s", tickCount=3)),
            tooltip=[alt.Tooltip("날짜:T", title="날짜"), alt.Tooltip("거래량:Q", format=",.0f")],
        )
        .properties(height=80)
    )
    return alt.vconcat(line, bars, spacing=4).resolve_scale(x="shared")


@st.fragment(run_every=60)
def _render_market_overview() -> None:
    """시장판단은 페이지 최상단에서 1분마다 독립 갱신한다."""
    overview = j3data.get_market_overview()
    st.session_state["j3_market_overview"] = overview
    st.subheader("미국 전체시장 판단")
    if not overview.get("ok"):
        st.error(f"시장 자료 조회 실패: {_safe_error_text(overview.get('error'))}")
        st.caption("네트워크가 복구되면 1분 자동 갱신에서 다시 시도합니다.")
        return

    phase = overview.get("phase", {}).get("label", "—")
    regime_color = {"방어 우선": "#ff5b5b", "중립·선별": "#ff9d3b", "상승 우위": "#44f0a1"}.get(overview["regime"], "#e6e6e6")
    if phase == "정규장 시간":
        phase_color = "#44f0a1"
    elif phase in ("프리마켓", "애프터마켓"):
        phase_color = "#ff9d3b"
    else:
        phase_color = "#ff5b5b"
    spy_row, qqq_row = overview["rows"]["SPY"], overview["rows"]["QQQ"]
    vix_value = overview["rows"].get("^VIX", {}).get("current")
    top_cells = [
        _top_metric("시장 국면", overview["regime"], regime_color, f"조건 {overview['score']}/100"),
        _top_metric("SPY", _price(spy_row.get("current")), "#e6e6e6", spy_row.get("change_pct"), sub_signed=True),
        _top_metric("QQQ", _price(qqq_row.get("current")), "#e6e6e6", qqq_row.get("change_pct"), sub_signed=True),
        _top_metric("장 상태", phase, phase_color, f"VIX {_number(vix_value, 2)}"),
    ]
    st.markdown(f"<div class='j3-top-row'>{''.join(top_cells)}</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="j3-score-guide">
            조건점수 {overview['score']}/100은 상승장 확인 조건에서 얻은 점수이며 승률이 아닙니다.<br>
            0~49점 방어 우선 · 50~74점 중립·선별 · 75~100점 상승 우위<br>
            {_market_score_detail(overview)}
        </div>
        <div class="j3-market-flow">
            <span class="j3-flow-label">시장 전체 흐름</span> : <span class="j3-flow-body">{_market_flow_text(overview)}</span>
        </div>
        <div class="j3-action-box">
            <span class="j3-action-label">행동 기준</span> : <span class="j3-action-posture">{overview['posture']}</span><br>
            <span class="j3-action-detail">{_market_action_detail(overview)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    stale_text = " · 마지막 정상 자료 표시 중" if overview.get("stale") else ""
    st.caption(
        f"최근 가용 시세: {overview.get('checked_at') or '시각 확인 불가'}{stale_text} · "
        "1분 자동 갱신 · 거래소 정식 실시간 피드가 아니므로 지연될 수 있음"
    )


@st.fragment(run_every=60)
def _render_selected_live_quote(stock_score=None, entry_state=None) -> None:
    ticker = st.session_state.get("j3_selected_ticker")
    if not ticker:
        return
    quote = j3data.get_live_quote(ticker)
    st.session_state["j3_selected_live_quote"] = quote
    if not quote.get("ok"):
        st.warning(f"{ticker} 실시간 시세 갱신 실패: {_safe_error_text(quote.get('error'))}")
        return
    # 최근가·52주대비·20일수익률·14일변동성·종목조건점수를 한 줄에 표시한다.
    # 라벨은 코발트, 증감 부호는 미국장 색(+파랑/−빨강), 종목조건점수는 우측 끝.
    score_val = f"{float(stock_score):.1f}/100" if stock_score is not None else "—"
    state_sub = f"<div class='j3-mc-sub j3-muted'>{entry_state}</div>" if entry_state else ""
    change_sub = f"<div class='j3-mc-sub {_sign_class(quote.get('change_pct'))}'>{_pct(quote.get('change_pct'))}</div>"
    cells = [
        f"<div class='j3-mc'><div class='j3-mc-label'>최근가</div>"
        f"<div class='j3-mc-val'>{_price(quote.get('current'))}</div>{change_sub}</div>",
        f"<div class='j3-mc'><div class='j3-mc-label'>52주 신고가 대비</div>"
        f"<div class='j3-mc-val {_sign_class(quote.get('from_high_pct'))}'>{_pct(quote.get('from_high_pct'))}</div></div>",
        f"<div class='j3-mc'><div class='j3-mc-label'>20일 수익률</div>"
        f"<div class='j3-mc-val {_sign_class(quote.get('ret20'))}'>{_pct(quote.get('ret20'))}</div></div>",
        f"<div class='j3-mc'><div class='j3-mc-label'>14일 변동성(ATR)</div>"
        f"<div class='j3-mc-val {_sign_class(quote.get('atr_pct'))}'>{_pct(quote.get('atr_pct'))}</div></div>",
        f"<div class='j3-mc'><div class='j3-mc-label'>종목 조건점수</div>"
        f"<div class='j3-mc-val j3-green'>{score_val}</div>{state_sub}</div>",
    ]
    st.markdown(f"<div class='j3-metric-row'>{''.join(cells)}</div>", unsafe_allow_html=True)
    stale_text = " · 마지막 정상 자료" if quote.get("stale") else ""
    st.caption(f"시세 기준 {quote.get('source_time') or '—'}{stale_text} · 1분 자동 갱신")


def _load_theme_rankings() -> dict:
    with st.spinner("미국 20개 테마와 구성종목을 조회하는 중입니다…"):
        return j3data.get_theme_rankings()


def _render_leader_comparison(leaders: list[dict]) -> None:
    st.markdown("<div class='j3-section-title'>대장주 1~3위 · 일봉/주봉 비교</div>", unsafe_allow_html=True)
    medal_by_rank = {1: "🥇", 2: "🥈", 3: "🥉"}
    for leader in leaders[:3]:
        metrics, plan = leader["metrics"], leader["plan"]
        rank = int(leader["rank"])
        # 메달은 종합점수 80점 이상인 대장주에만 붙인다.
        medal = medal_by_rank.get(rank, "") if float(leader["score"]) >= 80 else ""
        medal_html = f"<span class='j3-medal'>{medal}</span> " if medal else ""
        with st.container(border=True):
            left, daily_col, weekly_col = st.columns([1.05, 1.25, 1.25])
            with left:
                st.markdown(
                    f"<div class='j3-leader-name'>{medal_html}{rank}위 · {leader['name']}</div>",
                    unsafe_allow_html=True,
                )
                st.code(leader["ticker"])
                st.markdown(
                    "<div class='j3-leader-score-label'>종목 조건점수</div>"
                    f"<div class='j3-leader-score'>{float(leader['score']):.1f}</div>"
                    f"<div class='j3-leader-state'>{plan.get('state')}</div>",
                    unsafe_allow_html=True,
                )
                st.caption(f"52주 고가 대비 {_pct(metrics.get('from_high_pct'))}")
            with daily_col:
                st.caption("일봉 · 최근 60거래일")
                daily_payload = leader.get("daily_chart")
                if isinstance(daily_payload, dict) and daily_payload.get("ok"):
                    st.altair_chart(
                        _price_chart(daily_payload, "일봉", include_volume=False, height=210),
                        width="stretch",
                        theme="streamlit",
                    )
                else:
                    st.info("일봉 자료 없음")
            with weekly_col:
                st.caption("주봉 · 최근 52주")
                weekly_payload = leader.get("weekly_chart")
                if isinstance(weekly_payload, dict) and weekly_payload.get("ok"):
                    st.altair_chart(
                        _price_chart(weekly_payload, "주봉", include_volume=False, height=210),
                        width="stretch",
                        theme="streamlit",
                    )
                else:
                    st.info("주봉 자료 없음")


def _render_stock_detail(theme_row: dict, leader: dict, market: dict) -> None:
    ticker = leader["ticker"]
    st.session_state["j3_selected_ticker"] = ticker
    metrics, plan = leader["metrics"], leader["plan"]

    st.divider()
    # 대장주 비교와 동일하게, 80점 이상 1~3위 종목이면 종목명에도 메달을 붙인다.
    detail_rank = int(leader.get("rank") or 0)
    detail_medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(detail_rank, "") if float(leader.get("score") or 0) >= 80 else ""
    detail_medal_html = f"<span class='j3-medal'>{detail_medal}</span> " if detail_medal else ""
    st.markdown(
        f"<div class='j3-stock-name'>{detail_medal_html}{leader['name']} · {ticker}</div>"
        f"<div class='j3-stock-sub'>{theme_row['name']} 대장주 {leader['rank']}위 · {plan.get('recommendation')}</div>",
        unsafe_allow_html=True,
    )

    # 종목조건점수는 위로 빼지 않고 아래 한 줄 지표에 함께 표시한다.
    _render_selected_live_quote(leader.get("score"), plan.get("state"))

    factor_names = ["테마 대비 상대강도", "52주 신고가 위치", "추세", "유동성", "변동성 안정"]
    factor_max = [25, 25, 20, 15, 15]
    factor_rows = "".join(
        f"<tr><td class='j3-fac-name'>{name}</td>"
        f"<td class='j3-fac-val'>{_number(part)}</td>"
        f"<td class='j3-fac-val'>{maximum}</td></tr>"
        for name, part, maximum in zip(factor_names, leader["score_parts"], factor_max)
    )
    score_col, plan_col = st.columns([1, 1])
    with score_col:
        st.markdown("<div class='j3-section-title'>종목 선정 근거</div>", unsafe_allow_html=True)
        st.markdown(
            "<table class='j3-factor-table'><thead><tr>"
            "<th>심사 항목</th><th>획득</th><th>최대</th></tr></thead>"
            f"<tbody>{factor_rows}</tbody></table>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='j3-reason-mustard'>{leader['stock_reason']}</div>",
            unsafe_allow_html=True,
        )
    with plan_col:
        st.markdown("<div class='j3-section-title'>매수 심사 결과</div>", unsafe_allow_html=True)
        p1, p2 = st.columns(2)
        p1.metric("조건 기준가", _price(plan.get("trigger")))
        p2.metric("매수 허용 상단", _price(plan.get("zone_high")))
        p3, p4 = st.columns(2)
        p3.metric("무효화 가격", _price(plan.get("invalidation")))
        p4.metric("2R 목표 참고", _price(plan.get("target")))
        if plan.get("recommendation") == "조건부 후보":
            st.success(plan.get("buy_reason"))
        elif plan.get("state") == "추격 금지":
            st.error(plan.get("buy_reason"))
        else:
            st.warning(plan.get("buy_reason"))

    # 위 '테마 내 종합' 박스와 한 줄 더 띄운 뒤 차트 섹션을 시작한다.
    st.markdown(
        "<div class='j3-chart-heading'>가격 차트 · 일봉/주봉/월봉 한눈에 보기</div>",
        unsafe_allow_html=True,
    )
    st.caption("주가 흐름은 하늘색 · 20일선은 붉은색 · 50일선은 보라색입니다. 일봉 거래량은 일봉 바로 아래에 표시됩니다.")
    chart_bundle = j3data.get_chart_bundle(ticker)
    if chart_bundle.get("ok"):
        daily_col, weekly_col, monthly_col = st.columns(3)
        chart_columns = {"일봉": daily_col, "주봉": weekly_col, "월봉": monthly_col}
        for timeframe, chart_column in chart_columns.items():
            payload = chart_bundle["charts"].get(timeframe, {})
            with chart_column:
                # 제목을 차트 밖에서 통일된 높이로 그려 일봉·주봉·월봉을 한 줄에 정렬한다.
                st.markdown(f"<div class='j3-chart-title'>{timeframe}</div>", unsafe_allow_html=True)
                if payload.get("ok"):
                    st.altair_chart(
                        _price_chart(payload, timeframe, include_volume=timeframe == "일봉"),
                        width="stretch",
                        theme="streamlit",
                    )
                else:
                    st.warning(f"{timeframe} 자료 없음")
        if chart_bundle.get("stale"):
            st.warning("온라인 재조회가 실패해 마지막 정상 차트 자료를 표시하고 있습니다.")
    else:
        st.warning(f"차트 조회 실패: {_safe_error_text(chart_bundle.get('error'))}")

    st.markdown("<div class='j3-section-title'>추천 근거 요약</div>", unsafe_allow_html=True)
    reason_cards = [
        ("시장 근거", f"{market.get('regime', '자료부족')} · {market.get('score', 0)}/100"),
        ("테마 근거", theme_row.get("basis", "자료부족")),
        ("종목 근거", leader["stock_reason"]),
        ("매수 근거", plan.get("buy_reason", "자료부족")),
    ]
    for column, (title, body) in zip(st.columns(4), reason_cards):
        column.markdown(
            f"<div class='j3-reason-card'><div class='j3-reason-title'>{title}</div>"
            f"<div class='j3-reason-body'>{body}</div></div>",
            unsafe_allow_html=True,
        )

    _render_buy_form(theme_row, leader, market)


def _render_buy_form(theme_row: dict, leader: dict, market: dict) -> None:
    ticker = leader["ticker"]
    metrics, plan = leader["metrics"], leader["plan"]
    st.markdown("#### 실제 매수 기록")
    st.caption("실제로 매수한 경우에만 저장합니다. 저장 시 당시 시장·테마·종목 조건도 함께 보존됩니다.")
    with st.form(f"j3_buy_form_{ticker}", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns(4)
        buy_date = c1.date_input("매수일", value=date.today(), key=f"j3_buy_date_{ticker}")
        default_price = float(metrics.get("current") or 0.01)
        buy_price = c2.number_input(
            "실제 매수가(USD)", min_value=0.01, value=round(default_price, 2), step=0.01,
            key=f"j3_buy_price_{ticker}",
        )
        quantity = c3.number_input(
            "수량(선택)", min_value=0.0, value=0.0, step=1.0, key=f"j3_buy_qty_{ticker}",
        )
        trade_style = c4.selectbox(
            "매매유형", ["스윙", "단타", "중장기"], key=f"j3_trade_style_{ticker}",
        )
        memo = st.text_area("매수 이유·메모", key=f"j3_buy_memo_{ticker}", height=80)
        confirmed = st.checkbox(
            "실제 체결된 매수임을 확인합니다",
            key=f"j3_buy_confirm_{ticker}",
        )
        submitted = st.form_submit_button("매수 기록 저장", width="stretch")

    if submitted:
        if not confirmed:
            st.error("실제 체결 확인을 체크해야 저장할 수 있습니다.")
            return
        snapshot = {
            "captured_at": theme_row.get("source_time") or market.get("checked_at"),
            "market": {"regime": market.get("regime"), "score": market.get("score")},
            "theme": {
                "name": theme_row.get("name"), "etf": theme_row.get("etf"),
                "score": theme_row.get("score"), "rank": theme_row.get("rank"),
                "rs20": theme_row.get("rs20"), "breadth": theme_row.get("breadth"),
            },
            "stock": {
                "ticker": ticker, "rank": leader.get("rank"), "score": leader.get("score"),
                "current": metrics.get("current"), "from_high_pct": metrics.get("from_high_pct"),
                "ret20": metrics.get("ret20"), "atr_pct": metrics.get("atr_pct"),
            },
        }
        try:
            j3store.save_trade(
                ticker=ticker,
                stock_name=leader["name"],
                theme_name=theme_row["name"],
                buy_date=buy_date,
                buy_price=buy_price,
                quantity=quantity or None,
                trade_style=trade_style,
                entry_setup=plan.get("state"),
                recommendation_state=plan.get("recommendation"),
                market_regime=market.get("regime"),
                market_score=market.get("score"),
                theme_score=theme_row.get("score"),
                stock_score=leader.get("score"),
                entry_plan=plan,
                snapshot=snapshot,
                memo=memo,
            )
            st.success(f"{leader['name']} · {buy_date.isoformat()} · ${buy_price:,.2f} 매수 기록을 저장했습니다.")
        except Exception as exc:
            st.error(f"매수 기록 저장 실패: {_safe_error_text(exc)}")


def _render_radar_tab(market: dict) -> None:
    action_col, note_col = st.columns([1, 4])
    with action_col:
        if st.button("온라인 자료 새로고침", key="j3_force_refresh", width="stretch"):
            j3data.clear_runtime_cache()
            st.rerun()
    with note_col:
        st.caption("테마 순위는 5분 캐시, 선택 종목 최근가는 1분 자동 갱신됩니다.")

    ranking = _load_theme_rankings()
    if not ranking.get("ok"):
        st.error(f"테마 자료 조회 실패: {_safe_error_text(ranking.get('error'))}")
        return
    st.session_state["j3_theme_rankings"] = ranking
    if ranking.get("stale"):
        st.warning("온라인 재조회 실패로 마지막 정상 테마 자료를 표시하고 있습니다.")

    st.markdown("### 20개 테마 실시간 순위")
    st.caption("순위 일람입니다. 아래 ‘테마 선택’에서 테마를 누르면 대장주와 상세가 즉시 연결됩니다.")
    names = [row["name"] for row in ranking["rows"] if row.get("ok")]
    st.markdown(
        _theme_table_html(ranking, st.session_state.get("j3_theme_choice")),
        unsafe_allow_html=True,
    )
    st.caption(
        f"테마 계산 시각: {ranking.get('checked_at') or '—'} · ETF 상대강도와 구성종목 추세를 합산 · "
        "미국 휴장일에는 마지막 거래일 자료"
    )
    if st.session_state.get("j3_theme_choice_widget") not in names:
        preferred_theme = st.session_state.get("j3_theme_choice")
        st.session_state["j3_theme_choice_widget"] = preferred_theme if preferred_theme in names else names[0]
    selected_theme = st.pills(
        "테마 선택",
        names,
        selection_mode="single",
        key="j3_theme_choice_widget",
    ) or names[0]
    st.session_state["j3_theme_choice"] = selected_theme
    theme_row = next(row for row in ranking["rows"] if row["name"] == selected_theme)
    rs_level, rs_meaning = _relative_strength_guide(theme_row.get("rs20"))
    if theme_row.get("rs60") is not None and theme_row.get("breadth") is not None:
        basis_html = (
            f"<span class='j3-green-strong'>20일 상대강도</span> {theme_row['rs20']:+.1f}%p · "
            f"60일 {theme_row['rs60']:+.1f}%p · 20일선 위 {theme_row['breadth']:.0f}%"
        )
    else:
        basis_html = theme_row.get("basis", "근거 자료 부족")
    st.markdown(
        "<div class='j3-theme-box'>"
        f"<span class='j3-green-strong'>{selected_theme} · {theme_row['status']}</span> : "
        f"<span class='j3-green'>{theme_row['score']:.1f}/100</span><br>"
        f"{basis_html}<br>"
        f"<span class='j3-green-strong'>20일 상대강도 해석</span> : {rs_level} — {rs_meaning}<br>"
        "<span class='j3-green-strong'>기준</span> : +10%p 이상 매우 강함 · +5–10%p 강함 · "
        "0–5%p 시장 대비 우위 · 음수는 시장 대비 약세"
        "</div>",
        unsafe_allow_html=True,
    )

    with st.spinner(f"{selected_theme} 대장주를 조회하는 중입니다…"):
        leader_result = j3data.get_theme_leaders(
            selected_theme,
            market_score=float(market.get("score") or 0),
            theme_score=float(theme_row.get("score") or 0),
        )
    if not leader_result.get("ok"):
        st.error(f"대장주 조회 실패: {_safe_error_text(leader_result.get('error'))}")
        return
    if leader_result.get("stale"):
        st.warning("일부 종목은 마지막 정상 시세로 계산했습니다.")
    leaders = leader_result["rows"]
    leader_view = _leader_table(leaders)
    st.markdown(
        f"<div class='j3-section-title'><span class='j3-theme-badge'>{selected_theme}</span> 테마 종목 1–6위</div>",
        unsafe_allow_html=True,
    )
    st.caption("1–3위는 색으로 구분했습니다. 1–3위의 어느 셀을 클릭해도 아래 ‘상세 종목 선택’과 상세 분석이 연결됩니다.")
    leader_event = st.dataframe(
        leader_view,
        hide_index=True,
        width="stretch",
        key=f"j3_leader_rank_table_{selected_theme}",
        on_select="rerun",
        selection_mode="single-cell",
        column_config={
            "조건점수": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
            "52주 고가 대비": st.column_config.NumberColumn(format="%+.1f%%"),
            "20일 수익률": st.column_config.NumberColumn(format="%+.1f%%"),
        },
    )

    top_candidates = leaders[:3]
    ticker_options = [leader["ticker"] for leader in top_candidates]
    clicked_leader_rows = _selected_rows(leader_event)
    if clicked_leader_rows and 0 <= clicked_leader_rows[0] < len(leader_view):
        clicked_index = clicked_leader_rows[0]
        clicked_ticker = str(leader_view.iloc[clicked_index]["티커"])
        selection_token = (selected_theme, clicked_index, clicked_ticker)
        if clicked_index < 3 and selection_token != st.session_state.get("j3_last_leader_table_selection"):
            st.session_state[f"j3_stock_choice_{selected_theme}"] = clicked_ticker
            st.session_state["j3_last_leader_table_selection"] = selection_token
        elif clicked_index >= 3:
            st.info("4~6위는 예비 관찰 종목입니다. 현재 상세 매수 심사는 검증 강도가 높은 1~3위만 연결합니다.")

    _render_leader_comparison(leaders)

    selected_ticker = st.radio(
        "상세 종목 선택",
        ticker_options,
        format_func=lambda ticker: next(
            f"{item['rank']}위 · {item['name']} ({ticker}) · {item['score']:.1f}점 · {item['plan']['state']}"
            for item in top_candidates if item["ticker"] == ticker
        ),
        horizontal=True,
        key=f"j3_stock_choice_{selected_theme}",
    )
    selected_leader = next(item for item in top_candidates if item["ticker"] == selected_ticker)
    _render_stock_detail(theme_row, selected_leader, market)


def _render_records_tab() -> None:
    st.subheader("실제 매수 데이터")
    try:
        progress = j3store.trade_progress()
        records = j3store.list_trades(limit=300)
    except Exception as exc:
        st.error(f"기록 DB 조회 실패: {_safe_error_text(exc)}")
        return
    st.progress(
        min(progress["closed_count"] / progress["minimum_sample"], 1.0),
        text=f"청산 표본 {progress['closed_count']}/30건 · 전체 매수 {progress['total_count']}건 · 보유 {progress['open_count']}건",
    )
    if progress["closed_count"] < 30:
        st.info("청산 30건 전에는 승률·기대값을 확정하지 않고 원자료만 축적합니다.")
    if not records:
        st.caption("아직 저장된 자비스3 매수 기록이 없습니다.")
        return

    view = pd.DataFrame(records)
    columns = [
        "id", "buy_date", "ticker", "stock_name", "theme_name", "trade_style",
        "buy_price", "quantity", "status", "sell_date", "sell_price", "result_pct",
        "market_regime", "market_score", "theme_score", "stock_score", "memo",
    ]
    st.dataframe(view[[col for col in columns if col in view.columns]], hide_index=True, width="stretch")

    open_records = [record for record in records if record.get("status") == "보유"]
    if open_records:
        with st.expander("보유 기록 청산 입력", expanded=False):
            by_id = {int(record["id"]): record for record in open_records}
            trade_id = st.selectbox(
                "청산할 기록",
                list(by_id),
                format_func=lambda value: f"#{value} · {by_id[value]['ticker']} · {by_id[value]['buy_date']} · ${by_id[value]['buy_price']:,.2f}",
                key="j3_close_trade_id",
            )
            c1, c2 = st.columns(2)
            sell_date = c1.date_input("실제 매도일", value=date.today(), key="j3_sell_date")
            sell_price = c2.number_input("실제 매도가(USD)", min_value=0.01, value=0.01, step=0.01, key="j3_sell_price")
            if st.button("청산 기록 저장", key="j3_close_submit", width="stretch"):
                try:
                    j3store.close_trade(trade_id, sell_date=sell_date, sell_price=sell_price)
                    st.success("청산 기록을 저장했습니다.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"청산 저장 실패: {_safe_error_text(exc)}")


def _render_method_tab() -> None:
    st.subheader("판정 기준과 데이터 정책")
    st.markdown(
        """
        1. **시장 게이트** — SPY·QQQ의 20/50일선, IWM 동행, VIX로 신규 매수 가능 국면을 먼저 판단합니다.
        2. **테마 강도** — ETF의 SPY 대비 20·60일 상대강도, 추세, 구성종목 확산도를 합산합니다.
        3. **대장주 품질** — 테마 대비 상대강도, 52주 신고가 위치, 추세, 유동성, 변동성을 평가합니다.
        4. **매수 타이밍** — 신고가 거래량 돌파 또는 상승추세 내 20일선 눌림만 조건부 후보로 봅니다.
        5. **위험 우선** — 5일 급등과 고변동 종목은 점수가 높아도 추격 금지합니다.
        """
    )
    st.warning(
        "조건점수는 상승확률이 아닙니다. 실제 매수·청산 표본이 30건 이상 쌓인 뒤 "
        "셋업별 기대값과 최대손실을 검증해 가중치를 조정합니다."
    )
    st.caption(
        "온라인 시세는 yfinance의 최근 가용 1분봉·일봉을 사용합니다. 개인 연구용이며 "
        "거래소 정식 유료 실시간 피드가 아니므로 지연·누락 가능성을 화면에 표시합니다."
    )


def main() -> None:
    st.title("자비스3 — 미국 테마 레이더")
    try:
        j3store.ensure_tables()
    except Exception as exc:
        st.error(f"자비스3 기록 테이블 준비 실패: {_safe_error_text(exc)}")

    _render_market_overview()
    market = st.session_state.get("j3_market_overview") or {"ok": False, "score": 0, "regime": "자료부족"}
    st.divider()
    radar_tab, records_tab, method_tab = st.tabs(["테마·종목", "매수 기록", "판정 기준"])
    with radar_tab:
        _render_radar_tab(market)
    with records_tab:
        _render_records_tab()
    with method_tab:
        _render_method_tab()


main()

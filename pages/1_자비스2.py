"""자비스2 — 순환매 플레이북 & 급락일 기록 페이지.

기존 파일(app.py, database.py, theme_history.py 등)은 수정하지 않는다.
P1 모듈(market_data, theme_detail, playbook)만 import해서 사용한다.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="자비스2 — 순환매 플레이북", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stSidebarNav"] a {
        padding: 0.7rem 1rem !important;
    }
    [data-testid="stSidebarNav"] a,
    [data-testid="stSidebarNav"] a * {
        font-size: 1.8rem !important;
        font-weight: 800 !important;
        color: #ffb020 !important;
        line-height: 1.4 !important;
    }
    [data-testid="stSidebarNav"] a:hover,
    [data-testid="stSidebarNav"] a:hover * {
        color: #ffcf6b !important;
    }
    [data-testid="stSidebarNav"] li:first-child a p {
        font-size: 0 !important;
    }
    [data-testid="stSidebarNav"] li:first-child a p::before {
        content: "자비스1";
        font-size: 1.8rem;
        font-weight: 800;
        color: #ffb020;
    }
    [data-testid="stSidebarNav"] li:first-child a:hover p::before {
        color: #ffcf6b;
    }
    /* 제목·지표 글자 한 치수 축소 (2026-07-17 사용자 요청) */
    h1 { font-size: 2.05rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.7rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.85rem !important; }
    /* 테마 선택·종목 선택 셀렉트박스 강조 (2026-07-18 사용자 요청) —
       j2_stock_select_ 는 테마별 동적 key라 부분일치(attr *=)로 잡는다 */
    div[class*="st-key-j2_theme_select"] label p,
    div[class*="st-key-j2_stock_select_"] label p {
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        color: #facc15 !important;
    }
    div[class*="st-key-j2_theme_select"] [data-baseweb="select"] > div,
    div[class*="st-key-j2_stock_select_"] [data-baseweb="select"] > div {
        background-color: rgba(250, 204, 21, 0.16) !important;
        font-weight: 700 !important;
        border-color: #facc15 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

_log = logging.getLogger(__name__)

# ── 인증 게이트 — 이 페이지에서 바로 로그인 가능 (자비스1 경유 불필요) ─────────
if not st.session_state.get("authenticated"):
    st.markdown("## 자비스2 — 순환매 플레이북")
    st.caption("승인된 사용자만 접근할 수 있습니다. 여기서 바로 로그인하세요.")
    try:
        _app_password = st.secrets.get("APP_PASSWORD")
    except Exception:
        _app_password = None
    if not _app_password:
        st.warning("비밀번호 설정이 필요합니다. .streamlit/secrets.toml에 APP_PASSWORD를 설정하세요.")
        st.stop()
    _j2_pw = st.text_input("비밀번호", type="password", key="j2_login_password")
    if st.button("로그인", key="j2_login_submit", use_container_width=True):
        if _j2_pw == _app_password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()

# ── 공통 임포트 (인증 후) ──────────────────────────────────────────────────────
import importlib

import market_data
import playbook
import theme_detail
import theme_history
from theme_data import KR_THEME_NAVER_MAPPING, fetch_kr_theme_snapshot

# 배포 서버가 파일만 동기화하고 프로세스를 재시작하지 않으면, 이미 임포트된
# 모듈이 옛 버전으로 남아 페이지(새 코드)와 어긋난다 — get_market
# AttributeError 실사례. 최신 심볼이 없으면 해당 모듈을 자동 리로드한다.
if not hasattr(market_data, "get_market"):
    market_data = importlib.reload(market_data)
if not hasattr(playbook, "scan_near_high"):
    playbook = importlib.reload(playbook)
if not hasattr(theme_detail, "_FETCH_CACHE"):
    theme_detail = importlib.reload(theme_detail)

_THEME_NAMES = list(KR_THEME_NAVER_MAPPING.keys())

# ── 헬퍼 ──────────────────────────────────────────────────────────────────────


def _cfg() -> dict:
    return playbook._get_config()


def _age_badge(age: int | None, entry_max_age: float) -> str:
    if age is None:
        return "이력 축적 중"
    return f"D+{age}"


def _age_is_warn(age: int | None, entry_max_age: float) -> bool:
    return age is not None and age > entry_max_age


def _sign_html(v, digits: int = 2) -> str:
    """등락 수치를 한국 시장 색 관례(+빨강/−파랑)로 표기하는 HTML."""
    if v is None:
        return "<span style='color:#9ca3af'>데이터 없음</span>"
    color = "#ff4b4b" if v > 0 else "#4b9fff" if v < 0 else "#9ca3af"
    return f"<span style='color:{color};font-weight:800'>{v:+.{digits}f}%</span>"


def _enrich_candidates(cands: list) -> None:
    """1·2등주 후보에 장중 시가대비/고점대비와 셋업 판정을 채운다 (수집 시점 기준).

    셋업 판정(참고용 — 매수 신호 아님, 연구 기반 휴리스틱):
      막차 주의  = 최근 20거래일 내 +20% 급등 이력 (추격 금지 원칙)
      돌파 임박  = 52주 신고가 근접 + 거래대금 배수 기준(value_mult) 충족
      눌림 관찰  = 신고가 근접이지만 거래대금 미충족 — 눌림재상승 후보
      부적격     = 신고가 근접 게이트 미충족
    """
    cfg = _cfg()
    val_mult = cfg.get("value_mult", 3.0)

    def _one(c):
        info = market_data.get_intraday_summary(c["code"])
        if info:
            last, o, h = info["last"], info["open"], info["high"]
            if last:
                c["price"] = c.get("price") or round(last)
            c["open_pct"] = round((last / o - 1) * 100, 2) if o else None
            c["high_pct"] = round((last / h - 1) * 100, 2) if h else None
        try:
            w = playbook.max_warning(c["code"])
            spike = bool(w.get("ok") and w.get("warning"))
        except Exception:
            spike = False
        mult = c.get("turnover_mult")
        if spike:
            c["setup_judge"] = "막차 주의"
        elif c.get("near_high") and mult is not None and mult >= val_mult:
            c["setup_judge"] = "돌파 임박"
        elif c.get("near_high"):
            c["setup_judge"] = "눌림 관찰"
        else:
            c["setup_judge"] = "부적격"

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(_one, cands))


def _tag_str(theme: str, setup: str, age: int | None, alert_state: str | None) -> str:
    parts = ["#순환매", f"#{setup}"]
    if age is not None:
        parts.append(f"#테마D{age}")
    if alert_state:
        for a in alert_state.split(","):
            parts.append(f"#경보무시-{a.strip()}")
    return " ".join(parts)


_EXIT_SCENARIOS = {
    "눌림재상승": "+1R 절반 익절 · 대장 꺾임 시 전량",
    "돌파": "+1R 절반 익절 · 돌파 실패(되돌림) 시 전량",
}


def _exit_scenario(setup: str | None) -> str:
    return _EXIT_SCENARIOS.get(setup or "", "청산 규칙 미지정")


def _weekly_ohlc(df):
    """일봉 → 주봉 OHLC 합성."""
    return (
        df.resample("W")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
        .dropna()
        .tail(52)
    )


def _render_html_table(styled_df, max_height: int = 620) -> None:
    """pandas Styler를 실제 HTML/CSS로 렌더링한다.

    st.dataframe(캔버스 기반 glide-data-grid)은 df.style의 text-align 등
    임의 CSS를 조용히 무시한다(색상 .map()만 별도 경로로 반영됨) —
    헤더 가운데 정렬·값 정렬 요청이 계속 실패했던 근본 원인. 진짜 HTML로
    그리면 CSS가 그대로 먹는다. 대가: st.dataframe의 on_select(행 클릭)
    상호작용이 없어짐 — 호출부에서 별도 선택+버튼으로 대체할 것."""
    html = styled_df.to_html()
    st.markdown(
        "<style>"
        ".j2htbl-wrap { max-height:" + str(max_height) + "px; overflow:auto; "
        "border:1px solid #263247; border-radius:8px; margin-bottom:0.5rem; }"
        ".j2htbl-wrap table { width:100%; border-collapse:collapse; font-size:0.92rem; }"
        ".j2htbl-wrap thead th { position:sticky; top:0; background:#161d2b; "
        "color:#e5e7eb; font-weight:700; padding:0.5rem 0.6rem; "
        "border-bottom:2px solid #2d3b52; z-index:1; }"
        ".j2htbl-wrap tbody td { padding:0.42rem 0.6rem; border-bottom:1px solid #1f2937; "
        "color:#e5e7eb; white-space:nowrap; }"
        ".j2htbl-wrap tbody tr:hover { background:#1a2332; }"
        "</style>"
        f"<div class='j2htbl-wrap'>{html}</div>",
        unsafe_allow_html=True,
    )


def _candle_chart(dfo, height: int, bar_size: int = 6):
    """캔들 봉차트 (한국 관례: 상승 빨강 / 하락 파랑). altair 내장 사용."""
    import altair as alt

    d = dfo.reset_index()
    d = d.rename(columns={d.columns[0]: "Date"})
    color = alt.condition(
        "datum.Close >= datum.Open", alt.value("#ff4b4b"), alt.value("#4b9fff")
    )
    base = alt.Chart(d).encode(
        x=alt.X("Date:T", axis=alt.Axis(format="%m-%d", title=None, labelAngle=0))
    )
    wick = base.mark_rule().encode(
        y=alt.Y("Low:Q", scale=alt.Scale(zero=False), title=None),
        y2="High:Q",
        color=color,
    )
    body = base.mark_bar(size=bar_size).encode(y="Open:Q", y2="Close:Q", color=color)
    return (wick + body).properties(height=height)


# ── 섹션 1: 시장상태 스트립 ───────────────────────────────────────────────────


def _render_market_state() -> None:
    cfg = _cfg()
    warn_days = int(cfg.get("volatile_days_warn", 12))

    ms = st.session_state.get("j2_market_state")
    if ms is None:
        with st.spinner("시장 상태 조회 중…"):
            ms = playbook.market_state()
            # 성공 결과만 캐시 — 실패를 캐시하면 재시도 경로가 없어
            # 세션 내내 실패 화면에 갇힌다
            if ms and ms.get("ok"):
                st.session_state["j2_market_state"] = ms

    if not ms or not ms.get("ok"):
        st.info(f"시장 상태 조회 실패: {ms.get('error', '알 수 없음')}")
        return

    phase = ms["phase"]
    ret60 = ms.get("return_60d_pct", 0.0)
    vdays = ms.get("volatile_days", 0)

    is_warn = (phase == "하락국면") or (vdays is not None and vdays >= warn_days)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("시장 국면 (60일)", phase)
    c2.metric("코스피 60일 수익률", f"{ret60:+.1f}%")
    c3.metric(f"±3% 변동일 (기준 {warn_days}일)", f"{vdays}일" if vdays is not None else "—")
    c4.metric("경고", "⚠ 진입 축소" if is_warn else "정상")

    if is_warn:
        reasons = []
        if phase == "하락국면":
            reasons.append(
                f"- 코스피 60거래일 수익률이 {ret60:+.1f}%로 **하락국면**입니다. "
                "하락국면에서는 신고가 돌파가 되돌림으로 끝나는 비율이 높아집니다."
            )
        if vdays and vdays >= warn_days:
            reasons.append(
                f"- 최근 60거래일 중 지수가 하루 **±3% 이상** 움직인 날이 **{vdays}일** — "
                f"경고 기준({warn_days}일)의 {vdays / warn_days:.1f}배입니다. "
                "변동성이 큰 장에서는 손절선이 하루 만에 훼손되기 쉽습니다."
            )
        st.warning(
            "**모멘텀 진입 축소 권고**\n\n"
            + "\n".join(reasons)
            + "\n\n**행동 지침**: 신규 진입 포지션 크기 절반 이하 · "
            "돌파 추격보다 눌림 재상승 셋업 우선 · 손절가 이탈 시 미련 없이 청산."
        )

    if st.button("시장 상태 새로고침", key="j2_ms_refresh"):
        st.session_state.pop("j2_market_state", None)
        st.rerun()


# ── 섹션 2: 순환매 플레이북 ──────────────────────────────────────────────────


def _clear_theme_cache() -> None:
    for k in ["j2_signals", "j2_leader", "j2_stocks", "j2_stock_select"]:
        st.session_state.pop(k, None)


def _render_playbook(open_pos: list) -> None:
    cfg = _cfg()
    st.subheader("순환매 플레이북", anchor="playbook")
    st.caption("매수신호·점수·목표가는 표시하지 않습니다. 기록과 확인 도구입니다.")

    # 대장주 모음 표에서 행 클릭으로 넘어온 테마 적용 (표는 이 섹션보다 뒤에
    # 그려지므로 보류 키를 통해 다음 run에서 위젯 생성 전에 반영)
    pending = st.session_state.pop("j2_pending_theme", None)
    if pending and pending in _THEME_NAMES:
        st.session_state["j2_theme_select"] = pending
        st.session_state["j2_autorun_signal"] = True

    # ── 2a. 테마 선택 + 신호 확인 ──────────────────────────────────────────────
    # 첫 로딩: 클릭 없이 가장 강한(등락률 1위) 테마를 자동 선택하고 신호까지 자동 조회
    if not st.session_state.get("j2_boot_done"):
        snap0 = st.session_state.get("j2_theme_snap")
        if snap0 is not None:
            st.session_state["j2_boot_done"] = True
            if snap0.get("ok"):
                valid = [
                    (n, i["change_pct"])
                    for n, i in snap0.get("themes", {}).items()
                    if i.get("ok") and i.get("change_pct") is not None and n in _THEME_NAMES
                ]
                if valid:
                    ranked_themes = [n for n, _ in sorted(valid, key=lambda x: x[1], reverse=True)]

                    # ⭐ 신고가 임박주 자동 스캔 — 1위 종목의 테마를 기본 선택
                    # (당일 파일 캐시가 있으면 즉시, 없으면 자동 스캔)
                    nh = _ensure_nh_scan()
                    nh_rows = ((nh or {}).get("result") or {}).get("rows") or []
                    if nh_rows and nh_rows[0].get("theme") in _THEME_NAMES:
                        st.session_state["j2_nh_top"] = nh_rows[0]
                        top_theme = nh_rows[0]["theme"]
                    else:
                        top_theme = ranked_themes[0]
                    st.session_state["j2_theme_select"] = top_theme
                    st.session_state["j2_autorun_signal"] = True

                    # 강한 테마 5개의 1·2등주 자동 수집 → 대장주 모음 표
                    # (첫 로딩만 네트워크 조회로 오래 걸림, 같은 날 재로딩은 캐시)
                    lt = st.session_state.setdefault("j2_leader_table", {})
                    top5 = ranked_themes[:5]
                    prog = st.progress(0.0, text="강한 테마 5개 대장주 자동 수집 중… (첫 로딩만 오래 걸립니다)")
                    for k, tn in enumerate(top5):
                        try:
                            lr = playbook.find_leader(tn)
                            if lr.get("ok") and lr.get("candidates"):
                                pair = lr["candidates"][:2]
                                _enrich_candidates(pair)
                                lt[tn] = [(i + 1, c) for i, c in enumerate(pair)]
                                q = [c for c in lr["candidates"] if c.get("near_high")]
                                if q:
                                    st.session_state.setdefault("j2_qualified", {})[tn] = {
                                        "stocks": q,
                                        "at": datetime.now().strftime("%m-%d %H:%M"),
                                    }
                        except Exception as e:
                            _log.warning("auto leader collect failed %s: %s", tn, e)
                        prog.progress((k + 1) / len(top5), text=f"{tn} 수집 완료 ({k + 1}/{len(top5)})")
                    prog.empty()

    # (테마판 버튼 클릭 시 j2_theme_select/j2_autorun_signal이 미리 설정되어 들어온다)
    prev_theme = st.session_state.get("j2_prev_theme", "")

    # 자비스1에 다녀오면 Streamlit이 이 페이지 위젯 상태를 지워 선택이 첫 테마로
    # 리셋되고, '테마 바뀜'으로 오인해 조회 결과까지 지워지는 버그 방지 —
    # 위젯 상태가 사라졌으면 마지막 선택(prev_theme)을 복원한다.
    if "j2_theme_select" not in st.session_state and prev_theme in _THEME_NAMES:
        st.session_state["j2_theme_select"] = prev_theme

    theme = st.selectbox("테마 선택", _THEME_NAMES, key="j2_theme_select")
    if theme != prev_theme:
        _clear_theme_cache()
        st.session_state["j2_prev_theme"] = theme
        # 테마를 고르기만 하면 자동 조회 — 별도 버튼 클릭 불필요
        st.session_state["j2_autorun_signal"] = True

    run_signal = st.button("신호 새로고침 (테마 선택 시 자동 조회됨)", key="j2_signal_btn")
    if st.session_state.pop("j2_autorun_signal", False):
        run_signal = True

    # 표 클릭으로 넘어온 경우: 조회가 끝난 표시 run에서 '매수 대상 선택' 위치로 스크롤
    if not run_signal and st.session_state.pop("j2_scroll_playbook", False):
        import streamlit.components.v1 as components
        components.html(
            "<script>window.parent.document.getElementById('buy-target')"
            "?.scrollIntoView({behavior:'smooth'});</script>",
            height=0,
        )

    if run_signal:
        with st.spinner("네이버 테마 조회 중…"):
            sigs = playbook.theme_signals(theme)
            stocks_result = theme_detail.fetch_theme_stocks(theme)
            leader_result = playbook.find_leader(theme)
            age = playbook.theme_age(theme)

            st.session_state["j2_signals"] = sigs
            st.session_state["j2_stocks"] = stocks_result
            st.session_state["j2_leader"] = leader_result
            st.session_state["j2_age"] = age

            # 적격 대장(52주 신고가 근접 통과) 발견 시 별도 난에 축적
            qualified = [
                c for c in (leader_result.get("candidates") or [])
                if c.get("near_high")
            ]
            if qualified:
                store = st.session_state.setdefault("j2_qualified", {})
                store[theme] = {
                    "stocks": qualified,
                    "at": datetime.now().strftime("%m-%d %H:%M"),
                }

            # 대장주 모음 표(맨 아래)용 — 1·2등주만 테마별 축적 (장중·판정 보강 포함)
            pair = (leader_result.get("candidates") or [])[:2]
            _enrich_candidates(pair)
            lt = st.session_state.setdefault("j2_leader_table", {})
            lt[theme] = [(i + 1, c) for i, c in enumerate(pair)]

            # theme_state_log 축적 (upsert 안전 확인됨: ON CONFLICT DO UPDATE)
            if sigs.get("ok") and stocks_result.get("ok"):
                stocks = stocks_result["stocks"]
                if stocks:
                    avg_pct = sum(
                        s["change_pct"] for s in stocks if s.get("change_pct") is not None
                    ) / max(1, sum(1 for s in stocks if s.get("change_pct") is not None))
                    if avg_pct >= 2.0:
                        verdict = "강함"
                    elif avg_pct <= -2.0:
                        verdict = "약함"
                    else:
                        verdict = "보통"
                    try:
                        theme_history.record_theme_states({theme: verdict})
                    except Exception as e:
                        _log.warning("record_theme_states failed: %s", e)
        st.rerun()

    sigs = st.session_state.get("j2_signals")
    age = st.session_state.get("j2_age")
    stocks_result = st.session_state.get("j2_stocks")
    leader_result = st.session_state.get("j2_leader")

    if sigs is None:
        st.info("테마를 선택하고 **신호 확인** 버튼을 누르세요.")
        return

    if not sigs.get("ok"):
        st.warning(f"신호 조회 실패: {sigs.get('error')}")
        return

    # ── 신호등 3개 + 테마나이 ────────────────────────────────────────────────
    entry_max_age = cfg.get("entry_max_age", 3)
    age_warn = _age_is_warn(age, entry_max_age)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        up_ok = sigs.get("three_plus_up", False)
        (st.success if up_ok else st.warning)(
            f"양전 3개+ {'✔' if up_ok else '✗'}  ({sigs.get('up_count', 0)}/{sigs.get('total_count', 0)}종목)"
        )
    with col2:
        mult = sigs.get("leader_value_mult")
        val_thresh = cfg.get("value_mult", 3.0)
        val_ok = mult is not None and mult >= val_thresh
        if mult is not None:
            (st.success if val_ok else st.warning)(
                f"거래대금 급증 {'✔' if val_ok else '✗'}  (등락 1위 종목이 20일 평균의 {mult:.1f}배 / 기준 {val_thresh:.0f}배)"
            )
        else:
            st.warning("거래대금 급증 ✗  (데이터 없음)")
    with col3:
        streak = sigs.get("strong_streak")
        streak_ok = streak is not None and streak >= 2
        (st.success if streak_ok else st.info)(
            f"연속강세 {'✔' if streak_ok else '—'}  ({streak}일)" if streak else "연속강세 이력 없음"
        )
    with col4:
        if age_warn:
            st.warning(f"테마나이 D+{age} ⚠ 추격 주의")
        elif age is not None:
            st.success(f"테마나이 D+{age}")
        else:
            st.info("테마나이: 이력 축적 중")

    # 양전 종목 — 대장 1·2·3등 우선, 등락률 순, 최대 10개만 표시
    _all_stocks = (stocks_result or {}).get("stocks", [])
    _ups = [s for s in _all_stocks if (s.get("change_pct") or 0) > 0]
    if _ups:
        _lead_codes = []
        if leader_result and leader_result.get("ok"):
            _lead_codes = [c["code"] for c in (leader_result.get("candidates") or [])]

        def _up_key(s):
            lead = _lead_codes.index(s["code"]) if s["code"] in _lead_codes else 99
            return (lead, -(s.get("change_pct") or 0))

        _shown = sorted(_ups, key=_up_key)[:10]
        _marks = "①②③"

        def _chip(s):
            prefix = ""
            if s["code"] in _lead_codes and _lead_codes.index(s["code"]) < 3:
                prefix = f"{_marks[_lead_codes.index(s['code'])]} "
            return (
                f"<span class='j2-upchip'>{prefix}{s['name']} "
                f"<b>+{s['change_pct']:.2f}%</b></span>"
            )

        with st.expander(
            f"양전 종목 상위 {len(_shown)}개 (전체 {len(_ups)}개 · 대장 1·2·3등 우선 → 등락률 순)",
            expanded=True,
        ):
            chips = "".join(_chip(s) for s in _shown)
            st.markdown(
                "<style>.j2-upchip{color:#fca5a5;background:rgba(255,75,75,0.10);"
                "padding:0.15rem 0.55rem;border-radius:8px;display:inline-block;"
                "margin:0.15rem 0.2rem;font-size:0.88rem}"
                ".j2-upchip b{color:#ff4b4b}</style>"
                f"<div>{chips}</div>",
                unsafe_allow_html=True,
            )

    st.divider()

    # ── 2b. 대장 확인 카드 — 1등(대장)·2등·3등 항상 표시 ─────────────────────
    st.markdown(
        "<span style='color:#34d399;font-weight:800;font-size:1.12rem'>대장 확인</span>"
        " <span style='color:#9ca3af'>· 매수 대상 아님 — 확인용</span>",
        unsafe_allow_html=True,
    )
    rank_limit_v = int(cfg.get("rank_limit", 2))
    st.caption(
        f"정렬 기준: ① 52주 신고가 근접 여부 → ② 거래대금 배수(20일 평균 대비). "
        f"등수 한계 {rank_limit_v} — {rank_limit_v}등주까지만 매수 허용."
    )
    if leader_result and leader_result.get("ok") and leader_result.get("candidates"):
        candidates = leader_result["candidates"][:3]
        if not any(c.get("near_high") for c in candidates):
            st.info("적격 대장 없음 — 52주 고가 근접 10% 게이트 미충족 (아래는 참고용 상위 후보)")
        rank_names = ["1등 · 대장주", "2등주", "3등주"]
        cols = st.columns(len(candidates))
        for i, c in enumerate(candidates):
            with cols[i]:
                pct_h = c.get("pct_from_52w_high")
                mult_c = c.get("turnover_mult")
                chg = c.get("change_pct")
                mult_txt = (
                    f"<span style='font-weight:700'>{mult_c:.2f}배</span>"
                    if mult_c is not None
                    else "<span style='color:#9ca3af'>데이터 없음</span>"
                )
                # 종목명·등수: 밝은 코발트색 / 라벨: 밝은 초록 / 수치: +빨강 −파랑
                st.markdown(
                    f"<div style='color:#4dc3ff;font-weight:800;font-size:1.06rem;margin-bottom:0.15rem'>"
                    f"{rank_names[i]} — {c['name']} "
                    f"<span style='font-size:0.85rem;color:#93c5fd'>{c['code']}</span></div>"
                    f"<div><span style='color:#34d399;font-weight:600'>52주고가대비</span>: {_sign_html(pct_h, 1)}</div>"
                    f"<div><span style='color:#34d399;font-weight:600'>거래대금배수</span>: {mult_txt}</div>"
                    f"<div><span style='color:#34d399;font-weight:600'>등락률</span>: {_sign_html(chg, 2)}</div>",
                    unsafe_allow_html=True,
                )
                if i + 1 > rank_limit_v:
                    st.error(f"{i + 1}등 — 매수 금지 (등수 한계 {rank_limit_v})")
                elif c.get("near_high"):
                    st.success("52주고가 근접 — 적격")
                elif pct_h is None:
                    st.info("일봉 데이터 없음 — 근접 판정 불가")
                else:
                    st.warning(f"고가 근접 미달 (52주고가 대비 {pct_h:+.1f}%)")

                # 일봉·주봉 캔들차트 자동 표시 (find_leader가 이미 받아둔 데이터라 즉시)
                df_c = market_data.get_daily(c["code"])
                if df_c is not None and not df_c.empty:
                    st.markdown(
                        "<div style='font-size:1.3rem;font-weight:800;color:#22c55e'>일봉 (최근 60일)</div>",
                        unsafe_allow_html=True,
                    )
                    st.altair_chart(_candle_chart(df_c.tail(60), 300, 4), use_container_width=True)
                    try:
                        st.markdown(
                            "<div style='font-size:1.3rem;font-weight:800;color:#22c55e'>주봉 (최근 52주)</div>",
                            unsafe_allow_html=True,
                        )
                        st.altair_chart(_candle_chart(_weekly_ohlc(df_c), 300, 5), use_container_width=True)
                    except Exception:
                        pass
    else:
        err = leader_result.get("error") if leader_result else "후보 없음"
        st.warning(f"대장 후보를 계산하지 못했습니다: {err}")

    # 실시간 시세 스트립 (1분 자동 갱신 — 이 조각만 다시 그려짐)
    _render_live_strip()

    st.divider()

    # ── 2c. 매수 대상 선택 ──────────────────────────────────────────────────
    st.markdown(
        "<div id='buy-target' style='display:inline-block;border:2px solid #facc15;border-radius:8px;"
        "padding:0.25rem 0.75rem;margin-bottom:0.3rem'>"
        "<span style='color:#3b82f6;font-weight:800;font-size:1.25rem'>매수 대상 선택</span>"
        " <span style='color:#9ca3af'>(반자동 — 최종 선택은 사용자)</span></div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "후보 출처 두 갈래 — ① **신고가 임박 매매(취지)**: 아래 '⭐ 52주 신고가 임박주' 표에서 "
        "행을 클릭하면 이 화면과 연결되고, 적격 대장이 기본 선택 1순위로 잡힙니다. "
        "② **순환매 관찰**: 이 드롭다운은 테마 구성종목 전체를 등락률 순으로 정렬한 목록입니다. "
        "등수 한계 밖(3등주)은 기본 선택에서 건너뛰고 직접 선택 시 경보. 매수 판단은 사용자."
    )
    stocks = (stocks_result or {}).get("stocks", [])
    if not stocks:
        st.info("구성종목 데이터가 없습니다.")
        return
    stocks = sorted(
        stocks,
        key=lambda s: s.get("change_pct") if s.get("change_pct") is not None else -999,
        reverse=True,
    )

    def _pct_label(v):
        return f"{v:+.2f}%" if v is not None else "N/A"

    # 대장 등수 맵 — 등수 한계 밖(예: 3등주)은 기본 선택에서 건너뛰고,
    # 사용자가 직접 고르면 아래 경보로 처리한다 (목록 자체는 숨기지 않음)
    _rank_map: dict = {}
    if leader_result and leader_result.get("ok"):
        for _ri, _rc in enumerate(leader_result.get("candidates") or []):
            _rank_map[_rc["code"]] = _ri + 1

    stock_opts = [f"{s['name']} ({s['code']}) {_pct_label(s.get('change_pct'))}" for s in stocks]

    # 기본 선택 우선순위: ①적격 대장(1등주) → ②적격 2등주 → ③돌파 임박 →
    # ④등락률 1위(등수 한계 밖만 건너뜀)
    _cands_all = (leader_result.get("candidates") or []) if leader_result and leader_result.get("ok") else []
    _code_to_idx = {s["code"]: i for i, s in enumerate(stocks)}

    def _pick_default() -> int:
        # ⓪ 신고가 임박주 1위 (현재 테마 소속일 때) — 스캐너와 직결
        _nh_top = st.session_state.get("j2_nh_top")
        if _nh_top and _nh_top.get("theme") == theme and _nh_top.get("code") in _code_to_idx:
            return _code_to_idx[_nh_top["code"]]
        for c in _cands_all[:rank_limit_v]:
            if c.get("near_high") and c["code"] in _code_to_idx:
                return _code_to_idx[c["code"]]
        for c in _cands_all[:rank_limit_v]:
            if c.get("setup_judge") == "돌파 임박" and c["code"] in _code_to_idx:
                return _code_to_idx[c["code"]]
        for _i, _s in enumerate(stocks):
            _r = _rank_map.get(_s["code"])
            if _r is None or _r <= rank_limit_v:
                return _i
        return 0

    _default_idx = _pick_default()
    sel_idx = st.selectbox(
        "종목 선택", range(len(stock_opts)),
        index=_default_idx,
        format_func=lambda i: stock_opts[i],
        # 테마별 별도 키 — 이전 테마의 선택 인덱스가 남아 차트/요약이
        # 다른 종목을 가리키는 불일치를 원천 차단
        key=f"j2_stock_select_{theme}",
    )
    sel_stock = stocks[sel_idx]
    sel_code = sel_stock["code"]

    # 선택된 종목명 강조 (밝은 초록) — Streamlit 셀렉트 표시값 오버레이
    # (2026-07-18 사용자 요청으로 한 치수 축소: 2.1rem -> 1.5rem)
    st.markdown(
        f"<div style='font-size:1.5rem;font-weight:900;color:#22c55e;margin:-0.6rem 0 0.3rem'>"
        f"{sel_stock['name']} ({sel_code})</div>",
        unsafe_allow_html=True,
    )

    # 선정 기준 명시 — 왜 이 종목이 기본 선택됐는지 (밝은 주황)
    _sr = _rank_map.get(sel_code)
    _why = (
        f"대장 {_sr}등주"
        if _sr is not None
        else "대장 후보 아님 — 등락률 1위부터 시작해 등수 한계 밖(3등주)만 건너뛴 기본값"
    )
    st.markdown(
        f"<div style='color:#ffa14a;font-weight:700'>기본 선택 우선순위: "
        f"⓪신고가 임박 1위(현재 테마일 때) → ①적격 대장(1등주) → ②적격 2등주 → "
        f"③돌파 임박 → ④등락률 1위. 현재 선택 {sel_stock['name']} = {_why}. "
        f"목록 자체는 테마 전체를 등락률 순 정렬 — 최종 선택은 사용자.</div>",
        unsafe_allow_html=True,
    )

    # 일봉·주봉 캔들차트 — 항상 표시, 4:3 비율에 가깝게 (컬럼 절반폭 기준)
    chart_df = market_data.get_daily(sel_code)
    if chart_df is None or chart_df.empty:
        st.info("차트 데이터를 불러오지 못했습니다.")
    else:
        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown(
                f"<div style='font-size:1.3rem;font-weight:800;color:#22c55e'>"
                f"{sel_stock['name']} 일봉 (최근 60거래일)</div>",
                unsafe_allow_html=True,
            )
            st.altair_chart(_candle_chart(chart_df.tail(60), 460, 7), use_container_width=True)
        with cc2:
            try:
                st.markdown(
                    f"<div style='font-size:1.3rem;font-weight:800;color:#22c55e'>"
                    f"{sel_stock['name']} 주봉 (최근 52주)</div>",
                    unsafe_allow_html=True,
                )
                st.altair_chart(_candle_chart(_weekly_ohlc(chart_df), 460, 8), use_container_width=True)
            except Exception as e:
                _log.warning("주봉 차트 실패 %s: %s", sel_code, e)
                st.caption("주봉 차트 데이터 없음")

    # 경보 계산
    w_result = playbook.max_warning(sel_code)
    lb_result = playbook.leader_break(sel_code)

    # 선택 종목 요약 정보 (판단 참고용) — 등락 수치는 +빨강/−파랑
    _price = sel_stock.get("price")
    _tv = sel_stock.get("turnover_mil")
    _dp = lb_result.get("drop_pct") if lb_result.get("ok") else None

    def _stat(label: str, value_html: str) -> str:
        return (
            f"<div style='color:#9ca3af;font-size:0.85rem'>{label}</div>"
            f"<div style='font-size:1.45rem;line-height:1.4'>{value_html}</div>"
        )

    # 현재가·오늘등락률 둘 다 등락 부호 기준 색상 (+빨강/−파랑)
    _chg_val = sel_stock.get("change_pct")
    _price_color = "#ff4b4b" if (_chg_val or 0) > 0 else "#4b9fff" if (_chg_val or 0) < 0 else "#e5e7eb"

    # 거래대금 배수 — 돌파 확인 관행 기준 1.5배 이상이면 초록
    _mult = market_data.today_turnover_multiple(chart_df) if chart_df is not None and not chart_df.empty else None
    _mult_color = "#22c55e" if (_mult or 0) >= 1.5 else "#e5e7eb"

    ic1, ic2, ic3, ic4, ic5 = st.columns(5)
    ic1.markdown(
        _stat("현재가", f"<b style='color:{_price_color}'>{_price:,}원</b>" if _price else "—"),
        unsafe_allow_html=True,
    )
    ic2.markdown(
        _stat("오늘 등락률", _sign_html(_chg_val)),
        unsafe_allow_html=True,
    )
    ic3.markdown(
        _stat("오늘 거래대금", f"<b>{_tv / 100:,.0f}억</b>" if _tv else "—"),
        unsafe_allow_html=True,
    )
    ic4.markdown(
        _stat("최근 20일 고점 대비", _sign_html(_dp, 1)),
        unsafe_allow_html=True,
    )
    ic5.markdown(
        _stat(
            "거래대금 배수 (돌파 확인 1.5배↑)",
            f"<b style='color:{_mult_color}'>{_mult:.2f}배</b>" if _mult is not None else "—",
        ),
        unsafe_allow_html=True,
    )

    alerts: list[str] = []
    if w_result.get("ok") and w_result.get("warning"):
        alerts.append(
            f"막차 경보 — 최근 20거래일 내 일간 {w_result.get('max_gain_pct', 0):+.1f}% 급등 이력"
            f" ({w_result.get('spike_days')}일)"
        )
    if lb_result.get("ok") and lb_result.get("broken"):
        alerts.append(f"대장 꺾임 경보 — 최근 고점 대비 {lb_result.get('drop_pct', 0):+.1f}%")
    _sel_rank = _rank_map.get(sel_code)
    if _sel_rank is not None and _sel_rank > rank_limit_v:
        alerts.append(
            f"등수 한계 경보 — 이 종목은 대장 {_sel_rank}등주 "
            f"(규칙: {rank_limit_v}등주까지만 매수 허용)"
        )
    # 시가 급등 추격 금지 (관행 기준 +5% — 오닐 CANSLIM 이상적 매수점 이내 진입 원칙)
    _intra = market_data.get_intraday_summary(sel_code)
    if _intra and _intra.get("open") and _intra.get("last"):
        _open_gain = (_intra["last"] / _intra["open"] - 1) * 100
        if _open_gain >= 5.0:
            alerts.append(
                f"시가 급등 추격 금지 — 오늘 시가 대비 {_open_gain:+.1f}% (관행 기준 +5%)"
            )
    if age_warn:
        alerts.append(f"테마 추격 주의 (D+{age})")

    if alerts:
        st.warning("**경보 발생** — 차단 아님, 무시 시 사유 필수 입력\n\n" + "\n".join(f"- {a}" for a in alerts))
        alert_override = st.checkbox("경보 내용을 확인하고 진행합니다", key="j2_alert_chk")
        if alert_override:
            alert_reason = st.text_input("경보 무시 사유 (필수)", key="j2_alert_reason")
        else:
            alert_reason = ""
    else:
        alert_override = True
        alert_reason = ""

    st.divider()

    # ⭐ 52주 신고가 임박주 — 매수 대상 선택 바로 아래 (2026-07-17 사용자 지정 위치)
    _render_near_high_table()

    st.divider()

    # ── 2d. 셋업 + 진입가/손절가/수량 ──────────────────────────────────────
    st.markdown("**셋업 및 진입 계획** — 위에서 고른 매수 대상을 기록하는 곳")
    st.caption(
        "자비스는 주문하지 않습니다 — 증권사에서 실제 매수한(또는 하려는) 내용을 여기 **기록**합니다. "
        "사용 순서: ① 셋업 선택 — **눌림재상승**=돌파 후 3~5% 눌렸다 재상승할 때 진입 / "
        "**돌파**=신고가 돌파 순간 진입. "
        "② 진입가·손절가·수량 입력 → 1R(이 매매에서 감수하는 최대 손실 금액)이 자동 계산됩니다. "
        "③ **기록하고 진입** = 판단 기록 저장 · **탈락으로 기록** = 검토했지만 진입 안 한 것도 기록. "
        "이렇게 30건이 쌓이면 어떤 셋업이 나에게 확률 높은지 통계로 확인합니다."
    )
    setup = st.radio("셋업", ["눌림재상승", "돌파"], horizontal=True, key="j2_setup")

    c1, c2, c3 = st.columns(3)
    entry_price = c1.number_input("진입가 (원)", min_value=0, step=100, key="j2_entry_price")
    stop_price = c2.number_input("손절가 (원)", min_value=0, step=100, key="j2_stop_price")
    qty = c3.number_input("수량 (주)", min_value=0, step=1, key="j2_qty")

    if entry_price > 0 and stop_price > 0 and stop_price < entry_price and qty > 0:
        one_r = (entry_price - stop_price) * qty
        st.info(f"1R = {one_r:,.0f}원  (진입 {entry_price:,}원 / 손절 {stop_price:,}원 / {qty}주)")
    else:
        one_r = 0

    # 3R 게이지 (playbook_journal 미청산 기준 — main()에서 1회 조회해 전달받음)
    open_n = len(open_pos)
    gauge_val = min(open_n / 3, 1.0)
    st.caption(f"오픈 포지션: {open_n}건 / 3건 기준")
    st.progress(gauge_val)
    if open_n >= 3:
        st.warning(f"미청산 {open_n}건 — 신규 진입 시 오픈 리스크 한도 점검")

    st.divider()

    # ── 2e. 저장 버튼 ────────────────────────────────────────────────────────
    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("기록하고 진입", type="primary", key="j2_save_entry"):
            # 유효성 검사
            errors = []
            if entry_price <= 0:
                errors.append("진입가를 입력하세요.")
            if stop_price <= 0:
                errors.append("손절가를 입력하세요.")
            elif stop_price >= entry_price:
                errors.append("손절가는 진입가보다 낮아야 합니다.")
            if qty <= 0:
                errors.append("수량을 입력하세요.")
            if alerts and not alert_override:
                errors.append("경보 확인 체크박스를 선택하세요.")
            if alerts and alert_override and not alert_reason.strip():
                errors.append("경보 무시 사유를 입력하세요.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                alert_state_str = ", ".join(["막차" if "막차" in a else "꺾임" if "꺾임" in a else "등수" if "등수" in a else "시가" if "시가" in a else "추격" for a in alerts]) if alerts else None
                tags = _tag_str(theme, setup, age, alert_state_str)
                leader_candidates = leader_result.get("candidates", []) if leader_result else []
                leader_name = leader_candidates[0]["name"] if leader_candidates else None
                try:
                    row_id = playbook.save_journal_entry(
                        theme_name=theme,
                        theme_age_days=age,
                        leader_name=leader_name,
                        target_ticker=f"{sel_code}.KS",
                        setup=setup,
                        entry_price=float(entry_price),
                        stop_price=float(stop_price),
                        qty=int(qty),
                        alert_state=alert_state_str,
                        alert_ignore_reason=alert_reason.strip() or None,
                        tags=tags,
                    )
                    st.success(f"진입 기록 완료 (id={row_id}) · 태그: {tags}")
                    # 3R 게이지 새로고침
                    st.rerun()
                except Exception as ex:
                    st.error(f"저장 실패: {ex}")

    with col_btn2:
        if st.button("탈락으로 기록", key="j2_save_dropout"):
            tags = f"#순환매 #탈락 #{theme}"
            try:
                row_id = playbook.save_dropout_entry(
                    theme_name=theme,
                    target_ticker=f"{sel_code}.KS",
                    tags=tags,
                )
                st.success(f"탈락 기록 완료 (id={row_id})")
            except Exception as ex:
                st.error(f"저장 실패: {ex}")


# ── 섹션 3: 급락일 기록 ──────────────────────────────────────────────────────


def _render_crash_log() -> None:
    df_idx = market_data.get_index_daily()
    today_chg = None
    if df_idx is not None and len(df_idx) >= 2:
        try:
            today_chg = round(
                (float(df_idx["Close"].iloc[-1]) / float(df_idx["Close"].iloc[-2]) - 1) * 100, 2
            )
        except Exception:
            pass

    if today_chg is None or today_chg > -3.0:
        # 급락일 아닌 경우: 섹션 자체를 숨김
        return

    st.subheader(f"급락일 기록  (오늘 코스피 {today_chg:+.2f}%)")
    st.caption("원인 가설과 보유 논리 훼손 여부를 기록합니다. 참고용, 점수/판정 반영 없음.")

    causes_opts = [
        "매크로 외생 (금리·환율·지정학 등)",
        "섹터 펀더멘털 (업황·실적 쇼크)",
        "종목 개별 (공시·수급)",
        "수급·기계적 (프로그램·ETF 리밸런싱)",
    ]
    causes = st.multiselect("원인 가설 (복수 선택 가능)", causes_opts, key="j2_crash_causes")
    holding_ok = st.radio(
        "보유 논리 훼손 여부", ["N (논리 유지)", "Y (논리 훼손)"],
        horizontal=True, key="j2_crash_logic",
    )
    memo = st.text_input("한 줄 메모 (선택)", key="j2_crash_memo")

    if st.button("급락일 기록 저장", key="j2_crash_save"):
        try:
            playbook.save_crash_log(
                log_date=datetime.now().strftime("%Y-%m-%d"),
                index_change_pct=today_chg,
                causes=causes,
                holding_logic_broken="Y" if holding_ok.startswith("Y") else "N",
                memo=memo,
            )
            st.success("급락일 기록 저장 완료.")
        except Exception as ex:
            st.error(f"저장 실패: {ex}")


_NH_CACHE_FILE = Path(__file__).parent.parent / "cache" / "market_data" / "nh_scan.json"


def _load_nh_scan_file():
    """당일 스캔 결과 파일 캐시 — 재접속/새 세션에서 재스캔 없이 즉시 로드."""
    try:
        d = json.loads(_NH_CACHE_FILE.read_text(encoding="utf-8"))
        if d.get("date") == datetime.now().strftime("%Y-%m-%d"):
            return d
    except Exception:
        pass
    return None


def _is_cloud() -> bool:
    """Turso 원격 DB 사용 여부로 클라우드 배포인지 판별.
    클라우드는 자원이 제한적이라 1,038종목 전수 스캔이 세션을 통째로
    멈추게 한 사고가 있었음 (2026-07-17) — 그래서 자동 스캔을 금지한다."""
    try:
        import database
        return database.is_remote_database()
    except Exception:
        return False


def _ensure_nh_scan(force_scan: bool = False):
    """신고가 임박주 스캔 결과 확보: 세션 → 당일 파일 → 자동 스캔 순.

    클라우드에서는 캐시가 없으면 자동 스캔하지 않고 None을 반환한다
    (force_scan=True로 명시 호출할 때만 스캔 허용 — 버튼 클릭 경로).
    로컬은 기존과 동일하게 항상 자동 스캔."""
    saved = st.session_state.get("j2_nh_scan")
    if saved:
        return saved
    fd = _load_nh_scan_file()
    if fd:
        saved = {
            "result": {"ok": True, "rows": fd.get("rows", []),
                       "scanned": fd.get("scanned", 0), "error": None},
            "at": fd.get("at", ""),
        }
        st.session_state["j2_nh_scan"] = saved
        return saved

    if _is_cloud() and not force_scan:
        return None

    prog = st.progress(0.0, text="신고가 임박주 자동 스캔 중… (하루 첫 스캔만 수 분, 이후 즉시)")
    result = playbook.scan_near_high(
        per_theme=3,
        progress_cb=lambda f, t: prog.progress(min(f, 1.0), text=t),
    )
    prog.empty()
    at = datetime.now().strftime("%m-%d %H:%M")
    saved = {"result": result, "at": at}
    st.session_state["j2_nh_scan"] = saved
    if result.get("ok"):
        try:
            _NH_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _NH_CACHE_FILE.write_text(
                json.dumps({
                    "date": datetime.now().strftime("%Y-%m-%d"), "at": at,
                    "scanned": result.get("scanned", 0), "rows": result["rows"],
                }, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            _log.warning("nh scan cache save failed: %s", e)
    return saved


def _render_near_high_table() -> None:
    """⭐ 52주 신고가 + 테마 — 자비스2 취지의 핵심 표(추천 관찰 종목).
    대장주 모음(테마 등락률 서열)과 별개로, 전 테마 구성종목 전수에서
    52주 고가 근접 게이트를 실제 통과한 종목만 모은다. 행 클릭 → 플레이북 연결."""
    st.subheader("⭐ 52주 신고가 + 테마 — 추천 관찰 종목")
    st.caption(
        "자동 스캔: 접속 시 당일 결과를 자동 표시 (하루 첫 스캔만 수 분, 이후 즉시). "
        "유니버스: 20개 테마 구성종목 전체(중복 제거) 전수 · "
        "기준: 52주 고가 대비 -10% 이내 · 근접도 순, 테마별 최대 3개. "
        "행을 클릭하면 해당 테마 플레이북으로 이동하고 매수 대상에 자동 선택됩니다."
    )
    st.caption(
        "**종합점수 공식(0~100, 투명 공개)**: 52주고가 근접도(0~75점, 학술 근거 있는 "
        "핵심 신호) + 거래대금배수(0~25점, 관행 기준 1.5배 이상 만점). 막차 주의 종목은 "
        "15점 상한 강제. 초록 70+ / 노랑 40~69 / 회색 40미만. "
        "이 표에 이미 나온 지표를 조합한 정렬 보조값일 뿐 — 검증된 매수 신호가 아닙니다."
    )

    if st.button("다시 스캔 (최신 시세로 갱신)", key="j2_nh_scan_btn"):
        st.session_state.pop("j2_nh_scan", None)
        try:
            _NH_CACHE_FILE.unlink()
        except Exception:
            pass
        st.session_state["j2_nh_force_scan"] = True
        st.rerun()

    _force = st.session_state.pop("j2_nh_force_scan", False)
    saved = _ensure_nh_scan(force_scan=_force)
    if not saved:
        st.info(
            "아직 스캔 결과가 없습니다 — 온라인에서는 전 테마 전수 스캔이 무거워 "
            "자동 실행하지 않습니다. 위 '다시 스캔' 버튼을 눌러 실행하세요."
        )
        return
    result = saved["result"]
    if not result.get("ok"):
        st.warning(f"스캔 실패: {result.get('error')}")
        return
    rows_raw = result.get("rows", [])
    if not rows_raw:
        st.info(f"신고가 임박주 없음 — {result.get('scanned', 0)}종목 스캔 결과 게이트 통과 0건.")
        return

    def _nh_score(pct_h, mult, judge) -> int:
        """종합점수(0~100) = 근접도(0~75, 학술 근거·52주고가 0%에 가까울수록 高)
        + 거래대금배수(0~25, 관행 기준 1.5배 이상 만점). 막차 주의면 15점 상한 강제
        (오닐 관행 — 추격 금지 대상은 우선순위 최하). 매수신호 아님 — 이 표에 이미
        나온 두 지표(52주고가대비·거래대금배수)를 조합한 참고용 정렬 보조 지표."""
        prox = max(0.0, min(10.0, abs(pct_h))) if pct_h is not None else 10.0
        s1 = (10.0 - prox) / 10.0 * 75.0
        s2 = min((mult or 0.0) / 1.5, 1.0) * 25.0
        total = round(s1 + s2)
        if judge == "막차 주의":
            total = min(total, 15)
        return max(0, min(100, total))

    def _score_color(sc: int) -> str:
        if sc >= 70:
            return "#22c55e"
        if sc >= 40:
            return "#facc15"
        return "#9ca3af"

    # st.dataframe(캔버스 렌더러)는 df.style의 text-align/컬럼값 정렬을 전부
    # 무시한다 — 색상(.map())만 별도 경로로 반영됨. 진짜 HTML/CSS로 그려야
    # 정렬이 실제로 먹는다. 대신 행 클릭 자동이동은 아래 선택+버튼으로 대체.
    rows = []
    for r in rows_raw:
        mkt = market_data.get_market(r["code"])
        mkt_txt = "코스닥" if mkt == "KOSDAQ" else "코스피" if mkt == "KOSPI" else "—"
        _score = _nh_score(r.get("pct_from_52w_high"), r.get("turnover_mult"), r.get("judge"))
        rows.append({
            "종목명": f"{r['name']} ({r['code']})",
            "테마": r["theme"],
            "시장": mkt_txt,
            "52주고가대비": f"{r['pct_from_52w_high']:+.1f}%",
            "현재가": f"{r['price']:,.0f}" if r.get("price") else "—",
            "오늘 등락률": f"{r['change_pct']:+.2f}%" if r.get("change_pct") is not None else "—",
            "종합점수": _score,
            "셋업 판정": r.get("judge", "—"),
            "거래대금배수": f"{r['turnover_mult']:.2f}배" if r.get("turnover_mult") is not None else "—",
        })

    import pandas as pd

    df = pd.DataFrame(rows)

    def _style_updown(val):
        s = str(val)
        if s.startswith("+"):
            return "color:#ff4b4b; font-weight:700"
        if s.startswith("-"):
            return "color:#4b9fff; font-weight:700"
        return ""

    def _style_judge(val):
        return _JUDGE_STYLE.get(str(val), "")

    def _style_mkt(val):
        if str(val) == "코스닥":
            return "color:#22c55e; font-weight:700"
        if str(val) == "코스피":
            return "color:#4b9fff; font-weight:700"
        return ""

    def _style_score(val):
        try:
            return f"color:{_score_color(int(val))}; font-weight:800"
        except (TypeError, ValueError):
            return ""

    _right_cols = ["52주고가대비", "현재가", "오늘 등락률", "종합점수", "거래대금배수"]
    _center_cols = ["시장", "셋업 판정"]
    styled = (
        df.style
        .map(_style_updown, subset=["52주고가대비", "오늘 등락률"])
        .map(_style_judge, subset=["셋업 판정"])
        .map(_style_mkt, subset=["시장"])
        .map(_style_score, subset=["종합점수"])
        .set_table_styles([{"selector": "th", "props": [("text-align", "center")]}])
        .set_properties(subset=_right_cols, **{"text-align": "right"})
        .set_properties(subset=_center_cols, **{"text-align": "center"})
        .hide(axis="index")
    )
    _render_html_table(styled)
    st.caption(f"스캔 시각 {saved['at']} · {result.get('scanned', 0)}종목 검사, {len(rows_raw)}종목 통과")

    # 행 클릭 자동이동 대체 — 표는 이제 순수 HTML이라 클릭 이벤트가 없다
    _nh_themes = sorted({r["theme"] for r in rows_raw})
    _nc1, _nc2 = st.columns([3, 1])
    _nh_pick = _nc1.selectbox(
        "표에서 테마 골라 플레이북으로 이동", _nh_themes, key="j2_nh_theme_pick",
    )
    if _nc2.button("이동", key="j2_nh_goto_btn", use_container_width=True):
        if _nh_pick in _THEME_NAMES and _nh_pick != st.session_state.get("j2_prev_theme"):
            st.session_state["j2_pending_theme"] = _nh_pick
            st.session_state["j2_scroll_playbook"] = True
            st.rerun()

    with st.expander("📖 52주 신고가 + 테마 매매기법 설명서", expanded=False):
        st.markdown(
            """
### 표시 방식 안내
🤖 **자동** = 자비스가 계산·표시 (그대로 확인만 하면 됨)
✍️ **수동** = 사용자가 직접 판단·확인·기록해야 하는 것 (자비스가 대신 안 함)

---

### 이 기법이 무엇인가
테마(산업) 안에서 52주 신고가에 근접한 대장주를 골라, 돌파 또는 눌림재상승에서만 진입하는 스윙 기법.

**근거 등급 — 출처를 구분해 둡니다**

- **[학술]** 52주 신고가 근접주는 이후 초과수익 경향(George&Hwang 2004, 20개국 확인).
  원인은 앵커링: 투자자가 52주 고가를 심리적 기준점 삼아 호재에 과소반응. 개별 기업보다
  산업(테마) 정보 과소반응이 주도 → "테마+신고가" 조합의 근거. 하락장에선 모멘텀 수익 급감
  → 시장상태 경고의 근거.
- **[관행]** 거래대금 1.5배, 시가+5% 추격금지, 손절 -7~8%, 청산 신호들은 윌리엄 오닐(CANSLIM)
  유래 — 검증 통계 아님. "성공률 95%" 류 수치는 근거 없는 마케팅이니 무시할 것.
- **[자비스 임의값]** 테마나이 D+3, 신고가 근접 게이트 10%, 막차 기준 20% 급등 등 설정
  임계값은 전부 제(자비스)가 정한 시작값입니다 — 논문에도 오닐 자료에도 없는 숫자입니다.
  기록 30건 전 변경 금지.

🤖 **종합점수(⭐ 표) 계산 방식**: 52주고가 근접도 0~75점([학술] 근거 있는 핵심 신호라 최대
가중치) + 거래대금배수 0~25점([관행] 1.5배 이상 만점). 막차 주의 판정이면 15점 상한 강제.
매수 신호가 아니라 이미 표에 나온 두 지표를 조합한 정렬 보조값일 뿐입니다.

---

### 실전 순서 (화면 위→아래)

**① 시장 확인**
🤖 맨 위 경고 스트립을 봅니다. 하락국면/변동성 경고가 뜨면 신규 진입 중단이 원칙입니다.

**② 테마 게이트**
🤖 신호등 3개(양전 3종목+ / 거래대금 급증 / 연속강세) + 테마나이가 자동 표시됩니다.
D+3 초과는 막차 취급(**[자비스 임의값]**).
✍️ 재료가 지속형인지는 직접 판단하세요 — 실적·수주·정책=지속형, 풍문·단발 뉴스=단발형.
재료 유형을 태그로 기록해 두세요.

**③ 종목 선택**
🤖 ⭐ 52주 신고가+테마 표가 추천 관찰 목록입니다. 셋업 판정이 자동 계산됩니다:
돌파 임박(근접+배수 충족, 최우선) / 눌림 관찰(근접만) / 막차 주의(20일 내 +20% 급등, 진입 금지)
/ 부적격. 행을 클릭하면 플레이북·매수 대상에 자동 연결됩니다.
✍️ 대장주 모음 표는 테마 진위 확인용입니다(매수 대상 아님) — 최종 종목 선택은 직접 하세요.

**④ 진입 — 두 셋업만**
- **돌파**: 신고가 돌파 + 당일 거래대금이 20일 평균의 1.5배 이상.
  🤖 요약 카드의 거래대금 배수 칸을 참고하세요. 시가 대비 +5% 이상 급등했으면 자동 경보(추격 금지).
  막차 경보가 뜨면 사유를 입력하기 전까지 진입이 막힙니다.
  ✍️ 실제로 돌파했는지, 거래량이 충분한지는 직접 확인하세요.
- **눌림재상승**: 테마 발화 후 눌림 → 전일 고가 회복 시 진입. 손절 = 눌림 구간 저가.
  ✍️ 눌림·재상승 여부는 직접 판단하세요.

🤖 수량을 입력하면 1R이 자동 계산되고, 3건 오픈 한도 게이지가 표시됩니다.
✍️ 경보를 무시하려면 사유를 반드시 입력해야 저장됩니다(자비스가 강제).

**⑤ 손절**
✍️ 돌파 기준가를 종가로 하회하고 회복 못 할 때 손절하세요. 병행 안전선(**[관행]**): 진입가
-7~8% 도달 시 무조건.
🤖 대장 꺾임 경보가 뜨면 확인하세요.
✍️ 테마 동반 상승 종목 수가 급감했는지는 직접 체크하세요.

**⑥ 보유·청산 일일 체크**
✍️ 아래는 전부 수동 체크입니다 — 하나라도 해당하면 축소를 검토하세요:
- 대장꺾임 배지 점등 (🤖 자동 표시됨, 확인은 직접)
- 신호등 소멸 — 동반상승 종목 수 급감 (✍️ 재조회해서 확인)
- 거래량 없이 신고가만 갱신 — 수요 약화 신호 (✍️ 직접 확인, 자동 감지 안 됨)
- 장대음봉 + 거래량 증가 — 기관 분산 신호 (✍️ 직접 확인, 자동 감지 안 됨)
- 지수 급락일 (🤖 자동 감지되면 급락일 기록 섹션이 뜸, ✍️ 원인은 직접 기록)

대장주가 거래량을 동반하며 신고가를 계속 높이면 보유하세요. 테마 전체가 꺾이면 내 종목이
버텨도 정리하세요.

**⑦ 기록 규율**
✍️ 탈락(진입 안 한 것)도 반드시 기록하세요. 목표 30건.
🤖 진행률(N/30건)은 판단 기록 탭에 자동 표시됩니다.
30건 전에는 임계값·규칙을 감으로 바꾸지 마세요.
"""
        )


_JUDGE_ORDER = {"돌파 임박": 0, "눌림 관찰": 1, "막차 주의": 2, "부적격": 3}
_JUDGE_STYLE = {
    "돌파 임박": "color:#22c55e; font-weight:800",
    "눌림 관찰": "color:#facc15; font-weight:700",
    "막차 주의": "color:#ff4b4b; font-weight:700",
    "부적격": "color:#9ca3af",
}


def _render_leader_table() -> None:
    """강한 테마의 1·2등주 모음 표 — 확률 높은 셋업 판정 순 정렬.
    (자비스1 '오늘 주가 계산 결과' 스타일 · 메모/시총대비/섹터 없음)"""
    st.subheader("대장주 모음 (1·2등주)")
    st.caption(
        "셋업 판정 기준(참고용 자동 판정 — 매수 신호 아님): "
        "**돌파 임박**=신고가 근접+거래대금 배수 충족 · **눌림 관찰**=신고가 근접(배수 미충족) · "
        "**막차 주의**=20일 내 +20% 급등 이력 · **부적격**=근접 게이트 미충족. 판정 순으로 정렬."
    )
    store = st.session_state.get("j2_leader_table") or {}
    raw = []
    for theme_nm, cands in store.items():
        for rank, c in cands:
            raw.append((theme_nm, rank, c))
    if not raw:
        st.info("아직 없음 — 첫 로딩 자동 수집 또는 테마 신호 확인에서 대장 후보가 나오면 쌓입니다.")
        return

    # 확률 높은 판정 순 → 같은 판정 안에서는 52주고가 근접 순
    def _sort_key(item):
        _, _, c = item
        judge = c.get("setup_judge", "부적격")
        pct_h = c.get("pct_from_52w_high")
        return (_JUDGE_ORDER.get(judge, 9), -(pct_h if pct_h is not None else -999))

    raw.sort(key=_sort_key)

    rows = []
    for theme_nm, rank, c in raw:
        pct_h = c.get("pct_from_52w_high")
        if c.get("near_high"):
            w52 = "52주 고가근접 — 적격"
        elif pct_h is not None:
            w52 = f"고가근접미달 (52주고가대비 {pct_h:+.1f}%)"
        else:
            w52 = "데이터 없음"
        chg = c.get("change_pct")
        mult = c.get("turnover_mult")
        price = c.get("price")
        op = c.get("open_pct")
        hp = c.get("high_pct")
        rows.append({
            "등수": f"{rank}등주",
            "종목명": f"{c['name']} ({c['code']})",
            "테마": theme_nm,
            "52주": w52,
            "셋업 판정": c.get("setup_judge", "—"),
            "현재가": f"{price:,.0f}" if price else "—",
            "전일대비(%)": f"{chg:+.2f}%" if chg is not None else "—",
            "시가대비(오늘)": f"{op:+.2f}%" if op is not None else "—",
            "고점대비(오늘)": f"{hp:+.2f}%" if hp is not None else "—",
            "거래대금배수": f"{mult:.2f}배" if mult is not None else "—",
        })

    import pandas as pd

    df = pd.DataFrame(rows)

    def _style_updown(val):
        s = str(val)
        if s.startswith("+"):
            return "color:#ff4b4b; font-weight:700"
        if s.startswith("-"):
            return "color:#4b9fff; font-weight:700"
        return ""

    def _style_52w(val):
        if "적격" in str(val) and "미달" not in str(val):
            return "color:#34d399; font-weight:700"
        return ""

    def _style_judge(val):
        return _JUDGE_STYLE.get(str(val), "")

    _right_cols = ["현재가", "전일대비(%)", "시가대비(오늘)", "고점대비(오늘)", "거래대금배수"]
    _center_cols = ["등수", "셋업 판정"]
    styled = (
        df.style
        .map(_style_updown, subset=["전일대비(%)", "시가대비(오늘)", "고점대비(오늘)"])
        .map(_style_52w, subset=["52주"])
        .map(_style_judge, subset=["셋업 판정"])
        .set_table_styles([{"selector": "th", "props": [("text-align", "center")]}])
        .set_properties(subset=_right_cols, **{"text-align": "right"})
        .set_properties(subset=_center_cols, **{"text-align": "center"})
        .hide(axis="index")
    )
    st.caption("아래에서 테마를 골라 이동하면 해당 테마의 순환매 플레이북으로 연결됩니다.")
    _render_html_table(styled)

    _lt_themes = sorted({theme_nm for theme_nm, _, _ in raw})
    _lc1, _lc2 = st.columns([3, 1])
    _lt_pick = _lc1.selectbox(
        "표에서 테마 골라 플레이북으로 이동", _lt_themes, key="j2_leader_theme_pick",
    )
    if _lc2.button("이동", key="j2_leader_goto_btn", use_container_width=True):
        if _lt_pick in _THEME_NAMES and _lt_pick != st.session_state.get("j2_prev_theme"):
            st.session_state["j2_pending_theme"] = _lt_pick
            st.session_state["j2_scroll_playbook"] = True
            st.rerun()


def _render_interest_scoreboard_ref() -> None:
    with st.expander("관심점수판 · 참고용 (동결 중)", expanded=False):
        st.caption(
            "30건 통계 후 조건별 재평가 예정 — 지금은 감으로 건드리지 않습니다. "
            "기존 관심 점수표는 자비스1(사이드바 'app' 페이지) 한국장 판단 탭에서 그대로 볼 수 있습니다."
        )


# ── 섹션 4: 테마판 요약 ──────────────────────────────────────────────────────


@st.fragment(run_every=60)
def _render_live_strip() -> None:
    """대장 후보 3종목 실시간 시세 — 1분마다 이 조각만 자동 갱신.
    (2026-07-17 사용자 지시로 실시간 자동조회 금지 규칙 해제)
    fetch_theme_stocks의 60초 TTL 캐시와 주기가 맞아 분당 네이버 요청 1회."""
    theme = st.session_state.get("j2_prev_theme") or ""
    leader_result = st.session_state.get("j2_leader")
    if not theme or not leader_result or not leader_result.get("ok"):
        return
    cands = (leader_result.get("candidates") or [])[:3]
    if not cands:
        return
    try:
        res = theme_detail.fetch_theme_stocks(theme)
    except Exception:
        return
    if not res.get("ok"):
        return
    price_map = {s["code"]: s for s in res["stocks"]}

    st.markdown(
        "<span style='color:#34d399;font-weight:800'>실시간 시세</span> "
        "<span style='color:#9ca3af;font-size:0.82rem'>(1분마다 자동 갱신 · 네이버 지연시세)</span>",
        unsafe_allow_html=True,
    )
    cols = st.columns(len(cands))
    for i, c in enumerate(cands):
        live = price_map.get(c["code"])
        with cols[i]:
            if live and live.get("price"):
                st.markdown(
                    f"<span style='color:#4dc3ff;font-weight:800'>{c['name']}</span><br>"
                    f"<span style='font-size:1.35rem;font-weight:800'>{live['price']:,}원</span> "
                    f"{_sign_html(live.get('change_pct'))}",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<span style='color:#4dc3ff;font-weight:800'>{c['name']}</span><br>—",
                    unsafe_allow_html=True,
                )
    st.caption(f"갱신 {datetime.now().strftime('%H:%M:%S')}")


@st.fragment(run_every=60)
def _render_qualified_slot() -> None:
    """적격 대장 별도 난 — 52주 신고가 근접 게이트를 통과한 종목은 희소하고
    중요하므로 테마판 위에 항상 표시한다. 신호 확인에서 발견될 때마다 축적.
    전 건 표시. 시세(오늘 등락률)는 1분마다 자동 갱신(실시간).
    코스피=파랑 / 코스닥=초록 배지."""
    st.markdown("**⭐ 적격 대장 현황** — 52주 신고가 근접 게이트 통과 종목")
    store = st.session_state.get("j2_qualified") or {}
    rows = []
    for theme_nm, info in store.items():
        for c in info.get("stocks", []):
            rows.append((theme_nm, c, info.get("at", "")))
    if not rows:
        st.info("아직 없음 — 테마 신호 확인에서 적격 대장이 발견되면 여기에 표시됩니다.")
        return

    # 실시간 시세 맵 (테마당 네이버 1회/분 — 60초 TTL 캐시와 주기 일치)
    live: dict = {}
    for theme_nm in store.keys():
        try:
            res = theme_detail.fetch_theme_stocks(theme_nm)
            if res.get("ok"):
                for s in res["stocks"]:
                    live[s["code"]] = s
        except Exception:
            pass

    per_row = 4
    for start in range(0, len(rows), per_row):
        chunk = rows[start:start + per_row]
        cols = st.columns(per_row)
        for i, (theme_nm, c, at_time) in enumerate(chunk):
            with cols[i]:
                pct_h = c.get("pct_from_52w_high")
                liv = live.get(c["code"]) or {}
                chg = liv.get("change_pct", c.get("change_pct"))
                mkt = market_data.get_market(c["code"])
                if mkt == "KOSDAQ":
                    mkt_html = " <span style='color:#22c55e;font-weight:700'>코스닥</span>"
                elif mkt == "KOSPI":
                    mkt_html = " <span style='color:#4b9fff;font-weight:700'>코스피</span>"
                else:
                    mkt_html = ""
                st.markdown(
                    "<div style='background:rgba(52,211,153,0.08);border:1px solid #14532d;"
                    "border-radius:10px;padding:0.6rem 0.75rem;margin-bottom:0.5rem'>"
                    f"<div style='color:#4dc3ff;font-weight:800;font-size:1.05rem'>{c['name']} "
                    f"<span style='font-size:0.8rem;color:#93c5fd'>{c['code']}</span></div>"
                    f"<div style='color:#ff6b6b;font-weight:700'>{theme_nm}{mkt_html}</div>"
                    f"<div><span style='color:#34d399'>52주고가대비</span>: {_sign_html(pct_h, 1)}</div>"
                    f"<div><span style='color:#34d399'>오늘 등락률</span>: {_sign_html(chg, 2)}</div>"
                    f"<div style='color:#9ca3af;font-size:0.78rem'>적격 확인 {at_time}</div>"
                    "</div>",
                    unsafe_allow_html=True,
                )
    st.caption(
        f"시세 갱신 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · 1분마다 자동 · "
        "'적격 확인'은 그 테마 신호를 마지막으로 조회해 게이트 통과를 확인한 시각"
    )


# 자비스1 테마 상태 색 관례 참조: 강함 빨강 / 보통 파랑 / 약함 회색 (app.py 5873행대)
_VERDICT_STYLE = {
    "강함": ("#ff4b4b", "rgba(255,75,75,0.14)"),
    "보통": ("#4b9fff", "rgba(75,159,255,0.14)"),
    "약함": ("#94a3b8", "rgba(148,163,184,0.14)"),
}


def _fetch_theme_snap_into_state() -> None:
    snap = fetch_kr_theme_snapshot()
    st.session_state["j2_theme_snap"] = snap
    if snap.get("ok"):
        verdicts = {
            name: info.get("verdict", "보통")
            for name, info in snap.get("themes", {}).items()
            if info.get("ok")
        }
        if verdicts:
            try:
                theme_history.record_theme_states(verdicts)
            except Exception as e:
                _log.warning("record_theme_states (panel) failed: %s", e)


def _render_theme_panel() -> None:
    st.subheader("테마판")
    st.caption("카드를 클릭하면 아래 플레이북 테마가 자동 선택되고 신호도 자동 조회됩니다.")

    # 초기 화면에서 클릭 없이 자동 조회 (세션당 1회, 이후엔 버튼으로 갱신)
    snap = st.session_state.get("j2_theme_snap")
    if snap is None:
        with st.spinner("테마판 자동 조회 중…"):
            _fetch_theme_snap_into_state()
        snap = st.session_state.get("j2_theme_snap")

    if st.button("테마판 새로고침", key="j2_theme_panel_refresh"):
        with st.spinner("20개 테마 조회 중 (병렬)…"):
            _fetch_theme_snap_into_state()
        st.rerun()

    if not snap or not snap.get("ok"):
        st.warning(f"테마 조회 실패: {(snap or {}).get('error', '알 수 없음')}")
        return

    items = []
    failed = 0
    for name, info in snap.get("themes", {}).items():
        if info.get("ok"):
            items.append((name, info))
        else:
            failed += 1
    # 등락률 높은 순 — 뜨거운 테마가 위로
    items.sort(key=lambda x: x[1].get("change_pct") if x[1].get("change_pct") is not None else -999, reverse=True)

    # 카드 = st.button (같은 세션 안에서 rerun — 링크 방식은 세션이 초기화되어
    # 로그인이 풀리므로 금지). 버튼을 카드처럼 보이게 CSS로 스타일링.
    st.markdown(
        """
        <style>
        div[class*="st-key-j2_tp_"] button {
            background: #141b2a !important;
            border: 1px solid #263247 !important;
            border-radius: 12px !important;
            width: 100%;
            min-height: 5.2rem;
            padding: 0.55rem 0.8rem !important;
            justify-content: flex-start;
        }
        div[class*="st-key-j2_tp_"] button:hover { border-color: #ffb020 !important; }
        div[class*="st-key-j2_tp_"] button [data-testid="stMarkdownContainer"] p {
            font-size: 1.02rem; line-height: 1.45; text-align: left;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    per_row = 4
    for row_start in range(0, len(items), per_row):
        row_items = items[row_start:row_start + per_row]
        cols = st.columns(per_row)
        for offset, (name, info) in enumerate(row_items):
            pct = info.get("change_pct")
            verdict = info.get("verdict", "—")
            try:
                age = theme_history.get_theme_elapsed_strong_days(name)
            except Exception:
                age = None
            if pct is None:
                pct_md = "—"
            elif pct > 0:
                pct_md = f":red[**+{pct:.2f}%**]"
            elif pct < 0:
                pct_md = f":blue[**{pct:.2f}%**]"
            else:
                pct_md = "**0.00%**"
            streak_md = f" · 연속 {age}일" if age else ""
            label = f"**{name}**  \n{pct_md}  \n:gray[{verdict}{streak_md}]"
            with cols[offset]:
                if st.button(label, key=f"j2_tp_{row_start + offset}", use_container_width=True):
                    st.session_state["j2_theme_select"] = name
                    st.session_state["j2_autorun_signal"] = True

    checked_at = snap.get("checked_at")
    foot = f"조회 시각: {checked_at}" if checked_at else ""
    if failed:
        foot += f"  ·  조회 실패 {failed}개 테마"
    if foot:
        st.caption(foot)


# ── 섹션 5: 판단 기록 ────────────────────────────────────────────────────────


def _render_journal(records: list) -> None:
    st.subheader("판단 기록")
    total = len(records)
    st.progress(min(total / 30, 1.0), text=f"{total}/30건 (30건 달성 시 조건별 기대값 분석 가능)")

    if not records:
        st.info("기록이 없습니다. 플레이북에서 첫 번째 기록을 남겨보세요.")
        return

    for r in records:
        tags = r.get("tags", "")
        is_dropped = r.get("is_dropped", 0)
        result = r.get("result")
        recorded_at = r.get("recorded_at", "")[:16]
        theme_nm = r.get("theme_name", "—")
        ticker = r.get("target_ticker", "—")
        setup = r.get("setup", "—")
        age_days = r.get("theme_age_days")

        status_label = "탈락" if is_dropped else ("완료" if result else "오픈")
        with st.expander(
            f"[{status_label}] {theme_nm} · {ticker} · {setup or '—'} — {recorded_at}",
            expanded=False,
        ):
            c1, c2, c3 = st.columns(3)
            c1.metric("진입가", f"{r.get('entry_price') or '—':,}" if r.get("entry_price") else "—")
            c2.metric("손절가", f"{r.get('stop_price') or '—':,}" if r.get("stop_price") else "—")
            c3.metric("1R", f"{r.get('r_amount') or '—':,.0f}원" if r.get("r_amount") else "—")
            if not is_dropped and not result:
                st.caption(f"청산 시나리오: {_exit_scenario(setup)}")
            if age_days is not None:
                st.caption(f"테마나이 D+{age_days}")
            if tags:
                st.caption(f"태그: {tags}")
            alert = r.get("alert_state")
            if alert:
                reason = r.get("alert_ignore_reason", "")
                st.caption(f"경보: {alert} / 무시사유: {reason or '없음'}")


# ── 섹션 4b: 오픈 리스크 + 보유 포지션 카드 ──────────────────────────────────


def _render_open_risk(open_pos: list) -> None:
    st.subheader("오픈 리스크")
    open_n = len(open_pos)
    st.progress(min(open_n / 3, 1.0), text=f"{open_n}건 / 3건 기준 (플레이북 기록 건수 합산)")
    if open_n >= 3:
        st.warning(f"미청산 {open_n}건 — 신규 진입 시 오픈 리스크 한도 점검")

    st.markdown("**보유 포지션**")
    if not open_pos:
        st.caption("보유 중인 포지션이 없습니다.")
        return

    for r in open_pos:
        theme_nm = r.get("theme_name", "—")
        ticker = r.get("target_ticker", "—")
        stop_price = r.get("stop_price")
        setup = r.get("setup")
        tags = r.get("tags", "")
        with st.container(border=True):
            c1, c2 = st.columns([2, 1])
            c1.markdown(f"**{theme_nm}** · `{ticker}`")
            c2.markdown(f"손절 {stop_price:,.0f}" if stop_price else "손절 —")
            st.caption(f"청산 시나리오: {_exit_scenario(setup)}")
            if tags:
                st.caption(tags)


# ── 섹션 5b: 무시 로그 (경보 + 필터 통합) ───────────────────────────────────


def _render_ignore_log(records: list) -> None:
    st.subheader("무시 로그 (경보 + 필터 통합)")

    log_rows = []
    for r in records:
        date_short = (r.get("recorded_at") or "")[5:10] or "—"
        theme_nm = r.get("theme_name", "—")
        if r.get("alert_state"):
            reason = r.get("alert_ignore_reason") or "사유 없음"
            log_rows.append(("막차경보", date_short, theme_nm, reason))
        elif r.get("is_dropped"):
            reason = r.get("tags") or "—"
            log_rows.append(("필터", date_short, theme_nm, reason))

    if not log_rows:
        st.caption("경보 무시·필터 로그가 없습니다.")
        return

    for tag_label, date_short, theme_nm, reason in log_rows[:15]:
        render = st.error if tag_label == "막차경보" else st.info
        render(f"**{tag_label}**  {date_short} {theme_nm} — \"{reason}\"")


# ── 섹션 5c: 태그별 기대값 채점표 (30건 전까지 잠금) ─────────────────────────


def _render_tag_scorecard(records: list) -> None:
    st.markdown("**태그별 기대값 채점표**")
    total = len(records)
    st.progress(min(total / 30, 1.0), text=f"기록 진행 {total}/30건")

    tag_counts: dict[str, int] = {}
    for r in records:
        for tag in (r.get("tags") or "").split():
            tag = tag.lstrip("#")
            if not tag:
                continue
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    if not tag_counts:
        st.caption("아직 태그가 달린 기록이 없습니다.")
        return

    rows = [
        {"태그": tag, "건수": cnt, "평균 R": "잠김"}
        for tag, cnt in sorted(tag_counts.items(), key=lambda kv: -kv[1])
    ]
    import pandas as pd
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(
        "30건 도달 시 자동 활성 · 소표본 판단은 우연에 속는 지름길이라 잠급니다. "
        "평균 R은 청산 결과 기록 기능이 아직 없어 30건 이후에도 v1.1 과제로 남습니다."
    )


# ── 섹션 6: 설정 ─────────────────────────────────────────────────────────────


_CFG_LABELS = {
    "near_high_pct":       ("신고가 근접 (%)", "52주 최고가 대비 이 % 이내면 '근접'으로 판단"),
    "value_mult":          ("거래대금 배수", "당일 거래대금이 20일 평균의 이 배 이상이면 급증"),
    "min_value_eok":       ("유동성 하한 (억)", "이 금액 미만 종목은 대장 후보 제외 (현재 미구현)"),
    "max_spike_pct":       ("막차 기준 (%)", "최근 20일 내 이 % 이상 단일 급등 시 막차 경보"),
    "entry_max_age":       ("진입 허용 (일차)", "테마 연속강세 이 일 초과 시 추격 주의"),
    "leader_break_pct":    ("대장 꺾임 (%)", "최근 고점 대비 이 % 이상 하락 시 꺾임 경보"),
    "rank_limit":          ("등수 한계", "매수는 이 등수까지만 허용 (2 = 3등주 매수 금지)"),
    "volatile_days_warn":  ("시장 경고 변동일수", "60일 중 ±3% 이상 날이 이 이상이면 시장 경고"),
}


def _render_settings() -> None:
    st.caption(
        "시작값은 임의 제안 — **30건 증거 전 감으로 수정 금지**. "
        "통계 근거가 쌓인 뒤 조정하세요."
    )
    cfg = _cfg()
    updated = {}
    for key, (label, desc) in _CFG_LABELS.items():
        val = cfg.get(key, playbook._PLAYBOOK_CONFIG_DEFAULTS.get(key, 0.0))
        new_val = st.number_input(
            label, value=float(val), help=desc, step=0.5, key=f"j2_cfg_{key}"
        )
        updated[key] = new_val

    if st.button("설정 저장", key="j2_cfg_save"):
        import database
        conn = database.get_connection()
        try:
            # Turso 원격에서 upsert 구문이 간헐 실패해 SELECT 후 분기 방식만 쓴다
            for k, v in updated.items():
                row = conn.execute(
                    "SELECT 1 FROM playbook_config WHERE key=?", (k,)
                ).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO playbook_config (key, value) VALUES (?, ?)", (k, v)
                    )
                else:
                    conn.execute(
                        "UPDATE playbook_config SET value=? WHERE key=?", (v, k)
                    )
            conn.commit()
            playbook.invalidate_config_cache()
            st.success("설정 저장 완료.")
            # 시장상태 캐시도 무효화 (volatile_days_warn 변경 대응)
            st.session_state.pop("j2_market_state", None)
        except Exception as ex:
            st.error(f"설정 저장 실패: {ex}")
        finally:
            conn.close()


# ── 메인 ────────────────────────────────────────────────────────────────────


def main() -> None:
    st.title("자비스2 — 순환매 플레이북")

    tab_kr, tab_action, tab_stats, tab_journal, tab_settings = st.tabs(
        ["한국장", "행동·청산", "복기·통계", "기록", "보조"]
    )

    # journal/open-positions는 rerun당 1회만 조회해 전 탭에 공유
    # (기존엔 렌더링마다 4회 중복 조회 — 원격 DB에선 매번 네트워크 왕복)
    records = playbook.get_journal_recent(30)
    open_pos = playbook.get_open_positions()

    with tab_kr:
        # 초기 화면: 클릭 없이 시장상태 + 적격대장 + 테마판이 바로 보이게 배치
        _render_market_state()
        st.divider()
        _render_qualified_slot()
        st.divider()
        _render_theme_panel()
        st.divider()
        _render_playbook(open_pos)
        st.divider()
        _render_crash_log()
        _render_interest_scoreboard_ref()
        st.divider()
        _render_leader_table()

    with tab_action:
        _render_open_risk(open_pos)
        st.divider()
        _render_ignore_log(records)

    with tab_stats:
        _render_tag_scorecard(records)

    with tab_journal:
        _render_journal(records)

    with tab_settings:
        with st.expander("플레이북 설정 (playbook_config)", expanded=True):
            _render_settings()


main()

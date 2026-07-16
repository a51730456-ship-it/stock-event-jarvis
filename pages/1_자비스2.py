"""자비스2 — 순환매 플레이북 & 급락일 기록 페이지.

기존 파일(app.py, database.py, theme_history.py 등)은 수정하지 않는다.
P1 모듈(market_data, theme_detail, playbook)만 import해서 사용한다.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

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
    </style>
    """,
    unsafe_allow_html=True,
)

_log = logging.getLogger(__name__)

# ── 인증 게이트 ────────────────────────────────────────────────────────────────
if not st.session_state.get("authenticated"):
    st.warning("자비스1 메인 페이지에서 먼저 로그인하세요.")
    st.stop()

# ── 공통 임포트 (인증 후) ──────────────────────────────────────────────────────
import market_data
import playbook
import theme_detail
import theme_history
from theme_data import KR_THEME_NAVER_MAPPING, fetch_kr_theme_snapshot

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
        st.warning(
            "**모멘텀 진입 축소 권고** — "
            + ("하락국면 " if phase == "하락국면" else "")
            + (f"60일 변동일수 {vdays}일(기준 {warn_days}일) " if vdays and vdays >= warn_days else "")
            + "→ 새 진입 시 포지션 크기 절반 이하 고려"
        )

    if st.button("시장 상태 새로고침", key="j2_ms_refresh"):
        st.session_state.pop("j2_market_state", None)
        st.rerun()


# ── 섹션 2: 순환매 플레이북 ──────────────────────────────────────────────────


def _clear_theme_cache() -> None:
    for k in ["j2_signals", "j2_leader", "j2_stocks", "j2_stock_select"]:
        st.session_state.pop(k, None)


def _render_playbook() -> None:
    cfg = _cfg()
    st.subheader("순환매 플레이북")
    st.caption("매수신호·점수·목표가는 표시하지 않습니다. 기록과 확인 도구입니다.")

    # ── 2a. 테마 선택 + 신호 확인 ──────────────────────────────────────────────
    # (테마판 버튼 클릭 시 j2_theme_select/j2_autorun_signal이 미리 설정되어 들어온다)
    prev_theme = st.session_state.get("j2_prev_theme", "")
    theme = st.selectbox("테마 선택", _THEME_NAMES, key="j2_theme_select")
    if theme != prev_theme:
        _clear_theme_cache()
        st.session_state["j2_prev_theme"] = theme

    run_signal = st.button("신호 확인 (네트워크 조회)", key="j2_signal_btn")
    if st.session_state.pop("j2_autorun_signal", False):
        run_signal = True
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
                    "at": datetime.now().strftime("%H:%M"),
                }

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

    # 양전 종목이 실제로 무엇인지 펼쳐서 확인 (등락률 높은 순)
    _all_stocks = (stocks_result or {}).get("stocks", [])
    _ups = sorted(
        [s for s in _all_stocks if (s.get("change_pct") or 0) > 0],
        key=lambda s: s["change_pct"], reverse=True,
    )
    if _ups:
        with st.expander(f"양전 종목 {len(_ups)}개 보기 (등락률 순)", expanded=False):
            chips = "".join(
                f"<span class='j2-upchip'>{s['name']} <b>+{s['change_pct']:.2f}%</b></span>"
                for s in _ups
            )
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
    st.markdown("**대장 확인** · 매수 대상 아님 — 확인용")
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
                lines = [f"**{rank_names[i]} — {c['name']}** `{c['code']}`"]
                lines.append(f"52주고가대비: {pct_h:+.1f}%" if pct_h is not None else "52주고가대비: 데이터 없음")
                lines.append(f"거래대금배수: {mult_c:.2f}배" if mult_c is not None else "거래대금배수: 데이터 없음")
                lines.append(f"등락률: {chg:+.2f}%" if chg is not None else "등락률: 데이터 없음")
                st.markdown("  \n".join(lines))
                if i + 1 > rank_limit_v:
                    st.error(f"{i + 1}등 — 매수 금지 (등수 한계 {rank_limit_v})")
                elif c.get("near_high"):
                    st.success("52주고가 근접 — 적격")
                elif pct_h is None:
                    st.info("일봉 데이터 없음 — 근접 판정 불가")
                else:
                    st.warning(f"고가 근접 미달 (52주고가 대비 {pct_h:+.1f}%)")
    else:
        err = leader_result.get("error") if leader_result else "후보 없음"
        st.warning(f"대장 후보를 계산하지 못했습니다: {err}")

    st.divider()

    # ── 2c. 매수 대상 선택 ──────────────────────────────────────────────────
    st.markdown("**매수 대상 선택** (반자동 — 최종 선택은 사용자)")
    st.caption(
        "후보 출처: 네이버 이 테마의 구성종목 전체를 **등락률 높은 순**으로 정렬한 목록. "
        "자비스는 목록과 경보만 제공하고 매수 판단은 사용자가 합니다."
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

    stock_opts = [f"{s['name']} ({s['code']}) {_pct_label(s.get('change_pct'))}" for s in stocks]
    sel_idx = st.selectbox(
        "종목 선택", range(len(stock_opts)),
        format_func=lambda i: stock_opts[i],
        # 테마별 별도 키 — 이전 테마의 선택 인덱스가 남아 차트/요약이
        # 다른 종목을 가리키는 불일치를 원천 차단
        key=f"j2_stock_select_{theme}",
    )
    sel_stock = stocks[sel_idx]
    sel_code = sel_stock["code"]

    with st.expander(f"{sel_stock['name']} 일봉 차트 (참고용)", expanded=False):
        chart_df = market_data.get_daily(sel_code)
        if chart_df is None or chart_df.empty:
            st.info("차트 데이터를 불러오지 못했습니다.")
        else:
            st.line_chart(chart_df["Close"].tail(60), height=220)
            st.caption("종가 기준 최근 60거래일. 참고용이며 점수·판정에는 반영되지 않습니다.")

    # 경보 계산
    w_result = playbook.max_warning(sel_code)
    lb_result = playbook.leader_break(sel_code)

    # 선택 종목 요약 정보 (판단 참고용)
    ic1, ic2, ic3, ic4 = st.columns(4)
    ic1.metric("현재가", f"{sel_stock['price']:,}원" if sel_stock.get("price") else "—")
    _chg = sel_stock.get("change_pct")
    ic2.metric("오늘 등락률", f"{_chg:+.2f}%" if _chg is not None else "—")
    _tv = sel_stock.get("turnover_mil")
    ic3.metric("오늘 거래대금", f"{_tv / 100:,.0f}억" if _tv else "—")
    _dp = lb_result.get("drop_pct") if lb_result.get("ok") else None
    ic4.metric("최근 20일 고점 대비", f"{_dp:+.1f}%" if _dp is not None else "—")

    alerts: list[str] = []
    if w_result.get("ok") and w_result.get("warning"):
        alerts.append(
            f"막차 경보 — 최근 20거래일 내 일간 {w_result.get('max_gain_pct', 0):+.1f}% 급등 이력"
            f" ({w_result.get('spike_days')}일)"
        )
    if lb_result.get("ok") and lb_result.get("broken"):
        alerts.append(f"대장 꺾임 경보 — 최근 고점 대비 {lb_result.get('drop_pct', 0):+.1f}%")
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

    # ── 2d. 셋업 + 진입가/손절가/수량 ──────────────────────────────────────
    st.markdown("**셋업 및 진입 계획**")
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

    # 3R 게이지 (playbook_journal 미청산 기준)
    open_pos = playbook.get_open_positions()
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
                alert_state_str = ", ".join(["막차" if "막차" in a else "꺾임" if "꺾임" in a else "추격" for a in alerts]) if alerts else None
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


def _render_interest_scoreboard_ref() -> None:
    with st.expander("관심점수판 · 참고용 (동결 중)", expanded=False):
        st.caption(
            "30건 통계 후 조건별 재평가 예정 — 지금은 감으로 건드리지 않습니다. "
            "기존 관심 점수표는 자비스1(사이드바 'app' 페이지) 한국장 판단 탭에서 그대로 볼 수 있습니다."
        )


# ── 섹션 4: 테마판 요약 ──────────────────────────────────────────────────────


def _render_qualified_slot() -> None:
    """적격 대장 별도 난 — 52주 신고가 근접 게이트를 통과한 종목은 희소하고
    중요하므로 테마판 위에 항상 표시한다. 신호 확인에서 발견될 때마다 축적."""
    st.markdown("**⭐ 적격 대장 현황** — 52주 신고가 근접 게이트 통과 종목")
    store = st.session_state.get("j2_qualified") or {}
    rows = []
    for theme_nm, info in store.items():
        for c in info.get("stocks", []):
            rows.append((theme_nm, c, info.get("at", "")))
    if not rows:
        st.info("아직 없음 — 테마 신호 확인에서 적격 대장이 발견되면 여기에 표시됩니다.")
        return
    cols = st.columns(min(len(rows), 4))
    for i, (theme_nm, c, at_time) in enumerate(rows[:4]):
        with cols[i]:
            pct_h = c.get("pct_from_52w_high")
            pct_txt = f"{pct_h:+.1f}%" if pct_h is not None else "—"
            st.success(
                f"**{c['name']}** `{c['code']}`  \n"
                f"{theme_nm} · 52주고가대비 {pct_txt}  \n"
                f"확인 {at_time}"
            )
    if len(rows) > 4:
        st.caption(f"외 {len(rows) - 4}건")


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


def _render_journal() -> None:
    st.subheader("판단 기록")
    records = playbook.get_journal_recent(30)
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


def _render_open_risk() -> None:
    st.subheader("오픈 리스크")
    open_pos = playbook.get_open_positions()
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


def _render_ignore_log() -> None:
    st.subheader("무시 로그 (경보 + 필터 통합)")
    records = playbook.get_journal_recent(30)

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


def _render_tag_scorecard() -> None:
    st.markdown("**태그별 기대값 채점표**")
    records = playbook.get_journal_recent(30)
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

    with tab_kr:
        # 초기 화면: 클릭 없이 시장상태 + 적격대장 + 테마판이 바로 보이게 배치
        _render_market_state()
        st.divider()
        _render_qualified_slot()
        st.divider()
        _render_theme_panel()
        st.divider()
        _render_playbook()
        st.divider()
        _render_crash_log()
        _render_interest_scoreboard_ref()

    with tab_action:
        _render_open_risk()
        st.divider()
        _render_ignore_log()

    with tab_stats:
        _render_tag_scorecard()

    with tab_journal:
        _render_journal()

    with tab_settings:
        with st.expander("플레이북 설정 (playbook_config)", expanded=True):
            _render_settings()


main()

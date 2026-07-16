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
    [data-testid="stSidebarNav"] a,
    [data-testid="stSidebarNav"] a * {
        font-size: 1.8rem !important;
        font-weight: 800 !important;
        color: #ffb020 !important;
        padding: 0.7rem 1rem !important;
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


# ── 섹션 1: 시장상태 스트립 ───────────────────────────────────────────────────


def _render_market_state() -> None:
    cfg = _cfg()
    warn_days = int(cfg.get("volatile_days_warn", 12))

    ms = st.session_state.get("j2_market_state")
    if ms is None:
        with st.spinner("시장 상태 조회 중…"):
            ms = playbook.market_state()
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
    for k in ["j2_signals", "j2_leader", "j2_stocks"]:
        st.session_state.pop(k, None)


def _render_playbook() -> None:
    cfg = _cfg()
    st.subheader("순환매 플레이북")
    st.caption("매수신호·점수·목표가는 표시하지 않습니다. 기록과 확인 도구입니다.")

    # ── 2a. 테마 선택 + 신호 확인 ──────────────────────────────────────────────
    prev_theme = st.session_state.get("j2_prev_theme", "")
    theme = st.selectbox("테마 선택", _THEME_NAMES, key="j2_theme_select")
    if theme != prev_theme:
        _clear_theme_cache()
        st.session_state["j2_prev_theme"] = theme

    if st.button("신호 확인 (네트워크 조회)", key="j2_signal_btn"):
        with st.spinner("네이버 테마 조회 중…"):
            sigs = playbook.theme_signals(theme)
            stocks_result = theme_detail.fetch_theme_stocks(theme)
            leader_result = playbook.find_leader(theme)
            age = playbook.theme_age(theme)

            st.session_state["j2_signals"] = sigs
            st.session_state["j2_stocks"] = stocks_result
            st.session_state["j2_leader"] = leader_result
            st.session_state["j2_age"] = age

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
        (st.success if val_ok else st.warning)(
            f"거래대금 급증 {'✔' if val_ok else '✗'}  ({mult:.1f}x)" if mult else f"거래대금 급증 ✗  (데이터 없음)"
        )
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

    st.divider()

    # ── 2b. 대장 확인 카드 ───────────────────────────────────────────────────
    st.markdown("**대장 확인** · 매수 대상 아님 — 확인용")
    if leader_result and leader_result.get("ok"):
        candidates = leader_result.get("candidates", [])
        near_ok = any(c.get("near_high") for c in candidates)
        if not near_ok or not candidates:
            st.info("적격 대장 없음 — 52주 고가 근접 10% 게이트 미충족")
        else:
            cols = st.columns(min(len(candidates), 3))
            for i, c in enumerate(candidates[:3]):
                with cols[i]:
                    label = "52주고가 근접" if c.get("near_high") else "근접 미달"
                    pct_h = c.get("pct_from_52w_high")
                    mult_c = c.get("turnover_mult")
                    chg = c.get("change_pct")
                    st.markdown(
                        f"**{c['name']}** `{c['code']}`  \n"
                        f"52주고가대비: {pct_h:+.1f}%  \n"
                        f"거래대금배수: {mult_c:.2f}x  \n"
                        f"등락률: {chg:+.2f}%"
                        if pct_h is not None and mult_c is not None and chg is not None
                        else f"**{c['name']}** `{c['code']}`  \n데이터 부족"
                    )
                    if c.get("near_high"):
                        st.success(label)
                    else:
                        st.warning(label)
    else:
        err = leader_result.get("error") if leader_result else "—"
        st.warning(f"대장 조회 실패: {err}")

    st.divider()

    # ── 2c. 매수 대상 선택 ──────────────────────────────────────────────────
    st.markdown("**매수 대상 선택** (반자동 — 최종 선택은 사용자)")
    stocks = (stocks_result or {}).get("stocks", [])
    if not stocks:
        st.info("구성종목 데이터가 없습니다.")
        return

    def _pct_label(v):
        return f"{v:+.2f}%" if v is not None else "N/A"

    stock_opts = [f"{s['name']} ({s['code']}) {_pct_label(s.get('change_pct'))}" for s in stocks]
    sel_idx = st.selectbox(
        "종목 선택", range(len(stock_opts)),
        format_func=lambda i: stock_opts[i],
        key="j2_stock_select",
    )
    sel_stock = stocks[sel_idx]
    sel_code = sel_stock["code"]

    # 경보 계산
    w_result = playbook.max_warning(sel_code)
    lb_result = playbook.leader_break(sel_code)

    alerts: list[str] = []
    if w_result.get("ok") and w_result.get("warning"):
        alerts.append(f"급등 경보 ({w_result.get('max_gain_pct', 0):+.1f}%, {w_result.get('spike_days')}일)")
    if lb_result.get("ok") and lb_result.get("broken"):
        alerts.append(f"대장 붕괴 경보 ({lb_result.get('drop_pct', 0):+.1f}%)")
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
                alert_state_str = ", ".join(["급등" if "급등" in a else "붕괴" if "붕괴" in a else "추격" for a in alerts]) if alerts else None
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


# ── 섹션 4: 테마판 요약 ──────────────────────────────────────────────────────


def _render_theme_panel() -> None:
    st.subheader("테마판 요약")
    st.caption("아래 버튼을 누르면 네이버에서 테마 등락률을 새로 가져옵니다.")

    if st.button("테마판 새로고침", key="j2_theme_panel_refresh"):
        with st.spinner("20개 테마 조회 중 (병렬)…"):
            snap = fetch_kr_theme_snapshot()
            st.session_state["j2_theme_snap"] = snap
            # theme_state_log 축적
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
        st.rerun()

    snap = st.session_state.get("j2_theme_snap")
    if snap is None:
        st.info("**테마판 새로고침** 버튼을 눌러 데이터를 가져오세요.")
        return

    if not snap.get("ok"):
        st.warning(f"테마 조회 실패: {snap.get('error')}")
        return

    rows = []
    for name, info in snap.get("themes", {}).items():
        if not info.get("ok"):
            rows.append({"테마": name, "등락률": "—", "판정": "조회실패", "연속강세일": "—"})
            continue
        age = theme_history.get_theme_elapsed_strong_days(name)
        rows.append({
            "테마": name,
            "등락률": f"{info['change_pct']:+.2f}%",
            "판정": info.get("verdict", "—"),
            "연속강세일": f"D+{age}" if age else "—",
        })

    import pandas as pd
    df_snap = pd.DataFrame(rows)
    st.dataframe(df_snap, use_container_width=True, hide_index=True)

    checked_at = snap.get("checked_at")
    if checked_at:
        st.caption(f"조회 시각: {checked_at}")


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
            if age_days is not None:
                st.caption(f"테마나이 D+{age_days}")
            if tags:
                st.caption(f"태그: {tags}")
            alert = r.get("alert_state")
            if alert:
                reason = r.get("alert_ignore_reason", "")
                st.caption(f"경보: {alert} / 무시사유: {reason or '없음'}")


# ── 섹션 6: 설정 ─────────────────────────────────────────────────────────────


_CFG_LABELS = {
    "near_high_pct":       ("고점 근접 기준 (%)", "52주 최고가 대비 이 % 이내면 '근접'으로 판단"),
    "value_mult":          ("거래대금 급증 배수", "당일 거래대금이 20일 평균의 이 배 이상이면 급증"),
    "min_value_eok":       ("최소 거래대금 (억원)", "이 금액 미만 종목은 대장 후보 제외 (현재 미구현)"),
    "max_spike_pct":       ("급등 경보 기준 (%)", "최근 20일 내 이 % 이상 단일 급등 시 경보"),
    "entry_max_age":       ("추격 주의 기준 (거래일)", "테마 연속강세 이 일 초과 시 추격 주의"),
    "leader_break_pct":    ("대장 붕괴 기준 (%)", "최근 고점 대비 이 % 이상 하락 시 붕괴 경보"),
    "rank_limit":          ("대장 후보 최대 수", "find_leader 반환 최대 개수"),
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
            for k, v in updated.items():
                conn.execute(
                    "INSERT OR REPLACE INTO playbook_config (key, value) VALUES (?, ?)",
                    (k, v),
                )
            conn.commit()
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

    # 섹션 1
    _render_market_state()
    st.divider()

    # 섹션 2
    _render_playbook()
    st.divider()

    # 섹션 3 (급락일만 표시)
    _render_crash_log()

    # 섹션 4
    _render_theme_panel()
    st.divider()

    # 섹션 5
    _render_journal()
    st.divider()

    # 섹션 6
    with st.expander("설정 (playbook_config)", expanded=False):
        _render_settings()


main()

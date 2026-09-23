"""Independent J8 page. Only completed-session signals; no automatic trading."""
from __future__ import annotations
import json
from pathlib import Path
import streamlit as st
import auth
import login_prism

st.set_page_config(page_title="JARVIS 8 · 미국주식 연구실", page_icon="◈", layout="wide")
auth.sync_auth()
if login_prism.wants_guest(st):
    auth.login_as_guest()
if not st.session_state.get("authenticated"):
    st.title("JARVIS 8 · 미국주식 연구실")
    st.caption("테마의 힘, 매수 조건, 손실 위험을 따로 확인합니다.")
    try:
        password = st.secrets.get("APP_PASSWORD")
    except Exception:
        password = None
    with st.form("j8_login"):
        entered = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            if password and entered == password:
                auth.login_as_owner()
                st.rerun()
            st.error("비밀번호를 확인하세요.")
    if st.button("게스트로 둘러보기"):
        auth.login_as_guest()
        st.rerun()
    st.stop()

import page_access
if getattr(page_access, "MODULE_REVISION", 0) < 2026092201:
    import importlib
    page_access = importlib.reload(page_access)
page_access.guard(st, "자비스8")
import jarvis8_data as data
import jarvis8_ui as ui

st.html(ui.STYLE)
st.html(ui.TRANSLATION_GUARD, unsafe_allow_javascript=True)
st.caption("JARVIS 8  /  미국주식 · 마감 기준")
st.title("오늘 살펴볼 미국주식")
st.caption("① 오늘의 판단  →  ② 종목과 선정 근거  →  ③ 매수 전 위험 확인")
view = st.radio("화면", ["오늘의 판단", "모멘텀 스윙", "21개 테마", "상승장 눌림", "급락 후 회복", "기존·실험2", "다른 방법", "위험·비용", "검증 근거"], horizontal=True, label_visibility="collapsed", key="j8_view")


def go_to(destination):
    st.session_state["j8_view"] = destination


def forward_evidence():
    import pandas as pd
    path = Path(__file__).resolve().parents[1]/"data/jarvis8/forward_study.json"
    if not path.exists():
        st.info("자비스8 자체 규칙의 과거 표본 검사는 계산 중입니다. 아래 기존 연구와 구분해 확인하세요.")
        return
    result = json.loads(path.read_text(encoding="utf-8"))
    meta = result["metadata"]
    st.subheader("자비스8 자체 규칙 · 고정 간격 표본 검사")
    st.caption(f"{meta['first_signal']}~{meta['last_signal']} 신호 · 규칙 {meta['engine_version']} · 과거 탐색 자료")
    st.write("21거래일마다 그날까지의 자료로 후보를 고르고 다음 날 시가에 매수했습니다. 상위 최대 5종목에 각각 계좌의 10%를 배정하고 나머지는 현금으로 뒀습니다. 매일 나타나는 신호를 모두 검사한 결과는 아닙니다.")
    hold = st.selectbox("자비스8 검사 보유기간 (거래일)", [1,3,5,10,20], index=4, key="j8_study_hold")
    cost = st.selectbox("왕복 비용 가정 (%)", [0.,.2,.5,1.], index=2, key="j8_study_cost")
    table = pd.DataFrame(result["summary"])
    table = table[(table.hold==hold)&(table.cost_pct==cost)].copy()
    labels = {"rise":"상승장 눌림", "crash_baseline":"급락 · 기본 순위", "crash_recovery60":"급락 · 회복60 비교",
              "reversal":"동료 대비 하락 실험", "momentum":"중기 모멘텀 실험"}
    table["method"] = table.method.map(labels)
    columns = {"method":"방법", "active_cycles":"후보가 있던 관측 수", "stock_observations":"종목 관측 수",
               "positive_net_basket_pct":"비용 후 수익 난 관측 %", "mean_basket_gross_pct":"종목 묶음 평균 수익·비용 전 %",
               "cagr_pct":"가상 계좌 연복리 %", "max_daily_close_drawdown_pct":"가상 계좌 최대 하락 %"}
    st.dataframe(table[list(columns)].rename(columns=columns).round(2), hide_index=True, width="stretch")
    st.warning("‘수익 난 관측 비율’은 선택한 종목 묶음의 결과이며 개별 주식 승률이 아닙니다. 현재 살아 있는 종목 명부와 이미 본 과거를 사용했습니다. 미래 성과 검증이나 실제 계좌 기록이 아닙니다.")
    st.caption("연복리·최대 하락은 최대 50%만 투자한 가상 계좌입니다. 최대 하락은 일별 종가 기준으로 장중 손실은 포함하지 않습니다. 모멘텀의 1~20일 결과는 원 연구의 수개월 보유와 다릅니다.")
    if result.get("checks") and cost == .5:
        with st.expander("큰 이익 몇 번에 얼마나 의존했나"):
            stress = pd.DataFrame(result["checks"]["sensitivity"])
            stress = stress[stress.hold==hold].copy()
            stress["method"] = stress.method.map(labels)
            st.dataframe(stress[["method","original_cagr_pct","without_best_three_cagr_pct"]].rename(columns={
                "method":"방법", "original_cagr_pct":"원 가상 계좌 연복리 %", "without_best_three_cagr_pct":"최고 이익 3구간 제거 시 %"}).round(2), hide_index=True, width="stretch")
            st.caption("가장 잘 번 3개 구간을 사후에 지운 민감도 검사입니다. 미리 그 구간을 알 수 없으므로 실제 매매방법으로 해석하면 안 됩니다.")
    if meta["invalid_forward_cycles"] or meta["invalid_signal_dates"]:
        st.error("일부 입력·보유가격이 누락돼 해당 계좌 성과를 확정할 수 없습니다. 빈 성과를 0%로 읽지 마세요.")
    st.download_button("자비스8 표본 검사 결과 JSON", path.read_bytes(), "jarvis8_forward_study.json", "application/json")


def evidence():
    import pandas as pd
    forward_evidence()
    st.subheader("점수가 높다고 승률이 높은 것은 아닙니다")
    st.write("아래는 실제 저장된 일봉으로 재계산한 탐색 결과입니다. 현재 살아 있는 종목 명부를 과거에 적용했으며, 미래 실전 성적이나 계좌 수익률을 뜻하지 않습니다.")
    st.dataframe(pd.DataFrame([
        ["기존 상승장 통과 후보", "3일", 1138, "54.39%", "+0.55%", "+0.05%"],
        ["기존 상승장 통과 후보", "20일", 712, "56.60%", "+4.09%", "+3.59%"],
        ["앱 기준일 급락 · 기존 70점 이상", "20일", 778, "59.00%", "+4.51%", "+4.01%"],
        ["앱 기준일 급락 · 변동성 제외 42/60 이상", "20일", 435, "70.34%", "+7.73%", "+7.23%"],
    ], columns=["검사 대상", "보유", "관측 수", "상승 비율", "평균 수익", "왕복 0.5% 차감 예시"]), hide_index=True, width="stretch")
    st.warning("마지막 두 줄은 종목·진입일이 다른 집단입니다. 70.34%를 자비스8의 예상 승률로 사용하면 안 됩니다. 자비스8은 자료 품질 제외·기준일 이력 조건도 추가했으므로 이 표와 완전히 같은 전략이 아닙니다.")
    st.subheader("같은 날짜·같은 수로 다시 고르면 결과가 달랐습니다")
    st.dataframe(pd.DataFrame([
        ["상위 3종목 · 3일", 1435, .7505, .4766],
        ["상위 5종목 · 3일", 1435, .6647, .4428],
        ["상위 3종목 · 20일", 1418, 4.5667, 2.6530],
        ["상위 5종목 · 20일", 1418, 4.8282, 3.2268],
    ], columns=["공통 조건", "비교 날짜 수", "기존 점수 평균 수익 %", "회복60 평균 수익 %"]), hide_index=True, width="stretch")
    st.write("2026-09-14 추가 검사에서는 회복60 순위가 더 낮은 수익을 냈습니다. 따라서 기본 순서는 기존 점수를 유지합니다. 이 표도 현재 명부·상관된 날짜·동률의 티커순 처리라는 한계가 있으며 미래 성과를 보장하지 않습니다.")
    st.write("진입은 신호 다음 거래일 시가, 청산은 보유기간 마지막 종가입니다. 동일 종목의 겹치는 보유는 제외했지만, 종목 사이 중복 위험·계좌 자금 한도는 반영하지 않은 진단입니다. 1·3일 결과도 일봉 기준이며 장중 단타 검증이 아닙니다.")
    st.markdown("**확인한 것**: 앱은 미래 저점을 보지 않음 · 다섯 배점의 구조 · 실제 앱 기준일 재생 · 테마 변화점수 제거 · 테마 크기 보정 · 대장주 80점 비교.\n\n**남은 것**: 당시 종목 명부·상장폐지 복원, 독립 시세원 전체 대조, 분봉 체결, 새 규칙의 미사용 기간 검증, 자금 한도와 비용을 포함한 계좌 성과.")
    st.subheader("다른 매매방법의 근거와 한계")
    st.markdown("- **중기 모멘텀**: 3~12개월 강세 지속 연구가 있습니다. 1~3일 수익을 보장하는 근거는 아닙니다. [원 논문](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x)\n- **단기 되돌림**: 유동성과 회전율에 따라 거래비용 후 결과가 달라집니다. [비용 연구](https://repub.eur.nl/pub/25718/AnotherLook_2011.pdf) · [다른 실거래 비용 연구](https://www.aqr.com/Insights/Research/Working-Paper/Trading-Costs-of-Asset-Pricing-Anomalies)\n- **추세 추종**: 여러 자산의 장기 연구 근거가 있습니다. 개별 미국주식 눌림목 규칙의 검증을 대신하지 않습니다. [원 연구 자료](https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Original-Paper-Data)")
    st.info("우선 제안: 점수 최적화보다 비용·손실 폭·시장 상태를 먼저 관리하고, 동결한 규칙을 새 데이터로 관찰합니다. 승률과 수익률이 실제로 개선됐는지는 아직 확정할 수 없습니다.")
    root = Path(__file__).resolve().parents[1]
    for path, title in [("docs/JARVIS8_DESIGN_AND_VALIDATION.md", "자비스8 설계·검증 보고서"), ("docs/JARVIS3_ALTERNATIVE_STRATEGIES_RESEARCH_20260909.md", "대안 매매방법 심층 자료")]:
        f = root/path
        if f.exists():
            st.download_button(title, f.read_text(encoding="utf-8"), file_name=f.name, mime="text/markdown")


def stock_table(rows, kind):
    import pandas as pd
    from us_swing_selector import plain_state
    flat = []
    for r in rows:
        m = r["metrics"]
        item = {"종목": r["ticker"], "테마": " · ".join(r.get("themes", [])),
                "조정종가 $": m.get("current"), "52주 고점 대비 %": m.get("from_high_pct"),
                "ATR %": m.get("atr_pct"), "20일 평균 거래대금 $": m.get("avg_dollar_volume")}
        if kind == "crash":
            item.update({"회복 조건 /60": r["score"], "기존 점수 /100": r["baseline_score"],
                         "기준일 낙폭 %": r["reference_drop"], "기준일 이후 %": r["since_reference"], "현재 상태": r["state"]})
        elif kind == "rise":
            item.update({"핵심 /70": r.get("core_score"), "보조 /30": r.get("support_score"),
                         "기존 합계 /100": r.get("score"), "사유": " · ".join(plain_state(x) for x in r.get("failed_gates", [])) or "진입 조건 통과"})
        elif kind == "reversal":
            item.update({"20일 수익 %": m["ret20"], "동료 평균 %": r["peer_return"],
                         "동료 대비 %p": r["residual"], "비교 종목 수": r["peers"]})
        else:
            item.update({"최근 1개월 제외 수익 %": r["momentum"], "변동성 대비 모멘텀": r["risk_adjusted"]})
        flat.append(item)
    if not flat:
        st.info("현재 조건에 맞는 후보가 없습니다. 빈 목록도 정상적인 결과입니다.")
        return
    table = pd.DataFrame(flat)
    main = {"crash": ["기존 점수 /100", "회복 조건 /60"],
            "rise": ["핵심 /70", "보조 /30", "기존 합계 /100"],
            "reversal": ["동료 대비 %p", "20일 수익 %"],
            "momentum": ["변동성 대비 모멘텀", "최근 1개월 제외 수익 %"]}[kind]
    columns = ["종목"] + main + ["조정종가 $", "ATR %"]
    full = st.checkbox("전체 지표 보기", key="j8_full_"+kind)
    st.dataframe((table if full else table[columns]).round(2), hide_index=True, width="stretch")
    st.download_button("현재 후보 CSV 저장", table.to_csv(index=False).encode("utf-8-sig"), f"jarvis8_{kind}.csv", "text/csv", key="csv_"+kind)


def details(bundle, rows, kind, blocked=False):
    import pandas as pd
    if not rows:
        return
    st.subheader("종목별 근거와 차트")
    ticker = st.selectbox("종목 자세히 보기", list(dict.fromkeys(r["ticker"] for r in rows)),
                          format_func=lambda s: f"{ui.stock_name(s)} · {s}")
    r = next(r for r in rows if r["ticker"] == ticker)
    ui.render_candidates(st, bundle, [r], kind, blocked, limit=1)
    prices = bundle["charts"].get(ticker, {})
    if prices:
        chart = pd.Series(prices, name="조정종가")
        chart.index = pd.to_datetime(chart.index)
        st.line_chart(chart)
    parts = r.get("score_parts") if kind == "rise" else r.get("parts")
    if kind == "crash" and parts:
        parts = [("변동성", r["baseline_score"]-r["score"], 40, "크게 움직이는 종목에 가산 · 더 큰 손실 위험도 포함")] + list(parts)
    if parts:
        with st.expander("점수가 나온 과정 · 항목별 배점"):
            st.dataframe(pd.DataFrame(parts, columns=["항목", "점수", "만점", "설명"]), hide_index=True, width="stretch")
            st.caption("배점은 조건을 비교하는 기준입니다. 해당 종목의 예상 승률이나 예상 수익률이 아닙니다.")
    st.button("이 종목의 투자금·손실 계산", key="j8_risk_from_detail", on_click=prepare_risk, args=(ticker,))
    st.caption("일봉 차트는 조정 가격입니다. 실제 주문 전 현재 호가·갭·실적 발표·기업행사를 확인해야 합니다.")


def prepare_risk(ticker):
    st.session_state["j8_risk_selected"] = [ticker]
    go_to("위험·비용")


def momentum_candidates(bundle, blocked, preview=False):
    """The independent raw-return 12-1 strategy; never show the old risk-adjusted list here."""
    from html import escape
    import pandas as pd
    result = bundle.get("independent_momentum")
    if not result or not result.get("ok"):
        st.warning("독립 모멘텀 계산을 확인할 수 없습니다. 현재 후보를 표시하지 않습니다.")
        return
    if not preview:
        st.subheader("지난 1년 강세가 이어지는 종목 · 모멘텀 스윙")
        st.write("약 1년 전부터 **최근 한 달 전까지** 많이 오른 종목을 순서대로 봅니다. "
                 "최근 한 달의 급등은 순위에 더하지 않습니다. QQQ와 해당 종목이 모두 200일 평균 위이고 "
                 "거래 규모 조건을 통과해야 합니다.")
        st.caption("자비스3 배점과 별개입니다. 이 화면의 순위는 상승률 자체이며 변동성으로 나누지 않습니다.")
    if blocked:
        st.error("마감 자료가 오래되거나 갱신에 실패했습니다. 아래 후보는 과거 관찰용이며 현재 매수 판단을 보류합니다.")
    elif not result["market_ok"]:
        st.warning("QQQ가 200일 평균 아래입니다. 이 전략의 현재 통과 종목은 없습니다.")
    else:
        st.caption(f"QQQ ${result['qqq_close']:,.2f} · 200일 평균 ${result['qqq_sma200']:,.2f} 통과 · "
                   f"전체 {result['total']}종목 중 조건 통과 {result['eligible_count']}종목")
    rows = result.get("top5", [])
    if not rows:
        st.info("조건을 통과한 종목이 없습니다. 빈 목록도 정상적인 판단입니다.")
        return
    if preview:
        rows = rows[:2]
    cards = []
    for rank, row in enumerate(rows, 1):
        ticker = escape(row["ticker"])
        name = escape(ui.stock_name(row["ticker"]))
        cards.append(f'''<article class="j8-stock {'muted' if blocked else 'mint'}" translate="no">
          <div class="j8-card-top"><span class="j8-badge">{'과거 관찰' if blocked else '모멘텀 조건 통과'}</span><span class="j8-rank">{rank}위</span></div>
          <div class="j8-stock-title"><strong>{name}</strong><span>{ticker}</span></div>
          <div class="j8-price">{ui.number(row['momentum_pct'], signed=True)}% <span>약 1년 전 → 최근 한 달 전 상승률 · 순위 기준</span></div>
          <div class="j8-label">선정 근거</div>
          <ul><li>{escape(row['date_252'])} ${ui.number(row['c_252'], 2)} → {escape(row['date_21'])} ${ui.number(row['c_21'], 2)}</li>
          <li>최근 마감 ${ui.number(row['price'], 2)} · 200일 평균 ${ui.number(row['sma200'], 2)} 위</li>
          <li>20일 평균 거래 규모 대용치 ${ui.number(row['turnover_proxy'], 0)}</li></ul>
          <div class="j8-caution"><b>주의</b> 최근 한 달 수익 {ui.number(row['recent_month_pct'], signed=True)}%는 순위에서 제외했습니다. 현재가가 이미 너무 올랐는지 별도 확인하세요.</div>
          <div class="j8-next"><b>다음 확인</b> 실제 현재 호가·실적 발표·손실 가능 금액을 확인하세요.</div>
        </article>''')
    st.html('<div class="j8-card-grid" translate="no">' + ''.join(cards) + '</div>')
    if not preview:
        ticker = st.selectbox("후보 차트 자세히 보기", [r["ticker"] for r in rows],
                              format_func=lambda s: f"{ui.stock_name(s)} · {s}", key="j8_independent_ticker")
        prices = bundle.get("charts", {}).get(ticker, {})
        if prices:
            chart = pd.Series(prices, name="조정종가")
            chart.index = pd.to_datetime(chart.index)
            st.line_chart(chart)
        st.caption("차트는 조정 일봉입니다. 오늘 목록은 매일 계산한 관찰 결과이며, 아래 21거래일 간격 과거 연구의 매일 매수 성적이 아닙니다.")
        with st.expander("전체 통과 종목과 제외 사유"):
            st.dataframe(pd.DataFrame([{"종목": r["ticker"], "12-1 상승률 %": r["momentum_pct"],
                                        "최근 한 달 %": r["recent_month_pct"]} for r in result["rows"]]).round(2),
                         hide_index=True, width="stretch")
            st.json(result["excluded"])


def state_token(state):
    return (id(state["value"]), state["error"], state.get("stale", False), state["pending"])


@st.fragment(run_every="3s")
def poll_changes():
    # Poll only cache state. Tables and charts rerender only when data/state changes.
    state = data.CACHE.request()
    if state_token(state) != st.session_state.get("j8_rendered_state"):
        st.rerun()


@st.fragment(run_every="3s")
def poll_comparison(bundle):
    import jarvis8_lab as lab
    state=lab.request(bundle)
    token=(id(state.get('value')),state.get('pending'),state.get('error'))
    if token != st.session_state.get('j8_lab_rendered'):
        st.rerun()


@st.fragment(run_every="5s")
def quote_panel():
    import pandas as pd
    from jarvis8_engine import THEMES
    state = data.QUOTE_CACHE.request(data.load_market_quotes)
    if state["pending"]:
        st.caption("장중 참고 ETF 시세 확인 중… 마감 점수는 그대로입니다.")
    if state["error"]:
        st.warning("ETF 시세 갱신 실패 · 마지막 확인 시각을 보세요.")
    b = state["value"]
    if not b:
        return
    rows=[]
    for t in THEMES:
        q=b["quotes"].get(t["etf"], {})
        rows.append({"테마":t["name"], "참고 ETF":t["etf"], "가격 $":q.get("price"),
                     "직전장 마지막 5분봉 대비 %":q.get("change"), "미국 시각":q.get("time"),
                     "자료 상태":"지연·과거·누락" if not q or q.get("stale") or state["stale"] else "최근 확인"})
    st.dataframe(pd.DataFrame(rows).round(2), hide_index=True, width="stretch")
    st.caption(f"{b['phase']} · 공급처 5분봉 참고값이며 체결 호가가 아닙니다. ETF와 테마 구성종목 평균은 다릅니다. 마감 순위에 합치지 않습니다.")


def live_view():
    import pandas as pd
    import us_market_calendar as calendar
    refresh = st.button("자료 새로 확인", help="중복 다운로드를 막기 위해 요청 간 최소 60초 간격을 둡니다.")
    state = data.CACHE.request(refresh=refresh)
    st.session_state["j8_rendered_state"] = state_token(state)
    b = state["value"]
    if state["pending"]:
        st.info("시세와 조건을 백그라운드에서 확인하고 있습니다. 다른 메뉴를 먼저 볼 수 있습니다.")
    if state["error"]:
        st.warning("갱신 실패: " + state["error"] + " · 마지막 성공 자료가 있으면 아래에 표시합니다.")
    if not b:
        if view == "모멘텀 스윙":
            st.info("현재 후보를 불러오는 중입니다. 아래 과거 연구 결과는 별도로 볼 수 있습니다.")
            import jarvis8_momentum_evidence_ui
            jarvis8_momentum_evidence_ui.render(st)
        return
    outdated = b["as_of"] != calendar.previous_session_date().isoformat()
    blocked = outdated or state["stale"]
    st.caption(f"신호 기준 {b['as_of']} 미국장 종가 · {b.get('source', '검증용 자료')} · 규칙 {b['version']}")
    if blocked:
        st.error("자료가 최신 상태가 아닙니다. 아래는 과거 관찰 자료이며 현재 진입 판단을 보류합니다.")
    if b.get("observation_error"):
        st.warning(b["observation_error"] + " · 오늘 결과를 저장했다고 간주하지 마세요.")
    rows = []
    kind = "rise"
    if view == "기존·실험2":
        import jarvis8_lab_ui
        comparison=jarvis8_lab_ui.render(st,b,blocked)
        st.session_state['j8_lab_rendered']=(id(comparison.get('value')),comparison.get('pending'),comparison.get('error'))
        poll_comparison(b)
    elif view == "오늘의 판단":
        st.html(ui.overview_html(b, blocked))
        st.subheader("02 · 상승장 눌림 — 먼저 볼 종목")
        st.caption("신고가 뒤 잠시 내려온 강한 종목입니다. 필수 조건을 통과한 후보 중 점수순 상위 3개를 보여줍니다.")
        ui.render_candidates(st, b, b['rise']['primary_rows'], "rise", blocked)
        st.button(f"상승장 후보 {len(b['rise']['primary_rows'])}개 · 차트와 전체 근거 보기", on_click=go_to, args=("상승장 눌림",), type="primary", width="stretch")
        st.subheader("03 · 급락 후 회복 — 매수보다 관찰 먼저")
        st.caption("급락 기준일에 고점에서 20~50% 내려와 있던 종목입니다. 지금 바로 사라는 뜻이 아닙니다.")
        ui.render_candidates(st, b, b['crash'], "crash", blocked)
        st.button(f"급락 후보 {len(b['crash'])}개 · 회복 근거 보기", on_click=go_to, args=("급락 후 회복",), width="stretch")
        st.subheader("04 · 모멘텀 스윙 — 독립 전략")
        st.caption("지난 1년 중 최근 한 달을 뺀 상승률로 고릅니다. 자비스3 배점과 별개이며, 과거 가상 계좌 성적은 별도 화면에서 비교합니다.")
        momentum_candidates(b, blocked, preview=True)
        st.button("모멘텀 후보와 실제 계산 근거 보기", on_click=go_to, args=("모멘텀 스윙",), width="stretch")
        st.info("매수 전 마지막 확인: 현재 가격과 차트 → 실적 발표·하락 원인 → 감당할 손실과 투자금. 뉴스와 실적 일정은 이 화면에서 자동 검증하지 않습니다.")
        st.button("05 · 투자금과 손실 계산하기", on_click=go_to, args=("위험·비용",), width="stretch")
        st.button("기존 배점과 실험2 · 실제 비교 결과 보기", on_click=go_to, args=("기존·실험2",), width="stretch")
        with st.expander("추천이라는 말의 의미 · 무엇까지 검증했나"):
            st.write("상승장 목록은 정해진 마감 조건을 통과한 ‘매수 검토 후보’입니다. 급락 목록은 기준일 낙폭에 해당하는 ‘관찰 후보’입니다. 점수는 후보 간 순서를 정하며, 그 종목의 성공 확률이 아닙니다.")
            st.write("자비스8 규칙으로 과거 121개 기준일을 실제 계산했습니다. 현재 종목 명부와 이미 본 자료를 사용한 표본 연구이며, 오늘 후보의 미래 수익을 입증하지는 않습니다. 보유기간·비용별 결과는 검증 근거에서 확인하세요.")
    elif view == "모멘텀 스윙":
        momentum_candidates(b, blocked)
        import jarvis8_momentum_evidence_ui
        jarvis8_momentum_evidence_ui.render(st)
    elif view == "21개 테마":
        st.subheader("어느 테마부터 살펴볼까요?")
        st.caption("상위 테마는 종목을 찾는 출발점입니다. 테마 1위가 곧 매수 신호는 아닙니다.")
        theme_cards = []
        from html import escape
        for rank, r in enumerate(b["themes"][:3], 1):
            tone = "j8-up" if r['ret60'] >= 0 else "j8-down"
            theme_cards.append(f'<article class="j8-theme"><span class="j8-eyebrow">{rank}위 · {ui.number(r["score"])}/90점</span><strong>{escape(r["name"])}</strong><p>3개월 실제 수익 <b class="{tone}">{ui.number(r["ret60"], signed=True)}%</b></p><p>SPY보다 {ui.number(r["strength_60"], signed=True)}%p · 강한 종목 {ui.number(r["strong_members"], 0)}%</p></article>')
        if theme_cards:
            st.html('<div class="j8-card-grid" translate="no">'+''.join(theme_cards)+'</div>')
        table = pd.DataFrame([{ "테마": r["name"], "순위 점수 /90": r["score"], "3개월 수익 %": r["ret60"],
            "6개월 수익 %": r["ret120"], "3개월 SPY 대비 %p": r["strength_60"], "6개월 SPY 대비 %p": r["strength_120"],
            "강한 구성종목 %": r["strong_members"], "자료 통과": f"{r['count']}/{r['total']}"} for r in b["themes"]])
        st.dataframe(table[["테마", "순위 점수 /90", "3개월 수익 %", "강한 구성종목 %"]].round(2), hide_index=True, width="stretch")
        with st.expander("21개 테마 전체 지표 · 배점 설명"):
            st.write("6개월 상대강도 35 + 3개월 상대강도 30 + 강한 종목 비율 25 = 90점. 중복된 변화 10점을 제거했습니다. 이 가중치가 최적이라는 검증은 없고, 90점은 승률이 아닙니다.")
            st.dataframe(table.round(2), hide_index=True, width="stretch")
        st.button("테마 순위 확인 후 · 실제 눌림 후보 보기", on_click=go_to, args=("상승장 눌림",))
        st.caption("현재 고정 명부의 구성종목 평균입니다. 테마 ETF 수익률이 아닙니다. 자료 80% 미만인 테마는 순위를 보류합니다. 작은 테마의 흔들림과 구성종목 중복은 남아 있습니다.")
        if st.checkbox("현재 ETF 움직임도 보기 · 마감 점수와 별도", value=False):
            quote_panel()
    elif view == "상승장 눌림":
        st.subheader("강한 종목이 쉬어갈 때 · 상승장 눌림")
        st.caption("시장 조건 → 종목 강도 → 신고가 후 눌림을 확인합니다. 아래 종목을 선택하면 선정 근거와 차트가 나옵니다.")
        if not b["rise"].get("ok"):
            st.warning(b["rise"].get("error", "시장 자료 부족"))
        mode = st.radio("목록", ["조건 통과", "미통과 관찰"], horizontal=True)
        rows = b["rise"]["primary_rows" if mode == "조건 통과" else "watch_rows"]
        # Use the consistently audited metrics, not the breakout anchor's distance as 52w high.
        rows = [dict(r, themes=r.get("themes") or [], metrics=b["metrics"].get(r["ticker"], r["metrics"])) for r in rows]
    elif view == "급락 후 회복":
        kind = "crash"
        st.subheader("크게 내린 종목 · 회복을 확인하며 관찰")
        st.caption("후보 선정 이유와 지금까지의 반등을 구분해 보여줍니다. 점수가 높아도 자동 매수 신호는 아닙니다.")
        with st.expander("왜 이 순서인가 · 배점 근거"):
            st.write("기존 순위는 변동성40 + 테마 추세30 + 동반 후보20 + 테마 6개월 강도10입니다. 회복 관련60점만으로 정렬한 안은 같은 날짜 비교에서 더 나은 결과를 내지 못해 기본 순위에 채택하지 않았습니다.")
        st.caption(f"기준일 {b['reference']['date'] or '없음'} · 기준일 종목 낙폭 -50% 이상, -20% 미만 · 그 뒤 오른 종목도 관찰 이력을 유지합니다.")
        rows = b["crash"]
        compare = st.checkbox("실험용: 회복60 순서와 비교", value=False)
        if compare:
            rows = sorted(rows, key=lambda r: (-r["score"], r["ticker"]))
            st.warning("검증에서 우위가 확인되지 않은 비교 순서입니다.")
    elif view == "다른 방법":
        alternative = st.radio("실험 방법", ["동료 대비 과도한 하락", "변동성 조정 모멘텀 · 이전 실험"], horizontal=True)
        if alternative == "동료 대비 과도한 하락":
            kind = "reversal"
            st.subheader("테마 동료보다 많이 하락한 종목 · 별도 실험")
            st.write("최근 20일 하락 종목 중 같은 테마의 다른 종목보다 더 하락한 순서입니다. 자기 자신을 빼고 겹치는 동료도 한 번만 셉니다. 평균 거래대금 2천만 달러 이상, 동료 4개 이상을 관찰합니다. 이 숫자들은 검증된 최적값이 아닙니다.")
            st.warning("정식 업종 분류 대신 자비스 테마를 사용한 대용 실험입니다. 악재 때문에 떨어진 종목은 계속 하락할 수 있습니다. 실적·뉴스 원인을 자동 확인하지 않으므로 매수 추천이 아닙니다.")
            rows = b["reversal"]
        else:
            kind = "momentum"
            st.subheader("변동성 조정 모멘텀 · 이전 실험")
            st.write("최근 약 1개월을 제외한 12개월 수익률을 연율 변동성으로 나누어 정렬합니다. 종목과 QQQ가 각각 200일 평균 위인 경우만 관찰합니다. 자비스8의 121개 기준일 표본 계산은 완료했지만, 새 자료에서의 성과는 아직 검증하지 못했습니다.")
            st.warning("‘모멘텀 스윙’ 화면의 원시 상승률 순위와 다른 전략입니다. 그 화면의 과거 수익률을 여기에 적용할 수 없습니다. 현재 두 전략의 대체 매수 신호로 사용하지 않습니다.")
            rows = b["momentum"]
    elif view == "위험·비용":
        from jarvis8_engine import unique_risk
        st.subheader("같은 종목은 한 번만, 손실은 합산")
        rows = [{"ticker": s, "metrics": m} for s,m in b["metrics"].items()]
        if "j8_risk_selected" in st.session_state:
            st.session_state["j8_risk_selected"] = [s for s in st.session_state["j8_risk_selected"] if s in b["metrics"]]
        selected = st.multiselect("검토할 종목", sorted(b["metrics"]), key="j8_risk_selected")
        equity = st.number_input("가용 투자금 (달러)", min_value=100., value=10000., step=1000.)
        risk = st.number_input("종목당 가정 손실 예산 (%)", min_value=.1, max_value=5., value=.5, step=.1)
        cap = st.number_input("종목당 최대 투자 비중 (%)", min_value=1., max_value=100., value=10., step=1.)
        multiple = st.number_input("ATR 거리 배수", min_value=.5, max_value=10., value=2., step=.5)
        portfolio = unique_risk(rows, selected, equity, risk, multiple, cap)
        if portfolio:
            st.dataframe(pd.DataFrame(portfolio).rename(columns={"ticker":"종목","shares":"수량 예시","notional":"투자금 $","weight":"비중 %","atr_distance":"ATR 거리 $","planned_risk":"가정 손실 $","themes":"겹치는 테마"}).round(2), hide_index=True, width="stretch")
            st.write(f"합산 투자금 **${sum(r['notional'] for r in portfolio):,.0f}**, ATR 거리까지의 합산 손실 **${sum(r['planned_risk'] for r in portfolio):,.0f}**.")
        st.caption("비중 10%·손실 0.5%·2 ATR은 조절 가능한 계산 예시이며 최적값이 아닙니다. ATR 거리는 검증된 손절선이 아니고 갭 하락 시 실제 손실이 더 커질 수 있습니다. 같은 테마의 여러 종목도 함께 하락할 수 있습니다.")
        days = st.selectbox("평가할 보유기간 (거래일)", [1,3,5,10,20], index=2)
        gross = st.number_input("가정하는 1회 매매 수익 (%)", value=1., step=.1)
        st.dataframe(pd.DataFrame({"보유 거래일":[days]*3,"왕복 비용 가정 %":[.2,.5,1.],"비용 차감 수익 %":[gross-.2,gross-.5,gross-1.]}), hide_index=True, width="stretch")
        st.caption("보유기간 선택은 계산 메모이며 새 백테스트를 실행하지 않습니다. 비용은 수수료·호가 차이·체결 미끄러짐의 민감도 예시입니다.")
        rows = []
    if rows:
        details(b, rows, kind, blocked)
        with st.expander(f"전체 후보 {len(rows)}개 비교 · 지표와 CSV"):
            stock_table(rows, kind)
    elif view in ("상승장 눌림", "급락 후 회복", "다른 방법"):
        ui.render_candidates(st, b, [], kind, blocked)
    with st.expander("자료 품질·관측 기록"):
        st.write(f"전체 계산과 조회 {b.get('load_seconds', 0):.2f}초 · 같은 자료는 30분 공유 · 현재 캐시 나이 {state['age_seconds']}초")
        st.json(b["excluded"])
        st.write("시세를 고쳐 끼우거나 누락 가격을 전날 가격으로 채우지 않습니다. 명부는 현재 고정 명부이므로 과거 전체 미국주식을 대표하지 않습니다.")
        st.caption("화면을 사용할 때 성공한 관측만 저장합니다. 앱을 열지 않은 날까지 자동 수집하는 기능은 아닙니다. 서버 재시작·배포로 로컬 기록이 사라질 수 있어 중요한 기록은 내려받으세요.")
        st.download_button("이번 관측 요약 JSON 저장", json.dumps({k:v for k,v in b.items() if k != "charts"}, ensure_ascii=False, default=str), f"jarvis8_{b['as_of']}.json", "application/json")
        if b.get("observation"):
            st.caption("원본 입력 보관: " + b["observation"])


if view == "검증 근거":
    evidence()
else:
    live_view()
    poll_changes()

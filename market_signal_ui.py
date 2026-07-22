"""시장 판단 화면의 데이터 수집과 렌더링.

자비스1·2·3 어디에도 속하지 않는 독립 화면(pages/0_시장판단.py)에서 쓴다.
app.py를 import하면 자비스1 앱 전체가 실행되므로, 필요한 조회 로직은 여기에 둔다.

카드는 종목을 고르는 물건이 아니다. 지금 시장이 어떤 상태이고 무엇이 앞서
움직이는지 읽어서, 사용자가 자비스1·2·3과 대조해 스스로 판단할 재료를 준다.
그래서 결론 문구에 매수·매도 지시를 넣지 않는다.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

import database
import kis_market_data
import kr_intraday_flow
import market_signal_common
import naver_market_data
import price_data
import us_market_signal_engine


_SEOUL_TZ = ZoneInfo("Asia/Seoul")


def _now_seoul():
    """기준시각은 항상 한국 시간이다.

    스트림릿 클라우드 서버는 UTC라서 datetime.now()를 쓰면 화면에 04:28처럼
    9시간 어긋난 시각이 표시된다(2026-07-22 사용자 제보). tzinfo는 떼서 돌려준다 —
    기존 신호 dataclass가 naive datetime끼리 빼기 때문이다.
    """
    return datetime.now(_SEOUL_TZ).replace(tzinfo=None)


def _safe_pct_diff(a, b):
    """(a-b)/b*100. b가 0/None이면 None(계산 불가)."""
    if not b:
        return None
    return (a - b) / b * 100


def _fetch_quotes(tickers):
    """티커 묶음을 병렬 조회한다. 종목별 실패는 격리한다."""
    tickers = tuple(tickers)
    if not tickers:
        return {}
    results = {}
    with ThreadPoolExecutor(max_workers=min(16, len(tickers))) as executor:
        futures = {
            executor.submit(price_data.get_snapshot_defaults, ticker): ticker
            for ticker in tickers
        }
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                results[ticker] = future.result()
            except Exception:
                results[ticker] = {"ok": False, "error": "시세 조회 실패"}
    return results


@st.cache_data(ttl=60, show_spinner=False)
def _cached_quotes(tickers):
    return _fetch_quotes(tickers)


@st.cache_data(ttl=8, show_spinner=False)
def _short_cached_quotes(tickers):
    return _fetch_quotes(tickers)


# ---------------------------------------------------------------------------
# 기관 수급 반전 포착 (2026-07-20 추가)
# ---------------------------------------------------------------------------
# KIS 원자료를 읽어 kr_intraday_flow 엔진이 쓰는 스냅숏 dict로 바꾼다. API 하나가
# 실패해도 그 항목만 None으로 두고 나머지는 살린다 — 0으로 채우지 않는다.
_FLOW_SAMSUNG_TICKER = "005930.KS"
_FLOW_HYNIX_TICKER = "000660.KS"

# 기관 세부 주체는 KIS 원본 필드명을 그대로 옮긴다. fund는 원문이 '기금'이므로
# 화면에서도 "기금·연기금"으로 쓰고 연기금이라고 단정하지 않는다.
_FLOW_INVESTOR_FIELDS = {
    "foreign_cash_net_amount": "frgn_ntby_tr_pbmn",
    "personal_cash_net_amount": "prsn_ntby_tr_pbmn",
    "institution_cash_net_amount": "orgn_ntby_tr_pbmn",
    "securities_net_amount": "scrt_ntby_tr_pbmn",
    "investment_trust_net_amount": "ivtr_ntby_tr_pbmn",
    "private_fund_net_amount": "pe_fund_ntby_tr_pbmn",
    "fund_net_amount": "fund_ntby_tr_pbmn",
}


def _flow_kis_keys():
    return st.secrets.get("KIS_APP_KEY"), st.secrets.get("KIS_APP_SECRET")


@st.cache_data(ttl=1800, show_spinner=False)
def _flow_electronics_sector_code(_app_key, _app_secret):
    """전기전자 업종코드를 이름으로 찾아 거래일 동안 캐시한다. 못 찾으면 None."""
    result = kis_market_data.get_sector_category_prices(_app_key, _app_secret)
    if not result.get("ok"):
        return None, None
    code = kr_intraday_flow.find_electronics_sector_code(result["rows"])
    turnover = None
    if code:
        row = next(
            (
                r for r in result["rows"]
                if kr_intraday_flow.normalize_sector_name(r.get("hts_kor_isnm"))
                in kr_intraday_flow.ELECTRONICS_SECTOR_ALIASES
            ),
            None,
        )
        if row:
            turnover = kr_intraday_flow.parse_kis_number(row.get("acml_tr_pbmn"))
    return code, turnover


def collect_kr_flow_snapshot():
    """KIS + 가격 데이터를 한 번 읽어 스냅숏 dict와 실패 목록을 만든다."""
    app_key, app_secret = _flow_kis_keys()
    values = {}
    failures = []

    if not app_key or not app_secret:
        failures.append("KIS API 키 미설정 — 수급 항목 전부 확인 필요")

    parse = kr_intraday_flow.parse_kis_number

    # 1) 전체 프로그램 (최근 구간 마지막 행이 현재값)
    if app_key and app_secret:
        program = kis_market_data.get_program_trade_intraday(app_key, app_secret)
        if program.get("ok") and program["rows"]:
            last = program["rows"][-1]
            values["program_net_amount"] = parse(last.get("whol_smtn_ntby_tr_pbmn"))
            values["program_net_change"] = parse(last.get("whol_ntby_tr_pbmn_icdc2"))
        else:
            failures.append("프로그램 수급 조회 실패")

        # 2) 차익·비차익 (투자자 합계 행을 쓰되 없으면 전 행 합산)
        investor_program = kis_market_data.get_program_trade_by_investor(app_key, app_secret)
        if investor_program.get("ok") and investor_program["rows"]:
            arb = [parse(r.get("arbt_ntby_amt")) for r in investor_program["rows"]]
            nabt = [parse(r.get("nabt_ntby_amt")) for r in investor_program["rows"]]
            arb = [v for v in arb if v is not None]
            nabt = [v for v in nabt if v is not None]
            values["arbitrage_net_amount"] = sum(arb) if arb else None
            values["non_arbitrage_net_amount"] = sum(nabt) if nabt else None
        else:
            failures.append("차익·비차익 프로그램 조회 실패")

        # 3) 투자자별 수급
        investors = kis_market_data.get_market_investor_intraday(app_key, app_secret)
        if investors.get("ok"):
            row = investors["row"]
            for column, field in _FLOW_INVESTOR_FIELDS.items():
                values[column] = parse(row.get(field))
        else:
            failures.append("투자자별 수급 조회 실패")

        # 4) KOSPI200 선물 베이시스 (최근월물 코드는 설정값에서만 읽는다)
        futures = kis_market_data.get_kospi200_futures_snapshot(
            app_key, app_secret, futures_code=st.secrets.get("KIS_KOSPI200_FUTURES_CODE")
        )
        if futures.get("ok"):
            values["futures_basis"] = futures.get("basis")
            values["futures_market_basis"] = futures.get("market_basis")
        else:
            failures.append(f"선물 베이시스 조회 실패 ({futures.get('error')})")

        # 5) 전기전자 업종 — 코드를 이름으로 찾고, 못 찾으면 추측하지 않는다
        sector_code, sector_turnover = _flow_electronics_sector_code(app_key, app_secret)
        values["electronics_turnover"] = sector_turnover
        if sector_code:
            sector_flow = kis_market_data.get_market_investor_intraday(
                app_key, app_secret, sector_code=sector_code
            )
            # 업종 수급이 KOSPI 전체와 똑같이 나오면 업종 필터가 안 먹은 것이다.
            # 그 경우 전체 수급으로 대신 채우지 않고 미확인으로 둔다.
            if sector_flow.get("ok"):
                sector_net = parse(sector_flow["row"].get("orgn_ntby_tr_pbmn"))
                if sector_net is not None and sector_net != values.get("institution_cash_net_amount"):
                    values["electronics_institution_net"] = sector_net
                else:
                    failures.append("전기전자 업종 수급 미검증 — 확인 필요")
        else:
            failures.append("전기전자 업종코드 자동 탐색 실패")

    # 6) 삼성전자·SK하이닉스 (기존 가격 조회 재사용)
    for prefix, ticker in (("samsung", _FLOW_SAMSUNG_TICKER), ("hynix", _FLOW_HYNIX_TICKER)):
        quote = price_data.get_snapshot_defaults(ticker)
        if quote.get("ok"):
            values[f"{prefix}_price"] = quote.get("current")
            values[f"{prefix}_open"] = quote.get("open")
            values[f"{prefix}_day_low"] = quote.get("low")
        else:
            failures.append(f"{'삼성전자' if prefix == 'samsung' else 'SK하이닉스'} 가격 조회 실패")

    # 7) 외국인 선물 수급 — 수동 입력값이 있으면 우선, 없으면 네이버 지연 공개치를
    #    자동 조회한다(2026-07-22 사용자 지시: 직접 입력 대신 자동으로 찾아 띄울 것).
    manual = st.session_state.get("kr_flow_foreign_futures_manual") or {}
    if manual.get("net_contracts") is not None and manual.get("trade_date") == _flow_today():
        values["foreign_futures_net_contracts"] = int(manual["net_contracts"])
        values["foreign_futures_source"] = manual.get("source") or "HTS 수동 입력"
    else:
        auto_futures = naver_market_data.get_foreign_futures_daily_net()
        if auto_futures.get("ok"):
            values["foreign_futures_net_contracts"] = int(auto_futures["net_contracts"])
            values["foreign_futures_source"] = auto_futures.get("source") or "네이버 선물 투자자동향(지연)"
        else:
            failures.append("외국인 선물 자동 조회 실패 — 확인 필요")

    values["raw_source_status"] = " / ".join(failures) if failures else "정상"
    return values, failures


def _flow_today():
    return _now_seoul().strftime("%Y-%m-%d")


def run_kr_flow_check():
    """수급을 한 번 읽어 DB에 쌓고, 당일 스냅숏 전체로 판정을 만든다."""
    values, failures = collect_kr_flow_snapshot()
    trade_date = _flow_today()
    captured_at = _now_seoul().replace(second=0, microsecond=0).isoformat()

    try:
        database.save_kr_flow_snapshot(trade_date, captured_at, values)
    except Exception:
        failures.append("장중 수급 스냅숏 저장 실패")

    try:
        snapshots = database.list_kr_flow_snapshots(trade_date)
    except Exception:
        snapshots = [{**values, "captured_at": captured_at}]

    manual = st.session_state.get("kr_flow_foreign_futures_manual") or {}
    foreign_futures = None
    if manual.get("net_contracts") is not None and manual.get("trade_date") == trade_date:
        foreign_futures = kr_intraday_flow.ForeignFuturesFlowSnapshot(
            net_contracts=int(manual["net_contracts"]),
            previous_net_contracts=manual.get("previous_net_contracts"),
            as_of=manual.get("as_of"),
            source=manual.get("source") or "HTS 수동 입력",
            confidence="manual",
            available=True,
        )
    elif values.get("foreign_futures_net_contracts") is not None:
        # 네이버 자동 조회치 — 직전 스냅숏에 저장된 값과 비교해 증감 방향도 판정한다.
        previous_value = None
        for snap in reversed(snapshots[:-1]):
            try:
                candidate = snap.get("foreign_futures_net_contracts")
            except AttributeError:
                candidate = None
            if candidate is not None:
                previous_value = int(candidate)
                break
        foreign_futures = kr_intraday_flow.ForeignFuturesFlowSnapshot(
            net_contracts=int(values["foreign_futures_net_contracts"]),
            previous_net_contracts=previous_value,
            as_of=_now_seoul(),
            source=values.get("foreign_futures_source") or "네이버 선물 투자자동향(지연)",
            confidence="delayed_public",
            available=True,
        )

    result = kr_intraday_flow.build_result_from_snapshots(
        snapshots, foreign_futures=foreign_futures
    )
    st.session_state["kr_flow_result"] = result
    st.session_state["kr_flow_failures"] = failures
    return result


_FLOW_VERDICT_STYLE = {
    kr_intraday_flow.ReboundVerdict.CONFIRMED: ("#14532d", "#22c55e", "#86efac"),
    kr_intraday_flow.ReboundVerdict.PROXY_CONFIRMED: ("#1e3a5f", "#3b82f6", "#93c5fd"),
    kr_intraday_flow.ReboundVerdict.WATCHING: ("#4a2e05", "#eab308", "#fde047"),
    kr_intraday_flow.ReboundVerdict.NOT_CONFIRMED: ("#4c1d1d", "#ef4444", "#fca5a5"),
    kr_intraday_flow.ReboundVerdict.INSUFFICIENT_DATA: ("#27272a", "#71717a", "#d4d4d8"),
}

# 첫 화면에서 바로 보여야 하는 핵심 4개
_FLOW_CORE_DISPLAY = (
    ("non_arbitrage", "비차익 프로그램"),
    ("foreign_futures", "외국인 선물"),
    ("samsung", "삼성전자"),
    ("hynix", "SK하이닉스"),
)

_FLOW_TABLE_KEYS = (
    "program_total", "arbitrage", "non_arbitrage", "market_basis",
    "foreign_futures", "foreign_cash", "institution", "securities",
    "investment_trust", "private_fund", "fund",
    "electronics_turnover", "electronics_institution", "samsung", "hynix",
)


# 상세 표의 값별 색 — 같은 값은 어느 시장 카드에서든 같은 색으로 보이게 한다.
# 판정 칸은 마크만이 아니라 '표 읽는 법'과 똑같은 뜻 글자를 함께 쓴다
# (2026-07-22 사용자 지시: "⭕ 긍정(신호 켜짐)"처럼 마크와 내용을 같이 넣을 것).
_STATUS_TEXT = {
    market_signal_common.SignalStatus.POSITIVE: "긍정(신호 켜짐)",
    market_signal_common.SignalStatus.NEUTRAL: "중립(보합)",
    market_signal_common.SignalStatus.NEGATIVE: "부정",
    market_signal_common.SignalStatus.UNKNOWN: "확인 필요",
}

_TIMING_COLOR = {
    "선행": "#4da6ff", "확인": "#e6e6e6", "늦음": "#ff9d3b",
    "가짜": "#ef4444", "확인 필요": "#9ca3af",
}
_STRENGTH_COLOR = {"직접": "#22c55e", "대체": "#ff9d3b", "간접": "#9ca3af"}
_FRESHNESS_COLOR = {
    "정상": "#22c55e", "지연": "#ff9d3b", "오래됨": "#ef4444", "확인 필요": "#9ca3af",
}

_SIGNAL_TABLE_LEGEND_HTML = """
<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.12);
border-radius:8px;padding:10px 14px;margin-bottom:10px;font-size:0.9rem;line-height:1.8;">
  <div style="font-weight:800;color:#e6e6e6;margin-bottom:2px;">표 읽는 법</div>
  <b style="color:#9ca3af;">판정</b> :
  ⭕ <span style="color:#22c55e;">긍정(신호 켜짐)</span> ·
  🟡 <span style="color:#eab308;">중립(보합)</span> ·
  ❌ <span style="color:#ef4444;">부정</span> ·
  ⚪ <span style="color:#9ca3af;">확인 필요(자료 없음)</span><br>
  <b style="color:#9ca3af;">구분</b> :
  <span style="color:#4da6ff;">선행</span> = 본장보다 먼저 움직이는 지표 ·
  <span style="color:#e6e6e6;">확인</span> = 결과로 따라오는 지표 ·
  <span style="color:#ff9d3b;">늦음</span> = 이미 지나간 흐름일 수 있는 신호<br>
  <b style="color:#9ca3af;">신호세기</b> :
  <span style="color:#22c55e;">직접</span> = 원자료 그대로 ·
  <span style="color:#ff9d3b;">대체</span> = 직접값이 없어 대신 쓰는 근사 신호 ·
  <span style="color:#9ca3af;">간접</span> = 참고 수준 신호<br>
  <b style="color:#9ca3af;">신선도</b> :
  <span style="color:#22c55e;">정상</span> = 2분 이내 자료 ·
  <span style="color:#ff9d3b;">지연</span> = 5분 이내 ·
  <span style="color:#ef4444;">오래됨</span> = 5분 초과 ·
  <span style="color:#9ca3af;">확인 필요</span> = 기준시각 없음
</div>
"""

_SIGNAL_TABLE_CSS = """
<style>
.msig-table { width:100%; border-collapse:collapse; font-size:0.92rem; }
.msig-table th { text-align:center; color:#9aa0aa; font-weight:800; padding:0.45rem 0.4rem;
  border-bottom:1px solid rgba(255,255,255,0.2); }
.msig-table td { text-align:center; padding:0.4rem 0.4rem; color:#e6e6e6;
  border-bottom:1px solid rgba(255,255,255,0.07); }
.msig-table td.msig-name { text-align:left; font-weight:800; }
.msig-table td.msig-reason { text-align:left; color:#c9ced6; font-size:0.88rem; }
</style>
"""


def kr_flow_diagnosis(result) -> str | None:
    """한국장 수급이 왜 비어 있는지 한 줄로 설명한다.

    사용자가 조치할 수 있는 것(장 시간 기다리기)과 없는 것(API 장애)을 구분해 알려준다.
    """
    failures = st.session_state.get("kr_flow_failures") or []
    app_key, app_secret = _flow_kis_keys()
    now = _now_seoul()
    in_session = now.weekday() < 5 and 9 <= now.hour < 16

    if not app_key or not app_secret:
        return (
            "이 컴퓨터에는 증권사(KIS) 조회 키가 없어 프로그램·기관 수급을 못 읽습니다. "
            "온라인 자비스에서는 정상 조회됩니다."
        )
    if not in_session:
        return (
            "지금은 한국 정규장(09:00~15:30) 시간이 아니라 장중 수급이 공개되지 않습니다. "
            "장이 열리면 자동으로 채워집니다."
        )
    kis_failures = [f for f in failures if "조회 실패" in f or "응답" in f]
    if kis_failures:
        return (
            f"증권사(KIS) 수급 조회가 지금 실패하고 있습니다({len(kis_failures)}건). "
            "잠시 뒤 ‘수급 다시 확인’을 눌러보세요 — 값을 임의로 만들지 않고 비워 둡니다."
        )
    if failures:
        return "일부 항목이 아직 안 채워졌습니다. 스냅숏이 15분 이상 쌓이면 자동으로 판정됩니다."
    return None


def render_market_signal_card(
    result, *, verdict_style, core_display, table_keys, detail_title, detail_caption,
    table_key, diagnosis_text=None,
):
    """한국장·미국장이 함께 쓰는 카드 렌더러.

    공통으로 두는 것은 카드 모양·상태색·표 형식뿐이다. 판정 기준과 결론 문구는
    시장별 엔진이 이미 만들어서 넘겨준다 — 여기서 KR/US를 분기하지 않는다.
    """
    bg, border, text = verdict_style[result.verdict]
    _card_as_of = next((s.as_of for s in result.signals if s.as_of), None)
    _as_of_label = _card_as_of.strftime("%H:%M") + " 기준(한국시각)" if _card_as_of else "기준시각 확인 필요"

    # 왜 '확인 중'인지 한 줄로 알려준다(2026-07-22 사용자 제보: 계속 확인 중인데 이유가 안 보임).
    # 실패 목록을 나열하지 않고, 자료가 왜 비었는지 원인만 요약한다.
    _unknown_count = sum(1 for signal in result.signals if signal.is_unknown)
    _cause = diagnosis_text(result) if diagnosis_text else None
    _cause_html = (
        f"<div style='font-size:0.9rem;color:{text};opacity:0.95;margin-top:8px;'>왜 확인 중인가: {_cause}</div>"
        if _cause and _unknown_count else ""
    )

    st.markdown(
        f"""
        <div style="background-color:{bg};border:2px solid {border};border-radius:10px;
        padding:16px;margin-top:8px;">
          <div style="font-size:1.35rem;font-weight:800;color:{text};">{result.verdict_label}</div>
          <div style="font-size:0.85rem;color:{text};opacity:0.85;margin-top:4px;">
            {_as_of_label} · {result.data_status}
          </div>
          <div style="font-size:1.0rem;color:{text};margin-top:10px;line-height:1.5;">
            {result.headline}
          </div>
          <div style="font-size:0.9rem;color:{text};opacity:0.9;margin-top:8px;">
            흐름: {result.flow_note}
          </div>
          {_cause_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    for warning in result.warnings:
        st.warning(warning)

    # 핵심 4개 — 모바일 1열, 그 위 2열 (기존 반응형 규칙과 동일하게 columns 사용)
    st.markdown("#### 핵심 4개")
    _core_cols = st.columns(2)
    for index, (key, label) in enumerate(core_display):
        signal = result.signal(key)
        if signal is None:
            continue
        color = market_signal_common.STATUS_COLOR[signal.status]
        with _core_cols[index % 2]:
            st.markdown(
                f"""
                <div style="border-left:5px solid {color};padding:8px 12px;margin-bottom:8px;
                background-color:rgba(255,255,255,0.03);border-radius:6px;">
                  <div style="font-size:0.85rem;opacity:0.75;">{label}</div>
                  <div style="font-size:1.05rem;font-weight:700;color:{color};">
                    {signal.display_value}
                  </div>
                  <div style="font-size:0.8rem;opacity:0.8;">{signal.reason}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if result.supporting_reasons:
        st.markdown("**켜진 신호**")
        for reason in result.supporting_reasons:
            st.markdown(f"- {reason}")
    if result.missing_reasons:
        st.markdown("**아직 아닌 신호**")
        for reason in result.missing_reasons:
            st.markdown(f"- {reason}")

    # 상세 표는 자동으로 펼치고, 표 위에 각 열이 무엇을 뜻하는지 범례를 둔다
    # (2026-07-22 사용자 지시 — 캡처 주석: "자동으로 열리게", "설명 따로 위에 만들 것",
    # "색깔은 조건마다 다르게").
    with st.expander(detail_title, expanded=True):
        st.markdown(_SIGNAL_TABLE_LEGEND_HTML, unsafe_allow_html=True)
        _rows_html = []
        for key in table_keys:
            signal = result.signal(key)
            if signal is None:
                continue
            status_color = market_signal_common.STATUS_COLOR[signal.status]
            timing_text = market_signal_common.TIMING_LABEL[signal.timing]
            strength_text = market_signal_common.STRENGTH_LABEL[signal.strength]
            fresh_text = market_signal_common.freshness_label(signal.freshness_seconds)
            _rows_html.append(
                "<tr>"
                f"<td class='msig-name'>{signal.label}</td>"
                f"<td style='color:{status_color};font-weight:700'>{signal.display_value}</td>"
                f"<td style='color:{status_color};font-weight:700;white-space:nowrap'>"
                f"{market_signal_common.STATUS_MARK[signal.status]} {_STATUS_TEXT[signal.status]}</td>"
                f"<td style='color:{_TIMING_COLOR.get(timing_text, '#e6e6e6')};font-weight:700'>{timing_text}</td>"
                f"<td style='color:{_STRENGTH_COLOR.get(strength_text, '#e6e6e6')};font-weight:700'>{strength_text}</td>"
                f"<td class='msig-reason'>{signal.reason}</td>"
                f"<td style='color:{_FRESHNESS_COLOR.get(fresh_text, '#e6e6e6')};font-weight:700'>{fresh_text}</td>"
                "</tr>"
            )
        if _rows_html:
            st.markdown(
                _SIGNAL_TABLE_CSS
                + "<table class='msig-table'><thead><tr>"
                "<th>항목</th><th>현재값</th><th>판정</th><th>구분</th>"
                "<th>신호세기</th><th>설명</th><th>신선도</th></tr></thead>"
                f"<tbody>{''.join(_rows_html)}</tbody></table>",
                unsafe_allow_html=True,
            )
        st.caption(detail_caption)


def render_kr_flow_card():
    """🎯 한국장 기관 수급 반전 포착. 0단계 결과 바로 아래에 놓인다."""
    st.markdown("### 🎯 한국장 기관 수급 반전 포착")
    st.caption(
        "지금 기관이 들어오는 장인지, 무엇이 먼저 움직였는지를 읽어줍니다. "
        "매수·매도 판단은 상하님이 다른 자비스와 함께 결정하시는 몫입니다."
    )

    if st.button("수급 다시 확인", key="kr_flow_refresh"):
        with st.spinner("장중 수급 확인 중..."):
            run_kr_flow_check()

    result = st.session_state.get("kr_flow_result")
    if result is None:
        # 버튼을 누르기 전에도 첫 화면에서 자동으로 한 번 읽는다(2026-07-22 사용자 지시).
        with st.spinner("장중 수급 자동 확인 중..."):
            result = run_kr_flow_check()

    render_market_signal_card(
        result,
        verdict_style=_FLOW_VERDICT_STYLE,
        core_display=_FLOW_CORE_DISPLAY,
        table_keys=_FLOW_TABLE_KEYS,
        detail_title="한국장 전체 수급 상세",
        detail_caption=(
            "‘기금·연기금’은 KIS 원본 필드명이 기금입니다. 시장베이시스는 외국인 선물 "
            "직접 수급이 없을 때 쓰는 대체 신호이며 직접 수급값이 아닙니다."
        ),
        table_key="kr_flow_detail_table",
        diagnosis_text=kr_flow_diagnosis,
    )

    # 조회 실패 목록과 외국인 선물 수동 입력칸은 없앴다(2026-07-22 사용자 지시).
    # 사용자가 손쓸 수 없는 항목을 나열해봐야 의미가 없고, 못 가져온 값은 이미 위 표에
    # '확인 필요'로 정확히 표시된다. 외국인 선물은 네이버에서 자동 조회한다.


_US_VERDICT_STYLE = {
    us_market_signal_engine.UsMarketVerdict.RISK_ON: ("#14532d", "#22c55e", "#86efac"),
    us_market_signal_engine.UsMarketVerdict.RISK_ON_EARLY: ("#1e3a5f", "#3b82f6", "#93c5fd"),
    us_market_signal_engine.UsMarketVerdict.MIXED: ("#4a2e05", "#eab308", "#fde047"),
    us_market_signal_engine.UsMarketVerdict.RISK_OFF: ("#4c1d1d", "#ef4444", "#fca5a5"),
    us_market_signal_engine.UsMarketVerdict.INSUFFICIENT_DATA: ("#27272a", "#71717a", "#d4d4d8"),
}

_US_CORE_DISPLAY = (
    ("US_NQ_FUTURES", "나스닥100 선물"),
    ("US_SOXX", "SOXX"),
    ("US_VIX", "VIX"),
    ("US_TNX", "미국 10년물"),
)

_US_TABLE_KEYS = tuple(spec[0] for spec in us_market_signal_engine.US_SIGNAL_SPECS) + ("US_VIX_TERM",)


def run_us_market_signal_check(force_refresh=False):
    """미국장 신호 티커를 한 번에 조회해 판정을 만든다. DB 저장은 하지 않는다.

    미국장 신호는 전부 현재값·전일대비로 판정하므로 한국장처럼 스냅숏을 누적할
    필요가 없다. 안 쓰는 테이블을 만들지 않기 위해 일부러 저장하지 않는다.
    """
    # ^VIX3M은 신호 스펙에는 없지만 VIX 기간구조(대체신호) 계산에 필요해서 함께 조회한다.
    tickers = tuple(spec[2] for spec in us_market_signal_engine.US_SIGNAL_SPECS) + ("^VIX3M",)
    results = (
        _short_cached_quotes(tickers)
        if force_refresh
        else _cached_quotes(tickers)
    )

    quotes = {}
    failures = []
    for ticker in tickers:
        quote = results.get(ticker) or {}
        if quote.get("ok"):
            quotes[ticker] = {
                "change_pct": _safe_pct_diff(quote.get("current"), quote.get("prev_close")),
                "as_of": _now_seoul(),
                "source": quote.get("source") or "자동 조회",
            }
        else:
            failures.append(f"{ticker} 조회 실패")

    extras = {
        "vix_current": (results.get("^VIX") or {}).get("current"),
        "vix3m_current": (results.get("^VIX3M") or {}).get("current"),
    }
    result = us_market_signal_engine.build_us_market_signal_result(quotes, extras=extras)
    st.session_state["us_signal_result"] = result
    st.session_state["us_signal_failures"] = failures
    return result


def render_us_market_signal_card():
    """🌐 미국장 선행신호·시장 상태. 미국장 시장요약 바로 아래에 놓인다."""
    st.markdown("### 🌐 미국장 선행신호·시장 상태")
    st.caption(
        "선물·반도체 ETF·변동성·금리가 서로 같은 방향인지, 무엇이 먼저 움직였는지를 읽어줍니다. "
        "미국은 장중 수급 공개 데이터가 없어 한국장과 판정 방식이 다릅니다."
    )

    if st.button("미국장 신호 다시 확인", key="us_signal_refresh"):
        with st.spinner("미국장 신호 확인 중..."):
            run_us_market_signal_check(force_refresh=True)

    result = st.session_state.get("us_signal_result")
    if result is None:
        # 버튼을 누르기 전에도 첫 화면에서 자동으로 한 번 읽는다(2026-07-22 사용자 지시).
        with st.spinner("미국장 신호 자동 확인 중..."):
            result = run_us_market_signal_check()

    render_market_signal_card(
        result,
        verdict_style=_US_VERDICT_STYLE,
        core_display=_US_CORE_DISPLAY,
        table_keys=_US_TABLE_KEYS,
        detail_title="미국장 전체 신호 상세",
        detail_caption=(
            "VIX·미국 10년물·달러지수는 오르면 위험자산에 부담이라 ‘하락’이 긍정 판정입니다. "
            "선물·반도체 ETF는 본장보다 먼저 움직여 선행, 지수는 결과라서 확인 신호로 봅니다."
        ),
        table_key="us_signal_detail_table",
    )
    # 실패 목록 나열은 없앴다(2026-07-22 사용자 지시) — 못 가져온 값은 위 표에
    # '확인 필요'로 이미 표시되고, 사용자가 손쓸 수 없는 항목이라 나열해도 의미가 없다.






def render_market_judgment_page():
    """시장 판단 화면 전체. 한국장·미국장 카드를 위아래로 놓는다."""
    st.markdown("## 🧭 시장 판단")
    st.caption(
        "자비스1·2·3에 들어가기 전에 지금 시장이 어떤 상태인지 먼저 봅니다. "
        "여기서 나오는 것은 판정과 흐름이고, 무엇을 할지는 상하님이 정하십니다."
    )

    render_kr_flow_card()
    st.divider()
    render_us_market_signal_card()

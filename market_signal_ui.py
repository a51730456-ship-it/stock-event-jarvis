"""시장 판단 화면의 데이터 수집과 렌더링.

자비스1·2·3 어디에도 속하지 않는 독립 화면(pages/0_시장판단.py)에서 쓴다.
app.py를 import하면 자비스1 앱 전체가 실행되므로, 필요한 조회 로직은 여기에 둔다.

카드는 종목을 고르는 물건이 아니다. 지금 시장이 어떤 상태이고 무엇이 앞서
움직이는지 읽어서, 사용자가 자비스1·2·3과 대조해 스스로 판단할 재료를 준다.
그래서 결론 문구에 매수·매도 지시를 넣지 않는다.
"""

from __future__ import annotations

import importlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

import database
import kis_market_data
import kr_intraday_flow
import gauge_ui
import market_signal_common
import naver_market_data
import naver_stock_quote
import price_data
import us_market_signal_engine

if not hasattr(database, "list_previous_kr_flow_snapshots"):
    database = importlib.reload(database)

_SEOUL_TZ = ZoneInfo("Asia/Seoul")

# 실행 중인 프로세스에 옛 모듈이 남아 있는지 화면이 스스로 알아채기 위한 표식이다
# (jarvis3_data·jarvis4_data와 같은 장치). 기존 가드는 '_STATUS_TEXT가 있나'만 봐서,
# 이름이 그대로인 채 내용만 바뀐 경우를 못 걸렀다 — 2026-07-24 온라인에서 4대 지수는
# 나오는데 신호 카드 게이지만 빠지는 일이 실제로 있었다.
# 화면에 나가는 것이 바뀌면 이 숫자를 올린다.
MODULE_REVISION = 2026072911


def _now_seoul():
    """기준시각은 항상 한국 시간이다.

    스트림릿 클라우드 서버는 UTC라서 datetime.now()를 쓰면 화면에 04:28처럼
    9시간 어긋난 시각이 표시된다(2026-07-22 사용자 제보). tzinfo는 떼서 돌려준다 —
    기존 신호 dataclass가 naive datetime끼리 빼기 때문이다.
    """
    return datetime.now(_SEOUL_TZ).replace(tzinfo=None)


# 부호가 붙은 수(-4.55%, +1,711계약, +13,550억)를 찾아 색을 입힌다.
_SIGNED_NUMBER = re.compile(r"[+\-][\d,]+(?:\.\d+)?%?")

# 오름은 파랑, 내림은 빨강. 한국 관행은 반대지만 사용자 지시가 이 색이다.
_UP_COLOR = "#4da6ff"
_DOWN_COLOR = "#ff5b5b"

# 값 줄의 기본색. 판정색(초록·노랑·붉은색)을 값에 입히면 종목마다 같은 줄이
# 다른 색으로 떠서 서로 다른 뜻처럼 보인다 — 삼성전자(부정)는 통째로 붉고
# SK하이닉스(중립)는 노랬다(2026-07-29 지적: "삼성전자는 왜 저렇게 했냐,
# 하이닉스처럼 해야지"). 값은 흰색으로 두고 부호 붙은 수만 색을 갈라 준다.
# 판정색은 칸 테두리와 판정 글자에만 남는다.
_VALUE_COLOR = "#e6e6e6"


# 지수가 이만큼 넘게 빠지면 '하락장'이라고 적는다. 순매수가 사실이어도
# 지수가 무너지는 날에는 그 '긍정'을 다르게 읽어야 한다.
FALLING_MARKET_PCT = -2.0


@st.cache_data(ttl=30, show_spinner=False)
def _cached_kospi_snapshot():
    """코스피 현재지수. 30초만 캐시한다.

    수급 카드는 장중 1분마다 자동으로 다시 그린다. 그릴 때마다 지수를 새로
    받으면 그만큼 화면이 늦어진다. 하락장이냐 아니냐는 30초 사이에 뒤집히지
    않으므로 이 정도로 충분하다.
    """
    return naver_market_data.get_index_snapshot("KOSPI")


def falling_market_note(*, snapshot_fn=None, label="코스피"):
    """지금 지수가 크게 빠지고 있으면 붙일 꼬리표를 만든다.

    2026-07-29: 코스피 -5.7%인 날 표가 '긍정' 초록으로 도배됐다. 기관계
    +1조 3,550억 순매수는 사실이라 판정 자체는 틀리지 않았지만, 수급 판정이
    가격을 전혀 안 봐서 맨 위 결론('반전 신호 없음')과 앞뒤가 어긋나 보였다.

    **판정은 바꾸지 않는다**(사용자 선택 1번). 긍정 옆에 '(하락장)'만 적어
    무슨 상황에서 켜진 신호인지 알 수 있게 한다. 지수를 못 읽으면 조용히
    아무것도 안 붙인다 — 없는 값을 0으로 보고 '하락장 아님'이라 하면 안 된다.
    """
    fetch = snapshot_fn or _cached_kospi_snapshot
    try:
        snapshot = fetch() or {}
    except Exception:
        return None
    if not snapshot.get("ok"):
        return None
    change = snapshot.get("change_pct")
    try:
        change = float(change)
    except (TypeError, ValueError):
        return None
    if change > FALLING_MARKET_PCT:
        return None
    return {"label": label, "change_pct": change, "text": "(하락장)"}


def _falling_tag(signal, falling_market) -> str:
    """긍정으로 켜진 신호에만 '(하락장)'을 붙인다.

    중립·부정에까지 붙이면 화면이 꼬리표로 뒤덮여 정작 봐야 할 것이 묻힌다.
    오해가 생기는 자리는 '지수가 무너지는데 초록'인 곳뿐이다.
    """
    if not falling_market:
        return ""
    if signal.status is not market_signal_common.SignalStatus.POSITIVE:
        return ""
    return (f" <span style='color:{_DOWN_COLOR};font-weight:800'>"
            f"{falling_market['text']}</span>")


def _colorize_signed(text) -> str:
    """값 안의 부호 붙은 수만 오름·내림 색으로 칠한다.

    판정색(초록·노랑·붉은색)이 값을 통째로 덮으면 오른 건지 내린 건지
    알 수 없다 — 코스피 -5.7%인 날 '210,000 (-4.55% · 저점대비 +1.45%)'가
    전부 노랑(보합)으로 떠서 구분이 안 됐다(2026-07-29 사용자 지적).
    판정색은 칸 테두리와 판정 글자에만 남긴다.
    """
    if not text:
        return ""

    def paint(match):
        mark = match.group()
        color = _UP_COLOR if mark[0] == "+" else _DOWN_COLOR
        return f"<span style='color:{color}'>{mark}</span>"

    return _SIGNED_NUMBER.sub(paint, str(text))


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


@st.cache_data(ttl=60, show_spinner=False)
def _flow_electronics_sector_code(_app_key, _app_secret):
    """전기전자 업종코드·누적 거래대금을 1분 동안만 캐시한다."""
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


def _fresh_naver_stock_quote(quote, *, now=None) -> bool:
    """네이버 장중 종목 시세가 현재 한국장 값인지 확인한다."""
    quote = quote or {}
    if quote.get("price") is None or quote.get("day_open") is None or quote.get("day_low") is None:
        return False
    now = now or _now_seoul()
    if now.tzinfo is None:
        now = now.replace(tzinfo=_SEOUL_TZ)
    else:
        now = now.astimezone(_SEOUL_TZ)
    traded_at = quote.get("traded_at")
    try:
        traded_at = datetime.fromisoformat(str(traded_at))
    except (TypeError, ValueError):
        return False
    if traded_at.tzinfo is None:
        traded_at = traded_at.replace(tzinfo=_SEOUL_TZ)
    else:
        traded_at = traded_at.astimezone(_SEOUL_TZ)
    age = now - traded_at
    if quote.get("market_status") == "OPEN":
        return (
            traded_at.date() == now.date()
            and -timedelta(minutes=1) <= age <= timedelta(minutes=5)
        )
    # 장 마감 뒤에는 같은 날의 마감 스냅숏까지만 허용한다.
    return traded_at.date() == now.date() and now.time() > datetime.strptime("15:30", "%H:%M").time()


def _naive_seoul(value):
    """자료가 밝힌 기준시각을 naive 한국시각으로 맞춘다. 못 읽으면 None.

    신호 dataclass가 naive끼리 빼기 때문에 tzinfo를 남기면 신선도 계산이 터진다.
    """
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is not None:
        value = value.astimezone(_SEOUL_TZ).replace(tzinfo=None)
    return value


def collect_kr_flow_snapshot(*, force_refresh=False):
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

    # 3-b) KIS 투자자별 수급이 비었으면 네이버 시간별 공개치로 채운다
    #      (2026-07-22 추가: KIS가 실패하면 수급 항목이 통째로 비어 판정이 계속
    #      '확인 중'에 머물렀다. 값을 만들어내는 게 아니라 공개된 지연치를 쓰고,
    #      아래에서 신호 세기를 '대체'로 표시한다.)
    if values.get("foreign_cash_net_amount") is None:
        naver_flow = naver_market_data.get_market_investor_flow_intraday("KOSPI")
        if not naver_flow.get("ok"):
            # 장외·개장 직후 시간별 표가 비면 당일 누적 표를 마지막 대안으로 쓴다.
            naver_flow = naver_market_data.get_market_investor_flow("KOSPI")
        if naver_flow.get("ok"):
            amounts = naver_flow["values"]

            def _to_million(name):
                # 엔진(_fmt_amount·임계값)은 KIS와 같은 '백만원' 단위를 기대한다.
                # 네이버는 억원이므로 ×100이 맞다. 원(×1e8)으로 넣었더니 화면에
                # '+20,361,000,000억'처럼 1억 배 부풀려졌다(2026-07-22 실측 수정).
                value = amounts.get(name)
                return None if value is None else float(value) * 100

            values["foreign_cash_net_amount"] = _to_million("foreign")
            values["personal_cash_net_amount"] = _to_million("personal")
            values["institution_cash_net_amount"] = _to_million("institution")
            values["securities_net_amount"] = _to_million("securities")
            values["investment_trust_net_amount"] = _to_million("investment_trust")
            values["fund_net_amount"] = _to_million("pension")
            values["investor_flow_source"] = naver_flow.get("source")
            # 네이버 시간별 표는 몇 시 기준인지 밝힌다. 그 시각으로 신선도를 재야
            # '정상'이 실제로 최근 자료라는 뜻이 된다. 시각이 없는 일별 표로 내려간
            # 경우에는 비워 두고 화면이 '확인 필요'로 나가게 한다(2026-07-29).
            values["investor_flow_as_of"] = _naive_seoul(naver_flow.get("as_of"))
        else:
            failures.append("투자자별 수급 대체 조회도 실패")

    if app_key and app_secret:
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
        if force_refresh:
            _flow_electronics_sector_code.clear()
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

    # 6) 삼성전자·SK하이닉스 — Yahoo 일봉은 장중 약 20분까지 차이 났다.
    #    네이버 폴링의 현재가·시가·저가가 5분 이내일 때 우선 사용하고 실패할 때만
    #    기존 가격 조회로 내려간다.
    now = _now_seoul()
    try:
        live_quotes = naver_stock_quote.get_quotes(("005930", "000660"))
    except Exception:
        live_quotes = {}
    for prefix, code, ticker, label in (
        ("samsung", "005930", _FLOW_SAMSUNG_TICKER, "삼성전자"),
        ("hynix", "000660", _FLOW_HYNIX_TICKER, "SK하이닉스"),
    ):
        live = live_quotes.get(code) or {}
        if _fresh_naver_stock_quote(live, now=now):
            values[f"{prefix}_price"] = live.get("price")
            values[f"{prefix}_open"] = live.get("day_open")
            values[f"{prefix}_day_low"] = live.get("day_low")
            # 전일 종가가 있어야 화면이 '전일 대비'를 적을 수 있다. 없으면
            # 저점 대비만 남는데, 그건 폭락일에도 늘 플러스라 오해를 부른다.
            values[f"{prefix}_prev_close"] = live.get("prev_close")
            # 체결 시각으로 신선도를 잰다. 조회 시각으로 재면 5분 전 값도 '정상'이다.
            values[f"{prefix}_quote_as_of"] = _naive_seoul(live.get("traded_at"))
            continue
        quote = price_data.get_snapshot_defaults(ticker)
        if quote.get("ok"):
            values[f"{prefix}_price"] = quote.get("current")
            values[f"{prefix}_open"] = quote.get("open")
            values[f"{prefix}_day_low"] = quote.get("low")
            values[f"{prefix}_prev_close"] = quote.get("prev_close")
            failures.append(f"{label} 네이버 장중 시세 실패 — 기존 가격으로 대체")
        else:
            failures.append(f"{label} 가격 조회 실패")

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


def _value_before(snapshots, column, *, seconds, latest_at):
    """seconds만큼 전 시점의 값. 그만큼 안 쌓였으면 가장 오래된 값을 쓴다.

    엔진의 _recent_change와 같은 기준이다 — 외국인 선물만 직전 1분과 비교하면
    같은 표 안에서 항목마다 다른 잣대를 쓰게 된다.
    """
    known = []
    for snap in snapshots or []:
        try:
            value = snap.get(column)
        except AttributeError:
            continue
        if value is None:
            continue
        stamp = snap.get("captured_at")
        if isinstance(stamp, str):
            try:
                stamp = datetime.fromisoformat(stamp)
            except ValueError:
                continue
        if not isinstance(stamp, datetime):
            continue
        known.append((stamp, value))
    if not known:
        return None
    known.sort()
    older = [v for ts, v in known if (latest_at - ts).total_seconds() >= seconds]
    return int(older[-1]) if older else int(known[0][1])


def _flow_today():
    return _now_seoul().strftime("%Y-%m-%d")


def _expected_previous_weekday(trade_date: str) -> str | None:
    """주말만 건너뛴 직전 평일. 거래소 휴장일은 저장 여부로 따로 구별한다."""
    try:
        day = datetime.strptime(str(trade_date), "%Y-%m-%d").date() - timedelta(days=1)
    except (TypeError, ValueError):
        return None
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day.isoformat()


def run_kr_flow_check(*, force_refresh=False):
    """수급을 한 번 읽어 DB에 쌓고, 당일 스냅숏 전체로 판정을 만든다."""
    attempted_at = _now_seoul()
    # 실패하더라도 마지막 시도 시각을 남겨 전체 화면 rerun 때 API를 연속 호출하지 않는다.
    st.session_state["kr_flow_last_attempt_at"] = attempted_at
    try:
        values, failures = collect_kr_flow_snapshot(force_refresh=force_refresh)
    except Exception:
        values, failures = {}, ["한국장 수급 자동 조회 실패"]
    trade_date = _flow_today()
    captured_at = attempted_at.replace(second=0, microsecond=0).isoformat()

    try:
        database.save_kr_flow_snapshot(trade_date, captured_at, values)
    except Exception:
        failures.append("장중 수급 스냅숏 저장 실패")

    try:
        snapshots = database.list_kr_flow_snapshots(trade_date)
    except Exception:
        snapshots = [{**values, "captured_at": captured_at}]

    # 출처와 자료 기준시각은 DB 스키마를 바꾸지 않고 표시용으로만 최신 스냅숏에
    # 실어 보낸다(판정 표의 '대체' 구분과 신선도 계산에 쓴다).
    _passthrough = [
        "investor_flow_source", "investor_flow_as_of",
        "samsung_quote_as_of", "hynix_quote_as_of",
    ]
    _extra = {k: values[k] for k in _passthrough if values.get(k) is not None}
    if _extra and snapshots:
        snapshots = list(snapshots)
        snapshots[-1] = {**dict(snapshots[-1]), **_extra}

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
        # 직전 1분 값과 비교하면 판정이 매분 뒤집힌다(2026-07-29 실측 17/38).
        # 다른 항목과 같은 기준으로 몇 분 전 값과 비교한다.
        previous_value = _value_before(
            snapshots[:-1],
            "foreign_futures_net_contracts",
            seconds=kr_intraday_flow.TREND_WINDOW_SECONDS,
            latest_at=_now_seoul(),
        )
        foreign_futures = kr_intraday_flow.ForeignFuturesFlowSnapshot(
            net_contracts=int(values["foreign_futures_net_contracts"]),
            previous_net_contracts=previous_value,
            as_of=_now_seoul(),
            source=values.get("foreign_futures_source") or "네이버 선물 투자자동향(지연)",
            confidence="delayed_public",
            available=True,
        )

    result = kr_intraday_flow.build_result_from_snapshots(
        snapshots,
        foreign_futures=foreign_futures,
        # 기준시각은 한국시각이다. 넘기지 않으면 datetime.now()가 쓰이는데
        # 스트림릿 클라우드는 UTC라 9시간 어긋난 값으로 신선도를 재게 된다.
        now=_now_seoul(),
    )
    st.session_state["kr_flow_result"] = result
    st.session_state["kr_flow_failures"] = failures
    st.session_state["kr_flow_last_checked_at"] = _now_seoul()
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

# 개인은 계산은 되고 있었는데 이 목록에 없어서 표에 안 나왔다 — 기관이 사는 것만
# 보이고 누가 파는지는 안 보였다(2026-07-29 사용자 지적: 개인 -1조 7,814억).
_FLOW_TABLE_KEYS = (
    "program_total", "arbitrage", "non_arbitrage", "market_basis",
    "foreign_futures", "foreign_cash", "personal", "institution", "securities",
    "investment_trust", "private_fund", "fund",
    "electronics_turnover", "electronics_institution", "samsung", "hynix",
)


# 상세 표의 값별 색 — 같은 값은 어느 시장 카드에서든 같은 색으로 보이게 한다.
# 판정 칸은 마크만이 아니라 '표 읽는 법'과 똑같은 뜻 글자를 함께 쓴다
# (2026-07-22 사용자 지시: "⭕ 긍정(신호 켜짐)"처럼 마크와 내용을 같이 넣을 것).
# 눈금 안에 들어갈 짧은 단계 이름 — 카드 제목의 긴 문구(🟡 방향 혼조 …)는 반원
# 안에 넣으면 넘친다. 뜻이 달라지지 않는 선에서 줄인 이름만 쓴다.
_VERDICT_SHORT = {
    kr_intraday_flow.ReboundVerdict.NOT_CONFIRMED: "반전 없음",
    kr_intraday_flow.ReboundVerdict.WATCHING: "일부 켜짐",
    kr_intraday_flow.ReboundVerdict.PROXY_CONFIRMED: "반등 유력",
    kr_intraday_flow.ReboundVerdict.CONFIRMED: "반등 확인",
    us_market_signal_engine.UsMarketVerdict.RISK_OFF: "위험회피",
    us_market_signal_engine.UsMarketVerdict.MIXED: "방향 혼조",
    us_market_signal_engine.UsMarketVerdict.RISK_ON_EARLY: "선호 초기",
    us_market_signal_engine.UsMarketVerdict.RISK_ON: "위험선호",
}

# 나쁜 쪽 → 좋은 쪽 순서. 눈금 왼쪽부터 이 차례로 놓인다.
KR_VERDICT_ORDER = (
    kr_intraday_flow.ReboundVerdict.NOT_CONFIRMED,
    kr_intraday_flow.ReboundVerdict.WATCHING,
    kr_intraday_flow.ReboundVerdict.PROXY_CONFIRMED,
    kr_intraday_flow.ReboundVerdict.CONFIRMED,
)
US_VERDICT_ORDER = (
    us_market_signal_engine.UsMarketVerdict.RISK_OFF,
    us_market_signal_engine.UsMarketVerdict.MIXED,
    us_market_signal_engine.UsMarketVerdict.RISK_ON_EARLY,
    us_market_signal_engine.UsMarketVerdict.RISK_ON,
)

_SIGNAL_GAUGE_CSS = """
.sig-body { display: flex; flex-wrap: wrap; align-items: center; gap: 1.1rem; margin-top: 10px; }
.sig-gauge { flex: 0 0 auto; }
.sig-gauge .fg-gauge { width: 190px; height: 127px; }
.sig-gauge .fg-zone { font-size: 21px; }
.sig-current-score { margin-top: -0.35rem; text-align: center;
  font-size: 1.05rem; font-weight: 900; }
.sig-prev-score { margin-top: 0.08rem; text-align: center;
  font-size: 0.83rem; font-weight: 800; }
.sig-counts { flex: 0 0 auto; min-width: 168px; }
.sig-text { flex: 1 1 320px; min-width: 260px; }
@media (max-width: 720px) { .sig-body { gap: 0.7rem; } .sig-gauge .fg-gauge { width: 160px; height: 107px; } }
"""

# 이 칸은 값이 올랐나 내렸나가 아니라 '반등 신호가 켜졌나'를 답한다.
# 예전 글자 '중립(보합)'은 -12.86%인 삼성전자와 +2조 순매수인 기관계에 똑같이
# 붙었다. 보합은 "거의 안 움직였다"는 뜻이라 둘 다 틀린 말이었다
# (2026-07-29 사용자 지적: "뭐가 중립이란 말이냐").
_STATUS_TEXT = {
    market_signal_common.SignalStatus.POSITIVE: "켜짐",
    market_signal_common.SignalStatus.NEUTRAL: "애매",
    market_signal_common.SignalStatus.NEGATIVE: "아님",
    market_signal_common.SignalStatus.UNKNOWN: "자료 없음",
}

_TIMING_COLOR = {
    "먼저 움직임": "#4da6ff", "뒤따라옴": "#e6e6e6", "이미 늦음": "#ff9d3b",
    "가짜": "#ef4444", "모름": "#9ca3af",
}
# 값을 어디서 가져왔는지. 증권사 원본이면 초록, 공개 화면에서 긁어온 것이면 주황.
_SOURCE_COLOR = {
    "증권사": "#22c55e", "HTS 입력": "#22c55e", "시세": "#22c55e",
    "네이버": "#ff9d3b", "네이버 시세": "#ff9d3b", "뉴스": "#ff9d3b",
    "없음": "#9ca3af",
}
# 색은 등급으로 정하고, 글자는 '3분 전'처럼 실제 시간을 적는다.
_FRESHNESS_COLOR = {
    "정상": "#22c55e", "지연": "#ff9d3b", "오래됨": "#ef4444", "확인 필요": "#9ca3af",
}

# 범례를 접어 둔다(2026-07-29 사용자 지시). 스트림릿은 펼침(expander) 안에 펼침을
# 못 넣으므로 HTML <details>를 쓴다 — 표 자체가 이미 펼침 안에 있기 때문이다.
_SIGNAL_TABLE_LEGEND_HTML = """
<style>
.msig-legend { background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.12);
  border-radius:8px; padding:10px 14px; margin-bottom:10px; font-size:0.9rem; line-height:1.8; }
.msig-legend > summary { font-weight:800; color:#e6e6e6; cursor:pointer; list-style:none; }
.msig-legend > summary::-webkit-details-marker { display:none; }
.msig-legend > summary::before { content:"▸ "; color:#9aa0aa; }
.msig-legend[open] > summary::before { content:"▾ "; }
.msig-legend > summary .msig-legend-hint { font-weight:600; color:#9ca3af; }
.msig-legend[open] > summary .msig-legend-hint { display:none; }
</style>
<details class="msig-legend">
  <summary>표 읽는 법 <span class="msig-legend-hint">(눌러서 펼치기)</span></summary>
  <div style="margin-top:8px;">
  <b style="color:#e6e6e6;">이 표는 “지금 반등이 시작됐나”를 항목마다 따로 묻는 표입니다.</b>
  값이 올랐는지 내렸는지를 매기는 표가 아닙니다.<br>
  <b style="color:#9ca3af;">반등 신호인가</b> :
  ⭕ <span style="color:#22c55e;">켜짐</span> = 반등 쪽 신호 ·
  🟡 <span style="color:#eab308;">애매</span> = 반등이라 하기엔 이름 ·
  ❌ <span style="color:#ef4444;">아님</span> = 오히려 반대 ·
  ⚪ <span style="color:#9ca3af;">자료 없음</span> = 값을 못 가져옴<br>
  <span style="margin-left:3.2em;color:#c9ced6;">
  주가가 많이 빠진 종목도 저점에서 조금 오르면 <b>🟡 애매</b>가 됩니다 —
  “많이 빠졌다”가 아니라 “아직 반등이라 부르기 이르다”는 뜻입니다.
  </span><br>
  <b style="color:#9ca3af;">언제 나오는 신호</b> :
  <span style="color:#4da6ff;">먼저 움직임</span> = 시장보다 앞서 움직이는 항목 ·
  <span style="color:#e6e6e6;">뒤따라옴</span> = 결과로 따라오는 항목 ·
  <span style="color:#ff9d3b;">이미 늦음</span> = 지나간 흐름일 수 있음<br>
  <b style="color:#9ca3af;">이 값 어디서 왔나</b> :
  <span style="color:#22c55e;">증권사</span> = 증권사에서 받은 값 ·
  <span style="color:#ff9d3b;">네이버</span> = 네이버 화면에 공개된 값(증권사에서 못 받아 대신 쓰는 것, 몇 분 늦습니다) ·
  <span style="color:#22c55e;">HTS 입력</span> = 사람이 직접 적어 넣은 값 ·
  <span style="color:#9ca3af;">없음</span> = 가져올 데가 없음<br>
  <b style="color:#9ca3af;">몇 분 된 값</b> :
  <span style="color:#22c55e;">방금</span>·<span style="color:#ff9d3b;">3분 전</span>처럼
  그 값이 몇 분 전 것인지 그대로 적습니다.
  <span style="color:#22c55e;">초록</span>은 2분 이내, <span style="color:#ff9d3b;">주황</span>은 5분 이내,
  <span style="color:#ef4444;">빨강</span>은 5분이 넘은 값입니다.
  <span style="color:#9ca3af;">모름</span>은 그 자료에 시각이 안 적혀 있어 언제 것인지 알 수 없다는 뜻입니다.<br>
  <b style="color:#9ca3af;">└ 표시와 개인</b> :
  <b>기관계</b>는 금융투자·투신·사모·기금을 <b>모두 더한 값</b>입니다. 그래서 아래 └ 항목들은
  기관계와 같은 돈이며, 판정 칸에 ⭕ 대신
  <span style="color:#9ca3af;">‘기관계에 포함’</span>이라고 적고 위 ‘켜진 신호 N개’에도 기관계 하나만 셉니다.
  <b>개인</b>은 기관·외국인이 사면 파는 반대편이라 역시
  <span style="color:#9ca3af;">‘참고만’</span>으로 두고 개수에 넣지 않습니다. 값은 그대로 보여줍니다.<br>
  <b style="color:#9ca3af;">판정이 자주 바뀌지 않게</b> :
  방향은 직전 1분이 아니라 <b>최근 5분</b>을 통째로 보고 정합니다. 1분마다 비교하면
  자료가 조금만 출렁여도 켜짐과 애매가 계속 뒤집힙니다.<br>
  <b style="color:#9ca3af;">‘자료 없음’의 뜻</b> :
  값이 0이라는 게 아니라 <b>못 가져왔다</b>는 뜻입니다. 이유는 두 가지이고 설명 칸에 나뉘어 있습니다 —
  <span style="color:#e6e6e6;">‘스냅숏 부족’</span>은 자료는 오는데 15분 치가 아직 안 쌓인 것(시간이 지나면 채워집니다),
  <span style="color:#e6e6e6;">‘수급 확인 필요’</span>는 증권사에서 못 받아온 것입니다.
  확인 안 된 값을 임의로 지어내지 않는 것이 이 화면의 원칙입니다.
  </div>
</details>
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
        # 전에는 "온라인 자비스에서는 정상 조회됩니다"라고 적었는데, 온라인에도 키가
        # 없어서 그 화면을 보면서 읽으면 틀린 말이 된다(2026-07-24 사용자 확인).
        # 키가 없어도 판정은 계속 돌아간다는 사실을 대신 알려준다.
        return (
            "증권사(KIS) 조회 키가 없어 프로그램 매매·차익/비차익·선물 베이시스는 "
            "읽지 못합니다(이 항목들은 KIS에만 공개됩니다). 투자자별 수급은 네이버 "
            "지연 공개치로 대신 채우고 있어 판정은 계속 돌아갑니다 — 재료가 덜 "
            "들어갈 뿐 값을 지어내지는 않습니다."
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


def _verdict_stage_number(verdict, verdict_order) -> int | None:
    """판정이 전체 단계 중 몇 번째인지 돌려준다(예: 일부 켜짐 = 2/4단계)."""
    verdict_order = tuple(verdict_order or ())
    if not verdict_order or verdict not in verdict_order:
        return None
    return verdict_order.index(verdict) + 1


def _verdict_needle_position(verdict, verdict_order) -> float | None:
    """네 단계 판정의 바늘을 해당 구간 중앙에 놓을 내부 위치값을 돌려준다."""
    stage = _verdict_stage_number(verdict, verdict_order)
    if stage is None:
        return None
    step = 100 / len(tuple(verdict_order))
    return step * (stage - 0.5)


def _saved_foreign_futures(snapshots):
    """저장된 스냅숏에서 당시 외국인 선물 상태를 복원한다."""
    known = []
    for row in snapshots or []:
        value = row.get("foreign_futures_net_contracts")
        if value is None:
            continue
        stamp = row.get("captured_at")
        if isinstance(stamp, str):
            try:
                stamp = datetime.fromisoformat(stamp)
            except ValueError:
                stamp = None
        known.append((int(value), stamp, row.get("foreign_futures_source")))
    if not known:
        return None
    current, as_of, source = known[-1]
    previous = known[-2][0] if len(known) >= 2 else None
    return kr_intraday_flow.ForeignFuturesFlowSnapshot(
        net_contracts=current,
        previous_net_contracts=previous,
        as_of=as_of,
        source=source or "저장된 공개 수급",
        confidence="saved",
        available=True,
    )


def _previous_kr_flow_stage() -> dict | None:
    """저장된 직전 평일 스냅숏으로 직전 판정 단계를 다시 계산한다."""
    try:
        today = _flow_today()
        saved = database.list_previous_kr_flow_snapshots(today)
        snapshots = list(saved.get("rows") or [])
        if not snapshots:
            return None
        last_stamp = snapshots[-1].get("captured_at")
        if isinstance(last_stamp, str):
            last_stamp = datetime.fromisoformat(last_stamp)
        result = kr_intraday_flow.build_result_from_snapshots(
            snapshots,
            foreign_futures=_saved_foreign_futures(snapshots),
            # 과거 자료를 현재시각과 비교하면 모두 '오래됨'이 되므로 당시 마지막
            # 스냅숏 시각을 판정시각으로 쓴다.
            now=last_stamp,
        )
        score = _verdict_needle_position(result.verdict, KR_VERDICT_ORDER)
        if score is None:
            return None
        return {
            "score": score,
            "label": _VERDICT_SHORT.get(result.verdict) or str(result.verdict),
            "color": _FLOW_VERDICT_STYLE.get(
                result.verdict, ("", "#9ca3af", "")
            )[1],
            "trade_date": saved.get("trade_date"),
            # 정확히 직전 평일 자료일 때만 '전일'이라고 부른다. 저장이 며칠 비었거나
            # 평일 휴장일을 건너뛴 자료라면 날짜와 함께 '직전 저장'으로 밝힌다.
            "period_label": (
                "전일"
                if saved.get("trade_date") == _expected_previous_weekday(today)
                else "직전 저장"
            ),
        }
    except Exception:
        return None


def _verdict_gauge_html(
    result, verdict_style, verdict_order, previous_stage=None, *, show_position_score=False
) -> str:
    """판정을 반원 눈금 위에 올린다 (2026-07-24 사용자 요청).

    숫자는 승률이나 매수점수가 아니라 네 판정 구간의 중앙 위치값이다.
    한국장 카드에서만 현재·전일을 같은 0~100 눈금(12·38·62·88)으로 표시한다.

    verdict_order는 나쁜 쪽 → 좋은 쪽 순서다. 목록에 없는 판정(데이터 부족)은
    바늘 없이 눈금만 그린다.
    """
    step = 100 / len(verdict_order)
    zones = []
    for index, verdict in enumerate(verdict_order):
        color = verdict_style[verdict][1]
        name = _VERDICT_SHORT.get(verdict) or str(verdict)
        zones.append((round(step * (index + 1)), name, color))

    score = _verdict_needle_position(result.verdict, verdict_order)

    counts = {
        market_signal_common.SignalStatus.POSITIVE: 0,
        market_signal_common.SignalStatus.NEGATIVE: 0,
        market_signal_common.SignalStatus.NEUTRAL: 0,
        market_signal_common.SignalStatus.UNKNOWN: 0,
    }
    # 하위 내역(금융투자·투신·사모·기금)과 반대 주체(개인)는 세지 않는다.
    # 넷을 따로 세면 기관 순매수 한 건이 '켜진 신호 4개'로 부풀려진다(2026-07-29).
    for signal in market_signal_common.counted_signals(result.signals):
        if signal.status in counts:
            counts[signal.status] += 1
    rows = [
        ("켜진 신호", "켜짐", counts[market_signal_common.SignalStatus.POSITIVE], "#22c55e"),
        ("반대 신호", "아님", counts[market_signal_common.SignalStatus.NEGATIVE], "#ef4444"),
        ("애매한 신호", "애매", counts[market_signal_common.SignalStatus.NEUTRAL], "#9ca3af"),
        ("못 읽은 항목", "자료 없음", counts[market_signal_common.SignalStatus.UNKNOWN], "#71717a"),
    ]
    row_tuples = [(label, note, f"{value}개", color, value == 0)
                  for label, note, value, color in rows]

    score_html = ""
    if show_position_score and score is not None:
        current_color = verdict_style.get(result.verdict, ("", "#9ca3af", ""))[1]
        score_html = (
            f"<div class='sig-current-score' style='color:{current_color}'>"
            f"{score:.0f}</div>"
        )
    if previous_stage and previous_stage.get("score") is not None:
        day = str(previous_stage.get("trade_date") or "")
        day = day[5:].replace("-", ".") if len(day) >= 10 else ""
        day_text = f"({day})" if day else ""
        period_label = str(previous_stage.get("period_label") or "직전 저장")
        previous_color = str(previous_stage.get("color") or "#9ca3af")
        score_html += (
            f"<div class='sig-prev-score' style='color:{previous_color}'>"
            f"{period_label}{day_text} {float(previous_stage['score']):.0f} · "
            f"{previous_stage.get('label') or '판정 확인'}</div>"
        )

    return (
        "<div class='sig-gauge'>"
        f"{gauge_ui.gauge_svg(score, zones, ticks=(), show_score=False)}"
        f"{score_html}</div>"
        f"<div class='sig-counts'>{gauge_ui.rows_html(row_tuples)}</div>"
    )


def render_market_signal_card(
    result, *, verdict_style, core_display, table_keys, detail_title, detail_caption,
    table_key, diagnosis_text=None, verdict_order=(), previous_stage=None,
    show_position_score=False, falling_market=None,
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
        f"<div style='font-size:0.9rem;color:{text};opacity:0.95;margin-top:8px;'>못 읽은 항목이 있는 이유: {_cause}</div>"
        if _cause and _unknown_count else ""
    )

    # 지수가 무너지는 날이면 맨 위에도 한 줄 적는다. 표를 안 펼치는 날이
    # 더 많아서, 꼬리표만 달아 두면 못 보고 지나간다.
    _falling_html = ""
    if falling_market:
        _falling_html = (
            f"<div style='font-size:0.95rem;color:{_DOWN_COLOR};font-weight:800;margin-top:8px;'>"
            f"{falling_market['label']} {falling_market['change_pct']:+.2f}% — 지금은 하락장입니다. "
            f"켜진 '긍정'은 <b>지수가 빠지는 중에</b> 나온 순매수입니다.</div>"
        )
    _cause_html = _falling_html + _cause_html

    # 판정을 눈금 위에 올려 지금이 어느 단계인지 한눈에 보이게 한다(2026-07-24).
    _gauge_html = (
        _verdict_gauge_html(
            result,
            verdict_style,
            tuple(verdict_order),
            previous_stage=previous_stage,
            show_position_score=show_position_score,
        )
        if verdict_order else ""
    )
    st.markdown(f"<style>{gauge_ui.CSS}{_SIGNAL_GAUGE_CSS}</style>", unsafe_allow_html=True)
    # 줄바꿈·들여쓰기 없이 한 줄로 만든다. 여러 줄에 걸쳐 들여쓰면 빈 부분(예: 원인
    # 문구가 없을 때)에서 마크다운이 다음 줄을 코드블록으로 잡아 '</div>'가 화면에
    # 글자로 찍힌다(2026-07-24 실제 발생).
    st.markdown(
        f'<div style="background-color:{bg};border:2px solid {border};border-radius:10px;'
        f'padding:16px;margin-top:8px;">'
        f'<div style="font-size:1.35rem;font-weight:800;color:{text};">{result.verdict_label}</div>'
        f'<div style="font-size:0.85rem;color:{text};opacity:0.85;margin-top:4px;">'
        f'{_as_of_label} · {result.data_status}</div>'
        f'<div class="sig-body">{_gauge_html}<div class="sig-text">'
        f'<div style="font-size:1.0rem;color:{text};line-height:1.5;">{result.headline}</div>'
        f'<div style="font-size:0.9rem;color:{text};opacity:0.9;margin-top:8px;">'
        f'흐름: {result.flow_note}</div>'
        f'{_cause_html}</div></div></div>',
        unsafe_allow_html=True,
    )

    for warning in result.warnings:
        st.warning(warning)

    # 핵심 4개와 신호 목록도 접어 둔다 — 첫 화면이 설명으로 가득 찼다
    # (2026-07-25 사용자 지시: "다 숨겨라"). 값·판정은 그대로다.
    with st.expander("핵심 4개 · 신호 목록 보기", expanded=False):
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
                      <div style="font-size:1.05rem;font-weight:700;color:{_VALUE_COLOR};">
                        {_colorize_signed(signal.display_value)}
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

    # 상세 표는 접어 둔다 — 폰에서 이 표가 첫 화면을 다 먹어 정작 봐야 할 카드가
    # 한참 밑으로 밀렸다(2026-07-25 사용자 지시: "눌러야 내용이 나오도록").
    # 표 위 범례는 펼쳤을 때 같이 보인다.
    # 한국장 판정에는 장중이었는지가 실려 온다. 미국 카드에는 없으므로 기본은 장중.
    _market_closed = not getattr(result, "session_open", True)

    with st.expander(detail_title, expanded=False):
        st.markdown(_SIGNAL_TABLE_LEGEND_HTML, unsafe_allow_html=True)
        _rows_html = []
        for key in table_keys:
            signal = result.signal(key)
            if signal is None:
                continue
            status_color = market_signal_common.STATUS_COLOR[signal.status]
            timing_text = market_signal_common.TIMING_LABEL[signal.timing]
            source_text = market_signal_common.source_word(signal)
            # 글자는 '3분 전'처럼 실제 시간, 색은 등급으로 칠한다. 장이 끝난 뒤에는
            # '장 마감값'이라고 적고 초록으로 둔다 — 종가는 늦은 값이 아니다.
            fresh_text = market_signal_common.freshness_text(
                signal.freshness_seconds, closed=_market_closed
            )
            fresh_color = (
                "#22c55e" if (_market_closed and signal.freshness_seconds is not None)
                else _FRESHNESS_COLOR.get(
                    market_signal_common.freshness_label(signal.freshness_seconds), "#e6e6e6"
                )
            )
            # 기관계를 쪼갠 하위 항목은 이름 앞에 └를 붙여 눈으로 계층이 보이게 한다.
            name_text = signal.label
            if not signal.counts_toward_totals and signal.key != "personal":
                name_text = f"└ {signal.label}"
            # 개수에서 뺀 줄은 ⭕/🟡을 찍지 않는다. 표에 초록이 넷 보이는데 카드는
            # '켜진 신호 1개'라고 하면 앞뒤가 안 맞아 보인다(2026-07-29 사용자 지적).
            if signal.exclusion_note:
                verdict_cell = signal.exclusion_note
                verdict_color = "#9ca3af"
            else:
                verdict_cell = (
                    f"{market_signal_common.STATUS_MARK[signal.status]} "
                    f"{_STATUS_TEXT[signal.status]}"
                    f"{_falling_tag(signal, falling_market)}"
                )
                verdict_color = status_color
            _rows_html.append(
                "<tr>"
                f"<td class='msig-name'>{name_text}</td>"
                f"<td style='color:{_VALUE_COLOR};font-weight:700'>"
                f"{_colorize_signed(signal.display_value)}</td>"
                f"<td style='color:{verdict_color};font-weight:700;white-space:nowrap'>"
                f"{verdict_cell}</td>"
                f"<td style='color:{_TIMING_COLOR.get(timing_text, '#e6e6e6')};font-weight:700'>{timing_text}</td>"
                f"<td style='color:{_SOURCE_COLOR.get(source_text, '#e6e6e6')};font-weight:700'>{source_text}</td>"
                f"<td class='msig-reason'>{signal.reason}</td>"
                f"<td style='color:{fresh_color};font-weight:700'>{fresh_text}</td>"
                "</tr>"
            )
        if _rows_html:
            st.markdown(
                _SIGNAL_TABLE_CSS
                # 칸 이름이 곧 그 칸의 질문이 되게 적는다. '판정·구분·신호세기·
                # 신선도'는 무엇에 대한 것인지 이름만 봐서는 알 수 없었다
                # (2026-07-29 사용자 지적: "신호세기가 무슨 신호에 대한 세기냐").
                + "<table class='msig-table'><thead><tr>"
                "<th>항목</th><th>지금 값</th><th>반등 신호인가</th><th>언제 나오는 신호</th>"
                "<th>이 값 어디서 왔나</th><th>왜 그렇게 봤나</th><th>몇 분 된 값</th></tr></thead>"
                f"<tbody>{''.join(_rows_html)}</tbody></table>",
                unsafe_allow_html=True,
            )
        st.caption(detail_caption)


def _kr_flow_auto_due(result, last_attempt, now=None) -> bool:
    """최초·새 거래일·장중 1분 경과 때 자동 조회할지 판정한다."""
    now = now or _now_seoul()
    if now.tzinfo is None:
        now = now.replace(tzinfo=_SEOUL_TZ)
    else:
        now = now.astimezone(_SEOUL_TZ)
    if isinstance(last_attempt, str):
        try:
            last_attempt = datetime.fromisoformat(last_attempt)
        except ValueError:
            last_attempt = None
    if last_attempt is not None:
        if last_attempt.tzinfo is None:
            last_attempt = last_attempt.replace(tzinfo=_SEOUL_TZ)
        else:
            last_attempt = last_attempt.astimezone(_SEOUL_TZ)
    if result is None or last_attempt is None or last_attempt.date() != now.date():
        return True
    in_session = (
        now.weekday() < 5
        and datetime.strptime("09:00", "%H:%M").time()
        <= now.time()
        <= datetime.strptime("15:30", "%H:%M").time()
    )
    return in_session and now - last_attempt >= timedelta(seconds=55)


@st.fragment(run_every=60)
def render_kr_flow_card():
    """🎯 한국장 기관 수급 현황. 0단계 결과 바로 아래에 놓인다."""
    st.markdown("### 🎯 한국장 기관 수급 현황")
    st.caption(
        "지금 기관이 들어오는 장인지, 무엇이 먼저 움직였는지를 읽어줍니다. "
        "장중에는 1분마다 자동 확인하며, 버튼을 누르면 즉시 다시 조회합니다."
    )

    clicked = st.button("수급 다시 확인", key="kr_flow_refresh")
    result = st.session_state.get("kr_flow_result")
    if clicked:
        with st.spinner("장중 수급 확인 중..."):
            result = run_kr_flow_check(force_refresh=True)
    elif _kr_flow_auto_due(
        result, st.session_state.get("kr_flow_last_attempt_at"), _now_seoul()
    ):
        with st.spinner("장중 수급 자동 확인 중..."):
            result = run_kr_flow_check()

    render_market_signal_card(
        result,
        verdict_style=_FLOW_VERDICT_STYLE,
        core_display=_FLOW_CORE_DISPLAY,
        table_keys=_FLOW_TABLE_KEYS,
        detail_title="한국장 전체 수급 상세",
        detail_caption=(
            "‘기금·연기금’은 KIS 원본 필드명이 기금입니다. 시장베이시스는 외국인 선물이 "
            "얼마나 사고팔았는지를 못 구했을 때 대신 보는 다른 지표이며, 수급값 자체가 "
            "아닙니다. ‘기관계’는 금융투자·투신·사모·기금을 모두 더한 값입니다."
        ),
        table_key="kr_flow_detail_table",
        # 지수가 크게 빠지는 날에는 '긍정' 옆에 (하락장)을 적는다. 판정은
        # 그대로 두고 상황만 알려 준다(2026-07-29 사용자 선택 1번).
        falling_market=falling_market_note(),
        diagnosis_text=kr_flow_diagnosis,
        verdict_order=KR_VERDICT_ORDER,
        previous_stage=_previous_kr_flow_stage(),
        show_position_score=True,
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
        verdict_order=US_VERDICT_ORDER,
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

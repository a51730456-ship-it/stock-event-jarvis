"""시장 판단 화면의 데이터 수집과 렌더링.

자비스1·2·3 어디에도 속하지 않는 독립 화면(pages/0_시장판단.py)에서 쓴다.
app.py를 import하면 자비스1 앱 전체가 실행되므로, 필요한 조회 로직은 여기에 둔다.

카드는 종목을 고르는 물건이 아니다. 지금 시장이 어떤 상태이고 무엇이 앞서
움직이는지 읽어서, 사용자가 자비스1·2·3과 대조해 스스로 판단할 재료를 준다.
그래서 결론 문구에 매수·매도 지시를 넣지 않는다.
"""

from __future__ import annotations

import importlib
import math
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
MODULE_REVISION = 2026081310


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


def _fetch_previous_us_quote(ticker, as_of_date):
    """현재 표시 거래일 바로 전 미국 거래일의 종가 등락률을 읽는다.

    현재 카드의 ``as_of_date``보다 앞선 행만 쓰므로 장중 오늘 행이 있든, 장 마감
    뒤 오늘 행이 완성됐든 항상 화면의 '당일'보다 한 거래일 앞선 값을 고른다.
    """
    try:
        target = datetime.strptime(str(as_of_date), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return {"ok": False, "error": "기준 거래일 없음"}

    start = (target - timedelta(days=20)).isoformat()
    end = (target + timedelta(days=1)).isoformat()
    history = price_data.get_price_history(ticker, start, end)
    if history is None or len(history) < 3 or "Close" not in history.columns:
        return {"ok": False, "error": "전일 시세 없음"}
    try:
        prior = history[history.index.date < target]
        closes = prior["Close"].dropna().astype(float)
        if len(closes) < 2:
            return {"ok": False, "error": "전일 비교 시세 부족"}
        current = float(closes.iloc[-1])
        prev_close = float(closes.iloc[-2])
        trade_date = closes.index[-1].strftime("%Y-%m-%d")
        if current <= 0 or prev_close <= 0:
            return {"ok": False, "error": "전일 시세 비정상"}
        return {
            "ok": True,
            "current": current,
            "prev_close": prev_close,
            "change_pct": _safe_pct_diff(current, prev_close),
            "trade_date": trade_date,
        }
    except Exception:
        return {"ok": False, "error": "전일 시세 해석 실패"}


@st.cache_data(ttl=900, show_spinner=False)
def _cached_previous_us_quotes(ticker_dates):
    """미국 전일 비교값은 완성된 일봉이라 15분 동안 재사용한다."""
    pairs = tuple(ticker_dates)
    if not pairs:
        return {}
    results = {}
    with ThreadPoolExecutor(max_workers=min(16, len(pairs))) as executor:
        futures = {
            executor.submit(_fetch_previous_us_quote, ticker, as_of_date): ticker
            for ticker, as_of_date in pairs
        }
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                results[ticker] = future.result()
            except Exception:
                results[ticker] = {"ok": False, "error": "전일 시세 조회 실패"}
    return results


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

    save_failed = False
    try:
        database.save_kr_flow_snapshot(trade_date, captured_at, values)
    except Exception as exc:
        save_failed = True
        failures.append(f"장중 수급 스냅숏 저장 실패 ({type(exc).__name__})")

    try:
        snapshots = database.list_kr_flow_snapshots(trade_date)
    except Exception:
        snapshots = []

    # DB에 못 쌓았어도 방금 읽은 값으로 화면은 채운다.
    # 2026-07-31 09:27 실발생: 장이 열린 지 25분이 지났는데 '스냅숏이 아직
    # 없습니다'만 떴다. 자료는 멀쩡히 오는데(기관 -5,182억·외국인 선물 +98계약)
    # DB 저장이 실패하자 방금 읽은 값까지 통째로 버린 탓이다.
    # 저장은 '쌓아 두기'용이지 '보여주기'의 전제가 아니다.
    if not snapshots and values:
        snapshots = [{**values, "captured_at": captured_at}]
        if not save_failed:
            failures.append("장중 수급 스냅숏이 아직 안 쌓였습니다 (방금 읽은 값으로 표시)")

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


# 카드 색 = (배경, 테두리, 글자).
#
# 배경은 **거의 검은 남색 계열**로 통일하고 판정 색은 테두리와 글자로만 낸다
# (2026-08-06 사용자 지적 "배경이 너무 누렇다"). 예전에는 판정 색을 배경에 통째로
# 깔아서(#4a2e05 같은 진한 갈색) 화면이 누렇게 떴다. 색은 아주 조금만 섞어
# 어느 판정인지 눈치채게 하고, 판정은 테두리와 글자가 말한다.
_FLOW_VERDICT_STYLE = {
    kr_intraday_flow.ReboundVerdict.VERY_BAD: ("#170f13", "#ef4444", "#fca5a5"),
    kr_intraday_flow.ReboundVerdict.CONFIRMED: ("#0d1714", "#22c55e", "#86efac"),
    kr_intraday_flow.ReboundVerdict.PROXY_CONFIRMED: ("#0d1717", "#14b8a6", "#99f6e4"),
    kr_intraday_flow.ReboundVerdict.WATCHING: ("#15140f", "#eab308", "#fde047"),
    kr_intraday_flow.ReboundVerdict.NOT_CONFIRMED: ("#16110d", "#f97316", "#fdba74"),
    kr_intraday_flow.ReboundVerdict.INSUFFICIENT_DATA: ("#131316", "#71717a", "#d4d4d8"),
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

_KR_STAGE_GUIDE = (
    "<b>5단계 기준</b> 하락 압력 큼(프로그램·베이시스·반도체가 함께 약함) → "
    "약세 신호 우세(반등 근거 부족) → 방향 엇갈림(긍정 신호 일부) → "
    "상승 신호 우세(수급·반도체가 함께 개선) → "
    "상승 여건 양호(외국인 선물·비차익·반도체가 모두 확인).<br>"
    "<b>판정 구성</b> 외국인 선물, 비차익·프로그램, 시장베이시스, "
    "삼성전자·SK하이닉스, 기관 수급을 함께 봅니다."
)


# 상세 표의 값별 색 — 같은 값은 어느 시장 카드에서든 같은 색으로 보이게 한다.
# 판정 칸은 마크만이 아니라 '표 읽는 법'과 똑같은 뜻 글자를 함께 쓴다
# (2026-07-22 사용자 지시: "⭕ 긍정(신호 켜짐)"처럼 마크와 내용을 같이 넣을 것).
# 눈금 안에 들어갈 짧은 단계 이름. 한국장·미국장이 같은 5단계 말을 쓴다.
# 2026-08-05 사용자 지시로 '좋음·나쁨' 대신 무엇이 우세한지를 적는 말로 바꿨다.
# 미국테마·한국테마 화면(regime_gauge_ui.ZONES)과 같은 다섯 이름이다.
_VERDICT_SHORT = {
    kr_intraday_flow.ReboundVerdict.VERY_BAD: "하락 압력 큼",
    kr_intraday_flow.ReboundVerdict.NOT_CONFIRMED: "약세 신호 우세",
    kr_intraday_flow.ReboundVerdict.WATCHING: "방향 엇갈림",
    kr_intraday_flow.ReboundVerdict.PROXY_CONFIRMED: "상승 신호 우세",
    kr_intraday_flow.ReboundVerdict.CONFIRMED: "상승 여건 양호",
    us_market_signal_engine.UsMarketVerdict.VERY_BAD: "하락 압력 큼",
    us_market_signal_engine.UsMarketVerdict.RISK_OFF: "약세 신호 우세",
    us_market_signal_engine.UsMarketVerdict.MIXED: "방향 엇갈림",
    us_market_signal_engine.UsMarketVerdict.RISK_ON_EARLY: "상승 신호 우세",
    us_market_signal_engine.UsMarketVerdict.RISK_ON: "상승 여건 양호",
}

# 나쁜 쪽 → 좋은 쪽 순서. 눈금 왼쪽부터 이 차례로 놓인다.
KR_VERDICT_ORDER = (
    kr_intraday_flow.ReboundVerdict.VERY_BAD,
    kr_intraday_flow.ReboundVerdict.NOT_CONFIRMED,
    kr_intraday_flow.ReboundVerdict.WATCHING,
    kr_intraday_flow.ReboundVerdict.PROXY_CONFIRMED,
    kr_intraday_flow.ReboundVerdict.CONFIRMED,
)
US_VERDICT_ORDER = (
    us_market_signal_engine.UsMarketVerdict.VERY_BAD,
    us_market_signal_engine.UsMarketVerdict.RISK_OFF,
    us_market_signal_engine.UsMarketVerdict.MIXED,
    us_market_signal_engine.UsMarketVerdict.RISK_ON_EARLY,
    us_market_signal_engine.UsMarketVerdict.RISK_ON,
)

_SIGNAL_GAUGE_CSS = """
.sig-body { display: flex; flex-wrap: wrap; align-items: center; gap: 1.1rem; margin-top: 10px; }
.sig-gauge { flex: 0 0 auto; }
/* 높이는 auto — 픽셀로 박으면 gauge_ui._HEIGHT를 고칠 때 반원이 찌그러진다.
   폭도 못박지 않는다 — 칸이 좁아지면 그림이 밖으로 삐져나온다(2026-08-06). */
.sig-gauge .fg-gauge { width: 100%; max-width: 190px; height: auto; }
.sig-gauge .fg-zone { font-size: 21px; }
/* 카드 맨 위 당일·전일 두 칸 — 아래 계기판 두 칸과 같은 모양·같은 테두리 색으로
   맞춘다(2026-08-06 사용자 지시 "칸을 밑에 처럼 구분하라"). 두 줄을 그냥 쌓아
   놓으면 "저게 구분한 거냐"는 말을 듣는다. */
.sig-head-pair { display:flex; flex-wrap:wrap; gap:.6rem; margin-bottom:.5rem; }
/* **min-width:0이 없으면 정확히 반으로 안 갈린다**(2026-08-06 상하님 지적).
   flex 칸은 기본이 min-width:auto라 안의 글이 길면 그만큼 칸이 밀려 늘어난다.
   당일 칸에는 기준시각까지 들어가 전일 칸보다 길어서 한쪽으로 치우쳤다. */
.sig-head-box { flex:1 1 260px; min-width:0; border:1px solid rgba(255,255,255,.16);
  border-radius:.7rem; padding:.5rem .85rem; background:rgba(5,9,16,.3); }
.sig-head-sub { overflow-wrap:anywhere; }
/* 손을 올리면 살짝 뜬다(2026-08-06 사용자 지시) — 단추와 같은 결이다.
   당일·전일 머리 칸, 계기판 상자, 설명 상자 셋 다. */
.sig-head-box, .sig-gauge-shell, .sig-story {
  transition: transform .12s ease-out, filter .12s ease-out,
              border-color .12s ease-out;
}
.sig-head-box:hover, .sig-gauge-shell:hover, .sig-story:hover {
  transform: translateY(-3px);
  filter: brightness(1.1);
}
.sig-head-today { border-color:rgba(68,240,161,.45); }
.sig-head-previous { border-color:rgba(77,166,255,.45); }
.sig-head-label { font-size:.82rem; font-weight:900; letter-spacing:.04em; }
.sig-head-today .sig-head-label { color:#44f0a1; }
.sig-head-previous .sig-head-label { color:#4da6ff; }
.sig-head-verdict { font-size:1.25rem; font-weight:800; margin-top:.12rem;
  line-height:1.25; }
.sig-head-sub { font-size:.8rem; opacity:.82; margin-top:.2rem; line-height:1.35; }
.sig-gauge-pair { display:flex; flex-wrap:wrap; align-items:flex-start; gap:.65rem; }
.sig-gauge-shell { padding:.35rem .55rem .55rem; border:1px solid rgba(255,255,255,.16);
  border-radius:.75rem; background:rgba(5,9,16,.34); }
.sig-gauge-shell .sig-gauge-title { text-align:center; color:#f3f4f6; font-size:.92rem;
  font-weight:900; letter-spacing:.04em; }
.sig-gauge-today { border-color:rgba(68,240,161,.34); }
.sig-gauge-today .sig-gauge-title { color:#44f0a1; }
.sig-gauge-previous { border-color:rgba(77,166,255,.34); }
.sig-gauge-previous .sig-gauge-title { color:#4da6ff; }
/* 폭을 235px로 못박으면 칸이 좁아질 때 그림이 상자 밖으로 삐져나온다
   (2026-08-06 상하님 캡처). 상자에 맞춰 줄어들되 235px보다 커지지는 않게 한다. */
.sig-gauge-shell .sig-gauge .fg-gauge { width:100%; max-width:235px; height:auto; }
.sig-gauge-shell .sig-gauge .fg-zone { font-size:20px; }
.sig-gauge-shell .sig-gauge .fg-tick { font-size:13px; }
.sig-gauge-shell .sig-counts { width:100%; min-width:0; margin-top:-.2rem; }
.sig-gauge-shell .sig-counts .fg-hist-row { padding:.1rem .15rem; }
.sig-gauge-shell .fg-needle, .sig-gauge-shell .fg-hub { display:none; }
.sig-speed-tick { stroke:rgba(245,247,250,.68); stroke-width:1.4; }
.sig-speed-tick.mid { stroke:rgba(255,255,255,.82); stroke-width:2.2; }
.sig-speed-tick.major { stroke:#f8fafc; stroke-width:3.2; }
.sig-speed-arrow { fill:#f8fafc; stroke:#dbeafe; stroke-width:1.2;
  filter:drop-shadow(0 0 5px rgba(255,255,255,.75)); }
/* 손을 올리면 바늘이 좌우로 살짝 흔들렸다 제자리로 온다(2026-08-06 사용자 요청).
   회전 중심은 바늘이 꽂힌 축(160,132)이다 — 안 맞추면 바늘이 통째로 미끄러진다.
   손이 닿을 때만 도는 움직임이라 화면을 다시 그려도 재생되지 않는다. */
@keyframes sig-needle-wiggle {
  0%   { transform: rotate(0deg); }
  22%  { transform: rotate(-5deg); }
  52%  { transform: rotate(3.5deg); }
  78%  { transform: rotate(-1.5deg); }
  100% { transform: rotate(0deg); }
}
.sig-gauge-shell:hover .sig-speed-arrow {
  transform-origin: 160px 132px;
  animation: sig-needle-wiggle .7s cubic-bezier(.3,.7,.4,1);
}
/* 화면에 뜰 때는 **왼쪽에서 제자리까지 쓸고 와서 살짝 흔들린 뒤** 멈춘다
   (2026-08-09 상하님 지시). 시작 각도는 값마다 달라 SVG가 --fg-sweep로 적어 준다.
   손을 올렸을 때는 위 흔들기만 돈다 — 그 규칙(.sig-gauge-shell:hover .sig-speed-arrow)이
   더 좁아서 이긴다. 순서가 아니라 좁기로 정해지므로 이 블록을 옮겨도 안전하다. */
@keyframes sig-needle-sweep {
  0%   { transform: rotate(var(--fg-sweep, 0deg)); }
  70%  { transform: rotate(0deg); }
  80%  { transform: rotate(-3.5deg); }
  90%  { transform: rotate(2deg); }
  100% { transform: rotate(0deg); }
}
.sig-speed-arrow {
  transform-origin: 160px 132px;
  animation: sig-needle-sweep .9s cubic-bezier(.22,1,.36,1) both;
}
@media (prefers-reduced-motion: reduce) {
  .sig-speed-arrow { animation: none; }
}
.sig-speed-hub-outer { fill:#f8fafc; stroke:#dbeafe; stroke-width:2; }
.sig-speed-hub-inner { fill:#111827; }
/* 전일은 흐리게 두되 **읽을 수 있어야** 한다. .48은 너무 흐려 전일이 어느 단계인지
   눈에 안 들어왔다(2026-08-06 상하님 지적 "당일과 전일 완전 구분해야지"). */
.sig-gauge-previous .sig-gauge { opacity:.82; filter:saturate(.88); }
.sig-gauge-previous .sig-counts { opacity:.9; }
.sig-current-score { margin-top: -0.35rem; text-align: center;
  font-size: 1.05rem; font-weight: 900; }
.sig-prev-score { margin-top: 0.08rem; text-align: center;
  font-size: 0.83rem; font-weight: 800; }
.sig-stage-guide { margin-top:.65rem; padding:.48rem .65rem; border-left:3px solid rgba(255,255,255,.36);
  background:rgba(5,9,16,.16); color:#e6e6e6; font-size:.88rem; line-height:1.55; }
.sig-counts { flex: 0 0 auto; min-width: 168px; }
.sig-text { flex: 1 1 320px; min-width: 260px; }
.sig-story-stack { display:grid; gap:.75rem; }
.sig-story { border-left:3px solid rgba(255,255,255,.2); padding:.35rem .7rem .45rem; }
.sig-story-title { font-size:.9rem; font-weight:900; margin-bottom:.32rem; }
.sig-story-today { border-left-color:#44f0a1; }
.sig-story-today .sig-story-title { color:#44f0a1; }
.sig-story-previous { border-left-color:#4da6ff; background:rgba(5,9,16,.1); }
.sig-story-previous .sig-story-title { color:#4da6ff; }
.sig-story-previous .sig-story-body { opacity:.78; }
/* **최소폭(255px·230px)을 박아 두면 당일 쪽이 전일 쪽보다 넓어진다**
   (2026-08-06 상하님 지적 "중간이 절반이 아니고 왼쪽으로 넘어간다").
   화면이 좁아지면 왼쪽 두 칸이 최소폭을 먼저 차지하고 오른쪽 설명만 짓눌렸다.
   minmax(0, ...)으로 두면 비율이 그대로 지켜져 **좌우가 정확히 반씩** 된다.
   좁은 화면은 아래 @media가 따로 맡는다. */
/* **머리 칸도 같은 판에 넣는다**(2026-08-07 상하님 지적 "전일이 당일 사이에
   끼어 있다"). 예전에는 당일·전일 머리 칸 두 개가 판 위에 따로 얹혀 있어서,
   화면이 좁아 판이 여러 줄로 접히면 전일 머리 칸과 전일 계기판 사이에 당일
   계기판·설명이 끼어들었다. 한 판에 넣으면 줄이 어떻게 접히든 당일끼리·
   전일끼리 붙어 다닌다. */
.sig-body-comparison { display:grid; align-items:stretch; overflow-x:auto;
  grid-template-areas:"today-head today-head previous-head previous-head"
                      "today-gauge today-story previous-gauge previous-story";
  grid-template-columns:minmax(0,.9fr) minmax(0,1.15fr)
                        minmax(0,.9fr) minmax(0,1.15fr);
  /* 안전장치 — 칸 이름(today-head 등)은 이 파일과 mobile_ui.py가 **나눠 갖고**
     있다. 배포 도중 한쪽만 새것이면 이름을 못 찾은 칸이 제멋대로 자리를 만들어
     글자가 세로로 한 자씩 서 버린다(2026-08-07 온라인 실발생 — 상하님 폰·태블릿
     캡처). 그때라도 칸이 고르게 나뉘도록 해 둔다. 두 모듈을 같이 읽게 고쳐
     뒀지만(페이지의 재읽기 목록), 다시 어긋나도 화면이 무너지지는 않게 한다. */
  grid-auto-columns:minmax(0,1fr); }
.sig-body-comparison .sig-gauge-pair,
.sig-body-comparison .sig-text,
.sig-body-comparison .sig-head-pair,
.sig-body-comparison .sig-story-stack { display:contents; }
.sig-body-comparison .sig-head-today { grid-area:today-head; }
.sig-body-comparison .sig-head-previous { grid-area:previous-head; }
.sig-body-comparison .sig-gauge-today { grid-area:today-gauge; }
.sig-body-comparison .sig-story-today { grid-area:today-story; }
.sig-body-comparison .sig-gauge-previous { grid-area:previous-gauge; }
.sig-body-comparison .sig-story-previous { grid-area:previous-story; }
@media (max-width: 720px) { .sig-body { gap: 0.7rem; } .sig-gauge .fg-gauge { width: 100%; max-width: 160px; height: auto; }
  .sig-gauge-pair { width:100%; gap:.45rem; } .sig-gauge-shell { flex:1 1 145px; padding:.3rem .25rem .15rem; }
  .sig-gauge-shell .sig-gauge .fg-gauge { width:100%; height:auto; } }
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

    # 저장 실패는 가장 먼저 알린다. 이걸 안 알려주면 화면에는 '스냅숏이 아직
    # 없습니다'만 뜨고, 자료는 멀쩡히 오는데 왜 안 보이는지 알 길이 없다
    # (2026-07-31 09:27 실발생).
    save_failed = [f for f in failures if "저장 실패" in f]
    if save_failed:
        return (
            f"수급 자료는 들어왔는데 저장이 실패했습니다({save_failed[0]}). "
            "화면은 방금 읽은 값으로 채웠으니 지금 값은 맞습니다. 다만 하루치가 "
            "쌓이지 않아 '15분 연속 유입' 같은 시간 비교 항목은 계속 비어 있습니다."
        )

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
    """판정이 전체 단계 중 몇 번째인지 돌려준다."""
    verdict_order = tuple(verdict_order or ())
    if not verdict_order or verdict not in verdict_order:
        return None
    return verdict_order.index(verdict) + 1


def _unread_note(result) -> str:
    """못 읽은 항목의 **이름**을 적는다 (2026-08-06 상하님 지적).

    '판정 구성'은 두 날이 같아 보이지만, 못 읽은 항목이 다르면 그날 실제로 본 것이
    다르다. 개수만으로는 그 차이를 알 수 없어 이름을 함께 적는다.
    """
    if result is None:
        return ""
    names = [
        str(signal.label)
        for signal in market_signal_common.counted_signals(result.signals)
        if signal.status is market_signal_common.SignalStatus.UNKNOWN
    ]
    return f" · 못 읽음: {' · '.join(names)}" if names else ""


def _signal_balance(result) -> float | None:
    """켜진 신호와 반대 신호 중 어느 쪽이 우세한가 (0~1). 없으면 None.

    애매한 신호와 못 읽은 항목은 **방향이 없으므로 빼고 센다.**
    """
    if result is None:
        return None
    positive = negative = 0
    for signal in market_signal_common.counted_signals(result.signals):
        if signal.status is market_signal_common.SignalStatus.POSITIVE:
            positive += 1
        elif signal.status is market_signal_common.SignalStatus.NEGATIVE:
            negative += 1
    total = positive + negative
    if total == 0:
        return None
    return positive / total


def _verdict_needle_position(verdict, verdict_order, result=None) -> float | None:
    """판정 단계 **안에서** 바늘 자리를 정한다.

    예전에는 늘 그 단계의 한가운데였다. 그래서 켜진 신호가 2개인 날과 8개인 날의
    바늘이 똑같은 자리를 가리켰다(2026-08-06 상하님 지적: "전일과 당일이 켜진 신호
    자체가 다른데 왜 화살표는 똑같냐"). 이제 같은 단계 안에서 켜짐·반대 비율만큼
    좌우로 옮긴다.

    **단계 밖으로는 절대 나가지 않는다** — 나가면 눈금에 적힌 단계 이름과 바늘이
    어긋나 화면이 거짓말을 한다. 구간 양 끝은 10%씩 비워 두어 경계에 붙지 않게 한다.
    """
    stage = _verdict_stage_number(verdict, verdict_order)
    if stage is None:
        return None
    step = 100 / len(tuple(verdict_order))
    low = step * (stage - 1)
    balance = _signal_balance(result)
    if balance is None:
        return low + step * 0.5
    return low + step * (0.1 + 0.8 * float(balance))


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


def _previous_kr_flow_comparison() -> tuple[object | None, dict | None]:
    """저장된 직전 평일 스냅숏으로 전일 판정 전체와 표시정보를 복원한다."""
    try:
        today = _flow_today()
        saved = database.list_previous_kr_flow_snapshots(today)
        snapshots = list(saved.get("rows") or [])
        if not snapshots:
            return None, None
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
            return None, None
        stage = {
            "score": score,
            "stage_number": _verdict_stage_number(result.verdict, KR_VERDICT_ORDER),
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
        return result, stage
    except Exception:
        return None, None


def _previous_kr_flow_stage() -> dict | None:
    """기존 호출부용 직전 판정 단계. 전체 비교에서 표시정보만 돌려준다."""
    _result, stage = _previous_kr_flow_comparison()
    return stage


def _speedometer_gauge_svg(score, zones) -> str:
    """첫 참고 캡처처럼 촘촘한 눈금과 굵은 화살표를 얹은 판정 계기판."""
    svg = gauge_ui.gauge_svg(
        score, zones, ticks=(0, 25, 50, 75, 100), show_score=False
    )
    center_x, center_y = 160.0, 132.0

    marks = []
    # 0~100을 2.5 간격으로 잘게 나눈다. 5 단위는 조금 길게, 25 단위는
    # 구간 경계가 바로 보이도록 가장 굵게 그린다.
    for index in range(41):
        value = index * 2.5
        angle = math.pi * (1 - value / 100)
        major = index % 10 == 0
        middle = index % 2 == 0
        inner = 96 if major else 103 if middle else 108
        outer = 116
        x1 = center_x + inner * math.cos(angle)
        y1 = center_y - inner * math.sin(angle)
        x2 = center_x + outer * math.cos(angle)
        y2 = center_y - outer * math.sin(angle)
        tick_class = "sig-speed-tick major" if major else (
            "sig-speed-tick mid" if middle else "sig-speed-tick"
        )
        marks.append(
            f"<line x1='{x1:.2f}' y1='{y1:.2f}' x2='{x2:.2f}' y2='{y2:.2f}' "
            f"class='{tick_class}'></line>"
        )

    arrow = ""
    if score is not None:
        value = max(0.0, min(100.0, float(score)))
        angle = math.pi * (1 - value / 100)
        tip_x = center_x + 101 * math.cos(angle)
        tip_y = center_y - 101 * math.sin(angle)
        dx, dy = tip_x - center_x, tip_y - center_y
        length = math.hypot(dx, dy) or 1.0
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        base_x, base_y = center_x - ux * 5, center_y - uy * 5
        shoulder_x, shoulder_y = tip_x - ux * 18, tip_y - uy * 18
        points = (
            f"{base_x + px * 6:.2f},{base_y + py * 6:.2f} "
            f"{shoulder_x + px * 3.2:.2f},{shoulder_y + py * 3.2:.2f} "
            f"{tip_x:.2f},{tip_y:.2f} "
            f"{shoulder_x - px * 3.2:.2f},{shoulder_y - py * 3.2:.2f} "
            f"{base_x - px * 6:.2f},{base_y - py * 6:.2f}"
        )
        # 게이지와 같은 규칙으로 **왼쪽 끝에서 제자리까지 쓸고 온다**
        # (2026-08-09 상하님 지시). 시작 각도만 여기서 적고 움직임은 CSS가 맡는다.
        arrow = (
            f"<polygon points='{points}' class='sig-speed-arrow' "
            f"style='--fg-sweep:{-1.8 * value:.2f}deg'></polygon>"
            f"<circle cx='{center_x}' cy='{center_y}' r='10' class='sig-speed-hub-outer'></circle>"
            f"<circle cx='{center_x}' cy='{center_y}' r='4.2' class='sig-speed-hub-inner'></circle>"
        )

    return svg.replace("</svg>", "".join(marks) + arrow + "</svg>")


def _verdict_gauge_html(
    result, verdict_style, verdict_order, previous_stage=None, *, show_position_score=False,
    comparison_result=None, comparison_label="전일", current_label_text="당일",
) -> str:
    """판정을 반원 눈금 위에 올린다 (2026-07-24 사용자 요청).

    바늘 위치값은 내부 계산용이며 화면에는 단계명만 표시한다.

    verdict_order는 나쁜 쪽 → 좋은 쪽 순서다. 목록에 없는 판정(데이터 부족)은
    바늘 없이 눈금만 그린다.
    """
    step = 100 / len(verdict_order)
    zones = []
    for index, verdict in enumerate(verdict_order):
        color = verdict_style[verdict][1]
        name = _VERDICT_SHORT.get(verdict) or str(verdict)
        zones.append((round(step * (index + 1)), name, color))

    score = _verdict_needle_position(result.verdict, verdict_order, result)

    def _count_row_tuples(target_result):
        counts = {
            market_signal_common.SignalStatus.POSITIVE: 0,
            market_signal_common.SignalStatus.NEGATIVE: 0,
            market_signal_common.SignalStatus.NEUTRAL: 0,
            market_signal_common.SignalStatus.UNKNOWN: 0,
        }
        # 하위 내역(금융투자·투신·사모·기금)과 반대 주체(개인)는 세지 않는다.
        # 넷을 따로 세면 기관 순매수 한 건이 '켜진 신호 4개'로 부풀려진다(2026-07-29).
        for signal in market_signal_common.counted_signals(target_result.signals):
            if signal.status in counts:
                counts[signal.status] += 1
        rows = [
            ("켜진 신호", "켜짐", counts[market_signal_common.SignalStatus.POSITIVE], "#22c55e"),
            ("반대 신호", "아님", counts[market_signal_common.SignalStatus.NEGATIVE], "#ef4444"),
            ("애매한 신호", "애매", counts[market_signal_common.SignalStatus.NEUTRAL], "#9ca3af"),
            ("못 읽은 항목", "자료 없음", counts[market_signal_common.SignalStatus.UNKNOWN], "#71717a"),
        ]
        return [(label, note, f"{value}개", color, value == 0)
                for label, note, value, color in rows]

    row_tuples = _count_row_tuples(result)

    score_html = ""
    if show_position_score and score is not None:
        current_color = verdict_style.get(result.verdict, ("", "#9ca3af", ""))[1]
        current_stage = _verdict_stage_number(result.verdict, verdict_order)
        current_label = _VERDICT_SHORT.get(result.verdict) or "판정 확인"
        score_html = (
            f"<div class='sig-current-score' style='color:{current_color}'>"
            f"{current_stage}단계 · {current_label}</div>"
        )
    if previous_stage and previous_stage.get("score") is not None:
        day = str(previous_stage.get("trade_date") or "")
        day = day[5:].replace("-", ".") if len(day) >= 10 else ""
        day_text = f"({day})" if day else ""
        period_label = str(previous_stage.get("period_label") or "직전 저장")
        previous_color = str(previous_stage.get("color") or "#9ca3af")
        previous_number = previous_stage.get("stage_number")
        previous_text = (
            f"{int(previous_number)}단계 · {previous_stage.get('label') or '판정 확인'}"
            if previous_number is not None else (previous_stage.get("label") or "판정 확인")
        )
        score_html += (
            f"<div class='sig-prev-score' style='color:{previous_color}'>"
            f"{period_label}{day_text} {previous_text}</div>"
        )

    if comparison_result is not None:
        comparison_score = _verdict_needle_position(
            comparison_result.verdict, verdict_order, comparison_result
        )
        current_stage = _verdict_stage_number(result.verdict, verdict_order)
        previous_stage_number = _verdict_stage_number(comparison_result.verdict, verdict_order)
        current_label = _VERDICT_SHORT.get(result.verdict) or "판정 확인"
        comparison_stage_label = _VERDICT_SHORT.get(comparison_result.verdict) or "판정 확인"
        comparison_rows = _count_row_tuples(comparison_result)
        gauges_html = (
            "<div class='sig-gauge-pair'>"
            "<div class='sig-gauge-shell sig-gauge-today'>"
            f"<div class='sig-gauge-title'>{current_label_text} · {current_stage}단계 · {current_label}</div>"
            f"<div class='sig-gauge'>{_speedometer_gauge_svg(score, zones)}</div>"
            f"<div class='sig-counts'>{gauge_ui.rows_html(row_tuples)}</div>"
            "</div>"
            "<div class='sig-gauge-shell sig-gauge-previous'>"
            f"<div class='sig-gauge-title'>{comparison_label} · {previous_stage_number}단계 · {comparison_stage_label}</div>"
            f"<div class='sig-gauge'>{_speedometer_gauge_svg(comparison_score, zones)}</div>"
            f"<div class='sig-counts'>{gauge_ui.rows_html(comparison_rows)}</div>"
            "</div></div>"
        )
        return gauges_html

    return (
        "<div class='sig-gauge'>"
        f"{gauge_ui.gauge_svg(score, zones, ticks=(), show_score=False)}"
        f"{score_html}</div>"
        f"<div class='sig-counts'>{gauge_ui.rows_html(row_tuples)}</div>"
    )


def _level_text(result, key: str) -> str:
    """지수의 **지금 수준**을 등락률 앞에 적는다 (2026-08-12 상하님 지시).

    "VIX 지수의 수치를 넣어라. 하락율만 넣어져 있으니 그렇다."
    −1.16%만 보면 지금 VIX가 15인지 35인지 알 수 없다. 15.28처럼 수준을 같이
    적어야 '높은 건가 낮은 건가'를 안다. 수준을 못 받은 항목은 그냥 넘어간다.
    """
    level = (getattr(result, "levels", None) or {}).get(key)
    if level is None:
        return ""
    return (f"<span style='color:#e6e6e6'>{float(level):,.2f}</span>"
            "<span style='opacity:.5;margin:0 .35rem'>·</span>")


def render_market_signal_card(
    result, *, verdict_style, core_display, table_keys, detail_title, detail_caption,
    table_key, diagnosis_text=None, verdict_order=(), previous_stage=None,
    show_position_score=False, falling_market=None, comparison_result=None,
    comparison_label="전일", stage_guide="", current_label_text="당일",
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
    # 신호가 아예 하나도 없을 때(스냅숏 0개)도 이유를 적어야 한다. 예전에는
    # '못 읽은 항목'이 0이라 이 줄이 통째로 빠져, 화면에 '아직 없습니다'만 뜨고
    # 진짜 원인(저장 실패 등)은 어디에도 안 보였다(2026-07-31 실발생).
    _unknown_count = sum(1 for signal in result.signals if signal.is_unknown)
    _cause = diagnosis_text(result) if diagnosis_text else None
    _cause_html = (
        f"<div style='font-size:0.9rem;color:{text};opacity:0.95;margin-top:8px;'>못 읽은 항목이 있는 이유: {_cause}</div>"
        if _cause and (_unknown_count or not result.signals) else ""
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
    _stage_guide_html = (
        f"<div class='sig-stage-guide'>{stage_guide}</div>" if stage_guide else ""
    )

    if comparison_result is not None:
        _story_html = (
            "<div class='sig-story-stack'>"
            "<div class='sig-story sig-story-today'>"
            f"<div class='sig-story-title'>{current_label_text} 설명</div>"
            f"<div class='sig-story-body' style='font-size:1.0rem;color:{text};line-height:1.5;'>"
            f"{result.headline}<div style='font-size:.9rem;opacity:.9;margin-top:8px;'>"
            f"흐름: {result.flow_note}</div>{_cause_html}</div></div>"
            "<div class='sig-story sig-story-previous'>"
            f"<div class='sig-story-title'>{comparison_label} 설명</div>"
            f"<div class='sig-story-body' style='font-size:1.0rem;color:{text};line-height:1.5;'>"
            f"{comparison_result.headline}<div style='font-size:.9rem;opacity:.9;margin-top:8px;'>"
            f"흐름: {comparison_result.flow_note}</div></div></div></div>"
        )
    else:
        _story_html = (
            f'<div style="font-size:1.0rem;color:{text};line-height:1.5;">{result.headline}</div>'
            f'<div style="font-size:0.9rem;color:{text};opacity:0.9;margin-top:8px;">'
            f'흐름: {result.flow_note}</div>{_cause_html}'
        )
    _body_class = "sig-body sig-body-comparison" if comparison_result is not None else "sig-body"

    # 카드 맨 위 글자는 **당일 판정**이다. 전일은 안쪽 계기판에만 있어서 "전일은?"이라는
    # 물음을 받았다(2026-08-06 상하님 캡처). 맨 윗줄에서 둘을 갈라 적는다.
    #
    # **색으로 갈라야 한다.** 처음에는 두 줄 다 당일 색으로 찍어 "저게 구분한 거냐"는
    # 지적을 받았다. 전일 줄은 **전일 판정의 색**을 쓰고 왼쪽에 그 색 띠를 세운다.
    # 날짜도 comparison_label에 이미 들어 있다 — 따로 붙이면 '08.05 08.06'이 된다.
    if comparison_result is None:
        _headline_html = (
            f'<div style="font-size:1.35rem;font-weight:800;color:{text};">'
            f'{result.verdict_label}</div>'
        )
    else:
        # 아래 계기판 두 칸과 **같은 모양**으로 나눈다 — 당일은 초록 테두리,
        # 전일은 파랑 테두리(2026-08-06 사용자 지시 "칸을 밑에 처럼 구분하라").
        # 판정 글자는 각자 자기 판정의 색을 쓴다.
        _prev_style = verdict_style.get(comparison_result.verdict)
        _prev_text = _prev_style[2] if _prev_style else text
        _prev_label = getattr(comparison_result, "verdict_label", "") or "판정 확인"
        # 기준시각·읽은 항목 수도 **각 칸 안에** 넣는다(2026-08-06 상하님 지적) —
        # 밖에 한 줄만 있으면 그게 당일 것인지 전일 것인지 알 수 없다.
        # 전일은 시각을 안 적는다. 저장된 스냅숏의 시각이 오늘 것으로 남는 경우가 있어
        # '전일 · 08.05 08.06'처럼 엉뚱한 날짜가 찍혔다.
        _prev_status = getattr(comparison_result, "data_status", "") or ""
        _headline_html = (
            '<div class="sig-head-pair">'
            '<div class="sig-head-box sig-head-today">'
            f'<div class="sig-head-label">{current_label_text}</div>'
            f'<div class="sig-head-verdict" style="color:{text};">'
            f'{result.verdict_label}</div>'
            f'<div class="sig-head-sub" style="color:{text};">'
            f'{_as_of_label} · {result.data_status}{_unread_note(result)}</div></div>'
            '<div class="sig-head-box sig-head-previous">'
            f'<div class="sig-head-label">{comparison_label}</div>'
            f'<div class="sig-head-verdict" style="color:{_prev_text};">'
            f'{_prev_label}</div>'
            f'<div class="sig-head-sub" style="color:{_prev_text};">'
            f'{_prev_status or "그날 마감 기준"}{_unread_note(comparison_result)}</div></div>'
            '</div>'
        )

    # 당일·전일을 칸으로 나눈 화면에서는 기준시각 줄이 **칸 안으로** 들어간다.
    # 밖에 혼자 두면 그게 당일 것인지 전일 것인지 알 수 없다(2026-08-06 상하님 지적).
    _as_of_html = (
        ""
        if comparison_result is not None else
        f'<div style="font-size:0.85rem;color:{text};opacity:0.85;margin-top:4px;">'
        f'{_as_of_label} · {result.data_status}</div>'
    )

    # 판정을 눈금 위에 올려 지금이 어느 단계인지 한눈에 보이게 한다(2026-07-24).
    _gauge_html = (
        _verdict_gauge_html(
            result,
            verdict_style,
            tuple(verdict_order),
            previous_stage=previous_stage,
            show_position_score=show_position_score,
            comparison_result=comparison_result,
            comparison_label=comparison_label,
            current_label_text=current_label_text,
        )
        if verdict_order else ""
    )
    st.markdown(f"<style>{gauge_ui.CSS}{_SIGNAL_GAUGE_CSS}</style>", unsafe_allow_html=True)
    # 줄바꿈·들여쓰기 없이 한 줄로 만든다. 여러 줄에 걸쳐 들여쓰면 빈 부분(예: 원인
    # 문구가 없을 때)에서 마크다운이 다음 줄을 코드블록으로 잡아 '</div>'가 화면에
    # 글자로 찍힌다(2026-07-24 실제 발생).
    # 당일·전일을 견주는 화면에서는 머리 칸을 **판 안에** 넣는다(2026-08-07 지적).
    # 밖에 두면 화면이 좁아 판이 접힐 때 전일 머리 칸과 전일 계기판 사이에 당일
    # 것이 끼어든다. 견주지 않는 화면은 판이 없으므로 예전처럼 위에 둔다.
    _head_above = "" if comparison_result is not None else _headline_html
    _body_inner = ("" if comparison_result is None else _headline_html)
    st.markdown(
        f'<div style="background-color:{bg};border:2px solid {border};border-radius:10px;'
        f'padding:16px;margin-top:8px;">'
        f'{_head_above}{_as_of_html}'
        f'<div class="{_body_class}">{_body_inner}{_gauge_html}<div class="sig-text">'
        f'{_story_html}</div></div>'
        # 5단계 기준·판정 구성은 **날마다 안 변하는 설명**이라 맨 아래로 내린다
        # (2026-08-06 사용자 지시). 위에 두면 매번 읽어야 할 글처럼 보인다.
        f'{_stage_guide_html}</div>',
        unsafe_allow_html=True,
    )

    for warning in result.warnings:
        st.warning(warning)

    # 핵심 4개와 신호 목록도 접어 둔다 — 첫 화면이 설명으로 가득 찼다
    # (2026-07-25 사용자 지시: "다 숨겨라"). 값·판정은 그대로다.
    # 위 판정 카드와 딱 붙어 있어 답답했다(2026-07-30 사용자 지적) — 한 줄 띄운다.
    st.markdown(
        "<div style='height:.9rem'></div>", unsafe_allow_html=True
    )
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
                        {_level_text(result, key)}{_colorize_signed(signal.display_value)}
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
    """🎯 한국장 시장 상태. 수급 신호로 장중 흐름을 읽는다."""
    st.markdown("### 🎯 한국장 시장 상태")
    st.caption(
        "수급·반도체 신호가 지금 시장에 어떤 흐름을 만드는지 읽어줍니다. "
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

    previous_result, previous_stage = _previous_kr_flow_comparison()
    previous_label = "전일"
    if previous_stage:
        previous_label = str(previous_stage.get("period_label") or "전일")
        previous_date = str(previous_stage.get("trade_date") or "")
        if len(previous_date) >= 10:
            previous_label += f" · {previous_date[5:].replace('-', '.')}"

    render_market_signal_card(
        result,
        verdict_style=_FLOW_VERDICT_STYLE,
        core_display=_FLOW_CORE_DISPLAY,
        table_keys=_FLOW_TABLE_KEYS,
        detail_title="한국장 신호 상세",
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
        previous_stage=previous_stage,
        show_position_score=True,
        comparison_result=previous_result,
        comparison_label=previous_label,
        stage_guide=_KR_STAGE_GUIDE,
    )

    # 조회 실패 목록과 외국인 선물 수동 입력칸은 없앴다(2026-07-22 사용자 지시).
    # 사용자가 손쓸 수 없는 항목을 나열해봐야 의미가 없고, 못 가져온 값은 이미 위 표에
    # '확인 필요'로 정확히 표시된다. 외국인 선물은 네이버에서 자동 조회한다.


# 배경은 위 _FLOW_VERDICT_STYLE과 같은 뜻으로 맞춘다 — 두 시장 카드가 나란히 서므로
# 배경이 다르면 한쪽만 누렇게 뜬다(2026-08-06).
_US_VERDICT_STYLE = {
    us_market_signal_engine.UsMarketVerdict.VERY_BAD: ("#170f13", "#ef4444", "#fca5a5"),
    us_market_signal_engine.UsMarketVerdict.RISK_ON: ("#0d1714", "#22c55e", "#86efac"),
    us_market_signal_engine.UsMarketVerdict.RISK_ON_EARLY: ("#0d1717", "#14b8a6", "#99f6e4"),
    us_market_signal_engine.UsMarketVerdict.MIXED: ("#15140f", "#eab308", "#fde047"),
    us_market_signal_engine.UsMarketVerdict.RISK_OFF: ("#16110d", "#f97316", "#fdba74"),
    us_market_signal_engine.UsMarketVerdict.INSUFFICIENT_DATA: ("#131316", "#71717a", "#d4d4d8"),
}

_US_CORE_DISPLAY = (
    ("US_NQ_FUTURES", "나스닥100 선물"),
    ("US_SOXX", "SOXX"),
    ("US_VIX", "VIX"),
    ("US_TNX", "미국 10년물"),
)

_US_TABLE_KEYS = tuple(spec[0] for spec in us_market_signal_engine.US_SIGNAL_SPECS) + ("US_VIX_TERM",)

# 미국장 카드의 '5단계 기준 · 판정 구성' 안내는 **뺐다**(2026-08-21 상하님 지시).
# 상하님 물음 — "전일 맨 밑에는 5단계 기준… 내용이 나오는데 직전 미국장 08.20의
# 맨 밑에는 왜 없지? 중요하면 넣고 아니면 둘 다 빼라" → **둘 다 뺀다.**
# 카드 하나에 두 날(직전 미국장·전일)이 들어 있는데 이 안내는 카드 맨 아래에
# 한 번만 붙어서, 아랫날에만 딸린 설명처럼 보였다. 두 날에 각각 넣으면 같은
# 글이 두 번 나온다. 날마다 안 변하는 설명이라 없어도 판정은 그대로다.
# 되살리려면 이 자리에 글을 되돌리고 아래 stage_guide= 인자를 다시 넘기면 된다.


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
    live_result = us_market_signal_engine.build_us_market_signal_result(quotes, extras=extras)

    # ── 완성 일봉으로 두 판을 만든다 — **모든 티커가 같은 거래일을 본다** ────────
    # 2026-08-12 상하님 지적 — "미국장 종료 후 11시간인데 켜진 신호가 5개나 생겼다고?"
    #
    # 원인이 둘이었다.
    #   ① 본값이 실시간이었다. 선물은 24시간 도니까 프리마켓 값이고, SOXX·SMH 같은
    #      ETF는 마지막 거래(어제 종가)라 **한 카드 안에 다른 날이 섞였다.**
    #   ② '전일'을 티커마다 **자기 as_of_date** 기준으로 잡았다. 선물은 8/12,
    #      ETF는 8/11이라 '전일'도 서로 다른 날이었다. 그래서 당일 6개 켜짐 /
    #      전일 1개 켜짐처럼 두 칸이 어긋났다.
    #
    # 이제 **닻(anchor) 하나**로 두 판을 만든다. `_fetch_previous_us_quote`는
    # 닻보다 **앞선** 마지막 완성 일봉을 주므로, 같은 닻을 주면 전부 같은 날이 된다.
    #   마감 뒤면 닻 = 내일 → 오늘 종가가 '직전 완료 장'
    #   장중·장전이면 닻 = 오늘 → 어제 종가가 '직전 완료 장'
    import jarvis3_data as _j3

    closed = _j3.us_session_closed()
    today_ny = datetime.now(ZoneInfo("America/New_York")).date()
    anchor = (today_ny + timedelta(days=1)) if closed else today_ny
    frozen_rows = _cached_previous_us_quotes(
        tuple((ticker, anchor.isoformat()) for ticker in tickers))
    frozen_dates = sorted({row.get("trade_date") for row in frozen_rows.values()
                           if row.get("ok") and row.get("trade_date")})
    # '전일'은 그 직전 완료 장의 **하루 앞**이다. 여기도 닻 하나로 맞춘다.
    previous_anchor = frozen_dates[-1] if frozen_dates else anchor.isoformat()
    ticker_dates = tuple((ticker, previous_anchor) for ticker in tickers)
    previous_rows = _cached_previous_us_quotes(ticker_dates)
    previous_quotes = {
        ticker: {
            "change_pct": row.get("change_pct"),
            "as_of": _now_seoul(),
            "source": "완료 일봉",
        }
        for ticker, row in previous_rows.items()
        if row.get("ok")
    }
    previous_extras = {
        "vix_current": (previous_rows.get("^VIX") or {}).get("current"),
        "vix3m_current": (previous_rows.get("^VIX3M") or {}).get("current"),
    }
    previous_result = (
        us_market_signal_engine.build_us_market_signal_result(
            previous_quotes, extras=previous_extras
        )
        if previous_quotes else None
    )
    previous_dates = sorted({
        row.get("trade_date") for row in previous_rows.values()
        if row.get("ok") and row.get("trade_date")
    })

    # **카드의 본값은 언제나 '직전 완료 미국장'이다**(2026-08-12 상하님 지시:
    # "전날 종가에 마감되고 변동이 없어야 한다"). 완성 일봉으로 잰 값이라 다음
    # 마감까지 안 움직인다. 실시간 판정은 버리지 않고 비교 칸으로 남긴다.
    frozen_quotes = {
        ticker: {"change_pct": row.get("change_pct"), "as_of": _now_seoul(),
                 "source": "완료 일봉"}
        for ticker, row in frozen_rows.items() if row.get("ok")
    }
    frozen_result = (
        us_market_signal_engine.build_us_market_signal_result(
            frozen_quotes,
            extras={"vix_current": (frozen_rows.get("^VIX") or {}).get("current"),
                    "vix3m_current": (frozen_rows.get("^VIX3M") or {}).get("current")},
        )
        if frozen_quotes else None
    )
    result = frozen_result if frozen_result is not None else live_result
    as_of_note = frozen_dates[-1] if frozen_dates else None
    st.session_state["us_signal_result"] = result
    st.session_state["us_signal_live_result"] = live_result
    st.session_state["us_signal_frozen"] = bool(frozen_result is not None)
    st.session_state["us_signal_as_of_date"] = as_of_note
    st.session_state["us_signal_previous_result"] = previous_result
    st.session_state["us_signal_previous_date"] = previous_dates[-1] if previous_dates else None
    st.session_state["us_signal_failures"] = failures
    return result


def render_us_market_signal_card():
    """🌐 미국장 시장 상태. 선행·확인 신호로 흐름을 읽는다."""
    # **「미국 전체시장 판단」과 같은 크기·같은 보라색**이다(2026-08-21 상하님 지시).
    # 두 제목이 나란히 놓이는 화면이라 크기가 다르면 어느 쪽이 위인지 헷갈린다.
    st.markdown(
        "<div style='font-size:16px; font-weight:800; color:#c084fc; "
        "margin:.25rem 0 .4rem; letter-spacing:-.01em'>🌐 미국장 시장 상태</div>",
        unsafe_allow_html=True,
    )
    # 제목 밑 설명 두 줄은 2026-08-21에 뺐다(상하님 지시). 아래 카드가 판정과
    # 근거를 이미 다 적고 있어서, 그 위에 같은 말을 또 두면 화면만 길어졌다.
    # **빈 자리를 남기지 않는다** — st.caption을 통째로 지워 칸이 위로 붙는다.
    if st.button("미국장 신호 다시 확인", key="us_signal_refresh"):
        with st.spinner("미국장 신호 확인 중..."):
            run_us_market_signal_check(force_refresh=True)

    result = st.session_state.get("us_signal_result")
    if result is None:
        # 버튼을 누르기 전에도 첫 화면에서 자동으로 한 번 읽는다(2026-07-22 사용자 지시).
        with st.spinner("미국장 신호 자동 확인 중..."):
            result = run_us_market_signal_check()

    previous_result = st.session_state.get("us_signal_previous_result")
    previous_date = str(st.session_state.get("us_signal_previous_date") or "")
    previous_label = "전일"
    if len(previous_date) >= 10:
        previous_label += f" · {previous_date[5:].replace('-', '.')}"

    # 옆 칸은 **전일**이다 — 직전 완료 장의 하루 앞. run_us_market_signal_check가
    # 이미 그렇게 만들어 세션에 넣어 둔다(us_signal_previous_result).
    #
    # 2026-08-12 저녁까지는 여기서 그것을 **실시간 값으로 덮어써** '지금 (참고)'로
    # 그렸다. 상하님 지적 — "지금이 아니잖아 전날이어야 되잖아."
    # 맞는 말이다. 게다가 그 '지금'은 절반이 지금이 아니었다 — 마감 뒤에는
    # 선물만 움직이고 ETF·지수는 직전 종가 그대로라, 한 카드에 두 날이 섞였다.
    # 앞 카드에서 고쳐 놓고(닻 하나로 같은 거래일) 이 칸만 안 고친 셈이었다.
    current_label_text = "당일"
    if st.session_state.get("us_signal_frozen"):
        as_of = str(st.session_state.get("us_signal_as_of_date") or "")
        day = as_of[5:].replace("-", ".") if len(as_of) >= 10 else ""
        # **큰 글자부터 어느 날인지 밝힌다**(2026-08-12 상하님 지적 — 미국장이
        # 끝난 지 열한 시간인데 '당일 켜진 신호 6개'로 보였다). 완성 일봉으로
        # 잰 값이라 다음 마감까지 안 움직인다.
        # 어느 날 값인지는 **카드 제목**이 그대로 말한다(아래 current_label_text —
        # "직전 미국장 · 08.20"). 그 밑에 같은 말을 세 줄로 또 적던 것을
        # 2026-08-21에 뺐다(상하님 지시).
        current_label_text = f"직전 미국장{' · ' + day if day else ''}"

    render_market_signal_card(
        result,
        current_label_text=current_label_text,
        verdict_style=_US_VERDICT_STYLE,
        core_display=_US_CORE_DISPLAY,
        table_keys=_US_TABLE_KEYS,
        detail_title="미국장 신호 상세",
        detail_caption=(
            "VIX·미국 10년물·달러지수는 오르면 위험자산에 부담이라 ‘하락’이 긍정 판정입니다. "
            "선물·반도체 ETF는 본장보다 먼저 움직여 선행, 지수는 결과라서 확인 신호로 봅니다."
        ),
        table_key="us_signal_detail_table",
        verdict_order=US_VERDICT_ORDER,
        comparison_result=previous_result,
        comparison_label=previous_label,
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

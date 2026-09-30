"""자비스10 · 한국증시 — 자료 받기와 계산 (2026-09-30).

화면 설명서: docs/JARVIS10_SPEC.md · 숫자의 근거: docs/JARVIS10_KR_RESEARCH.md

이 모듈은 스트림릿을 부르지 않는다(시험에서 그대로 부를 수 있게). 받은 자료는 프로세스 안에
잠깐 담아 두고(_cached), 받기에 실패하면 **마지막으로 받은 것을 그대로 쓴다** — 있던 값을
지우지 않는다(CLAUDE.md 0-0-2).

말은 정확히 쓴다(설명서 1장) — **코스피 지수**(종합주가지수) · **코스피200 상품**(지수를 따라가는
상품, 배당 넣음) · **개별 종목**을 섞지 않는다.
"""
from __future__ import annotations

import re
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

# 계산 결과나 돌려주는 키를 바꾸면 올리고, pages/9_자비스10.py 의 요구 숫자도 같이 올린다(CLAUDE.md 11).
MODULE_REVISION = 2026093001

SEOUL = ZoneInfo("Asia/Seoul")
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Referer": "https://finance.naver.com/",
}
_NAVER_DAY = "https://fchart.stock.naver.com/sise.nhn?timeframe=day&count={count}&requestType=0&symbol={symbol}"
_YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# 1996-12-11 — 야후 ^KS11 이 시작하는 날보다 조금 앞. 30년 셈이 여기서 시작한다.
KOSPI_HISTORY_START = 849_000_000
# KODEX 200(069500.KS) — 코스피200 을 따라가는 상품. 수정가에 배당이 들어간다.
KOSPI200_FUND = "069500.KS"
KOSPI200_FUND_START = 1_167_609_600       # 2007-01-01

_CACHE: dict = {}
_LOCK = threading.Lock()
_SESSION_LOCAL = threading.local()


def _session() -> requests.Session:
    s = getattr(_SESSION_LOCAL, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update(_HEADERS)
        _SESSION_LOCAL.s = s
    return s


def _cached(key, ttl: float, fetch):
    """ttl 초 안에 받은 것이 있으면 그것을 쓴다. 새로 받다 실패하면 옛것을 쓴다(없으면 실패)."""
    now = time.time()
    with _LOCK:
        hit = _CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    try:
        value = fetch()
    except Exception:
        if hit:
            return hit[1]
        raise
    with _LOCK:
        _CACHE[key] = (now, value)
    return value


# ── 받기 ────────────────────────────────────────────────────────────────────
def naver_daily(symbol: str, count: int = 400) -> pd.DataFrame:
    """네이버 일봉(수정주가). 장중이면 오늘 줄이 지금 값으로 들어 있다."""
    def fetch():
        r = _session().get(_NAVER_DAY.format(count=count, symbol=symbol), timeout=15)
        r.raise_for_status()
        text = r.content.decode("euc-kr", errors="replace")
        rows = []
        for raw in re.findall(r'data="([^"]+)"', text):
            p = raw.split("|")
            if len(p) < 6 or not p[0].isdigit():
                continue
            try:
                rows.append((pd.Timestamp(p[0]), float(p[1]), float(p[2]), float(p[3]), float(p[4]), float(p[5])))
            except ValueError:
                continue
        if len(rows) < 30:
            raise RuntimeError(f"네이버 일봉이 너무 적습니다: {symbol}")
        df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"]).set_index("date")
        df = df[~df.index.duplicated(keep="last")].sort_index()
        return df[df["close"] > 0]
    return _cached(("naver", symbol, count), 60, fetch)


def yahoo_daily(symbol: str, period1: int, *, ttl: float = 300) -> pd.DataFrame:
    """야후 일봉 — close 와 adjclose(배당·분할 넣은 값). 날짜는 그 시장 날짜."""
    def fetch():
        r = _session().get(_YAHOO_CHART.format(symbol=requests.utils.quote(symbol, safe="")),
                           params={"period1": period1, "period2": int(time.time()) + 86400,
                                   "interval": "1d", "events": "div,splits"}, timeout=20)
        r.raise_for_status()
        res = r.json()["chart"]["result"][0]
        tz = ZoneInfo(res.get("meta", {}).get("exchangeTimezoneName") or "UTC")
        stamps = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert(tz)
        q = res["indicators"]["quote"][0]
        adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose")
        df = pd.DataFrame({"close": q.get("close"), "high": q.get("high"),
                           "adjclose": adj if adj is not None else q.get("close")},
                          index=pd.DatetimeIndex(stamps.date, name="date"))
        df = df.astype(float).dropna(subset=["close"])
        df = df[~df.index.duplicated(keep="last")].sort_index()
        df = df[df["close"] > 0]
        if len(df) < 30:
            raise RuntimeError(f"야후 일봉이 너무 적습니다: {symbol}")
        return df
    return _cached(("yahoo", symbol, period1), ttl, fetch)


# ── 코스피 지수 ─────────────────────────────────────────────────────────────
def kospi_close_history() -> tuple[pd.Series, str]:
    """코스피 지수 종가 — 야후 1996~ 에 네이버 최근(오늘 장중 값 포함)을 덮어 붙인다.

    야후를 못 받으면 네이버 3,000줄(약 12년)로 대신하고 그 사실을 돌려준다.
    """
    recent = naver_daily("KOSPI", 3000)["close"]
    try:
        long = yahoo_daily("^KS11", KOSPI_HISTORY_START, ttl=12 * 3600)["close"]
        merged = pd.concat([long[long.index < recent.index[0]], recent])
        source = "1996년부터"
    except Exception:
        merged = recent
        source = f"{recent.index[0].year}년부터(야후를 못 받아 네이버 12년치)"
    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    return merged, source


def index_card(close: pd.Series, *, spark_days: int = 125, with_high: bool = True) -> dict:
    """지수 한 칸 — 값 · 전일 대비 · 6개월 선 · 고점 대비 · 200일선 대비."""
    c = close.dropna()
    if len(c) < 2:
        return {"ok": False}
    out = {
        "ok": True,
        "date": c.index[-1].strftime("%Y-%m-%d"),
        "close": float(c.iloc[-1]),
        "change_pct": float((c.iloc[-1] / c.iloc[-2] - 1) * 100),
        "spark": [float(v) for v in c.iloc[-spark_days:]],
    }
    if len(c) >= 200:
        sma = float(c.iloc[-200:].mean())
        out["sma200"] = sma
        out["ma_pct"] = float((c.iloc[-1] / sma - 1) * 100)
    if with_high:
        hi_at = c.idxmax()
        out["high"] = float(c.max())
        out["high_date"] = hi_at.strftime("%Y-%m-%d")
        out["dd_pct"] = float((c.iloc[-1] / c.max() - 1) * 100)
        after = c.loc[hi_at:]
        if len(after) > 1:
            lo_at = after.idxmin()
            out["low_after_high"] = float(after.min())
            out["low_after_high_date"] = lo_at.strftime("%Y-%m-%d")
            out["low_after_high_pct"] = float((after.min() / c.max() - 1) * 100)
    return out


# 1년 = 250거래일. research/kospi_index_study_20260930.py [B] 와 같은 잣대다.
HOLD_DAYS = ((1, 250), (3, 750), (5, 1250), (10, 2500))


def long_hold_stats(close: pd.Series) -> dict:
    """코스피 지수를 아무 날이나 사서 N년 들고 있었다면 — 오른 비율 · 가운데 · 가장 나빴을 때 (배당 뺌).

    매달 같은 돈을 5·10년 넣었다면 — 번 비율 · 가운데 · 가장 나빴을 때(넣은 돈 대비).
    """
    c = close.dropna()
    rows = []
    for years, h in HOLD_DAYS:
        f = (c.shift(-h) / c - 1).dropna() * 100
        if len(f) < 50:
            continue
        rows.append({"years": years, "up": float((f > 0).mean()), "median": float(f.median()),
                     "worst": float(f.min()), "n": int(len(f))})
    m = c.resample("ME").last().dropna()
    dca = []
    for years in (5, 10):
        n = years * 12
        res = []
        for i in range(0, len(m) - n):
            px = m.iloc[i:i + n].to_numpy()
            res.append(((1 / px).sum() * m.iloc[i + n] / n - 1) * 100)
        if res:
            arr = np.array(res)
            dca.append({"years": years, "win": float((arr > 0).mean()), "median": float(np.median(arr)),
                        "worst": float(arr.min()), "n": int(len(arr))})
    return {"rows": rows, "dca": dca, "start": c.index[0].strftime("%Y-%m-%d"),
            "end": c.index[-1].strftime("%Y-%m-%d")}


# ── 코스피200 상품을 사고파는 때를 정하는 규칙 (research/kospi_timing_rules_20260930.py 와 같은 셈) ──
RULE_COST = 0.001      # 한 번 바꿀 때 0.1%


def _rule_positions(c: pd.Series) -> dict[str, pd.Series]:
    sma = c.rolling(200).mean()
    month_end = c.index.to_series().groupby(c.index.to_period("M")).transform("max") == c.index.to_series()
    daily = (c > sma).astype(float).where(sma.notna())
    monthly = daily.where(month_end).ffill()
    state, band = np.nan, []
    for r in (c / sma).to_numpy():
        if np.isnan(r):
            band.append(np.nan)
            continue
        if np.isnan(state):
            state = 1.0 if r > 1 else 0.0
        elif state == 1.0 and r < 0.97:
            state = 0.0
        elif state == 0.0 and r > 1.03:
            state = 1.0
        band.append(state)
    mom = (c > c.shift(250)).astype(float).where(c.shift(250).notna())
    return {
        "그냥 들고 있기": pd.Series(1.0, index=c.index).where(sma.notna()),
        "200일선 위만 · 달마다": monthly,
        "1년 전보다 높을 때만": mom.where(month_end).ffill(),
        "200일선 ±3%": pd.Series(band, index=c.index),
        "200일선 위만 · 매일": daily,
    }


def _rule_returns(c: pd.Series, pos: pd.Series) -> pd.Series:
    ret = c.pct_change().fillna(0)
    held = pos.shift(1).fillna(0)                     # 오늘 판단 → 다음 날부터
    trade = held.diff().abs().fillna(0)
    daily = np.where(held > 0, ret, 0.0) - trade * RULE_COST
    return pd.Series(daily, index=c.index).loc[pos.first_valid_index():]


def timing_rules(adj_close: pd.Series) -> dict:
    """규칙마다 해마다 번 돈 · 가장 크게 빠진 폭 · 들고 있던 날 비율 · 바꾼 횟수 (현금 이자 0)."""
    c = adj_close.dropna()
    out = []
    for name, pos in _rule_positions(c).items():
        r = _rule_returns(c, pos)
        eq = (1 + r).cumprod()
        yrs = len(r) / 250
        out.append({"name": name,
                    "cagr": float((eq.iloc[-1] ** (1 / yrs) - 1) * 100),
                    "mdd": float((eq / eq.cummax() - 1).min() * 100),
                    "held": float(pos.loc[r.index].mean() * 100),
                    "switches": int(pos.loc[r.index].diff().abs().sum())})
    return {"rules": out, "start": c.index[0].strftime("%Y-%m-%d"), "end": c.index[-1].strftime("%Y-%m-%d")}


# ── 화면 한 판에 필요한 것 ──────────────────────────────────────────────────
def kospi_panel() -> dict:
    """① 코스피 화면 — 코스피 지수 지금 · 오래 들면 · 코스피200 상품 규칙."""
    out = {"ok": False}
    try:
        hist, source = kospi_close_history()
        out.update(ok=True, card=index_card(hist), hold=long_hold_stats(hist), source=source,
                   history_monthly=[float(v) for v in hist.resample("ME").last().dropna()])
    except Exception as exc:          # 코스피 지수부터 못 받으면 칸마다 알린다
        out["error"] = str(exc)[:200]
    try:
        fund = yahoo_daily(KOSPI200_FUND, KOSPI200_FUND_START, ttl=12 * 3600)["adjclose"]
        out["rules"] = timing_rules(fund)
    except Exception as exc:
        out["rules_error"] = str(exc)[:200]
    return out


US_INDEXES = (("NQ=F", "나스닥100 선물"), ("^IXIC", "나스닥 종합"), ("^GSPC", "S&P 500"), ("^DJI", "다우존스"))
_TEN_YEARS_AGO = lambda: int(time.time()) - 10 * 365 * 86400   # noqa: E731 — 고점을 재는 기간(지금 고점은 다 이 안이다)


def market_cards() -> dict:
    """② 시장분석 — 코스닥 지수 · 원/달러 · 미국 지수 넷 (각 칸 따로 실패한다)."""
    cards: dict = {}
    try:
        cards["KOSDAQ"] = index_card(naver_daily("KOSDAQ", 3000)["close"])
    except Exception:
        cards["KOSDAQ"] = {"ok": False}
    try:
        cards["USDKRW"] = index_card(yahoo_daily("KRW=X", int(time.time()) - 2 * 365 * 86400)["close"],
                                     with_high=False)
    except Exception:
        cards["USDKRW"] = {"ok": False}
    for symbol, _label in US_INDEXES:
        try:
            cards[symbol] = index_card(yahoo_daily(symbol, _TEN_YEARS_AGO())["close"])
        except Exception:
            cards[symbol] = {"ok": False}
    cards["FLOW"] = flow_5d()
    return cards


FLOW_STOCKS = (("005930", "삼성전자"), ("000660", "SK하이닉스"))
_NAVER_TREND = "https://m.stock.naver.com/api/stock/{code}/trend?pageSize=10"


def _to_float(text) -> float:
    return float(str(text).replace(",", "").replace("+", "").strip() or 0)


def flow_5d() -> dict:
    """대표 **개별 종목** 둘(삼성전자·SK하이닉스)의 최근 5거래일 외국인·기관 순매수 — 금액은 그날 종가로 셈(약).

    2026-09-30 — 한국테마가 쓰던 네이버 옛 페이지(item/frgn.naver)가 새 모양으로 바뀌어 표를 못 찾는다.
    한국증시는 네이버 모바일 자료(날짜별 순매수 주식 수 · 종가)로 따로 센다. 한국테마 파일은 안 건드린다.
    **시장 전체가 아니다** — 두 개별 종목의 합이다.
    """
    def fetch():
        stocks, dates = [], []
        for code, label in FLOW_STOCKS:
            r = _session().get(_NAVER_TREND.format(code=code), timeout=15,
                               headers={"Referer": "https://m.stock.naver.com/"})
            r.raise_for_status()
            rows = r.json()[:5]
            if len(rows) < 5:
                raise RuntimeError(f"수급 줄이 모자랍니다: {code}")
            foreign = sum(_to_float(x["foreignerPureBuyQuant"]) * _to_float(x["closePrice"]) for x in rows)
            organ = sum(_to_float(x["organPureBuyQuant"]) * _to_float(x["closePrice"]) for x in rows)
            stocks.append({"code": code, "label": label, "foreign": foreign, "organ": organ})
            dates.append(str(rows[0]["bizdate"]))
        latest = max(dates)
        return {"ok": True, "stocks": stocks, "foreign": sum(s["foreign"] for s in stocks),
                "organ": sum(s["organ"] for s in stocks),
                "latest": f"{latest[:4]}-{latest[4:6]}-{latest[6:8]}"}
    try:
        return _cached(("flow5",), 600, fetch)
    except Exception:
        return {"ok": False}


def forget_live() -> None:
    """↻ 를 누르면 — 1분·5분짜리(지금 값)만 버린다. 30년 자료(12시간)는 그대로 둔다."""
    short = {"KRW=X", *(s for s, _ in US_INDEXES)}
    with _LOCK:
        for key in list(_CACHE):
            if key[0] == "naver" or (key[0] == "yahoo" and key[1] in short):
                _CACHE.pop(key, None)


def market_phase(now: datetime | None = None) -> str:
    """한국장 단계 — jarvis4_data.market_phase 와 같은 잣대(주말·공휴일 달력은 없다)."""
    from datetime import time as t

    n = (now or datetime.now(SEOUL)).astimezone(SEOUL)
    if n.weekday() >= 5:
        return "주말 휴장"
    if n.time() < t(8, 30):
        return "장 시작 전"
    if n.time() < t(9, 0):
        return "장전 동시호가"
    if n.time() <= t(15, 20):
        return "정규장"
    if n.time() <= t(15, 30):
        return "장 마감 동시호가"
    if n.time() <= t(18, 0):
        return "시간외 거래"
    return "장 마감"

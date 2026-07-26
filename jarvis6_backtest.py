"""자비스6 종가 관찰 — 일봉 기준 되돌아보기(백테스트).

무엇을 하는 것인가
------------------
"장 막판에 강한 종목을 사서 다음 날 아침에 판다"는 방식이 과거에 실제로
기대값이 있었는지를 **상하님 자료로** 재는 것이다. 남이 정리한 승률을 믿지
않기 위해 만든다.

왜 일봉인가 (2026-07-26 실측)
-----------------------------
네이버 분봉은 **5거래일치만** 남는다. 그래서 15:18 시점 특징값은 과거로
소급할 수 없고, 오늘부터 모으는 수밖에 없다(자비스5 수집기가 그 일을 한다).
반면 일봉은 2010년치가 그대로 나온다. 그래서 **일봉으로 되는 것만 먼저**
재고, 분봉이 필요한 것은 자료가 쌓인 뒤로 미룬다.

이 결과를 어떻게 읽어야 하는가 — 중요
--------------------------------------
일봉 종가·당일 총거래량은 **15:20이 지나야 알 수 있는 값**이다. 그걸로 뽑은
후보를 그날 종가에 샀다고 계산하므로, 이 결과는 실제로 낼 수 있는 성적이
아니라 **상한선**이다. 여기서 기대값이 안 나오면 실제로는 더 나쁘다.
"여기서 살아남는가"를 보는 1차 관문으로만 쓴다.

자비스 규칙
-----------
- 이 파일은 단독으로 돈다. app.py·database.py·performance.py·price_data.py를
  건드리지 않고, db/jarvis.sqlite3도 열지 않는다.
- 받아온 일봉은 cache/jarvis6/ 에 쌓는다(.gitignore에 이미 cache/ 가 있다).
- 상장폐지된 종목도 과거 후보에 넣는다. 지금 살아 있는 종목만 보면
  성적이 실제보다 좋게 나온다(생존편향).
"""

from __future__ import annotations

import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

_CACHE_DIR = Path(__file__).parent / "cache" / "jarvis6" / "daily"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}

# 네이버 일봉. 한 번에 긴 기간을 통째로 준다(2010년치 확인, 2026-07-26).
_DAY_URL = (
    "https://api.finance.naver.com/siseJson.naver"
    "?symbol={code}&requestType=1&startTime={start}&endTime={end}&timeframe=day"
)
# ["20260701", 시가, 고가, 저가, 종가, 거래량, 외국인소진율]
_DAY_ROW = re.compile(
    r'\["(\d{8})",\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)'
)

_HTTP_LOCAL = threading.local()


def _session() -> requests.Session:
    """스레드마다 연결을 재사용한다. 종목 수가 많아 매번 새로 붙으면 느리다."""
    session = getattr(_HTTP_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(_HEADERS)
        _HTTP_LOCAL.session = session
    return session


def _cache_path(code: str) -> Path:
    return _CACHE_DIR / f"{code}.csv"


def fetch_daily(code: str, start: str, end: str, *, retries: int = 2) -> pd.DataFrame | None:
    """네이버에서 일봉을 받아 온다. start·end는 'YYYYMMDD'.

    응답은 JSON이 아니라 파이썬 리터럴 형식이고 머리글이 EUC-KR이라
    그냥 정규식으로 숫자 행만 뽑는다(자비스4 분봉 처리와 같은 방식).
    """
    url = _DAY_URL.format(code=code, start=start, end=end)
    for attempt in range(retries + 1):
        try:
            response = _session().get(url, timeout=12)
            text = response.content.decode("euc-kr", errors="replace")
            rows = _DAY_ROW.findall(text)
            if not rows:
                return None
            frame = pd.DataFrame(
                [
                    {
                        "date": datetime.strptime(day, "%Y%m%d").date(),
                        "open": int(open_), "high": int(high),
                        "low": int(low), "close": int(close),
                        "volume": int(volume),
                    }
                    for day, open_, high, low, close, volume in rows
                ]
            )
            return frame.drop_duplicates("date").sort_values("date").reset_index(drop=True)
        except Exception:
            if attempt >= retries:
                return None
            time.sleep(0.6 * (attempt + 1))
    return None


def load_daily(code: str, start: str, end: str, *, refresh: bool = False) -> pd.DataFrame | None:
    """캐시에 있으면 그걸 쓰고, 없으면 받아서 저장한다.

    같은 구간을 다시 돌릴 때 네이버를 또 때리지 않기 위한 것이다. 되돌아보기는
    조건을 바꿔가며 여러 번 돌려야 하는데, 그때마다 2천 종목을 다시 받으면
    시간도 걸리고 남의 서버에도 폐가 된다.
    """
    path = _cache_path(code)
    if not refresh and path.exists():
        try:
            frame = pd.read_csv(path, parse_dates=["date"])
            frame["date"] = frame["date"].dt.date
            return frame
        except Exception:
            pass  # 캐시가 깨졌으면 그냥 다시 받는다

    frame = fetch_daily(code, start, end)
    if frame is None or frame.empty:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return frame


def load_many(codes, start: str, end: str, *, workers: int = 6,
              refresh: bool = False, progress=None) -> dict[str, pd.DataFrame]:
    """여러 종목을 동시에 받는다. 동시 6개는 네이버에 무리가 안 가는 선이다."""
    result: dict[str, pd.DataFrame] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as executor:
        futures = {
            executor.submit(load_daily, code, start, end, refresh=refresh): code
            for code in codes
        }
        for future in as_completed(futures):
            code = futures[future]
            done += 1
            try:
                frame = future.result()
            except Exception:
                frame = None
            if frame is not None and not frame.empty:
                result[code] = frame
            if progress and done % 50 == 0:
                progress(done, len(futures))
    return result


# ---------------------------------------------------------------------------
# 자료 청소 — 이걸 안 하면 조건 계산이 조용히 틀린다
# ---------------------------------------------------------------------------
def clean_daily(frame: pd.DataFrame) -> pd.DataFrame:
    """받아온 일봉에서 계산을 망치는 행을 걸러낸다 (2026-07-26 실측 근거).

    전 종목 5,179,378행을 훑어 나온 세 가지 문제를 처리한다.

    1) 거래정지일 — 시·고·저가 0, 거래량 0, 종가만 직전값 유지 (11.9만 행, 769종목)
       액면분할 정지기간이나 자진상폐 후 잔여행이 이렇게 남는다. 그대로 두면
       종가위치 계산이 (종가-0)/(0-0)이 되고, 거래량 0인 날이 20일 평균을
       끌어내려 '거래대금 몇 배' 판정이 부풀려진다. **버린다.**

    2) 수정주가 반올림 잔차 — 종가가 고가보다 1원쯤 높은 행 (2.1만 행)
       네이버가 분할·배당을 소급 반영할 때 네 값을 각각 반올림해 생긴 것이다.
       버리면 멀쩡한 거래일이 사라지므로 **고가·저가를 넓혀 담는다.**
       이걸 안 하면 종가위치가 1을 넘고 윗꼬리가 음수가 된다.

    3) 정리매매는 **절대 버리지 않는다.**
       스타코링크는 상폐 직전 6거래일에 220원→17원(-92%)이었고 거래량은
       정상이었다. 이 행을 지우면 실제로 났을 손실이 통계에서 사라진다.
       거래량이 있으면 실제로 사고팔 수 있었던 날이므로 남긴다.

    자진상폐(현대홈쇼핑·더존비즈온)와 정리매매(스타코링크)는 겉보기에 둘 다
    '상장폐지'지만 자료 모습이 정반대다. 거래량 유무로 가른다.
    """
    if frame is None or frame.empty:
        return frame

    out = frame.copy()
    # 1) 거래정지·상폐 후 잔여행
    tradable = (
        (out[["open", "high", "low", "close"]] > 0).all(axis=1)
        & (out["volume"] > 0)
    )
    out = out[tradable].copy()
    if out.empty:
        return out

    # 2) 반올림 잔차 흡수 — 네 값 중 최대/최소를 고가/저가로 삼는다
    out["high"] = out[["open", "high", "low", "close"]].max(axis=1)
    out["low"] = out[["open", "high", "low", "close"]].min(axis=1)

    return out.reset_index(drop=True)


def load_clean(code: str, start: str, end: str, *, refresh: bool = False) -> pd.DataFrame | None:
    """캐시는 원본 그대로 두고, 읽을 때 청소한다.

    청소 규칙이 바뀔 수 있으니 원본을 덮어쓰지 않는다. 규칙을 고쳐도
    네이버를 다시 때릴 필요가 없다.
    """
    frame = load_daily(code, start, end, refresh=refresh)
    if frame is None:
        return None
    cleaned = clean_daily(frame)
    return cleaned if cleaned is not None and not cleaned.empty else None


# ---------------------------------------------------------------------------
# 투자 대상 종목 목록
# ---------------------------------------------------------------------------
_EXCLUDE_NAME = re.compile(r"\d*우[A-Z]?$|스팩|SPAC|리츠")
_EXCLUDE_DEPT = ("SPAC(소속부없음)", "관리종목(소속부없음)", "투자주의환기종목(소속부없음)")


def build_universe(*, include_delisted: bool = True) -> pd.DataFrame:
    """지금 살아 있는 종목 + 과거에 상장폐지된 종목을 합쳐 후보 목록을 만든다.

    상폐 종목을 빼면 '망하지 않은 종목만 골라 놓고' 성적을 재는 셈이 된다
    (생존편향). 실제로 그날 살 수 있었던 종목은 그때 상장돼 있던 전부다.
    """
    import FinanceDataReader as fdr

    live = fdr.StockListing("KRX")
    live = live[live["Market"].isin(["KOSPI", "KOSDAQ"])].copy()
    if "Dept" in live.columns:
        live = live[~live["Dept"].isin(_EXCLUDE_DEPT)]
    live = live[~live["Name"].astype(str).str.contains(_EXCLUDE_NAME, regex=True, na=False)]
    rows = [
        {"code": str(r["Code"]).strip(), "name": str(r["Name"]).strip(),
         "market": r["Market"], "marcap": r.get("Marcap"), "delisted_at": None}
        for _, r in live.iterrows()
    ]

    if include_delisted:
        gone = fdr.StockListing("KRX-DELISTING")
        gone = gone[gone.get("SecuGroup").astype(str).eq("주권")] if "SecuGroup" in gone else gone
        gone = gone[gone["Market"].isin(["KOSPI", "KOSDAQ"])] if "Market" in gone else gone
        gone = gone[~gone["Name"].astype(str).str.contains(_EXCLUDE_NAME, regex=True, na=False)]
        alive = {row["code"] for row in rows}
        for _, r in gone.iterrows():
            code = str(r.get("Symbol") or "").strip().zfill(6)
            if not code or code in alive:
                continue
            rows.append({
                "code": code, "name": str(r.get("Name") or "").strip(),
                "market": r.get("Market"), "marcap": None,
                "delisted_at": r.get("DelistingDate"),
            })

    return pd.DataFrame(rows).drop_duplicates("code").reset_index(drop=True)


def _smoke_test() -> None:
    """받아오기·캐시·유니버스가 실제로 도는지 작은 규모로 확인한다."""
    end = date.today().strftime("%Y%m%d")
    start = (date.today() - timedelta(days=365 * 10)).strftime("%Y%m%d")

    print("[1] 종목 목록 만드는 중...")
    universe = build_universe()
    live_count = int(universe["delisted_at"].isna().sum())
    print(f"    전체 {len(universe):,}개 (현재 상장 {live_count:,} + 상장폐지 {len(universe) - live_count:,})")

    sample = ["005930", "000660", "137310", "247540", "196170"]
    print(f"[2] 표본 {len(sample)}종목 일봉 받는 중 ({start}~{end})...")
    started = time.perf_counter()
    frames = load_many(sample, start, end, workers=5)
    elapsed = time.perf_counter() - started

    for code in sample:
        frame = frames.get(code)
        if frame is None:
            print(f"    {code}: 실패")
            continue
        print(f"    {code}: {len(frame):,}행  {frame['date'].iloc[0]} ~ {frame['date'].iloc[-1]}")
    print(f"    걸린 시간 {elapsed:.1f}초, 캐시 위치 {_CACHE_DIR}")

    print("[3] 캐시 재사용 확인...")
    started = time.perf_counter()
    load_many(sample, start, end, workers=5)
    print(f"    두 번째 조회 {time.perf_counter() - started:.2f}초 (네트워크 없이 캐시에서)")


if __name__ == "__main__":
    _smoke_test()


# ---------------------------------------------------------------------------
# 일봉 낙관적 사전검사 — "이 방식이 과거에 통했나"를 재는 1차 관문
# ---------------------------------------------------------------------------
# 이 결과는 실제로 낼 수 있는 성적이 아니라 **상한선**이다. 종가와 당일 총거래량은
# 15:20이 지나야 아는 값인데 그걸로 후보를 뽑기 때문이다. 여기서 안 되면 실제로는
# 더 나쁘다. 여기서 되더라도 "된다"가 아니라 "더 볼 만하다"까지다.

SELL_TAX = 0.0015          # 증권거래세(농특세 포함) 매도 시
FEE = 0.00015              # 수수료 편도
SLIPPAGE = 0.0005          # 시초가 체결 미끄러짐 가정
ROUND_TRIP_COST = FEE * 2 + SELL_TAX + SLIPPAGE

MIN_VALUE = 5_000_000_000  # 20일 중앙 거래대금 50억 미만은 제외
MIN_PRICE = 1_000
WARMUP = 260               # 전고점·평균 계산에 필요한 최소 일수


def build_features(frame: pd.DataFrame) -> pd.DataFrame | None:
    """하루하루에 대해 조건 값을 계산한다. 그날까지의 자료만 쓴다."""
    if frame is None or len(frame) < WARMUP + 5:
        return None
    d = frame.copy()
    o, h, l, c, v = d["open"], d["high"], d["low"], d["close"], d["volume"]
    rng = (h - l).replace(0, pd.NA)

    d["value"] = c * v
    d["value_med20"] = d["value"].rolling(20).median()
    # 오늘 거래대금이 최근 20일 중앙값의 몇 배인가 (오늘 제외한 과거와 비교)
    d["vol_ratio"] = d["value"] / d["value"].shift(1).rolling(20).median()

    # 전고점: 어제까지의 250일 최고가와 비교한다. 오늘 고가를 넣으면
    # "오늘 신고가니까 오늘 신고가 근처"라는 동어반복이 된다.
    prior_high = h.shift(1).rolling(250).max()
    d["from_high"] = (c / prior_high - 1) * 100
    # 그 고점을 며칠 전에 찍었나
    d["days_since_high"] = (
        h.shift(1).rolling(250).apply(lambda x: len(x) - 1 - x.argmax(), raw=True)
    )

    d["upper_wick"] = (h - c) / rng           # 0 = 고가 마감, 1 = 종일 밀림
    d["close_pos"] = (c - l) / rng            # 1 = 고가 마감
    d["body"] = (c - o) / rng
    d["ret1"] = (c / c.shift(1) - 1) * 100

    # 익일 시초가에 판다. 다음 거래일이 없으면(상폐 등) 거래로 치지 않는다.
    d["next_open"] = o.shift(-1)
    d["gross"] = (d["next_open"] / c - 1)
    d["net"] = d["gross"] - ROUND_TRIP_COST

    d["ok"] = (
        (d["value_med20"] >= MIN_VALUE)
        & (c >= MIN_PRICE)
        & d["next_open"].notna()
        & d["from_high"].notna()
        & rng.notna()
    )
    d["dow"] = pd.to_datetime(d["date"]).dt.dayofweek
    d["year"] = pd.to_datetime(d["date"]).dt.year
    return d.iloc[WARMUP:]


def collect_signals(*, limit: int | None = None, progress=None) -> pd.DataFrame:
    """전 종목의 하루하루 조건값을 한 표로 모은다."""
    universe = build_universe()
    market = dict(zip(universe["code"], universe["market"]))
    codes = [Path(p).stem for p in (_CACHE_DIR).glob("*.csv")]
    if limit:
        codes = codes[:limit]
    keep = ["date", "close", "value", "vol_ratio", "from_high", "days_since_high",
            "upper_wick", "close_pos", "body", "ret1", "net", "gross", "dow", "year"]
    out = []
    for index, code in enumerate(codes, 1):
        if market.get(code) not in ("KOSPI", "KOSDAQ"):
            continue
        frame = clean_daily(pd.read_csv(_CACHE_DIR / f"{code}.csv"))
        rows = build_features(frame)
        if rows is None:
            continue
        rows = rows[rows["ok"]]
        if rows.empty:
            continue
        rows = rows[keep].copy()
        rows["code"] = code
        rows["market"] = market[code]
        out.append(rows)
        if progress and index % 300 == 0:
            progress(index, len(codes))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def summarize(net: pd.Series) -> dict:
    """거래 결과 한 묶음을 성적표로 바꾼다. 승률만 보지 않는다."""
    n = len(net)
    if n == 0:
        return {"n": 0}
    wins, losses = net[net > 0], net[net <= 0]
    gain, loss = wins.sum(), -losses.sum()
    equity = (1 + net).cumprod()
    drawdown = (equity / equity.cummax() - 1).min()
    return {
        "n": n,
        "win": len(wins) / n * 100,
        "avg": net.mean() * 100,          # 거래당 기대값(%)
        "avg_win": wins.mean() * 100 if len(wins) else 0.0,
        "avg_loss": losses.mean() * 100 if len(losses) else 0.0,
        "rr": (wins.mean() / -losses.mean()) if len(wins) and len(losses) else float("nan"),
        "pf": (gain / loss) if loss > 0 else float("inf"),
        "mdd": drawdown * 100,
    }


def apply_condition(rows: pd.DataFrame, *, from_high: float, vol_ratio: float,
                    upper_wick: float = 1.0, close_pos: float = 0.0,
                    days_min: int = 0) -> pd.DataFrame:
    """조건을 걸어 후보만 남긴다. 기본 전제는 '오늘 오른 양봉'이다."""
    return rows[
        (rows["ret1"] > 0)
        & (rows["body"] > 0)
        & (rows["from_high"] >= from_high)
        & (rows["vol_ratio"] >= vol_ratio)
        & (rows["upper_wick"] <= upper_wick)
        & (rows["close_pos"] >= close_pos)
        & (rows["days_since_high"] >= days_min)
    ]

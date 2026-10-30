"""한국 급락 후 반등장 — 자비스12 방식으로 바꾸기 전에 다시 잰다 (2026-10-30 상하님 「둘 다 해라」).

무엇을 재나 (설명서 docs/KR_THEME_SPEC.md 3-4 · 상하님께 드린 의견 「나」 1~6)
  ① 언제 사나 — 미래를 보지 않는 네 방법과, 8월에 쓴 방법(국면이 끝나야 아는 「가장 깊은 날」)을 나란히
       처음 닿은 날 · 새 바닥 날마다(자비스12 처럼 기준일이 옮겨 감) · 새 바닥 뒤 5일 더 안 빠짐 · 국면 안 매일(지금 자비스4 화면)
  ② 코스피 문턱 −10 · −15 · −20%
  ③ 종목 낙폭을 재는 자리 — 그 종목 1년 최고가(지금 자비스4) / 코스피 고점일의 그 종목 고가(자비스12)
  ④ 칸 · ⑤ 빼기(흔들림·복권·급등·거래 급증 — 9/30 자비스10 연구 그대로) + 「최근 11일 +5% 넘게 오름」 빼기 · 3배 경고
  ⑥ 보유 20 · 40 · 60거래일 — 앱은 파는 때를 정하지 않으므로 셋을 나란히
잣대(2026-09-30 상하님 결정) — **같은 날 코스피보다 나았나 + 실제로 벌었나 둘 다**.

재는 틀 (9/30 자비스10 연구와 같다)
  · 상장폐지 종목까지 — 거래소(KIND) 상장·폐지 목록 → 네이버 일봉(수정주가 · 최대 3,000줄 ≈ 12년)
  · 사는 때 신호 다음 거래일 시가 · 파는 때 신호일에서 N거래일 뒤 종가(그 전에 폐지되면 마지막 거래 가격)
  · **다음 날 시가가 상한가거나 거래가 없으면 못 산 것으로 뺀다**(한국만의 가격제한폭)
  · 50일 평균 거래대금 50억↑ · 250거래일 넘게 거래된 종목
  · 테마 명부는 과거 것이 없어 쓰지 않는다 — 앱은 네이버 테마 종목만 보지만 여기서는 보통주 전부다
  · 거래비용·세금은 안 넣었다

클라우드 작업 칸은 네이버·거래소가 막혀 못 돈다 — 깃허브(.github/workflows/j13_kr_remeasure.yml)에서 돈다.
저장소에는 아무것도 쓰지 않는다. 결과는 실행 기록과 첨부 파일(J13_OUT)에 남는다.
J13_FAKE=1 이면 만든 값으로 틀만 돌려 본다(시험용).
"""
from __future__ import annotations

import io
import json
import os
import pathlib
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

OUT = pathlib.Path(os.environ.get("J13_OUT") or "/tmp/j13")
FAKE = os.environ.get("J13_FAKE") == "1"
KIND = "https://kind.krx.co.kr"
NAVER = "https://fchart.stock.naver.com/sise.nhn?timeframe=day&count={count}&requestType=0&symbol={code}"
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")}
MARKETS = {"stockMkt": "KOSPI", "kosdaqMkt": "KOSDAQ"}
_NOT_COMMON = ("스팩", "SPAC", "리츠", "선박", "인프라", "기업인수목적")
_PREF = re.compile(r"(\d?우[A-C]?|\(전환\))$")

FLOOR = 50.0                    # 50일 평균 거래대금 문턱(억) — jarvis4_data.KR_LIQUIDITY_FLOOR
HOLDS = (20, 40, 60)
THRESHOLDS = (-0.10, -0.15, -0.20)
SPLIT = pd.Timestamp("2021-01-01")
LIMIT_UP_CHANGE = pd.Timestamp("2015-06-15")    # 가격제한폭 ±15% → ±30%
MERGE_GAP = 20                  # 국면이 잠깐 끊겨도 20거래일 안에 다시 들어오면 같은 국면


# ── 자료 받기 ────────────────────────────────────────────────────────────────
def _excluded(name: str) -> bool:
    return any(t in str(name) for t in _NOT_COMMON) or bool(_PREF.search(str(name)))


def _kind_table(resp) -> pd.DataFrame:
    df = pd.read_html(io.StringIO(resp.content.decode("euc-kr", errors="replace")))[0]
    df["종목코드"] = df["종목코드"].astype(str).str.zfill(6)
    return df


def universe() -> tuple[pd.DataFrame, str]:
    """상장 + 2013년 뒤 폐지 종목. 거래소가 막히면 FinanceDataReader 로, 폐지 목록을 못 받으면 그 사실을 밝힌다."""
    import requests

    note = "거래소(KIND) 목록"
    try:
        rows = []
        for mkt, name in MARKETS.items():
            r = requests.get(f"{KIND}/corpgeneral/corpList.do",
                             params={"method": "download", "marketType": mkt}, headers=UA, timeout=60)
            df = _kind_table(r)
            df["market"] = name
            rows.append(df.rename(columns={"회사명": "name", "종목코드": "code"})[["name", "code", "market"]])
        listed = pd.concat(rows)
        listed["status"] = "listed"
        s = requests.Session()
        s.headers.update({**UA, "Referer": f"{KIND}/investwarn/delcompany.do?method=searchDelCompanyMain"})
        rows = []
        for mkt, name in MARKETS.items():
            data = {"method": "searchDelCompanySub", "forward": "delcompany_down", "currentPageSize": "5000",
                    "pageIndex": "1", "orderMode": "1", "orderStat": "D", "searchMode": "", "searchCodeType": "",
                    "searchCorpName": "", "marketType": mkt, "repIsuSrtCd": "",
                    "fromDate": "2013-01-01", "toDate": "2026-12-31"}
            df = _kind_table(s.post(f"{KIND}/investwarn/delcompany.do", data=data, timeout=60))
            df["market"] = name
            rows.append(df.rename(columns={"회사명": "name", "종목코드": "code", "폐지일자": "delisted_on"})
                        [["name", "code", "market", "delisted_on"]])
        gone = pd.concat(rows)
        gone["status"] = "delisted"
    except Exception as exc:  # 해외 컴퓨터에서 거래소가 막힐 수 있다
        print(f"거래소 목록 실패({exc}) → FinanceDataReader 로 받는다")
        import FinanceDataReader as fdr

        note = "FinanceDataReader 목록"
        now = fdr.StockListing("KRX")
        now = now[now["Market"].isin(["KOSPI", "KOSDAQ", "KOSDAQ GLOBAL"])]
        listed = pd.DataFrame({"name": now["Name"], "code": now["Code"].astype(str).str.zfill(6),
                               "market": now["Market"].str.replace(" GLOBAL", "", regex=False), "status": "listed"})
        try:
            old = fdr.StockListing("KRX-DELISTING")
            old = old[pd.to_datetime(old["DelistingDate"], errors="coerce") >= "2013-01-01"]
            gone = pd.DataFrame({"name": old["Name"], "code": old["Symbol"].astype(str).str.zfill(6),
                                 "market": old.get("Market", "?"), "status": "delisted",
                                 "delisted_on": old["DelistingDate"]})
        except Exception as exc2:
            print(f"⚠ 상장폐지 목록도 실패({exc2}) — **살아남은 종목만** 잰다. 성적이 좋게 나온다.")
            gone = pd.DataFrame(columns=["name", "code", "market", "status", "delisted_on"])
            note += " · ⚠ 폐지 종목 없음"
    gone = gone[~gone["code"].isin(listed["code"])].drop_duplicates("code", keep="last")
    uni = pd.concat([listed, gone], ignore_index=True)
    uni = uni[~uni["name"].map(_excluded)].drop_duplicates("code")
    return uni.reset_index(drop=True), note


def _naver(code: str, count: int = 3000) -> pd.DataFrame | None:
    """네이버 일봉(수정주가). count 는 받을 줄 수 — 재기는 3,000(≈12년), 그림자 목록 저장(j13_shadow_collect)은 짧게."""
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(NAVER.format(code=code, count=count),
                                         headers={**UA, "Referer": "https://finance.naver.com/"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                text = resp.read().decode("euc-kr", errors="replace")
            break
        except Exception as exc:
            last = exc
            time.sleep(0.6 * (attempt + 1))
    else:
        raise RuntimeError(f"{code}: {last}")
    rows = [p.split("|")[:6] for p in re.findall(r'data="([^"]+)"', text) if p.split("|")[0].isdigit()]
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df.index = pd.to_datetime(df.pop("date"), format="%Y%m%d")
    return df.astype(float)


def load_real():
    uni, note = universe()
    print(f"목록({note}): 상장 {int((uni.status == 'listed').sum())} · 폐지 {int((uni.status == 'delisted').sum())}")
    frames, fail = {}, 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(_naver, c): c for c in uni["code"]}
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                df = fut.result()
                if df is not None and len(df) >= 260:
                    frames[futs[fut]] = df
            except Exception:
                fail += 1
            if i % 1000 == 0:
                print(f"  일봉 {i}/{len(futs)}")
    idx = {name: _naver(name) for name in ("KOSPI", "KOSDAQ")}
    print(f"일봉 받음 {len(frames)} · 실패 {fail} · 코스피 {idx['KOSPI'].index[0].date()} ~ {idx['KOSPI'].index[-1].date()}")
    dates = idx["KOSPI"].index
    wide = {k: pd.DataFrame({c: f[k] for c, f in frames.items()}).reindex(dates) for k in ("open", "high", "close", "volume")}
    meta = uni.set_index("code").reindex(list(frames))
    # 폐지 종목의 일봉을 네이버가 안 주면 **살아남은 종목만** 재게 된다 — 성적이 좋게 나온다. 받은 수를 따로 적는다.
    got = meta["status"].value_counts()
    asked = uni["status"].value_counts()
    print(f"일봉을 받은 종목: 상장 {int(got.get('listed', 0))}/{int(asked.get('listed', 0))} · "
          f"폐지 {int(got.get('delisted', 0))}/{int(asked.get('delisted', 0))}"
          + ("  ⚠ 폐지 종목을 거의 못 받음 — 살아남은 종목 위주라 성적이 좋게 나올 수 있다"
             if got.get("delisted", 0) < 0.2 * max(asked.get("delisted", 0), 1) else ""))
    note += (f" · 일봉 받은 종목 상장 {int(got.get('listed', 0))}/{int(asked.get('listed', 0))}"
             f" · 폐지 {int(got.get('delisted', 0))}/{int(asked.get('delisted', 0))}")
    return wide, idx, meta, note


def load_fake():
    """시험용 — 같은 모양의 값을 만든다(성적은 뜻이 없다)."""
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2014-07-01", "2026-10-29")
    n, t = 300, len(dates)
    market = np.cumsum(rng.normal(0, 0.011, t))
    market[1500:1580] -= np.linspace(0, 0.35, 80)
    market[1580:] -= 0.35
    k = 2000 * np.exp(market)
    noise = np.cumsum(rng.normal(0, 0.025, (t, n)), axis=0) + market[:, None] * rng.uniform(0.5, 2.0, n)
    close = 10000 * np.exp(noise)
    openp = close * (1 + rng.normal(0, 0.01, (t, n)))
    high = np.maximum(close, openp) * (1 + np.abs(rng.normal(0, 0.01, (t, n))))
    vol = rng.uniform(1e5, 3e6, (t, n))
    cols = [f"{i:06d}" for i in range(n)]
    close[2500:, :20] = np.nan        # 폐지된 종목 흉내
    wide = {"open": pd.DataFrame(openp, dates, cols), "high": pd.DataFrame(high, dates, cols),
            "close": pd.DataFrame(close, dates, cols), "volume": pd.DataFrame(vol, dates, cols)}
    kos = pd.DataFrame({"open": k * (1 + rng.normal(0, 0.003, t)), "high": k * 1.005, "low": k * 0.995,
                        "close": k, "volume": 1.0}, index=dates)
    meta = pd.DataFrame({"name": cols, "market": "KOSPI", "status": "listed"}, index=cols)
    return wide, {"KOSPI": kos, "KOSDAQ": kos * 0.4}, meta, "시험용 값"


# ── 바탕 계산 ────────────────────────────────────────────────────────────────
def prepare(wide, idx):
    close, openp, high, vol = wide["close"], wide["open"], wide["high"], wide["volume"]
    dates = close.index
    traded = (vol > 0) & close.notna()
    value = close * vol / 1e8
    env = {"dates": dates, "codes": close.columns}
    env["value50"] = value.rolling(50, min_periods=20).mean()
    history = close.notna().cumsum() >= 250
    env["pool"] = (env["value50"] >= FLOOR) & traded & history
    env["own_dd"] = close / high.rolling(252, min_periods=60).max() - 1.0
    env["ret11"] = close / close.shift(11) - 1.0
    # 빼기 — 9/30 kr_rules_vs_kospi_20260930 그대로(울타리 20일 10억↑ 안에서 순위)
    ret = close.pct_change(fill_method=None)
    value20 = value.rolling(20, min_periods=10).mean()
    base = (value20 >= 10) & traded & history

    def top(df, share):
        return df.where(base).rank(axis=1, pct=True, ascending=False) <= share
    env["bad"] = (top(ret.rolling(60, min_periods=50).std(), 0.4) | top(ret.rolling(20, min_periods=15).max(), 0.4)
                  | top(close / close.shift(20) - 1, 0.2)
                  | top(value.rolling(5).mean() / value.rolling(60, min_periods=40).mean(), 0.2))
    # 사는 날(다음 날 시가) — 거래가 없거나 시가가 상한가면 못 산다
    nxt_open = openp.shift(-1)
    limit = pd.Series(np.where(dates >= LIMIT_UP_CHANGE, 0.30, 0.15), index=dates)
    up_open = nxt_open.div(close).sub(1.0).ge(limit.shift(-1).fillna(0.30) - 0.005, axis=0)
    env["fillable"] = (nxt_open > 0) & vol.shift(-1).gt(0) & ~up_open
    env["limit_up_next"] = up_open & (nxt_open > 0)
    close_ff = close.ffill()               # 폐지 뒤에는 마지막 거래 가격이 남는다
    env["fwd"] = {}
    for h in HOLDS:
        f = close_ff.shift(-h) / nxt_open.where(nxt_open > 0) - 1.0
        f.iloc[-h - 1:] = np.nan
        env["fwd"][h] = f
    k = idx["KOSPI"].reindex(dates).ffill()
    env["k_close"] = k["close"]
    env["k_dd"] = k["close"] / k["close"].rolling(252, min_periods=60).max() - 1.0      # 지금 자비스4
    env["k_dd_high"] = k["close"] / k["high"].rolling(252, min_periods=60).max() - 1.0  # 자비스12 식(고가 → 종가)
    env["kfwd"] = {}
    for h in HOLDS:
        kf = k["close"].shift(-h) / k["open"].shift(-1) - 1.0
        kf.iloc[-h - 1:] = np.nan
        env["kfwd"][h] = kf
    # 코스피 고점일 — 그날까지 1년 안에 코스피 종가가 가장 높았던 날
    pos = np.arange(len(dates))
    roll_arg = k["close"].rolling(252, min_periods=60).apply(np.argmax, raw=True)
    start = np.maximum(pos - 251, 0)
    env["k_peak_pos"] = pd.Series(np.where(roll_arg.notna(), start + roll_arg.fillna(0).to_numpy(), np.nan),
                                  index=dates)
    env["high"] = high.to_numpy()
    env["close"] = close.to_numpy()
    for key in ("own_dd", "pool", "fillable", "bad", "ret11"):
        env[key + "_np"] = env[key].to_numpy()
    env["fwd_np"] = {h: env["fwd"][h].to_numpy() for h in HOLDS}
    env["kfwd_np"] = {h: env["kfwd"][h].to_numpy() for h in HOLDS}
    env["k_peak_np"] = env["k_peak_pos"].to_numpy()
    return env


def episodes(env, threshold: float, dd_key: str = "k_dd") -> list[dict]:
    """코스피가 문턱 아래로 들어간 국면들. 20거래일 안에 다시 들어오면 같은 국면으로 본다."""
    dd = env[dd_key].to_numpy()
    inside = np.where(dd <= threshold)[0]
    if not len(inside):
        return []
    runs, start, prev = [], inside[0], inside[0]
    for p in inside[1:]:
        if p - prev > MERGE_GAP:
            runs.append((start, prev))
            start = p
        prev = p
    runs.append((start, prev))
    out = []
    for a, b in runs:
        seg = dd[a:b + 1]
        zone = [p for p in range(a, b + 1) if dd[p] <= threshold]
        lows, best = [], np.inf
        for p in zone:
            if dd[p] < best:
                best = dd[p]
                lows.append(p)
        out.append({"start": a, "end": b, "deepest": a + int(np.nanargmin(seg)), "zone": zone, "lows": lows,
                    "depth": float(np.nanmin(seg))})
    return out


def signal_days(eps: list[dict], how: str, n_dates: int) -> list[tuple[int, int, int]]:
    """(사는 신호일, 낙폭을 재는 기준일, 국면 번호) 목록."""
    out = []
    for e_no, e in enumerate(eps):
        if how == "first":
            out.append((e["zone"][0], e["zone"][0], e_no))
        elif how == "newlow":
            out.extend((p, p, e_no) for p in e["lows"])
        elif how == "deepest":                       # 8월 방법 — 국면이 끝나야 안다(미래를 본 값)
            out.append((e["deepest"], e["deepest"], e_no))
        elif how == "confirm5":                      # 새 바닥 뒤 5거래일 더 안 빠지면 그다음 날 산다
            lows = e["lows"]
            for i, p in enumerate(lows):
                nxt = lows[i + 1] if i + 1 < len(lows) else None
                s = p + 5
                if (nxt is None or nxt > s) and s < n_dates:
                    out.append((s, p, e_no))
        elif how == "daily":                         # 지금 자비스4 화면 — 국면 안 날마다 · 기준일은 그때까지 가장 깊은 날
            best_p = None
            for p in e["zone"]:
                if p in e["lows"]:
                    best_p = p
                out.append((p, best_p, e_no))
    return out


def stock_dd(env, basis: str, b: int) -> np.ndarray:
    if basis == "own":
        return env["own_dd_np"][b]
    peak = env["k_peak_np"][b]
    if np.isnan(peak):
        return np.full(len(env["codes"]), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        return env["close"][b] / env["high"][int(peak)] - 1.0


def evaluate(env, eps, how, basis, band, filters, threshold) -> dict:
    lo, hi = band
    sig = signal_days(eps, how, len(env["dates"]))
    k_dd = env["k_dd"].to_numpy()
    pool, fill = env["pool_np"], env["fillable_np"]
    bad, ret11 = env["bad_np"], env["ret11_np"]
    per_hold = {h: [] for h in HOLDS}
    picks = dropped = 0
    names_prev, turnover = None, []
    for s, b, e_no in sig:
        if b is None:
            continue
        dd = stock_dd(env, basis, b)
        with np.errstate(invalid="ignore"):
            cand = pool[b] & (dd <= hi) & (dd >= lo)
        if "clean" in filters:
            cand &= ~bad[s]
        with np.errstate(invalid="ignore"):
            if "fresh" in filters:
                cand &= ~(ret11[s] > 0.05)
            if "x3" in filters and k_dd[b] < 0:
                cand &= ~(dd < 3.0 * k_dd[b])
        sel = cand & fill[s]
        picks += int(sel.sum())
        dropped += int((cand & ~fill[s]).sum())
        if names_prev is not None and sel.sum():
            now = set(np.where(sel)[0])
            turnover.append(len(now - names_prev) / max(len(now), 1))
        names_prev = set(np.where(sel)[0]) if sel.sum() else names_prev
        for h in HOLDS:
            row = env["fwd_np"][h][s]
            f = row[sel]
            f = f[np.isfinite(f)]
            kf = env["kfwd_np"][h][s]
            if not len(f) or not np.isfinite(kf):
                continue
            allf = row[pool[s] & fill[s]]
            allf = allf[np.isfinite(allf)]
            per_hold[h].append({"s": s, "e": e_no, "n": len(f), "bk": float(f.mean()), "k": float(kf),
                                "all": float(allf.mean()) if len(allf) else np.nan,
                                "up": float((f > 0).mean()), "beat": float((f > kf).mean())})
    res = {"how": how, "basis": basis, "band": band, "filters": " + ".join(FILTER_NAME[f] for f in filters) or "없음",
           "threshold": threshold, "picks": picks, "dropped": dropped,
           "turnover": float(np.mean(turnover)) if turnover else None, "holds": {}}
    for h, rows in per_hold.items():
        if not rows:
            res["holds"][h] = None
            continue
        df = pd.DataFrame(rows)
        df["ex"] = df["bk"] - df["k"]
        by_ep = df.groupby("e").agg(ex=("ex", "mean"), bk=("bk", "mean"), k=("k", "mean"))
        dates = env["dates"]
        when = dates[df["s"].to_numpy()]
        first = df.loc[when < SPLIT, "ex"]
        second = df.loc[when >= SPLIT, "ex"]
        loo = [by_ep.drop(i)["ex"].mean() for i in by_ep.index] if len(by_ep) > 1 else []
        res["holds"][h] = {
            # 국면마다 — 화면 「사례 표」에 쓴다(2026-10-31 상하님 「라」)
            "by_ep": [{"e": int(e_no), "ex": float(row.ex * 100), "bk": float(row.bk * 100), "k": float(row.k * 100)}
                      for e_no, row in by_ep.iterrows()],
            "episodes": int(len(by_ep)), "baskets": int(len(df)), "size": float(df["n"].mean()),
            "bk_mean": float(df["bk"].mean() * 100), "bk_median": float(df["bk"].median() * 100),
            "k_mean": float(df["k"].mean() * 100), "all_mean": float(np.nanmean(df["all"]) * 100),
            "beat_pct": float((df["bk"] > df["k"]).mean() * 100), "pos_pct": float((df["bk"] > 0).mean() * 100),
            "stock_up": float(np.average(df["up"], weights=df["n"]) * 100),
            "stock_beat": float(np.average(df["beat"], weights=df["n"]) * 100),
            "ep_ex": float(by_ep["ex"].mean() * 100), "ep_beat_pct": float((by_ep["ex"] > 0).mean() * 100),
            "ep_pos_pct": float((by_ep["bk"] > 0).mean() * 100),
            "half1_ex": float(first.mean() * 100) if len(first) else None,
            "half2_ex": float(second.mean() * 100) if len(second) else None,
            "loo_min_ex": float(min(loo) * 100) if loo else None,
        }
    return res


# ── 보여 주기 ────────────────────────────────────────────────────────────────
HOW_NAME = {"first": "처음 닿은 날", "newlow": "새 바닥 날마다(자비스12식)", "confirm5": "새 바닥 뒤 5일 안 빠짐",
            "daily": "국면 안 매일(지금 화면)", "deepest": "⚠가장 깊은 날(8월식·미래 봄)"}
BASIS_NAME = {"own": "자기 1년 고점", "kpeak": "코스피 고점일"}
FILTER_NAME = {"clean": "흔들림·복권·급등·몰림", "fresh": "11일 +5%↑", "x3": "코스피 3배↑"}


def _fmt(v, d=1, sign=True):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "  —  "
    return f"{v:+.{d}f}" if sign else f"{v:.{d}f}"


def line(res) -> str:
    lo, hi = res["band"]
    head = (f"{HOW_NAME[res['how']]:<20} · {BASIS_NAME[res['basis']]} {abs(hi) * 100:.0f}~{abs(lo) * 100:.0f}% · "
            f"빼기 {res['filters']}")
    parts = []
    for h in HOLDS:
        r = res["holds"].get(h)
        if not r:
            parts.append(f"{h}일 없음")
            continue
        parts.append(f"{h}일 사건 {r['episodes']}번 묶음 {r['baskets']} · 평균 {_fmt(r['bk_mean'])}% vs 코스피 {_fmt(r['k_mean'])}% · "
                     f"코스피 이긴 {r['beat_pct']:.0f}% · 번 것 {r['pos_pct']:.0f}% · 사건마다 {_fmt(r['ep_ex'])}%p "
                     f"(이긴 사건 {r['ep_beat_pct']:.0f}% · 하나 빼면 최악 {_fmt(r['loo_min_ex'])}%p · 앞 {_fmt(r['half1_ex'])} 뒤 {_fmt(r['half2_ex'])}) · "
                     f"그날 아무 종목 {_fmt(r['all_mean'])}%")
    extra = f" · 고른 {res['picks']:,} · 못 산(상한가·정지) {res['dropped']:,}"
    if res.get("turnover") is not None:
        extra += f" · 다음 목록에 새로 든 종목 {res['turnover'] * 100:.0f}%"
    return head + extra + "\n      " + "\n      ".join(parts)


def short(res) -> str:
    """한 줄 요약 — 보유기간마다 사건마다 셈(코스피보다 몇 %p) · 코스피를 이긴 사건 · 번 사건."""
    lo, hi = res["band"]
    cells, first = [], {}
    for h in HOLDS:
        r = res["holds"].get(h)
        if not r:
            cells.append(f"{h}일 없음")
            continue
        first = first or r
        cells.append(f"{h}일 {_fmt(r['ep_ex'])}%p 이긴 {r['ep_beat_pct']:.0f}% 번 {r['ep_pos_pct']:.0f}%")
    return (f"코스피 {res['threshold'] * 100:.0f}% · {HOW_NAME[res['how']]} · {BASIS_NAME[res['basis']]} "
            f"{abs(hi) * 100:.0f}~{abs(lo) * 100:.0f}% · 빼기 {res['filters']} · 사건 {first.get('episodes', 0)}번 · "
            + " | ".join(cells))


def _worst_ex(res) -> float:
    values = [r["ep_ex"] for r in res["holds"].values() if r and r.get("ep_ex") is not None]
    return min(values) if values else float("-inf")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.time()
    wide, idx, meta, note = load_fake() if FAKE else load_real()
    env = prepare(wide, idx)
    dates = env["dates"]
    print(f"\n자료: {note} · 종목 {len(env['codes'])} · {dates[0].date()} ~ {dates[-1].date()} · 받는 데 {time.time() - started:.0f}초")
    print(f"  50억↑ 울타리 하루 평균 {env['pool'].sum(axis=1).mean():.0f}종목")

    k_dd = env["k_dd"]
    print(f"\n### 지금 코스피 — {dates[-1].date()} 종가 {env['k_close'].iloc[-1]:,.2f}")
    print(f"  1년 최고 종가 대비 {k_dd.iloc[-1] * 100:+.1f}% (지금 자비스4) · 1년 최고가(고가) 대비 {env['k_dd_high'].iloc[-1] * 100:+.1f}% (자비스12 식)")
    summary = {"data": note, "codes": int(len(env["codes"])), "from": str(dates[0].date()), "to": str(dates[-1].date()),
               "kospi_now": float(env["k_close"].iloc[-1]), "kospi_dd_now": float(k_dd.iloc[-1] * 100),
               "kospi_dd_high_now": float(env["k_dd_high"].iloc[-1] * 100), "episodes": {}, "results": []}
    for th in THRESHOLDS:
        eps = episodes(env, th)
        rows = [{"start": str(dates[e["start"]].date()), "deepest": str(dates[e["deepest"]].date()),
                 "depth": round(e["depth"] * 100, 1), "end": str(dates[e["end"]].date()), "new_lows": len(e["lows"])}
                for e in eps]
        summary["episodes"][str(th)] = rows
        print(f"\n### 코스피 {th * 100:.0f}% 아래 국면 {len(eps)}번")
        for r in rows:
            print(f"  {r['start']} ~ {r['end']} · 가장 깊은 날 {r['deepest']} {r['depth']}% · 새 바닥 {r['new_lows']}번")

    bands = {"own": [(-0.60, -0.40), (-0.40, -0.20)],
             "kpeak": [(-0.20, -0.10), (-0.30, -0.20), (-0.50, -0.30), (-0.80, -0.50)]}
    filter_sets = [(), ("clean", "fresh"), ("clean", "fresh", "x3")]
    for th in THRESHOLDS:
        eps = episodes(env, th)
        print(f"\n\n######## 코스피 {th * 100:.0f}% 아래 ########")
        for how in ("deepest", "first", "newlow", "confirm5", "daily"):
            for basis, blist in bands.items():
                for band in blist:
                    for flt in filter_sets:
                        if basis == "own" and "x3" in flt:
                            continue
                        res = evaluate(env, eps, how, basis, band, flt, th)
                        summary["results"].append(res)
                        print("  " + line(res))
        sys.stdout.flush()

    # 한눈에 — 잣대 둘(코스피보다 나음 · 벌었음)을 사건마다 셈으로 다 넘은 것
    print("\n\n### 한눈에 — 사건마다 셈으로 코스피를 이기고(평균) · 번 사건이 절반 넘고 · 하나 빼도 코스피보다 나은 것")
    ok = []
    for res in summary["results"]:
        if res["how"] == "deepest":
            continue
        marks = []
        for h in HOLDS:
            r = res["holds"].get(h)
            good = bool(r and r["episodes"] >= 3 and r["ep_ex"] > 0 and r["ep_pos_pct"] > 50
                        and (r["loo_min_ex"] or -1) > 0)
            marks.append(good)
        if all(marks):
            ok.append(res)
    if not ok:
        print("  없음 — 미래를 보지 않는 방법 가운데 세 보유기간 다 넘은 것이 하나도 없다")
    for res in ok:
        print("  " + line(res))
    summary["passed_all_holds"] = len(ok)

    # 마지막 요약 — 깃허브 기록은 끝부분만 쉽게 읽힌다(작업 칸에서는 기록 파일·첨부를 못 받는다 · 2026-10-30).
    # 위에서 이미 잰 것을 짧게 다시 적을 뿐 새로 재지 않는다. 기준도 바꾸지 않는다(바꿀지는 상하님께 여쭘 · CLAUDE.md 0-1).
    passed = {id(res) for res in ok}
    print("\n\n### 마지막 요약 (위 내용을 짧게 다시)")
    print(f"  자료: {note} · 종목 {len(env['codes'])} · {dates[0].date()} ~ {dates[-1].date()}")
    print(f"  지금 코스피 {env['k_close'].iloc[-1]:,.2f} · 1년 최고 종가 대비 {k_dd.iloc[-1] * 100:+.1f}%")
    print("  국면 수: " + " · ".join(f"코스피 {float(th) * 100:.0f}% 아래 {len(rows)}번"
                                  for th, rows in summary["episodes"].items()))
    print(f"  세 보유기간(20·40·60일)을 다 넘은 것 {len(ok)}개 (8월식 「가장 깊은 날」은 미래를 봐서 뺌) — 가장 약한 기간이 좋은 차례로 12개")
    for res in sorted(ok, key=_worst_ex, reverse=True)[:12]:
        print("    " + short(res))
    print("  지금 화면 방식(국면 안 매일 · 자기 1년 고점) — 전부 · ✓ 는 세 기간 다 넘음")
    for res in summary["results"]:
        if res["how"] == "daily" and res["basis"] == "own":
            print("    " + short(res) + (" ✓" if id(res) in passed else ""))
    # 국면별 표 — 화면 「사례 표」와 그림자 목록 규칙(docs/KR_THEME_SPEC.md 3-4 · 2026-10-31 「라」)에 쓰는 숫자
    eps15 = episodes(env, -0.15)
    for title, (how, basis, band, flt) in (("지금 화면 규칙", ("daily", "own", (-0.60, -0.40), ())),
                                            ("그림자 목록 규칙", ("newlow", "kpeak", (-0.80, -0.50), ("clean", "fresh")))):
        res = evaluate(env, eps15, how, basis, band, flt, -0.15)
        print(f"\n### 국면별 — {title} (코스피 −15% · " + short(res).split(" · ", 2)[-1] + ")")
        table = {h: {row["e"]: row for row in (res["holds"].get(h) or {}).get("by_ep", [])} for h in HOLDS}
        for e_no, e in enumerate(eps15):
            cells = []
            for h in HOLDS:
                row = table[h].get(e_no)
                cells.append(f"{h}일 " + ("—" if row is None else f"{row['ex']:+.1f}%p(종목 {row['bk']:+.1f}% · 코스피 {row['k']:+.1f}%)"))
            print(f"  EP {e_no + 1:>2} · {dates[e['start']].date()} ~ {dates[e['end']].date()} · 가장 깊은 날 "
                  f"{dates[e['deepest']].date()} {e['depth'] * 100:.1f}% · " + " | ".join(cells))
    (OUT / "j13_kr_crash.json").write_text(json.dumps(summary, ensure_ascii=False, default=str, indent=1),
                                           encoding="utf-8")
    print(f"\n끝 · {time.time() - started:.0f}초 · 결과 파일 {OUT / 'j13_kr_crash.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

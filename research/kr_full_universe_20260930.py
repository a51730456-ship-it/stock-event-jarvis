"""한국 전 종목 일봉 — 상장폐지된 종목까지 (2026-09-30, 자비스10 연구용 · 앱 안 씀).

왜: research/_data/wide 의 2,272종목은 지금 살아 있는 테마 종목뿐이라 과거 성적이 좋게 나온다.
    3년씩 내리다 사라진 종목이 통째로 빠져 있다.

1. 한국거래소 공시 사이트(KIND)에서 지금 상장 목록 · 상장폐지 목록(시장별)을 받는다.
2. 네이버 일봉(수정주가 · 한 번에 최대 3,000줄 ≈ 12년)을 받는다. 폐지 종목도 정리매매 날까지 나온다.

결과: research/_data/kr_universe_20260930.csv · research/_data/kr_daily_full/{code}.csv
중간에 끊겨도 다시 돌리면 받은 종목은 건너뛴다.
쓰는 법: python research/kr_full_universe_20260930.py
"""
from __future__ import annotations

import io
import pathlib
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "research" / "_data"
OUT = DATA / "kr_daily_full"
LIST = DATA / "kr_universe_20260930.csv"

KIND = "https://kind.krx.co.kr"
NAVER = "https://fchart.stock.naver.com/sise.nhn?timeframe=day&count=3000&requestType=0&symbol={code}"
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")}
MARKETS = {"stockMkt": "KOSPI", "kosdaqMkt": "KOSDAQ"}


def _table(resp: requests.Response) -> pd.DataFrame:
    text = resp.content.decode("euc-kr", errors="replace")
    df = pd.read_html(io.StringIO(text))[0]
    df["종목코드"] = df["종목코드"].astype(str).str.zfill(6)
    return df


def listed() -> pd.DataFrame:
    rows = []
    for mkt, name in MARKETS.items():
        r = requests.get(f"{KIND}/corpgeneral/corpList.do",
                         params={"method": "download", "marketType": mkt}, headers=UA, timeout=60)
        df = _table(r)
        df["market"] = name
        rows.append(df[["회사명", "종목코드", "market", "업종", "상장일"]])
    out = pd.concat(rows)
    out["status"] = "listed"
    return out.rename(columns={"회사명": "name", "종목코드": "code", "업종": "industry", "상장일": "listed_on"})


def delisted(since: str = "2013-01-01") -> pd.DataFrame:
    rows = []
    s = requests.Session()
    s.headers.update({**UA, "Referer": f"{KIND}/investwarn/delcompany.do?method=searchDelCompanyMain"})
    for mkt, name in MARKETS.items():
        data = {"method": "searchDelCompanySub", "forward": "delcompany_down", "currentPageSize": "5000",
                "pageIndex": "1", "orderMode": "1", "orderStat": "D", "searchMode": "", "searchCodeType": "",
                "searchCorpName": "", "marketType": mkt, "repIsuSrtCd": "",
                "fromDate": since, "toDate": "2026-12-31"}
        df = _table(s.post(f"{KIND}/investwarn/delcompany.do", data=data, timeout=60))
        df["market"] = name
        rows.append(df[["회사명", "종목코드", "market", "폐지일자", "폐지사유"]])
    out = pd.concat(rows)
    out["status"] = "delisted"
    return out.rename(columns={"회사명": "name", "종목코드": "code", "폐지일자": "delisted_on", "폐지사유": "reason"})


def fetch(code: str) -> int:
    target = OUT / f"{code}.csv"
    if target.exists():
        return -1
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(NAVER.format(code=code), headers={**UA, "Referer": "https://finance.naver.com/"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                text = resp.read().decode("euc-kr", errors="replace")
            break
        except Exception as exc:  # 가끔 튕긴다 — 세 번까지
            last = exc
            time.sleep(0.6 * (attempt + 1))
    else:
        raise RuntimeError(f"{code}: {last}")
    rows = [",".join(p.split("|")[:6]) for p in re.findall(r'data="([^"]+)"', text)
            if p.split("|")[0].isdigit()]
    target.write_text("date,open,high,low,close,volume\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return len(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if LIST.exists():
        uni = pd.read_csv(LIST, dtype={"code": str})
    else:
        a, b = listed(), delisted()
        # 이전상장(코스닥→코스피)·재상장은 지금 목록에 같은 코드가 있다 → 지금 것을 쓴다
        b = b[~b["code"].isin(a["code"])]
        b = b.sort_values("delisted_on").drop_duplicates("code", keep="last")
        uni = pd.concat([a, b], ignore_index=True)
        uni.to_csv(LIST, index=False, encoding="utf-8-sig")
    print(f"목록: 상장 {int((uni.status == 'listed').sum())} · 폐지(2013~) {int((uni.status == 'delisted').sum())}")
    codes = uni["code"].tolist()
    done = fail = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(fetch, c): c for c in codes}
        for f in as_completed(futs):
            try:
                f.result()
                done += 1
            except Exception as exc:
                fail += 1
                print("실패", exc, file=sys.stderr)
            if (done + fail) % 500 == 0:
                print(f"  {done + fail}/{len(codes)}")
    print(f"끝: 받음 {done} · 실패 {fail}")


if __name__ == "__main__":
    main()

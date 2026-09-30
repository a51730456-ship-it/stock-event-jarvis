"""한국 전 종목(상장폐지 포함) 사업보고서 주요 계정 — DART 다중회사 주요계정 API (2026-09-30, 자비스10 연구용).

받는 것: 자산총계·부채총계·자본총계·매출액·영업이익·당기순이익 (연결 우선, 없으면 별도)
언제 알 수 있었나: 접수번호(rcept_no) 앞 8자리 = 공시 접수일. 그날 **다음 거래일부터** 쓴다(앞을 훔쳐보지 않는다).
열쇠는 .streamlit/secrets.toml 의 DART_API_KEY — 화면·기록에 찍지 않는다.
결과: research/_data/dart_fundamentals_2015_2025.csv
"""
from __future__ import annotations

import json
import pathlib
import time
import tomllib

import pandas as pd
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "research" / "_data"
OUT = DATA / "dart_fundamentals_2015_2025.csv"
URL = "https://opendart.fss.or.kr/api/fnlttMultiAcnt.json"
ACCOUNTS = {"자산총계": "assets", "부채총계": "liabilities", "자본총계": "equity",
            "매출액": "sales", "영업이익": "op_income", "당기순이익": "net_income",
            "당기순이익(손실)": "net_income"}   # 2026-09-30 첫 받기에서 이 이름을 몰라 순이익이 통째로 빠졌다


def main() -> None:
    key = tomllib.load(open(ROOT / ".streamlit" / "secrets.toml", "rb"))["DART_API_KEY"]
    cc = pd.read_csv(DATA / "dart_corpcode.csv", dtype=str)
    cc = cc[cc["stock_code"].fillna("") != ""]
    meta = pd.read_csv(DATA / "wide_full" / "meta.csv", dtype={"code": str})
    corps = cc[cc["stock_code"].isin(meta["code"])]["corp_code"].tolist()
    print(f"회사 {len(corps)}")
    rows, calls, t0 = [], 0, time.time()
    s = requests.Session()
    for year in range(2015, 2026):
        got = 0
        for i in range(0, len(corps), 100):
            batch = ",".join(corps[i:i + 100])
            for attempt in range(3):
                try:
                    r = s.get(URL, params={"crtfc_key": key, "corp_code": batch, "bsns_year": str(year),
                                           "reprt_code": "11011"}, timeout=60)
                    j = r.json()
                    break
                except Exception:  # 가끔 끊긴다
                    time.sleep(1.5 * (attempt + 1))
            else:
                print(f"  {year} {i} 실패")
                continue
            calls += 1
            if j.get("status") not in ("000", "013"):
                print(f"  {year} {i} 상태 {j.get('status')} {j.get('message')}")
                if j.get("status") == "020":  # 하루 한도
                    raise SystemExit("하루 요청 한도")
                continue
            for it in j.get("list", []):
                name = ACCOUNTS.get(it.get("account_nm"))
                if not name:
                    continue
                amt = (it.get("thstrm_amount") or "").replace(",", "").strip()
                if amt in ("", "-"):
                    continue
                rows.append({"stock_code": it.get("stock_code"), "corp_code": it.get("corp_code"), "year": year,
                             "fs_div": it.get("fs_div"), "rcept_no": it.get("rcept_no"), "account": name,
                             "amount": float(amt)})
                got += 1
            time.sleep(0.15)
        print(f"{year}: 줄 {got} · 요청 {calls} · {time.time() - t0:.0f}초", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print("저장", OUT, len(df))


if __name__ == "__main__":
    main()

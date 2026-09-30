"""kr_dart_fundamentals_20260930 에서 해마다 실패한 묶음(회사 2600~2699번)을 10개씩 나눠 다시 받아 붙인다."""
from __future__ import annotations

import pathlib
import sys
import time
import tomllib

import pandas as pd
import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from kr_dart_fundamentals_20260930 import ACCOUNTS, DATA, OUT, ROOT, URL  # noqa: E402


def main() -> None:
    key = tomllib.load(open(ROOT / ".streamlit" / "secrets.toml", "rb"))["DART_API_KEY"]
    cc = pd.read_csv(DATA / "dart_corpcode.csv", dtype=str)
    cc = cc[cc["stock_code"].fillna("") != ""]
    meta = pd.read_csv(DATA / "wide_full" / "meta.csv", dtype={"code": str})
    corps = cc[cc["stock_code"].isin(meta["code"])]["corp_code"].tolist()[2600:2700]
    rows, bad = [], []
    s = requests.Session()
    for year in range(2015, 2026):
        for i in range(0, len(corps), 10):
            chunk = corps[i:i + 10]
            try:
                j = s.get(URL, params={"crtfc_key": key, "corp_code": ",".join(chunk), "bsns_year": str(year),
                                       "reprt_code": "11011"}, timeout=60).json()
            except Exception:
                # 10개 묶음도 깨지면 하나씩
                j = {"status": "000", "list": []}
                for c in chunk:
                    try:
                        jj = s.get(URL, params={"crtfc_key": key, "corp_code": c, "bsns_year": str(year),
                                                "reprt_code": "11011"}, timeout=60).json()
                        j["list"] += jj.get("list", [])
                    except Exception:
                        bad.append((year, c))
            for it in j.get("list", []):
                name = ACCOUNTS.get(it.get("account_nm"))
                amt = (it.get("thstrm_amount") or "").replace(",", "").strip()
                if name and amt not in ("", "-"):
                    rows.append({"stock_code": it.get("stock_code"), "corp_code": it.get("corp_code"), "year": year,
                                 "fs_div": it.get("fs_div"), "rcept_no": it.get("rcept_no"), "account": name,
                                 "amount": float(amt)})
            time.sleep(0.12)
        print(year, len(rows), flush=True)
    old = pd.read_csv(OUT, dtype={"stock_code": str, "corp_code": str, "rcept_no": str})
    new = pd.concat([old, pd.DataFrame(rows)]).drop_duplicates(["corp_code", "year", "fs_div", "account"])
    new.to_csv(OUT, index=False, encoding="utf-8-sig")
    print("붙임", len(rows), "· 끝내 실패", len(bad), bad[:5], "· 전체", len(new))


if __name__ == "__main__":
    main()

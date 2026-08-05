"""한국 일봉 내려받기 — 시총 상위 200(우선주·스팩·리츠 제외) + 코스피 지수."""
import pickle, re, time
from concurrent.futures import ThreadPoolExecutor
import FinanceDataReader as fdr
import pandas as pd

SCRATCH = str(Path(__file__).parent / "_data")
START = "2013-01-01"

lst = fdr.StockListing("KRX")
lst = lst[lst["Market"].isin(["KOSPI", "KOSDAQ"])].copy()
lst = lst.dropna(subset=["Marcap"]).sort_values("Marcap", ascending=False)


def skip(name, code):
    n = str(name)
    if re.search(r"(우|우B|우C|\(전환\)|\(신\))$", n):     # 우선주
        return True
    if "스팩" in n or "기업인수목적" in n:
        return True
    if "리츠" in n or n.endswith("리츠"):
        return True
    return False


rows = []
for _, r in lst.iterrows():
    if skip(r["Name"], r["Code"]):
        continue
    rows.append((r["Code"], r["Name"], r["Market"]))
    if len(rows) >= 200:
        break
print("고른 종목", len(rows), "· 예:", rows[:5])


def get(item):
    code, name, market = item
    for _ in range(3):
        try:
            df = fdr.DataReader(code, START)
            if df is not None and len(df) > 400:
                return code, name, market, df[["Open", "High", "Low", "Close", "Volume"]].dropna()
            return None
        except Exception:
            time.sleep(1.0)
    return None


t0 = time.time()
out = {}
with ThreadPoolExecutor(max_workers=8) as ex:
    for res in ex.map(get, rows):
        if res:
            code, name, market, df = res
            out[code] = {"name": name, "market": market, "df": df}
print(f"받은 종목 {len(out)}개 · {time.time()-t0:.0f}초")

ks = fdr.DataReader("KS11", START)
print("코스피", ks.index[0].date(), "~", ks.index[-1].date(), len(ks), "줄")

with open(SCRATCH + r"\kr_daily.pkl", "wb") as f:
    pickle.dump({"stocks": out, "kospi": ks}, f)

any_code = next(iter(out))
print("보기", out[any_code]["name"], out[any_code]["df"].index[0].date(),
      "~", out[any_code]["df"].index[-1].date(), len(out[any_code]["df"]), "줄")

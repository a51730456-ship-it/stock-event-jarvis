"""미국 일봉 내려받기 — 자비스3의 대형주 명부 + QQQ/SPY 지수."""
import sys, pickle, time
sys.path.insert(0, r"C:\Users\jangs_tjkt17a\Documents\stock_event_jarvis")
import yfinance as yf
import pandas as pd
from jarvis3_data import US_LARGE_CAP_UNIVERSE

OUT = str(Path(__file__).parent / "_data") + r"\us_daily.pkl"

tickers = list(US_LARGE_CAP_UNIVERSE) + ["QQQ", "SPY"]
print("종목수", len(tickers))

t0 = time.time()
data = yf.download(tickers, period="10y", interval="1d",
                   auto_adjust=False, group_by="ticker",
                   threads=8, progress=False)
print("받는 데 걸린 시간 %.1f초" % (time.time() - t0))

out = {}
for t in tickers:
    try:
        df = data[t].dropna(how="all")
    except Exception:
        continue
    if df is None or len(df) < 400:
        continue
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    out[t] = df
print("쓸 수 있는 종목", len(out))
missing = [t for t in tickers if t not in out]
print("빠진 것", missing[:20], "…" if len(missing) > 20 else "")

with open(OUT, "wb") as f:
    pickle.dump(out, f)
sample = out.get("AAPL")
if sample is not None:
    print("AAPL 범위", sample.index[0].date(), "~", sample.index[-1].date(), len(sample), "줄")

"""한국 종목별 외국인·기관 순매매를 네이버에서 받는다.

앱과 **같은 파서**를 쓴다(jarvis4_data._parse_stock_flow). 따로 만들면 앱이 보는 값과
다른 것을 재게 된다.
"""
import pickle, sys, time, threading
from concurrent.futures import ThreadPoolExecutor

import requests

sys.path.insert(0, r"C:\Users\jangs_tjkt17a\Documents\stock_event_jarvis")
from jarvis4_data import _parse_stock_flow, _HEADERS

S = str(Path(__file__).parent / "_data")
URL = "https://finance.naver.com/item/frgn.naver?code={code}&page={page}"

N_STOCKS = int(sys.argv[1]) if len(sys.argv) > 1 else 120
N_PAGES = int(sys.argv[2]) if len(sys.argv) > 2 else 130

KR = pickle.load(open(S + r"\kr_daily.pkl", "rb"))
codes = list(KR["stocks"])[:N_STOCKS]

_local = threading.local()


def sess():
    if not hasattr(_local, "s"):
        s = requests.Session()
        s.headers.update(_HEADERS)
        a = requests.adapters.HTTPAdapter(pool_connections=32, pool_maxsize=32)
        s.mount("https://", a)
        _local.s = s
    return _local.s


def one(code):
    out = {}
    for page in range(1, N_PAGES + 1):
        for attempt in range(3):
            try:
                r = sess().get(URL.format(code=code, page=page), timeout=12)
                rows = _parse_stock_flow(r.text)
                break
            except Exception:
                time.sleep(0.5)
                rows = []
        if not rows:
            break
        before = len(out)
        for row in rows:
            out[row["date"]] = row
        if len(out) == before:      # 같은 쪽이 반복되면 끝
            break
    return code, out


t0 = time.time()
done = 0
flow = {}
with ThreadPoolExecutor(max_workers=12) as ex:
    for code, rows in ex.map(one, codes):
        flow[code] = rows
        done += 1
        if done % 20 == 0:
            print(f"  {done}/{len(codes)}종목 · {time.time()-t0:.0f}초", flush=True)

lens = sorted(len(v) for v in flow.values())
print(f"끝. {len(flow)}종목 · {time.time()-t0:.0f}초")
print(f"종목당 받은 날 수 — 가장 적음 {lens[0]} · 가운데 {lens[len(lens)//2]} · 가장 많음 {lens[-1]}")
any_code = max(flow, key=lambda c: len(flow[c]))
ds = sorted(flow[any_code])
print(f"보기 {any_code}: {ds[0]} ~ {ds[-1]}")

with open(S + r"\kr_flow.pkl", "wb") as f:
    pickle.dump(flow, f)

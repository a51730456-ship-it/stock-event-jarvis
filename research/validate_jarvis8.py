"""Actual frozen-price run, repeated latency measurement, isolation manifest."""
from pathlib import Path
import hashlib,json,sys,time
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from jarvis8_engine import build,FIELDS
from jarvis8_data import archive,BundleCache
OUT=ROOT/'output/jarvis8';OUT.mkdir(exist_ok=True)
OLD=ROOT/'output/jarvis3_audit_20260909'
w={k:pd.read_parquet(OLD/f'fresh_{k.lower()}.parquet') for k in FIELDS}
day=pd.Timestamp('2026-08-18')
frames={s:pd.DataFrame({k:v[s] for k,v in w.items()}).dropna(how='all').loc[:day].tail(504) for s in w['Close']}
ix=pd.read_parquet(OLD/'ixic_25year_warmup.parquet').loc[:day]
t=time.perf_counter();bundle=build(frames,day,ix);elapsed=time.perf_counter()-t
path,digest=archive(bundle,frames,ix,OUT/'observations')
cache=BundleCache()
cache.value=bundle;cache.updated=time.monotonic()
lat=[]
for _ in range(100):
    t=time.perf_counter();cache.request();lat.append(time.perf_counter()-t)
cache.pool.shutdown()
before=json.loads((OUT/'protected_resume_0914.json').read_text(encoding='utf-8'))
protected={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in before.items()}
result={'date':str(day.date()),'actual_frozen_data_run':True,'build_seconds':elapsed,
        'cache_mean_ms':sum(lat)/len(lat)*1000,'cache_max_ms':max(lat)*1000,
        'valid':bundle['valid'],'excluded':bundle['excluded'],'themes':len(bundle['themes']),
        'rise':len(bundle['rise']['primary_rows']),'crash':len(bundle['crash']),
        'momentum':len(bundle['momentum']),'reversal':len(bundle['reversal']),
        'protected_unchanged':protected,'archive_sha256':digest,'archive':str(path)}
(OUT/'validation_0914.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
assert all(protected.values())

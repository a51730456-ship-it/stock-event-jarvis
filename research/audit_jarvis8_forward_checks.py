"""Independent arithmetic check and ex-post sensitivity, not a trading rule."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/jarvis8/forward_0914'
t=pd.read_csv(OUT/'cycles.csv').fillna({'tickers':''})
s=pd.read_csv(OUT/'summary.csv')
meta=json.loads((OUT/'metadata.json').read_text(encoding='utf-8'))
years=(pd.Timestamp(meta['last_exit'])-pd.Timestamp(meta['first_entry'])).days/365.25
op=pd.read_parquet(ROOT/'output/jarvis3_audit_20260909/fresh_open.parquet')
cl=pd.read_parquet(ROOT/'output/jarvis3_audit_20260909/fresh_close.parquet')
dates=cl.QQQ.dropna().index;op=op.reindex(dates);cl=cl.reindex(dates)
errors=[]
for r in t.sample(n=min(200,len(t)),random_state=20260914).itertuples():
    i=dates.get_loc(pd.Timestamp(r.day));symbols=r.tickers.split();half=r.cost_pct/200
    result=1-.1*len(symbols)
    for ticker in symbols:
        units=.1/(float(op[ticker].iloc[i+1])*(1+half))
        result+=units*float(cl[ticker].iloc[i+r.hold])*(1-half)
    errors.append(abs((result-1)*100-r.account_return_pct))
assert max(errors)<1e-8
stress=[]
for r in s[s.cost_pct.eq(.5)].itertuples():
    g=t[t.method.eq(r.method)&t.hold.eq(r.hold)&t.cost_pct.eq(.5)]
    terminal=np.prod(1+g.account_return_pct/100)
    assert abs((terminal-1)*100-r.total_return_pct)<1e-8
    best=g.account_return_pct.nlargest(3)
    stress.append({'method':r.method,'hold':int(r.hold),'original_cagr_pct':r.cagr_pct,
                   'largest_account_cycle_pct':float(best.iloc[0]),
                   'without_best_three_cagr_pct':float(((terminal/np.prod(1+best/100))**(1/years)-1)*100)})
report={'forward_return_spot_checks':len(errors),'max_absolute_error_pp':max(errors),
        'account_compounds_checked':len(stress),'sensitivity':stress,
        'note':'Best-three removal is an ex-post stress test, not a selectable real trading policy.',
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(OUT/'arithmetic_and_sensitivity.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
p=ROOT/'data/jarvis8/forward_study.json'
payload=json.loads(p.read_text(encoding='utf-8'));payload['checks']=report
temp=p.with_suffix('.tmp');temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
temp.replace(p)
print('VERIFIED',len(errors),'max error',max(errors))
print(pd.DataFrame(stress).query('hold==20').round(3).to_string(index=False))

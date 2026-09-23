"""Research only: reduce exposure to test whether momentum's edge survives.

Follow-up chosen AFTER the exploratory 20-session result: not out-of-sample.
No reranking, optimized weights or trading application changes. Compare 5% and
10% per stock (25%/50% max). Same timing/exposure QQQ plus original 50% QQQ.
All three pre-existing grids and .2/.5/1% cost assumptions are reported.
"""
from pathlib import Path
import hashlib,json,sys
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import independent_high_screen_20260922 as screen

ROOT=screen.ROOT
BASE=ROOT/'output/independent_research/high_screen_20260922'
OUT=ROOT/'output/independent_research/risk_check_20260923'

def main():
    source=json.loads((BASE/'result.json').read_text(encoding='utf-8'))
    assert screen.sha(Path(screen.__file__))==source['metadata']['script_sha256']
    for name,digest in source['metadata']['input_hashes'].items():
        assert screen.sha(ROOT/name)==digest
    selected=json.loads((BASE/'selections.json').read_text(encoding='utf-8'))
    cl=pd.read_parquet(screen.SRC/'fresh_close.parquet')
    dates=cl.QQQ.dropna().index;cl=cl.reindex(dates)
    op=pd.read_parquet(screen.SRC/'fresh_open.parquet').reindex(dates)
    col={s:i for i,s in enumerate(cl.columns)};oa=op.to_numpy();ca=cl.to_numpy()
    rows=[];cycles=[]
    for offset in [0,7,14]:
        group=[s for s in selected if s['offset']==offset]
        positions=[dates.get_loc(pd.Timestamp(s['day'])) for s in group]
        first=positions[0]+1;last=positions[-1]+20
        years=(dates[last]-dates[first]).days/365.25
        for weight in [.05,.1]:
            for cost in [.2,.5,1.]:
                for method in ['high','momentum','qqq']:
                    nav=np.ones(last-first+1);equity=1.;g=[]
                    for p,s in zip(positions,group):
                        ss=s[method];weights=([weight*len(s['high'])] if ss else []) if method=='qqq' else [weight]*len(ss)
                        path=screen.path(oa,ca,[col[t] for t in ss],p,20,cost,weights)
                        a=p+1-first;z=a+20;nav[a:z]=equity*path;equity*=path[-1];nav[z:]=equity
                        item={'offset':offset,'weight':weight,'cost':cost,'method':method,'day':s['day'],
                              'exposure':sum(weights),'return_pct':float((path[-1]-1)*100)}
                        g.append(item);cycles.append(item)
                    f=pd.DataFrame(g);active=f[f.exposure>0]
                    peak=np.maximum.accumulate(np.r_[1.,nav])[1:]
                    if weight==.1:
                        old=next(r for r in source['summary'] if r['offset']==offset and r['hold']==20 and r['cost']==cost and r['method']==method) if offset==0 or cost==.5 else None
                        if old:
                            assert abs(old['cagr_pct']-(equity**(1/years)-1)*100)<1e-10
                            assert abs(old['mdd_pct']-(nav/peak-1).min()*100)<1e-10
                    rows.append({'offset':offset,'method':method,'weight':weight,'cost':cost,'active':len(active),
                                 'basket_win_pct':float((active.return_pct>0).mean()*100),
                                 'cagr_pct':float((equity**(1/years)-1)*100),
                                 'mdd_pct':float((nav/peak-1).min()*100),
                                 'without_best3_cagr_pct':float(((equity/np.prod(1+f.return_pct.nlargest(3)/100))**(1/years)-1)*100)})
    all_cycles=pd.DataFrame(cycles)
    yearly=[]
    # Calendar-year paired cycle means; few years, correlated stocks/offsets.
    for (offset,weight,cost),g in all_cycles.groupby(['offset','weight','cost']):
        pivot=g.pivot(index='day',columns='method',values='return_pct')
        pivot['year']=pd.to_datetime(pivot.index).year
        for year,yg in pivot.groupby('year'):
            yearly.append({'offset':int(offset),'weight':weight,'cost':cost,'year':int(year),
                           'cycles':len(yg),'momentum_minus_qqq_mean_pp':float((yg.momentum-yg.qqq).mean()),
                           'high_minus_qqq_mean_pp':float((yg.high-yg.qqq).mean())})
    OUT.mkdir(parents=True,exist_ok=True)
    report={'metadata':{'script_sha256':screen.sha(Path(__file__)),'original_result_sha256':screen.sha(BASE/'result.json'),
                       'selections_sha256':screen.sha(BASE/'selections.json'),'policy':__doc__,
                       'limits':source['metadata']['limits']+['Half allocation chosen after initial result, not risk-matched optimization',
                       'Recorded CAGR and drawdown are not predictions; no probability of future success estimated']},
            'summary':rows,'yearly_pairs':yearly}
    (OUT/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    all_cycles.to_csv(OUT/'cycles.csv',index=False)
    print(pd.DataFrame(rows).query('cost==.5 and (weight==.05 or method=="qqq")').round(3).to_string(index=False))
    print('CORE REPLICATION PASSED; all 54 scenarios saved')

if __name__=='__main__':main()

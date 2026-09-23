"""Fixed original/experiment comparisons; pre-existing discovery data, NOT OOS.

Original J3 selection + tie handling is replayed in an isolated namespace.
No J3 mutation, no new optimal-weight search, no orders. 21-session samples.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import time
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import jarvis8_lab as lab
from research.audit_jarvis8_forward import account_path


def atomic_json(path,body):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(body,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
    for attempt in range(10):
        try:
            os.replace(temporary,path);return
        except PermissionError:
            if attempt==9:raise
            time.sleep(.2)


def run(limit=0):
    started=time.perf_counter()
    out=ROOT/'output/jarvis8'/('lab_smoke_0916' if limit else 'lab_0916')
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'output/jarvis3_audit_20260909'
    fields=['Open','High','Low','Close','Volume']
    source_paths=[source/f'fresh_{k.lower()}.parquet' for k in fields]+[source/'ixic_25year_warmup.parquet']
    code_paths=[ROOT/p for p in ('jarvis8_lab.py','jarvis3_data.py','us_swing_selector.py','jarvis8_engine.py',
                                  'jarvis8_data.py','research/audit_jarvis8_lab.py','research/audit_jarvis8_forward.py')]
    previous_path=ROOT/'output/jarvis8/forward_0914/checkpoint.json'
    signature={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
               for p in source_paths+code_paths+[previous_path]}
    # Reuse only already executed J8 arms with matching original input/engine hashes.
    previous=json.loads(previous_path.read_text(encoding='utf-8'))
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in previous['signature'].items())
    w={k:pd.read_parquet(source/f'fresh_{k.lower()}.parquet') for k in fields}
    dates=w['Close'].QQQ.dropna().index
    w={k:f.reindex(dates) for k,f in w.items()}
    frames={s:pd.DataFrame({k:f[s] for k,f in w.items()}).dropna(how='all') for s in w['Close']}
    ixic=pd.read_parquet(source/'ixic_25year_warmup.parquet')
    positions=list(range(274,len(dates)-20,21))
    if limit:positions=positions[:limit]
    checkpoint=out/'checkpoint.json'
    saved=json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.exists() else {}
    done=saved.get('dates',{}) if saved.get('signature')==signature else {}
    for count,pos in enumerate(positions,1):
        day=dates[pos];label=str(day.date())
        if label not in done:
            past={s:f.loc[day-pd.DateOffset(years=2):day] for s,f in frames.items()}
            b=lab.compare(lab.original_snapshot(past,ixic.loc[:day],day))
            picks={m:[r['ticker'] for r in rows[:5]] for m,rows in b['models'].items()}
            counts={m:len(rows) for m,rows in b['models'].items()}
            old=previous['dates'][label]
            if not old['ok']:raise ValueError('Previous J8 input missing at '+label)
            picks.update({'j8_'+m:v for m,v in old['picks'].items()})
            done[label]={'day':label,'picks':picks,'candidate_counts':counts,
                         'reference':b['reference'].get('reference_date'),
                         'score_blind':b['crash']['score_blind'],'score_weak':b['crash']['score_weak']}
            atomic_json(checkpoint,{'signature':signature,'dates':done})
        if count%10==0 or count==len(positions):
            print('LAB',count,'/',len(positions),label,'seconds',round(time.perf_counter()-started,1),flush=True)
    selections=[done[str(dates[p].date())] for p in positions]
    methods=list(selections[0]['picks'])
    holds=[1,3,5,10,20];costs=[0.,.2,.5,1.];ks=[1,5]
    first=positions[0]+1;last=positions[-1]+20
    years=(dates[last]-dates[first]).days/365.25
    all_rows=[];summaries=[];yearly=[];missing=[]
    for method in methods:
        for k in ks:
            for hold in holds:
                for cost in costs:
                    nav=np.ones(last-first+1);equity=1.;cycles=[];valid=True
                    for pos,selection in zip(positions,selections):
                        symbols=selection['picks'][method][:k]
                        exposure=.1*len(symbols)
                        try:
                            path=account_path(w['Open'],w['Close'],symbols,pos,hold,cost)
                            qqq=account_path(w['Open'],w['Close'],['QQQ'] if symbols else [],pos,hold,cost,exposure)
                        except ValueError as exc:
                            valid=False;missing.append({'day':selection['day'],'method':method,'k':k,'hold':hold,'cost':cost,'reason':str(exc)})
                            continue
                        start=pos+1-first;end=start+hold
                        nav[start:end]=equity*path;equity*=path[-1];nav[end:]=equity
                        row={'day':selection['day'],'method':method,'k':k,'hold':hold,'cost':cost,
                             'tickers':' '.join(symbols),'n':len(symbols),'return_pct':float((path[-1]-1)*100),
                             'qqq_return_pct':float((qqq[-1]-1)*100)}
                        all_rows.append(row);cycles.append(row)
                    f=pd.DataFrame(cycles);active=f[f.n>0]
                    peak=np.maximum.accumulate(np.r_[1.,nav])[1:]
                    r=active.return_pct
                    best=f.return_pct.nlargest(3).index
                    trimmed=f.return_pct.copy();trimmed.loc[best]=0
                    summaries.append({'method':method,'k':k,'hold':hold,'cost':cost,'cycles':len(f),
                        'active':len(active),'win_pct':float((r>0).mean()*100) if len(r) else None,
                        'mean_net_basket_pct':float((r/(active.n*.1)).mean()) if len(r) else None,
                        'mean_cycle_pct':float(f.return_pct.mean()),
                        'qqq_excess_cycle_pct':float((f.return_pct-f.qqq_return_pct).mean()),
                        'cagr_pct':float((equity**(1/years)-1)*100) if valid else None,
                        'mdd_pct':float((nav/peak-1).min()*100) if valid else None,
                        'without_best3_cagr_pct':float((np.prod(1+trimmed/100)**(1/years)-1)*100) if valid else None,
                        'complete':valid})
                    for year,g in f.groupby(pd.to_datetime(f.day).dt.year):
                        yearly.append({'method':method,'k':k,'hold':hold,'cost':cost,'signal_year':int(year),
                                       'cycle_return_pct':float((np.prod(1+g.return_pct/100)-1)*100)})
    f=pd.DataFrame(all_rows);f.to_csv(out/'cycles.csv',index=False)
    pd.DataFrame(summaries).to_csv(out/'summary.csv',index=False)
    pd.DataFrame(yearly).to_csv(out/'yearly.csv',index=False)
    pairs=[]
    for old,new in [('rise_original','rise2'),('crash_original','crash2'),
                    ('rise_original','j8_rise'),('crash_original','j8_crash_baseline')]:
        a=f[f.method==old];b=f[f.method==new]
        paired=a.merge(b,on=['day','k','hold','cost'],suffixes=('_old','_new'))
        for (k,h,cost),g in paired.groupby(['k','hold','cost']):
            delta=g.return_pct_new-g.return_pct_old
            different=g.tickers_old!=g.tickers_new
            yearmeans=delta.groupby(pd.to_datetime(g.day).dt.year).mean().to_numpy()
            rng=np.random.default_rng(20260916)
            boot=np.mean(rng.choice(yearmeans,size=(3000,len(yearmeans))),axis=1)
            pairs.append({'old':old,'new':new,'k':int(k),'hold':int(h),'cost':cost,
                          'dates':len(g),'changed_dates':int(different.sum()),
                          'mean_cycle_difference_pp':float(delta.mean()),
                          'mean_changed_difference_pp':float(delta[different].mean()) if different.any() else None,
                          'annual_block_low_pp':float(np.quantile(boot,.025)),
                          'annual_block_high_pp':float(np.quantile(boot,.975)),
                          'winning_signal_years':int((yearmeans>0).sum()),'signal_years':len(yearmeans)})
    pd.DataFrame(pairs).to_csv(out/'paired.csv',index=False)
    meta={'version':lab.VERSION,'signature':signature,'models':lab.MODELS,'completed':len(selections),
          'first_signal':selections[0]['day'],'last_signal':selections[-1]['day'],
          'first_entry':str(dates[first].date()),'last_exit':str(dates[last].date()),
          'grid':'every21 QQQ sessions; original historical selection and tie order at completed close',
          'entry_exit':'next open; hold1/3/5/10/20 exit at close; no overlapping cycles',
          'allocation':'top1 or top5; each10% including entry cost; rest cash without interest',
          'costs':'roundtrip0/0.2/0.5/1%, equally split entry and exit on actual notionals',
          'blind_dates':sum(s['score_blind'] for s in selections),
          'weak_dates':sum(s['score_weak'] for s in selections),'missing':missing,
          'scope':'J3 candidate selection/ties, not complete J3 page execution or an original sell rule',
          'limitations':['current surviving roster; not point-in-time','discovery data already seen; not OOS',
                         'sparse grid misses daily signals','index history clock anchored to signal date',
                         'J3 warnings recorded, not converted into a new cash rule',
                         'daily close MDD, not intraday; no corporate-action independent verification',
                         'annual bootstrap has few years; exploratory, not proof of future edge'],
          'elapsed_this_invocation_seconds':time.perf_counter()-started}
    result={'metadata':meta,'summary':summaries,'paired':pairs}
    atomic_json(out/'result.json',result)
    if not limit:atomic_json(ROOT/'data/jarvis8/lab_study.json',result)
    print(pd.DataFrame(summaries).query('k==5 and hold==20 and cost==0.5').round(3).to_string(index=False),flush=True)
    print('DONE missing',len(missing),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=0)
    run(parser.parse_args().limit)

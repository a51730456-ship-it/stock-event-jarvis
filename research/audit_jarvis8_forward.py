"""Forward returns of actual J8 selections on a fixed 21-session grid.

Discovery study of current survivors, not an unseen test or daily signal replay.
One position uses 10% of start-of-cycle equity, at most five, rest idle cash.
No overlapping cycles (holds 1/3/5/10/20 < 21). No leverage or cash interest.
"""
from pathlib import Path
import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def account_path(open_prices, close_prices, tickers, pos, hold, cost_pct=0., weight=.1):
    """Daily close liquidation NAV factors for a single nonoverlapping sleeve.

    Buy at pos+1 open. Terminal sales incur half the stated round-trip cost.
    Any missing held price makes the WHOLE sleeve unknown, not idle cash.
    """
    tickers=list(dict.fromkeys(tickers))
    if len(tickers)*weight>1+1e-12:
        raise ValueError('Allocation exceeds cash')
    if not tickers:
        return np.ones(hold)
    entry=open_prices.iloc[pos+1].reindex(tickers).to_numpy(float)
    closes=close_prices.iloc[pos+1:pos+hold+1].reindex(columns=tickers).to_numpy(float)
    if len(closes)!=hold or not np.isfinite(entry).all() or not np.isfinite(closes).all() or (entry<=0).any() or (closes<=0).any():
        raise ValueError('Missing or invalid selected forward price')
    half=cost_pct/200.
    invested=(closes/entry/(1+half)*weight).sum(axis=1)
    nav=1-weight*len(tickers)+invested
    nav[-1]-=invested[-1]*half
    return nav


def main():
    import jarvis8_engine as engine
    start=time.perf_counter()
    out=ROOT/'output/jarvis8/forward_0914';out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'output/jarvis3_audit_20260909'
    source_paths=[source/f'fresh_{k.lower()}.parquet' for k in engine.FIELDS]+[source/'ixic_25year_warmup.parquet']
    signature_paths=source_paths+[ROOT/p for p in ['jarvis8_engine.py','jarvis8_data.py','jarvis3_data.py','us_swing_selector.py','data/jarvis8/universe.json','us_market_calendar.py']]
    signature={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in signature_paths}
    checkpoint=out/'checkpoint.json'
    saved=json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.exists() else {}
    completed=saved.get('dates',{}) if saved.get('signature')==signature else {}
    engine_hashes={p:signature[p] for p in ['jarvis8_engine.py','jarvis8_data.py','jarvis3_data.py','us_swing_selector.py','data/jarvis8/universe.json','us_market_calendar.py']}
    w={k:pd.read_parquet(source/f'fresh_{k.lower()}.parquet') for k in engine.FIELDS}
    dates=w['Close']['QQQ'].dropna().index
    w={k:f.reindex(dates) for k,f in w.items()}
    frames={s:pd.DataFrame({k:f[s] for k,f in w.items()}).dropna(how='all') for s in w['Close']}
    ix=pd.read_parquet(source/'ixic_25year_warmup.parquet')
    methods=['rise','crash_baseline','crash_recovery60','reversal','momentum']
    holds=[1,3,5,10,20];costs=[0.,.2,.5,1.]
    positions=list(range(274,len(dates)-20,21))
    trades=[];checks=[];unknown=[];curves={};equities={}
    first=positions[0]+1;last=positions[-1]+20
    for method in methods:
        for h in holds:
            for cost in costs:
                key=(method,h,cost)
                curves[key]=np.ones(last-first+1)
                equities[key]=1.
    for count,pos in enumerate(positions,1):
        day=dates[pos]
        day_key=str(day.date())
        if day_key not in completed:
            past={s:f.loc[day-pd.DateOffset(years=2):day] for s,f in frames.items()}
            try:
                b=engine.build(past,day,ix.loc[:day])
                picks={
                    'rise':[r['ticker'] for r in b['rise']['primary_rows'][:5]],
                    'crash_baseline':[r['ticker'] for r in b['crash'][:5]],
                    'crash_recovery60':[r['ticker'] for r in sorted(b['crash'],key=lambda r:(-r['score'],r['ticker']))[:5]],
                    'reversal':[r['ticker'] for r in b['reversal'][:5]],
                    'momentum':[r['ticker'] for r in b['momentum'][:5]]}
                completed[day_key]={'day':day_key,'ok':True,'valid':b['valid'],'excluded':b['excluded'],
                                    'picks':picks,'input_hashes':b['input_hashes']}
            except ValueError as exc:
                completed[day_key]={'day':day_key,'ok':False,'reason':str(exc)}
            temporary=out/'checkpoint.tmp'
            temporary.write_text(json.dumps({'signature':signature,'dates':completed},ensure_ascii=False),encoding='utf-8')
            # Windows indexers may briefly hold the last snapshot open.
            for attempt in range(10):
                try:
                    os.replace(temporary,checkpoint)
                    break
                except PermissionError:
                    if attempt==9:raise
                    time.sleep(.2)
        check=completed[day_key];checks.append(check)
        if not check['ok']:continue
        picks=check['picks']
        for method,symbols in picks.items():
            for h in holds:
                try:
                    gross=account_path(w['Open'],w['Close'],symbols,pos,h,0.)
                    exposure=.1*len(symbols)
                    qqq=account_path(w['Open'],w['Close'],['QQQ'] if symbols else [],pos,h,0.,exposure)
                except ValueError as exc:
                    unknown.append({'day':str(day.date()),'method':method,'hold':h,'tickers':symbols,'error':str(exc)})
                    continue
                for cost in costs:
                    path=account_path(w['Open'],w['Close'],symbols,pos,h,cost)
                    matched=account_path(w['Open'],w['Close'],['QQQ'] if symbols else [],pos,h,cost,exposure)
                    key=(method,h,cost)
                    a=pos+1-first;z=a+h
                    curves[key][a:z]=equities[key]*path
                    equities[key]*=path[-1]
                    curves[key][z:]=equities[key]
                    trades.append({'day':str(day.date()),'method':method,'hold':h,'cost_pct':cost,
                        'tickers':' '.join(symbols),'n':len(symbols),'exposure_pct':exposure*100,
                        'account_return_pct':(path[-1]-1)*100,
                        'stock_basket_return_pct':((gross[-1]-1)/exposure*100) if symbols else None,
                        'matched_qqq_return_pct':(matched[-1]-1)*100,
                        'daily_close_trough_pct':(min(1.,path.min())-1)*100})
        if count%10==0:
            (out/'progress.json').write_text(json.dumps({'completed':count,'total':len(positions),'last_day':str(day.date())}),encoding='utf-8')
            print('J8_FORWARD',count,'/',len(positions),str(day.date()),flush=True)
    t=pd.DataFrame(trades);t.to_csv(out/'cycles.csv',index=False)
    (out/'selections.json').write_text(json.dumps(checks,ensure_ascii=False,default=str),encoding='utf-8')
    summary=[];yearly=[]
    for (method,h,cost),g in t.groupby(['method','hold','cost_pct']):
        active=g[g.n>0];curve=curves[(method,h,cost)]
        invalid=any(not x['ok'] for x in checks) or any(x['method']==method and x['hold']==h for x in unknown)
        # Flat cash intervals are present; drawdown uses daily close NAV, not intraday lows.
        years=(dates[last]-dates[first]).days/365.25
        peak=np.maximum.accumulate(np.r_[1.,curve])[1:]
        summary.append({'method':method,'hold':int(h),'cost_pct':cost,'cycles':len(g),'active_cycles':len(active),
            'stock_observations':int(active.n.sum()),'mean_basket_gross_pct':float(active.stock_basket_return_pct.mean()) if len(active) else None,
            'positive_net_basket_pct':float((active.account_return_pct>0).mean()*100) if len(active) else None,
            'mean_account_cycle_pct':float(g.account_return_pct.mean()),
            'mean_active_qqq_excess_pct':float((active.account_return_pct-active.matched_qqq_return_pct).mean()) if len(active) else None,
            'total_return_pct':float((curve[-1]-1)*100) if not invalid else None,
            'cagr_pct':float((curve[-1]**(1/years)-1)*100) if not invalid else None,
            'max_daily_close_drawdown_pct':float((curve/peak-1).min()*100) if not invalid else None,
            'account_complete':not invalid})
        for year,yg in g.groupby(pd.to_datetime(g.day).dt.year):
            yearly.append({'method':method,'hold':h,'cost_pct':cost,'year':int(year),
                           'cycle_compound_return_pct':float((np.prod(1+yg.account_return_pct/100)-1)*100)})
    pd.DataFrame(summary).to_csv(out/'summary.csv',index=False)
    pd.DataFrame(yearly).to_csv(out/'yearly.csv',index=False)
    pd.DataFrame(curves,index=dates[first:last+1]).to_csv(out/'daily_equity.csv')
    meta={'engine_version':engine.VERSION,'engine_hashes':engine_hashes,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'first_signal':str(dates[positions[0]].date()),'last_signal':str(dates[positions[-1]].date()),
          'first_entry':str(dates[first].date()),'last_exit':str(dates[last].date()),
          'sample_grid':'every 21 QQQ trading sessions, starting at offset 274; 1/3/5/10/20-day holds',
          'position_policy':'top at most 5; 10% starting equity each incl entry cost; rest cash; no leverage or interest',
          'cost_policy':'half roundtrip percentage on entry and half on exit, proportional to actual notionals',
          'invalid_forward_cycles':unknown,'invalid_signal_dates':[x for x in checks if not x['ok']],
          'seconds':time.perf_counter()-start,
          'limitations':['Discovery sample previously seen; not out of sample','Current surviving universe and memberships',
                        'Sparse grid misses transient daily signals','EOD signals, next open fills; no intraday slippage model',
                        'Daily close drawdown excludes intraday loss','Corporate action and single-provider pricing limitations remain',
                        'Missing selected future prices make account metrics unavailable, not cash',
                        'This 10% top-five policy is a comparison assumption, not an optimized allocation']}
    (out/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    # Small self-contained read-only asset for the evidence screen; not production prices.
    (ROOT/'data/jarvis8/forward_study.json').write_text(json.dumps({'metadata':meta,'summary':summary},ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(pd.DataFrame(summary).query('hold in [3,20] and cost_pct==0.5').round(3).to_string(index=False),flush=True)
    print('DONE',meta['seconds'], 'unknown',len(unknown),flush=True)


if __name__=='__main__':
    main()

"""Matched-date, fixed-count score comparison; discovery data, NOT out of sample.

Choose ranks before looking at returns. Evaluate non-overlapping calendar sleeves
as a sensitivity check. Missing selected returns invalidate BOTH arms of a pair.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/jarvis8';OUT.mkdir(exist_ok=True)
SOURCE=ROOT/'output/jarvis3_audit_20260909'
c=pd.read_csv(SOURCE/'crash_app_observable_events.csv',parse_dates=['day'])
c=c[c.armed].copy()
calendar=pd.read_parquet(ROOT/'research/_data/us_wide/close.parquet').index
position={day:i for i,day in enumerate(calendar)}
rows=[];missing=[]
for day,g in c.groupby('day',sort=True):
    for k in [3,5]:
        if len(g)<k:continue
        a=g.sort_values(['score','ticker'],ascending=[False,True]).head(k)
        b=g.sort_values(['no_vol_score','ticker'],ascending=[False,True]).head(k)
        for h in [1,3,5,10,20]:
            if position[day]+h>=len(calendar):continue
            if a[f'r{h}'].isna().any() or b[f'r{h}'].isna().any():
                missing.append({'day':str(day.date()),'k':k,'hold':h});continue
            rows.append({'day':day,'k':k,'hold':h,'calendar_position':position[day],
                         'old':a[f'r{h}'].mean(),'recovery60':b[f'r{h}'].mean(),
                         'overlap':len(set(a.ticker)&set(b.ticker)),
                         'old_tickers':' '.join(a.ticker),'new_tickers':' '.join(b.ticker)})
p=pd.DataFrame(rows);p['difference']=p.recovery60-p.old
p.to_csv(OUT/'crash_matched_pairs.csv',index=False)
rng=np.random.default_rng(20260914);summary=[];years=[]
for (k,h),g in p.groupby(['k','hold']):
    yr=g.groupby(g.day.dt.year).difference.mean()
    boot=np.array([rng.choice(yr.to_numpy(),len(yr),replace=True).mean() for _ in range(3000)])
    sleeves=[]
    for offset in range(h):
        sleeve=g[g.calendar_position%h==offset]
        if len(sleeve):sleeves.append(float(sleeve.difference.mean()))
    summary.append({'k':int(k),'hold':int(h),'dates':len(g),'old_mean':g.old.mean(),
                    'recovery_mean':g.recovery60.mean(),'difference':g.difference.mean(),
                    'old_positive_pct':(g.old>0).mean()*100,'recovery_positive_pct':(g.recovery60>0).mean()*100,
                    'mean_overlap':g.overlap.mean(),'positive_years':int((yr>0).sum()),'years':len(yr),
                    'equal_year_difference':yr.mean(),'year_boot_low':np.quantile(boot,.025),'year_boot_high':np.quantile(boot,.975),
                    'calendar_sleeve_min_difference':min(sleeves),'calendar_sleeve_max_difference':max(sleeves)})
    for year,v in yr.items():years.append({'k':k,'hold':h,'year':year,'difference':v})
pd.DataFrame(summary).to_csv(OUT/'crash_matched_summary.csv',index=False)
pd.DataFrame(years).to_csv(OUT/'crash_matched_years.csv',index=False)
(OUT/'crash_matched_limits.json').write_text(json.dumps({'missing_selected_pairs':missing,
    'selection':'same day same candidate universe; top k; alphabetical ties; rank before future return check',
    'win_definition':'percentage of positive equal-weight basket outcomes, not stock win rate',
    'bootstrap':'resample annual mean differences with equal year weight; few years, exploratory only',
    'sleeves':'all offsets of nonoverlapping calendar-horizon samples; no account equity or intraday MDD',
    'cost':'same k and holding horizon; constant roundtrip costs subtract equally from both means',
    'limitations':'current survivors; correlated crises; old cached price anomalies; extensive prior exploration'},indent=2),encoding='utf-8')
print(pd.DataFrame(summary).round(4).to_string(index=False))

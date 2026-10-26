"""Reproducible prospective-style 2021 out-of-time bloom-proxy benchmark.

Real source: historical station-month chlorophyll and water quality from the
user-provided Water Atlas-derived Lake Okeechobee CSV (2019-2021).
All output labels are explicitly proxies based on the supplied 40 ug/L
chlorophyll threshold. This is not a satellite-fusion or HAB-toxicity test.

Run: python backend/historical_backtest.py
"""
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'backend/data/lake_okeechobee_station_month_2019_2021.csv'
OUT = ROOT / 'frontend/public/historical_backtest_2021.json'
MODEL_OUT = ROOT / 'backend/models/xgb_insitu_trend_baseline.json'
PARAMS = ('temperature_c_median','pH_median','DO_mg_l_median')
FEATURE_NAMES = [f'{k}_t' for k in PARAMS] + [f'{k}_prev' for k in PARAMS] + [f'{k}_delta' for k in PARAMS]


def month_next(m):
    d=datetime.strptime(m, '%Y-%m')
    y = d.year + (d.month == 12)
    m2 = (d.month % 12) + 1
    return f'{y:04}-{m2:02}'


def load():
    with SRC.open(newline='',encoding='utf-8-sig') as f:
        data=list(csv.DictReader(f))
    by_station={}
    for r in data:
        by_station.setdefault(r['station_id'], {})[r['month']] = r
    examples=[]
    for sid,months in by_station.items():
        for m, row in months.items():
            prev = months.get(next((p for p in months if month_next(p)==m), ''))
            following = months.get(month_next(m))
            if prev is None or following is None:
                continue
            try:
                cur = [float(row[k]) for k in PARAMS]
                old = [float(prev[k]) for k in PARAMS]
                target = int(following['observed_bloom_proxy_event_40ug_l'])
                if target not in (0,1): continue
                features = cur + old + [a-b for a,b in zip(cur,old)]
                if not np.isfinite(features).all(): continue
            except (ValueError, KeyError, TypeError):
                continue
            examples.append({'station_id':sid,'input_month':m,'target_month':month_next(m),
                             'features':features,'actual':target,
                             'actual_next_month_chlorophyll_ug_l':float(following['insitu_chl_a_ug_l_median']),
                             'actual_next_month_chlorophyll_max_ug_l':float(following['insitu_chl_a_ug_l_max']),
                             'current_inputs':dict(zip(PARAMS, cur)),
                             'monthly_delta':dict(zip(PARAMS,[a-b for a,b in zip(cur,old)]))})
    return data, sorted(examples,key=lambda x:(x['target_month'],x['station_id']))


def main():
    original,examples=load()
    train=[x for x in examples if x['target_month'] < '2021-01']
    test=[x for x in examples if '2021-01'<=x['target_month']<='2021-12']
    assert train and test, 'Not enough historical data'
    ytr = np.asarray([x['actual'] for x in train])
    yte = np.asarray([x['actual'] for x in test])
    print('Source rows:', len(original), 'Train pairs:',len(train),'Test pairs:',len(test))
    print('Training positives:',int(ytr.sum()),'Test positives:',int(yte.sum()))
    if len(set(ytr))<2:
        raise SystemExit('Training set only contains one class; evaluation unavailable')
    ratio = float((ytr==0).sum()/max(1,(ytr==1).sum()))
    model=XGBClassifier(n_estimators=100,max_depth=2,learning_rate=0.04,
                        min_child_weight=2, subsample=0.9,colsample_bytree=0.9,
                        reg_lambda=5,scale_pos_weight=ratio,
                        eval_metric='logloss',random_state=42,n_jobs=1)
    model.fit(np.asarray([x['features'] for x in train]), ytr)
    probs=model.predict_proba(np.asarray([x['features'] for x in test]))[:,1]
    pred=(probs>=0.5).astype(int)
    baseline=np.zeros_like(yte)
    def metrics(yhat):
        tn,fp,fn,tp=[int(v) for v in confusion_matrix(yte,yhat,labels=[0,1]).ravel()]
        return {'accuracy':round(float(accuracy_score(yte,yhat)),4),
                'precision':round(float(precision_score(yte,yhat,zero_division=0)),4),
                'recall':round(float(recall_score(yte,yhat,zero_division=0)),4),
                'f1':round(float(f1_score(yte,yhat,zero_division=0)),4),
                'correct':int((yhat==yte).sum()),'total':len(yte),
                'confusion':{'TN':tn,'FP':fp,'FN':fn,'TP':tp}}
    rows=[]
    for item,p,yhat in zip(test,probs,pred):
        rows.append({**{k:v for k,v in item.items() if k!='features'},
                     'probability':round(float(p),4),'predicted':int(yhat),
                     'correct':bool(yhat==item['actual'])})
    eight={}
    for station in sorted({r['station_id'] for r in rows}):
        station_rows=[r for r in rows if r['station_id']==station][:8]
        eight[station]=station_rows
    payload={
        'dataset':'Lake Okeechobee Water Atlas-derived historical station-month observations (2019-2021)',
        'test_type':'REAL_HISTORICAL_INSITU_ONLY_NEXT_MONTH_PROXY_BACKTEST',
        'split':'Train target months up to December 2020; held-out target months January-December 2021',
        'model':'Separate XGBoost sensor-trend baseline, NOT the saved five-feature satellite-fusion model',
        'target':'Following-month maximum in-situ chlorophyll-a >= 40 ug/L; proxy event only, not toxicity or verified HAB',
        'real_satellite_used':False,
        'time_features':FEATURE_NAMES,
        'source_rows':len(original), 'training_examples':len(train), 'test_examples':len(test),
        'training_positives':int(ytr.sum()),'test_positives':int(yte.sum()),
        'metrics':metrics(pred),'always_no_bloom_baseline':metrics(baseline),
        'eight_month_by_station':eight,
        'all_test_results':rows,
        'limitations':['Only a chlorophyll-based proxy; not verified harmful blooms',
                       'Historical Okeechobee satellite feature values absent; do not claim satellite-fusion validation',
                       'Potential station-level dependence and small positive class; results preliminary',
                       'No Laguna de Bay model accuracy implied']}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    MODEL_OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,indent=2),encoding='utf-8')
    model.save_model(MODEL_OUT)
    print('Model', payload['metrics'])
    print('Always-negative',payload['always_no_bloom_baseline'])
    for s in sorted(eight):
        print('station',s,':',[(x['target_month'],x['correct']) for x in eight[s]])
    print('Report:',OUT,'Model:',MODEL_OUT)

if __name__=='__main__': main()

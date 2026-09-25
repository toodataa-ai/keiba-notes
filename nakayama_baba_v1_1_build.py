import json, math
from pathlib import Path
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

# 2018-2025 September Nakayama weekends.
# sat_moist/sun_moist = average of JRA turf moisture at finish + 4C.
# sat_rain = JMA Funabashi daily precipitation on Saturday.
# sun_01_06_rain = JMA Funabashi precipitation from 01:00 through 06:00 Sunday.
# Some zero values were verified from hourly/10-min pages; where the station page showed
# no measurable precipitation in that window, zero is used. One 2022-09-18 zero is lower-confidence.
DATA = [
[2018,'09-08',11.75, 9.35, 0.0, 0.0,'verified'],
[2018,'09-15',11.30,11.85,11.0, 0.0,'verified'],
[2018,'09-22',13.90,12.00, 0.5, 0.0,'verified'],
[2018,'09-29',11.75,14.45, 9.5,15.5,'verified'],
[2019,'09-07',10.20, 9.75, 0.0, 0.0,'verified'],
[2019,'09-14',12.05,11.85, 2.5, 0.0,'verified'],
[2019,'09-21',11.00,11.25, 0.0, 0.0,'verified'],
[2019,'09-28',10.30,10.30, 0.0, 0.0,'verified'],
[2020,'09-12', 9.95,10.95, 4.5, 0.0,'verified'],
[2020,'09-19',11.25,10.20, 0.0, 0.0,'verified'],
[2020,'09-26',12.75,12.75, 3.5, 0.0,'verified'],
[2021,'09-11',12.60,12.85, 0.0, 0.0,'verified'],
[2021,'09-18',11.30,14.95,52.5, 2.0,'verified'],
[2021,'09-25',12.45,11.80, 0.0, 0.0,'verified'],
[2022,'09-10',13.05,13.55, 0.0, 0.0,'verified'],
[2022,'09-17',11.85,12.70, 0.0, 0.0,'inferred_zero'],
[2022,'09-24',15.95,13.75,51.5, 0.0,'verified'],
[2023,'09-09',17.65,15.20,14.5, 0.0,'verified'],
[2023,'09-16',15.25,14.05, 0.0, 0.0,'verified'],
[2024,'09-07',13.20,13.55, 0.0, 0.0,'verified'],
[2024,'09-14',13.85,13.50, 0.0, 0.0,'verified'],
[2024,'09-21',13.50,12.90, 0.0, 1.5,'verified'],
[2024,'09-28',14.00,13.90, 0.0, 0.0,'verified'],
[2025,'09-06',14.45,13.05, 0.0, 0.0,'verified'],
[2025,'09-13',15.70,13.20,32.0, 0.0,'verified'],
[2025,'09-20',13.85,13.55, 0.0, 0.0,'verified'],
[2025,'09-27',12.30,12.40, 0.0, 0.0,'verified'],
]
COLS=['year','saturday','sat_moist','sun_moist','sat_rain_mm','sun_01_06_rain_mm','timing_quality']


def frame():
    df=pd.DataFrame(DATA,columns=COLS)
    df['delta']=df['sun_moist']-df['sat_moist']
    return df


def features_v1(df):
    return pd.DataFrame({
        'sat_moist':df['sat_moist'],
        'rain_sqrt':np.sqrt(df['sat_rain_mm']),
        'rain_log':np.log1p(df['sat_rain_mm']),
        'wet_excess':np.maximum(df['sat_moist']-13.0,0.0),
    })


def features_timing(df):
    return pd.DataFrame({
        'sat_moist':df['sat_moist'],
        'sat_rain_sqrt':np.sqrt(df['sat_rain_mm']),
        'overnight_rain_sqrt':np.sqrt(df['sun_01_06_rain_mm']),
        'overnight_rain_log':np.log1p(df['sun_01_06_rain_mm']),
        'overnight_rain_flag':(df['sun_01_06_rain_mm']>0).astype(float),
        'wet_excess':np.maximum(df['sat_moist']-13.0,0.0),
    })


def new_v1_model():
    return RandomForestRegressor(n_estimators=1200,max_depth=3,min_samples_leaf=2,random_state=26)


def new_timing_model():
    # Predict change from Sat->Sun rather than absolute level. This makes the timing
    # component focus on wetting/drying. Huber loss limits small-sample outlier leverage.
    return GradientBoostingRegressor(n_estimators=100,max_depth=2,learning_rate=0.03,loss='huber',random_state=26)


def loyo_backtest():
    df=frame()
    p_v1=np.zeros(len(df)); p_timing=np.zeros(len(df))
    for yr in sorted(df.year.unique()):
        tr=df.year!=yr; te=df.year==yr
        m1=new_v1_model(); m1.fit(features_v1(df.loc[tr]),df.loc[tr,'sun_moist'])
        p_v1[te]=m1.predict(features_v1(df.loc[te]))
        mt=new_timing_model(); mt.fit(features_timing(df.loc[tr]),df.loc[tr,'delta'])
        p_timing[te]=df.loc[te,'sat_moist'].to_numpy()+mt.predict(features_timing(df.loc[te]))
    # Conservative fixed blend: level model + timing-sensitive delta model.
    p_v11=0.5*p_v1+0.5*p_timing
    out=df.copy(); out['cv_v1']=p_v1; out['cv_timing']=p_timing; out['cv_v11']=p_v11
    out['abs_err_v1']=abs(out.cv_v1-out.sun_moist); out['abs_err_v11']=abs(out.cv_v11-out.sun_moist)
    def metrics(p):
        e=np.abs(p-df.sun_moist.to_numpy())
        return {
            'n':len(df),
            'mae':float(e.mean()),
            'rmse':float(np.sqrt(np.mean((p-df.sun_moist.to_numpy())**2))),
            'within_0_5pt':float(np.mean(e<=0.5)),
            'within_1_0pt':float(np.mean(e<=1.0)),
            'within_1_5pt':float(np.mean(e<=1.5)),
            'within_2_0pt':float(np.mean(e<=2.0)),
            'max_abs_error':float(e.max()),
        }
    return out, {'v1_baseline':metrics(p_v1),'v1_1':metrics(p_v11)}


def fit_final_models():
    df=frame()
    m1=new_v1_model(); m1.fit(features_v1(df),df.sun_moist)
    mt=new_timing_model(); mt.fit(features_timing(df),df.delta)
    return df,m1,mt


def condition_probs(moist_mean, sigma=1.05):
    # Operational probability mapping only. JRA's official Going is NOT mechanically
    # determined by moisture alone, and the JRA moisture bands overlap.
    centers={'良':11.9,'稍重':13.5,'重':16.0,'不良':18.5}
    scales={'良':1.25,'稍重':1.25,'重':1.40,'不良':1.55}
    # incorporate model uncertainty by broadening each component
    raw={}
    for k,c in centers.items():
        s=math.sqrt(scales[k]**2+sigma**2)
        raw[k]=math.exp(-0.5*((moist_mean-c)/s)**2)/s
    z=sum(raw.values())
    return {k:v/z for k,v in raw.items()}


def predict_sunday_morning(sat_moist, sat_rain_mm, sun_01_06_rain_mm=0.0):
    df,m1,mt=fit_final_models()
    r=pd.DataFrame([{
        'sat_moist':sat_moist,'sat_rain_mm':sat_rain_mm,
        'sun_01_06_rain_mm':sun_01_06_rain_mm
    }])
    p1=float(m1.predict(features_v1(r))[0])
    pt=float(sat_moist+mt.predict(features_timing(r))[0])
    p=0.5*p1+0.5*pt
    return {
        'predicted_sunday_morning_moisture':round(p,2),
        'components':{'level_model':round(p1,2),'timing_delta_model':round(pt,2)},
        'condition_probs_operational':{k:round(v,4) for k,v in condition_probs(p).items()},
    }


def update_to_race_time(sunday_morning_moist, rain_after_measurement_mm=0.0,
                        hours_since_last_rain=None, temperature_c=22.0,
                        wind_mps=2.0, sunshine_hours=0.0, target_hours=9.5):
    """Operational v1.1 race-time updater (NOT backtested yet).

    The JRA archive gives morning moisture, not a dense intraday target series, so this
    layer intentionally returns a range rather than pretending to be a validated point model.
    It is designed to be replaced/calibrated when race-time labels are collected.
    """
    # modest rain uptake; diminishing return at high rainfall
    wetting=0.20*math.sqrt(max(rain_after_measurement_mm,0.0)) + 0.012*max(rain_after_measurement_mm,0.0)
    # drying score per hour: warmer/windier/sunnier conditions accelerate drying.
    dry_per_hour=0.035 + 0.003*max(temperature_c-18.0,0.0) + 0.010*max(wind_mps-1.0,0.0)
    dry_per_hour += 0.020*max(sunshine_hours,0.0)/max(target_hours,1.0)
    if rain_after_measurement_mm>0 and hours_since_last_rain is not None:
        effective_dry_hours=min(max(hours_since_last_rain,0.0),target_hours)
    elif rain_after_measurement_mm==0:
        effective_dry_hours=target_hours
    else:
        effective_dry_hours=target_hours*0.35
    drying=dry_per_hour*effective_dry_hours
    mid=sunday_morning_moist+wetting-drying
    # Wider uncertainty because intraday layer is not yet historically calibrated.
    half_width=0.9 + 0.10*math.sqrt(max(rain_after_measurement_mm,0.0))
    lo=max(5.0,mid-half_width); hi=mid+half_width
    probs=condition_probs(mid,sigma=1.45)
    return {
        'race_time_moisture_midpoint_heuristic':round(mid,2),
        'race_time_moisture_range_heuristic':[round(lo,2),round(hi,2)],
        'condition_probs_operational':{k:round(v,4) for k,v in probs.items()},
        'validation_status':'intraday layer is operational heuristic, not yet backtested',
    }


def main(outdir):
    outdir=Path(outdir); outdir.mkdir(parents=True,exist_ok=True)
    bt,metrics=loyo_backtest()
    payload={
        'model':'Nakayama turf condition model v1.1',
        'scope':'September Nakayama turf; Sat morning -> Sun morning',
        'features':['Saturday morning JRA turf moisture avg','Saturday Funabashi daily rain','Sunday 01:00-06:00 Funabashi rain'],
        'rows':frame().to_dict(orient='records'),
        'metrics':metrics,
        'notes':[
            'LOYO = leave-one-year-out cross validation.',
            'v1.1 final is a fixed 50/50 blend of the v1 level model and a timing-sensitive delta model.',
            'Going probabilities are operational, not an official JRA classifier.',
            'Race-time updater is not backtested in v1.1 because historical race-time JRA moisture labels are not densely published.'
        ]
    }
    (outdir/'nakayama_baba_v1_1_data.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    bt.to_csv(outdir/'nakayama_baba_v1_1_predictions.csv',index=False,encoding='utf-8-sig')
    lines=[]
    for name,m in metrics.items():
        lines += [name, json.dumps(m,ensure_ascii=False,indent=2), '']
    lines += ['Per-row LOYO predictions:',bt[['year','saturday','sat_moist','sat_rain_mm','sun_01_06_rain_mm','sun_moist','cv_v1','cv_timing','cv_v11','abs_err_v1','abs_err_v11']].to_string(index=False)]
    (outdir/'nakayama_baba_v1_1_backtest.txt').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(metrics,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main(Path(__file__).resolve().parent)

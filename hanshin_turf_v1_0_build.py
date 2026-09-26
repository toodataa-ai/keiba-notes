import json, math
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
DATA_PATH=Path(__file__).with_name('hanshin_turf_v1_0_data.json')
SURFACE='turf'

def _df(): return pd.DataFrame(json.loads(DATA_PATH.read_text(encoding='utf-8'))['rows'])
def _feat(d):
 x=d[SURFACE+'_sat']; return pd.DataFrame({'sat_moist':x,'month6':(d.month==6).astype(int),'month7':(d.month==7).astype(int),'month9':(d.month==9).astype(int),'wet_excess':np.maximum(x-(14.0),0),'post_2025_regime':(d.year>=2025).astype(int)})
def _model():
 d=_df(); m=make_pipeline(StandardScaler(),Ridge(alpha=3.0)); m.fit(_feat(d),d[SURFACE+'_sun']); return m
def condition_probs(m,sigma=1.498):
 centers={'良':11.3,'稍重':14.0,'重':16.2,'不良':18.8}; scales={'良':1.6,'稍重':1.55,'重':1.65,'不良':1.9}; raw={}
 for k,c in centers.items():
  s=(scales[k]**2+sigma**2)**.5; raw[k]=math.exp(-.5*((m-c)/s)**2)/s
 z=sum(raw.values()); return {k:v/z for k,v in raw.items()}
def predict_sunday_morning(sat_moist,month=9,post_2025_regime=True):
 d=pd.DataFrame([{'year':2026 if post_2025_regime else 2023,'month':month,'turf_sat':sat_moist}]); p=float(_model().predict(_feat(d))[0]); return {'baseline_sunday_morning_moisture':round(p,2),'baseline_uncertainty_pt':1.50,'condition_probs_operational':{k:round(v,4) for k,v in condition_probs(p).items()},'warning':'Hanshin v1.0 baseline has no fully joined overnight-rain feature; widen uncertainty when rain is forecast.'}
def update_to_race_time(morning_moist,rain_after_measurement_mm=0,hours_since_last_rain=None,temperature_c=22,wind_mps=2,sunshine_hours=0,target_hours=6.25):
 rain=max(rain_after_measurement_mm,0)
 wet=.20*math.sqrt(rain)+.012*rain
 dry=.035+.003*max(temperature_c-18,0)+.010*max(wind_mps-1,0)+.020*sunshine_hours/max(target_hours,1)
 hw=1.2+.12*math.sqrt(rain)
 dry_hours=target_hours if rain==0 else min(max(hours_since_last_rain or 0,0),target_hours)
 mid=morning_moist+wet-dry*dry_hours
 return {'race_time_moisture_midpoint_heuristic':round(mid,2),'race_time_moisture_range_heuristic':[round(max(0,mid-hw),2),round(mid+hw,2)],'condition_probs_operational':{k:round(v,4) for k,v in condition_probs(mid, max(1.498,1.5)).items()},'validation_status':'operational heuristic; not backtested'}

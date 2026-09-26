import json, math
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
DATA_PATH=Path(__file__).with_name('nakayama_dirt_v1_1_data.json')

def _df(): return pd.DataFrame(json.loads(DATA_PATH.read_text(encoding='utf-8'))['rows'])
def _fl(d): return pd.DataFrame({'sat_moist':d.sat_moist,'rain_sqrt':np.sqrt(d.sat_rain_mm),'rain_log':np.log1p(d.sat_rain_mm),'wet_excess':np.maximum(d.sat_moist-9.0,0)})
def _fd(d): return pd.DataFrame({'sat_moist':d.sat_moist,'sat_rain_sqrt':np.sqrt(d.sat_rain_mm),'overnight_rain_sqrt':np.sqrt(d.sun_01_06_rain_mm),'overnight_rain_log':np.log1p(d.sun_01_06_rain_mm),'overnight_rain_flag':(d.sun_01_06_rain_mm>0).astype(float),'wet_excess':np.maximum(d.sat_moist-9.0,0)})
def _models():
 d=_df(); d['delta']=d.sun_moist-d.sat_moist
 m1=RandomForestRegressor(n_estimators=300,max_depth=3,min_samples_leaf=2,random_state=26,n_jobs=-1)
 md=GradientBoostingRegressor(n_estimators=60,max_depth=2,learning_rate=.03,loss='huber',random_state=26)
 m1.fit(_fl(d),d.sun_moist); md.fit(_fd(d),d.delta); return m1,md

def condition_probs(m,sigma=2.1):
 centers={'良':5.5,'稍重':9.8,'重':13.4,'不良':16.8}; scales={'良':1.7,'稍重':1.8,'重':1.8,'不良':2.0}; raw={}
 for k,c in centers.items():
  s=(scales[k]**2+sigma**2)**.5; raw[k]=math.exp(-.5*((m-c)/s)**2)/s
 z=sum(raw.values()); return {k:v/z for k,v in raw.items()}
def predict_sunday_morning(sat_moist,sat_rain_mm,sun_01_06_rain_mm=0):
 m1,md=_models(); r=pd.DataFrame([{'sat_moist':sat_moist,'sat_rain_mm':sat_rain_mm,'sun_01_06_rain_mm':sun_01_06_rain_mm}])
 p1=float(m1.predict(_fl(r))[0]); pdelta=float(sat_moist+md.predict(_fd(r))[0]); p=.5*(p1+pdelta)
 return {'predicted_sunday_morning_moisture':round(p,2),'uncertainty_hint_pt':2.1,'condition_probs_operational':{k:round(v,4) for k,v in condition_probs(p).items()}}
def update_to_race_time(morning_moist,rain_after_measurement_mm=0,hours_since_last_rain=None,temperature_c=22,wind_mps=2,sunshine_hours=0,target_hours=6.25):
 # Dirt reacts quickly to rain; this layer is intentionally heuristic and not backtested.
 rain=max(rain_after_measurement_mm,0); wet=1.0*math.sqrt(rain)+0.08*rain
 dry_rate=.10+.006*max(temperature_c-18,0)+.018*max(wind_mps-1,0)+.035*sunshine_hours/max(target_hours,1)
 dry_hours=target_hours if rain==0 else min(max(hours_since_last_rain or 0,0),target_hours)
 mid=morning_moist+wet-dry_rate*dry_hours; hw=1.8+.18*math.sqrt(rain)
 return {'race_time_moisture_midpoint_heuristic':round(mid,2),'race_time_moisture_range_heuristic':[round(max(0,mid-hw),2),round(mid+hw,2)],'condition_probs_operational':{k:round(v,4) for k,v in condition_probs(mid,2.4).items()},'validation_status':'operational heuristic; not backtested'}

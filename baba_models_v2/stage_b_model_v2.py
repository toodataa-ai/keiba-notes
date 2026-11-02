"""Stage B v2: all information incl. the morning going (proxy = going of the day's first race on that surface).
Scored on non-reference races only. Compared with the 'morning persists' baseline."""
import json, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from stage_b_experiment import BASE, PREV, MORNING, WX, MORNING_WX, COURSE_NUM, COURSE_CAT, design, metrics

df = pd.read_csv('stage_b/stage_b_dataset.csv.gz', parse_dates=['date']).sort_values(['track','date','surface','race_no']).reset_index(drop=True)
g = df.groupby(['track','date','surface'])
df['morning'] = g['going_n'].transform('first'); df['is_ref'] = g.cumcount()==0
df['trans'] = g['going_n'].transform('nunique')>1
# other surface's morning going on the same day (known from the same morning notice)
oth = df[df.is_ref].pivot_table(index=['track','date'], columns='surface', values='going_n')
df = df.join(oth.rename(columns={'turf':'m_turf','dirt':'m_dirt'}), on=['track','date'])
df['morning_other'] = np.where(df.surface=='turf', df.m_dirt, df.m_turf)
df['hours_since_ref'] = df.start_h - g['start_h'].transform('first')
MOR = ['morning','morning_other','hours_since_ref']
SETS = {
 'G1 朝の馬場＋含水率＋前日':        (BASE+PREV+MORNING+MOR, []),
 'G2 ＋早朝までの実測気象（予報なし）': (BASE+PREV+MORNING+MORNING_WX+['start_h','race_no']+MOR, []),
 'G3 ＋当日の実測気象（完全予報＝上限）': (BASE+PREV+MORNING+WX+MOR, []),
 'G4 ＋コース（内外・A〜D・距離）':      (BASE+PREV+MORNING+WX+MOR+COURSE_NUM, COURSE_CAT),
}
def fit(tr, te, nums, cats):
    Xtr=design(tr,nums,cats); Xte=design(te,nums,cats,Xtr.columns)
    m=HistGradientBoostingClassifier(max_depth=4,learning_rate=0.05,max_iter=200,l2_regularization=1.0,min_samples_leaf=30,random_state=0).fit(Xtr,tr.going_n)
    P=np.zeros((len(te),4)); pr=m.predict_proba(Xte)
    for j,c in enumerate(m.classes_): P[:,c]=pr[:,j]
    P=np.clip(P,1e-6,1); return P/P.sum(1,keepdims=True)
out={}
for surface in ('turf','dirt'):
    d=df[df.surface==surface].reset_index(drop=True); parts=[]
    for y in (2023,2024,2025,2026):
        tr,te=d[d.year<y],d[d.year==y].copy()
        C=np.ones((4,4))
        for m,a in zip(tr.morning,tr.going_n): C[m,a]+=1
        C/=C.sum(1,keepdims=True); te['P_base']=list(C[te.morning.values])
        for k,(n,c) in SETS.items(): te['P_'+k[:2]]=list(fit(tr,te,n,c))
        parts.append(te)
    t=pd.concat(parts); t=t[~t.is_ref]; y=t.going_n.values
    for lab,msk in (('全レース',np.ones(len(t),bool)),('途中で馬場が変わった日',t.trans.values),('変わらなかった日',~t.trans.values)):
        r={'n':int(msk.sum())}
        for c in ['base','G1','G2','G3','G4']:
            P=np.vstack(t['P_'+c].values)[msk]; m=metrics(y[msk],P); m['adjacent_acc']=float((np.abs(P.argmax(1)-y[msk])<=1).mean()); r[c]=m
        out.setdefault(surface,{})[lab]=r
    # per track (all races)
    for tr_ in sorted(t.track.unique()):
        mk=(t.track==tr_).values
        if mk.sum()<150: continue
        r={'n':int(mk.sum())}
        for c in ['base','G2','G3']:
            P=np.vstack(t['P_'+c].values)[mk]; r[c]=float(-np.log(P[np.arange(mk.sum()),y[mk]]).mean())
        out[surface].setdefault('競馬場別',{})[tr_]=r
json.dump(out,open('stage_b/model_v2.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
for s in out:
    for lab in ('全レース','途中で馬場が変わった日','変わらなかった日'):
        v=out[s][lab]; print(s,lab,v['n'])
        for k in ('base','G1','G2','G3','G4'):
            m=v[k]; print(f"  {k:5s} ll {m['logloss']:.3f} brier {m['brier']:.3f} acc {m['acc']:.3f} adj {m['adjacent_acc']:.3f}")
    for k,v in out[s]['競馬場別'].items(): print(' ',s,k,v['n'],'base %.3f G2 %.3f G3 %.3f'%(v['base'],v['G2'],v['G3']))

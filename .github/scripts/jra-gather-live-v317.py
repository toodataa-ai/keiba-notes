#!/usr/bin/env python3
"""Forward-only v3.17 adapter around the immutable v3.14 collector.
Correct official form clocks, create a Shadow signal; keep formal STEP1 unchanged.
"""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from jra_clock_v1 import recover,shadow_signal
spec=importlib.util.spec_from_file_location('immutable_jra_v314',HERE/'jra-gather-live-v314.py')
legacy=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=legacy
spec.loader.exec_module(legacy)
original_past_from=legacy.past_from

def corrected_past_from(cell,distance,surface,venue):
    return recover(original_past_from(cell,distance,surface,venue))

def entry():
    p=argparse.ArgumentParser()
    p.add_argument('--request',required=True)
    p.add_argument('--validate-only',action='store_true')
    args=p.parse_args()
    path=legacy.safe_path(args.request,'e2e_validation/requests/v317/')
    req=json.loads(path.read_text(encoding='utf8'))
    race,preview=legacy.validate_request(req)
    if args.validate_only:
        print('V317_REQUEST_VALID',race['slug'])
        return
    legacy.require_market_open(req,race)
    legacy.DATE=req['date']
    legacy.PREVIEW=Path(req['preview_path'])
    legacy.RACES=[race]
    legacy.past_from=corrected_past_from
    if req.get('official_snapshot_path'):
        orig_load=legacy.load
        evidence=legacy.safe_path(req['official_snapshot_path'],'e2e_validation/source-evidence/')
        def audited_load(url):
            if url==race['official']:
                raw=evidence.read_bytes()
                return raw,legacy.BeautifulSoup(raw,'html.parser')
            return orig_load(url)
        legacy.load=audited_load
    preview_race=next(x for x in preview['races'] if x['id']==race['slug'])
    output=legacy.build(race,preview_race)
    input_bytes=Path(output[0]).read_bytes()
    formal=json.loads(input_bytes)
    shadow=shadow_signal(formal['step1']['runners'],req['date'])
    shadow['race_id']=race['slug']
    shadow['source_input_sha256']=hashlib.sha256(input_bytes).hexdigest()
    target=Path('e2e_validation/clock-shadow-v1')/(race['slug']+'.json')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(shadow,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    Path('/tmp/jra-v314-actual-input-manifest.json').write_text(json.dumps({
        'date':req['date'],'request':str(path),'race_id':race['slug'],
        'input':output[0],'captures':output[1],'clock_shadow':str(target)
    },ensure_ascii=False))
    print('V317_SOURCE_COMPLETE',race['slug'],'input=',output[0],'shadow=',target)

if __name__=='__main__':
    try: entry()
    except Exception as error:
        print('JRA_V317_BLOCKER:',str(error),file=sys.stderr)
        sys.exit(1)

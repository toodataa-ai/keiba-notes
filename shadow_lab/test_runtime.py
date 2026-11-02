"""Meaningful trust-boundary regressions; fixtures never enter evidence counts."""
import copy
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from shadow_lab import runtime as rt

class RuntimeTests(unittest.TestCase):
    def test_all_seven_have_independent_current_candidates(self):
        self.assertEqual(len({rt.design(t)['challenger'] for t in rt.THEMES}),7)
        observation=rt.read(rt.ROOT/'docs/data/jra_improvement_cycle_v1.json')
        young=next(h for h in observation['formal']['hypotheses'] if h['id']=='field_experience')
        self.assertEqual(rt.gate('field_experience'),
                         young['next_decision']['screening']['ready_to_design_experiment'])
        self.assertTrue(rt.gate('E0')) # probability shortage must not deadlock collection

    def test_retroactive_preparation_blocked_for_every_theme(self):
        packet={'official_purchase_path':'e2e_validation/predictions/2026-10-31-fantasy-stakes/v3.15-run41143733649-attempt1-sealed.json',
                'baseline_path':'e2e_validation/predictions/2026-10-31-fantasy-stakes/v3.13-run41143212430-attempt1.json',
                'input_path':'e2e_validation/inputs/v313/2026-10-31-fantasy-stakes.json','information_cutoff_at':'2026-10-31T08:00:00+09:00'}
        for theme in rt.THEMES:
            with self.subTest(theme=theme),self.assertRaisesRegex(ValueError,'start_passed'):
                rt.make_pair(packet,theme)

    def test_no_naive_or_nonfinite_values(self):
        with self.assertRaises(ValueError):rt.when('2026-11-01T10:00:00')
        for value in (True,float('nan'),float('inf'),-1,1.1):
            with self.assertRaises(ValueError):rt.finite(value)

    def test_path_escape_rejected(self):
        for p in ('../test','/tmp/test'):
            with self.assertRaises(ValueError):rt.safe(p)

    def test_feature_digest_and_cutoff(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(rt,'ROOT',Path(tmp)):
            p=Path(tmp)/'evidence.json';p.write_text('{}')
            source={'path':'evidence.json','sha256':rt.digest(p.read_bytes()),'url':'https://www.jra.go.jp/test','observed_at':'2026-10-01T00:00:00Z'}
            rt.source(source,rt.when('2026-10-02T00:00:00Z'))
            p.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError,'digest'):rt.source(source,rt.when('2026-10-02T00:00:00Z'))

    def proof_fixture(self,root):
        subprocess.run(['git','init','-q',str(root)],check=True)
        subprocess.run(['git','-C',str(root),'config','user.name','test'],check=True)
        subprocess.run(['git','-C',str(root),'config','user.email','test@example.invalid'],check=True)
        for name in ('runtime.py','candidate.mjs'):
            path=root/'shadow_lab'/name;path.parent.mkdir(exist_ok=True);path.write_text(name)
        pair={'theme':'pace_positioning','race_id':'fixture','information_cutoff_at':'2026-11-01T00:00:00Z',
              'generated_at':'2026-11-01T00:01:00Z','scheduled_start_at':'2026-11-01T06:00:00Z','sources':{},'packet':{},
              'baseline':{'race_id':'fixture','race_context':{}},
              'candidate':{'race_id':'fixture','race_context':{},'prompt_version':'v3.13-pace-positioning-shadow-v0.1-runtime1'},
              'code_sha256':None}
        with patch.object(rt,'ROOT',root):pair['code_sha256']=rt.code_digest()
        path=rt.DATA+'/pairs/pace_positioning/fixture.json';rt.dump(root/path,pair)
        subprocess.run(['git','-C',str(root),'add','.'],check=True)
        subprocess.run(['git','-C',str(root),'commit','-qm','fixture'],check=True)
        sha=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
        receipt={'proof_commit':sha,'repository':rt.REPO,'pair_path':path,'pair_sha256':rt.digest((root/path).read_bytes()),
                 'status_id':1,'status_created_at':'2026-11-01T00:02:00Z'}
        status={'id':1,'created_at':receipt['status_created_at'],'state':'success','context':'shadow/prestart-sealed'}
        return receipt,status

    def test_real_git_objects_and_server_attestation_required(self):
        actual_design=rt.design('pace_positioning')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);receipt,status=self.proof_fixture(root)
            with patch.object(rt,'ROOT',root),patch.object(rt,'design',return_value=actual_design):
                self.assertEqual(rt.audit(receipt,lambda sha:[status])['race_id'],'fixture')
                with self.assertRaisesRegex(ValueError,'status_missing'):rt.audit(receipt,lambda sha:[])
                late={**status,'created_at':'2026-11-01T06:00:00Z'}
                with self.assertRaisesRegex(ValueError,'grade_A'):rt.audit(receipt,lambda sha:[late])
                (root/receipt['pair_path']).write_text('{}')
                with self.assertRaisesRegex(ValueError,'changed_since_proof'):rt.audit(receipt,lambda sha:[status])

    def case_fixture(self):
        p={'race_id':'fixture','theme':'E0','week':'2026-10-26','conditions':{},'scheduled_start_at':'2026-10-01T00:00:00Z',
           'metadata':{'groups':{'1':'E0','2':'E1','3':'E2','4':'E0'}}}
        probs={'win':{'1':.4,'2':.3,'3':.2,'4':.1},'top3':{'1':.9,'2':.8,'3':.7,'4':.6}}
        p['probabilities']={s:copy.deepcopy(probs) for s in ('baseline','candidate')}
        for s in ('baseline','candidate'):
            p[s]={'step1_ranking':[{'horse_number':int(n),'win_probability':v} for n,v in probs['win'].items()],
                  'final_bets':[{'type':'単勝','selection':[1],'stake_yen':100}]}
        r={'race_id':'fixture','observed_at':'2026-10-01T01:00:00Z','source_url':'https://www.jra.go.jp/result',
           'finish_order':[1,2,3,4],'dead_heat':False,'payouts':{t:[] for t in ('単勝','複勝','枠連','馬連','馬単','ワイド','三連複','三連単')}}
        r['payouts']['単勝']=[{'selection':[1],'yen_per_100':250}]
        return p,r

    def test_official_results_metrics_and_roi(self):
        p,r=self.case_fixture()
        with tempfile.TemporaryDirectory() as tmp,patch.object(rt,'ROOT',Path(tmp)):
            cap=Path(tmp)/'result.json';rt.dump(cap,r)
            r.update(capture_path='result.json',capture_sha256=rt.digest(cap.read_bytes()))
            case=rt.settle(p,r);m=rt.summarize([case])
            self.assertEqual(m['baseline']['roi'],2.5)
            self.assertEqual(m['candidate']['honmei_top3_rate'],1)
            self.assertAlmostEqual(case['sides']['baseline']['horses'][0]['win_brier'],.36)
            r['finish_order']=[4,3,2,1]
            with self.assertRaisesRegex(ValueError,'bound_to_capture'):rt.settle(p,r)

    def test_duplicate_results_and_scratch_fail_closed(self):
        p,r=self.case_fixture()
        r['finish_order']=[1,2,3]
        with tempfile.TemporaryDirectory() as tmp,patch.object(rt,'ROOT',Path(tmp)):
            cap=Path(tmp)/'result.json';rt.dump(cap,r)
            r.update(capture_path='result.json',capture_sha256=rt.digest(cap.read_bytes()))
            with self.assertRaisesRegex(ValueError,'scratch'):rt.settle(p,r)

    def test_no_zero_evidence_auto_approval(self):
        result=rt.status()
        self.assertEqual(len(result['experiments']),7)
        self.assertTrue(all(not x['adopted'] and not x['automatic_promotion'] for x in result['experiments']))

    def test_manual_approval_needs_actual_owner_comment_and_cannot_skip_threshold(self):
        actual_design=rt.design('pace_positioning'); metrics=rt.summarize([])
        with tempfile.TemporaryDirectory() as tmp,patch.object(rt,'ROOT',Path(tmp)),patch.object(rt,'design',return_value=actual_design):
            root=Path(tmp);report=root/'report.json';report.write_text('{}')
            token={'theme':'pace_positioning','candidate':actual_design['challenger']+'-runtime1','classification':'C','decision':'rejected',
                   'metrics_sha256':rt.digest(json.dumps(metrics,sort_keys=True,separators=(',',':')).encode())}
            record={'decision':token,'report_path':'report.json','report_sha256':rt.digest(report.read_bytes()),'github_comment_id':7}
            path=root/rt.DATA/'reviews/pace_positioning.json';rt.dump(path,record)
            comment={'user':{'login':'toodataa-ai'},'body':'SHADOW_DECISION '+json.dumps(token,sort_keys=True,separators=(',',':')),'html_url':'https://github.com/test'}
            self.assertEqual(rt.approval_state('pace_positioning',False,metrics,lambda id_:comment)[0],'rejected')
            comment['user']['login']='someone-else'
            with self.assertRaisesRegex(ValueError,'owner_approval'):rt.approval_state('pace_positioning',False,metrics,lambda id_:comment)
            token['decision']='approved_for_release';rt.dump(path,{**record,'decision':token})
            with self.assertRaisesRegex(ValueError,'threshold'):rt.approval_state('pace_positioning',False,metrics,lambda id_:comment)

    def test_research_thresholds_independent_and_not_interchangeable(self):
        cases=[]
        for i in range(3):
            cases.append({'race_id':str(i),'week':'2026-10-26' if i<2 else '2026-11-02',
                          'sides':{'baseline':{'horses':[{'group':'E0'} for _ in range(10)]}}})
        self.assertEqual(rt.diagnostic_counts(cases,'E0'),(30,3,2,True))
        self.assertFalse(rt.diagnostic_counts(cases,'E1')[3])
        self.assertFalse(rt.diagnostic_counts(cases[:2],'E0')[3])
        for c in cases:c['week']='2026-10-26'
        self.assertFalse(rt.diagnostic_counts(cases,'E0')[3])

    def test_all_research_groups_generate_without_formal_betting_or_nine_runner_gate(self):
        actual_root=rt.ROOT
        designs={t:rt.design(t) for t in ('E0','E1','E2')}
        with tempfile.TemporaryDirectory() as tmp,patch.object(rt,'ROOT',Path(tmp)),patch.object(rt,'design',side_effect=lambda t:designs[t]):
            root=Path(tmp)
            config=root/'experience_regime_v1/config.json';config.parent.mkdir()
            config.write_bytes((actual_root/'experience_regime_v1/config.json').read_bytes())
            pool={'week_id':'2099-01-03','races':[{'race_id':'2099-test','race_no':1,'date':'2099-01-03','venue':'東京',
                  'race_category':'maiden','official_prediction':True,'start_at':'2099-01-03T10:00:00+09:00'}]}
            week=root/'experience_regime_v1/collection/2099-01-03';week.mkdir(parents=True)
            rt.dump(week/'race_pool.json',pool)
            rt.dump(week/'sample_plan.json',rt.select_races(pool,rt.load_sampling_policy(config)))
            frozen='experience_regime_v1/step1_frozen/2099-01-03/2099-test.json'
            forecast={'race_id':'2099-test','step1_fixed_at':'2026-10-31T00:00:00Z','no_odds_used':True,'no_synthetic_predictions':True,
                      'runners':[{'horse_number':i,'predicted_win_probability':.25,'predicted_top3_probability':.75} for i in range(1,5)]}
            rt.dump(root/frozen,forecast)
            evidence=root/'career.json';rt.dump(evidence,{'test_only':True})
            for name in ('runtime.py','candidate.mjs'):rt.dump(root/'shadow_lab'/name,{})
            packet={'research_snapshot_path':frozen,'sample_plan_path':str((week/'sample_plan.json').relative_to(root)),
                    'information_cutoff_at':forecast['step1_fixed_at'],'features':{'experience':{'path':'career.json',
                    'sha256':rt.digest(evidence.read_bytes()),'url':'https://www.jra.go.jp/test-fixture','observed_at':'2026-10-30T23:00:00Z',
                    'starts_by_horse':{'1':0,'2':1,'3':4,'4':2}}}}
            for group in designs:
                result=rt.research_pair(packet,group,rt.now())
                self.assertEqual(result['baseline']['final_bets'],[])
                self.assertAlmostEqual(sum(result['probabilities']['candidate']['win'].values()),1)
                self.assertAlmostEqual(sum(result['probabilities']['candidate']['top3'].values()),3)
                self.assertTrue(result['metadata']['research_only'])

if __name__=='__main__':unittest.main()

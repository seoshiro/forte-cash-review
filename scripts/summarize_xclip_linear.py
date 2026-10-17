"""Safe aggregate arithmetic and code-hash check; never read private OOF rows."""
from pathlib import Path
import json,hashlib,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.private/xclip-linear-control'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path=OUT/'safe-summary.json';r=json.loads(path.read_text());t=json.loads((OUT/'run/terminal-safe-summary.json').read_text())
    assert r['status']=='completed' and r['technical_monitor_validated']
    assert t['status']=='completed' and t['worker_exit_code']==0 and t['cleanup_complete'] and t['worker_report_valid']
    assert t['quality_gate_passed'] and not t['deadline_exceeded']
    assert t['completed_cases']==t['passed_cases']==t['expected_cases']==24
    assert r['train_unique_contents']==26 and r['train_auto_groups']==24 and not r['tune_used'] and not r['holdout_used']
    assert not r['media_opened'] and not r['new_gpu_inference'] and not r['baseline_or_deployment_pack_changed']
    code=json.loads((OUT/'registration.json').read_text())['code_sha256']
    assert all(sha(ROOT/name)==value for name,value in code.items())
    a=r['results']['baseline'];b=r['results']['linear_head'];p=r['paired_point_diagnostic']
    def counts(x):
        cm=x['confusion_matrix_tn_fp_fn_tp'];tn,fp,fn,tp=[*cm[0],*cm[1]]
        assert sum((tn,fp,fn,tp))==26 and fn+tp==14 and tn+fp==12
        assert abs(2*tp/(2*tp+fp+fn)-x['f1'])<1e-12
        assert x['timestamp_matched_positive_videos']==tp and x['all_positive_candidate_point_count']==14
        return tn,fp,fn,tp
    ac=counts(a);bc=counts(b)
    assert max(0,ac[3]+bc[3]-14)<=p['common_true_positive_count']<=min(ac[3],bc[3])
    cfg=json.loads((ROOT/'config/xclip-linear-protocol.json').read_text());gate=cfg['binary_gate']
    binary=bc[2]<=gate['fn_max'] and bc[1]<=gate['fp_max'] and b['f1']>=gate['f1_min']
    point=bool(p['common_true_positive_count'] and b['all_positive_candidate_point_mae_sec']<=a['all_positive_candidate_point_mae_sec']
        and p['linear_candidate_point_mae_sec']<=p['baseline_candidate_point_mae_sec'])
    assert r['binary_gate_passed']==binary and r['point_non_regression_gate_passed']==point
    assert r['joint_useful_gate_passed']==bool(binary and point)
    tests=ET.parse(ROOT/'.private/reliability/xclip-linear-final-tests.xml').getroot()
    suites=list(tests.iter('testsuite'));totals={key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ['tests','errors','failures','skipped']}
    assert totals['tests']==294 and not any(totals[k] for k in ['errors','failures','skipped'])
    test_report={'status':'PASS',**totals,'junit_elapsed_sec':sum(float(s.attrib.get('time',0)) for s in suites),
        'scope':'Synthetic/unit/integration tests; no bank media or model loading; not detection quality',
        'known_warnings':'Starlette/httpx deprecation; sklearn/scipy ignored iprint verbosity option'}
    (OUT/'tests-safe-summary.json').write_text(json.dumps(test_report,indent=2))
    report={'status':'PASS','source_safe_summary_sha256':sha(path),'registration_sha256':sha(OUT/'registration.json'),
        'registered_source_file_count':len(code),'registered_code_unchanged':True,
        'derived_gates':{'binary':binary,'point_non_regression':point,'joint_useful':bool(binary and point)},
        'comparison':{'f1_delta':b['f1']-a['f1'],'fp_delta':bc[1]-ac[1],'fn_delta':bc[2]-ac[2],
            'all_positive_point_count':a['all_positive_candidate_point_count'],
            'all_positive_point_mae_delta_sec':b['all_positive_candidate_point_mae_sec']-a['all_positive_candidate_point_mae_sec'],
            'common_true_positive_count':p['common_true_positive_count'],
            'common_true_positive_point_mae_delta_sec':p['linear_candidate_point_mae_sec']-p['baseline_candidate_point_mae_sec']},
        'baseline_preserved':True,'new_gpu_inference':False,'media_opened':False,
        'monitor_wall_sec':t['elapsed_sec'],'tests':test_report}
    (OUT/'calculation-safe-summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))


if __name__=='__main__':
    try:main()
    except Exception as error:print(json.dumps({'status':'failed','technical_error_type':type(error).__name__}));raise SystemExit(1)

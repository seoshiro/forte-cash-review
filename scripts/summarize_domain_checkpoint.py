"""Aggregate regression/source checkpoint, explicitly separate from failed ML gates."""
from pathlib import Path
import sys,json,subprocess,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]


def main():
    suites=list(ET.parse(ROOT/'.private/reliability/domain-final-tests.xml').getroot().iter('testsuite'))
    tests={key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ['tests','errors','failures','skipped']}
    assert tests['tests']>0 and not any(tests[k] for k in ['errors','failures','skipped'])
    tests['elapsed_sec']=sum(float(s.attrib.get('time',0)) for s in suites)
    result=subprocess.run([sys.executable,'scripts/verify_rules.py'],cwd=ROOT,capture_output=True,check=True,text=True)
    verified=json.loads(result.stdout);assert verified['status']=='PASS' and not verified['network_used']
    audit=json.loads((ROOT/'.private/train-preparation-audit/safe-summary.json').read_text())
    model=json.loads((ROOT/'.private/xclip-temporal-control/safe-summary.json').read_text())
    assert audit['status']=='PASS' and model['status']=='completed' and not model['joint_useful_gate_passed']
    registry=json.loads((ROOT/'config/rules.json').read_text(encoding='utf-8'))
    inventory={'status':'source_linkage_verified_limits_retained','enabled_registry_entries':len(registry['rules']),
        'registered_source_urls':1,'accepted_semantic_detectors':sum(bool(r['semantic_detector_accepted']) for r in registry['rules']),
        'source_provenance_linkage_gap_open':False,'scope':'Direct official-source provenance verified; visual applicability/recognition unvalidated'}
    assert inventory['accepted_semantic_detectors']==0
    (ROOT/'.private/release/capability-inventory-safe-summary.json').write_text(json.dumps(inventory,indent=2))
    report={'status':'PASS','scope':'Engineering/source evidence checkpoint, not accepted detector quality','tests':tests,
        'fixed_input_validation_gaps':4,'existing_train_preparation_bug_found':False,'manifest_split_or_cache_regenerated':False,
        'official_source_linkage_verified':True,'model_useful_gate_passed':False,'tune_or_holdout_reused':False,
        'new_bank_frames_decoded':False,'public_synthetic_tunnel_repeated':False,'competition_service_ready':False}
    folder=ROOT/'.private/domain-checkpoint';folder.mkdir(exist_ok=True)
    (folder/'safe-summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))


if __name__=='__main__':
    try:main()
    except Exception as error:print(json.dumps({'status':'failed','technical_error_type':type(error).__name__}));sys.exit(1)

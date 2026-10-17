"""Completeness/provenance only. Never opens annotation text or media."""
from pathlib import Path
from collections import Counter
import argparse,json,hashlib,datetime,sys
ROOT=Path(__file__).resolve().parents[1]
STATUSES={'unknown','possibly_cloud_assisted','fresh_local_review_attested'}
USES={'training','prompt_construction','evaluation_ground_truth','model_selection','official_label_editing'}

def initialize(private,selected,registration_sha):
    path=Path(private)/'provenance-policy.json'
    if path.exists():return path
    data={'schema_version':1,'registration_sha256':registration_sha,'selected_cases':selected,
          'batch_status':'potential_cloud_assistance_disclosed','independent_expert_ground_truth':False,
          'allowed_uses':{key:False for key in sorted(USES)},'case_provenance':{str(i):'unknown' for i in range(1,selected+1)},
          'external_chat_contents_requested_or_read':False,'external_chat_deletion_verified':False}
    path.write_text(json.dumps(data,indent=2),encoding='utf-8');return path

def summarize(private,selected,registration_sha):
    private=Path(private);valid=False;counts=Counter({'unknown':selected})
    try:
        data=json.loads((private/'provenance-policy.json').read_text(encoding='utf-8'))
        flags=data['case_provenance']
        valid=(data.get('schema_version')==1 and data.get('registration_sha256')==registration_sha and data.get('selected_cases')==selected
               and data.get('batch_status')=='potential_cloud_assistance_disclosed' and data.get('independent_expert_ground_truth') is False
               and type(flags) is dict and set(flags)=={str(i) for i in range(1,selected+1)}
               and all(type(v) is str and v in STATUSES for v in flags.values())
               and data.get('allowed_uses')=={key:False for key in USES})
        if valid:counts=Counter(flags.values())
    except (OSError,ValueError,TypeError,KeyError):pass
    progress=json.loads((private/'progress-safe-summary.json').read_text(encoding='utf-8'))
    saved=progress.get('saved_cases')
    if type(saved) is not int or not 0<=saved<=selected:raise ValueError('Invalid aggregate completion counter')
    return {'scope':'Aggregate completeness/provenance only; no annotation contents read','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'selected_cases':selected,'saved_cases':saved,'remaining_cases':selected-saved,'provenance_record_valid':bool(valid),
            'provenance_counts':{key:counts[key] for key in sorted(STATUSES)},'manual_training_allowed':False,
            'manual_prompt_construction_allowed':False,'manual_evaluation_ground_truth_allowed':False,
            'manual_model_selection_allowed':False,'manual_official_label_editing_allowed':False,
            'manual_review_stopped':True,'completion_signal_required':False,
            'independent_expert_ground_truth':False,'official_labels_remain_evaluation_truth':True,
            'annotation_contents_read':False,'cloud_chat_contents_read':False,'external_chat_deletion_verified':False,
            'manual_annotation_model_runs_started':0,'holdout_opened':False}

def require_manual_use_allowed(use):
    if use not in USES:raise ValueError('Unknown manual annotation use')
    # Manual work was stopped; only aggregate completeness/provenance is allowed.
    # A local attestation does not silently enable any downstream use.
    raise RuntimeError('Manual annotation use is blocked by provenance policy')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--initialize',action='store_true')
    parser.add_argument('--quarantine',action='store_true');args=parser.parse_args()
    registration=ROOT/'.private/oracle-diagnostic-r1/registration.json'
    selected=len(json.loads(registration.read_text())['source_sha256']);sha=hashlib.sha256(registration.read_bytes()).hexdigest()
    private=ROOT/'.private/manual-review'
    if args.initialize:initialize(private,selected,sha)
    if args.quarantine:
        # Typed provenance only. Preserve the original proposals and journal.
        path=private/'provenance-policy.json';policy=json.loads(path.read_text(encoding='utf-8'))
        policy['allowed_uses']={key:False for key in sorted(USES)}
        policy['manual_review_status']='stopped_non_expert_potential_cloud_assistance'
        policy['completion_signal_required']=False
        path.write_text(json.dumps(policy,indent=2),encoding='utf-8')
    report=summarize(private,selected,sha)
    (ROOT/'.private/annotation-provenance-safe-summary.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))
if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'blocked','technical_error_type':type(error).__name__,'contents_emitted':False}));sys.exit(1)

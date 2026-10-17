"""Validate safe infrastructure/test aggregates only; never load credentials or jobs."""
from pathlib import Path
import json,hashlib,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]


def main():
    directory=ROOT/'.private/access-synthetic'
    result=json.loads((directory/'safe-summary.json').read_text())
    monitor=json.loads((directory/'run/terminal-safe-summary.json').read_text())
    rollback=json.loads((directory/'rollback-safe-summary.json').read_text())
    cleanup=json.loads((directory/'process-cleanup-safe-summary.json').read_text())
    assert result['status']=='PASS' and monitor['worker_exit_code']==0 and monitor['quality_gate_passed']
    assert monitor['cleanup_complete'] and monitor['worker_report_valid'] and not monitor['deadline_exceeded']
    assert rollback['owned_cleanup_confirmed'] and rollback['public_origin_no_longer_responds']
    assert cleanup['owned_origin_and_connector_stopped']
    for key in ['bank_data_used','secret_values_emitted','jury_key_created','new_cloudflare_account_credentials_created',
        'paid_resources_or_trials','os_firewall_warp_dns_or_service_changed','raw_connector_logs_collected','production_or_model_quality_claim']:
        assert result[key] is False
    assert result['strict_synthetic_results_completed']==2 and result['source_jpeg_checks']==3
    report={'status':'PASS','scope':'Synthetic-only HTTPS/auth/isolation/rollback; no active service or bank quality claim',
        'safe_summary_sha256':hashlib.sha256((directory/'safe-summary.json').read_bytes()).hexdigest(),
        'synthetic_completed_jobs':2,'source_jpeg_checks':3,'monitor_wall_sec':monitor['elapsed_sec'],
        'owned_cleanup_and_public_rollback_confirmed':True,'bank_data_used':False,'credentials_read':False}
    (directory/'calculation-safe-summary.json').write_text(json.dumps(report,indent=2))
    suites=list(ET.parse(ROOT/'.private/reliability/tune-public-final-tests.xml').getroot().iter('testsuite'))
    tests={key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ['tests','errors','failures','skipped']}
    assert tests['tests']>0 and not any(tests[key] for key in ['errors','failures','skipped'])
    tests.update(status='PASS',junit_elapsed_sec=sum(float(s.attrib.get('time',0)) for s in suites),
        scope='Unit/synthetic integration only; no bank media/model load/public tunnel in suite')
    out=ROOT/'.private/xclip-tune-control/tests-safe-summary.json';out.write_text(json.dumps(tests,indent=2))
    rules=json.loads((ROOT/'config/rules.json').read_text())
    inventory={'status':'documented_limits','enabled_registry_entries':sum(bool(r['enabled']) for r in rules['rules']),
        'registered_source_urls':1,'accepted_semantic_detectors':0,'scope':'Code inventory and explicit acceptance state, not legal/visual validation',
        'source_provenance_linkage_gap_open':True}
    (ROOT/'.private/release/capability-inventory-safe-summary.json').write_text(json.dumps(inventory,indent=2))
    print(json.dumps({'infrastructure':report,'tests':tests,'capability_inventory':inventory}))


if __name__=='__main__':
    try:main()
    except Exception as error:print(json.dumps({'status':'failed','technical_error_type':type(error).__name__}));raise SystemExit(1)

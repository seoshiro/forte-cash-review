import json
import pytest
from scripts.manual_provenance import initialize,summarize,require_manual_use_allowed

def test_default_unknown_provenance_is_blocked_and_never_reads_annotations(tmp_path):
    # Deliberately invalid raw annotation bytes: the summarizer must not open them.
    (tmp_path/'annotations.json').write_bytes(b'not valid JSON; synthetic forbidden-content sentinel')
    (tmp_path/'progress-safe-summary.json').write_text(json.dumps({'saved_cases':2}))
    path=initialize(tmp_path,8,'synthetic-registration')
    report=summarize(tmp_path,8,'synthetic-registration')
    assert report['provenance_record_valid'] and report['provenance_counts']['unknown']==8
    assert report['saved_cases']==2 and not report['annotation_contents_read']
    before=path.read_bytes();initialize(tmp_path,8,'synthetic-registration');assert path.read_bytes()==before
    for use in ['training','prompt_construction','evaluation_ground_truth','model_selection','official_label_editing']:
        with pytest.raises(RuntimeError,match='blocked'):require_manual_use_allowed(use)

def test_local_attestation_is_not_an_automatic_training_permission(tmp_path):
    (tmp_path/'progress-safe-summary.json').write_text(json.dumps({'saved_cases':8}))
    path=initialize(tmp_path,8,'synthetic-registration');data=json.loads(path.read_text())
    data['case_provenance']={str(i):'fresh_local_review_attested' for i in range(1,9)};path.write_text(json.dumps(data))
    report=summarize(tmp_path,8,'synthetic-registration')
    assert report['provenance_counts']['fresh_local_review_attested']==8
    assert not report['manual_training_allowed'] and not report['independent_expert_ground_truth']
    assert report['official_labels_remain_evaluation_truth']

def test_unexpected_free_text_in_provenance_fails_closed_without_echo(tmp_path):
    (tmp_path/'progress-safe-summary.json').write_text(json.dumps({'saved_cases':3}))
    path=initialize(tmp_path,8,'synthetic-registration');data=json.loads(path.read_text())
    data['case_provenance']['1']='synthetic untrusted free text must not appear in summary';path.write_text(json.dumps(data))
    report=summarize(tmp_path,8,'synthetic-registration')
    assert not report['provenance_record_valid'] and report['provenance_counts']['unknown']==8
    assert 'synthetic untrusted' not in json.dumps(report)

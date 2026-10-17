import numpy as np
import pytest
from hybrid_candidate.observer import parse,apply_rule,select_proposals
from hybrid_candidate.fixtures import CASES,frames


def facts(**changes):
    d={'area':'clear','motion':'left','service':'ongoing','context':'sufficient','f':3,'e':[0,3],'o':'Synthetic operator crosses the marked working area boundary.'};d.update(changes);return d


def test_rule_conditions_are_separate_from_presence_or_label():
    assert apply_rule(facts())=='R22'
    for changes in [{'motion':'stayed'},{'area':'unclear'},{'service':'completed'},{'service':'unclear'},
        {'context':'insufficient'},{'e':[3]},{'o':''}]:assert apply_rule(facts(**changes))=='no_event'


def test_structure_rejects_unverified_keys_and_invalid_support():
    import json
    assert parse(json.dumps(facts()))['e']==[0,3]
    for changes in [{'target':1},{'e':[0,4]},{'e':[0,0]},{'f':True}]:
        with pytest.raises(ValueError):parse(json.dumps(facts(**changes)))


def test_topk_includes_negative_margins_and_is_time_separated():
    f=np.array([[0,1],[.1,.9],[.2,.8],[.3,.7]],dtype=float);times=np.array([1.,2.,4.,7.])
    choices=select_proposals(f,times,np.array([1.,0.]),np.array([0.,1.]),2,3.)
    assert choices==[3,2] and abs(times[choices[0]]-times[choices[1]])>=3


def test_all_generated_fixtures_are_four_safe_frames():
    for case in CASES:
        values=frames(case)
        assert len(values)==4 and all(f.image.size==(384,384) for f in values)


def test_cache_coverage_rejects_omitted_and_unselected_inputs():
    from scripts.hybrid_experiment import check_cache_coverage
    rows=[{'sha256':'a'},{'sha256':'b'}]
    check_cache_coverage(rows,{'a.npz':'hash','b.npz':'hash'})
    for inventory in [{'a.npz':'hash'},{'a.npz':'hash','b.npz':'hash','c.npz':'hash'}]:
        with pytest.raises(ValueError):check_cache_coverage(rows,inventory)


def test_final_deadlines_reject_post_request_overrun():
    from scripts.hybrid_experiment import check_budget
    cfg={'budget':{'total_compute_sec':1800,'synthetic_total_sec':600,'train_total_sec':1200}}
    check_budget(cfg,0,synthetic=True,now=600)
    with pytest.raises(TimeoutError):check_budget(cfg,0,synthetic=True,now=600.01)
    with pytest.raises(TimeoutError):check_budget(cfg,0,train_start=600,now=1800.01)
    with pytest.raises(TimeoutError):check_budget(cfg,0,train_start=100,now=1300.01)


def test_verified_metadata_attaches_only_after_all_conditions():
    from scripts.hybrid_experiment import verified_event
    registry={'document':'Synthetic rule document','source':'https://example.invalid/rules',
        'rules':[{'id':'R22','enabled':True,'paragraph':'22','type':'Synthetic departure type'}]}
    sequence=frames(CASES[0]);event=verified_event(facts(),sequence,registry)
    assert event['timestamp_sec']==6 and event['type']=='Synthetic departure type'
    assert 'https://example.invalid/rules' in event['description']
    assert event['observation']==facts()['o']
    assert verified_event(facts(service='unclear'),sequence,registry) is None


def test_native_identity_rejects_replaced_executable(tmp_path,monkeypatch):
    import hashlib,json,zipfile
    import scripts.hybrid_experiment as experiment
    monkeypatch.setattr(experiment,'ROOT',tmp_path)
    runtime=tmp_path/'.private/llama-cuda124-b11712';runtime.mkdir(parents=True)
    downloads=tmp_path/'.private/gguf-preflight/downloads';downloads.mkdir(parents=True)
    (runtime/'llama-server.exe').write_bytes(b'official synthetic binary')
    archive=downloads/'official-test.zip'
    with zipfile.ZipFile(archive,'w') as z:z.write(runtime/'llama-server.exe','llama-server.exe')
    config=tmp_path/'config';config.mkdir()
    (config/'gguf-artifacts.json').write_text(json.dumps({'artifacts':[{'kind':'runtime','filename':archive.name,
        'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}]}))
    (downloads.parent/'safe-summary.json').write_text(json.dumps({'status':'artifacts_verified_not_benchmarked','server_path':str(runtime/'llama-server.exe')}))
    assert experiment.native_identity()
    (runtime/'llama-server.exe').write_bytes(b'replaced synthetic binary')
    with pytest.raises(ValueError):experiment.native_identity()


def test_attempt_claim_is_exclusive_and_preserves_existing_result(tmp_path,monkeypatch):
    import scripts.hybrid_experiment as experiment
    monkeypatch.setattr(experiment,'OUT',tmp_path);monkeypatch.setattr(experiment,'ATTEMPT_OWNED',False)
    experiment.claim_attempt();assert experiment.ATTEMPT_OWNED
    checkpoint=b'{"status":"completed","synthetic_gate_passed":false}'
    (tmp_path/'status.json').write_bytes(checkpoint)
    monkeypatch.setattr(experiment,'ATTEMPT_OWNED',False)
    with pytest.raises(FileExistsError):experiment.claim_attempt()
    assert not experiment.ATTEMPT_OWNED and (tmp_path/'status.json').read_bytes()==checkpoint

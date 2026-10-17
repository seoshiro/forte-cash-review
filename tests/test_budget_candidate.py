from types import SimpleNamespace
from io import BytesIO
from PIL import Image
import pytest
from scripts.synthetic import generate
from cashreview.video import sample
from budget_candidate.evidence import event_frames
from budget_candidate.runtime_guard import disable_artifact_loaders
import json
from pathlib import Path
from budget_candidate.engine import BudgetEngine
from cashreview.observations import ObservationError
from scripts.qa_model_api import verify_frames

def encoded(frame):
    buffer=BytesIO();frame.image.save(buffer,'JPEG',quality=85);return buffer.getvalue()

def test_batch_evidence_preserves_pts_and_jpeg_for_overlapping_edge_events(tmp_path):
    path=generate(tmp_path/'safe.mov',positive=True);duration=3.0;times=[0.,.01,1.0,1.02,2.85]
    batches=event_frames(path,times,duration)
    for timestamp,batch in zip(times,batches):
        original=sample(path,[max(0,timestamp-1),timestamp,min(duration-.1,timestamp+1)],960)
        assert [f.sec for f in batch]==[f.sec for f in original]
        assert [encoded(f) for f in batch]==[encoded(f) for f in original]
    assert event_frames(path,[],duration)==[]

def test_executable_artifact_loader_guard_rejects_before_loading():
    touched=[]
    def unsafe(*args,**kwargs):touched.append(True)
    fake=SimpleNamespace(load=unsafe,serialization=SimpleNamespace(load=unsafe),
                         jit=SimpleNamespace(load=unsafe),export=SimpleNamespace(load=unsafe))
    report=disable_artifact_loaders(fake)
    assert len(report['blocked_loaders'])==4
    for function in [fake.load,fake.serialization.load,fake.jit.load,fake.export.load]:
        with pytest.raises(RuntimeError,match='disabled'):function('untrusted.pt2')
    assert touched==[]

def fake_engine(observations):
    root=Path(__file__).resolve().parents[1];engine=object.__new__(BudgetEngine)
    engine.protocol=json.loads((root/'config/budget-protocol.json').read_text());engine.config=engine.protocol['candidate']
    engine.registry=json.loads((root/'config/rules.json').read_text(encoding='utf-8'));engine.precision='synthetic-test'
    engine.torch=SimpleNamespace(cuda=SimpleNamespace(reset_peak_memory_stats=lambda:None,
                  synchronize=lambda:None,max_memory_allocated=lambda:0,max_memory_reserved=lambda:0))
    engine.calls=[]
    def observe(frames,max_events,token_limit,deadline):
        engine.calls.append((len(frames),max_events,token_limit))
        result=observations.pop(0)
        if isinstance(result,Exception):raise result
        return result
    engine.observe=observe
    return engine

def test_bounded_sequence_refines_only_one_event_and_preserves_other_evidence(tmp_path):
    root=Path(__file__).resolve().parents[1];rules=[r['id'] for r in json.loads((root/'config/rules.json').read_text(encoding='utf-8'))['rules'] if r['enabled']]
    def event(rule,t,confidence):return {'rule_id':rule,'timestamp_sec':t,'confidence':confidence,
       'all_conditions_visible':True,'observation':'Искусственный тест.','limitation':''}
    engine=fake_engine([{'events':[event(rules[0],1.,.95),event(rules[1],1.4,.85)],'limitation':''},
                        {'events':[],'limitation':'Тест'}])
    path=generate(tmp_path/'artificial.mov',positive=True)
    result=engine.analyze(path,'safe-synthetic-job',tmp_path/'private')
    assert engine.calls==[(8,3,384),(4,1,192)]
    assert result['verdict']=='violation' and len(result['violations'])==1
    assert verify_frames(path,result)>=1
    assert not engine.calls or len(engine.calls)<=2

def test_model_contract_failure_remains_technical_failure(tmp_path):
    engine=fake_engine([ObservationError('invalid_budget_structure')])
    path=generate(tmp_path/'artificial.mov',positive=False)
    with pytest.raises(ObservationError,match='invalid_budget_structure'):
        engine.analyze(path,'safe-synthetic-job',tmp_path/'private')
    assert not (tmp_path/'private/result.json').exists()

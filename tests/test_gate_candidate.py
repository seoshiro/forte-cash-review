import json,time
from pathlib import Path
from types import SimpleNamespace
import pytest
from gate_candidate.engine import GatedEngine,parse_gate
from budget_candidate.engine import BudgetEngine
from cashreview.observations import ObservationError
from scripts.synthetic import generate

@pytest.mark.parametrize('text',['{"visible_violation":0}','{"visible_violation":"false"}','{"visible_violation":false,"extra":1}','unfinished'])
def test_invalid_gate_is_technical_failure(text):
    with pytest.raises(ObservationError,match='invalid_observable_gate'):parse_gate(text)

def fake_engine(decision):
    root=Path(__file__).resolve().parents[1];engine=object.__new__(GatedEngine)
    engine.protocol=json.loads((root/'config/budget-protocol.json').read_text());engine.config=engine.protocol['candidate']
    engine.registry=json.loads((root/'config/rules.json').read_text(encoding='utf-8'));engine.precision='synthetic-test';engine.telemetry=[];engine.gate_calls=[]
    engine.torch=SimpleNamespace(cuda=SimpleNamespace(reset_peak_memory_stats=lambda:None,synchronize=lambda:None,max_memory_allocated=lambda:0,max_memory_reserved=lambda:0))
    def decide(frames,deadline):
        if isinstance(decision,Exception):raise decision
        engine.gate_calls.append({'frames':len(frames),'visible_violation':decision});return decision
    engine.decide=decide
    return engine

def test_negative_gate_skips_detail_and_preserves_scope(tmp_path,monkeypatch):
    monkeypatch.setattr(BudgetEngine,'observe',lambda *a,**k:pytest.fail('Negative gate must not request detail'))
    engine=fake_engine(False);path=generate(tmp_path/'synthetic.mov',positive=False)
    result=engine.analyze(path,'synthetic-negative',tmp_path/'private')
    assert result['verdict']=='no_violation' and result['violations']==[]
    assert len(engine.gate_calls)==1
    detail=json.loads((tmp_path/'private/detail.json').read_text(encoding='utf-8'))
    assert any('не доказывает' in limitation for limitation in detail['limitations'])

def test_positive_gate_does_not_create_an_unsupported_event(tmp_path,monkeypatch):
    calls=[]
    def observe(*args,**kwargs):calls.append(True);return {'events':[],'limitation':'Синтетический тест'}
    monkeypatch.setattr(BudgetEngine,'observe',observe)
    engine=fake_engine(True);path=generate(tmp_path/'synthetic.mov',positive=True)
    result=engine.analyze(path,'synthetic-positive-gate',tmp_path/'private')
    assert calls==[True] and result['verdict']=='no_violation' and result['violations']==[]

def test_malformed_gate_never_turns_into_negative_result(tmp_path):
    engine=fake_engine(ObservationError('invalid_observable_gate'));path=generate(tmp_path/'synthetic.mov',positive=False)
    with pytest.raises(ObservationError):engine.analyze(path,'synthetic-failed-gate',tmp_path/'private')
    assert not (tmp_path/'private/result.json').exists()

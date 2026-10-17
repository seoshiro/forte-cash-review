"""Synthetic code checks: legal applicability/exclusion gates, no banking footage."""
from pathlib import Path
import json
import pytest
from PIL import Image
from cashreview.video import Sample
from budget_candidate.engine import BudgetEngine,ROOT
from gguf_candidate.engine import GGUFEngine

class FakeNative:
    def __init__(self,event=None,decision=True):self.event=event;self.decision=decision;self.calls=0
    def complete(self,*args):
        self.calls+=1
        data={'visible_violation':self.decision} if self.calls==1 else {'events':[self.event], 'limitation':''}
        return json.dumps(data),{'generation_sec':0.}

def engine_for(event=None,decision=True):
    engine=object.__new__(GGUFEngine)
    engine.protocol=json.loads((ROOT/'config/budget-protocol.json').read_text())
    engine.config=engine.protocol['candidate'];engine.registry=json.loads((ROOT/'config/rules.json').read_text(encoding='utf-8'))
    engine.telemetry=[];engine.gate_calls=[];engine.server=FakeNative(event,decision);engine.precision='synthetic-code-test'
    engine.reset_resources=lambda:None;engine.resource_metrics=lambda:{}
    return engine

@pytest.mark.parametrize('exclusion,visible,confidence', [('unknown',True,.95),('present',True,.95),('absent',False,.95),('absent',True,.79)])
def test_nonqualifying_event_cannot_reach_evidence_or_api(monkeypatch,tmp_path,exclusion,visible,confidence):
    event={'r':'R22','f':'F0','c':confidence,'v':visible,'x':exclusion,'o':'Synthetic observation'}
    engine=engine_for(event)
    monkeypatch.setattr('budget_candidate.engine.validate_input',lambda _: {'duration_sec':10.})
    monkeypatch.setattr('budget_candidate.engine.sample',lambda *args:[Sample(float(i),Image.new('RGB',(16,16))) for i in range(4)])
    def evidence(_path,times,_duration):
        assert times==[]
        return []
    monkeypatch.setattr('budget_candidate.engine.event_frames',evidence)
    result=BudgetEngine.analyze(engine,tmp_path/'unused.mov','synthetic-job',tmp_path)
    assert result['verdict']=='no_violation' and result['violations']==[]

def test_negative_gate_does_not_fabricate_detail():
    engine=engine_for(decision=False)
    result=engine.observe([Sample(0.,Image.new('RGB',(16,16)))],2,192,99999999)
    assert result['events']==[] and engine.server.calls==1

def test_invented_rule_is_rejected_before_result_mapping():
    engine=engine_for({'r':'UNVERIFIED','f':'F0','c':.99,'v':True,'x':'absent','o':'Synthetic observation'})
    with pytest.raises(ValueError):engine.observe([Sample(0.,Image.new('RGB',(16,16)))],2,192,99999999)
